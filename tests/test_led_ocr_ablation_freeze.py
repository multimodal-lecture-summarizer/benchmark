import json
from pathlib import Path

import pytest

from experiments.scripts import led_ocr_ablation_freeze as freeze

REPO = Path(__file__).resolve().parents[2]


def rows():
    return freeze.read_shortlist(REPO / freeze.SHORTLIST)


def test_cohort_matches_plan():
    cohort = freeze.build_cohort(rows())
    assert cohort["count"] == 40
    assert cohort["strata_counts"] == freeze.EXPECTED_STRATA
    assert cohort["split_counts"] == {"test": 19, "train": 17, "valid": 4}
    assert all(v["core_ready"] for v in cohort["videos"])


def test_smoke_videos_are_outside_cohort():
    cohort = freeze.build_cohort(rows())
    ids = {v["id"] for v in cohort["videos"]}
    assert len(cohort["smoke_videos"]) == 3
    assert not ids & {v["id"] for v in cohort["smoke_videos"]}
    assert not any(v["core_ready"] for v in cohort["smoke_videos"])


def test_cohort_is_deterministic():
    assert freeze.canonical(freeze.build_cohort(rows())) == freeze.canonical(freeze.build_cohort(rows()))


def test_cohort_rejects_wrong_counts():
    bad = [r for r in rows() if r["id"] != freeze.build_cohort(rows())["videos"][0]["id"]]
    with pytest.raises(ValueError):
        freeze.build_cohort(bad)


def test_thresholds_match_approved_values():
    rules = freeze.DECISION_RULES
    assert rules["primary"]["margin"] == 0.01
    assert rules["guard"]["margin"] == 0.03
    assert rules["min_comparable_pairs"] == 32
    assert rules["interval"]["resamples"] == 10000


def test_segmenter_defaults_match_frozen_params():
    frozen = json.loads((REPO / freeze.FROZEN_PARAMS).read_text(encoding="utf-8"))
    source = (REPO / freeze.SEGMENTER_SOURCE).read_text(encoding="utf-8")
    assert freeze.segmenter_defaults_match(frozen, source)["block_threshold"] == 4.0


def test_segmenter_mismatch_is_rejected():
    frozen = {"params": {"block_threshold": 5.0}}
    source = "    block_threshold: float = 4.0\n"
    with pytest.raises(ValueError):
        freeze.segmenter_defaults_match(frozen, source)
