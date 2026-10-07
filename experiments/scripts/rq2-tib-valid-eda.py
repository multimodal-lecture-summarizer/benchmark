"""Validation-only metadata scan for the RQ2 TIB text diagnostic."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset


DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
SPLIT = "valid"
ALL_SPLITS = ("train", "valid", "test")


def _word_count(value: object) -> int:
    return len(str(value or "").split())


def _normalized(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _doi_url_match(doi: object, url: object) -> bool | None:
    doi_id = re.search(r"10\.5446/(\d+)", str(doi or ""))
    url_id = re.search(r"/media/(\d+)", str(url or ""))
    return doi_id.group(1) == url_id.group(1) if doi_id and url_id else None


def _finite_time(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _scan_split(split: str) -> list[dict]:
    """Read one pinned creator split and retain compact metadata."""
    rows = []
    dataset = load_dataset(DATASET, split=split, revision=REVISION, streaming=True)
    for index, record in enumerate(dataset):
        segments = record.get("transcript_segments") or {}
        starts = (segments.get("start") or []) if isinstance(segments, dict) else []
        ends = (segments.get("end") or []) if isinstance(segments, dict) else []
        texts = (segments.get("text") or []) if isinstance(segments, dict) else []
        aligned = len(starts) == len(ends) == len(texts)
        numeric_times = all(
            _finite_time(start) and _finite_time(end)
            for start, end in zip(starts, ends)
        )
        valid_times = aligned and numeric_times and all(
            start >= 0 and end >= start for start, end in zip(starts, ends)
        )
        transcript_words = _word_count(record.get("transcript"))
        segment_words = sum(_word_count(text) for text in texts)
        ordered = valid_times and all(starts[i] >= starts[i - 1] for i in range(1, len(starts)))
        first_start_inversion = next(
            (
                {
                    "previous_segment": i - 1,
                    "previous_start_seconds": starts[i - 1],
                    "current_segment": i,
                    "current_start_seconds": starts[i],
                }
                for i in range(1, len(starts))
                if valid_times and starts[i] < starts[i - 1]
            ),
            None,
        )
        overlap_count = sum(starts[i] < ends[i - 1] for i in range(1, len(starts))) if ordered else None
        rows.append(
            {
                "source_index": index,
                "doi": str(record.get("doi") or "").strip(),
                "title": str(record.get("title") or "").strip(),
                "genre": str(record.get("genre") or "").strip(),
                "subject": str(record.get("subject") or "").strip(),
                "author": str(record.get("author") or "").strip(),
                "release_year": str(record.get("release_year") or "").strip(),
                "language": str(record.get("language") or "").strip(),
                "source_url_present": bool(record.get("url")),
                "doi_source_url_match": _doi_url_match(record.get("doi"), record.get("url")),
                "video_url_present": bool(record.get("video_url")),
                "transcript_words": transcript_words,
                "segment_text_words": segment_words,
                "segment_word_ratio": round(segment_words / transcript_words, 3) if transcript_words else None,
                "abstract_words": _word_count(record.get("abstract")),
                "segment_count": len(texts),
                "segments_aligned": aligned,
                "segments_valid_times": valid_times,
                "segments_ordered": ordered,
                "first_start_inversion": first_start_inversion,
                "segment_overlaps": overlap_count,
                "empty_segment_texts": sum(not str(text or "").strip() for text in texts),
                "duration_minutes": max(ends) / 60 if valid_times and ends else None,
            }
        )
    return rows


def scan_validation() -> list[dict]:
    """Historical validation-only diagnostic; retain its original row shape."""
    return _scan_split(SPLIT)


def scan_all_splits() -> list[dict]:
    """Scan every creator TIB record in train, valid and test, without genre filtering."""
    return [{"split": split, **row} for split in ALL_SPLITS for row in _scan_split(split)]


def build_full_validation_cohort(rows: list[dict], output: Path) -> dict:
    """Audit every validation row and export a reproducible, non-genre-gated cohort.

    A DOI is metadata, not a row key: duplicate and missing DOIs remain in the
    structurally usable list when their transcript is valid, with audit flags.
    """
    if len({row["source_index"] for row in rows}) != len(rows):
        raise ValueError("Duplicate source_index in validation scan")
    doi_counts = Counter(str(row.get("doi") or "").strip() for row in rows)
    manifest = []
    for row in sorted(rows, key=lambda item: item["source_index"]):
        doi = str(row.get("doi") or "").strip()
        flags = []
        if not doi:
            flags.append("missing_doi")
        elif doi_counts[doi] > 1:
            flags.append("duplicate_doi")
        if not row.get("source_url_present"):
            flags.append("missing_source_url")
        reasons = []
        if row.get("transcript_words", 0) <= 0:
            reasons.append("missing_transcript")
        if row.get("segment_count", 0) < 2:
            reasons.append("insufficient_segments")
        if not row.get("segments_aligned"):
            reasons.append("misaligned_segments")
        if not row.get("segments_valid_times"):
            reasons.append("invalid_segment_times")
        elif not row.get("segments_ordered"):
            reasons.append("unordered_segments")
        manifest.append({**row, "usable": not reasons, "exclusion_reasons": reasons,
                         "audit_flags": flags})
    usable = [row for row in manifest if row["usable"]]
    canonical = [{"source_index": row["source_index"], "doi": row["doi"]} for row in usable]
    digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    receipt = {
        "dataset": DATASET,
        "revision": REVISION,
        "split_read": SPLIT,
        "test_content_accessed": False,
        "selection": "Every valid row with structurally usable transcript, regardless of genre or DOI/URL flags; no abstract quality or label claim",
        "source_count": len(manifest),
        "usable_count": len(usable),
        "excluded_count": len(manifest) - len(usable),
        "usable_index_doi_sha256": digest,
        "manifest": manifest,
        "usable": canonical,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def build_full_dataset_cohort(rows: list[dict], output: Path) -> dict:
    """Export all split rows and a separately marked text-usable cohort.

    Access to `test` here is intentional for whole-dataset EDA. Its previous
    sealed-final-test status cannot be claimed for this new analysis.
    """
    keys = [(row["split"], row["source_index"]) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate split/source_index in TIB scan")
    unknown = {row["split"] for row in rows} - set(ALL_SPLITS)
    if unknown:
        raise ValueError(f"Unknown TIB splits: {sorted(unknown)}")
    doi_counts = Counter(str(row.get("doi") or "").strip() for row in rows)
    manifest = []
    for row in sorted(rows, key=lambda item: (ALL_SPLITS.index(item["split"]), item["source_index"])):
        doi = str(row.get("doi") or "").strip()
        flags = []
        if not doi:
            flags.append("missing_doi")
        elif doi_counts[doi] > 1:
            flags.append("duplicate_doi_across_dataset")
        if not row.get("source_url_present"):
            flags.append("missing_source_url")
        reasons = []
        if row.get("transcript_words", 0) <= 0:
            reasons.append("missing_transcript")
        if row.get("segment_count", 0) < 2:
            reasons.append("insufficient_segments")
        if not row.get("segments_aligned"):
            reasons.append("misaligned_segments")
        if not row.get("segments_valid_times"):
            reasons.append("invalid_segment_times")
        elif not row.get("segments_ordered"):
            reasons.append("unordered_segments")
        manifest.append({**row, "usable": not reasons, "exclusion_reasons": reasons,
                         "audit_flags": flags})
    usable = [{"split": row["split"], "source_index": row["source_index"], "doi": row["doi"]}
              for row in manifest if row["usable"]]
    split_counts = {
        split: {
            "source_count": sum(row["split"] == split for row in manifest),
            "usable_count": sum(row["split"] == split and row["usable"] for row in manifest),
        }
        for split in ALL_SPLITS
    }
    cross_split_groups = {}
    for field in ("doi", "title", "author"):
        groups: dict[str, set[str]] = defaultdict(set)
        for row in manifest:
            key = _normalized(row.get(field))
            if key:
                groups[key].add(row["split"])
        cross_split_groups[field] = sum(len(splits) > 1 for splits in groups.values())
    digest = hashlib.sha256(json.dumps(usable, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    receipt = {
        "dataset": DATASET,
        "revision": REVISION,
        "splits_read": list(ALL_SPLITS),
        "test_content_accessed": True,
        "final_test_holdout_sealed": False,
        "selection": "Every creator record; usable denotes timed transcript structure only, regardless of genre or DOI/URL flags",
        "source_count": len(manifest),
        "usable_count": len(usable),
        "excluded_count": len(manifest) - len(usable),
        "split_counts": split_counts,
        "cross_split_shared_group_counts": cross_split_groups,
        "usable_split_index_doi_sha256": digest,
        "manifest": manifest,
        "usable": usable,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def select_diagnostic(rows: list[dict], limit: int = 20) -> list[dict]:
    """Stable development selection; no test content or reference-based screen."""
    candidates = [
        row
        for row in rows
        if row["genre"].casefold() == "lecture"
        and row["doi"]
        and row["source_url_present"]
        and row["transcript_words"] > 0
        and row["segment_count"] >= 2
        and row["segments_valid_times"]
        and row["segments_ordered"]
    ]
    candidates.sort(key=lambda row: (hashlib.sha256(row["doi"].encode()).hexdigest(), row["doi"]))
    selected = []
    used_authors = set()
    for row in candidates:
        author_key = _normalized(row["author"])
        if author_key and author_key in used_authors:
            continue
        selected.append(row)
        if author_key:
            used_authors.add(author_key)
        if len(selected) == limit:
            break
    return selected


def write_receipt(rows: list[dict], selected: list[dict], output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    selected_ids = [row["doi"] for row in selected]
    digest = hashlib.sha256(json.dumps(selected_ids, ensure_ascii=False).encode()).hexdigest()
    receipt = {
        "dataset": DATASET,
        "revision": REVISION,
        "split_read": SPLIT,
        "test_content_accessed": False,
        "selection": "SHA-256 DOI order, first 20 validation Lecture records with DOI, source URL and ordered timed transcript, one record per exact normalized author string; license is not an eligibility gate",
        "source_count": len(rows),
        "lecture_count": sum(row["genre"].casefold() == "lecture" for row in rows),
        "candidate_count": sum(
            row["genre"].casefold() == "lecture"
            and row["doi"]
            and row["source_url_present"]
            and row["transcript_words"] > 0
            and row["segment_count"] >= 2
            and row["segments_valid_times"]
            and row["segments_ordered"]
            for row in rows
        ),
        "lecture_anomalies": [
            {
                "doi": row["doi"],
                "doi_source_url_match": row["doi_source_url_match"],
                "segments_ordered": row["segments_ordered"],
                "first_start_inversion": row["first_start_inversion"],
            }
            for row in rows
            if row["genre"].casefold() == "lecture"
            and (row["doi_source_url_match"] is not True or not row["segments_ordered"])
        ],
        "selected_doi_sha256": digest,
        "selected": selected,
        "status": "LIMIT: text diagnostic candidate only; source/group/reference quality and human H2 gates pending",
    }
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def scan_train_metadata_overlap(selected: list[dict]) -> dict:
    """Project only DOI, title and author from train Parquet; never read test."""
    import pyarrow.parquet as parquet
    from huggingface_hub import HfFileSystem

    selected_ids = {row["doi"] for row in selected if row["doi"]}
    selected_titles: dict[str, set[str]] = defaultdict(set)
    selected_authors: dict[str, set[str]] = defaultdict(set)
    doi_indices: dict[str, set[int]] = defaultdict(set)
    title_indices: dict[str, set[int]] = defaultdict(set)
    author_indices: dict[str, set[int]] = defaultdict(set)
    for row in selected:
        source_index = row.get("source_index")
        if isinstance(source_index, int):
            if row["doi"]:
                doi_indices[row["doi"]].add(source_index)
            if row["title"]:
                title_indices[_normalized(row["title"])].add(source_index)
            if row["author"]:
                author_indices[_normalized(row["author"])].add(source_index)
        if row["title"]:
            selected_titles[_normalized(row["title"])].add(row["doi"])
        if row["author"]:
            selected_authors[_normalized(row["author"])].add(row["doi"])
    doi_hits: set[str] = set()
    title_hits: set[str] = set()
    author_counts = {doi: 0 for doi in selected_ids}
    doi_index_hits: set[int] = set()
    title_index_hits: set[int] = set()
    author_index_counts = {index: 0 for row in selected
                           if isinstance(index := row.get("source_index"), int)}
    scanned = 0
    filesystem = HfFileSystem()
    for shard in range(2):
        remote = (
            f"datasets/{DATASET}@{REVISION}/data/"
            f"train-{shard:05d}-of-00002.parquet"
        )
        with filesystem.open(remote, "rb") as source:
            table = parquet.ParquetFile(source)
            for batch in table.iter_batches(columns=["doi", "title", "author"], batch_size=4096):
                for record in batch.to_pylist():
                    scanned += 1
                    doi = str(record.get("doi") or "").strip()
                    title = _normalized(record.get("title"))
                    author = _normalized(record.get("author"))
                    if doi in selected_ids:
                        doi_hits.add(doi)
                        doi_index_hits.update(doi_indices.get(doi, ()))
                    title_hits.update(selected_titles.get(title, ()))
                    title_index_hits.update(title_indices.get(title, ()))
                    for selected_doi in selected_authors.get(author, ()):
                        author_counts[selected_doi] += 1
                    for source_index in author_indices.get(author, ()):
                        author_index_counts[source_index] += 1
    return {
        "revision": REVISION,
        "train_records_scanned": scanned,
        "columns_read": ["doi", "title", "author"],
        "test_content_accessed": False,
        "selected_doi_in_train": sorted(doi_hits),
        "selected_exact_title_in_train": sorted(title_hits),
        "selected_author_train_record_counts": {doi: n for doi, n in author_counts.items() if n},
        "selected_source_index_doi_in_train": sorted(doi_index_hits),
        "selected_source_index_exact_title_in_train": sorted(title_index_hits),
        "selected_source_index_author_train_record_counts": {
            str(index): n for index, n in sorted(author_index_counts.items()) if n
        },
    }
