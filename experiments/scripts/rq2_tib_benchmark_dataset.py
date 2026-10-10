"""Prepare pinned TIB text inputs for a limited RQ2 abstract-agreement benchmark.

This module returns data and audit tables in memory. It never qualifies creator
abstracts as factual ground truth or silently truncates a transcript.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from typing import Iterable, Mapping

DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
SPLITS = ("train", "valid", "test")
EXPECTED_COUNTS = {"train": 7282, "valid": 910, "test": 911}
_RAW_FIELDS = {"source_text", "reference_text", "segment_texts", "segment_starts_seconds",
               "segment_ends_seconds"}


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized(value: object) -> str:
    return " ".join(_text(value).casefold().split())


def _tokens(value: object) -> list[str]:
    return re.findall(r"\b\w+\b", _text(value).casefold())


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def prepare_record(split: str, source_index: int, record: Mapping) -> dict:
    """Keep original segment content and explain every mechanical exclusion."""
    if split not in SPLITS or not isinstance(source_index, int) or source_index < 0:
        raise ValueError("A valid creator split and nonnegative source_index are required")
    transcript = _text(record.get("transcript"))
    abstract = _text(record.get("abstract"))
    segments = record.get("transcript_segments")
    segments = segments if isinstance(segments, Mapping) else {}
    arrays = [segments.get(field) for field in ("text", "start", "end")]
    aligned_arrays = all(isinstance(value, (list, tuple)) for value in arrays)
    texts, starts, ends = (tuple(value) for value in arrays) if aligned_arrays else ((), (), ())
    clean_texts = tuple(_text(value) for value in texts)
    source_text = " ".join(clean_texts)
    structural_reasons: list[str] = []
    if not transcript:
        structural_reasons.append("missing_transcript")
    if len(texts) < 2:
        structural_reasons.append("insufficient_segments")
    if not aligned_arrays or len(texts) != len(starts) or len(texts) != len(ends):
        structural_reasons.append("misaligned_segments")
    if any(not text for text in clean_texts):
        structural_reasons.append("empty_segment_text")
    valid_times = (
        aligned_arrays
        and len(texts) == len(starts) == len(ends)
        and all(
            isinstance(start, (int, float)) and not isinstance(start, bool)
            and isinstance(end, (int, float)) and not isinstance(end, bool)
            and math.isfinite(start) and math.isfinite(end)
            and 0 <= start <= end
            for start, end in zip(starts, ends)
        )
    )
    if not valid_times:
        structural_reasons.append("invalid_segment_times")
    elif any(starts[i] < starts[i - 1] for i in range(1, len(starts))):
        structural_reasons.append("unordered_segments")
    # Overlaps and text disagreement need review, but both arms can use the same
    # ordered segment text; neither destroys a text-only source by itself.
    overlap_count = (sum(starts[i] < ends[i - 1] for i in range(1, len(starts)))
                     if valid_times and "unordered_segments" not in structural_reasons else None)
    transcript_matches_segments = _tokens(transcript) == _tokens(source_text)
    reference_reasons = [] if abstract else ["empty_abstract"]
    flags = []
    if not _text(record.get("doi")):
        flags.append("missing_doi")
    if not _text(record.get("url")):
        flags.append("missing_source_url")
    if abstract and len(abstract.split()) < 30:
        flags.append("short_abstract_under_30_words")
    if overlap_count:
        flags.append("overlapping_segments")
    if transcript and source_text and not transcript_matches_segments:
        flags.append("transcript_segment_mismatch")
    license_text = _text(record.get("license"))
    source_url = _text(record.get("url"))
    return {
        "split": split, "source_index": source_index,
        "doi": _text(record.get("doi")), "title": _text(record.get("title")),
        "author": _text(record.get("author")), "genre": _text(record.get("genre")),
        "subject": _text(record.get("subject")), "language": _text(record.get("language")),
        "release_year": _text(record.get("release_year")),
        "license_label": license_text.splitlines()[0] if license_text else "",
        "source_url": source_url, "source_url_present": bool(source_url),
        "video_url_present": bool(_text(record.get("video_url"))),
        "transcript_words": len(transcript.split()),
        "source_words": len(source_text.split()),
        "abstract_words": len(abstract.split()), "segment_count": len(texts),
        "duration_minutes": max(ends) / 60 if valid_times and ends else None,
        "segment_overlap_count": overlap_count,
        "transcript_matches_segments": transcript_matches_segments,
        "source_text": source_text, "reference_text": abstract,
        "segment_texts": clean_texts,
        "segment_starts_seconds": tuple(float(x) for x in starts) if valid_times else (),
        "segment_ends_seconds": tuple(float(x) for x in ends) if valid_times else (),
        "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "reference_sha256": hashlib.sha256(abstract.encode("utf-8")).hexdigest(),
        "structural_reasons": structural_reasons,
        "reference_reasons": reference_reasons,
        "audit_flags": flags,
        "text_usable": not structural_reasons,
        "abstract_agreement_candidate": not structural_reasons and not reference_reasons,
        "unique_reference_candidate": not structural_reasons and not reference_reasons,
        "domain_status": "unverified",
        "reference_status": "unverified_creator_abstract",
    }


def load_pinned_splits(splits: Iterable[str]) -> dict[str, Iterable[Mapping]]:
    """Stream explicitly requested creator splits; importing this module stays offline."""
    requested = tuple(splits)
    if not requested or len(set(requested)) != len(requested) or set(requested) - set(SPLITS):
        raise ValueError("Specify distinct train/valid/test splits")
    from datasets import load_dataset

    return {
        split: load_dataset(DATASET, split=split, revision=REVISION, streaming=True)
        for split in requested
    }


def prepare_dataset(rows_by_split: Mapping[str, Iterable[Mapping]], *,
                    verify_counts: bool = True) -> dict:
    """Build a deterministic audit and mechanical candidates without file output."""
    if not rows_by_split or set(rows_by_split) - set(SPLITS):
        raise ValueError("Unknown or empty creator split selection")
    records = [
        prepare_record(split, index, record)
        for split in SPLITS if split in rows_by_split
        for index, record in enumerate(rows_by_split[split])
    ]
    counts = {split: sum(row["split"] == split for row in records)
              for split in SPLITS if split in rows_by_split}
    if verify_counts and any(count != EXPECTED_COUNTS[split] for split, count in counts.items()):
        raise ValueError(f"Pinned TIB row count changed: {counts}")
    shared_groups: dict[str, int] = {}
    for field in ("doi", "title", "author"):
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in records:
            key = _normalized(row[field])
            if key:
                groups[key].append(row)
        shared = [group for group in groups.values()
                  if len({row["split"] for row in group}) > 1]
        shared_groups[field] = len(shared)
        for group in shared:
            for row in group:
                row["audit_flags"].append(f"cross_split_{field}_group")
    references: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        key = _normalized(row["reference_text"])
        if key and row["text_usable"]:
            references[key].append(row)
    for group in references.values():
        if len(group) > 1:
            # A reused abstract cannot distinguish the content of individual talks.
            cross_split = len({row["split"] for row in group}) > 1
            for row in group:
                row["audit_flags"].append("shared_abstract_group")
                if cross_split:
                    row["audit_flags"].append("cross_split_shared_abstract_group")
                row["unique_reference_candidate"] = False
    for row in records:
        row["audit_flags"].sort()
    candidates = [row for row in records if row["abstract_agreement_candidate"]]
    broad_pool = [row for row in records if row["unique_reference_candidate"]]
    broad_identity = [{"split": row["split"], "source_index": row["source_index"],
                       "doi": row["doi"], "reference_sha256": row["reference_sha256"]}
                      for row in broad_pool]
    duration_bins = Counter(
        "unknown" if row["duration_minutes"] is None else
        "under_15" if row["duration_minutes"] < 15 else
        "15_to_30" if row["duration_minutes"] < 30 else
        "30_to_60" if row["duration_minutes"] < 60 else
        "60_to_90" if row["duration_minutes"] < 90 else "90_plus"
        for row in broad_pool
    )
    audit = [{key: value for key, value in row.items() if key not in _RAW_FIELDS}
             for row in records]
    return {
        "dataset": DATASET, "revision": REVISION,
        "splits_read": [split for split in SPLITS if split in rows_by_split],
        "all_splits_scanned": set(rows_by_split) == set(SPLITS),
        "test_content_accessed": "test" in rows_by_split,
        "source_count": len(records), "candidate_count": len(candidates),
        "broad_pool_count": len(broad_pool),
        "broad_pool_ids": [(row["split"], row["source_index"]) for row in broad_pool],
        "broad_pool_sha256": _digest(broad_identity),
        "broad_pool_diversity": {
            "genre": dict(Counter(row["genre"] for row in broad_pool)),
            "subject": dict(Counter(row["subject"] for row in broad_pool)),
            "release_year": dict(Counter(row["release_year"] for row in broad_pool)),
            "duration_bin": dict(duration_bins),
        },
        "counts_by_split": counts, "shared_group_counts": shared_groups,
        "structural_exclusions": dict(Counter(reason for row in records
                                              for reason in row["structural_reasons"])),
        "reference_exclusions": dict(Counter(reason for row in records
                                             for reason in row["reference_reasons"])),
        "audit": audit, "records": records,
        "status": "mechanical_candidates_only",
    }


def freeze_abstract_agreement_cohort(prepared: Mapping,
                                     selected_ids: Iterable[tuple[str, int]]) -> dict:
    """Freeze explicit candidates for a limited, text-only paired comparison."""
    if prepared.get("dataset") != DATASET or prepared.get("revision") != REVISION:
        raise ValueError("Dataset or revision does not match pinned TIB")
    selected = list(selected_ids)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("Select distinct (split, source_index) IDs")
    by_id = {(row["split"], row["source_index"]): row for row in prepared["records"]}
    if len(by_id) != len(prepared["records"]):
        raise ValueError("Duplicate source IDs in preparation")
    if any(key not in by_id or not by_id[key]["unique_reference_candidate"]
           for key in selected):
        raise ValueError("Selected ID is missing or mechanically ineligible")
    items = sorted((by_id[key] for key in selected),
                   key=lambda row: (SPLITS.index(row["split"]), row["source_index"]))
    identity = [{"split": row["split"], "source_index": row["source_index"],
                 "doi": row["doi"], "source_sha256": row["source_sha256"],
                 "reference_sha256": row["reference_sha256"]} for row in items]
    return {
        "dataset": DATASET, "revision": REVISION,
        "claim": "agreement_with_unverified_creator_abstracts_only",
        "reference_status": "unverified_creator_abstract",
        "domain_status": "unverified",
        "group_safety_verified": False,
        "all_splits_scanned": prepared.get("all_splits_scanned", False),
        "unseen_final_test_claim_supported": False,
        "selected_count": len(items),
        "selected_ids": [(row["split"], row["source_index"]) for row in items],
        "selection_sha256": _digest(identity), "items": items,
    }
