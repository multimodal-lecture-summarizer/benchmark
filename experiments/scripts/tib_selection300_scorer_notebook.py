"""Generate the user-run selection300 scoring Colab T4 notebook; it never executes anything itself.

Cells follow the audited Pilot40 scorer notebook (hash-verified ZIP, pip-less venv, pinned assets) and the
selection300 generation notebook (user authorization gate, shared ledger) with the gaps seen in the
generation run closed: the T4 check runs before the ledger is touched, the export never touches the ledger,
and the session is closed by exactly one cell that only acts while the ledger session is still active.
"""
import json
from pathlib import Path

from experiments.scripts.tib_pilot_bundle import sha, write
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL
from experiments.scripts.tib_selection300_scorer_bundle import (
    EVIDENCE_SHA256, REGISTRY, ROOT,
)

NAME = "tib-selection300-scorer-colab-t4-261024-v1.ipynb"
STORE_NAME = "TIB_SELECTION300_261023_V1"   # same Drive folder (and ledger) as generation
EVIDENCE_NAME = "tib-selection300-evidence-20261023T175142Z.zip"
AUTHORIZATION = "start_authorization_scoring.json"
EXPORT_RESERVE_HOURS = 0.3

CONFIG = '''from pathlib import Path
import hashlib, json, os, resource, shutil, subprocess, sys, time, zipfile
import psutil
RESUME = False   # the only setting: True only to replay a COMPLETE cache from an earlier scoring attempt
EXPECTED_ZIP_SHA256 = @@ZIP@@
EXPECTED_MANIFEST_SHA256 = @@MANIFEST@@
GENERATION_MANIFEST_SHA256 = @@GEN_MANIFEST@@   # the shared ledger is bound to the GENERATION bundle, not to this one
GENERATION_EVIDENCE_NAME = @@EVIDENCE_NAME@@
GENERATION_EVIDENCE_SHA256 = @@EVIDENCE_SHA@@
EXPORT_RESERVE_SECONDS = @@RESERVE@@ * 3600
SESSION_STARTED = time.monotonic()
SESSION_EPOCH_NS = time.time_ns()
SETUP_CPU_START = resource.getrusage(resource.RUSAGE_CHILDREN)
SETUP_NET_START = psutil.net_io_counters()
SETUP_WALL_START = SESSION_STARTED
WORK = Path('/content/@@STORE@@')
BUNDLE = WORK / 'scoring'
SESSION_OPENED = SCORER_READY = GPU_OK = False
'''

GPU_GATE = '''# Cheap check before Drive or the shared ledger is touched: a wrong runtime must not cost a session.
try:
    probe = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                           capture_output=True, text=True, timeout=60)
    gpu_names = [line.strip() for line in probe.stdout.splitlines() if line.strip()] if probe.returncode == 0 else []
except (OSError, subprocess.SubprocessError):
    gpu_names = []
if gpu_names != ['Tesla T4']:
    raise SystemExit('HOLD: the runtime GPU is ' + (', '.join(gpu_names) or 'missing') + ', not one Tesla T4. '
                     'Choose Runtime > Change runtime type > T4 GPU and rerun from the first cell. The ledger was not touched.')
GPU_OK = True
print('GPU gate passed:', gpu_names[0])
'''

VERIFY = '''from google.colab import drive, files
BUNDLE.mkdir(parents=True, exist_ok=True)
drive.mount('/content/drive')
STORE = Path('/content/drive/MyDrive/@@STORE@@')
GENERATION_DIR = STORE / 'selection'
OUTPUT = STORE / 'scoring'
OUTPUT.mkdir(parents=True, exist_ok=True)
def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for part in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()
def bootstrap_hold(reason):
    hold = {'status': 'HOLD', 'reason': str(reason), 'scoring_complete': False, 'scoring_start_authorized': False}
    (OUTPUT / ('bootstrap-hold-' + str(time.time_ns()) + '.json')).write_text(json.dumps(hold, indent=2))
uploaded = files.upload()   # choose the supplied scoring ZIP and @@AUTH@@
# Authorization gate first: without a user-made file bound to this exact bundle nothing is extracted or installed.
AUTH = OUTPUT / '@@AUTH@@'
supplied = [n for n in uploaded if n.endswith('.json')]
if supplied:
    AUTH.write_bytes(uploaded[supplied[0]])
if not AUTH.exists():
    bootstrap_hold('@@AUTH@@ missing: not authorized to start')
    raise SystemExit('HOLD: @@AUTH@@ missing. Nothing was extracted, installed or opened.')
authorization = json.loads(AUTH.read_text())
required = {'manifest_sha256', 'scoring_readiness_receipt_sha256', 'authorized_by', 'authorized_on', 'statement'}
receipt_hash = str(authorization.get('scoring_readiness_receipt_sha256', '')) if isinstance(authorization, dict) else ''
if not (isinstance(authorization, dict) and required <= set(authorization) and authorization['authorized_by'] == 'user'
        and str(authorization['statement']).strip() and authorization['manifest_sha256'] == EXPECTED_MANIFEST_SHA256
        and len(receipt_hash) == 64 and set(receipt_hash) <= set('0123456789abcdef')):
    bootstrap_hold('@@AUTH@@ incomplete, not made by the user, or bound to another bundle')
    raise SystemExit('HOLD: scoring authorization invalid for this bundle.')
archives = [Path(n) for n in uploaded if n.endswith('.zip')]
assert len(archives) == 1, 'Upload exactly the supplied scoring ZIP'
archive = archives[0]
assert sha(archive) == EXPECTED_ZIP_SHA256, 'ZIP differs from the prepared scoring bundle'
with zipfile.ZipFile(archive) as z:
    names = z.namelist()
    assert len(names) == len(set(names)) and z.testzip() is None, 'Invalid ZIP'
    for item in z.infolist():
        assert (BUNDLE / item.filename).resolve().is_relative_to(BUNDLE.resolve()), 'Unsafe path'
        assert (item.external_attr >> 16) & 0o170000 != 0o120000, 'Symlink member'
    z.extractall(BUNDLE)
assert sha(BUNDLE / 'package_manifest.json') == EXPECTED_MANIFEST_SHA256
manifest = json.loads((BUNDLE / 'package_manifest.json').read_text())
assert set(names) == set(manifest['files']) | {'package_manifest.json'}
assert all(sha(BUNDLE / n) == v for n, v in manifest['files'].items()), 'Bundle file hash mismatch'
contract = json.loads((BUNDLE / 'scoring_contract.json').read_text())
assert (contract['generation_bundle_manifest_sha256'] == GENERATION_MANIFEST_SHA256
        and contract['generation_evidence_zip_sha256'] == GENERATION_EVIDENCE_SHA256), 'Contract binds other generation hashes'
# The generation evidence (the scored outputs' origin) must still be intact on Drive.
evidence = STORE / GENERATION_EVIDENCE_NAME
if not evidence.exists() or sha(evidence) != GENERATION_EVIDENCE_SHA256:
    bootstrap_hold('Generation evidence ZIP missing or changed on Drive')
    raise SystemExit('HOLD: ' + GENERATION_EVIDENCE_NAME + ' must be on Drive in the generation folder, unchanged.')
# Shared ledger: read-only precheck here; nothing is written until the next cell.
LEDGER = GENERATION_DIR / 'resource_ledger.json'
allocation = json.loads((BUNDLE / 'selection_allocation.json').read_text())
assert LEDGER.exists(), 'Shared generation ledger missing; the ledger is never recreated'
state = json.loads(LEDGER.read_text())
assert json.loads((GENERATION_DIR / 'allocation.json').read_text()) == allocation, 'Drive allocation differs from the bundle'
sys.path.insert(0, str(BUNDLE))
from experiments.scripts.tib_selection300_scorer_validation import check_ledger_ready
usage = check_ledger_ready(state, allocation, GENERATION_MANIFEST_SHA256,
                           boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())   # raises when bound elsewhere, active on another VM, or no session left
assert RESUME or not any((OUTPUT / 'checkpoints').glob('*.json')), 'Scoring checkpoints exist: set RESUME=True (a complete cache only)'
print('Authorization and bundle verified. Sessions used:', usage['sessions_used'], 'of', usage['max_sessions'],
      '| GPU hours used:', round(usage['gpu_hours_used'], 3), 'of', usage['total_gpu_hours'])
'''

OPEN_SESSION = '''assert GPU_OK, 'Run the runtime gate cell successfully before opening the ledger session'
sys.path.insert(0, str(BUNDLE))
from experiments.scripts.tib_stage_session import begin_session, record_setup, finish_session
ledger = begin_session(LEDGER, allocation, GENERATION_MANIFEST_SHA256, local_working_root=WORK,
    observation={'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 'monotonic': SESSION_STARTED, 'epoch_ns': SESSION_EPOCH_NS, 'logical_cpu_count': os.cpu_count()})
SESSION_LIMIT_SECONDS = ledger['session_limit_seconds']
SESSION_STARTED = ledger['session_started_monotonic']
SESSION_DEADLINE_SECONDS = SESSION_LIMIT_SECONDS * (1 - allocation['session_headroom_fraction'])
SESSION_OPENED = True
print('Session opened. Granted hours:', SESSION_LIMIT_SECONDS / 3600, '| scoring deadline hours:', SESSION_DEADLINE_SECONDS / 3600,
      '| sessions used:', len(ledger['session_runs']), 'of', allocation['max_sessions'])
'''

ASSETS = '''assert SESSION_OPENED
ASSETS = WORK / 'scorer-assets'
asset_code = """
from pathlib import Path
from experiments.scripts.tib_benchmark_scorer_assets import acquire
from experiments.scripts.tib_benchmark_scorer import validate_assets
from experiments.scripts.rq2_tib_benchmark_metrics import BERT_MODEL,BERT_REVISION,SBERT_MODEL,SBERT_REVISION
root=Path(__import__('sys').argv[1])
if not all((root/k/'asset_manifest.json').exists() for k in ('bert','sentence')):
    acquire(root)
for k,m,r in [('bert',BERT_MODEL,BERT_REVISION),('sentence',SBERT_MODEL,SBERT_REVISION)]:
    validate_assets(root/k,model=m,revision=r)
print('Actual pinned scorer asset hashes verified')
"""
asset_exit = execute([str(PYTHON), '-c', asset_code, str(ASSETS)], 'assets.log')
if asset_exit:
    bootstrap_hold('Scorer assets incomplete/invalid; see assets.log')
assert asset_exit == 0, 'HOLD: assets. Export evidence, then close the session with the last cell.'
torch_probe = ("import json, torch; assert torch.cuda.is_available(), 'CUDA unavailable in the venv'; "
               "name = torch.cuda.get_device_name(0); assert name == 'Tesla T4', name; "
               "print(json.dumps({'torch': torch.__version__, 'device': name}))")
torch_exit = execute([str(PYTHON), '-c', torch_probe], 'torch-preflight.log')
if torch_exit:
    bootstrap_hold('torch/CUDA preflight failed in the venv; see torch-preflight.log')
assert torch_exit == 0, 'HOLD: torch preflight. Export evidence, then close the session with the last cell.'
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
net = psutil.net_io_counters()
setup_cpu = (usage.ru_utime + usage.ru_stime) - (SETUP_CPU_START.ru_utime + SETUP_CPU_START.ru_stime)
setup_transfer = (net.bytes_recv + net.bytes_sent) - (SETUP_NET_START.bytes_recv + SETUP_NET_START.bytes_sent)
record_setup(LEDGER, cpu_seconds=setup_cpu, transfer_bytes=max(0, setup_transfer), wall_seconds=time.monotonic() - SETUP_WALL_START)
SCORER_READY = True
'''

RUN = '''assert SESSION_OPENED and SCORER_READY, 'Run the session, setup and asset cells successfully first'
remaining_hours = (SESSION_DEADLINE_SECONDS - (time.monotonic() - SESSION_STARTED) - EXPORT_RESERVE_SECONDS) / 3600
assert remaining_hours > 0.25, 'Too little session time left; do not start scoring.'
command = [str(PYTHON), '-m', 'experiments.scripts.tib_pilot40_scorer_runner', '--stage', 'selection300',
           '--bundle', str(BUNDLE), '--output', str(OUTPUT), '--assets', str(ASSETS), '--ledger', str(LEDGER),
           '--wall-hours', str(remaining_hours)]   # the runner stops early enough to leave time to export
if RESUME:
    command.append('--resume')
launch_ns = time.time_ns()
bootstrap_hold('Scorer subprocess started; awaiting current actual receipt')
exit_code = execute(command, 'scorer-' + str(launch_ns) + '.log')
if exit_code not in (0, 2):
    bootstrap_hold('Scorer subprocess failed before a complete receipt; inspect logs')
receipt_path = OUTPUT / '@@RECEIPT@@'
if receipt_path.exists() and exit_code in (0, 2):
    current = json.loads(receipt_path.read_text())
    if int(current.get('run_id', 0)) >= launch_ns:
        print(json.dumps({k: current.get(k) for k in ('delivered_status', 'views_status', 'reasons',
              'successful_metric_records', 'expected_scoreable')}, indent=2))
    else:
        bootstrap_hold('Receipt does not belong to this execution; a prior PASS cannot certify it')
else:
    bootstrap_hold('No actual scorer receipt produced')
print('Do not infer PASS from install/download completion or local tests.')
'''

EXPORT = '''from datetime import datetime, timezone
# Safe to run any number of times, before or after the session is closed: it only reads the ledger.
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
export = STORE / ('tib-selection300-scoring-evidence-' + stamp + '.zip')
with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
    for path in sorted(OUTPUT.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            z.write(path, 'evidence/' + path.relative_to(OUTPUT).as_posix())
    for path in sorted(BUNDLE.rglob('*')):
        # Sources and references stay out of the returned evidence; their hash is in the manifest.
        if path.is_file() and '__pycache__' not in path.parts and path.name != 'scoring_outputs.jsonl':
            z.write(path, 'bundle/' + path.relative_to(BUNDLE).as_posix())
    if LEDGER.exists():
        z.write(LEDGER, 'ledger/resource_ledger_at_export.json')
    if 'ASSETS' in globals():
        for key in ('bert', 'sentence'):
            manifest_path = ASSETS / key / 'asset_manifest.json'
            if manifest_path.exists():
                z.write(manifest_path, 'scorer-assets/' + key + '/asset_manifest.json')
print('ZIP:', export, '| bytes:', export.stat().st_size, '| SHA256:', sha(export))
files.download(str(export))
'''

CLOSE = '''# The only cell that closes the session. It acts once, only while the ledger session is active, and is safe to rerun.
state = json.loads(LEDGER.read_text())
if state['session_status'] == 'active':
    try:
        sys.path.insert(0, str(BUNDLE))   # a fresh kernel or VM has neither the path nor the import from the session cell
        from experiments.scripts.tib_stage_session import finish_session
        finish_session(LEDGER, status='scoring_evidence_exported')
        print('Session closed in the shared ledger.')
    except (ValueError, ImportError) as error:
        print('Session NOT closed (' + str(error) + '); the ledger keeps the conservative accounting. Do not rerun scoring.')
else:
    print('Session already closed (' + str(state['session_status']) + '); nothing to do.')
final_copy = STORE / 'resource_ledger_after_scoring.json'
final_copy.write_bytes(LEDGER.read_bytes())
files.download(str(final_copy))   # small text-free file: send it back with the evidence ZIP for the audit
'''

MONITOR_BASH = ("D=/content/drive/MyDrive/@@STORE@@/scoring; while true; do clear; date; "
                "echo \"scored: $(ls $D/checkpoints 2>/dev/null | wc -l)/1197\"; "
                "echo \"views: $(ls $D/view_checkpoints 2>/dev/null | wc -l)/1197\"; "
                "tail -n 6 $(ls -t $D/scorer-*.log 2>/dev/null | head -1); "
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader; sleep 15; done")
MONITOR_POWERSHELL = ("$D=\"G:\\My Drive\\@@STORE@@\\scoring\"; while($true){ Clear-Host; Get-Date; "
                      "\"scored: $((Get-ChildItem $D\\checkpoints -ErrorAction SilentlyContinue).Count)/1197\"; "
                      "\"views: $((Get-ChildItem $D\\view_checkpoints -ErrorAction SilentlyContinue).Count)/1197\"; "
                      "Get-ChildItem $D\\scorer-*.log | Sort-Object LastWriteTime | Select-Object -Last 1 | "
                      "ForEach-Object { Get-Content $_.FullName -Tail 6 }; Start-Sleep 15 }")


def fill(text, prepared, receipt_name):
    values = {"@@ZIP@@": repr(prepared["archive_sha256"]), "@@MANIFEST@@": repr(prepared["manifest_sha256"]),
              "@@GEN_MANIFEST@@": repr(prepared["generation_bundle_manifest_sha256"]),
              "@@EVIDENCE_NAME@@": repr(EVIDENCE_NAME), "@@EVIDENCE_SHA@@": repr(prepared["generation_evidence_zip_sha256"]),
              "@@RESERVE@@": repr(EXPORT_RESERVE_HOURS), "@@STORE@@": STORE_NAME, "@@AUTH@@": AUTHORIZATION,
              "@@RECEIPT@@": receipt_name}
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def create(registry=REGISTRY, root=ROOT, expected_evidence_sha=EVIDENCE_SHA256):
    from experiments.scripts.tib_selection300_scorer_validation import SELECTION_STAGE
    prepared = json.loads((Path(registry) / "preparation_receipt.json").read_text(encoding="utf-8"))
    if prepared["generation_evidence_zip_sha256"] != expected_evidence_sha:
        raise ValueError("Preparation receipt binds a different generation evidence ZIP")
    receipt_name = SELECTION_STAGE["receipt"]
    cells = []

    def markdown(source):
        cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)})

    def code(source):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": fill(source, prepared, receipt_name).splitlines(keepends=True)})
    markdown(f"""# TIB selection300 scoring on Colab T4 (v1)
Choose a **T4 GPU** runtime, then run the cells in order. Upload the supplied scoring ZIP **and** `{AUTHORIZATION}` when asked. Keep Drive private.

Scores **{prepared['scoreable_rows']} delivered summaries** of {prepared['rows']} generation cells (Lead-3, LexRank, BART control, LED ngram3; **no Qwen3**)
with the frozen scorer v2 (ROUGE-1/2/L, BERTScore; source similarity is computed but not reported), then the S/M/L views (ROUGE + BERTScore).
The {prepared['failed_rows']} failed LED cells stay in the denominator with NULL metrics and are never scored. Nothing is generated, ranked or selected here.

This is the **last authorized session** on the shared ledger (generation used two of three). It opens with the generation bundle hash, the only hash the
ledger accepts. If scoring is cut short the run stops as a partial HOLD with an intact denominator; there is no spare session to resume it.
The bundle holds sources and references: keep Drive private and never publish the ZIP.

Run once, in order. **There is no cell that closes the session early:** only the last cell does, after the evidence is exported.
""")
    code(CONFIG)
    markdown("## 1. Runtime gate\nChecks the GPU **before** Drive or the ledger is touched. A CPU or other GPU runtime stops here and costs nothing.\n")
    code(GPU_GATE)
    markdown(f"## 2. Verify the authorization, the ZIP and the shared ledger (read-only)\nWithout a valid `{AUTHORIZATION}` bound to this bundle nothing is extracted or installed.\n")
    code(VERIFY)
    markdown("## 3. Open the ledger session\nUses the generation bundle hash. Refuses when no authorized session is left.\n")
    code(OPEN_SESSION)
    markdown("## 4. Pinned runtime\nProven pip-less venv bootstrap, same pins as the Pilot40 scorer run.\n")
    code(SETUP_CELL)
    markdown("## 5. Scorer assets and torch preflight\nOnly the two pinned scorer models are acquired. Setup time, CPU and transfer are charged to the ledger once, here.\n")
    code(ASSETS)
    markdown("## 6. Score\nFresh scoring is the default. `RESUME=True` replays only a **complete** matching cache. Order: long sources first, each source's four profiles together, "
             "then the views. The runner refuses to start when the ledger session is not active.\n")
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
`scored` counts per-output checkpoints of the delivered summaries; `views` counts the S/M/L checkpoints.
""")
    markdown("## 7a. Export the evidence ZIP (also after a HOLD)\nRead-only for the ledger and safe to repeat. Sources and references are left out. Keep the ZIP private.\n")
    code(EXPORT)
    markdown("## 7b. Close the session\nRun **once, after 7a**. It closes the ledger session only while it is active; rerunning does nothing. Send back the ZIP and `resource_ledger_after_scoring.json`.\n")
    code(CLOSE)
    for index, cell in enumerate(cells):
        cell["id"] = "selection300-scoring-" + str(index)
    notebook = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                             "colab": {"name": NAME}, "accelerator": "GPU"}}
    path = Path(root) / "experiments/notebooks" / NAME
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    result = {"path": str(path), "sha256": sha(path), "executed": False}
    write(Path(registry) / "notebook_preparation.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(create(), indent=2))
