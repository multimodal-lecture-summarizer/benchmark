"""Focused checks for deterministic, course-disjoint MITFLD selection."""

from __future__ import annotations

import pytest

from experiments.scripts.select_mitfld_rq1_cohort import _write_locked_set, select


def _row(course: str, suffix: int, *, title: str = "Lecture") -> dict[str, str]:
    return {
        "video_id": f"{course}-{suffix}",
        "course_group_key": course,
        "canonical_course_url": f"https://ocw.mit.edu/courses/{course}",
        "mapping_evidence": "youtube_description_course_url",
        "course_media_type": "lecture_video_candidate_course",
        "review_flag": "check_shortlink" if suffix == 1 else "",
        "video_title": title,
    }


def _select(rows: list[dict[str, str]]):
    return select(
        rows, seed="fixture", pilot_ids=frozenset({"A-0"}),
        split_courses={"train": 1, "validation": 1, "final_test": 1},
        extra_courses={"train": 1, "validation": 0, "final_test": 0},
    )


def test_selection_is_order_independent_and_course_disjoint() -> None:
    rows = [_row(course, index) for course in "ABC" for index in range(5)]
    rows.append(_row("A", 8, title="Problem Session 3"))
    audio = _row("A", 9)
    audio["course_media_type"] = "lecture_audio_course"
    rows.append(audio)

    selected, reserves, counts = _select(rows)
    again, again_reserves, again_counts = _select(list(reversed(rows)))

    assert (selected, reserves, counts) == (again, again_reserves, again_counts)
    assert counts == {"train": 2, "validation": 1, "final_test": 1}
    assert len(selected) == 4
    assert len(reserves) == 10
    assert len({row["video_id"] for row in selected + reserves}) == 14
    assert next(row for row in selected + reserves if row["video_id"] == "B-1")["review_flag"] == "check_shortlink"
    assert not {"A-0", "A-8", "A-9"} & {row["video_id"] for row in selected + reserves}
    assert {row["course_id"] for row in selected} == {"A", "B", "C"}
    for course in "ABC":
        assert len({row["split_proposed"] for row in selected + reserves if row["course_id"] == course}) == 1


def test_duplicate_ids_and_inconsistent_course_urls_fail_closed() -> None:
    rows = [_row(course, index) for course in "ABC" for index in range(3)]
    with pytest.raises(ValueError, match="duplicate video_id"):
        _select(rows + [dict(rows[0])])

    changed = [dict(row) for row in rows]
    changed[1]["canonical_course_url"] = "https://ocw.mit.edu/courses/other"
    with pytest.raises(ValueError, match="inconsistent canonical URL"):
        _select(changed)


def test_locked_set_preflights_all_conflicts(tmp_path) -> None:
    first = tmp_path / "selected.csv"
    later = tmp_path / "receipt.json"
    later.write_bytes(b"old")
    with pytest.raises(ValueError, match="locked artifact differs"):
        _write_locked_set(((first, b"selected"), (later, b"new")))
    assert not first.exists()
    assert later.read_bytes() == b"old"
