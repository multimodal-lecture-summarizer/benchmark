"""Paired RQ1 uncertainty with the connected course/lecturer group as sampling unit."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from typing import Any


def _quantile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[min(lower + 1, len(sorted_values) - 1)] * fraction


def grouped_paired_bootstrap(
    scores: Mapping[str, Mapping[str, float]], groups: Sequence[Sequence[str]],
    *, candidate: str, baseline: str, seed: int, resamples: int = 10_000,
) -> dict[str, Any]:
    """Resample means of per-video paired deltas within complete groups."""
    if candidate == baseline or not candidate or not baseline or not groups or resamples < 1:
        raise ValueError("candidate/baseline must differ; groups and resamples are required")
    seen: set[str] = set()
    group_means: list[float] = []
    all_deltas: list[float] = []
    for group in groups:
        if not group:
            raise ValueError("empty group")
        deltas: list[float] = []
        for uid in group:
            if uid in seen or uid not in scores:
                raise ValueError("duplicate or missing video in groups")
            seen.add(uid)
            pair = scores[uid]
            if set((candidate, baseline)) - set(pair):
                raise ValueError("missing paired candidate score")
            values = (pair[candidate], pair[baseline])
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
                raise ValueError("invalid paired score")
            deltas.append(values[0] - values[1])
        all_deltas.extend(deltas)
        group_means.append(sum(deltas) / len(deltas))
    if seen != set(scores):
        raise ValueError("groups do not cover exact score cohort")
    rng = random.Random(seed)
    n = len(group_means)
    draws = sorted(sum(group_means[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples))
    return {
        "candidate": candidate, "baseline": baseline, "group_count": n, "video_count": len(all_deltas),
        "group_sizes": [len(group) for group in groups],
        "video_macro_paired_delta": sum(all_deltas) / len(all_deltas),
        "equal_group_mean_delta": sum(group_means) / n,
        "group_means": group_means,
        "ci_95_lower": _quantile(draws, 0.025), "ci_95_upper": _quantile(draws, 0.975),
        "resamples": resamples, "seed": seed, "sampling_unit": "connected_course_or_lecturer_group",
    }
