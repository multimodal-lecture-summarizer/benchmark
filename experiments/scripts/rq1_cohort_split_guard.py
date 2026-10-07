"""Validate a proposed RQ1 split before any final-test access.

Each video has one canonical row, even when both YTSeg and VidChapters list it.
The caller proposes splits; this module never assigns or changes them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DATASETS = frozenset({"ytseg", "vidchapters", "yale_publisher_native"})
SPLITS = frozenset({"train", "validation", "final_test"})
PLACEHOLDERS = frozenset({"", "unknown", "unverified", "none", "null", "n/a", "na", "tbd", "todo", "placeholder"})
HISTORY_FIELDS = (
    "qualification_observed",
    "training_or_tuning_evidence",
    "model_selection_evidence",
    "historical_use_outside_records",
)
FINAL_TEST_CLEARANCE = "audited_no_project_development_use"


class RQ1CohortSplitError(ValueError):
    """Proposed cohort lacks evidence or leaks a connected group across splits."""


def _identity(value: Any, label: str) -> str:
    if not isinstance(value, str) or value.strip().lower() in PLACEHOLDERS:
        raise RQ1CohortSplitError(f"{label}: missing or placeholder identity")
    return value.strip()


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise RQ1CohortSplitError(f"{label}: expected non-empty list")
    items = tuple(_identity(item, label) for item in value)
    if len(set(items)) != len(items):
        raise RQ1CohortSplitError(f"{label}: duplicate identity")
    return items


def validate_rq1_cohort_split(
    units: Sequence[Mapping[str, Any]],
    use_history: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], ...]:
    """Return connected video groups, or raise on incomplete/leaking evidence.

    Unit fields: video_id, dataset_ids, source_refs (dataset -> {source,
    revision}), course_id, lecturer_ids, split. History has one row per video
    with HISTORY_FIELDS. A final-test row requires a scoped audit that this
    project's candidate training, tuning and selection did not use the video.
    Unknown use by unrelated parties is recorded, not treated as proof of
    leakage or as proof of universal non-use.
    """
    if not units:
        raise RQ1CohortSplitError("cohort: no units")
    parent: dict[str, str] = {}
    split_by_id: dict[str, str] = {}
    first_by_identity: dict[tuple[str, str], str] = {}

    def find(video_id: str) -> str:
        while parent[video_id] != video_id:
            parent[video_id] = parent[parent[video_id]]
            video_id = parent[video_id]
        return video_id

    def union(left: str, right: str) -> None:
        parent[find(left)] = find(right)

    for row in units:
        if not isinstance(row, Mapping):
            raise RQ1CohortSplitError("cohort: unit is not a mapping")
        video_id = _identity(row.get("video_id"), "video_id")
        if video_id in parent:
            raise RQ1CohortSplitError(f"video_id {video_id}: duplicate across cohort/datasets")
        datasets = _string_list(row.get("dataset_ids"), f"{video_id}.dataset_ids")
        if not set(datasets).issubset(DATASETS):
            raise RQ1CohortSplitError(f"{video_id}: unsupported dataset_ids")
        source_refs = row.get("source_refs")
        if not isinstance(source_refs, Mapping) or set(source_refs) != set(datasets):
            raise RQ1CohortSplitError(f"{video_id}: source_refs must cover exactly dataset_ids")
        for dataset_id, source_ref in source_refs.items():
            if not isinstance(source_ref, Mapping):
                raise RQ1CohortSplitError(f"{video_id}/{dataset_id}: invalid source_ref")
            _identity(source_ref.get("source"), f"{video_id}/{dataset_id}.source")
            _identity(source_ref.get("revision"), f"{video_id}/{dataset_id}.revision")
        course = _identity(row.get("course_id"), f"{video_id}.course_id")
        lecturers = _string_list(row.get("lecturer_ids"), f"{video_id}.lecturer_ids")
        split = row.get("split")
        if split not in SPLITS:
            raise RQ1CohortSplitError(f"{video_id}: invalid proposed split")
        parent[video_id] = video_id
        split_by_id[video_id] = split
        for identity in (("course", course), *(("lecturer", lecturer) for lecturer in lecturers)):
            previous = first_by_identity.setdefault(identity, video_id)
            union(video_id, previous)

    history_by_id: dict[str, Mapping[str, Any]] = {}
    for row in use_history:
        if not isinstance(row, Mapping):
            raise RQ1CohortSplitError("history: row is not a mapping")
        video_id = _identity(row.get("video_id"), "history.video_id")
        if video_id in history_by_id:
            raise RQ1CohortSplitError(f"history: duplicate video_id {video_id}")
        history_by_id[video_id] = row
    if set(history_by_id) != set(parent):
        raise RQ1CohortSplitError(
            f"history: video IDs differ from cohort; missing={sorted(set(parent) - set(history_by_id))}, "
            f"extra={sorted(set(history_by_id) - set(parent))}"
        )
    for video_id, row in history_by_id.items():
        for field in HISTORY_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RQ1CohortSplitError(f"history[{video_id}].{field}: missing evidence status")
        if split_by_id[video_id] == "final_test":
            for field in HISTORY_FIELDS[1:3]:
                if row[field].strip().lower() != FINAL_TEST_CLEARANCE:
                    raise RQ1CohortSplitError(
                        f"{video_id}: final_test blocked by {field}={row[field]!r}"
                    )

    groups: dict[str, list[str]] = {}
    for video_id in parent:
        groups.setdefault(find(video_id), []).append(video_id)
    for members in groups.values():
        if len({split_by_id[video_id] for video_id in members}) != 1:
            raise RQ1CohortSplitError(f"connected group crosses splits: {sorted(members)}")
    return tuple(sorted(tuple(sorted(members)) for members in groups.values()))
