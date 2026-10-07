"""Bind two preselected Yale QA decisions to their untouched GT and exact MOV diagnostics."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.scripts.rq1_locked_yale_media_receipt import sha256_file


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
DIAGNOSTICS = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / "qa_existing_diagnostics"
PREFIX = "rq1-yale-qa-existing-260930"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists() or not rows:
        raise ValueError(f"output exists or empty: {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    bridge = json.loads((REPORTS / "rq1-yale-qa-existing-260929-source-bridge.json").read_text(encoding="utf-8"))
    decision_path = REPORTS / f"{PREFIX}-review-decisions.json"
    decisions = json.loads(decision_path.read_text(encoding="utf-8"))
    if not all(decisions[key] for key in ("source_only", "no_timestamp_or_label_edits", "no_candidate_prediction_or_metric_consulted")):
        raise ValueError("source-only declaration missing")
    if len(bridge["files"]) != 2 or set(decisions["decisions"]) != {item["video_id"] for item in bridge["files"]}:
        raise ValueError("preselected source set mismatch")
    boundaries: list[dict[str, object]] = []
    gates: list[dict[str, object]] = []
    for item in bridge["files"]:
        video_id = item["video_id"]
        review = decisions["decisions"][video_id]
        media = Path(item["local_media_path"])
        diagnostic_path = DIAGNOSTICS / f"{video_id}-boundary-diagnostic.json"
        storyboard_path = DIAGNOSTICS / f"{video_id}-rights-storyboard.json"
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        media_sha = item["local_media_sha256"]
        if item["previous_full_decode_exit_code"] != 0 or sha256_file(media) != media_sha:
            raise ValueError(f"exact media or full decode mismatch: {video_id}")
        if diagnostic["media_sha256"] != media_sha or storyboard["media_sha256"] != media_sha:
            raise ValueError(f"diagnostic media mismatch: {video_id}")
        originals = {int(pair["original_time_sec"]): pair for pair in item["pairs"] if pair["original_time_sec"] > 0}
        reviewed = review["boundary_pass"] + review["boundary_uncertain"] + review["boundary_error"]
        if len(reviewed) != len(set(reviewed)) or set(reviewed) != set(originals):
            raise ValueError(f"boundary coverage mismatch: {video_id}")
        titles = review["title_uncertain"] + review["title_error"]
        if len(titles) != len(set(titles)) or not set(titles) <= set(originals):
            raise ValueError(f"title coverage mismatch: {video_id}")
        if len(diagnostic["boundaries"]) != len(originals):
            raise ValueError(f"diagnostic coverage mismatch: {video_id}")
        base = {"video_id": video_id, "course_id": item["course_id"], "lecturer": item["lecturer"], "publisher_page": item["publisher_page"]}
        for boundary in diagnostic["boundaries"]:
            second = int(boundary["original_time_sec"])
            pair = originals[second]
            if pair["original_label"] != boundary["original_label"] or pair["chapter_index"] != boundary["chapter_index"]:
                raise ValueError(f"GT mismatch: {video_id} {second}")
            boundaries.append({**base, "chapter_index": pair["chapter_index"], "original_label": pair["original_label"], "original_time_sec": second,
                "title_status": "title_error" if second in review["title_error"] else "uncertain" if second in review["title_uncertain"] else "pass",
                "boundary_status": "pass" if second in review["boundary_pass"] else "uncertain" if second in review["boundary_uncertain"] else "boundary_error",
                "review_window_sec": f"{second - 3}..{second + 3}", "source_only_reason": review["boundary_reason"][str(second)],
                "media_sha256": media_sha, "diagnostic_json_sha256": sha256_file(diagnostic_path),
                "contact_sheet_sha256": diagnostic["contact_sheet_sha256"]})
        eligible = review["rights"] == "pass_scoped" and not review["boundary_uncertain"] and not review["boundary_error"]
        gates.append({**base, "source_gt_pairing": "pass", "full_audio_video_decode": "pass_prior_receipt", "internal_starts": len(originals),
            "boundary_pass_count": len(review["boundary_pass"]), "boundary_uncertain_count": len(review["boundary_uncertain"]),
            "boundary_error_count": len(review["boundary_error"]), "title_uncertain_count": len(review["title_uncertain"]),
            "rights_status": review["rights"], "rights_reason": review["rights_reason"],
            "qualification_status": "pass" if eligible else "hold_boundary", "final_test_role": "unassigned_pending_use_history",
            "media_sha256": media_sha, "storyboard_sha256": storyboard["image_sha256"], "decision_sha256": sha256_file(decision_path)})
    if len(boundaries) != 10 or len(gates) != 2:
        raise ValueError("unexpected QA sample size")
    write_csv(REPORTS / f"{PREFIX}-boundary-review.csv", boundaries)
    write_csv(REPORTS / f"{PREFIX}-final-gates.csv", gates)
    print(f"{len(boundaries)} internal starts, {sum(row['qualification_status'] == 'pass' for row in gates)}/2 QA groups pass")


if __name__ == "__main__":
    main()
