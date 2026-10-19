"""Prediction-independent event scoring primitives; never generate or repair GT."""

import math
import re
from collections import defaultdict
from numbers import Real


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite real number")
    return float(value)


def _times(values, name, duration=None):
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{name} must be an array")
    result = [_number(value, name) for value in values]
    if any(t < 0 or (duration is not None and t >= duration) for t in result):
        raise ValueError(f"{name} must be inside [0, duration)")
    return result


def match_events(reference, predicted, collar=0.5):
    """Maximize pairs, then minimize absolute error, then original-index pairs.

    Sorted noncrossing dynamic programming is sufficient for 1-D absolute
    distance and a common collar. Inputs and original indices remain unchanged.
    Duplicate times are separate events; GT deduplication belongs to review.
    """
    collar = _number(collar, "collar")
    if collar < 0:
        raise ValueError("collar must be nonnegative")
    refs = sorted(enumerate(_times(reference, "reference")), key=lambda x: (x[1], x[0]))
    preds = sorted(enumerate(_times(predicted, "predicted")), key=lambda x: (x[1], x[0]))
    # State: (number of matches, summed error, ordered original-index pairs).
    empty = (0, 0.0, ())
    previous = [empty] * (len(preds) + 1)
    rank = lambda state: (-state[0], state[1], state[2])
    for ri, rt in refs:
        current = [empty]
        for j, (pi, pt) in enumerate(preds, 1):
            choices = [previous[j], current[j - 1]]
            error = abs(rt - pt)
            if error <= collar:
                count, total, pairs = previous[j - 1]
                choices.append((count + 1, total + error, pairs + ((ri, pi),)))
            current.append(min(choices, key=rank))
        previous = current
    return [{"reference_index": ri, "prediction_index": pi,
             "absolute_error_sec": abs(reference[ri] - predicted[pi])}
            for ri, pi in previous[-1][2]]


def _metrics(tp, fp, fn):
    # Undefined denominators stay null; a known empty source does not earn F1=1.
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}


def score_videos(ground_truth, predictions, sources, *, label_track="reviewed",
                 collar=0.5, formal=False, qualification=None):
    """Diagnostic scores for explicit full-source scopes; formal use is gated.

    sources maps IDs to duration_sec, group, eligible, fully_annotated_scope,
    hold_intervals and ignored_event_count. Missing prediction keys mean []
    with a missing-output ledger entry (formal aggregation refuses them).
    Missing GT keys never mean a negative source. Any hold blocks the source.
    Qualification is a caller assertion, not certification by this function.
    """
    if label_track not in ("raw_released", "reviewed"):
        raise ValueError("one explicit label track required")
    collar = _number(collar, "collar")
    if collar not in (0.5, 1.0, 2.0):
        raise ValueError("use a predeclared collar: 0.5, 1, or 2 seconds")
    if any(key not in sources for key in set(ground_truth) | set(predictions)):
        raise ValueError("unknown video ID")
    qualification = qualification or {}
    if formal and not (qualification.get("gt_status") == "frozen"
                       and qualification.get("cohort_status") == "frozen"
                       and isinstance(qualification.get("manifest_sha256"), str)
                       and re.fullmatch(r"[0-9a-f]{64}", qualification["manifest_sha256"])
                       and qualification.get("label_track") == label_track):
        raise ValueError("formal aggregate blocked: GT/cohort/track/hash pending")
    if formal and not sources:
        raise ValueError("formal aggregate requires a nonempty manifest")
    rows, blocked, ignored, missing_outputs = {}, {}, 0, []
    for video, source in sorted(sources.items()):
        duration = _number(source["duration_sec"], "duration")
        if duration <= 0 or not isinstance(source.get("group"), str) or not source["group"]:
            raise ValueError("positive duration and nonempty source group required")
        count = source.get("ignored_event_count", 0)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("ignored_event_count must be a nonnegative integer")
        ignored += count
        reasons = []
        if source.get("eligible") is not True:
            reasons.append("ineligible")
        if source.get("fully_annotated_scope") is not True:
            reasons.append("annotation_scope_pending")
        if source.get("hold_intervals"):
            reasons.append("unresolved_hold")
        if video not in ground_truth:
            reasons.append("unlabeled")
        # Even blocked arrays must be well formed; overshoots require review.
        refs = _times(ground_truth.get(video, []), "reference", duration)
        preds = _times(predictions.get(video, []), "predicted", duration)
        if reasons:
            blocked[video] = {"reasons": reasons, "reference_count": len(refs),
                              "prediction_count": len(preds), "ignored_event_count": count}
            continue
        if video not in predictions:
            missing_outputs.append(video)
        pairs = match_events(refs, preds, collar)
        rows[video] = {**_metrics(len(pairs), len(preds) - len(pairs), len(refs) - len(pairs)),
                       "group": source["group"], "matches": pairs,
                       "ignored_event_count": count,
                       "prediction_status": "provided" if video in predictions else "missing_output"}
    if formal and (blocked or missing_outputs):
        raise ValueError("formal aggregate blocked: unresolved/ineligible source or missing output")
    grouped = defaultdict(list)
    for row in rows.values():
        grouped[row["group"]].append(row)
    aggregate = lambda items: _metrics(*(sum(r[key] for r in items) for key in ("tp", "fp", "fn")))
    groups = {group: aggregate(items) for group, items in sorted(grouped.items())}
    macro = {}
    for key in ("precision", "recall", "f1"):
        values = [group[key] for group in groups.values() if group[key] is not None]
        macro[key] = sum(values) / len(values) if values else None
        macro[key + "_defined_groups"] = len(values)
    return {"status": "formal" if formal else "diagnostic_only", "label_track": label_track,
            "collar_sec": collar, "per_video": rows, "per_group": groups,
            "pooled": aggregate(list(rows.values())), "macro_group": macro,
            "scored_video_count": len(rows), "blocked_video_count": len(blocked),
            "blocked": blocked, "ignored_event_count": ignored,
            "missing_prediction_videos": missing_outputs}
