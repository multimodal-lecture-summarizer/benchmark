"""Precision planning must consume only complete locked validation pairs."""

import json
from pathlib import Path

import pytest

from experiments.scripts.rq1_validation_precision_gate import plan_validation_precision


ROOT = Path(__file__).resolve().parents[2]
SPLIT = json.loads((ROOT / "plans/reports/rq1-split-260930-8-4-8-locked.json").read_text())
VALIDATION_IDS = [row["video_id"] for row in SPLIT if row["split"] == "validation"]


def _scores(values):
    return [{"unit_id": uid, "candidate": candidate, "status": "run",
             "metrics": {"collar_f1_3s": values.get((uid, candidate), 0.5)}}
            for uid in VALIDATION_IDS for candidate in ("C1", "C2", "C3", "C4", "C5", "C6")]


def test_precision_gate_rejects_sealed_test_score_even_with_complete_validation():
    scores = _scores({})
    final_id = next(row["video_id"] for row in SPLIT if row["split"] == "final_test")
    scores.append({"unit_id": final_id, "candidate": "C1", "status": "run",
                   "metrics": {"collar_f1_3s": 0.5}})
    with pytest.raises(ValueError, match="outside locked validation"):
        plan_validation_precision(SPLIT, scores)


def test_precision_gate_requires_all_paired_candidates_and_uses_sample_sd():
    values = {(uid, "C2"): value for uid, value in zip(VALIDATION_IDS, (0.2, 0.4, 0.6, 0.8))}
    result = plan_validation_precision(SPLIT, _scores(values))
    assert result["status"] == "planning_threshold_pass"
    assert result["required_final_test_groups"] == 8
    assert result["contrasts"]["C2-C1"]["sample_sd"] == pytest.approx(0.2581988897471611)
    with pytest.raises(ValueError, match="incomplete paired"):
        plan_validation_precision(SPLIT, _scores(values)[:-1])
