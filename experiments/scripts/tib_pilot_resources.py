"""Numeric pilot-only allocations, shared session accounting and resource sampling."""
import importlib.metadata
import fnmatch
import json
import math
import os
from pathlib import Path
import shutil
import threading
import time

from .tib_benchmark_checkpoint import digest


ALLOCATION_FIELDS = ('total_gpu_hours total_cpu_hours total_wall_hours max_sessions session_wall_hours '
    'persistent_storage_bytes minimum_local_free_bytes local_working_storage_bytes transfer_bytes checkpoint_bytes '
    'checkpoint_flush_seconds recovery_time_hours retry_limit_per_node retry_cost_reserve '
    'session_headroom_fraction scoring_gpu_hours scoring_cpu_hours scoring_wall_hours '
    'transfer_wall_hours checkpoint_wall_hours pilot_metric_tuning_trial_cap_per_candidate '
    'pilot_feasibility_probe_cap_per_candidate pilot_total_profile_cap').split()
GIB = 1024 ** 3
GENERATION_PINS = {'torch': '2.11.0+cu130', 'numpy': '2.1.3', 'transformers': '4.57.6',
    'huggingface-hub': '0.36.2', 'accelerate': '1.15.0', 'tokenizers': '0.22.2',
    'safetensors': '0.8.0', 'psutil': '5.9.5', 'scikit-learn': '1.6.1'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def allocated(value, wall_hours):
    require(value.get('state') == 'ALLOCATED', 'REQUIRED_NO_START: explicit pilot allocation missing')
    for key in ALLOCATION_FIELDS:
        n = value.get(key)
        require(type(n) in (int, float) and math.isfinite(n) and n >= 0, 'Numeric allocation required: ' + key)
    for key in ('retry_limit_per_node', 'retry_cost_reserve', 'pilot_metric_tuning_trial_cap_per_candidate',
                'pilot_feasibility_probe_cap_per_candidate'):
        require(value[key] == 0, 'No retry or search authorized: ' + key)
    require(value['pilot_total_profile_cap'] == 5, 'Exactly five fixed profiles required')
    require(value['max_sessions'] >= 1 and float(value['max_sessions']).is_integer(), 'Invalid session count')
    require(0 < wall_hours <= 11.5 and 0 < value['session_wall_hours'] <= 11.5, '11.5h session bound')
    require(0 <= value['session_headroom_fraction'] < 1, 'Invalid headroom')
    require(value['minimum_local_free_bytes'] >= 32*GIB and value['local_working_storage_bytes'] > 0,
            'At least32GiB free disk and positive working storage cap required')
    require(all(value[k] > 0 for k in ('total_wall_hours', 'total_cpu_hours', 'persistent_storage_bytes',
                                     'checkpoint_bytes')), 'Positive operating quota required')
    require(value['checkpoint_flush_seconds'] > 0 or
            value.get('checkpoint_flush_policy') == 'fsync_after_every_committed_node',
            'Zero flush interval requires fsync after every committed node')
    return value


def atomic_json(path, payload):
    path = Path(path)
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False).encode()
    temporary = path.with_suffix(path.suffix + '.partial')
    started = time.perf_counter()
    with temporary.open('wb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)
    return len(raw), time.perf_counter() - started


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text(encoding='utf-8').strip()


class PilotBudget:
    """Shared sequential candidate ledger; session setup time is never reset."""
    def __init__(self, output, allocation, candidate, wall_hours, *, dependencies=None):
        self.output, self.allocation, self.candidate = Path(output), allocated(allocation, wall_hours), candidate
        self.dependencies = dependencies
        self.path = self.output.parent/'resource_ledger.json'
        self.ledger = json.loads(self.path.read_text(encoding='utf-8'))
        self.clock = dependencies.clock if dependencies else time.monotonic
        self.cpu_clock = dependencies.cpu_clock if dependencies else time.process_time
        require(self.ledger['allocation_sha256'] == digest(allocation), 'Allocation/ledger identity mismatch')
        require(self.ledger['boot_id'] == (dependencies.boot_id if dependencies else boot_id()), 'Session boot changed')
        for field in ('cpu_seconds', 'gpu_seconds', 'transfer_bytes', 'checkpoint_bytes', 'checkpoint_flush_seconds'):
            require(type(self.ledger.get(field)) in (int, float) and math.isfinite(self.ledger[field]) and
                    self.ledger[field] >= 0, 'Invalid ledger: ' + field)
        require(isinstance(self.ledger.get('candidate_runs'), list), 'Invalid candidate ledger')
        self.started, self.cpu_started = self.clock(), self.cpu_clock()
        self.initial_cpu, self.initial_gpu = self.ledger['cpu_seconds'], self.ledger['gpu_seconds']
        self.storage_snapshot = None
        start = self.ledger['session_started_monotonic']
        require(type(start) in (int, float) and math.isfinite(start) and start <= self.started, 'Invalid session clock')
        require(len(self.ledger['session_runs']) <= allocation['max_sessions'], 'Authorized session count exceeded')
        self.session_remaining_wall = (allocation['total_wall_hours']-allocation['recovery_time_hours']-
                                      allocation['scoring_wall_hours'])*3600-self.ledger['completed_session_wall_seconds']
        self.deadline = min(self.started+wall_hours*3600,
                            start+min(allocation['session_wall_hours']*3600,
                                      self.ledger['session_limit_seconds'])*(1-allocation['session_headroom_fraction']),
                            start+self.session_remaining_wall)

    def usage(self):
        self.ledger['cpu_seconds'] = self.initial_cpu + max(0, self.cpu_clock()-self.cpu_started)
        self.ledger['gpu_seconds'] = max(self.initial_gpu,
            self.ledger['completed_session_wall_seconds']+max(0, self.clock()-self.ledger['session_started_monotonic']))
        self.ledger['measured_neural_candidate_wall_seconds'] = max(0, self.clock()-self.started) if self.candidate in (
            'bart', 'led', 'qwen3') else 0

    def guard(self, *, check_memory=True, forecast_seconds=0, checkpoint_reserve_bytes=0):
        self.usage()
        a, l = self.allocation, self.ledger
        require(math.isfinite(forecast_seconds) and forecast_seconds >= 0, 'Invalid node forecast')
        require(self.clock()+forecast_seconds < self.deadline, 'Pilot wall quota/headroom reached')
        require(l['cpu_seconds']+forecast_seconds*2 < (a['total_cpu_hours']-a['scoring_cpu_hours'])*3600,
                'Reserved scorer CPU budget protected')
        require(l['gpu_seconds']+forecast_seconds < (a['total_gpu_hours']-a['scoring_gpu_hours'])*3600,
                'Reserved scorer GPU budget protected')
        if a['checkpoint_wall_hours'] > 0:
            require(l['checkpoint_flush_seconds'] < a['checkpoint_wall_hours']*3600, 'Checkpoint flush wall quota reached')
        require(l['checkpoint_bytes']+checkpoint_reserve_bytes <= a['checkpoint_bytes'], 'Projected checkpoint quota reached')
        for used, quota, scale in (
                                  ('transfer_bytes', 'transfer_bytes', 1), ('checkpoint_bytes', 'checkpoint_bytes', 1)):
            require(l[used] < a[quota]*scale or l[used] == a[quota]*scale == 0, 'Pilot quota reached: ' + used)
        if self.dependencies:
            return
        import psutil
        working = Path(l['local_working_root'])
        require(working.is_absolute() and working.is_relative_to(Path('/content')), 'Invalid local cache root')
        if self.storage_snapshot is None or self.clock()-self.storage_snapshot['at'] >= 10:
            self.storage_snapshot = {'at': self.clock(), 'checkpoint_bytes': l['checkpoint_bytes'],
                'local_free': shutil.disk_usage('/content').free,
                'working_bytes': sum(p.stat().st_size for p in working.rglob('*') if p.is_file()),
                'drive_free': shutil.disk_usage(self.output.parent).free,
                'stored_bytes': sum(p.stat().st_size for p in self.output.parent.rglob('*') if p.is_file())}
        disk = self.storage_snapshot
        growth = max(0, l['checkpoint_bytes']-disk['checkpoint_bytes'])+checkpoint_reserve_bytes
        require(disk['local_free'] >= a['minimum_local_free_bytes'], 'Local free working storage quota')
        require(disk['working_bytes'] <= a['local_working_storage_bytes'], 'Local working storage cap reached')
        require(disk['drive_free']-growth >= a['persistent_storage_bytes'], 'Drive free storage quota')
        require(disk['stored_bytes']+growth < a['persistent_storage_bytes'], 'Persistent pilot storage quota reached')
        if check_memory:
            require(psutil.virtual_memory().available >= 2*GIB, 'Host available memory below2GiB')
            if self.candidate in ('bart', 'led', 'qwen3'):
                import torch
                require(torch.cuda.mem_get_info()[0] >= GIB, 'VRAM available below1GiB')

    def flush(self, *, bytes_added=0, flush_seconds=0, final=False):
        self.usage()
        self.ledger['checkpoint_bytes'] += bytes_added
        self.ledger['checkpoint_flush_seconds'] += flush_seconds
        self.ledger['session_elapsed_wall_seconds'] = max(0, self.clock()-self.ledger['session_started_monotonic'])
        self.ledger['last_heartbeat_monotonic'] = self.clock()
        if final:
            self.ledger['candidate_runs'].append({'candidate_id': self.candidate,
                'wall_seconds': self.clock()-self.started, 'cpu_seconds': self.cpu_clock()-self.cpu_started})
        atomic_json(self.path, self.ledger)


def runtime_environment(candidate):
    import psutil
    versions = {p: importlib.metadata.version(p) for p in GENERATION_PINS}
    require(versions == GENERATION_PINS, 'Exact pilot runtime package pins required')
    require(Path('/content').is_dir(), 'Actual Colab required')
    import torch
    require(torch.cuda.is_available() and torch.cuda.get_device_name(0) in (
        'Tesla T4', 'NVIDIA T4', 'NVIDIA Tesla T4'), 'Actual Colab T4 required for pilot session')
    result = {'packages': {k: versions[k] for k in ('torch', 'transformers', 'huggingface-hub', 'numpy')},
              'runtime_dependencies': {k: versions[k] for k in ('accelerate', 'tokenizers', 'safetensors', 'psutil')},
              'cpu_packages': {k: versions[k] for k in ('numpy', 'scikit-learn', 'psutil')},
              'host_memory_total_bytes': psutil.virtual_memory().total, 'cpu_count': psutil.cpu_count()}
    require(type(result['cpu_count']) is int and 0 < result['cpu_count'] <= 2, 'Observed pilot CPU cores must be1or2')
    if candidate in ('bart', 'led', 'qwen3'):
        import torch
        require(torch.cuda.is_available(), 'Actual CUDA required')
        device = torch.cuda.get_device_name(0)
        require(device in ('Tesla T4', 'NVIDIA T4', 'NVIDIA Tesla T4'), 'Actual T4 required')
        result.update(device_name=device, device_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
                      cuda_runtime=torch.version.cuda)
        torch.cuda.reset_peak_memory_stats()
    else:
        result.update(device_name='cpu', device_memory_bytes=None, cuda_runtime=None)
    return result


def admit_assets(profile, budget):
    """Reserve the full pinned transfer size before any snapshot/model loading."""
    from huggingface_hub import HfApi
    from .tib_benchmark_capacity_runtime import checkpoint_download_patterns
    working = Path(budget.ledger['local_working_root']).resolve()
    cache = Path(os.environ.get('HF_HUB_CACHE', '')).resolve()
    require(cache.is_relative_to(working), 'HF_HUB_CACHE must stay inside measured working root')
    info = HfApi().model_info(profile['checkpoint'], revision=profile['revision'], files_metadata=True)
    require(info.sha == profile['revision'], 'Asset metadata revision differs')
    patterns = checkpoint_download_patterns([f.rfilename for f in info.siblings])
    files = [f for f in info.siblings if any(fnmatch.fnmatch(f.rfilename, p) for p in patterns) and
             not f.rfilename.startswith(('onnx/', 'openvino/'))]
    require(files and all(type(f.size) is int and f.size >= 0 for f in files), 'Missing asset byte-size metadata')
    estimated = sum(f.size for f in files)
    current = sum(p.stat().st_size for p in working.rglob('*') if p.is_file())
    require(current+estimated <= budget.allocation['local_working_storage_bytes'], 'Pinned asset forecast exceeds local working cap')
    require(shutil.disk_usage('/content').free-estimated >= budget.allocation['minimum_local_free_bytes'],
            'Pinned asset forecast violates local free disk floor')
    require(budget.ledger['transfer_bytes']+estimated <= budget.allocation['transfer_bytes'], 'Pinned asset forecast exceeds transfer cap')
    budget.ledger['transfer_bytes'] += estimated
    budget.storage_snapshot = None
    budget.flush()
    return {'estimated_full_asset_transfer_bytes_charged': estimated,
            'method': 'full pinned asset metadata sizes; conservative charge even if cached',
            'revision': info.sha}


class ResourceSample:
    def __init__(self, neural):
        self.neural, self.stop = neural, threading.Event()
        self.data = {'peak_rss_bytes': 0, 'minimum_available_host_bytes': None,
                     'cuda_peak_allocated_bytes': None, 'cuda_peak_reserved_bytes': None,
                     'peak_gpu_utilization_percent': None, 'peak_cpu_percent': 0}

    def __enter__(self):
        import psutil
        if self.neural:
            import torch
            torch.cuda.reset_peak_memory_stats()
        self.process = psutil.Process()
        self.start, self.cpu = time.perf_counter(), time.process_time()
        def sample():
            while not self.stop.is_set():
                self.data['peak_rss_bytes'] = max(self.data['peak_rss_bytes'], self.process.memory_info().rss)
                self.data['peak_cpu_percent'] = max(self.data['peak_cpu_percent'], self.process.cpu_percent())
                available = psutil.virtual_memory().available
                old = self.data['minimum_available_host_bytes']
                self.data['minimum_available_host_bytes'] = available if old is None else min(old, available)
                if self.neural:
                    import torch
                    self.data.update(cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                     cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
                    try:
                        utilization = torch.cuda.utilization()
                        self.data['peak_gpu_utilization_percent'] = max(
                            self.data['peak_gpu_utilization_percent'] or 0, utilization)
                    except Exception:
                        pass
                self.stop.wait(.5)
        self.thread = threading.Thread(target=sample, daemon=True); self.thread.start()
        return self.data

    def __exit__(self, *args):
        self.stop.set(); self.thread.join()
        self.data.update(wall_seconds=time.perf_counter()-self.start, cpu_seconds=time.process_time()-self.cpu)
