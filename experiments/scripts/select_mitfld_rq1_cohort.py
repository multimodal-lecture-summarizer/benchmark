"""Lock a 35-video MITFLD qualification cohort without consulting model scores."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path


VERSION = "mitfld-rq1-35-v2"
SEED = "rq1-mitfld-qualification-20260928"
REVISION = "f5a5047e040ecf0f80a3cb67d64e324407f323ec"
SOURCE_SHA256 = "b9fced1fb98d24c21fc0bc0480bcf2f18acfc8dc125e57276203b93e7d9c2a62"
PILOT_IDS = frozenset({
    "-Pg11JHzUTo", "6MssatXXAzc", "EXYw8_pnKr0", "LMSTMBX_2F4",
    "R2vL2wLqGYg", "Z2ScgFh81Dc", "g0bXSXuLVb0", "mhQebe1Y4d0",
    "smHwRzk81b0", "z_xyx-z6arc",
})
SPLIT_COURSES = {"train": 11, "validation": 5, "final_test": 5}
EXTRA_COURSES = {"train": 8, "validation": 3, "final_test": 3}
FIELDS = (
    "cohort_version", "role", "split_proposed", "course_id", "video_id",
    "rank_in_course", "canonical_course_url", "mapping_evidence", "review_flag", "video_title",
)


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def select(
    rows: list[dict[str, str]], *, seed: str = SEED,
    pilot_ids: frozenset[str] = PILOT_IDS,
    split_courses: dict[str, int] = SPLIT_COURSES,
    extra_courses: dict[str, int] = EXTRA_COURSES,
) -> tuple[list[dict[str, str | int]], list[dict[str, str | int]], dict[str, int]]:
    """Choose one video per course plus fixed extras; rank all reserves in-course."""
    ids = [row["video_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("source map has duplicate video_id")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["course_media_type"] != "lecture_video_candidate_course":
            continue
        if "problem session" in row["video_title"].casefold():
            continue
        if row["video_id"] in pilot_ids:
            continue
        course = row["course_group_key"]
        if not course or not row["canonical_course_url"]:
            raise ValueError(f"missing course identity for {row['video_id']}")
        groups[course].append(row)

    if len(groups) != sum(split_courses.values()):
        raise ValueError("course count does not match split quotas")
    course_order = sorted(groups, key=lambda course: (_digest(seed, "course", course), course))
    assigned: dict[str, list[str]] = {}
    offset = 0
    for split, count in split_courses.items():
        assigned[split] = course_order[offset:offset + count]
        offset += count

    selected: list[dict[str, str | int]] = []
    reserves: list[dict[str, str | int]] = []
    for split, courses in assigned.items():
        # More available candidates get the extra slot; course ID resolves ties.
        extra = set(sorted(courses, key=lambda course: (-len(groups[course]), course))[:extra_courses[split]])
        for course in courses:
            ranked = sorted(
                groups[course],
                key=lambda row: (_digest(seed, REVISION, course, row["video_id"]), row["video_id"]),
            )
            take = 2 if course in extra else 1
            if len(ranked) <= take:
                raise ValueError(f"no same-course reserve for {course}")
            urls = {row["canonical_course_url"] for row in ranked}
            if len(urls) != 1:
                raise ValueError(f"inconsistent canonical URL for {course}")
            for rank, row in enumerate(ranked, start=1):
                record: dict[str, str | int] = {
                    "cohort_version": VERSION,
                    "role": "selected" if rank <= take else "reserve",
                    "split_proposed": split,
                    "course_id": course,
                    "video_id": row["video_id"],
                    "rank_in_course": rank,
                    "canonical_course_url": row["canonical_course_url"],
                    "mapping_evidence": row["mapping_evidence"],
                    "review_flag": row.get("review_flag", ""),
                    "video_title": row["video_title"],
                }
                (selected if rank <= take else reserves).append(record)
    counts = {split: sum(row["split_proposed"] == split for row in selected) for split in split_courses}
    if len(selected) != sum(split_courses.values()) + sum(extra_courses.values()):
        raise ValueError("selected size does not match quotas")
    return selected, reserves, counts


def _csv_bytes(rows: list[dict[str, str | int]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_locked_set(artifacts: tuple[tuple[Path, bytes], ...]) -> None:
    """Reject conflicts across the complete artifact set before creating files."""
    for path, content in artifacts:
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"locked artifact differs: {path}")
    for path, content in artifacts:
        if not path.exists():
            path.write_bytes(content)


def main() -> None:
    outer_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=outer_root / "plans/reports/mitfld-260928-1031-normalized-course-map.csv")
    parser.add_argument("--output-dir", type=Path, default=outer_root / "plans/reports")
    args = parser.parse_args()
    source_bytes = args.source.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    if source_hash != SOURCE_SHA256:
        raise ValueError("source map changed; create a versioned selection rule")
    rows = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8-sig"))))
    selected, reserves, split_counts = select(rows)
    if len(rows) != 538 or len(selected) != 35 or len(reserves) != 424:
        raise ValueError("unexpected source or selection denominator")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "mitfld-rq1-35-260928-1120"
    selected_bytes = _csv_bytes(selected)
    reserve_bytes = _csv_bytes(reserves)
    selected_path = args.output_dir / f"{prefix}-selected.csv"
    reserve_path = args.output_dir / f"{prefix}-reserve-order.csv"
    receipt_path = args.output_dir / f"{prefix}-selection-receipt.json"
    receipt = {
        "cohort_version": VERSION, "status": "candidate_only_not_d2",
        "dataset_revision": REVISION, "seed": SEED,
        "source_sha256": source_hash, "excluded_pilot_ids": sorted(PILOT_IDS),
        "filter": "lecture_video_candidate_course; exclude title containing Problem Session; exclude prior 10 pilot IDs",
        "candidate_count_after_filter": 459,
        "split_course_quotas": SPLIT_COURSES, "extra_course_quotas": EXTRA_COURSES,
        "selected_count": len(selected), "reserve_count": len(reserves),
        "selected_split_counts": split_counts,
        "selected_sha256": hashlib.sha256(selected_bytes).hexdigest(),
        "reserve_sha256": hashlib.sha256(reserve_bytes).hexdigest(),
        "replacement_rule": "next reserve rank in same course/split only; retain all failed selected IDs in attrition",
    }
    receipt_bytes = (json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_locked_set(((selected_path, selected_bytes), (reserve_path, reserve_bytes), (receipt_path, receipt_bytes)))
    print(f"selected={len(selected)} reserves={len(reserves)} split_counts={split_counts}")


if __name__ == "__main__":
    main()
