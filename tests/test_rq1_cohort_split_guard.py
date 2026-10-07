"""RQ1 split guard rejects identity, overlap, and history leakage."""

from __future__ import annotations

import copy

import pytest

from experiments.scripts.rq1_cohort_split_guard import (
    RQ1CohortSplitError,
    validate_rq1_cohort_split,
)


def _unit(video_id: str, course: str, lecturers: list[str], split: str) -> dict:
    return {
        "video_id": video_id,
        "dataset_ids": ["ytseg"],
        "source_refs": {"ytseg": {"source": f"publisher/{video_id}", "revision": "snapshot-1"}},
        "course_id": course,
        "lecturer_ids": lecturers,
        "split": split,
    }


def _history(video_id: str, *, verified: bool = True) -> dict:
    evidence = "audited_no_project_development_use" if verified else "none_in_current_qualification_records"
    return {
        "video_id": video_id,
        "qualification_observed": "metadata_and_gt_checked",
        "training_or_tuning_evidence": evidence,
        "model_selection_evidence": evidence,
        "historical_use_outside_records": "unverified",
    }


def test_clean_transitive_group_and_cross_dataset_canonical_unit() -> None:
    units = [
        _unit("a", "course-1", ["lecturer-1"], "train"),
        _unit("b", "course-1", ["lecturer-2"], "train"),
        _unit("c", "course-2", ["lecturer-2"], "train"),
        _unit("d", "course-3", ["lecturer-3"], "final_test"),
    ]
    units[3]["dataset_ids"] = ["ytseg", "vidchapters"]
    units[3]["source_refs"]["vidchapters"] = {"source": "vidchapters/d", "revision": "snapshot-2"}
    histories = [_history(unit["video_id"]) for unit in units]
    assert validate_rq1_cohort_split(units, histories) == (("a", "b", "c"), ("d",))


def test_publisher_native_yale_group_can_be_locked_with_its_page_revision() -> None:
    unit = _unit("yale-id", "yale-hist-210", ["paul-freedman"], "final_test")
    unit["dataset_ids"] = ["yale_publisher_native"]
    unit["source_refs"] = {
        "yale_publisher_native": {
            "source": "https://oyc.yale.edu/history/hist-210/lecture-2",
            "revision": "source-pairs-sha256:0123456789abcdef",
        }
    }
    assert validate_rq1_cohort_split([unit], [_history("yale-id")]) == (("yale-id",),)


def test_transitive_lecturer_course_overlap_crosses_splits() -> None:
    units = [
        _unit("a", "course-1", ["lecturer-1"], "train"),
        _unit("b", "course-1", ["lecturer-2"], "train"),
        _unit("c", "course-2", ["lecturer-2"], "validation"),
    ]
    with pytest.raises(RQ1CohortSplitError, match="connected group crosses splits"):
        validate_rq1_cohort_split(units, [_history(row["video_id"]) for row in units])


def test_duplicate_video_across_dataset_rows_is_rejected() -> None:
    units = [_unit("a", "course-1", ["lecturer-1"], "train")]
    duplicate = copy.deepcopy(units[0])
    duplicate["dataset_ids"] = ["vidchapters"]
    duplicate["source_refs"] = {"vidchapters": {"source": "vidchapters/a", "revision": "snapshot-2"}}
    with pytest.raises(RQ1CohortSplitError, match="duplicate across cohort"):
        validate_rq1_cohort_split(units + [duplicate], [_history("a")])


@pytest.mark.parametrize("lecturers", [[], ["unknown"], ["lecturer-1", "lecturer-1"]])
def test_unknown_or_repeated_lecturer_rejected(lecturers: list[str]) -> None:
    with pytest.raises(RQ1CohortSplitError, match="lecturer_ids"):
        validate_rq1_cohort_split(
            [_unit("a", "course-1", lecturers, "train")], [_history("a")]
        )


@pytest.mark.parametrize("field,value", [
    ("training_or_tuning_evidence", "used_for_training"),
    ("model_selection_evidence", "used_for_selection"),
    ("model_selection_evidence", "unverified"),
    ("training_or_tuning_evidence", "none_in_current_qualification_records"),
])
def test_final_test_requires_verified_absence_of_prior_use(field: str, value: str) -> None:
    history = _history("a")
    history[field] = value
    with pytest.raises(RQ1CohortSplitError, match="final_test blocked"):
        validate_rq1_cohort_split([_unit("a", "course-1", ["lecturer-1"], "final_test")], [history])


def test_missing_history_and_source_revision_rejected() -> None:
    unit = _unit("a", "course-1", ["lecturer-1"], "train")
    with pytest.raises(RQ1CohortSplitError, match="history: video IDs differ"):
        validate_rq1_cohort_split([unit], [])
    unit["source_refs"]["ytseg"]["revision"] = "TBD"
    with pytest.raises(RQ1CohortSplitError, match="placeholder identity"):
        validate_rq1_cohort_split([unit], [_history("a")])


def test_unverified_prior_use_allowed_only_outside_final_test() -> None:
    unit = _unit("a", "course-1", ["lecturer-1"], "validation")
    assert validate_rq1_cohort_split([unit], [_history("a", verified=False)]) == (("a",),)
