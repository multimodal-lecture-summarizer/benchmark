"""Audit and coverage tooling on hand-built mini evidence (12 IDs x 4 profiles, one failed LED cell)."""
import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from experiments.scripts import tib_selection300_scoring_audit as audit_module
from experiments.scripts.tib_selection300_scorer_bundle import BINDING

PROFILES = ("lead3", "lexrank", "bart", "led")
STRATA = ("short", "medium", "long")
IDS = [f"fixture:{i:02d}" for i in range(12)]
STRATUM = {i: STRATA[n % 3] for n, i in enumerate(IDS)}
FAILED = "led__fixture-05"
RULES = json.loads((BINDING / "admission_rules_v2.json").read_text(encoding="utf-8"))
MANIFEST_SHA = "b" * 64
GEN_ZIP_SHA = "e" * 64


def contract():
    return {"selection_ids": IDS, "source_strata": STRATUM, "quotas": {s: 4 for s in STRATA},
            "expected_rows": 48, "expected_scoreable": 47, "failed_cells": [FAILED],
            "generation_evidence_zip_sha256": GEN_ZIP_SHA, "generation_bundle_manifest_sha256": "c" * 64}


def metric_row(profile, record):
    sample = f"{profile}__{record.replace(':', '-')}"
    base = {"sample_id": sample, "record_id": record, "profile_id": profile, "source_stratum": STRATUM[record], "reused": False}
    if sample == FAILED:
        return {**base, "scoring_status": "not_scoreable_generation_failed", "metrics": dict.fromkeys(audit_module.METRICS),
                "failures": {"record": "AdapterFailure: x"}, "new_scoring_wall_seconds": 0.0}
    value = 0.3 + 0.01 * PROFILES.index(profile)
    return {**base, "scoring_status": "completed", "failures": {},
            "metrics": {"rouge1_f1": value + 0.2, "rouge2_f1": value - 0.1, "rougeL_f1": value, "bertscore_f1": value + 0.4,
                        "source_sentence_similarity_v1": 0.5},
            "new_scoring_wall_seconds": 4.0, "bertscore_seconds": 3.0, "source_similarity_seconds": 0.5,
            "rouge_and_other_seconds": 0.5}


def write_evidence(root, mutate=None):
    evidence = Path(root) / "evidence"
    evidence.mkdir(parents=True)
    rows = [metric_row(p, i) for i in IDS for p in PROFILES]
    views = [{"sample_id": r["sample_id"], "views": {v: {"metrics": dict.fromkeys(audit_module.VIEW_METRICS, 0.2), "failures": {}}
                                                       for v in "SML"}} for r in rows if r["scoring_status"] == "completed"]
    costs = {"resources": {"wall_seconds": 1.0, "cpu_seconds": 1.0, "cuda_peak_reserved_bytes": 1}, "total_wall_seconds": 6000.0,
             "view_scoring_seconds": 100.0, "checkpoint_seconds": 10.0, "input_profiling_seconds": 5.0,
             "initialization_seconds": 30.0, "fixtures_seconds": 20.0, "new_view_calls": 47, "reused_identical_view_texts": 0}
    receipt = {"delivered_status": "PASS", "reasons": [], "views_status": "COMPLETE", "T4_verified": True,
               "runtime": {"google_colab_imported": True, "T4_device_observed": True, "device_name": "Tesla T4"},
               "testing_dependency_injection": False, "fixtures": {"status": "pass"},
               "binding": {"package_manifest_sha256": MANIFEST_SHA, "evidence_zip_sha256": GEN_ZIP_SHA},
               "qwen3_scored": False, "generation_executed": False, "selection_start_authorized": False,
               "successful_metric_records": 47, "failed_generation_cells": 1}
    if mutate:
        mutate(rows, views, costs, receipt)
    (evidence / "cost_evidence.json").write_text(json.dumps(costs))
    (evidence / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (evidence / "view_metrics.jsonl").write_text("".join(json.dumps(v) + "\n" for v in views))
    receipt["artifact_sha256"] = {n: hashlib.sha256((evidence / n).read_bytes()).hexdigest()
                                  for n in ("cost_evidence.json", "metrics.jsonl", "view_metrics.jsonl")}
    (evidence / audit_module.RECEIPT).write_text(json.dumps(receipt))
    return root


def ledger(**changes):
    value = {"bundle_sha256": "c" * 64, "gpu_seconds": 40000.0,
             "session_runs": [{"status": "preflight_failed_before_any_model", "measured_wall_seconds": 489.0, "granted_wall_seconds": 18000.0},
                              {"status": "preflight_failed_before_any_model", "measured_wall_seconds": 151.0, "granted_wall_seconds": 18000.0},
                              {"status": audit_module.CLOSED_STATUS, "measured_wall_seconds": 6500.0, "granted_wall_seconds": 18000.0}]}
    value.update(changes)
    return value


ALLOCATION = {"max_sessions": 3, "total_gpu_hours": 15}


def run_audit(tmp_path, mutate=None, ledger_value=None):
    root = write_evidence(tmp_path, mutate)
    return audit_module.audit(root, MANIFEST_SHA, contract(), ledger_value if ledger_value is not None else ledger(), ALLOCATION)


def test_clean_evidence_passes_every_check_and_has_no_anomaly(tmp_path):
    checks, rows, views, costs, receipt, anomalies = run_audit(tmp_path)
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    assert anomalies == [] and len(rows) == 48 and len(views) == 47


def test_coverage_matches_hand_count_and_never_applies_the_rule(tmp_path):
    _, rows, *_ = run_audit(tmp_path)
    cover = audit_module.coverage(rows, contract(), RULES)
    assert cover["rule_applied"] is False
    assert [cover["per_profile"][p]["scored_success"] for p in PROFILES] == [12, 12, 12, 11]
    failed_stratum = STRATUM["fixture:05"]
    assert cover["per_profile"]["led"]["by_stratum"][failed_stratum] == 3
    assert cover["per_profile"]["led"]["stratum_fraction"][failed_stratum] == 0.75
    assert cover["per_profile"]["led"]["informational_floors"]["per_stratum_met"][failed_stratum] is False
    assert cover["per_profile"]["lead3"]["informational_floors"]["overall_met"] is True
    assert cover["c_between"]["size"] == 11 and "fixture:05" not in {r["record_id"] for r in rows if audit_module.is_success(r)
                                                                      and r["profile_id"] == "led"}
    assert cover["c_between"]["informational_floors"]["common_n_met"] is False  # 11 < 180 on this miniature


def test_one_nonfinite_metric_lowers_coverage_and_fails_the_check(tmp_path):
    def poison(rows, *_):
        next(r for r in rows if r["profile_id"] == "bart")["metrics"]["rougeL_f1"] = None
    checks, rows, *_ = run_audit(tmp_path, poison)
    assert checks["five_metrics_finite"] is False
    cover = audit_module.coverage(rows, contract(), RULES)
    assert cover["per_profile"]["bart"]["scored_success"] == 11 and cover["c_between"]["size"] == 10


def test_missing_row_or_wrong_failed_cell_fails(tmp_path):
    checks, *_ = run_audit(tmp_path / "a", lambda rows, *_: rows.pop())
    assert checks["row_counts"] is False
    def swap(rows, *_):
        rows[:] = [metric_row(p, i) if f"{p}__{i.replace(':', '-')}" != FAILED else metric_row(p, i) for i in IDS for p in PROFILES]
        victim = next(r for r in rows if r["sample_id"] == "bart__fixture-01")
        victim.update(scoring_status="not_scoreable_generation_failed", failures={"record": "x"})
    checks, *_ = run_audit(tmp_path / "b", swap)
    assert checks["failed_cells_are_the_declared_ones"] is False


@pytest.mark.parametrize("name,mutate,check", [
    ("injected", lambda rows, views, costs, receipt: receipt.update(testing_dependency_injection=True), "not_injected"),
    ("cpu_runtime", lambda rows, views, costs, receipt: receipt["runtime"].update(device_name="cpu"), "actual_colab_t4"),
    ("no_t4_flag", lambda rows, views, costs, receipt: receipt.update(T4_verified=False), "actual_colab_t4"),
    ("hold", lambda rows, views, costs, receipt: receipt.update(delivered_status="HOLD"), "receipt_delivered_pass"),
    ("partial_views", lambda rows, views, costs, receipt: views.pop(), "view_rows_finite"),
    ("other_manifest", lambda rows, views, costs, receipt: receipt["binding"].update(package_manifest_sha256="0" * 64), "bundle_manifest_bound"),
    ("other_generation", lambda rows, views, costs, receipt: receipt["binding"].update(evidence_zip_sha256="0" * 64), "generation_evidence_bound"),
    ("no_resources", lambda rows, views, costs, receipt: costs.update(resources={}), "resources_measured"),
    ("qwen3", lambda rows, views, costs, receipt: rows[0].update(profile_id="qwen3"), "profiles_fixed_no_qwen3"),
    ("generation_ran", lambda rows, views, costs, receipt: receipt.update(generation_executed=True), "no_generation_no_selection"),
])
def test_each_integrity_violation_flips_its_check(tmp_path, name, mutate, check):
    checks, *_ = run_audit(tmp_path, mutate)
    assert checks[check] is False


def test_tampered_artifact_breaks_hash_check(tmp_path):
    root = write_evidence(tmp_path)
    path = Path(root) / "evidence/metrics.jsonl"
    path.write_text(path.read_text() + "\n")  # still valid JSON lines, different bytes
    checks, *_ = audit_module.audit(root, MANIFEST_SHA, contract(), ledger(), ALLOCATION)
    assert checks["artifact_hashes_match"] is False


@pytest.mark.parametrize("changes,anomaly", [
    ({"session_runs": ledger()["session_runs"][:2] + [{"status": "preflight_failed_before_any_model", "measured_wall_seconds": 6500.0, "granted_wall_seconds": 18000.0}]},
     "scoring_session_closed_as_preflight_failed_before_any_model"),
    ({"session_runs": ledger()["session_runs"][:2] + [{"status": "active", "measured_wall_seconds": None, "granted_wall_seconds": 18000.0}]},
     "scoring_session_still_active"),
    ({"gpu_seconds": 15 * 3600 + 1}, "cumulative_gpu_above_allocation"),
    ({"bundle_sha256": "0" * 64}, "ledger_bound_to_another_bundle"),
    ({"session_runs": ledger()["session_runs"][:1] + ledger()["session_runs"][2:]}, "scoring_session_is_not_the_third"),
    ({"session_runs": ledger()["session_runs"][:2] + [{"status": audit_module.CLOSED_STATUS, "measured_wall_seconds": 100.0, "granted_wall_seconds": 18000.0}]},
     "session_wall_shorter_than_runner_wall"),
    ({"session_runs": ledger()["session_runs"] + [copy.deepcopy(ledger()["session_runs"][2])]}, "session_count_above_allocation"),
])
def test_ledger_anomalies_are_listed(tmp_path, changes, anomaly):
    *_, anomalies = run_audit(tmp_path, ledger_value=ledger(**changes))
    assert anomaly in anomalies


def outcome(tmp_path, **kwargs):
    checks, rows, views, costs, receipt, anomalies = run_audit(tmp_path)
    return audit_module.build_outcome(checks, rows, costs, receipt, anomalies, contract(), RULES, "z" * 64, MANIFEST_SHA, **kwargs)


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


def test_outcome_describes_without_ranking_or_selection(tmp_path):
    result = outcome(tmp_path)
    json.dumps(result, allow_nan=False)  # text-free, serialisable
    assert result["audit_pass"] is True and result["rule_applied"] is False and result["coverage"]["rule_applied"] is False
    for key, item in walk_keys(result):
        assert not any(word in key.lower() for word in ("delta", "winner", "margin", "leader", "guard")), key
        if re.search(r"(^|_)rank", key.lower()):  # "lexrank" is a profile name, not a ranking field
            assert item is False, key
    assert "descriptive" in result["scores_descriptive"]["label"] or "not a ranking" in result["scores_descriptive"]["label"]
    assert set(result["timing_seconds"]) == set(audit_module.COMPONENTS)
    assert all(key.startswith("final523|") for key in result["projection_final523_from_selection300_measurement"])
    assert result["wall"]["within_conservative_estimate"] is True


def test_lead3_valid_139_note_is_descriptive_and_conditional(tmp_path):
    assert outcome(tmp_path / "a")["notes"] == []
    noted = outcome(tmp_path / "b", lead3_note_ids=("fixture:03",))
    assert len(noted["notes"]) == 1 and "kept unchanged" in noted["notes"][0]
    assert "valid:139" in noted["notes"][0]


def test_anomaly_makes_the_outcome_fail(tmp_path):
    checks, rows, views, costs, receipt, anomalies = run_audit(tmp_path, ledger_value=ledger(bundle_sha256="0" * 64))
    result = audit_module.build_outcome(checks, rows, costs, receipt, anomalies, contract(), RULES, "z" * 64, MANIFEST_SHA)
    assert result["audit_pass"] is False and "ledger_bound_to_another_bundle" in result["anomalies"]


def test_partial_evidence_without_a_whole_stratum_still_produces_an_outcome(tmp_path):
    def long_only(rows, views, costs, receipt):
        for r in rows:
            if r["source_stratum"] != "long" and r["scoring_status"] == "completed":
                r.update(scoring_status="not_attempted", metrics=dict.fromkeys(audit_module.METRICS),
                         failures={"record": "not_scored_due_to_HOLD"})
        receipt.update(delivered_status="HOLD", successful_metric_records=sum(
            r["scoring_status"] == "completed" for r in rows))
    checks, rows, views, costs, receipt, anomalies = run_audit(tmp_path, long_only)
    result = audit_module.build_outcome(checks, rows, costs, receipt, anomalies, contract(), RULES, "z" * 64, MANIFEST_SHA)
    assert result["audit_pass"] is False and result["projection_final523_from_selection300_measurement"] is None
