"""Generate the user-run selection300 Colab T4 notebook; it never executes anything itself.

Cells follow the audited Pilot40 notebook (hash-verified ZIP, pip-less venv, sequential candidate
subprocesses, shared ledger, evidence export) with three additions: a user start-authorization file bound
to the bundle manifest, an in-session preflight receipt, and a progress-monitoring recipe.
"""
import json

from experiments.scripts.tib_pilot_bundle import ROOT, sha, write
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL
from experiments.scripts.tib_selection300_bundle import REGISTRY

NAME = "tib-selection300-colab-t4-261023-v1.ipynb"
STORE_NAME = "TIB_SELECTION300_261023_V1"

CONFIG = '''from pathlib import Path
import hashlib, json, os, resource, shutil, subprocess, sys, time, zipfile
import psutil
from google.colab import drive, files
RESUME = False   # the only setting: True for session 2 or 3 (same ZIP, same Drive folder)
EXPECTED_ZIP_SHA256 = @@ZIP@@
EXPECTED_MANIFEST_SHA256 = @@MANIFEST@@
SESSION_STARTED = time.monotonic()
SESSION_EPOCH_NS = time.time_ns()
SETUP_CPU_START = resource.getrusage(resource.RUSAGE_CHILDREN)
SETUP_NET_START = psutil.net_io_counters()
SETUP_WALL_START = SESSION_STARTED
WORK = Path('/content/@@STORE@@')
BUNDLE = WORK / 'package'
BUNDLE.mkdir(parents=True, exist_ok=True)
drive.mount('/content/drive')
STORE = Path('/content/drive/MyDrive/@@STORE@@')
OUTPUT = STORE / 'selection'
OUTPUT.mkdir(parents=True, exist_ok=True)
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bootstrap_hold(reason):
    hold = {'status': 'HOLD', 'reason': str(reason), 'selection_complete': False, 'selection_start_authorized': False}
    (OUTPUT / ('bootstrap-hold-' + str(time.time_ns()) + '.json')).write_text(json.dumps(hold, indent=2))
'''

UPLOAD = '''uploaded = files.upload()   # choose the supplied ZIP and start_authorization.json
archives = [Path(n) for n in uploaded if n.endswith('.zip')]
assert len(archives) == 1, 'Upload exactly the supplied selection300 ZIP'
archive = archives[0]
assert sha(archive) == EXPECTED_ZIP_SHA256, 'ZIP differs from the prepared bundle'
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    assert len(names) == len(set(names)) and z.testzip() is None, 'Invalid ZIP'
    for item in z.infolist():
        assert (BUNDLE / item.filename).resolve().is_relative_to(BUNDLE.resolve()), 'Unsafe path'
        assert (item.external_attr >> 16) & 0o170000 != 0o120000, 'Symlink member'
    z.extractall(BUNDLE)
assert sha(BUNDLE / 'selection_manifest.json') == EXPECTED_MANIFEST_SHA256
manifest = json.loads((BUNDLE / 'selection_manifest.json').read_text())
assert set(names) == set(manifest['files']) | {'selection_manifest.json'}
assert all(sha(BUNDLE / n) == v for n, v in manifest['files'].items()), 'Bundle file hash mismatch'
# Start gate: a user authorization bound to this exact bundle. Without it nothing is installed or loaded.
AUTH = OUTPUT / 'start_authorization.json'
supplied = [n for n in uploaded if n.endswith('.json')]
if supplied:
    AUTH.write_bytes(uploaded[supplied[0]])
if not AUTH.exists():
    bootstrap_hold('start_authorization.json missing: not authorized to start')
    raise SystemExit('HOLD: start_authorization.json missing. Nothing was installed or loaded.')
authorization = json.loads(AUTH.read_text())
required = {'manifest_sha256', 'readiness_receipt_v2_sha256', 'authorized_by', 'authorized_on', 'statement'}
receipt_hash = str(authorization.get('readiness_receipt_v2_sha256', ''))
if not (required <= set(authorization) and authorization['authorized_by'] == 'user'
        and str(authorization['statement']).strip() and authorization['manifest_sha256'] == EXPECTED_MANIFEST_SHA256
        and len(receipt_hash) == 64 and set(receipt_hash) <= set('0123456789abcdef')):
    bootstrap_hold('start_authorization.json incomplete, not made by the user, or bound to another bundle')
    raise SystemExit('HOLD: authorization invalid for this bundle.')
sys.path.insert(0, str(BUNDLE))
from experiments.scripts.tib_stage_session import begin_session, record_setup, finish_session
from experiments.scripts.tib_stage_resources import allocated_stage
allocation = json.loads((BUNDLE / 'selection_allocation.json').read_text())
allocated_stage(allocation, 4.0)
ALLOCATION = OUTPUT / 'allocation.json'
if ALLOCATION.exists():
    assert json.loads(ALLOCATION.read_text()) == allocation, 'Existing allocation differs'
else:
    ALLOCATION.write_text(json.dumps(allocation, indent=2))
LEDGER = OUTPUT / 'resource_ledger.json'
assert RESUME or not LEDGER.exists(), 'Ledger exists: set RESUME=True; the ledger is never reset'
ledger = begin_session(LEDGER, allocation, EXPECTED_MANIFEST_SHA256, local_working_root=WORK,
    observation={'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 'monotonic': SESSION_STARTED, 'epoch_ns': SESSION_EPOCH_NS, 'logical_cpu_count': os.cpu_count()})
SESSION_LIMIT_SECONDS = ledger['session_limit_seconds']
SESSION_STARTED = ledger['session_started_monotonic']
print('Bundle and authorization verified. Session grant hours:', SESSION_LIMIT_SECONDS / 3600,
      '| sessions used:', len(ledger['session_runs']), 'of', allocation['max_sessions'])
'''

SETUP_TAIL = '''
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
net = psutil.net_io_counters()
setup_cpu = (usage.ru_utime + usage.ru_stime) - (SETUP_CPU_START.ru_utime + SETUP_CPU_START.ru_stime)
setup_transfer = (net.bytes_recv + net.bytes_sent) - (SETUP_NET_START.bytes_recv + SETUP_NET_START.bytes_sent)
record_setup(LEDGER, cpu_seconds=setup_cpu, transfer_bytes=max(0, setup_transfer), wall_seconds=time.monotonic() - SETUP_WALL_START)
DEPENDENCIES_READY = True
'''

PREFLIGHT = '''assert DEPENDENCIES_READY
preflight_code = """
import json, os, shutil, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from experiments.scripts.tib_stage_resources import require, runtime_environment
out, minimum_free = Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
env = runtime_environment('bart')              # exact pins, actual Colab T4, 1-2 CPU cores
free = shutil.disk_usage('/content').free
require(free >= minimum_free, 'Local free disk below the floor')
payload = {'t': time.time_ns()}
probe = out / 'preflight-probe.json'
with probe.open('w') as handle:
    handle.write(json.dumps(payload)); handle.flush(); os.fsync(handle.fileno())
renamed = out / 'preflight-probe.renamed'
os.replace(probe, renamed)
require(json.loads(renamed.read_text()) == payload, 'Store readback differs')
renamed.unlink()
receipt = {'status': 'PASS', 'device_name': env['device_name'], 'device_memory_bytes': env['device_memory_bytes'],
           'packages': env['packages'], 'runtime_dependencies': env['runtime_dependencies'], 'cpu_count': env['cpu_count'],
           'local_free_bytes': free, 'store_write_fsync_rename_readback_verified': True, 'store_path': str(out)}
(out / 'preflight_receipt.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps(receipt))
"""
code = execute([str(PYTHON), '-c', preflight_code, str(BUNDLE), str(OUTPUT), str(allocation['minimum_local_free_bytes'])],
               'preflight-' + str(time.time_ns()) + '.log')
if code or not (OUTPUT / 'preflight_receipt.json').exists():
    bootstrap_hold('Preflight failed before any model was loaded; see the preflight log')
assert code == 0, 'HOLD: preflight failed. Export evidence using the last cell.'
PREFLIGHT_OK = True
'''

RUN = '''assert DEPENDENCIES_READY and PREFLIGHT_OK, 'Run the preflight cell successfully first'
contract = json.loads((BUNDLE / 'selection_contract.json').read_text())
def finished(candidate):
    path = OUTPUT / candidate / 'candidate_receipt.json'
    if not path.exists():
        return False
    s = json.loads(path.read_text()).get('summary') or {}
    # `started` records (lost mid-record) are interrupted attempts that are never retried, so pending == 0 is complete.
    return s.get('pending') == 0 and s.get('denominator') == len(contract['selection_ids'])
exits = {}
for candidate in contract['candidate_order']:
    if finished(candidate):
        print(candidate, 'already complete; kept untouched')
        continue
    remaining = (SESSION_LIMIT_SECONDS - (time.monotonic() - SESSION_STARTED)) / 3600
    if remaining <= 0:
        bootstrap_hold('Session guard reached before ' + candidate)
        break
    command = [str(PYTHON), '-m', 'experiments.scripts.tib_selection_runtime',
               '--bundle', str(BUNDLE), '--output', str(OUTPUT / candidate), '--candidate', candidate,
               '--allocation', str(ALLOCATION), '--authorization', str(AUTH), '--wall-hours', str(min(5.75, remaining))]
    if (OUTPUT / candidate / 'run_identity.json').exists():
        assert RESUME, 'Existing candidate output requires RESUME=True'
        command.append('--resume')
    exits[candidate] = execute(command, candidate + '-' + str(time.time_ns()) + '.log')
    path = OUTPUT / candidate / 'candidate_receipt.json'
    receipt = json.loads(path.read_text()) if path.exists() else {'status': 'HOLD'}
    print(candidate, receipt.get('status'), receipt.get('summary'))
    if receipt.get('status') not in ('PASS', 'COMPLETED_WITH_FAILURES'):
        print('Stopping at partial/HOLD. The 300-ID denominator stays; export evidence.')
        break
'''

EXPORT = '''from datetime import datetime, timezone
EXPORT_STARTED = time.monotonic()
EXPORT_CPU_STARTED = time.process_time()
EXPORT_NET_STARTED = psutil.net_io_counters()
contract = json.loads((BUNDLE / 'selection_contract.json').read_text())
summary = {'scope': 'selection300_generation_only', 'expected_cells': contract['expected_cells'], 'candidates': {},
           'actual_colab_evidence_requires_audit': True, 'selection_start_authorized': False, 'metrics_executed': False}
for candidate in contract['candidate_order']:
    path = OUTPUT / candidate / 'candidate_receipt.json'
    summary['candidates'][candidate] = json.loads(path.read_text()) if path.exists() else {
        'status': 'NOT_STARTED', 'selected_denominator': len(contract['selection_ids'])}
(OUTPUT / 'selection_summary.json').write_text(json.dumps(summary, indent=2))
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export = STORE / ('tib-selection300-evidence-' + stamp + '.zip')
payload_bytes = sum(p.stat().st_size for root in (OUTPUT, BUNDLE) for p in root.rglob('*')
                    if p.is_file() and '__pycache__' not in p.parts)
stored_bytes = sum(p.stat().st_size for p in STORE.rglob('*') if p.is_file())
assert stored_bytes + payload_bytes + 1024**2 <= allocation['persistent_storage_bytes'], 'Drive quota lacks export headroom'
ledger = json.loads(LEDGER.read_text())
assert ledger['transfer_bytes'] + 2 * (payload_bytes + 1024**2) <= allocation['transfer_bytes'], 'Transfer quota lacks export headroom'
with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
    for root, prefix in [(OUTPUT, 'selection'), (BUNDLE, 'package')]:
        for path in sorted(root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                z.write(path, prefix + '/' + path.relative_to(root).as_posix())
net = psutil.net_io_counters()
export_transfer = max(2 * export.stat().st_size,
                      (net.bytes_recv + net.bytes_sent) - (EXPORT_NET_STARTED.bytes_recv + EXPORT_NET_STARTED.bytes_sent))
record_setup(LEDGER, cpu_seconds=time.process_time() - EXPORT_CPU_STARTED, transfer_bytes=export_transfer,
             wall_seconds=time.monotonic() - EXPORT_STARTED)
closed = finish_session(LEDGER, status='evidence_exported')   # closes this session only; the shared ledger stays open
with zipfile.ZipFile(export, 'a', zipfile.ZIP_DEFLATED) as z:
    z.writestr('selection/session_close_after_export.json', json.dumps(closed, indent=2))
print(json.dumps({k: {'status': v.get('status'), 'summary': v.get('summary')} for k, v in summary['candidates'].items()}, indent=2))
print(export, 'bytes', export.stat().st_size, 'SHA256', sha(export))
files.download(str(export))
'''

MONITOR_BASH = ("D=/content/drive/MyDrive/@@STORE@@/selection; while true; do clear; date; "
                "for c in lead3 lexrank bart led; do echo \"$c attempted: $(ls $D/$c/records 2>/dev/null | wc -l)/300\"; done; "
                "tail -n 6 $(ls -t $D/*.log 2>/dev/null | head -1); "
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader; sleep 15; done")
MONITOR_POWERSHELL = ("$D=\"G:\\My Drive\\@@STORE@@\\selection\"; while($true){ Clear-Host; Get-Date; "
                      "foreach($c in 'lead3','lexrank','bart','led'){ \"$c attempted: $((Get-ChildItem $D\\$c\\records -ErrorAction SilentlyContinue).Count)/300\" }; "
                      "Get-ChildItem $D\\*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | ForEach-Object { Get-Content $_.FullName -Tail 6 }; Start-Sleep 15 }")


def fill(text, prepared):
    return (text.replace("@@ZIP@@", repr(prepared["archive_sha256"])).replace("@@MANIFEST@@", repr(prepared["manifest_sha256"]))
            .replace("@@STORE@@", STORE_NAME))


def create(registry=REGISTRY, root=ROOT):
    prepared = json.loads((registry / "preparation_receipt.json").read_text(encoding="utf-8"))
    allocation = json.loads((registry / "selection_allocation.json").read_text(encoding="utf-8"))
    per_session = min(allocation["session_wall_hours"], allocation["total_wall_hours"] / allocation["max_sessions"])
    deadline = per_session * (1 - allocation["session_headroom_fraction"])
    cells = []

    def markdown(source):
        cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)})

    def code(source):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": source.splitlines(keepends=True)})
    markdown(f"""# TIB selection300 generation on Colab T4 (v1)
Choose a **T4 GPU** runtime. Upload the supplied ZIP **and** `start_authorization.json` when asked. Keep Drive private.

Fixed: 300 sealed selection sources x 4 profiles (Lead-3, LexRank, BART control, LED ngram3), cap 350, no Qwen3.
Expected cells: {prepared['expected_cells']} (600 neural, 600 CPU). Generation only: no scoring, no selection, no final test.

Ceiling (shared ledger for generation and scoring): {allocation['total_gpu_hours']} GPU-h over at most {allocation['max_sessions']} sessions.
Each session is granted {per_session:.2f} h and stops at {deadline:.2f} h including setup. Scoring {allocation['scoring_gpu_hours']} GPU-h and recovery
{allocation['recovery_time_hours']} h are reserved inside the total. These are operating ceilings, not measured needs; retries are 0.

Session 1: run every cell. Session 2/3 (only if needed, or for scoring later): new T4 runtime, **RESUME=True**, same ZIP, same Drive folder.
Never delete the ledger, edit profiles or shrink the cohort to get past a HOLD.
""")
    code(fill(CONFIG, prepared))
    markdown("## 1. Verify the ZIP and the start authorization, then open a ledger session\n"
             "Without a valid `start_authorization.json` bound to this bundle the notebook stops before installing anything.\n")
    code(UPLOAD)
    markdown("## 2. Pinned runtime\nProven pip-less venv bootstrap; setup time, CPU and transfer count against the shared ledger.\n")
    setup = SETUP_CELL.replace("str(BUNDLE/'requirements-colab-t4.txt')", "str(BUNDLE/'requirements-selection.txt')")
    setup = setup.replace("HF_HUB_DISABLE_TELEMETRY='1')",
                          "HF_HUB_DISABLE_TELEMETRY='1', HF_HOME=str(WORK/'hf-cache'), HF_HUB_CACHE=str(WORK/'hf-cache/hub'), "
                          "XDG_CACHE_HOME=str(WORK/'cache'), PIP_CACHE_DIR=str(WORK/'pip-cache'))")
    code("assert shutil.disk_usage('/content').free >= allocation['minimum_local_free_bytes'], 'Need 32GiB free'\n" + setup + SETUP_TAIL)
    markdown("## 3. Preflight (T4, pins, disk, Drive write/fsync/rename/readback)\nAny failure stops before weights are downloaded.\n")
    code(PREFLIGHT)
    markdown("## 4. Generate\nSequential candidate subprocesses, node-level checkpoints, no automatic retry. A complete candidate is left untouched on resume.\n")
    code(RUN)
    markdown("""### Progress from a terminal
Colab Terminal (bash):
```bash
""" + MONITOR_BASH.replace("@@STORE@@", STORE_NAME) + """
```
PowerShell with Drive for desktop (adjust the drive letter):
```powershell
""" + MONITOR_POWERSHELL.replace("@@STORE@@", STORE_NAME) + """
```
`attempted` counts record files (started or finished); the log tail shows the last finished records.
""")
    markdown("## 5. Summarise and export\nKeep the ZIP private. It closes this session in the ledger but not the shared ledger.\n")
    code(EXPORT)
    for index, cell in enumerate(cells):
        cell["id"] = "selection300-" + str(index)
    notebook = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
                "metadata": {"kernelspec": {"display_name": "Python3", "language": "python", "name": "python3"},
                             "colab": {"name": NAME}, "accelerator": "GPU"}}
    path = root / "experiments/notebooks" / NAME
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    result = {"path": str(path), "sha256": sha(path), "executed": False}
    write(registry / "notebook_preparation.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(create(), indent=2))
