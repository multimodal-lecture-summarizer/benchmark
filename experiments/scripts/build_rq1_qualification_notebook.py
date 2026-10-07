"""Build the RQ1 dataset-qualification diagnostic notebook (outside the 22-node DAG).

The notebook replays the cached, bounded Phase-1 source probes offline, runs the
04a/04b runners on validation-only OCW timed-TOC lectures in a fresh diagnostic
artifact root, verifies receipts and writes a GO/BLOCKED readiness ledger.  It
never writes to the ``official`` namespace and makes no RQ1 claim.
"""
from pathlib import Path

import nbformat


def build() -> Path:
    root = Path(__file__).resolve().parents[2]
    md, code = nbformat.v4.new_markdown_cell, nbformat.v4.new_code_cell
    cells = [md("""# RQ1 dataset qualification and chaptering pilot (diagnostic)

Outside the 22-node official manifest. Source probes are replayed **offline** from the bounded, logged cache written by `experiments.scripts.rq1_candidate_ledger`. The pilot uses only `validation` units, `evidence_status=partial` and the `diagnostic` namespace. A passing cell is not an RQ1 result; the conclusion is the GO/BLOCKED ledger at the end.
"""), code('''from pathlib import Path
from datetime import datetime, timezone
import os, sys, json, subprocess
import pandas as pd
from IPython.display import display, Markdown
ROOT = Path.cwd()
assert (ROOT / "experiments/scripts").is_dir(), "run from the project root"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
QUAL = ROOT / "experiments/outputs/diagnostic/rq1_qualification"
RUN = ROOT / "experiments/outputs/diagnostic/rq1_pilot_runs" / STAMP
RUN.mkdir(parents=True)
os.environ.update(PYTHONIOENCODING="utf-8")
commands = []
def command(args, accepted=(0,), timeout=900):
    result = subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                            capture_output=True, timeout=timeout)
    entry = dict(command=args, exit_code=result.returncode, accepted=result.returncode in accepted,
                 stdout=result.stdout[-4000:], stderr=result.stderr[-2000:])
    commands.append(entry)
    (RUN / "commands.json").write_text(json.dumps(commands, indent=2), encoding="utf-8")
    print("COMMAND", " ".join(map(str, args)), "EXIT", result.returncode)
    print(result.stdout[-3000:])
    return result
print("Run directory:", RUN)
'''), md("## 1. Focused contract tests\nGT provenance, split sealing (final_test first in manifest, smoke truncation), same-unit features, ±3 s collar edges, empty predictions, checkpoint identity, manifest edges, dataset contracts, endpoint eligibility."), code('''command([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_rq1_chaptering_contract.py", "tests/test_dataset_contracts.py",
         "tests/test_endpoint_eligibility.py", "tests/test_chapter_metrics.py"])
assert commands[-1]["accepted"], "focused tests failed"
'''), md("## 2. Candidate ledger (offline replay of bounded probes)"), code('''command([sys.executable, "-m", "experiments.scripts.rq1_candidate_ledger",
         "--output-dir", str(QUAL), "--offline"])
assert commands[-1]["accepted"]
ledger = json.loads((QUAL / "candidate_ledger.json").read_text(encoding="utf-8"))
assert ledger["network"]["offline_replay"] and ledger["network"]["new_requests_this_invocation"] == 0
rows = []
for r in ledger["records"]:
    e = r["evidence"]
    rows.append(dict(source=r["source_id"], course=r["course_id"], lecture=r["lecture_id"],
                     split=e.get("official_split"), boundaries=len(e.get("chapter_boundaries_sec") or []),
                     media_duration=(e.get("media_probe") or {}).get("duration_sec"),
                     rights=r["rights_status"], access=r["access_status"], excluded=r["exclusion_reason"]))
table = pd.DataFrame(rows)
display(table.groupby(["source", table.excluded.isna().rename("unexcluded")]).size().rename("units").reset_index())
display(table[table.source != "ytseg"])
display(Markdown("YTSeg summary"))
display(pd.json_normalize(ledger["ytseg_summary"]).T)
display(pd.json_normalize(ledger["decision"]).T)
'''), md("## 3. Boundary/media alignment audit\nPublished offsets vs decoded media duration for the pre-declared sample. Offsets are never edited."), code('''audit = []
for r in ledger["records"]:
    e = r["evidence"]
    if not e.get("media_probe_sample"):
        continue
    audit.append(dict(lecture=r["lecture_id"], clips=e["timed_clip_count"],
                      first_clip_start=e["first_start_sec"], last_clip_end=e["last_end_sec"],
                      media_duration=e["media_probe"].get("duration_sec"),
                      end_minus_media=round(e["last_end_sec"] - (e["media_probe"].get("duration_sec") or 0), 3),
                      gaps=e["gap_count"], max_gap=e["max_gap_sec"],
                      media_license=(e.get("media_item_rights") or {}).get("licenseurl"),
                      excluded=r["exclusion_reason"], titles=e["clip_titles"]))
display(pd.DataFrame(audit))
'''), md("## 4. Validation-only pilot of the 04a/04b runners\nFresh diagnostic root; all units `validation`; single course, so no final_test exists to leak."), code('''PILOT = RUN / "artifacts"
command([sys.executable, "-m", "experiments.scripts.rq1_diagnostic_pilot",
         "--ledger", str(QUAL / "candidate_ledger.json"), "--artifact-root", str(PILOT),
         "--cache-dir", str(QUAL)], accepted=(0, 1))
pilot = json.loads((PILOT / "pilot_summary.json").read_text(encoding="utf-8"))
print(json.dumps({k: pilot[k] for k in ("unit_ids", "splits", "exit_codes", "evidence_status")}, indent=2))
'''), md("## 5. Receipt verification and split audit"), code('''from benchmarks.scripts.execute_all_notebooks import load_manifest, validate_produced_artifacts
entries = {e["id"]: e for e in load_manifest()["notebooks"]}
assert len(entries) == 22
NS = PILOT / "diagnostic" / "full"
receipt_errors = {}
for nid in ("04a_chaptering_benchmark", "04b_chaptering_modality_ablation"):
    run = json.loads((NS / "runs" / f"{nid}.run.json").read_text(encoding="utf-8"))
    ctx = {k: run[k] for k in ("run_id", "status", "source_sha256", "config_sha256", "dependency_state_sha256")}
    receipt_errors[nid] = validate_produced_artifacts(entries[nid], PILOT, "full", "diagnostic", ctx)
    assert run["evaluation_mode"] == "selection" and run["status"] == "partial"
print("receipt errors:", receipt_errors)
def records(aid):
    return json.loads((NS / "payloads" / f"{aid}.json").read_text(encoding="utf-8"))["records"]
frozen_units = records("dataset.frozen_manifest")[0]["unit_records"]
unit_split = {u["unit_id"]: u["split"] for u in frozen_units}
seen = {aid: sorted({r["unit_id"] for r in records(aid)}) for aid in (
    "chapter.input_features", "chapter.raw_predictions", "chapter.per_unit_metrics",
    "chapter.ablation_predictions", "chapter.ablation_metrics")}
non_validation = {aid: [u for u in ids if unit_split[u] != "validation"] for aid, ids in seen.items()}
print("non-validation units per artifact:", non_validation)
assert not any(non_validation.values())
assert len({tuple(v) for v in seen.values()}) == 1, "artifacts do not cover the same units"
'''), md("## 6. Pilot outputs (diagnostic, not RQ1 performance)"), code('''display(pd.DataFrame([{"candidate": r["candidate"], "units": r["unit_count"],
                       "empty_predictions": r["empty_prediction_count"], **r["metrics"]}
                      for r in records("chapter.aggregate")]))
display(pd.DataFrame(records("chapter.candidate_status")))
display(pd.DataFrame(records("chapter.ablation_status")))
display(pd.DataFrame([{"unit": p["unit_id"], "candidate": p["candidate"],
                       "predicted": p["predictions"]["chapter_boundaries_sec"][:8],
                       "reference": p["predictions"]["reference_boundaries_sec"]}
                      for p in records("chapter.raw_predictions")]))
display(pd.json_normalize(records("chapter.frozen_configuration")[0]).T)
'''), md("## 7. GO/BLOCKED readiness ledger"), code('''decision = ledger["decision"]
ocw = decision["ocw_timed_toc"]
checks = [
    ("contract_tests", "PASS" if commands[0]["accepted"] else "FAIL", "focused suites"),
    ("dataset_access", "BLOCKED", "AVLectures archive: " + decision["avlectures_archive"]
        + "; OCW timed-TOC media URLs published and headers decoded for "
        + str(ocw["media_verified_lectures"]) + " lectures"),
    ("rights", "PENDING_REVIEW", "OCW pages CC BY-NC-SA 4.0 + archive.org item 3.0, no reserved marking; "
        "YTSeg video blocked_rights; human rights review not done"),
    ("independent_gt", "PARTIAL", "OCW publisher timed-TOC (editorial excerpt offsets) aligned for "
        + str(ocw["media_verified_lectures"]) + "/6 sampled lectures; YTSeg creator chapters (editorial)"),
    ("course_disjoint_splits", "BLOCKED", decision["course_disjoint_learned_study"]
        + ": OCW cohort = " + ", ".join(ocw["independent_source_courses"])
        + "; YTSeg val/test share channels"),
    ("d2_receipt", "BLOCKED", "no official D2 freeze; pilot uses diagnostic 00c-equivalent artifacts"),
    ("same_unit_features", "PASS" if not any(non_validation.values()) else "FAIL",
        "chapter.input_features hash-bound per unit; transcript only (OCR/scene/visual/acoustic blocked_compute)"),
    ("candidate_models", "BLOCKED", "; ".join(f"{s['candidate']}={s['status']}"
        for s in records("chapter.candidate_status") if s["status"] != "run")),
    ("notebook_runs", "PASS" if pilot["exit_codes"] == {"04a": 0, "04b": 0}
        and not any(receipt_errors.values()) else "FAIL", "04a/04b runners + executor receipt validation"),
    ("compute", "BLOCKED", "per-unit OCR/scene/visual/acoustic extraction not run (full media not downloaded)"),
]
ready = pd.DataFrame(checks, columns=["gate", "status", "evidence"])
display(ready)
overall = "GO" if all(s == "PASS" for _, s, _ in checks) else "BLOCKED"
out = {"generated_at": STAMP, "overall_official_rq1": overall, "gates": ready.to_dict("records"),
       "ledger": str(QUAL / "candidate_ledger.json"), "pilot_root": str(PILOT),
       "claim": "diagnostic only; no RQ1 hypothesis, final-test or full-DAG claim"}
(RUN / "readiness_ledger.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("OVERALL official RQ1:", overall)
print("Readiness ledger:", RUN / "readiness_ledger.json")
''')]
    for index, cell in enumerate(cells):
        cell.id = f"rq1-qualification-{index:02d}"
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata.kernelspec = {"name": "python3", "display_name": "Python 3", "language": "python"}
    destination = root / "experiments/notebooks/diagnostics/rq1_dataset_qualification.ipynb"
    destination.parent.mkdir(parents=True, exist_ok=True)
    existing = nbformat.read(destination, as_version=4) if destination.is_file() else None
    if existing is None or [(c.cell_type, c.id, c.source) for c in existing.cells] != [
        (c.cell_type, c.id, c.source) for c in notebook.cells
    ]:
        nbformat.write(notebook, destination)
    return destination


if __name__ == "__main__":
    print(build())
