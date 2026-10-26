"""Generate the user-run final523 Colab T4 notebook; it never executes anything itself.

Built on the audited selection300 notebook cells (hash-verified ZIP, pip-less venv, shared ledger, evidence export,
start-authorization file). Added here, with the generation runtime untouched:
- `SESSION_PROFILES`: which profiles this session runs, so BART and LED can sit in different sessions;
- a read-only resume-status cell shown before any compute (per profile attempted/pending/status, ledger use);
- a run cell that polls the candidate subprocess and prints elapsed, rate, ETA and remaining session budget live,
  instead of one tail after the profile ends;
- an atomic `checkpoint_summary.json` on Drive after every profile.
Output is text-free: record IDs and counts only, never source or summary text.
"""
import json

from experiments.scripts import tib_selection300_notebook as base
from experiments.scripts.tib_pilot_bundle import ROOT, sha, write
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL
from experiments.scripts.tib_final523_bundle import REGISTRY

NAME = "tib-final523-colab-t4-261024-v1.ipynb"
STORE_NAME = "TIB_FINAL523_261024_V1"
# Hours of work per profile projected from the selection300 run (x 523/300); informational warnings only.
EXPECTED_HOURS = {"lead3": 0.05, "lexrank": 0.05, "bart": 2.4, "led": 3.1}


def _final(text):
    """Reuse a selection300 cell body, renaming the stage; no selection300 identifier may survive."""
    return text.replace("selection300", "final523").replace("Selection300", "Final523")


CONFIG = _final(base.CONFIG).replace(
    "RESUME = False   # the only setting: True for session 2 or 3 (same ZIP, same Drive folder)",
    "RESUME = False   # True from the second session on (same ZIP, same Drive folder)\n"
    "SESSION_PROFILES = ['lead3', 'lexrank', 'bart']   # session 1; session 2: ['led']; BART and LED never share a session")
UPLOAD = _final(base.UPLOAD)
SETUP_TAIL = base.SETUP_TAIL
PREFLIGHT = base.PREFLIGHT
EXPORT = _final(base.EXPORT)

STATUS = '''contract = json.loads((BUNDLE / 'selection_contract.json').read_text())
CANDIDATES = contract['candidate_order']
TOTAL = len(contract['selection_ids'])
EXPECTED_HOURS = @@EXPECTED@@   # from the selection300 run x 523/300; informational only
FINISHED = ('completed', 'completed_with_warning', 'failed')
def check_session_profiles():
    assert SESSION_PROFILES and len(set(SESSION_PROFILES)) == len(SESSION_PROFILES) and set(SESSION_PROFILES) <= set(CANDIDATES), 'SESSION_PROFILES must be distinct profiles of ' + str(CANDIDATES)
    assert not {'bart', 'led'} <= set(SESSION_PROFILES), 'BART and LED together exceed one session; run them in separate sessions'
check_session_profiles()

def stamp(): return time.strftime('%H:%M:%S')
def left_hours(): return (SESSION_LIMIT_SECONDS - (time.monotonic() - SESSION_STARTED)) / 3600

def candidate_state(candidate):
    folder = OUTPUT / candidate
    records = folder / 'records'
    attempted = len(list(records.glob('*'))) if records.exists() else 0
    path = folder / 'candidate_receipt.json'
    receipt = json.loads(path.read_text()) if path.exists() else {}
    summary = receipt.get('summary') or {}
    complete = bool(summary) and summary.get('pending') == 0 and summary.get('denominator') == TOTAL
    return {'attempted': attempted, 'status': receipt.get('status', 'NOT_STARTED'), 'complete': complete,
            'counts': summary.get('status_counts', {}), 'has_identity': (folder / 'run_identity.json').exists()}

def progress_table():
    states = {c: candidate_state(c) for c in CANDIDATES}
    print('profile    this session  state          attempted      status')
    for c in CANDIDATES:
        s = states[c]
        state = 'complete' if s['complete'] else 'partial' if s['attempted'] else 'not started'
        print('%-10s %-13s %-14s %4d/%-4d      %s %s' % (c, 'yes' if c in SESSION_PROFILES else 'no', state,
                                                          s['attempted'], TOTAL, s['status'], s['counts'] or ''))
    return states

print('Authorization: by %s on %s | %s' % (authorization.get('authorized_by'), authorization.get('authorized_on'), str(authorization.get('statement'))[:200]))
ledger_now = json.loads(LEDGER.read_text())
print('[%s] sessions used %d of %d | cumulative GPU %.2f of %.1f h | this session left %.2f h of %.2f h' % (
    stamp(), len(ledger_now['session_runs']), allocation['max_sessions'], ledger_now['gpu_seconds'] / 3600,
    allocation['total_gpu_hours'], left_hours(), SESSION_LIMIT_SECONDS / 3600))
states = progress_table()
for c in SESSION_PROFILES:
    if states[c]['has_identity'] and not RESUME:
        print('WARNING:', c, 'has earlier output: set RESUME=True before running (the run cell will refuse otherwise)')
    if not states[c]['complete'] and EXPECTED_HOURS.get(c, 0) > left_hours():
        print('WARNING:', c, 'projects ~%.2f h of work but only %.2f h are left in this session' % (EXPECTED_HOURS[c], left_hours()))
todo = [c for c in SESSION_PROFILES if not states[c]['complete']]
print('Next:', ('run ' + ', '.join(todo)) if todo else 'nothing to generate in this session; go to the export cell')
'''


LIVE_RUNNER = '''POLL_SECONDS = 30
FINISHED = ('completed', 'completed_with_warning', 'failed')

def stamp(): return time.strftime('%H:%M:%S')
def left_hours(): return (SESSION_LIMIT_SECONDS - (time.monotonic() - SESSION_STARTED)) / 3600

def read_log(log_path, offset):
    with log_path.open('r', errors='replace') as handle:
        handle.seek(offset)
        text = handle.read()
        return text, handle.tell()

def stop_process(process):
    """SIGTERM, then SIGKILL after 30 s, so an old process can never keep writing next to a resumed run."""
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

def run_logged(command, log_name, label, counter, total, limit_seconds, unit='rec'):
    """Run a subprocess, printing progress every POLL_SECONDS; checkpoints survive any interruption.

    counter() returns how many of `total` units are checkpointed; limit_seconds stops the subprocess at the session guard.
    """
    assert limit_seconds > 0, 'Session guard reached'
    log_path = OUTPUT / log_name
    started, offset, next_report, start_count, pending = time.monotonic(), 0, 0, counter(), ''
    with log_path.open('w') as log:
        process = subprocess.Popen(command, cwd=BUNDLE, env=RUN_ENV, stdout=log, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                time.sleep(2)
                elapsed = time.monotonic() - started
                if elapsed > limit_seconds:
                    stop_process(process)
                    bootstrap_hold('Session guard reached during ' + label)
                    print('[%s] %s: session guard reached; checkpoints kept' % (stamp(), label))
                    break
                if elapsed >= next_report:
                    next_report = elapsed + POLL_SECONDS
                    fresh, offset = read_log(log_path, offset)
                    lines = (pending + fresh).split('\\n')
                    pending = lines.pop()   # an incomplete last line waits for the next poll
                    shown = 0
                    for line in lines:
                        try:
                            item = json.loads(line)
                        except ValueError:
                            if shown < 5:
                                print('   log:', line[:300])
                                shown += 1
                            continue
                        if isinstance(item, dict) and item.get('status') in FINISHED:
                            print('   [%s] %s %s' % (stamp(), item.get('record_id'), item['status']))
                    done = counter()
                    rate = (done - start_count) / (elapsed / 3600) if done > start_count and elapsed else 0.0
                    eta = '%.2f h' % ((total - done) / rate) if rate else 'n/a'
                    print('[%s] %-8s %4d/%d %s (%.1f%%) | %.1f %s/h | ETA %s | elapsed %.2f h | session left %.2f h | free disk %.1f GiB' % (
                        stamp(), label, done, total, unit, 100 * done / total, rate, unit, eta,
                        elapsed / 3600, left_hours(), shutil.disk_usage('/content').free / 1024**3))
            process.wait()
        except BaseException:
            stop_process(process)
            print('[%s] %s interrupted: checkpoints kept; rerun with RESUME=True. The record in flight may stay started and is never retried.' % (stamp(), label))
            raise
    print('[%s] %s exit %s | %.2f h | log %s' % (stamp(), label, process.returncode, (time.monotonic() - started) / 3600, log_path.name))
    print(log_path.read_text(errors='replace')[-1500:])
    return process.returncode
'''

RUN = '''assert DEPENDENCIES_READY and PREFLIGHT_OK, 'Run the preflight cell successfully first'
assert 'progress_table' in globals(), 'Run the resume-status cell first'
check_session_profiles()
# The runtime stops itself at a record boundary this long before the session ends; the notebook only kills at the very end.
RUNTIME_MARGIN_HOURS = 0.25
@@LIVE@@
def candidate_runner(command, log_name, candidate):
    return run_logged(command, log_name, candidate, lambda: candidate_state(candidate)['attempted'], TOTAL,
                      SESSION_LIMIT_SECONDS - (time.monotonic() - SESSION_STARTED))

def write_checkpoint_summary():
    body = {'written_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'total_per_profile': TOTAL,
            'session_profiles': SESSION_PROFILES, 'session_left_hours': round(left_hours(), 3), 'profiles': {}}
    for c in CANDIDATES:
        state = candidate_state(c)
        receipt = OUTPUT / c / 'candidate_receipt.json'
        body['profiles'][c] = {**state, 'receipt_sha256': sha(receipt) if receipt.exists() else None}
    temporary = OUTPUT / 'checkpoint_summary.json.tmp'
    temporary.write_text(json.dumps(body, indent=2))
    os.replace(temporary, OUTPUT / 'checkpoint_summary.json')

exits = {}
for candidate in [c for c in CANDIDATES if c in SESSION_PROFILES]:
    if candidate_state(candidate)['complete']:
        print('[%s] %s already complete; kept untouched' % (stamp(), candidate))
        continue
    remaining = left_hours()
    if remaining - RUNTIME_MARGIN_HOURS <= 0:
        bootstrap_hold('Session guard reached before ' + candidate)
        break
    print('[%s] === %s: start | %d of %d attempted | session left %.2f h (projected %.2f h) ===' % (
        stamp(), candidate, candidate_state(candidate)['attempted'], TOTAL, remaining, EXPECTED_HOURS.get(candidate, 0)))
    command = [str(PYTHON), '-m', 'experiments.scripts.tib_selection_runtime',
               '--bundle', str(BUNDLE), '--output', str(OUTPUT / candidate), '--candidate', candidate,
               '--allocation', str(ALLOCATION), '--authorization', str(AUTH), '--wall-hours', str(min(5.75, remaining - RUNTIME_MARGIN_HOURS))]
    if (OUTPUT / candidate / 'run_identity.json').exists():
        assert RESUME, 'Existing candidate output requires RESUME=True'
        command.append('--resume')
    exits[candidate] = candidate_runner(command, candidate + '-' + str(time.time_ns()) + '.log', candidate)
    path = OUTPUT / candidate / 'candidate_receipt.json'
    receipt = json.loads(path.read_text()) if path.exists() else {'status': 'HOLD'}
    print(candidate, receipt.get('status'), receipt.get('summary'))
    write_checkpoint_summary()
    print('[%s] checkpoint_summary.json written' % stamp())
    if receipt.get('status') not in ('PASS', 'COMPLETED_WITH_FAILURES'):
        print('Stopping at partial/HOLD. The', TOTAL, 'ID denominator stays; export evidence.')
        break
print('=== final table ===')
progress_table()
'''

MONITOR_BASH = ("D=/content/drive/MyDrive/@@STORE@@/selection; while true; do clear; date; "
                "for c in lead3 lexrank bart led; do echo \"$c attempted: $(ls $D/$c/records 2>/dev/null | wc -l)/523\"; done; "
                "cat $D/checkpoint_summary.json 2>/dev/null | head -c 600; echo; "
                "f=$(ls -t $D/*.log 2>/dev/null | head -1); [ -n \"$f\" ] && tail -n 6 \"$f\"; "
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader; sleep 15; done")


def fill(text, prepared):
    return (text.replace("@@ZIP@@", repr(prepared["archive_sha256"])).replace("@@MANIFEST@@", repr(prepared["manifest_sha256"]))
            .replace("@@STORE@@", STORE_NAME).replace("@@EXPECTED@@", repr(EXPECTED_HOURS)))


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
    markdown(f"""# TIB final523 generation on Colab T4 (v1)
Choose a **T4 GPU** runtime. Upload the supplied ZIP **and** `start_authorization.json` when asked. Keep Drive private.

Fixed: 523 sealed test sources x 4 profiles (Lead-3, LexRank, BART control, LED ngram3), cap 350. Locked choice from selection300: **LED ngram3**.
Expected cells: {prepared['expected_cells']} (1,046 neural, 1,046 CPU). Generation only: no scoring, no selection.

Ceiling (shared ledger for generation and scoring): {allocation['total_gpu_hours']} GPU-h over at most {allocation['max_sessions']} sessions.
Each session is granted {per_session:.2f} h and stops at {deadline:.2f} h including setup. Retries are 0; these are operating ceilings, not measured needs.

| Session | Notebook | `SESSION_PROFILES` | RESUME |
|---|---|---|---|
| 1 | this one | `['lead3', 'lexrank', 'bart']` | False |
| 2 | this one | `['led']` | True |
| 3 | scoring notebook (built after generation) | - | - |
| 4 | spare for a lost session | - | - |

BART and LED never share a session. A lost or interrupted session is resumed with **RESUME=True**, same ZIP, same Drive folder.
Never delete the ledger, edit profiles or shrink the cohort to get past a HOLD.
""")
    code(fill(CONFIG, prepared))
    markdown("## 1. Verify the ZIP and the start authorization, then open a ledger session\n"
             "Without a valid `start_authorization.json` bound to this bundle the notebook stops before installing anything.\n")
    code(UPLOAD)
    markdown("## 1b. Resume status (read-only)\nShows what is done and what remains per profile, ledger use and warnings, before any compute.\n")
    code(fill(STATUS, prepared))
    markdown("## 2. Pinned runtime\nProven pip-less venv bootstrap; setup time, CPU and transfer count against the shared ledger.\n")
    setup = SETUP_CELL.replace("str(BUNDLE/'requirements-colab-t4.txt')", "str(BUNDLE/'requirements-selection.txt')")
    setup = setup.replace("HF_HUB_DISABLE_TELEMETRY='1')",
                          "HF_HUB_DISABLE_TELEMETRY='1', HF_HOME=str(WORK/'hf-cache'), HF_HUB_CACHE=str(WORK/'hf-cache/hub'), "
                          "XDG_CACHE_HOME=str(WORK/'cache'), PIP_CACHE_DIR=str(WORK/'pip-cache'))")
    code("assert shutil.disk_usage('/content').free >= allocation['minimum_local_free_bytes'], 'Need 32GiB free'\n" + setup + SETUP_TAIL)
    markdown("## 3. Preflight (T4, pins, disk, Drive write/fsync/rename/readback)\nAny failure stops before weights are downloaded.\n")
    code(PREFLIGHT)
    markdown("## 4. Generate\nOnly `SESSION_PROFILES`, sequentially, node-level checkpoints, no automatic retry. Progress prints every 30 s; "
             "a complete profile is left untouched on resume, and `checkpoint_summary.json` is rewritten after each profile.\n")
    code(RUN.replace('@@LIVE@@', LIVE_RUNNER))
    markdown("""### Progress from a terminal
Colab Terminal (bash):
```bash
""" + MONITOR_BASH.replace("@@STORE@@", STORE_NAME) + """
```
`attempted` counts record files (started or finished); the log tail shows the last finished records.
""")
    markdown("## 5. Summarise and export\nKeep the ZIP private. It closes this session in the ledger but not the shared ledger.\n")
    code(EXPORT)
    for index, cell in enumerate(cells):
        cell["id"] = "final523-" + str(index)
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
