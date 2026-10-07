"""Official wrapper preserves failed video units in the primary denominator."""

from __future__ import annotations

import math

import pytest

from experiments.scripts.rq1_official_scorer import (
    OfficialScoreError, macro_primary_f1, score_official_unit,
)


def _score(predicted, reference=(40.0,), duration=100.0, unit="v1"):
    return score_official_unit(unit_id=unit, candidate="C1", predicted_sec=predicted,
                               reference_sec=reference, duration_sec=duration)


def test_sentinels_are_recorded_and_do_not_change_internal_score():
    scored = _score([0, 40, 100])
    assert scored["status"] == "run"
    assert scored["discarded_sentinel_count"] == 2
    assert scored["predicted_boundary_count"] == 1
    assert scored["normalized_prediction_sec"] == [40.0]
    assert scored["metrics"]["collar_f1_3s"] == 1.0
    assert scored["pk_wd_k_bins"] == 25


@pytest.mark.parametrize("prediction", [
    None, "40", [math.nan], [math.inf], [True], ["40"], [-1], [101], [40, 40],
])
def test_invalid_prediction_is_a_zero_score_failure(prediction):
    scored = _score(prediction)
    assert scored["status"] == "candidate_unit_failure"
    assert scored["metrics"]["collar_f1_3s"] == 0.0
    assert scored["metrics"]["pk"] is None
    assert scored["secondary_status"] == "not_scored_failure"
    assert scored["denominator_weight"] == 1
    assert scored["normalized_prediction_sec"] is None


def test_empty_single_chapter_and_failure_counted_in_macro():
    empty = _score([], reference=())
    assert empty["metrics"]["collar_f1_3s"] == 1.0
    failed = _score([101], unit="v2")
    summary = macro_primary_f1([empty, failed], expected_candidate="C1",
                               expected_unit_ids=["v1", "v2"])
    assert summary == {"macro_collar_f1_3s": 0.5, "unit_count": 2, "failure_count": 1}


def test_macro_requires_exact_candidate_and_cohort():
    first = _score([40], unit="v1")
    second = _score([40], unit="v2")
    expected = {"expected_candidate": "C1", "expected_unit_ids": ["v1", "v2"]}
    with pytest.raises(OfficialScoreError, match="cover"):
        macro_primary_f1([first], **expected)
    with pytest.raises(OfficialScoreError, match="different candidate"):
        macro_primary_f1([first, {**second, "candidate": "C2"}], **expected)
    with pytest.raises(OfficialScoreError, match="expected unit set"):
        macro_primary_f1([first, {**second, "unit_id": "v3"}], **expected)
    with pytest.raises(OfficialScoreError, match="expected unit set"):
        macro_primary_f1([first, first], **expected)
    with pytest.raises(OfficialScoreError, match="invalid status"):
        macro_primary_f1([first, {**second, "status": "not_run"}], **expected)
    with pytest.raises(OfficialScoreError, match="primary F1 zero"):
        macro_primary_f1([first, {**second, "status": "candidate_unit_failure"}], **expected)


def test_invalid_reference_is_cohort_gate_error():
    with pytest.raises(OfficialScoreError, match="reference boundary"):
        _score([40], reference=(0,))
    with pytest.raises(OfficialScoreError, match="increase strictly"):
        _score([40], reference=(40, 40))
    with pytest.raises(OfficialScoreError, match="duration_sec"):
        _score([40], duration=math.nan)
