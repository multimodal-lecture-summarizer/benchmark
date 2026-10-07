"""Unit tests for leaderboard_builder.py — Phase 7 verification."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, ".")

from experiments.scripts.registry_loader import load_registry, TaskID, LeaderboardWeights
from experiments.scripts.leaderboard_builder import (
    normalize_metric,
    compute_composite_score,
    build_task_leaderboard,
    bootstrap_ci_95,
    is_pareto_optimal,
    CandidateScore,
    TaskLeaderboard,
)
from experiments.scripts.ablation_runner import ComboResult


def test_normalize_higher_better():
    """Higher direction: best=1.0, worst=0.0, midpoint=0.5."""
    assert normalize_metric(10, "higher", [0, 5, 10]) == 1.0
    assert normalize_metric(0, "higher", [0, 5, 10]) == 0.0
    assert normalize_metric(5, "higher", [0, 5, 10]) == 0.5


def test_normalize_lower_better():
    """Lower direction: best=1.0, worst=0.0, midpoint=0.5."""
    assert normalize_metric(0, "lower", [0, 5, 10]) == 1.0
    assert normalize_metric(10, "lower", [0, 5, 10]) == 0.0
    assert normalize_metric(5, "lower", [0, 5, 10]) == 0.5


def test_normalize_binary():
    """Binary: 1.0 if value >= 0.99 else 0.0."""
    assert normalize_metric(1.0, "binary") == 1.0
    assert normalize_metric(0.99, "binary") == 1.0
    assert normalize_metric(0.5, "binary") == 0.0


def test_normalize_all_equal_returns_one():
    """All values equal → return 1.0 (perfect tie)."""
    assert normalize_metric(5, "higher", [5, 5, 5]) == 1.0
    assert normalize_metric(5, "lower", [5, 5, 5]) == 1.0


def test_normalize_handles_empty_list():
    """Empty list → return 1.0 (no comparison possible)."""
    assert normalize_metric(5, "higher", []) == 1.0


def test_normalize_works_without_all_values_arg():
    """Binary direction doesn't need all_values."""
    assert normalize_metric(1.0, "binary") == 1.0
    assert normalize_metric(0.0, "binary") == 0.0


def test_composite_score_in_range():
    """Composite score must be in [0, 1] for any valid metrics."""
    weights = {"wer": 0.4, "cer": 0.2, "rtf": 0.2, "success_rate": 0.2}
    directions = {"wer": "lower", "cer": "lower", "rtf": "lower", "success_rate": "binary"}
    metrics_a = {"wer": 11.0, "cer": 8.0, "rtf": 0.05, "success_rate": 1.0}
    all_seeds = [metrics_a, {"wer": 12.0, "cer": 9.0, "rtf": 0.06, "success_rate": 1.0}]
    score = compute_composite_score(metrics_a, weights, directions, all_seeds)
    assert 0.0 <= score <= 1.0, f"Composite score {score} out of range"


def test_composite_score_higher_for_better_metrics():
    """Better metrics → higher composite score."""
    weights = {"wer": 1.0}
    directions = {"wer": "lower"}
    all_seeds = [
        {"wer": 10.0},
        {"wer": 12.0},
        {"wer": 15.0},
    ]
    score_best = compute_composite_score({"wer": 10.0}, weights, directions, all_seeds)
    score_worst = compute_composite_score({"wer": 15.0}, weights, directions, all_seeds)
    assert score_best > score_worst


def test_build_task_leaderboard_picks_winner():
    """Best candidate (lowest WindowDiff + highest F1) wins."""
    mock = [
        ComboResult(combo_id="A", base_id="RQ1.C5", toggle_values={},
                     metrics={"window_diff": 0.10, "collar_f1_5s": 0.30},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
        ComboResult(combo_id="B", base_id="RQ1.C1", toggle_values={},
                     metrics={"window_diff": 0.20, "collar_f1_5s": 0.20},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
        ComboResult(combo_id="C", base_id="RQ1.C3", toggle_values={},
                     metrics={"window_diff": 0.15, "collar_f1_5s": 0.25},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
    ]
    _, _, weights_dict = load_registry()
    lb = build_task_leaderboard(TaskID.RQ1, mock, weights_dict[TaskID.RQ1])
    assert lb.winner_id == "A", f"Expected A to win, got {lb.winner_id}"
    assert lb.candidates[0].rank == 1


def test_pareto_detection():
    """A (best on all metrics) is Pareto-optimal; B (worst on all) is not."""
    mock = [
        ComboResult(combo_id="A", base_id="RQ1.C5", toggle_values={},
                     metrics={"window_diff": 0.10, "collar_f1_5s": 0.30},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
        ComboResult(combo_id="B", base_id="RQ1.C1", toggle_values={},
                     metrics={"window_diff": 0.20, "collar_f1_5s": 0.20},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
    ]
    _, _, weights_dict = load_registry()
    lb = build_task_leaderboard(TaskID.RQ1, mock, weights_dict[TaskID.RQ1])
    a_score = next(c for c in lb.candidates if c.candidate_id == "A")
    b_score = next(c for c in lb.candidates if c.candidate_id == "B")
    assert a_score.is_pareto_optimal is True
    assert b_score.is_pareto_optimal is False


def test_bootstrap_ci_95():
    """Bootstrap CI should give sensible bounds."""
    values = [0.5, 0.6, 0.7, 0.8, 0.9]
    lo, hi = bootstrap_ci_95(values, n_bootstrap=1000, seed=42)
    assert 0.0 <= lo <= 1.0
    assert 0.0 <= hi <= 1.0
    assert lo < hi


def test_leaderboard_to_json():
    """JSON export produces valid JSON with required keys."""
    import json
    mock = [
        ComboResult(combo_id="A", base_id="RQ1.C5", toggle_values={},
                     metrics={"window_diff": 0.10, "collar_f1_5s": 0.30},
                     runtime_sec=1.0, peak_vram_mb=0, success=True, seed=42),
    ]
    _, _, weights_dict = load_registry()
    lb = build_task_leaderboard(TaskID.RQ1, mock, weights_dict[TaskID.RQ1])
    d = lb.to_dict()
    assert "task" in d
    assert "winner" in d
    assert "candidates" in d
    assert d["winner"]["candidate_id"] == "A"
    # Should serialize to JSON
    json.dumps(d)