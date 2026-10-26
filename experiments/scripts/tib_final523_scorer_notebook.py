"""Generate the user-run final523 scoring Colab T4 notebook; it never executes anything itself.

Built on the audited selection300 scoring notebook (T4 gate before the ledger is touched, authorization gate, shared
ledger session, pinned assets, export that never touches the ledger, one closing cell). Added here, with the scorer
runner's strict modes untouched:
- a read-only status cell (scored/views checkpoints against the contract, ledger use, resume advice);
- a run cell that polls the scorer subprocess and prints checkpoint count, rate, ETA and remaining session budget live;
- `RESUME_MODE`: 'none' (fresh), 'partial' (continue an interrupted run under the user's pre-run policy,
  scorer_resume_policy_final523_v1.json, via --resume-partial) or 'complete' (replay a COMPLETE cache via --resume).
Output is text-free (counts and hashes only).
"""
import json
from pathlib import Path

from experiments.scripts import tib_selection300_scorer_notebook as base
from experiments.scripts.tib_final523_notebook import LIVE_RUNNER
from experiments.scripts.tib_final523_scorer_bundle import REGISTRY, ROOT
from experiments.scripts.tib_final523_scorer_validation import FINAL_STAGE
from experiments.scripts.tib_pilot_bundle import sha, write
from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL

NAME = "tib-final523-scorer-colab-t4-261024-v1.ipynb"
STORE_NAME = "TIB_FINAL523_261024_V1"   # same Drive folder as final523 generation; scoring keeps its own ledger inside it
AUTHORIZATION = base.AUTHORIZATION
EXPORT_RESERVE_HOURS = base.EXPORT_RESERVE_HOURS

CONFIG = base.CONFIG.replace(
    "RESUME = False   # the only setting: True only to replay a COMPLETE cache from an earlier scoring attempt",
    "RESUME_MODE = 'none'   # 'none' fresh | 'partial' continue an interrupted run (pre-run policy) | 'complete' replay a COMPLETE cache\n"
    "assert RESUME_MODE in ('none', 'partial', 'complete'), RESUME_MODE\n"
    "RESUME = RESUME_MODE != 'none'")
assert "RESUME_MODE" in CONFIG
GPU_GATE, OPEN_SESSION, ASSETS, CLOSE = base.GPU_GATE, base.OPEN_SESSION, base.ASSETS, base.CLOSE
_OLD_CHECK = "'Scoring checkpoints exist: set RESUME=True (a complete cache only)'"
assert base.VERIFY.count(_OLD_CHECK) == 1
_LEDGER_START = "# Shared ledger: read-only precheck here; nothing is written until the next cell.\n"
_LEDGER_END = "assert RESUME or not any("
assert base.VERIFY.count(_LEDGER_START) == 1 and base.VERIFY.count(_LEDGER_END) == 1
# Scoring has its own ledger and allocation, carved out of what the generation ledger left (scoring_budget_decision_final523_v1.json).
# The generation ledger is only read: it must still be the one the carve-out was computed from.
SCORING_LEDGER_BLOCK = """# Scoring ledger: its own budget, carved out of what the generation ledger left. The generation ledger is only read here.
GEN_LEDGER = GENERATION_DIR / 'resource_ledger.json'
LEDGER = OUTPUT / 'resource_ledger_scoring.json'
allocation = json.loads((BUNDLE / 'selection_allocation.json').read_text())
carve = allocation['carved_from_generation']
assert GEN_LEDGER.exists(), 'Generation ledger missing from Drive; it is never recreated'
sys.path.insert(0, str(BUNDLE))
from experiments.scripts.tib_stage_session import digest
from experiments.scripts.tib_final523_scorer_validation import check_scoring_ledger_ready
gen_state = json.loads(GEN_LEDGER.read_text())
assert digest(json.loads((GENERATION_DIR / 'allocation.json').read_text())) == carve['generation_allocation_sha256'], 'Drive generation allocation differs from the carved-out budget'
assert gen_state['bundle_sha256'] == GENERATION_MANIFEST_SHA256, 'Generation ledger is bound to another bundle'
assert gen_state['session_status'] != 'active', 'Generation ledger still shows an active session'
assert gen_state['gpu_seconds'] <= carve['generation_ledger_used']['gpu_seconds'] + 60, 'Generation ledger shows more use than the carved-out budget assumed'
usage = check_scoring_ledger_ready(LEDGER, allocation, GENERATION_MANIFEST_SHA256,
                                   boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())   # raises when bound elsewhere, active on another VM, or no session left
"""
VERIFY = (base.VERIFY[:base.VERIFY.index(_LEDGER_START)] + SCORING_LEDGER_BLOCK + base.VERIFY[base.VERIFY.index(_LEDGER_END):]
          ).replace(_OLD_CHECK, "'Scoring checkpoints exist: set RESUME_MODE to partial (continue) or complete (replay)'")
assert "check_scoring_ledger_ready" in VERIFY and "GENERATION_DIR / 'resource_ledger.json'" in VERIFY and VERIFY.count("\nLEDGER = ") == 1
EXPORT = base.EXPORT.replace("tib-selection300-scoring-evidence-", "tib-final523-scoring-evidence-")

STATUS = '''EXPECTED = contract['expected_scoreable']
def stamp(): return time.strftime('%H:%M:%S')
def checkpoint_count(folder): return len(list((OUTPUT / folder).glob('*.json'))) if (OUTPUT / folder).exists() else 0
def scored(): return checkpoint_count('checkpoints')
def viewed(): return checkpoint_count('view_checkpoints')
ledger_now = json.loads(LEDGER.read_text()) if LEDGER.exists() else {'session_runs': [], 'gpu_seconds': 0.0}   # no scoring session yet
print('[%s] scoring sessions used %d of %d | scoring GPU %.2f of %.2f h (its own ledger)' % (
    stamp(), len(ledger_now['session_runs']), allocation['max_sessions'], ledger_now['gpu_seconds'] / 3600, allocation['total_gpu_hours']))
print('scored checkpoints %d/%d | view checkpoints %d/%d | failed generation cells kept as NULL: %d' % (
    scored(), EXPECTED, viewed(), EXPECTED, contract['expected_failed']))
if scored() or viewed():
    complete = scored() == EXPECTED and viewed() == EXPECTED
    if complete:
        print("Earlier checkpoints found: COMPLETE cache. RESUME_MODE = 'complete' replays it")
    else:
        print("Earlier checkpoints found: PARTIAL (%d scored, %d views of %d). RESUME_MODE = 'partial' continues it: valid checkpoints are "
              "reused, 6 of them are re-scored as a drift canary, and only the absent ones are scored" % (scored(), viewed(), EXPECTED))
    if RESUME_MODE == 'none':
        print("WARNING: RESUME_MODE is 'none'; set it to continue, or move the checkpoint folders aside to start over")
else:
    print('Next: score all', EXPECTED, 'delivered summaries, then the S/M/L views')
partials = [p.name for folder in ('checkpoints', 'view_checkpoints') if (OUTPUT / folder).exists() for p in (OUTPUT / folder).glob('*.partial')]
if partials and RESUME_MODE == 'partial':
    print('%d torn *.partial checkpoint files (a killed write) will be quarantined and their rows scored again' % len(partials))
elif partials:
    print("WARNING: %d torn *.partial checkpoint files (a killed write): only RESUME_MODE = 'partial' can quarantine them" % len(partials))
'''

RUN = '''assert SESSION_OPENED and SCORER_READY, 'Run the session, setup and asset cells successfully first'
assert 'scored' in globals(), 'Run the status cell first'
@@LIVE@@
def left_hours(): return (SESSION_DEADLINE_SECONDS - EXPORT_RESERVE_SECONDS - (time.monotonic() - SESSION_STARTED)) / 3600
remaining_hours = (SESSION_DEADLINE_SECONDS - (time.monotonic() - SESSION_STARTED) - EXPORT_RESERVE_SECONDS) / 3600
assert remaining_hours > 0.25, 'Too little session time left; do not start scoring.'
command = [str(PYTHON), '-m', 'experiments.scripts.tib_pilot40_scorer_runner', '--stage', 'final523',
           '--bundle', str(BUNDLE), '--output', str(OUTPUT), '--assets', str(ASSETS), '--ledger', str(LEDGER),
           '--wall-hours', str(remaining_hours)]   # the runner stops early enough to leave time to export
if RESUME_MODE == 'complete':
    command.append('--resume')
elif RESUME_MODE == 'partial':
    command.append('--resume-partial')
launch_ns = time.time_ns()
bootstrap_hold('Scorer subprocess started; awaiting current actual receipt')
exit_code = run_logged(command, 'scorer-' + str(launch_ns) + '.log', 'scoring', lambda: scored() + viewed(),
                       2 * EXPECTED, remaining_hours * 3600 + 300, unit='ckpt')   # the runner stops itself first; the kill is a 5 min backstop
print('[%s] scored %d/%d | views %d/%d' % (stamp(), scored(), EXPECTED, viewed(), EXPECTED))
if exit_code not in (0, 2):
    bootstrap_hold('Scorer subprocess failed before a complete receipt; inspect logs')
receipt_path = OUTPUT / '@@RECEIPT@@'
if receipt_path.exists() and exit_code in (0, 2):
    current = json.loads(receipt_path.read_text())
    if int(current.get('run_id', 0)) >= launch_ns:
        print(json.dumps({k: current.get(k) for k in ('delivered_status', 'views_status', 'reasons',
              'successful_metric_records', 'expected_scoreable', 'partial_resume_used', 'reused_rows', 'fresh_rows', 'reused_failed_rows', 'mixed_runtime',
              'run_ids', 'quarantined', 'canary')}, indent=2))
    else:
        bootstrap_hold('Receipt does not belong to this execution; a prior PASS cannot certify it')
else:
    bootstrap_hold('No actual scorer receipt produced')
print('Do not infer PASS from install/download completion or local tests.')
'''

MONITOR_BASH = ("D=/content/drive/MyDrive/@@STORE@@/scoring; while true; do clear; date; "
                "echo \"scored: $(ls $D/checkpoints 2>/dev/null | wc -l)/@@N@@\"; "
                "echo \"views: $(ls $D/view_checkpoints 2>/dev/null | wc -l)/@@N@@\"; "
                "f=$(ls -t $D/scorer-*.log 2>/dev/null | head -1); [ -n \"$f\" ] && tail -n 6 \"$f\"; "
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader; sleep 15; done")


def fill(text, prepared, receipt_name):
    values = {"@@ZIP@@": repr(prepared["archive_sha256"]), "@@MANIFEST@@": repr(prepared["manifest_sha256"]),
              "@@GEN_MANIFEST@@": repr(prepared["generation_bundle_manifest_sha256"]),
              "@@EVIDENCE_NAME@@": repr(prepared["generation_evidence_zip_name"]),
              "@@EVIDENCE_SHA@@": repr(prepared["generation_evidence_zip_sha256"]),
              "@@RESERVE@@": repr(EXPORT_RESERVE_HOURS), "@@STORE@@": STORE_NAME, "@@AUTH@@": AUTHORIZATION,
              "@@RECEIPT@@": receipt_name, "@@N@@": str(prepared["scoreable_rows"]), "@@LIVE@@": LIVE_RUNNER}
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def create(registry=REGISTRY, root=ROOT):
    prepared = json.loads((Path(registry) / "preparation_receipt.json").read_text(encoding="utf-8"))
    receipt_name = FINAL_STAGE["receipt"]
    cells = []

    def markdown(source):
        cells.append({"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)})

    def code(source):
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": fill(source, prepared, receipt_name).splitlines(keepends=True)})
    markdown(f"""# TIB final523 scoring on Colab T4 (v1)
Choose a **T4 GPU** runtime, then run the cells in order. Upload the supplied scoring ZIP **and** `{AUTHORIZATION}` when asked. Keep Drive private.

Scores **{prepared['scoreable_rows']} delivered summaries** of {prepared['rows']} generation cells (Lead-3, LexRank, BART control, LED ngram3; **no Qwen3**)
with the frozen scorer v2 (ROUGE-1/2/L, BERTScore; source similarity is computed but not reported), then the S/M/L views (ROUGE + BERTScore).
The {prepared['failed_rows']} failed generation cells stay in the denominator with NULL metrics and are never scored. Nothing is generated or selected here.

Scoring has **its own ledger** (`scoring/resource_ledger_scoring.json`) and up to **{prepared['scoring_max_sessions']} sessions**, the second being the spare:
the generation ledger ended with 3 of its 4 sessions used (one lost), so your decision of 2026-10-25 (`scoring_budget_decision_final523_v1.json`) carved the
scoring budget out of what it left: {prepared['scoring_total_hours']} h in total, so generation use plus scoring can never exceed the approved 21 h.
The generation ledger is only read here. The scoring ledger opens with the generation bundle hash, as the generation ledger did.
**Resuming an interrupted scoring run** (policy `scorer_resume_policy_final523_v1.json`, declared by you before any final score existed):
set `RESUME_MODE = 'partial'` in the first cell. Valid checkpoints are reused, only absent ones are scored, 6 reused rows are re-scored as a drift canary
(tolerance 1e-6; a mismatch stops the run), torn `*.partial` files are quarantined and listed, and the checkpoint key binds the compute runtime (CUDA, device,
Python, pinned packages) but not the VM. Corrupt, foreign or mismatched checkpoints stop the run; they are never treated as holes. `'complete'` only replays a
COMPLETE cache. The status cell tells you which case you are in. Scoring work is projected at ~2.4 h; the second session continues a cut-off run.
If the first session is lost or cut off, open a **new** Colab runtime (Disconnect and delete runtime) and run again with `RESUME_MODE = 'partial'`.
The bundle holds sources and references: keep Drive private and never publish the ZIP.

Run once, in order. **There is no cell that closes the session early:** only the last cell does, after the evidence is exported.
""")
    code(CONFIG)
    markdown("## 1. Runtime gate\nChecks the GPU **before** Drive or the ledger is touched. A CPU or other GPU runtime stops here and costs nothing.\n")
    code(GPU_GATE)
    markdown(f"## 2. Verify the authorization, the ZIP and the ledgers (read-only)\nWithout a valid `{AUTHORIZATION}` bound to this bundle nothing is extracted or installed.\n")
    code(VERIFY)
    markdown("## 2b. Status (read-only)\nScored and view checkpoints against the contract, ledger use, and whether an earlier cache can be continued or replayed.\n")
    code(STATUS)
    markdown("## 3. Open the ledger session\nUses the generation bundle hash. Refuses when no authorized session is left.\n")
    code(OPEN_SESSION)
    markdown("## 4. Pinned runtime\nProven pip-less venv bootstrap, same pins as the Pilot40 scorer run.\n")
    code(SETUP_CELL)
    markdown("## 5. Scorer assets and torch preflight\nOnly the two pinned scorer models are acquired. Setup time, CPU and transfer are charged to the ledger once, here.\n")
    code(ASSETS)
    markdown("## 6. Score\nFresh scoring is the default. Order: long sources first, each source's four profiles together, then the views. "
             "Progress prints every 30 s with checkpoint count, rate, ETA and the session budget left. The runner refuses to start when the ledger session is not active.\n")
    code(RUN)
    markdown("""### Progress from a terminal
Colab Terminal (bash):
```bash
""" + MONITOR_BASH.replace("@@STORE@@", STORE_NAME).replace("@@N@@", str(prepared["scoreable_rows"])) + """
```
`scored` counts per-output checkpoints of the delivered summaries; `views` counts the S/M/L checkpoints.
""")
    markdown("## 7a. Export the evidence ZIP (also after a HOLD)\nRead-only for the ledger and safe to repeat. Sources and references are left out. Keep the ZIP private.\n")
    code(EXPORT)
    markdown("## 7b. Close the session\nRun **once, after 7a**. It closes the ledger session only while it is active; rerunning does nothing. Send back the ZIP and `resource_ledger_after_scoring.json`.\n")
    code(CLOSE)
    for index, cell in enumerate(cells):
        cell["id"] = "final523-scoring-" + str(index)
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
