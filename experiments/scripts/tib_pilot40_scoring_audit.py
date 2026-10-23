"""Offline audit of the Pilot40 scoring evidence and the scoring-hours projection for selection300/final523.

No metric call is made. The projection reuses the 18:42 budget method: base = stratum mean x quota,
conservative = stratum p90 x quota x 1.5, stress = stratum max x quota x 1.5; sessions give 4.14 h of
real work each, 0.75 h overhead per session and 0.5 h recovery per resume.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

VIEW_METRICS = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1")
METRICS = VIEW_METRICS + ("source_sentence_similarity_v1",)
PROFILES = ("lead3", "lexrank", "bart", "led")
STRATA = ("short", "medium", "long")
QUOTAS = {"selection300": {"short": 100, "medium": 90, "long": 110},
          "final523": {"short": 182, "medium": 172, "long": 169}}
# Generation hours (bart + led) from the 18:42 budget update; unchanged by scoring measurements.
GENERATION_HOURS = {("selection300", "base"): 1.05 + 1.28, ("selection300", "conservative"): 1.27 + 1.71,
                    ("selection300", "stress"): 1.39 + 1.99, ("final523", "base"): 1.78 + 2.16,
                    ("final523", "conservative"): 2.12 + 2.86, ("final523", "stress"): 2.33 + 3.32}
SAFETY, WORK_PER_SESSION, OVERHEAD, RECOVERY, LOSS_SLICE = 1.5, 4.14, 0.75, 0.5, 5.75


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def describe(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "mean": None, "p50": None, "p90": None, "max": None}
    def at(q):
        pos = (len(values) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    return {"n": len(values), "mean": statistics.fmean(values), "p50": at(0.5), "p90": at(0.9), "max": values[-1]}


def audit(evidence_dir, expected_bundle_manifest_sha, expected_rows=160, expected_scoreable=154):
    """Return (checks, per-row metric rows); every failed check is listed, none is repaired."""
    root = Path(evidence_dir) / "evidence"
    receipt = json.loads((root / "scorer_pilot40_receipt.json").read_text(encoding="utf-8"))
    costs = json.loads((root / "cost_evidence.json").read_text(encoding="utf-8"))
    rows = read_jsonl(root / "metrics.jsonl")
    views = read_jsonl(root / "view_metrics.jsonl")
    runtime = receipt["runtime"]
    scoreable = [r for r in rows if r["scoring_status"] == "completed"]
    failed_cells = [r for r in rows if r["scoring_status"] == "not_scoreable_generation_failed"]
    checks = {
        "receipt_delivered_pass": receipt["delivered_status"] == "PASS" and not receipt["reasons"],
        "views_complete": receipt["views_status"] == "COMPLETE",
        "actual_colab_t4": bool(runtime.get("google_colab_imported") and runtime.get("T4_device_observed")
                                and runtime.get("device_name") == "Tesla T4") and receipt["T4_verified"],
        "not_injected": receipt["testing_dependency_injection"] is False,
        "fixtures_pass": str(receipt["fixtures"].get("status")).lower() == "pass",
        "bundle_manifest_bound": receipt["binding"]["package_manifest_sha256"] == expected_bundle_manifest_sha,
        "artifact_hashes_match": all(sha256(root / n) == h for n, h in receipt["artifact_sha256"].items()),
        "row_counts": len(rows) == expected_rows and len(scoreable) == expected_scoreable
                       and len(failed_cells) == expected_rows - expected_scoreable,
        "no_qwen3": all(r["profile_id"] in PROFILES for r in rows) and receipt["qwen3_scored"] is False,
        "five_metrics_finite": all(all(finite(r["metrics"].get(m)) for m in METRICS) and not r["failures"]
                                   for r in scoreable),
        "failed_cells_null": all(all(v is None for v in r["metrics"].values()) for r in failed_cells),
        "view_rows_finite": len(views) == expected_scoreable and all(
            finite(s["metrics"].get(m)) and not s["failures"] for v in views for s in v["views"].values()
            for m in VIEW_METRICS),
        "no_generation_no_selection": receipt["generation_executed"] is False
                                      and receipt["selection_start_authorized"] is False,
        "resources_recorded": all(finite(costs["resources"].get(k)) and costs["resources"][k] > 0
                                  for k in ("wall_seconds", "cpu_seconds", "cuda_peak_reserved_bytes")),
    }
    return checks, rows, views, costs, receipt


def timing_tables(rows):
    cells = {}
    for r in rows:
        if r["scoring_status"] == "completed":
            cells.setdefault((r["profile_id"], r["source_stratum"]), []).append(r["new_scoring_wall_seconds"])
    by_stratum = {s: [v for (p, st), vs in cells.items() if st == s for v in vs] for s in STRATA}
    return ({f"{p}|{s}": describe(v) for (p, s), v in sorted(cells.items())},
            {s: describe(v) for s, v in by_stratum.items()})


def component_shares(rows):
    done = [r for r in rows if r["scoring_status"] == "completed"]
    total = sum(r["new_scoring_wall_seconds"] for r in done)
    parts = {"bertscore": sum(r["bertscore_seconds"] for r in done),
             "source_similarity_sbert": sum(r["source_similarity_seconds"] for r in done),
             "rouge_and_other": sum(r["rouge_and_other_seconds"] for r in done)}
    by_stratum = {s: {"seconds_mean_sbert": statistics.fmean([r["source_similarity_seconds"] for r in done if r["source_stratum"] == s]),
                      "seconds_mean_bertscore": statistics.fmean([r["bertscore_seconds"] for r in done if r["source_stratum"] == s]),
                      "mean_source_sentences": statistics.fmean([r["source_sentence_count"] for r in done if r["source_stratum"] == s])}
                  for s in STRATA}
    return {"total_seconds": total, "seconds": parts, "share": {k: v / total for k, v in parts.items()},
            "by_stratum": by_stratum}


def project(stratum_stats, per_output_extra, sbert_fraction_by_stratum=None, drop_sbert=False):
    """Hours per stage and level. per_output_extra = views + checkpoint + profiling seconds per scored output."""
    out = {}
    for stage, quota in QUOTAS.items():
        for level, factor, key in (("base", 1.0, "mean"), ("conservative", SAFETY, "p90"), ("stress", SAFETY, "max")):
            seconds = 0.0
            for s in STRATA:
                per = stratum_stats[s][key]
                if drop_sbert:
                    per = max(0.0, per - sbert_fraction_by_stratum[s][key])
                seconds += (per + per_output_extra) * quota[s] * len(PROFILES) * factor
            scoring = seconds / 3600
            work = GENERATION_HOURS[(stage, level)] + scoring
            sessions = math.ceil(work / WORK_PER_SESSION)
            wall = work + OVERHEAD * sessions + RECOVERY * (sessions - 1)
            out[f"{stage}|{level}"] = {"scoring_hours": scoring, "generation_hours": GENERATION_HOURS[(stage, level)],
                                       "work_hours": work, "sessions": sessions, "wall_equals_gpu_hours": wall,
                                       "ceiling_with_loss_slice": math.ceil(wall + LOSS_SLICE)}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="folder holding the extracted evidence/ directory")
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    checks, rows, views, costs, receipt = audit(args.evidence, args.manifest_sha)
    per_cell, per_stratum = timing_tables(rows)
    shares = component_shares(rows)
    scored = receipt["successful_metric_records"]
    extra = (costs["view_scoring_seconds"] + costs["checkpoint_seconds"] + costs["input_profiling_seconds"]) / scored
    # SBERT-only per-stratum statistics (p90/max of the component itself) for the "drop SBERT" what-if.
    sbert = {s: describe([r["source_similarity_seconds"] for r in rows
                          if r["scoring_status"] == "completed" and r["source_stratum"] == s]) for s in STRATA}
    outcome = {
        "schema_version": 1, "protocol_id": "tib-pilot40-scoring-261023-v1",
        "scope": "text-free summary of Pilot40 reference scoring (4 profiles, no Qwen3); descriptive, no ranking",
        "evidence_zip_sha256": sha256(args.zip), "bundle_manifest_sha256": args.manifest_sha,
        "audit_checks": checks, "audit_pass": all(checks.values()),
        "counts": {"cells": len(rows), "scored": scored, "failed_generation_cells": receipt["failed_generation_cells"]},
        "timing_by_profile_stratum_seconds": per_cell, "timing_by_stratum_seconds": per_stratum,
        "component_shares": shares, "sbert_seconds_by_stratum": sbert,
        "fixed_costs": {k: costs[k] for k in ("initialization_seconds", "fixtures_seconds", "view_scoring_seconds",
                                              "checkpoint_seconds", "input_profiling_seconds", "total_wall_seconds",
                                              "new_view_calls", "reused_identical_view_texts")},
        "resources": costs["resources"], "per_output_extra_seconds": extra,
        "projection_scorer_v2_as_is": project(per_stratum, extra),
        "projection_without_sbert_what_if": project(per_stratum, extra, sbert, drop_sbert=True),
        "metric_means_descriptive": {
            f"{p}|{s}": {m: statistics.fmean([r["metrics"][m] for r in rows if r["profile_id"] == p
                                              and r["source_stratum"] == s and r["scoring_status"] == "completed"])
                         for m in ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1")}
            for p in PROFILES for s in STRATA},
        "claim_limit": "Pilot40 development data; no ranking, no model selection; 11-15 outputs per profile x stratum",
    }
    args.out.write_text(json.dumps(outcome, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": outcome["audit_pass"], "failed": [k for k, v in checks.items() if not v]}))


if __name__ == "__main__":
    main()
