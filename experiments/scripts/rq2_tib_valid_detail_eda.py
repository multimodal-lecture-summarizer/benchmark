"""Characterize only the declared creator-TIB validation records for RQ2 EDA."""

from __future__ import annotations

import re
import math

from datasets import load_dataset

DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
ALL_SPLITS = ("train", "valid", "test")


def _tokens(value: object) -> list[str]:
    return re.findall(r"\b\w+\b", str(value or "").casefold())


def _preview(value: object, limit: int = 180) -> str:
    return " ".join(str(value or "").split())[:limit]


def scan_selected_details(selected: list[dict]) -> list[dict]:
    """Read the pinned `valid` split; retain metadata and short source examples only."""
    wanted = {row["doi"] for row in selected}
    found: dict[str, dict] = {}
    rows = load_dataset(DATASET, split="valid", revision=REVISION, streaming=True)
    for record in rows:
        doi = str(record.get("doi") or "").strip()
        if doi not in wanted:
            continue
        segments = record.get("transcript_segments") or {}
        texts = list(segments.get("text") or [])
        starts = [float(value) for value in segments.get("start") or []]
        ends = [float(value) for value in segments.get("end") or []]
        if not texts or not (len(texts) == len(starts) == len(ends)):
            raise ValueError(f"Misaligned transcript segments for {doi}")
        keyframes = record.get("keyframes") or {}
        slides = list(keyframes.get("slide") or [])
        frames = list(keyframes.get("frames") or [])
        ranges = list(keyframes.get("timestamp") or [])
        keyframe_arrays_aligned = len(slides) == len(frames) == len(ranges)
        keyframe_intervals_ordered = keyframe_arrays_aligned and all(
            len(pair) == 2 and 0 <= float(pair[0]) <= float(pair[1])
            for pair in ranges
        ) and all(float(ranges[index][0]) >= float(ranges[index - 1][0])
                  for index in range(1, len(ranges)))
        duration = max(ends)
        abstract = str(record.get("abstract") or "")
        segment_tokens = _tokens(" ".join(texts))
        source_tokens = _tokens(record.get("transcript"))
        license_text = str(record.get("license") or "")
        found[doi] = {
            "doi": doi,
            "title": str(record.get("title") or "").strip(),
            "subject": str(record.get("subject") or "").strip(),
            "language": str(record.get("language") or "").strip(),
            "release_year": str(record.get("release_year") or "").strip(),
            "source_url": str(record.get("url") or "").strip(),
            "video_url_present": bool(record.get("video_url")),
            "license_label": license_text.splitlines()[0].strip() if license_text else "",
            "transcript_words": len(str(record.get("transcript") or "").split()),
            "segment_text_words": sum(len(str(text or "").split()) for text in texts),
            "whitespace_word_count_matches": len(str(record.get("transcript") or "").split()) == sum(
                len(str(text or "").split()) for text in texts
            ),
            "segment_count": len(texts),
            "duration_minutes": round(duration / 60, 2),
            "words_per_minute": round(len(source_tokens) / (duration / 60), 1) if duration else None,
            "transcript_matches_segments": source_tokens == segment_tokens,
            "zero_duration_segments": sum(start == end for start, end in zip(starts, ends)),
            "gaps_over_30_sec": sum(starts[index] - ends[index - 1] > 30
                                    for index in range(1, len(starts))),
            "abstract_words": len(abstract.split()),
            "abstract_chars": len(abstract),
            "abstract_text": abstract,
            "abstract_preview": _preview(abstract),
            "transcript_example": _preview(texts[len(texts) // 2]),
            "keyframe_count": len(ranges),
            "first_keyframe_filename": str(slides[0]) if slides else "",
            "first_keyframe_seconds": [round(float(value), 2) for value in ranges[0]] if ranges else [],
            "keyframe_arrays_aligned": keyframe_arrays_aligned,
            "keyframe_intervals_ordered": keyframe_intervals_ordered,
            "keyframe_last_minus_transcript_end_sec": round(float(ranges[-1][1]) - duration, 2)
            if ranges else None,
            "keyframe_pixels_read": False,
            "audio_sample_read": False,
        }
    missing = wanted - found.keys()
    if missing:
        raise RuntimeError(f"Selected validation DOI missing: {sorted(missing)}")
    return [found[row["doi"]] for row in selected]


def _scan_usable_details_for_split(usable: list[dict], split: str) -> list[dict]:
    """Characterize all eligible validation source indices; log item failures.

    DOI is carried for traceability but never used as the unique lookup key.
    Text/abstract properties are descriptive, not ground-truth judgments.
    """
    wanted = {row["source_index"]: row for row in usable}
    if len(wanted) != len(usable):
        raise ValueError("Duplicate source_index in usable cohort")
    found: dict[int, dict] = {}
    rows = load_dataset(DATASET, split=split, revision=REVISION, streaming=True)
    for source_index, record in enumerate(rows):
        if source_index not in wanted:
            continue
        doi = str(record.get("doi") or "").strip()
        expected_doi = wanted[source_index]["doi"]
        try:
            if doi != expected_doi:
                raise ValueError(f"DOI changed from {expected_doi!r} to {doi!r}")
            segments = record.get("transcript_segments") or {}
            if not isinstance(segments, dict):
                raise ValueError("transcript_segments is not a mapping")
            texts = list(segments.get("text") or [])
            starts = list(segments.get("start") or [])
            ends = list(segments.get("end") or [])
            if len(texts) < 2 or len(texts) != len(starts) or len(texts) != len(ends):
                raise ValueError("transcript segment arrays are missing or misaligned")
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) for value in starts + ends):
                raise ValueError("transcript segment times are not finite numbers")
            if any(start < 0 or end < start for start, end in zip(starts, ends)):
                raise ValueError("transcript segment time range is invalid")
            if any(starts[index] < starts[index - 1] for index in range(1, len(starts))):
                raise ValueError("transcript segments are unordered")
            keyframes = record.get("keyframes") or {}
            if not isinstance(keyframes, dict):
                raise ValueError("keyframes is not a mapping")
            slides = list(keyframes.get("slide") or [])
            frames = list(keyframes.get("frames") or [])
            ranges = list(keyframes.get("timestamp") or [])
            keyframe_arrays_aligned = len(slides) == len(frames) == len(ranges)
            valid_ranges = []
            for pair in ranges:
                valid_ranges.append(
                    isinstance(pair, (list, tuple)) and len(pair) == 2
                    and all(isinstance(value, (int, float)) and not isinstance(value, bool)
                            and math.isfinite(value) for value in pair)
                    and 0 <= pair[0] <= pair[1]
                )
            ordered_keyframes = (keyframe_arrays_aligned and all(valid_ranges)
                                 and all(ranges[index][0] >= ranges[index - 1][0]
                                         for index in range(1, len(ranges))))
            transcript = str(record.get("transcript") or "")
            abstract = str(record.get("abstract") or "")
            license_text = str(record.get("license") or "")
            segment_text = " ".join(str(text or "") for text in texts)
            duration = max(ends)
            found[source_index] = {
                "source_index": source_index,
                "doi": doi,
                "status": "ok",
                "genre": str(record.get("genre") or "").strip(),
                "language": str(record.get("language") or "").strip(),
                "source_url": str(record.get("url") or "").strip(),
                "video_url_present": bool(record.get("video_url")),
                "license_label": license_text.splitlines()[0].strip() if license_text else "",
                "transcript_words": len(transcript.split()),
                "segment_text_words": len(segment_text.split()),
                "transcript_matches_segments": _tokens(transcript) == _tokens(segment_text),
                "segment_count": len(texts),
                "duration_minutes": round(duration / 60, 2),
                "words_per_minute": round(len(_tokens(transcript)) / (duration / 60), 1) if duration else None,
                "zero_duration_segments": sum(start == end for start, end in zip(starts, ends)),
                "gaps_over_30_sec": sum(starts[index] - ends[index - 1] > 30
                                        for index in range(1, len(starts))),
                "abstract_words": len(abstract.split()),
                "abstract_chars": len(abstract),
                "abstract_text": abstract,
                "abstract_preview": _preview(abstract),
                "transcript_example": _preview(texts[len(texts) // 2]),
                "keyframe_count": len(ranges),
                "keyframe_arrays_aligned": keyframe_arrays_aligned,
                "keyframe_intervals_ordered": ordered_keyframes,
                "keyframe_last_minus_transcript_end_sec": round(ranges[-1][1] - duration, 2)
                if ranges and valid_ranges[-1] else None,
                "keyframe_pixels_read": False,
                "audio_sample_read": False,
            }
        except (TypeError, ValueError, OverflowError, AttributeError, IndexError) as exc:
            found[source_index] = {
                "source_index": source_index,
                "doi": doi,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    for source_index, row in wanted.items():
        if source_index not in found:
            found[source_index] = {
                "source_index": source_index,
                "doi": row["doi"],
                "status": "missing",
                "error": "Validation source index absent at pinned revision",
            }
    return [found[index] for index in sorted(wanted)]


def scan_all_usable_details(usable: list[dict]) -> list[dict]:
    """Validation-only detail scan retained for the earlier extension."""
    return _scan_usable_details_for_split(usable, "valid")


def scan_all_dataset_details(usable: list[dict]) -> list[dict]:
    """Inspect all structurally usable rows across every creator split."""
    unknown = {row.get("split") for row in usable} - set(ALL_SPLITS)
    if unknown:
        raise ValueError(f"Unknown TIB splits: {sorted(map(str, unknown))}")
    details = []
    for split in ALL_SPLITS:
        rows = [row for row in usable if row["split"] == split]
        details.extend({"split": split, **detail}
                       for detail in _scan_usable_details_for_split(rows, split))
    return details
