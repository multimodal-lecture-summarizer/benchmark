"""Measured plot tables for candidate dataset readiness; no official D2 claims."""

from __future__ import annotations

import math
from typing import Any


def observed_numbers(records: list[dict], field: str) -> list[float]:
    values = []
    for row in records:
        value = row.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field}: expected a measured number or null")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{field}: non-finite or negative measurement")
        values.append(float(value))
    return values


def fixed_bins(protocol: dict, field: str, values: list[float]) -> list[float]:
    defaults = {
        "duration_sec": [0, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1800, 3600, 14400, 86400],
        "file_size_bytes": [0, 10_000, 30_000, 100_000, 300_000, 1_000_000,
                            3_000_000, 10_000_000, 30_000_000, 100_000_000,
                            1_000_000_000, 1_000_000_000_000],
    }
    protocol_key = "histogram_duration_edges" if field == "duration_sec" else "histogram_bytes_edges"
    bins = protocol.get(protocol_key, protocol.get("plot_bins", {}).get(field, defaults[field]))
    if (not isinstance(bins, list) or len(bins) < 2
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in bins)
            or any(a >= b for a, b in zip(bins, bins[1:]))):
        raise ValueError(f"invalid preregistered bins: {field}")
    if values and (min(values) < bins[0] or max(values) > bins[-1]):
        raise ValueError(f"{field}: measurements outside preregistered bins; no silent truncation")
    return list(bins)


def plot_tables(dataset_id: str, records: list[dict], audit: dict, protocol: dict) -> dict[str, Any]:
    """Freeze plotted values before rendering so sidecars reproduce each chart."""
    if not records:
        raise ValueError("readiness figures require selected records")
    if any(r.get("decision") not in {"keep", "exclude"} for r in records):
        raise ValueError("readiness figures require explicit keep/exclude decisions")
    if any(not isinstance(r.get("split"), str) or not r["split"] for r in records):
        raise ValueError("readiness figure record has missing split")
    splits = sorted({r["split"] for r in records})
    grouped = {s: [r for r in records if r["split"] == s] for s in splits}
    kept = [r for r in records if r["decision"] == "keep"]
    image_only = dataset_id == "iiit_cvid" or protocol.get("modality") == "image"
    durations = observed_numbers(records, "duration_sec")
    if image_only and durations:
        raise ValueError("still-image duration must be null, not a zero observation")
    sizes = observed_numbers(records, "bytes")
    fields = ["reference_text", "decoded", "speaker_id", "talk_id", "duration_sec"]
    coverage = []
    for split in splits:
        rows = grouped[split]
        coverage.append([
            None if field == "duration_sec" and image_only else
            sum((r.get(field) is True if field == "decoded" else
                 r.get(field) is not None if field == "duration_sec" else
                 (bool(str(r.get(field) or "").strip()) and not r.get("ground_truth_error")
                  and str(r.get(field) or "").strip() != "ignore_time_segment_in_scoring")
                 if field == "reference_text" else
                 bool(str(r.get(field) or "").strip())) for r in rows) / len(rows) * 100
            for field in fields
        ])
    matrices = {}
    for field in ("speaker_id", "talk_id"):
        sets = {s: {str(r[field]) for r in kept if r["split"] == s and r.get(field)} for s in splits}
        matrices[field] = [[len(sets[left] & sets[right]) for right in splits] for left in splits]
    pairs = audit.get("pairs", [])
    pair_coverage = audit.get("pair_coverage", [])
    pair_splits = sorted(set(splits) | set(audit.get("cohort_counts", {})) |
                         {str(p.get(k) or "unknown") for p in pairs + pair_coverage for k in ("left_split", "right_split")})
    pair_matrices = {name: [[0] * len(pair_splits) for _ in pair_splits] for name in ("exact", "near")}
    for pair in pairs:
        kind = str(pair.get("kind", "")).lower()
        category = "exact" if "exact" in kind or "identity" in kind else "near"
        left = pair_splits.index(str(pair.get("left_split") or "unknown"))
        right = pair_splits.index(str(pair.get("right_split") or "unknown"))
        pair_matrices[category][left][right] += 1
        if left != right:
            pair_matrices[category][right][left] += 1
    measured_coverage = {}
    for row in pair_coverage:
        key = tuple(sorted((row["left_split"], row["right_split"])))
        expected, completed = row["expected_pairs"], row["completed_pairs"]
        if (key in measured_coverage or type(expected) is not int or type(completed) is not int
                or not 0 <= completed <= expected):
            raise ValueError("invalid or duplicate pair coverage")
        measured_coverage[key] = (expected, completed)
    hit_lower_bounds = pair_matrices
    pair_matrices = {name: [list(row) for row in matrix] for name, matrix in hit_lower_bounds.items()}
    completion = []
    for i, left in enumerate(pair_splits):
        completion_row = []
        for j, right in enumerate(pair_splits):
            expected, completed = measured_coverage.get(tuple(sorted((left, right))), (0, 0))
            completion_row.append({"expected_pairs": expected, "completed_pairs": completed})
            if expected == 0 or completed < expected:
                for matrix in pair_matrices.values():
                    matrix[i][j] = None
        completion.append(completion_row)
    return {
        "scale_bytes": {"splits": splits,
                        "bytes": [sum(values) if values else None for values in
                                  (observed_numbers(grouped[s], "bytes") for s in splits)],
                        "measured_n": [len(observed_numbers(grouped[s], "bytes")) for s in splits],
                        "missing_n_by_split": [len(grouped[s]) - len(observed_numbers(grouped[s], "bytes")) for s in splits],
                        "missing_n": len(records) - len(sizes), "measure_policy": "sum_of_observed_bytes_only"},
        "duration_distribution": {"values": sorted(durations), "bins": fixed_bins(protocol, "duration_sec", durations),
                                  "unit": "seconds", "applicability": "not_applicable" if image_only else "applicable",
                                  "reason": "Still frames; elapsed duration is not defined" if image_only else None,
                                  "missing_n": 0 if image_only else len(records) - len(durations),
                                  "not_applicable_n": len(records) if image_only else 0},
        "file_size_distribution": {"values": sorted(sizes), "bins": fixed_bins(protocol, "file_size_bytes", sizes),
                                   "unit": "bytes", "missing_n": len(records) - len(sizes)},
        "missingness_gt_coverage": {"splits": splits, "fields": fields, "observed_percent": coverage,
                                    "split_n": [len(grouped[s]) for s in splits]},
        "attrition_waterfall": {"selected": len(records), "decoded": sum(r.get("decoded") is True for r in records),
                               "kept": len(kept), "excluded": len(records) - len(kept)},
        "split_comparison": {"splits": splits, "selected": [len(grouped[s]) for s in splits],
                             "kept": [sum(r["decision"] == "keep" for r in grouped[s]) for s in splits]},
        "source_overlap": {"splits": splits, "matrices": matrices, "population": "kept",
                           "missing_group_metadata_n": {f: sum(not r.get(f) for r in kept) for f in ("speaker_id", "talk_id")},
                           "labels": ["course_id", "video_id"] if image_only else ["speaker_id", "talk_id"]},
        "duplicate_matrix": {"splits": pair_splits, "matrices": pair_matrices,
                             "recorded_hit_lower_bounds": hit_lower_bounds,
                             "completion": completion,
                             "expected_pairs": sum(v[0] for v in measured_coverage.values()),
                             "completed_pairs": sum(v[1] for v in measured_coverage.values()),
                             "pair_count": len(pairs), "population": "all selected screening hits, before exclusions",
                             "methods": sorted({str(p.get("method", p.get("kind"))) for p in pairs}),
                             "audit_status": audit.get("status", "unknown"),
                             "historical_count": audit.get("historical_count", 0)},
    }
