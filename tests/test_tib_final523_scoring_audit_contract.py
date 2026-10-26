"""The scoring audit reads what the real runner writes: keys, files and checkpoint envelopes from an actual (fake-backed) run."""
import json
from pathlib import Path

from experiments.scripts import tib_final523_scoring_audit as audit_module
from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts.tib_final523_scorer_validation import FINAL_STAGE
from test_tib_pilot40_scorer_runner import package, read_lines  # noqa: F401  (fixture + helper)

STAGE = {**runner.PILOT40_STAGE, "receipt": FINAL_STAGE["receipt"], "ready_key": FINAL_STAGE["ready_key"],
         "partial_resume_allowed": True, "portable_binding": True}

RECEIPT_KEYS_READ_BY_THE_AUDIT = (
    "delivered_status", "views_status", "reasons", "runtime", "T4_verified", "testing_dependency_injection", "fixtures", "binding",
    "artifact_sha256", "qwen3_scored", "generation_executed", "selection_start_authorized", "successful_metric_records", "run_id",
    FINAL_STAGE["ready_key"])
PARTIAL_KEYS = ("partial_resume_requested", "partial_resume_used", "reused_rows", "fresh_rows", "reused_failed_rows", "run_ids",
                "runtime_full_sha256_by_run", "mixed_runtime", "reused_original_scoring_seconds", "quarantined", "canary")


def interrupted_then_resumed(p):
    original, state = p.options["score_function"], {"n": 0}

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        state["n"] += 1
        if state["n"] == 3:
            p.clock.offset += 10_000
        return result
    p.options["score_function"] = wrapped
    first = runner.run(p.root, p.output, p.assets, stage=STAGE, **p.options)
    p.options["score_function"] = original
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    return first, second


def test_receipts_carry_every_key_the_audit_reads(package):
    first, second = interrupted_then_resumed(package)
    for receipt in (first, second):
        assert not [k for k in RECEIPT_KEYS_READ_BY_THE_AUDIT if k not in receipt]
    assert not [k for k in PARTIAL_KEYS if k not in second]
    assert (package.output / FINAL_STAGE["receipt"]).exists()


def test_the_archived_runs_and_cost_evidence_have_the_shape_the_audit_expects(package):
    first, second = interrupted_then_resumed(package)
    runs = audit_module.run_overview(package.output / "runs")
    assert {r["run_id"] for r in runs} == {first["run_id"], second["run_id"]} and all(r["has_receipt"] for r in runs)
    by_id = {r["run_id"]: r for r in runs}
    assert by_id[first["run_id"]]["delivered_status"] == "HOLD" and by_id[first["run_id"]]["rows_scored_fresh"] == 3
    assert by_id[second["run_id"]]["rows_reused"] == 3
    costs = json.loads((package.output / "cost_evidence.json").read_text())
    assert {"resources", "total_wall_seconds", "reused_original_scoring_seconds"} <= set(costs)
    assert all(k in read_lines(package.output / "metrics.jsonl")[0] for k in ("sample_id", "scoring_status", "metrics", "failures", "reused"))


def test_real_checkpoints_are_readable_with_provenance_and_the_receipt_binding(package):
    first, second = interrupted_then_resumed(package)
    scores, bad, duplicates = audit_module.checkpoint_scan(package.output / "checkpoints")
    views, bad_views, duplicate_views = audit_module.checkpoint_scan(package.output / "view_checkpoints")
    assert bad == bad_views == duplicates == duplicate_views == 0 and len(scores) == len(views) == 7
    assert all(p["key"]["binding"] == second["binding"] for p in scores + views)
    assert {p["provenance"]["run_id"] for p in scores} == {first["run_id"], second["run_id"]}
    assert all(p["key"]["sample_id"].endswith("__views") for p in views)
    assert sorted(second["runtime_full_sha256_by_run"]) == sorted([first["run_id"], second["run_id"]])


def test_the_audit_flags_the_injected_fake_run_as_not_actual_evidence(package):
    """A run on the fake harness must never audit as a pass: injection is visible in the receipt."""
    _, second = interrupted_then_resumed(package)
    assert second["testing_dependency_injection"] is True and second["delivered_status"] == "HOLD"
    assert second["T4_verified"] is False
