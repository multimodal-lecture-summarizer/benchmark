"""Pretest RQ1 precision calculation from locked validation-only primary scores."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


CONTRASTS = (("C2", "C1"), ("C3", "C1"), ("C4", "C1"), ("C5", "C6"))
ALL_CANDIDATES = frozenset({candidate for pair in CONTRASTS for candidate in pair})


def plan_validation_precision(split: list[dict], scores: list[dict]) -> dict:
    """Reject any non-validation score before computing group-level paired SDs."""
    split_by_id = {row["video_id"]: row for row in split}
    if len(split_by_id) != len(split):
        raise ValueError("duplicate split video ID")
    validation = {uid: row for uid, row in split_by_id.items() if row["split"] == "validation"}
    if len(validation) != 4:
        raise ValueError("locked design requires four validation videos")
    if len({row["course_id"] for row in validation.values()}) != 4:
        raise ValueError("validation courses are not independent")
    lecturers = [lecturer for row in validation.values() for lecturer in row["lecturer_ids"]]
    if len(set(lecturers)) != len(lecturers):
        raise ValueError("validation lecturers overlap")
    seen: dict[str, dict[str, float]] = {uid: {} for uid in validation}
    for record in scores:
        uid = record.get("unit_id")
        if uid not in validation:
            raise ValueError("score receipt contains an ID outside locked validation")
        candidate = record.get("candidate")
        if candidate not in ALL_CANDIDATES or candidate in seen[uid]:
            raise ValueError("score receipt has unknown or duplicate candidate")
        value = record.get("metrics", {}).get("collar_f1_3s")
        if (record.get("status") not in {"run", "candidate_unit_failure"}
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError("score receipt lacks a valid primary F1")
        if record["status"] == "candidate_unit_failure" and value != 0:
            raise ValueError("failed candidate unit must have primary F1 zero")
        seen[uid][candidate] = float(value)
    if any(set(candidate_scores) != ALL_CANDIDATES for candidate_scores in seen.values()):
        raise ValueError("incomplete paired validation candidate scores")
    ordered_ids = sorted(validation)
    contrasts: dict[str, dict] = {}
    for candidate, baseline in CONTRASTS:
        deltas = [seen[uid][candidate] - seen[uid][baseline] for uid in ordered_ids]
        contrasts[f"{candidate}-{baseline}"] = {
            "validation_group_deltas": dict(zip(ordered_ids, deltas)),
            "sample_sd": statistics.stdev(deltas),
        }
    maximum = max(value["sample_sd"] for value in contrasts.values())
    required = max(8, math.ceil((1.96 * maximum / 0.20) ** 2))
    return {"status": "planning_threshold_pass" if required <= 8 else "blocked_precision_floor",
            "validation_group_count": 4, "locked_final_test_group_count": 8,
            "contrasts": contrasts, "max_sample_sd": maximum,
            "required_final_test_groups": required,
            "eight_group_max_sample_sd": 0.20 * math.sqrt(8) / 1.96,
            "planning_only": "Final grouped-bootstrap CI width is unknown until the sealed test is scored."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--validation-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    split_bytes = args.split.read_bytes()
    score_bytes = args.validation_scores.read_bytes()
    result = plan_validation_precision(json.loads(split_bytes), json.loads(score_bytes))
    result["split_sha256"] = hashlib.sha256(split_bytes).hexdigest()
    result["validation_score_receipt_sha256"] = hashlib.sha256(score_bytes).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "required_final_test_groups": result["required_final_test_groups"]}))


if __name__ == "__main__":
    main()
