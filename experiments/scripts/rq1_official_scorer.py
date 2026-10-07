"""Strict per-video RQ1 scoring around the shared frozen chapter scorer."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from benchmarks.metrics.chapter_metrics import boundaries_to_binary_sequence
from experiments.scripts.chapter_benchmark_contract import score_chapters


class OfficialScoreError(ValueError):
    """Reference or duration is invalid, so this unit cannot be scored."""


def _duration(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise OfficialScoreError("duration_sec must be a positive finite number")
    return float(value)


def _reference(values: Any, duration: float) -> list[float]:
    if not isinstance(values, (list, tuple)):
        raise OfficialScoreError("reference boundaries must be a list or tuple")
    result: list[float] = []
    for value in values:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 < value < duration):
            raise OfficialScoreError("reference boundary outside internal timeline")
        if result and value <= result[-1]:
            raise OfficialScoreError("reference boundaries must increase strictly")
        result.append(float(value))
    return result


def _prediction(values: Any, duration: float) -> tuple[list[float], int]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("prediction payload must be a list or tuple")
    result: list[float] = []
    sentinel_count = 0
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("prediction contains malformed or nonfinite timestamp")
        stamp = float(value)
        if stamp == 0 or stamp == duration:
            sentinel_count += 1
        elif not 0 < stamp < duration:
            raise ValueError("prediction outside internal timeline")
        else:
            result.append(stamp)
    if len(set(result)) != len(result):
        raise ValueError("prediction contains duplicate internal boundary")
    return sorted(result), sentinel_count


def score_official_unit(
    *, unit_id: str, candidate: str, predicted_sec: Any,
    reference_sec: Sequence[float], duration_sec: float,
) -> dict[str, Any]:
    """Return one record even on candidate failure, with primary F1 set to zero.

    A bad reference/duration is a cohort gate error and raises. A bad candidate
    prediction remains in the denominator with secondary metrics unscored.
    """
    if not unit_id or not candidate:
        raise OfficialScoreError("unit_id and candidate are required")
    duration = _duration(duration_sec)
    reference = _reference(reference_sec, duration)
    binary = boundaries_to_binary_sequence(reference, duration, step_sec=1.0)
    k = max(1, round((len(binary) / (sum(binary) + 1)) / 2))
    base: dict[str, Any] = {
        "unit_id": unit_id, "candidate": candidate, "duration_sec": duration,
        "reference_boundary_count": len(reference), "pk_wd_k_bins": k,
        "pk_wd_step_sec": 1.0, "denominator_weight": 1,
    }
    try:
        prediction, sentinel_count = _prediction(predicted_sec, duration)
    except ValueError as exc:
        return {
            **base, "status": "candidate_unit_failure", "failure_reason": str(exc),
            "discarded_sentinel_count": None, "predicted_boundary_count": None,
            "normalized_prediction_sec": None,
            "metrics": {"collar_f1_3s": 0.0, "collar_f1_5s": None,
                        "collar_f1_10s": None, "pk": None, "window_diff": None},
            "secondary_status": "not_scored_failure",
        }
    return {
        **base, "status": "run", "failure_reason": None,
        "discarded_sentinel_count": sentinel_count,
        "predicted_boundary_count": len(prediction),
        "normalized_prediction_sec": prediction,
        "metrics": score_chapters(prediction, reference, duration),
        "secondary_status": "scored",
    }


def macro_primary_f1(
    records: Sequence[dict[str, Any]], *, expected_candidate: str,
    expected_unit_ids: Sequence[str],
) -> dict[str, float | int]:
    """Macro mean for exactly one candidate and the complete expected cohort."""
    if not isinstance(expected_candidate, str) or not expected_candidate:
        raise OfficialScoreError("expected_candidate is required")
    if (not isinstance(expected_unit_ids, (list, tuple)) or not expected_unit_ids
            or any(not isinstance(uid, str) or not uid for uid in expected_unit_ids)
            or len(set(expected_unit_ids)) != len(expected_unit_ids)):
        raise OfficialScoreError("expected_unit_ids must be a nonempty unique list")
    if len(records) != len(expected_unit_ids):
        raise OfficialScoreError("score records do not cover the expected unit set")
    if any(row.get("candidate") != expected_candidate for row in records):
        raise OfficialScoreError("score records contain a different candidate")
    unit_ids = [row.get("unit_id") for row in records]
    if len(set(unit_ids)) != len(unit_ids) or set(unit_ids) != set(expected_unit_ids):
        raise OfficialScoreError("score records do not match the expected unit set")
    if any(row.get("status") not in {"run", "candidate_unit_failure"} for row in records):
        raise OfficialScoreError("score records contain an invalid status")
    values = [row.get("metrics", {}).get("collar_f1_3s") for row in records]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           or not 0 <= v <= 1 for v in values):
        raise OfficialScoreError("each unit needs a primary F1 in [0, 1]")
    if any(row["status"] == "candidate_unit_failure" and value != 0
           for row, value in zip(records, values)):
        raise OfficialScoreError("failed candidate units must have primary F1 zero")
    return {
        "macro_collar_f1_3s": sum(values) / len(values),
        "unit_count": len(values),
        "failure_count": sum(row.get("status") == "candidate_unit_failure" for row in records),
    }
