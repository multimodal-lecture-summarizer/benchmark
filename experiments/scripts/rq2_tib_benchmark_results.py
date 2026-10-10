"""Fixed Unicode word ROUGE-L scorer and paired TIB benchmark summaries."""

import random
import re
import math
from collections import defaultdict

SCORER = "unicode_word_lcs_rouge_l_f1_v1"


def rouge_l(reference, hypothesis):
    """ROUGE-L F1: lowercase Unicode word tokens, no stemming, LCS matching."""
    reference, hypothesis = (re.findall(r"\b\w+\b", text.casefold()) for text in (reference, hypothesis))
    if not reference or not hypothesis:
        return 0.0
    previous = [0] * (len(hypothesis) + 1)
    for word in reference:
        current = [0]
        for j, other in enumerate(hypothesis, 1):
            current.append(previous[j - 1] + 1 if word == other else max(current[-1], previous[j]))
        previous = current
    return 2 * previous[-1] / (len(reference) + len(hypothesis))


def score_pair(arms, reference):
    scores = {arm: rouge_l(reference, arms[arm]["summary"]) for arm in ("S1", "S3")}
    return {**scores, "S3_minus_S1": scores["S3"] - scores["S1"], "scorer": SCORER}


def validate_semantic_scores(scores):
    """Reject invalid scorer output before it can contaminate saved means/CIs."""
    normalized = {}
    for metric in ("bertscore", "sbertscore"):
        try:
            values = {name: float(scores[metric][name]) for name in ("S1", "S3", "S3_minus_S1")}
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError(f"Invalid {metric} result") from exc
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"Nonfinite {metric} result")
        if not math.isclose(values["S3_minus_S1"], values["S3"] - values["S1"], abs_tol=1e-7):
            raise ValueError(f"Unpaired {metric} delta")
        normalized[metric] = values
    return normalized


def _aggregate(rows):
    complete = [row for row in rows if row["status"] == "completed"]
    return {"selected": len(rows), "completed": len(complete), "failed": len(rows) - len(complete),
            **{metric: sum(row["scores"][metric] for row in complete) / len(complete) if complete else None
               for metric in ("S1", "S3", "S3_minus_S1")}}


def summarize_results(rows, *, bootstrap_samples=5000, seed=20261009):
    """Keep failures visible; paired estimates use records completed in both arms."""
    summary = {"overall": _aggregate(rows), "scorer": SCORER, "strata": {}}
    resources = {"known_prompt_tokens": 0, "known_output_tokens": 0,
                 "attempts_with_incomplete_usage": 0, "seconds": 0.0}
    for row in rows:
        for attempt in [*row.get("prior_attempts", []), row]:
            resources["seconds"] += attempt.get("seconds", 0)
            resources["attempts_with_incomplete_usage"] += attempt.get("status") == "in_progress"
            for arm in attempt.get("arms", {}).values():
                if arm.get("reused"):
                    continue
                resources["known_prompt_tokens"] += arm.get("prompt_tokens", 0)
                resources["known_output_tokens"] += arm.get("output_tokens", 0)
                resources["attempts_with_incomplete_usage"] += not arm.get("usage_complete", True)
    overhead = [attempt["shared_preparation_seconds"] for row in rows
                for attempt in [*row.get("prior_attempts", []), row]
                if attempt.get("shared_preparation_seconds") is not None]
    resources["shared_preparation_seconds"] = sum(overhead) if overhead else None
    summary["resources"] = resources
    summary["resources_by_arm"] = _arm_resources(rows)
    for field in ("split", "genre", "subject", "duration_band"):
        groups = defaultdict(list)
        for row in rows:
            minutes = row["duration_minutes"]
            band = ("unknown" if minutes is None else "<15" if minutes < 15 else "15-30" if minutes < 30
                    else "30-60" if minutes < 60 else "60-90" if minutes < 90 else ">=90")
            groups[band if field == "duration_band" else row[field] or "(missing)"].append(row)
        summary["strata"][field] = {key: _aggregate(group) for key, group in sorted(groups.items())}
    deltas = [row["scores"]["S3_minus_S1"] for row in rows if row["status"] == "completed"]
    if bootstrap_samples <= 0:
        raise ValueError("Bootstrap sample count must be positive")
    summary["paired_bootstrap"] = _paired_interval(deltas, bootstrap_samples, seed)
    summary["metrics"] = _metric_summaries(rows, bootstrap_samples, seed)
    return summary


def _arm_resources(rows):
    """Sum actual attempts, including failures, without recounting reused arms.

    Missing historical timing/memory remains unknown; zero is never substituted
    for an unmeasured timing. CUDA peaks are maxima, not additive memory costs.
    """
    resources = {}
    for name in ("S1", "S3"):
        arms = [attempt["arms"][name] for row in rows
                for attempt in [*row.get("prior_attempts", []), row]
                if name in attempt.get("arms", {}) and not attempt["arms"][name].get("reused")]
        receipt = {"attempts": len(arms), "incomplete_attempts": sum(not arm.get("usage_complete", True) for arm in arms),
                   "prompt_tokens": sum(arm.get("prompt_tokens", 0) for arm in arms),
                   "output_tokens": sum(arm.get("output_tokens", 0) for arm in arms),
                   "call_count": sum(arm.get("call_count", len(arm.get("calls", []))) for arm in arms)}
        for field in ("segmentation_seconds", "generation_seconds", "wall_seconds"):
            measured = [arm[field] for arm in arms if arm.get(field) is not None]
            receipt[field] = sum(measured) if measured else None
            receipt[f"{field}_measured_attempts"] = len(measured)
        requests = [arm["generation_request_count"] for arm in arms
                    if arm.get("generation_request_count") is not None]
        receipt["generation_request_count"] = sum(requests) if requests else None
        receipt["generation_request_count_measured_attempts"] = len(requests)
        for field in ("peak_gpu_allocated_bytes", "peak_gpu_reserved_bytes"):
            measured = [arm[field] for arm in arms if arm.get(field) is not None]
            receipt[field] = max(measured) if measured else None
        resources[name] = receipt
    return resources


def _metric_summaries(rows, samples, seed):
    """Every metric uses paired video-level deltas and its own scored denominator."""
    metrics = {}
    for name in ("rouge_l", "bertscore", "sbertscore"):
        metric_rows = []
        for row in rows:
            scores = (row.get("scores") if name == "rouge_l" else row.get("semantic_scores", {}).get(name))
            available = row["status"] == "completed" and scores is not None
            metric_rows.append({**row, "scores": scores, "status": "completed" if available else "failed"})
        scored = [row for row in metric_rows if row["status"] == "completed"]
        complete = len(scored)
        aggregate = _aggregate(metric_rows)
        aggregate.update(selected=len(rows), scored=complete,
                         unscored=len(rows) - complete)
        deltas = [row["scores"]["S3_minus_S1"] for row in scored]
        metrics[name] = {"overall": aggregate,
                         "paired_bootstrap": _paired_interval(deltas, samples, seed), "strata": {}}
        for field in ("split", "genre", "subject", "duration_band"):
            groups = defaultdict(list)
            for row in metric_rows:
                minutes = row["duration_minutes"]
                band = ("unknown" if minutes is None else "<15" if minutes < 15 else "15-30" if minutes < 30
                        else "30-60" if minutes < 60 else "60-90" if minutes < 90 else ">=90")
                groups[band if field == "duration_band" else row[field] or "(missing)"].append(row)
            metrics[name]["strata"][field] = {key: _aggregate(group) for key, group in sorted(groups.items())}
    return metrics


def _paired_interval(deltas, samples, seed):
    if not deltas:
        return {"ci95": None, "samples": samples, "seed": seed, "implementation": "not_computed"}
    try:
        import numpy as np
        rng = np.random.default_rng(seed)
        values = np.asarray(deltas)
        means = np.concatenate([values[rng.integers(0, len(values), size=(min(64, samples-i), len(values)))].mean(axis=1)
                                for i in range(0, samples, 64)])
        interval, implementation = np.quantile(means, [.025, .975]).tolist(), "numpy_generator_percentile_v1"
    except ImportError:
        rng = random.Random(seed)
        means = sorted(sum(rng.choices(deltas, k=len(deltas))) / len(deltas) for _ in range(samples))
        interval = [means[int(.025*(samples-1))], means[int(.975*(samples-1))]]
        implementation = "python_random_percentile_v1"
    return {"ci95": interval, "samples": samples, "seed": seed, "implementation": implementation}
