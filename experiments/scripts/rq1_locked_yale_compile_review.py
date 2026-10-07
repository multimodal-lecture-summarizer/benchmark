"""Compile source-only Yale qualification decisions with immutable evidence links."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from experiments.scripts.rq1_locked_yale_boundary_diagnostics import source_rows
from experiments.scripts.rq1_locked_yale_media_receipt import DATASETS, sha256_file


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if path.exists():
        raise FileExistsError(path)
    if not rows:
        raise ValueError(f"empty receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--media-receipt", type=Path, required=True)
    parser.add_argument("--boundary-output", type=Path, required=True)
    parser.add_argument("--unit-output", type=Path, required=True)
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not decisions["source_only"] or not decisions["no_timestamp_or_label_edits"]:
        raise ValueError("source-only qualification declaration is required")
    media = json.loads(args.media_receipt.read_text(encoding="utf-8"))
    media_by_path = {item["local_path"]: item for item in media["files"]}
    _, source_pairs = source_rows()
    if set(decisions["decisions"]) != set(source_pairs) or len(source_pairs) != 18:
        raise ValueError("decisions must cover exactly the 18 locked video IDs")

    boundary_rows: list[dict[str, object]] = []
    unit_rows: list[dict[str, object]] = []
    for video_id, review in decisions["decisions"].items():
        diagnostic_path = DATASETS / "boundary_diagnostics" / f"{video_id}-boundary-diagnostic.json"
        storyboard_path = DATASETS / "rights_storyboards" / f"{video_id}-rights-storyboard.json"
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        if diagnostic["video_id"] != video_id or storyboard["video_id"] != video_id:
            raise ValueError(f"evidence ID mismatch: {video_id}")
        media_row = media_by_path.get(diagnostic["media_path"])
        if media_row is None or media_row["sha256"] != diagnostic["media_sha256"] or media_row["sha256"] != storyboard["media_sha256"]:
            raise ValueError(f"media hash mismatch: {video_id}")
        if media_row["full_audio_video_decode"] != "pass":
            raise ValueError(f"full decode missing: {video_id}")
        original = {
            int(pair["original_time_sec"]): pair["original_label"]
            for pair in source_pairs[video_id] if int(pair["original_time_sec"]) > 0
        }
        decided = review["boundary_pass"] + review["boundary_uncertain"] + review["boundary_error"]
        if len(decided) != len(set(decided)) or set(decided) != set(original):
            raise ValueError(f"incomplete or duplicated boundary decisions: {video_id}")
        title_decided = review["title_error"] + review["title_uncertain"]
        if len(title_decided) != len(set(title_decided)) or not set(title_decided).issubset(original):
            raise ValueError(f"title decision outside source pair: {video_id}")
        if review["rights"] not in {"pass_scoped", "hold_component"}:
            raise ValueError(f"unknown rights status: {video_id}")
        for boundary in diagnostic["boundaries"]:
            t = int(boundary["original_time_sec"])
            if boundary["original_label"] != original[t]:
                raise ValueError(f"source label changed: {video_id} at {t}")
            status = (
                "pass" if t in review["boundary_pass"]
                else "uncertain" if t in review["boundary_uncertain"] else "boundary_error"
            )
            title = (
                "title_error" if t in review["title_error"]
                else "uncertain" if t in review["title_uncertain"] else "pass"
            )
            segments = [
                segment for segment in boundary["diagnostic_asr_segments"]
                if segment["start_sec"] <= t + 3 and segment["end_sec"] >= t - 3
            ]
            if not segments:
                segments = sorted(
                    boundary["diagnostic_asr_segments"],
                    key=lambda segment: abs(segment["start_sec"] - t),
                )[:1]
            excerpt = " | ".join(f"{s['start_sec']}-{s['end_sec']}: {s['text']}" for s in segments)
            boundary_rows.append({
                "video_id": video_id,
                "chapter_index": boundary["chapter_index"],
                "original_time_sec": t,
                "original_label": original[t],
                "title_status": title,
                "boundary_status": status,
                "observed_interval_sec": f"{t-3}..{t+3}",
                "evidence_type": "publisher_media_audio_asr_plus_frames",
                "media_audio_excerpt": excerpt,
                "review_reason": review.get("boundary_reason", {}).get(str(t), "Source-media speech or slide transition reviewed within the fixed collar; see excerpt and contact sheet."),
                "media_sha256": media_row["sha256"],
                "diagnostic_json_sha256": sha256_file(diagnostic_path),
                "contact_sheet_sha256": diagnostic["contact_sheet_sha256"],
            })
        eligible = review["rights"] == "pass_scoped" and not review["boundary_uncertain"] and not review["boundary_error"]
        unit_rows.append({
            "video_id": video_id,
            "course_id": media_row["course_id"],
            "lecture_no": media_row["lecture_no"],
            "internal_starts": len(original),
            "full_media_decode": "pass",
            "rights_status": review["rights"],
            "rights_reason": review["rights_reason"],
            "boundary_pass_count": len(review["boundary_pass"]),
            "boundary_uncertain_count": len(review["boundary_uncertain"]),
            "boundary_error_count": len(review["boundary_error"]),
            "title_error_count": len(review["title_error"]),
            "title_uncertain_count": len(review["title_uncertain"]),
            "qualification_status": "pass" if eligible else "hold",
            "media_sha256": media_row["sha256"],
            "rights_storyboard_sha256": storyboard["image_sha256"],
            "source_review_json_sha256": sha256_file(args.decisions),
        })
    if len(boundary_rows) != 91 or len(unit_rows) != 18:
        raise ValueError(f"expected 91 internal starts and 18 units; found {len(boundary_rows)}, {len(unit_rows)}")
    if args.boundary_output.exists() or args.unit_output.exists():
        raise FileExistsError("review output already exists")
    write_csv(args.boundary_output, boundary_rows)
    write_csv(args.unit_output, unit_rows)
    print(f"Reviewed {len(boundary_rows)} starts; {sum(r['qualification_status'] == 'pass' for r in unit_rows)}/18 units pass.")


if __name__ == "__main__":
    main()
