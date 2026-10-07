"""Convert a pinned YTSeg target_ts row into independently checked RQ1 GT.

This adapter belongs in cohort preparation. Its label fields must not be passed
to a chapter predictor as input features.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any


class TargetAdapterError(ValueError):
    """The released target cannot be bound to this video timeline."""


_MARKER = re.compile(r"\[CSTART\] (\d{2,}):([0-5]\d):([0-5]\d) - ([^\r\n]+?) \[CEND\]")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TargetAdapterError(f"{label} must be a finite number")
    return float(value)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def adapt_ytseg_target(
    row: Mapping[str, Any], *, expected_video_id: str,
    verified_media_video_id: str, annotation_row_locator: Mapping[str, Any],
    source: str, revision: str,
    annotation_source_sha256: str, media_sha256: str, media_duration_sec: float,
    media_duration_tolerance_sec: float = 0.0,
) -> dict[str, Any]:
    """Validate published markers and return internal chapter starts with provenance.

    The caller must verify the annotation shard hash/row position and the media
    identity, file hash and timeline before passing these values. This function
    checks their consistency; it cannot prove external files were inspected.

    ``media_duration_tolerance_sec`` is an explicit, recorded audit allowance.
    The default requires exact duration parity. Any timeline disagreement beyond
    that allowance blocks the row; timestamps are never stretched or clamped.
    """
    for label, value in (("source", source), ("revision", revision)):
        if not isinstance(value, str) or not value.strip():
            raise TargetAdapterError(f"{label} must be nonempty")
    row_video_id = row.get("video_id")
    if (not isinstance(expected_video_id, str) or not expected_video_id
            or row_video_id != expected_video_id
            or verified_media_video_id != expected_video_id):
        raise TargetAdapterError("annotation row and verified media video_id mismatch")
    for label, value in (("annotation_source_sha256", annotation_source_sha256),
                         ("media_sha256", media_sha256)):
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise TargetAdapterError(f"{label} must be a SHA-256 digest")
    if (not isinstance(annotation_row_locator, Mapping)
            or annotation_row_locator.get("shard_sha256") != annotation_source_sha256
            or isinstance(annotation_row_locator.get("row_zero_based"), bool)
            or not isinstance(annotation_row_locator.get("row_zero_based"), int)
            or annotation_row_locator["row_zero_based"] < 0):
        raise TargetAdapterError("annotation row locator must bind shard hash and row index")
    try:
        annotation_row_sha256 = _sha256_json(row)
    except (TypeError, ValueError) as exc:
        raise TargetAdapterError("annotation row cannot be canonically hashed") from exc

    duration = _number(row.get("duration"), "annotation duration")
    media_duration = _number(media_duration_sec, "media duration")
    tolerance = _number(media_duration_tolerance_sec, "media duration tolerance")
    if duration <= 0 or media_duration <= 0 or tolerance < 0:
        raise TargetAdapterError("durations must be positive and tolerance nonnegative")
    if abs(duration - media_duration) > tolerance:
        raise TargetAdapterError("annotation and media duration disagree")

    target = row.get("target_ts")
    raw = row.get("raw_chapters")
    if not isinstance(target, str) or not target or not isinstance(raw, list) or not raw:
        raise TargetAdapterError("target_ts and nonempty raw_chapters are required")
    lines = target.split("\n")
    if any(not line for line in lines) or len(lines) != len(raw):
        raise TargetAdapterError("target_ts marker count differs from raw_chapters")

    boundaries: list[float] = []
    previous_end = 0.0
    for index, (line, chapter) in enumerate(zip(lines, raw)):
        match = _MARKER.fullmatch(line)
        if match is None:
            raise TargetAdapterError(f"target_ts marker {index} has invalid syntax")
        hours, minutes, seconds = (int(part) for part in match.group(1, 2, 3))
        marker_start = float(hours * 3600 + minutes * 60 + seconds)
        title = match.group(4)
        if not title.strip() or not isinstance(chapter, Mapping):
            raise TargetAdapterError(f"raw chapter {index} is malformed")
        start = _number(chapter.get("start_time"), f"raw chapter {index} start")
        end = _number(chapter.get("end_time"), f"raw chapter {index} end")
        if chapter.get("title") != title or start != marker_start:
            raise TargetAdapterError(f"marker {index} differs from raw chapter title/start")
        if start != previous_end or end <= start or end > duration:
            raise TargetAdapterError(f"raw chapter {index} breaks timeline continuity")
        if index and not 0 < start < duration:
            raise TargetAdapterError(f"marker {index} is outside internal timeline")
        if index:
            boundaries.append(start)
        previous_end = end
    if previous_end != duration:
        raise TargetAdapterError("raw chapter end differs from annotation duration")

    return {
        "video_id": expected_video_id,
        "duration_sec": duration,
        "chapter_boundaries_sec": boundaries,
        "chapter_gt": {
            "source": source,
            "revision": revision,
            "annotation_origin": "creator_chapters",
            "timestamp_convention": "target_ts chapter starts in seconds from media start; exclude 0 and duration",
            "annotation_source_sha256": annotation_source_sha256,
            "annotation_row_locator": dict(annotation_row_locator),
            "annotation_row_sha256": annotation_row_sha256,
            "video_id": expected_video_id,
            "media_sha256": media_sha256,
            "target_ts_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
            "raw_chapters_sha256": _sha256_json(raw),
            "annotation_duration_sec": duration,
            "media_duration_sec": media_duration,
            "media_duration_tolerance_sec": tolerance,
            "marker_count": len(lines),
        },
    }
