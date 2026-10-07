"""Lock three existing Yale QA lectures for source-only recruitment review."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


REPORTS = Path(__file__).resolve().parents[2] / "plans" / "reports"
PREFIX = "rq1-yale-qa-extension-260930"
COURSES = ("econ251", "econ25208", "phys201")
LECTURERS = {"econ251": "John Geanakoplos", "econ25208": "Robert J. Shiller", "phys201": "Ramamurti Shankar"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    prior_path = REPORTS / "rq1-yale-260928-1952-nine-course-qa-sample.csv"
    source_path = REPORTS / "rq1-yale-260929-1111-source-gt-snapshot-receipt.json"
    output = REPORTS / f"{PREFIX}-locked.csv"
    receipt = REPORTS / f"{PREFIX}-selection-receipt.json"
    if output.exists() or receipt.exists():
        raise FileExistsError("QA extension already locked")
    with prior_path.open(encoding="utf-8", newline="") as stream:
        prior = {row["course_id"]: row for row in csv.DictReader(stream)}
    source = {row["course_id"]: row for row in json.loads(source_path.read_text(encoding="utf-8"))["files"]}
    selected = []
    for order, course_id in enumerate(COURSES, 1):
        original = prior[course_id]
        snapshot = source[course_id]
        if original["gt_url"] != snapshot["source_url"] or len(snapshot["publisher_chapters"]) < 2:
            raise ValueError(f"source identity mismatch: {course_id}")
        selected.append({"order": order, "course_code": course_id.upper(), "course_id": course_id,
            "lecturer": LECTURERS[course_id], "lecture_url": original["gt_url"],
            "prior_selection_sha256": original["selection_sha256"],
            "prior_publisher_pairs_sha256": snapshot["publisher_chapters_sha256"],
            "status": "locked_existing_qa_before_current_media_review"})
    with output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    receipt.write_text(json.dumps({"schema": "rq1-yale-qa-extension-lock/1", "qualification_only": True,
        "selection_rule": "from original nine-course QA selection, choose unqualified source-snapshot courses ECON251, ECON25208 and PHYS201 in fixed order; first two add previously unqualified lecturers, third is a held-lecturer course; original lecture URL and chapter pairs are unchanged",
        "prior_qa_selection_sha256": digest(prior_path), "source_snapshot_sha256": digest(source_path),
        "locked_csv_sha256": digest(output)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"locked {len(selected)} prior-selected QA lectures")


if __name__ == "__main__":
    main()
