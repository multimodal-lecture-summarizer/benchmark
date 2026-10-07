"""Unit tests for statistical significance, bootstrap CIs, and Holm-Bonferroni corrections."""

import numpy as np
import pytest
from benchmarks.metrics.statistics import (
    calculate_cohens_d,
    calculate_hedges_g,
    holm_bonferroni_family,
    paired_bootstrap_ci,
)


def test_cohens_d_zero_variance():
    diffs = [0.0, 0.0, 0.0]
    assert calculate_cohens_d(diffs) == 0.0


def test_cohens_d_positive():
    diffs = [1.0, 2.0, 3.0, 4.0, 5.0]
    d = calculate_cohens_d(diffs)
    assert d > 0.0
    assert pytest.approx(d, rel=1e-2) == (3.0 / np.std(diffs, ddof=1))


def test_hedges_g_small_sample():
    d = 1.0
    n = 10
    g = calculate_hedges_g(d, n)
    assert g < d  # Hedges' g reduces overestimate for small sample
    assert calculate_hedges_g(d, 2) == d


def test_paired_bootstrap_ci_coverage():
    diffs = [0.05, 0.08, 0.12, 0.07, 0.10, 0.09, 0.06, 0.11]
    res = paired_bootstrap_ci(diffs, n_resamples=1000, confidence_level=0.95, seed=42)
    assert res.ci_lower < res.mean < res.ci_upper
    assert res.mean == pytest.approx(np.mean(diffs))
    assert res.ci_lower > 0.0  # Entire CI is strictly positive


def test_holm_bonferroni_family_step_down():
    # RQ1 family: 4 deltas
    np.random.seed(42)
    deltas = {
        "C5 - C1": np.random.normal(loc=0.15, scale=0.02, size=30),  # Strong positive
        "C2 - C1": np.random.normal(loc=0.04, scale=0.03, size=30),  # Moderate positive
        "C3 - C1": np.random.normal(loc=0.01, scale=0.05, size=30),  # Weak / null
        "C5 - C6": np.random.normal(loc=0.10, scale=0.02, size=30),  # Strong positive
    }

    results = holm_bonferroni_family(deltas, alpha=0.05)
    assert len(results) == 4

    # Check that corrected p >= raw p
    for label, comp in results.items():
        assert comp.corrected_p_value >= comp.raw_p_value
        assert comp.cohens_d != 0.0
        assert comp.ci_95[0] <= comp.mean_diff <= comp.ci_95[1]

    # Strong deltas should reject null
    assert results["C5 - C1"].reject_null is True
    assert results["C5 - C6"].reject_null is True


# ---------------------------------------------------------------------------
# Pin tests for `direction` parameter — guards against the historical bug
# where `reject_null` hard-coded "mean_diff > 0" and failed for "lower is
# better" metrics (WER, hallucination_rate, WindowDiff, latency).
# ---------------------------------------------------------------------------


def test_direction_higher_with_positive_delta_rejects_null():
    """Higher-is-better metric (e.g., F1, Recall) với tested > baseline → reject."""
    np.random.seed(7)
    deltas = {
        "C5 - C1": np.random.normal(loc=0.20, scale=0.05, size=20),
    }
    res = holm_bonferroni_family(deltas, alpha=0.05, direction="higher")["C5 - C1"]
    assert res.mean_diff > 0.0
    assert res.reject_null is True, (
        "Expected reject_null=True for higher-is-better metric with positive delta"
    )


def test_direction_lower_with_negative_delta_rejects_null():
    """Lower-is-better metric (e.g., WER) với tested < baseline → reject.

    This is the BUG case: pre-fix code returned reject_null=False here because
    mean_diff < 0 didn't satisfy the hardcoded `mean_diff > 0` check.
    """
    np.random.seed(11)
    # WER of A1 (tested) is consistently LOWER than A0 (baseline)
    # so mean_diff = wer_A1 - wer_A0 is NEGATIVE.
    deltas = {
        "A1 - A0 (WER)": np.random.normal(loc=-2.5, scale=0.5, size=20),
    }
    res = holm_bonferroni_family(
        deltas, alpha=0.05, direction="lower"
    )["A1 - A0 (WER)"]
    assert res.mean_diff < 0.0
    assert res.raw_p_value < 0.001, "Synthetic negative delta should be highly significant"
    assert res.reject_null is True, (
        "BUG REGRESSION: lower-is-better metric with negative delta MUST "
        "reject null when significant — otherwise we silently fail to "
        "report that the tested model is better."
    )


def test_direction_higher_with_negative_delta_fails_to_reject():
    """Higher-is-better metric với tested < baseline → fail to reject."""
    np.random.seed(13)
    deltas = {
        "BAD - GOOD": np.random.normal(loc=-0.15, scale=0.04, size=20),
    }
    res = holm_bonferroni_family(
        deltas, alpha=0.05, direction="higher"
    )["BAD - GOOD"]
    assert res.mean_diff < 0.0
    assert res.reject_null is False


def test_direction_lower_with_positive_delta_fails_to_reject():
    """Lower-is-better metric với tested > baseline (worse) → fail to reject."""
    np.random.seed(17)
    deltas = {
        "BAD_WER - GOOD_WER": np.random.normal(loc=+2.0, scale=0.5, size=20),
    }
    res = holm_bonferroni_family(
        deltas, alpha=0.05, direction="lower"
    )["BAD_WER - GOOD_WER"]
    assert res.mean_diff > 0.0
    assert res.reject_null is False


def test_direction_invalid_raises():
    """Unknown direction string must raise ValueError (not silently default)."""
    import pytest as _pytest
    deltas = {"x": [0.1, 0.2, 0.3]}
    with _pytest.raises(ValueError, match="direction must be"):
        holm_bonferroni_family(deltas, direction="sideways")
