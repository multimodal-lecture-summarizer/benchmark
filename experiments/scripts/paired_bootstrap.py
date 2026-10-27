"""Paired cluster bootstrap and the pre-registered decision rule (shared by detection and tracking).

Units are images or videos; `groups` lets dependent units (LVVO source groups) be resampled together.
The same multiplicity matrix is applied to every compared system, so differences are paired.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np


def cluster_multiplicities(n_units: int, groups: Sequence | None, resamples: int, seed: int) -> np.ndarray:
    """(resamples, n_units) integer matrix: how often each unit appears in each bootstrap sample.

    Whole groups are drawn with replacement; every unit of a drawn group is included.
    With `groups=None` each unit is its own group (plain bootstrap).
    """
    rng = np.random.default_rng(seed)
    if groups is None:
        labels = np.arange(n_units)
    else:
        labels = np.asarray(groups)
        assert len(labels) == n_units
    uniq, inv = np.unique(labels, return_inverse=True)
    k = len(uniq)
    draws = rng.integers(0, k, size=(resamples, k))
    group_counts = np.stack([np.bincount(row, minlength=k) for row in draws])      # (R, k)
    return group_counts[:, inv].astype(np.int64)


def metric_series(metric: Callable[[np.ndarray], float], multiplicities: np.ndarray) -> tuple[float, np.ndarray]:
    """Point estimate and per-resample values of one system, reusable across every pair it appears in."""
    ones = np.ones(multiplicities.shape[1], dtype=np.int64)
    return float(metric(ones)), np.array([metric(m) for m in multiplicities], dtype=float)


def paired_bootstrap(metric_a: Callable[[np.ndarray], float], metric_b: Callable[[np.ndarray], float],
                     multiplicities: np.ndarray, level: float = 0.95) -> dict[str, float]:
    """Bootstrap the paired difference a - b. Metrics take a per-unit multiplicity vector."""
    return paired_from_series(metric_series(metric_a, multiplicities), metric_series(metric_b, multiplicities), level)


def paired_from_series(series_a: tuple[float, np.ndarray], series_b: tuple[float, np.ndarray],
                       level: float = 0.95) -> dict[str, float]:
    """Paired difference a - b from two precomputed series evaluated on the same resamples."""
    (a_hat, a), (b_hat, b) = series_a, series_b
    d = a - b
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    return dict(a=a_hat, b=b_hat, delta=a_hat - b_hat,
                delta_lo=float(np.nanquantile(d, lo_q)), delta_hi=float(np.nanquantile(d, hi_q)),
                a_lo=float(np.nanquantile(a, lo_q)), a_hi=float(np.nanquantile(a, hi_q)),
                b_lo=float(np.nanquantile(b, lo_q)), b_hi=float(np.nanquantile(b, hi_q)),
                resamples=int(len(d)), nan_resamples=int(np.isnan(d).sum()))


def decide_difference(result: dict[str, float], practical_threshold: float) -> str:
    """Pre-registered rule: 'a_better' / 'b_better' needs the paired CI to exclude 0 AND |delta| >= threshold."""
    d, lo, hi = result["delta"], result["delta_lo"], result["delta_hi"]
    if lo > 0 and d >= practical_threshold:
        return "a_better"
    if hi < 0 and -d >= practical_threshold:
        return "b_better"
    return "indistinguishable"
