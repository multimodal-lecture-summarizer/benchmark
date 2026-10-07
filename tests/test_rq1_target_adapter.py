"""Published YTSeg target_ts is the sole RQ1 label source."""

from __future__ import annotations

import hashlib

import pytest

from experiments.scripts.chapter_benchmark_contract import validate_chapter_ground_truth
from experiments.scripts.rq1_target_adapter import TargetAdapterError, adapt_ytseg_target


HASH = hashlib.sha256(b"fixture").hexdigest()


def _row():
    return {
        "video_id": "video-1",
        "duration": 100.0,
        "target_ts": "[CSTART] 00:00:00 - Intro [CEND]\n[CSTART] 00:00:40 - Topic - A [CEND]",
        "raw_chapters": [
            {"start_time": 0.0, "end_time": 40.0, "title": "Intro"},
            {"start_time": 40.0, "end_time": 100.0, "title": "Topic - A"},
        ],
    }


def _adapt(row, **overrides):
    kwargs = {"expected_video_id": "video-1", "verified_media_video_id": "video-1",
              "annotation_row_locator": {"shard_sha256": HASH, "row_zero_based": 7},
              "source": "retkowski/ytseg:text", "revision": "pinned-r1",
              "annotation_source_sha256": HASH, "media_sha256": HASH,
              "media_duration_sec": 100.0}
    kwargs.update(overrides)
    return adapt_ytseg_target(row, **kwargs)


def test_adapter_emits_only_internal_starts_and_bound_provenance():
    result = _adapt(_row())
    assert result["chapter_boundaries_sec"] == [40.0]
    assert result["video_id"] == "video-1"
    assert result["chapter_gt"]["annotation_origin"] == "creator_chapters"
    assert result["chapter_gt"]["annotation_row_locator"]["row_zero_based"] == 7
    assert len(result["chapter_gt"]["annotation_row_sha256"]) == 64
    assert result["chapter_gt"]["target_ts_sha256"] == hashlib.sha256(
        _row()["target_ts"].encode("utf-8")
    ).hexdigest()
    assert validate_chapter_ground_truth({"dataset_id": "ytseg", "unit_id": "v1", **result}) == [40.0]
    assert "title" not in result and "target_ts" not in result


@pytest.mark.parametrize("mutate, error", [
    (lambda r: r.update(target_ts=r["target_ts"] + "\n"), "marker count"),
    (lambda r: r.update(target_ts=r["target_ts"].replace("Topic - A", "Topic - B")), "differs"),
    (lambda r: r.update(target_ts=r["target_ts"].replace("00:00:40", "00:00:41")), "differs"),
    (lambda r: r.update(target_ts=r["target_ts"].replace("[CEND]", "[END]", 1)), "syntax"),
    (lambda r: r["raw_chapters"][1].update(start_time=41.0), "differs"),
    (lambda r: r["raw_chapters"][0].update(end_time=39.0), "continuity"),
    (lambda r: r["raw_chapters"][1].update(end_time=99.0), "duration"),
    (lambda r: r.update(duration=39.0), "duration disagree"),
])
def test_adapter_rejects_marker_or_timeline_corruption(mutate, error):
    row = _row()
    mutate(row)
    with pytest.raises(TargetAdapterError, match=error):
        _adapt(row)


def test_single_chapter_and_media_duration_audit():
    row = _row()
    row["target_ts"] = "[CSTART] 00:00:00 - Intro [CEND]"
    row["raw_chapters"] = [{"start_time": 0.0, "end_time": 100.0, "title": "Intro"}]
    assert _adapt(row)["chapter_boundaries_sec"] == []
    with pytest.raises(TargetAdapterError, match="duration disagree"):
        _adapt(row, media_duration_sec=100.2)
    accepted = _adapt(row, media_duration_sec=100.2, media_duration_tolerance_sec=0.25)
    assert accepted["chapter_gt"]["media_duration_tolerance_sec"] == 0.25


def test_rejects_cross_video_and_unbound_row_locator():
    row = _row()
    with pytest.raises(TargetAdapterError, match="video_id mismatch"):
        _adapt({**row, "video_id": "other-video"})
    with pytest.raises(TargetAdapterError, match="video_id mismatch"):
        _adapt(row, verified_media_video_id="other-video")
    with pytest.raises(TargetAdapterError, match="row locator"):
        _adapt(row, annotation_row_locator={"shard_sha256": "b" * 64, "row_zero_based": 7})
