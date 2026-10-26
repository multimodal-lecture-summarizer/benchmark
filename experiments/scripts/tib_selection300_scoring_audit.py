"""Offline audit of the returned selection300 scoring evidence: integrity, coverage and cost; no ranking.

No metric call is made. Coverage and common-set sizes are measured against the floors in admission_rules_v2 only
as information (`rule_applied` stays false): no delta between profiles, no 0.01 ROUGE-L comparison, no Lead-3
guard, no tier A/B decision. Scores are development data and are labelled so.
"""
import argparse
import json
import statistics
from pathlib import Path

from experiments.scripts.tib_pilot40_scoring_audit import (
    PROFILES, STRATA, VIEW_METRICS, describe, finite, project, read_jsonl, sha256, timing_tables,
)

RECEIPT = "scorer_selection300_receipt.json"
METRICS = VIEW_METRICS + ("source_sentence_similarity_v1",)
ESTIMATE_HOURS = {"base": 1.42, "conservative": 3.0}
CLOSED_STATUS = "scoring_evidence_exported"
COMPONENTS = {"total": "new_scoring_wall_seconds", "bertscore": "bertscore_seconds",
              "source_similarity_sbert": "source_similarity_seconds", "rouge_and_other": "rouge_and_other_seconds"}
LEAD3_NOTE_IDS = ("valid:139",)
LEAD3_NOTE = ("Lead-3 valid:139 is cut mid-sentence at 350 words per the declared baseline; kept unchanged. "
              "Descriptive note on possible Lead-3 guard bias only; no score or guard adjusted.")


def is_success(row):
    """Scored success: scoring completed and ROUGE-L F1 finite (the declared definition)."""
    return row["scoring_status"] == "completed" and finite(row["metrics"].get("rougeL_f1")) and not row["failures"]


def ledger_review(ledger, allocation, contract, runner_wall_seconds):
    """Anomalies in the shared ledger after the scoring session; an empty list means nothing unusual."""
    anomalies = []
    runs = ledger["session_runs"]
    if ledger.get("bundle_sha256") != contract["generation_bundle_manifest_sha256"]:
        anomalies.append("ledger_bound_to_another_bundle")
    if len(runs) > allocation["max_sessions"]:
        anomalies.append("session_count_above_allocation")
    if ledger["gpu_seconds"] > allocation["total_gpu_hours"] * 3600:
        anomalies.append("cumulative_gpu_above_allocation")
    last = runs[-1]
    if last["status"] == "active":
        anomalies.append("scoring_session_still_active")
    elif last["status"] != CLOSED_STATUS:
        anomalies.append(f"scoring_session_closed_as_{last['status']}")
    measured = last.get("measured_wall_seconds")
    if measured is None or measured + 1 < runner_wall_seconds:
        anomalies.append("session_wall_shorter_than_runner_wall")
    elif measured > last["granted_wall_seconds"]:
        anomalies.append("session_wall_above_granted")
    if len(runs) < 3:
        anomalies.append("scoring_session_is_not_the_third")
    return anomalies


def audit(extracted, expected_bundle_manifest_sha, contract, ledger=None, allocation=None):
    """Return (checks, rows, views, costs, receipt, anomalies); every failed check is listed, none repaired."""
    root = Path(extracted) / "evidence"
    receipt = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
    costs = json.loads((root / "cost_evidence.json").read_text(encoding="utf-8"))
    rows = read_jsonl(root / "metrics.jsonl")
    views = read_jsonl(root / "view_metrics.jsonl")
    runtime = receipt["runtime"]
    expected_rows, expected_scoreable = contract["expected_rows"], contract["expected_scoreable"]
    scoreable = [r for r in rows if r["scoring_status"] == "completed"]
    failed_cells = [r for r in rows if r["scoring_status"] == "not_scoreable_generation_failed"]
    resources = costs.get("resources") or {}
    checks = {
        "receipt_delivered_pass": receipt["delivered_status"] == "PASS" and not receipt["reasons"],
        "views_complete": receipt["views_status"] == "COMPLETE",
        "actual_colab_t4": bool(runtime.get("google_colab_imported") and runtime.get("T4_device_observed")
                                and runtime.get("device_name") == "Tesla T4") and receipt.get("T4_verified") is True,
        "not_injected": receipt["testing_dependency_injection"] is False,
        "fixtures_pass": str(receipt["fixtures"].get("status")).lower() == "pass",
        "bundle_manifest_bound": receipt["binding"]["package_manifest_sha256"] == expected_bundle_manifest_sha,
        "generation_evidence_bound": receipt["binding"]["evidence_zip_sha256"] == contract["generation_evidence_zip_sha256"],
        "artifact_hashes_match": bool(receipt["artifact_sha256"]) and all(
            sha256(root / n) == h for n, h in receipt["artifact_sha256"].items()),
        "row_counts": len(rows) == expected_rows and len(scoreable) == expected_scoreable
                      and len(failed_cells) == expected_rows - expected_scoreable,
        "failed_cells_are_the_declared_ones": sorted(r["sample_id"] for r in failed_cells) == sorted(contract["failed_cells"])
                                              and all(r["failures"].get("record") for r in failed_cells),
        "profiles_fixed_no_qwen3": all(r["profile_id"] in PROFILES for r in rows) and receipt["qwen3_scored"] is False,
        "five_metrics_finite": all(all(finite(r["metrics"].get(m)) for m in METRICS) and not r["failures"]
                                   for r in scoreable),
        "failed_cells_null": all(all(v is None for v in r["metrics"].values()) for r in failed_cells),
        "view_rows_finite": len(views) == expected_scoreable and all(
            finite(s["metrics"].get(m)) and not s["failures"] for v in views for s in v["views"].values()
            for m in VIEW_METRICS) and all(set(v["views"]) == {"S", "M", "L"} for v in views),
        "no_generation_no_selection": receipt["generation_executed"] is False
                                      and receipt["selection_start_authorized"] is False,
        "resources_measured": all(finite(resources.get(k)) and resources[k] > 0
                                  for k in ("wall_seconds", "cpu_seconds", "cuda_peak_reserved_bytes")),
    }
    anomalies = []
    if ledger is not None:
        anomalies = ledger_review(ledger, allocation, contract, costs["total_wall_seconds"])
    return checks, rows, views, costs, receipt, anomalies


def coverage(rows, contract, rules):
    """Measured coverage per profile x stratum and the common set; floors are shown for information only."""
    quotas, strata = contract["quotas"], contract["source_strata"]
    config, common = rules["config_coverage"], rules["common_coverage"]
    success = {p: {r["record_id"] for r in rows if r["profile_id"] == p and is_success(r)} for p in PROFILES}
    total = len(contract["selection_ids"])
    per_profile = {}
    for p in PROFILES:
        by_stratum = {s: sum(strata[i] == s for i in success[p]) for s in STRATA}
        generated = sum(r["profile_id"] == p and r["scoring_status"] != "not_scoreable_generation_failed" for r in rows)
        per_profile[p] = {
            "denominator": total, "generated": generated, "scored_success": len(success[p]),
            "rougeL_finite": len(success[p]), "by_stratum": by_stratum,
            "overall_fraction": len(success[p]) / total,
            "stratum_fraction": {s: by_stratum[s] / quotas[s] for s in STRATA},
            "informational_floors": {
                "overall_min": config["overall_min"], "per_stratum_min": config["per_stratum_min"],
                "overall_met": len(success[p]) / total >= config["overall_min"],
                "per_stratum_met": {s: by_stratum[s] / quotas[s] >= config["per_stratum_min"] for s in STRATA}}}
    between = set.intersection(*success.values())
    by_stratum = {s: sum(strata[i] == s for i in between) for s in STRATA}
    return {"per_profile": per_profile,
            "c_between": {"size": len(between), "by_stratum": by_stratum, "fraction": len(between) / total,
                          "stratum_fraction": {s: by_stratum[s] / quotas[s] for s in STRATA},
                          "informational_floors": {
                              "common_n_min": common["common_n_min"], "common_n_met": len(between) >= common["common_n_min"],
                              "per_nonempty_stratum_n_min": common["per_nonempty_stratum_n_min"],
                              "per_stratum_n_met": {s: by_stratum[s] >= common["per_nonempty_stratum_n_min"]
                                                    for s in STRATA if by_stratum[s]},
                              "overall_min": common["overall_min"], "per_stratum_min": common["per_stratum_min"]}},
            "rule_applied": False,
            "note": "measured sizes only; PASS/FAIL here is information, not the tier A/B decision"}


def timing(rows):
    """Seconds per component x profile x stratum for newly scored outputs."""
    fresh = [r for r in rows if r["scoring_status"] == "completed" and not r.get("reused")]
    out = {}
    for component, key in COMPONENTS.items():
        cells = {}
        for r in fresh:
            cells.setdefault(f"{r['profile_id']}|{r['source_stratum']}", []).append(r[key])
        out[component] = {name: describe(values) for name, values in sorted(cells.items())}
    return out


def descriptive_means(rows):
    def mean(p, s, m):
        values = [r["metrics"][m] for r in rows if is_success(r) and r["profile_id"] == p and r["source_stratum"] == s]
        return statistics.fmean(values) if values else None
    return {f"{p}|{s}": {m: mean(p, s, m) for m in VIEW_METRICS} for p in PROFILES for s in STRATA}


def build_outcome(checks, rows, costs, receipt, anomalies, contract, rules, zip_sha, manifest_sha, lead3_note_ids=LEAD3_NOTE_IDS):
    _, per_stratum = timing_tables(rows)
    scored = receipt["successful_metric_records"]
    extra = ((costs["view_scoring_seconds"] + costs["checkpoint_seconds"] + costs["input_profiling_seconds"]) / scored
             if scored else None)
    # A partial run can leave a stratum unmeasured; the projection is then withheld, not guessed.
    projectable = extra is not None and all(per_stratum[s]["mean"] is not None for s in STRATA)
    notes = [LEAD3_NOTE] if any(r["profile_id"] == "lead3" and r["record_id"] in lead3_note_ids and is_success(r)
                                for r in rows) else []
    wall_hours = costs["total_wall_seconds"] / 3600
    means = descriptive_means(rows)
    return {
        "schema_version": 1, "protocol_id": "tib-selection300-scoring-261024-v1",
        "scope": "text-free summary of selection300 reference scoring (4 profiles, no Qwen3); descriptive only",
        "evidence_zip_sha256": zip_sha, "bundle_manifest_sha256": manifest_sha,
        "audit_checks": checks, "audit_pass": all(checks.values()) and not anomalies, "anomalies": anomalies,
        "notes": notes,
        "counts": {"cells": len(rows), "scored": scored, "failed_generation_cells": receipt["failed_generation_cells"]},
        "coverage": coverage(rows, contract, rules),
        "timing_seconds": timing(rows),
        "wall": {"total_hours": wall_hours, "estimate_hours": ESTIMATE_HOURS,
                 "within_conservative_estimate": wall_hours <= ESTIMATE_HOURS["conservative"]},
        "fixed_costs": {k: costs[k] for k in ("initialization_seconds", "fixtures_seconds", "view_scoring_seconds",
                                              "checkpoint_seconds", "input_profiling_seconds", "total_wall_seconds",
                                              "new_view_calls", "reused_identical_view_texts")},
        "resources": costs["resources"], "per_output_extra_seconds": extra,
        "projection_final523_from_selection300_measurement": {
            k: v for k, v in project(per_stratum, extra).items() if k.startswith("final523|")} if projectable else None,
        "scores_descriptive": {"label": "development data, not a ranking; selection rule not applied", "means": means},
        "rule_applied": False,
        "claim_limit": "Selection300 development data; no ranking, no model selection, no tier A/B decision",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="folder holding the extracted evidence/ directory")
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--contract", required=True, type=Path, help="scoring_contract.json")
    parser.add_argument("--rules", required=True, type=Path, help="admission_rules_v2.json (floors shown for information)")
    parser.add_argument("--ledger", required=True, type=Path, help="resource_ledger_after_scoring.json")
    parser.add_argument("--allocation", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
    contract, rules = load(args.contract), load(args.rules)
    checks, rows, _, costs, receipt, anomalies = audit(args.evidence, args.manifest_sha, contract,
                                                       load(args.ledger), load(args.allocation))
    outcome = build_outcome(checks, rows, costs, receipt, anomalies, contract, rules, sha256(args.zip), args.manifest_sha)
    args.out.write_text(json.dumps(outcome, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": outcome["audit_pass"], "failed": [k for k, v in checks.items() if not v],
                      "anomalies": anomalies}))


if __name__ == "__main__":
    main()
