"""Compile locked Yale source-only decisions against exact media and GT evidence."""

from __future__ import annotations

import csv
import argparse
import json
from collections import defaultdict
from pathlib import Path

from experiments.scripts.rq1_locked_yale_media_receipt import sha256_file


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
DEFAULT_PREFIX = "rq1-yale-remaining-260929"
PREFIX = DEFAULT_PREFIX
DIAGNOSTICS = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / "remaining_diagnostics"


def rows(name: str) -> list[dict[str, str]]:
    with (REPORTS / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, content: list[dict[str, object]]) -> None:
    if path.exists() or not content:
        raise ValueError(f"output exists or empty: {path}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(content[0]))
        writer.writeheader()
        writer.writerows(content)


def main() -> None:
    global PREFIX, DIAGNOSTICS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--expected", type=int, default=11)
    parser.add_argument("--diagnostic-subdir", default="remaining_diagnostics")
    args = parser.parse_args()
    PREFIX = args.prefix
    DIAGNOSTICS = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / args.diagnostic_subdir
    decision_path = REPORTS / f"{PREFIX}-review-decisions.json"
    boundary_path = REPORTS / f"{PREFIX}-boundary-review.csv"
    gate_path = REPORTS / f"{PREFIX}-final-gates.csv"
    decisions = json.loads(decision_path.read_text(encoding="utf-8"))
    if not (decisions["source_only"] and decisions["no_timestamp_or_label_edits"] and decisions["no_candidate_prediction_or_metric_consulted"]):
        raise ValueError("source-only review declaration required")
    source = rows(f"{PREFIX}-source-metadata.csv")
    grouped_pairs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for pair in rows(f"{PREFIX}-source-pairs.csv"):
        grouped_pairs[pair["video_id"]].append(pair)
    media = json.loads((REPORTS / f"{PREFIX}-full-media-decode-receipt.json").read_text(encoding="utf-8"))
    decoded = {item["video_id"]: item for item in media["files"]}
    source_valid = {item["video_id"] for item in source if item["source_status"] == "source_gt_present_media_head_pass"}
    if len(source) != args.expected or set(decoded) != source_valid or set(decoded) != set(decisions["decisions"]):
        raise ValueError("locked source/media/decision count mismatch")

    boundary_rows: list[dict[str, object]] = []
    gate_rows: list[dict[str, object]] = []
    for item in source:
        video_id = item["video_id"]
        base = {"video_id": video_id, "course_code": item["course_code"], "lecturer": item["lecturer"], "lecture_url": item["lecture_url"]}
        if item["source_status"] != "source_gt_present_media_head_pass":
            if item["source_status"] != "hold_source_gt_or_identity":
                raise ValueError("unexpected source hold status")
            source_reason = (
                f"Publisher page has {item['label_count']} labels and {item['time_count']} numeric starts "
                f"({item['original_times_s']}); strict increasing source pairing was not established."
            )
            gate_rows.append({**base, "source_status": "hold_source_gt_pairing_or_sequence", "full_media_decode": "not_attempted_source_hold", "internal_starts": "", "rights_status": "not_reviewed_source_hold", "rights_reason": source_reason, "boundary_pass_count": 0, "boundary_uncertain_count": 0, "boundary_error_count": 0, "title_error_count": 0, "title_uncertain_count": 0, "qualification_status": "hold_source", "media_sha256": "", "rights_storyboard_sha256": "", "source_review_json_sha256": sha256_file(decision_path)})
            continue
        review = decisions["decisions"][video_id]
        exact_media = decoded[video_id]
        diagnostic_path = DIAGNOSTICS / f"{video_id}-boundary-diagnostic.json"
        storyboard_path = DIAGNOSTICS / f"{video_id}-rights-storyboard.json"
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        if exact_media["full_audio_video_decode"] != "pass" or exact_media["sha256"] != diagnostic["media_sha256"] or exact_media["sha256"] != storyboard["media_sha256"]:
            raise ValueError(f"full decode or media hash mismatch: {video_id}")
        originals = {int(pair["original_time_sec"]): pair for pair in grouped_pairs[video_id] if int(pair["original_time_sec"]) > 0}
        decisions_at = review["boundary_pass"] + review["boundary_uncertain"] + review["boundary_error"]
        if len(decisions_at) != len(set(decisions_at)) or set(decisions_at) != set(originals):
            raise ValueError(f"incomplete boundary review: {video_id}")
        titles_at = review["title_error"] + review["title_uncertain"]
        if len(titles_at) != len(set(titles_at)) or not set(titles_at) <= set(originals):
            raise ValueError(f"invalid title review: {video_id}")
        if review["rights"] not in {"pass_scoped", "hold_component"}:
            raise ValueError(f"invalid rights status: {video_id}")
        for boundary in diagnostic["boundaries"]:
            second = int(boundary["original_time_sec"])
            original = originals[second]
            if boundary["original_label"] != original["original_label"]:
                raise ValueError(f"source label mismatch: {video_id} {second}")
            speech = [segment for segment in boundary["diagnostic_asr_segments"] if segment["start_sec"] <= second + 3 and segment["end_sec"] >= second - 3]
            excerpt = " | ".join(f"{segment['start_sec']}-{segment['end_sec']}: {segment['text']}" for segment in speech)
            boundary_rows.append({
                **base, "chapter_index": original["chapter_index"], "original_label": original["original_label"], "original_time_sec": second,
                "title_status": "title_error" if second in review["title_error"] else "uncertain" if second in review["title_uncertain"] else "pass",
                "boundary_status": "pass" if second in review["boundary_pass"] else "uncertain" if second in review["boundary_uncertain"] else "boundary_error",
                "review_window_sec": f"{second - 3}..{second + 3}", "source_audio_asr_excerpt": excerpt,
                "review_reason": review.get("boundary_reason", {}).get(str(second), "Distinct source-media spoken topic onset within the fixed ±3 s collar; see diagnostic audio and frames."),
                "media_sha256": exact_media["sha256"], "diagnostic_json_sha256": sha256_file(diagnostic_path),
                "contact_sheet_sha256": diagnostic["contact_sheet_sha256"], "source_pairs_sha256": original["source_pairs_sha256"],
            })
        eligible = review["rights"] == "pass_scoped" and not review["boundary_uncertain"] and not review["boundary_error"]
        gate_rows.append({**base, "source_status": "pass_source_gt_pairing", "full_media_decode": "pass", "internal_starts": len(originals), "rights_status": review["rights"], "rights_reason": review["rights_reason"], "boundary_pass_count": len(review["boundary_pass"]), "boundary_uncertain_count": len(review["boundary_uncertain"]), "boundary_error_count": len(review["boundary_error"]), "title_error_count": len(review["title_error"]), "title_uncertain_count": len(review["title_uncertain"]), "qualification_status": "pass" if eligible else "hold", "media_sha256": exact_media["sha256"], "rights_storyboard_sha256": storyboard["image_sha256"], "source_review_json_sha256": sha256_file(decision_path)})
    expected_boundaries = sum(len(grouped_pairs[video_id]) - 1 for video_id in source_valid)
    if len(boundary_rows) != expected_boundaries or len(gate_rows) != args.expected:
        raise ValueError(f"review count mismatch: {len(boundary_rows)} starts, {len(gate_rows)} units")
    write_rows(boundary_path, boundary_rows)
    write_rows(gate_path, gate_rows)
    print(f"{len(boundary_rows)} internal starts, {sum(row['qualification_status'] == 'pass' for row in gate_rows)}/{args.expected} selected groups pass")


if __name__ == "__main__":
    main()
