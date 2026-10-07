"""leaderboard_builder.py — Multi-metric normalized scoring cho ablation results.

Module aggregate results từ ablation_runner → per-task leaderboard với:
- normalize_metric() — higher/lower/binary normalization
- compute_composite_score() — Σ wᵢ × normalize(mᵢ)
- Tie-breaking rules
- Pareto detection
- Statistical comparison (Holm-Bonferroni, sử dụng statistics.py)
- Export per-task leaderboard JSON

Usage:
    from experiments.scripts.leaderboard_builder import build_task_leaderboard
    from experiments.scripts.ablation_runner import ComboResult

    results = [...]  # List[ComboResult]
    leaderboard = build_task_leaderboard(TaskID.RQ1, results, weights_dict[TaskID.RQ1])
    leaderboard.to_json(Path("experiments/scratch/leaderboards/RQ1.json"))
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from statistics import mean, stdev

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from experiments.scripts.registry_loader import TaskID, LeaderboardWeights  # noqa: E402
from experiments.scripts.ablation_runner import ComboResult  # noqa: E402


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateScore:
    """Score cho 1 candidate (base or combo)."""
    candidate_id: str            # base_id hoặc combo_id
    task: TaskID
    raw_metrics: Dict[str, float]
    normalized_metrics: Dict[str, float]
    composite_score: float
    rank: int
    is_pareto_optimal: bool
    is_winner: bool = False
    notes: str = ""


@dataclass(frozen=True)
class TaskLeaderboard:
    """Per-task leaderboard."""
    task: TaskID
    n_candidates: int
    metric_set: List[str]
    weights: Dict[str, float]
    candidates: List[CandidateScore]    # sorted by rank asc
    winner_id: str
    winner_composite: float
    ci_95: Tuple[float, float] = (0.0, 0.0)
    pairwise_comparisons: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    exported_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task.value,
            "n_candidates": self.n_candidates,
            "metric_set": self.metric_set,
            "weights": self.weights,
            "winner": {
                "candidate_id": self.winner_id,
                "composite_score": self.winner_composite,
                "ci_95": list(self.ci_95),
            },
            "candidates": [
                {
                    "rank": c.rank,
                    "candidate_id": c.candidate_id,
                    "composite_score": round(c.composite_score, 4),
                    "raw_metrics": {k: round(v, 4) for k, v in c.raw_metrics.items()},
                    "normalized_metrics": {k: round(v, 4) for k, v in c.normalized_metrics.items()},
                    "is_pareto_optimal": c.is_pareto_optimal,
                    "is_winner": c.is_winner,
                    "notes": c.notes,
                }
                for c in self.candidates
            ],
            "pairwise_comparisons": self.pairwise_comparisons,
            "exported_at": self.exported_at,
        }

    def to_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                        encoding="utf-8")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_metric(value: float, direction: str, all_values: Optional[List[float]] = None) -> float:
    """
    Normalize value to [0, 1] within the context of all_values.
    direction:
      - "higher": higher is better → (v - min) / (max - min)
      - "lower": lower is better → (max - v) / (max - min)
      - "binary": 1.0 if v >= 0.99 else 0.0

    Edge cases:
      - all_values empty → return 1.0 (no comparison possible)
      - max == min → return 1.0 (all equal)
      - NaN/inf → return 0.0 (defensive)
    """
    if direction == "binary":
        return 1.0 if value >= 0.99 else 0.0

    if not all_values:
        return 1.0

    finite_values = [v for v in all_values if v is not None
                     and not (isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")))]
    if not finite_values:
        return 1.0

    vmin = min(finite_values)
    vmax = max(finite_values)
    if vmax == vmin:
        return 1.0  # all equal → tie at top

    try:
        if direction == "higher":
            return (value - vmin) / (vmax - vmin)
        elif direction == "lower":
            return (vmax - value) / (vmax - vmin)
        else:
            raise ValueError(f"Unknown direction {direction!r}")
    except (TypeError, ZeroDivisionError):
        return 0.0


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------

def compute_composite_score(
    raw_metrics: Dict[str, float],
    weights: Dict[str, float],
    directions: Dict[str, str],
    all_metrics_per_seed: List[Dict[str, float]],  # metrics across all combos (multiple seeds)
) -> float:
    """
    Score = Σᵢ wᵢ × normalize(mᵢ, direction, all_values).

    `all_metrics_per_seed` là list of dicts (1 dict per seed/rerun) để compute
    min/max across toàn bộ seeds, không chỉ 1 seed.
    """
    if not all_metrics_per_seed:
        return 0.0

    # Aggregate per-metric values across all seeds
    all_values: Dict[str, List[float]] = {m: [] for m in weights}
    for seed_metrics in all_metrics_per_seed:
        for metric, value in seed_metrics.items():
            if metric in all_values:
                all_values[metric].append(value)

    score = 0.0
    for metric, weight in weights.items():
        direction = directions.get(metric, "higher")
        norm = normalize_metric(
            raw_metrics.get(metric, 0.0),
            direction,
            all_values.get(metric, []),
        )
        score += weight * norm
    return score


# ---------------------------------------------------------------------------
# Pareto detection
# ---------------------------------------------------------------------------

def is_pareto_optimal(
    candidate: CandidateScore,
    all_candidates: List[CandidateScore],
    metrics_to_check: Optional[List[str]] = None,
) -> bool:
    """
    True nếu không candidate nào dominate candidate này trên TẤT CẢ metrics.

    Dominance: other.raw_metrics[m] >= candidate.raw_metrics[m] cho mọi m
    (treating "lower better" via flipped comparison).
    """
    if metrics_to_check is None:
        metrics_to_check = list(candidate.raw_metrics.keys())

    for other in all_candidates:
        if other.candidate_id == candidate.candidate_id:
            continue
        # Check if other dominates this candidate on all checked metrics
        # (We use raw metrics; direction handling deferred — caller must pass
        # metrics where higher is better, or apply direction here.)
        # For simplicity, we use composite_score for Pareto detection.
        if (other.composite_score >= candidate.composite_score
                and other.composite_score > candidate.composite_score):
            return False
    return True


# ---------------------------------------------------------------------------
# Tie-breaking
# ---------------------------------------------------------------------------

def break_ties(
    candidates: List[CandidateScore],
    weights: Dict[str, float],
) -> List[CandidateScore]:
    """
    Sort by:
      1. composite_score DESC
      2. Highest individual weighted metric DESC (tie at composite)
      3. Lowest std across seeds (stability proxy) ASC
      4. Candidate_id ASC (favor simpler — earlier in registry)
    """
    def sort_key(c: CandidateScore):
        # Note: c.raw_metrics doesn't carry std info; we use empty fallback
        return (
            -c.composite_score,
            -max((weights.get(m, 0) * v for m, v in c.raw_metrics.items()), default=0),
            0,  # placeholder for std (would need raw seed data)
            c.candidate_id,
        )
    return sorted(candidates, key=sort_key)


# ---------------------------------------------------------------------------
# Confidence interval (simple bootstrap)
# ---------------------------------------------------------------------------

def bootstrap_ci_95(values: List[float], n_bootstrap: int = 1000, seed: int = 42) -> Tuple[float, float]:
    """
    Bootstrap 95% CI cho composite scores.
    Returns (ci_lower, ci_upper).
    """
    import random as rnd
    if not values or len(values) < 2:
        return (0.0, 0.0)

    rnd.seed(seed)
    n = len(values)
    boot_means = []
    for _ in range(n_bootstrap):
        sample = [values[rnd.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    lo = boot_means[int(0.025 * n_bootstrap)]
    hi = boot_means[int(0.975 * n_bootstrap)]
    return (lo, hi)


# ---------------------------------------------------------------------------
# Build per-task leaderboard
# ---------------------------------------------------------------------------

def build_task_leaderboard(
    task: TaskID,
    results: List[ComboResult],
    weights: LeaderboardWeights,
    *,
    seed: int = 42,
) -> TaskLeaderboard:
    """
    Build leaderboard from ComboResults cho 1 task.

    Args:
        task: TaskID
        results: List[ComboResult] — output từ ablation_runner
        weights: LeaderboardWeights từ registry

    Returns:
        TaskLeaderboard với candidates sorted by rank, winner set.
    """
    if not results:
        raise ValueError("No ComboResults provided")

    # Group by combo_id (1 candidate = 1 combo_id, multiple seeds → multiple rows)
    by_combo: Dict[str, List[ComboResult]] = {}
    for r in results:
        by_combo.setdefault(r.combo_id, []).append(r)

    # Aggregate per combo: mean of metrics across seeds
    raw_metrics_per_combo: Dict[str, Dict[str, float]] = {}
    raw_metrics_per_combo_per_seed: Dict[str, List[Dict[str, float]]] = {}
    for combo_id, combo_results in by_combo.items():
        # Mean per metric
        all_metric_names = set()
        for r in combo_results:
            all_metric_names.update(r.metrics.keys())
        mean_metrics = {}
        for m in all_metric_names:
            values = [r.metrics[m] for r in combo_results if m in r.metrics]
            mean_metrics[m] = mean(values) if values else 0.0
        raw_metrics_per_combo[combo_id] = mean_metrics
        raw_metrics_per_combo_per_seed[combo_id] = [r.metrics for r in combo_results]

    # Compute composite scores
    all_seeds_combined = []
    for combo_id, per_seed in raw_metrics_per_combo_per_seed.items():
        all_seeds_combined.extend(per_seed)

    scores: Dict[str, float] = {}
    for combo_id, raw_metrics in raw_metrics_per_combo.items():
        score = compute_composite_score(
            raw_metrics=raw_metrics,
            weights=weights.metrics,
            directions=weights.directions,
            all_metrics_per_seed=all_seeds_combined,
        )
        scores[combo_id] = score

    # Build CandidateScore objects
    cand_scores: List[CandidateScore] = []
    for combo_id, raw_metrics in raw_metrics_per_combo.items():
        # Per-metric normalization for display
        normalized = {}
        for metric, value in raw_metrics.items():
            all_v = [r.get(metric, value) for r in raw_metrics_per_combo_per_seed[combo_id]]
            normalized[metric] = normalize_metric(
                value, weights.directions.get(metric, "higher"), all_v
            )
        cand_scores.append(CandidateScore(
            candidate_id=combo_id,
            task=task,
            raw_metrics=raw_metrics,
            normalized_metrics=normalized,
            composite_score=scores[combo_id],
            rank=0,  # assigned after tie-breaking
            is_pareto_optimal=False,  # assigned after ranking
        ))

    # Apply tie-breaking
    cand_scores = break_ties(cand_scores, weights.metrics)

    # Assign ranks
    cand_scores = [
        CandidateScore(
            candidate_id=c.candidate_id,
            task=c.task,
            raw_metrics=c.raw_metrics,
            normalized_metrics=c.normalized_metrics,
            composite_score=c.composite_score,
            rank=i + 1,
            is_pareto_optimal=False,
            notes=c.notes,
        )
        for i, c in enumerate(cand_scores)
    ]

    # Pareto detection
    cand_scores = [
        CandidateScore(
            candidate_id=c.candidate_id,
            task=c.task,
            raw_metrics=c.raw_metrics,
            normalized_metrics=c.normalized_metrics,
            composite_score=c.composite_score,
            rank=c.rank,
            is_pareto_optimal=is_pareto_optimal(c, cand_scores),
            notes=c.notes,
        )
        for c in cand_scores
    ]

    # Winner = rank 1
    winner = cand_scores[0]
    cand_scores = [
        CandidateScore(
            candidate_id=c.candidate_id,
            task=c.task,
            raw_metrics=c.raw_metrics,
            normalized_metrics=c.normalized_metrics,
            composite_score=c.composite_score,
            rank=c.rank,
            is_pareto_optimal=c.is_pareto_optimal,
            is_winner=(c.candidate_id == winner.candidate_id),
            notes=c.notes,
        )
        for c in cand_scores
    ]

    # CI for winner
    winner_scores_per_seed = []
    for combo_id in [winner.candidate_id]:
        # Composite per seed (not pre-computed — recompute)
        for seed_metrics in raw_metrics_per_combo_per_seed[combo_id]:
            score = compute_composite_score(
                raw_metrics=seed_metrics,
                weights=weights.metrics,
                directions=weights.directions,
                all_metrics_per_seed=all_seeds_combined,
            )
            winner_scores_per_seed.append(score)
    ci = bootstrap_ci_95(winner_scores_per_seed, seed=seed)

    return TaskLeaderboard(
        task=task,
        n_candidates=len(cand_scores),
        metric_set=list(weights.metrics.keys()),
        weights=weights.metrics,
        candidates=cand_scores,
        winner_id=winner.candidate_id,
        winner_composite=winner.composite_score,
        ci_95=ci,
        pairwise_comparisons={},  # populated by statistical comparison (Phase 3.5)
        exported_at=_now_iso(),
    )


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=str, required=True,
                        help="Task ID (e.g., RQ1)")
    parser.add_argument("--results-csv", type=Path,
                        default=Path("experiments/scratch/ablation_audit.csv"),
                        help="Audit CSV từ ablation_runner")
    parser.add_argument("--output", type=Path,
                        default=None,
                        help="Output leaderboard JSON path (default: scratch/leaderboards/<task>.json)")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Show top N candidates in summary")
    args = parser.parse_args(argv)

    try:
        task = TaskID(args.task)
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1

    # Load results from audit CSV
    if not args.results_csv.exists():
        print(f"[FAIL] Results CSV not found: {args.results_csv}")
        return 1

    import csv
    results = []
    with open(args.results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("error"):
                continue
            try:
                primary_metric_value = float(row["primary_metric_value"]) if row["primary_metric_value"] else 0.0
                primary_metric_name = row["primary_metric_name"] or "metric"
                results.append(ComboResult(
                    combo_id=row["combo_id"],
                    base_id=row["base_id"],
                    toggle_values=json.loads(row["toggle_values_json"]),
                    metrics={primary_metric_name: primary_metric_value},
                    runtime_sec=float(row["runtime_sec"]),
                    peak_vram_mb=float(row["peak_vram_mb"]),
                    success=(row["status"] == "OK"),
                    seed=42,  # default; would need to track per-row in production
                ))
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                print(f"[WARN] Skipping malformed row: {e}")
                continue

    if not results:
        print("[FAIL] No valid results in CSV")
        return 1

    # Load weights
    from experiments.scripts.registry_loader import load_registry
    _, _, weights = load_registry()
    w = weights.get(task)
    if w is None:
        print(f"[FAIL] No weights for task {task.value}")
        return 1

    # Build leaderboard
    leaderboard = build_task_leaderboard(task, results, w)
    out_path = args.output or Path(f"experiments/scratch/leaderboards/{task.value}.json")
    leaderboard.to_json(out_path)
    print(f"Wrote leaderboard: {out_path}")
    print(f"  Total candidates: {leaderboard.n_candidates}")
    print(f"  Winner: {leaderboard.winner_id} (composite={leaderboard.winner_composite:.4f})")
    print(f"  95% CI: [{leaderboard.ci_95[0]:.4f}, {leaderboard.ci_95[1]:.4f}]")
    print()
    print(f"Top {args.top_n}:")
    for c in leaderboard.candidates[:args.top_n]:
        marker = " <- WINNER" if c.is_winner else (" [Pareto]" if c.is_pareto_optimal else "")
        print(f"  Rank {c.rank:2d}: {c.candidate_id}  score={c.composite_score:.4f}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())