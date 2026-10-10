"""Bounded pilot runtime: exact dispatch evidence and conservative stop rules."""
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def code_identity():
    folder = Path(__file__).resolve().parent
    names = ['rq2_tib_benchmark_pair', 'rq2_controlled_validation', 'rq2_local_hf_backend',
             'rq2_tib_benchmark_bundle', 'rq2_tib_benchmark_results', 'rq2_tib_benchmark_metrics',
             'rq2_tib_benchmark', 'rq2_tib_benchmark_dataset', 'rq2_tib_pilot_data',
             'rq2_tib_pilot', 'rq2_tib_pilot_runtime', 'rq2_tib_pilot_cohort', 'rq2_tib_pilot_forecast']
    hashes = {name:hashlib.sha256((folder/(name+'.py')).read_bytes()).hexdigest() for name in names}
    return {'files':hashes, 'sha256':digest(hashes)}


def hardware_profile(backend):
    versions = {}
    for name in ('torch', 'transformers', 'datasets', 'numpy'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    profile = {'platform':platform.platform(), 'python':platform.python_version(),
               'device':str(backend.device), 'model':backend.model_id, 'tokenizer':backend.tokenizer_id,
               'map_batch_size':getattr(backend, 'map_batch_size', 1), 'packages':versions}
    torch = sys.modules.get('torch')
    if torch is not None and str(backend.device).startswith('cuda'):
        props = torch.cuda.get_device_properties(0)
        profile.update(gpu_name=props.name, gpu_total_bytes=props.total_memory,
                       cuda_version=torch.version.cuda)
    return profile


class TimedPilotBackend:
    """A deadline is checked BETWEEN dispatches; it cannot kill a running kernel.

    No automatic retry. Exceptions retain known input usage; unavailable output
    usage remains null. Raw prompts/references never enter the dispatch log.
    """
    def __init__(self, backend, log_path, *, wall_limit_seconds=7200):
        self.backend = backend
        self.log_path = Path(log_path)
        self.deadline = time.monotonic() + wall_limit_seconds
        self.blocked_reason = None
        self.arm = None
        self.item_id = None

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def _dispatch(self, prompts, kwargs, batched):
        if self.blocked_reason:
            raise RuntimeError(self.blocked_reason)
        if time.monotonic() >= self.deadline:
            self.blocked_reason = 'pilot_wall_deadline_reached_between_dispatches'
            raise TimeoutError(self.blocked_reason)
        row = {'id':self.item_id, 'arm':self.arm, 'batch_size':len(prompts),
               'requested_output_cap_per_prompt':kwargs['max_output_tokens'],
               'prompt_tokens':[self.count_tokens(p) for p in prompts],
               'output_tokens':None, 'status':'started'}
        started = time.perf_counter()
        try:
            output = (self.backend.generate_batch(prompts, **kwargs) if batched else
                      self.backend.generate(prompts[0], **kwargs))
            responses = output if batched else [output]
            row['attempts'] = [r.get('attempts', []) for r in responses]
            row['output_tokens'] = [sum(a['output_tokens'] for a in r.get('attempts', [])) for r in responses]
            row['status'] = 'returned' if all(r.get('text', '').strip() for r in responses) else 'empty_output'
            return output
        except BaseException as exc:
            row.update(status='failed', error_type=type(exc).__name__, error=str(exc))
            if 'cuda' in str(exc).casefold() or 'out of memory' in str(exc).casefold():
                self.blocked_reason = 'CUDA_failure_requires_fresh_runtime; no_automatic_retry'
            raise
        finally:
            row['dispatch_seconds'] = time.perf_counter() - started
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')

    def generate(self, prompt, **kwargs):
        return self._dispatch([prompt], kwargs, False)

    def generate_batch(self, prompts, **kwargs):
        return self._dispatch(prompts, kwargs, True)
