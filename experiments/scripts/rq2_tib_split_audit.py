"""Audit creator-split overlap without reading abstract/reference text.

The review queue comes from the saved all-split EDA export. Full transcript
content is fetched only for queued source IDs from the pinned public release.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from urllib.parse import urlsplit

from experiments.scripts.rq2_tib_benchmark_dataset import (
    DATASET, EXPECTED_COUNTS, REVISION, SPLITS, load_pinned_splits,
)

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = Path.home() / "Downloads" / "drive-download-20261009T023146Z-1-001.zip"
OUT = ROOT / "experiments" / "outputs" / "rq2_tib_split_audit"
EXPECTED_ARCHIVE_SHA256 = "c86daacd4c861b1be7d1e5b81a92d6a96c2c059296ab1b5b1f2b3af4f567dcbd"
FIELDS = ("title", "author")


def digest_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def tokens(value: object) -> tuple[str, ...]:
    return tuple(re.findall(r"\b\w+\b", str(value or "").casefold()))


def shingle_set(words: tuple[str, ...], size: int = 5) -> set[str]:
    return {" ".join(words[i:i + size]) for i in range(max(0, len(words) - size + 1))}


def series_stem(title: object) -> str:
    """Conservative lexical clue only; never an exclusion rule."""
    value = str(title or "").casefold()
    value = re.sub(r"\b(?:lecture|part|episode|session|lesson)\s*[#:.-]?\s*\d+\b", "", value)
    value = re.sub(r"\b\d{1,3}\s*(?:/|of)\s*\d{1,3}\b", "", value)
    value = re.sub(r"\s+", " ", value).strip(" :-._")
    return value if len(value) >= 12 else ""


def normalized_url(value: object) -> str:
    parts = urlsplit(str(value or "").strip())
    return (parts.netloc.casefold() + parts.path.rstrip("/").casefold()) if parts.netloc else ""


def read_queue() -> tuple[dict, dict, str]:
    sha = digest_file(ARCHIVE)
    if sha != EXPECTED_ARCHIVE_SHA256:
        raise ValueError(f"EDA ZIP hash differs: {sha}")
    with zipfile.ZipFile(ARCHIVE) as archive:
        manifest = csv.DictReader(io.TextIOWrapper(archive.open("all_splits_manifest.csv"), encoding="utf-8-sig"))
        by_id = {(row["split"], int(row["source_index"])): row for row in manifest}
        ledger = csv.DictReader(io.TextIOWrapper(archive.open("cross_split_shared_groups.csv"), encoding="utf-8-sig"))
        groups = defaultdict(list)
        for row in ledger:
            if row["field"] not in FIELDS:
                continue
            key = (row["field"], row["normalized_value"])
            identity = (row["split"], int(row["source_index"]))
            if identity not in by_id:
                raise ValueError(f"Missing EDA manifest identity: {identity}")
            groups[key].append(identity)
    if Counter(field for field, _ in groups) != {"title": 11, "author": 398}:
        raise ValueError("Saved EDA queue no longer matches the declared 11/398 groups")
    return by_id, groups, sha


def fetch_queue(ids: set[tuple[str, int]]) -> tuple[dict, dict]:
    source = load_pinned_splits(SPLITS)
    rows = {}
    counts = {}
    for split in SPLITS:
        count = 0
        for index, record in enumerate(source[split]):
            count += 1
            key = (split, index)
            if key not in ids:
                continue
            words = tokens(record.get("transcript"))
            joined = " ".join(words)
            rows[key] = {
                "doi": str(record.get("doi") or "").strip().casefold(),
                "title": str(record.get("title") or "").strip(),
                "author": str(record.get("author") or "").strip(),
                "source_url": normalized_url(record.get("url")),
                "video_url": normalized_url(record.get("video_url")),
                "source_host": urlsplit(str(record.get("url") or "")).netloc.casefold(),
                "series_stem": series_stem(record.get("title")),
                "transcript_sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest(),
                "transcript_token_count": len(words),
                "shingles": shingle_set(words),
            }
        counts[split] = count
        if count != EXPECTED_COUNTS[split]:
            raise ValueError(f"Pinned split count changed: {split}={count}")
    if set(rows) != ids:
        raise ValueError(f"Queued records missing from HF: {len(ids - set(rows))}")
    return rows, counts


def score_pair(left: dict, right: dict) -> dict:
    overlap = len(left["shingles"] & right["shingles"])
    union = len(left["shingles"] | right["shingles"])
    smaller = min(len(left["shingles"]), len(right["shingles"]))
    exact_source = bool(left["source_url"] and left["source_url"] == right["source_url"])
    exact_video = bool(left["video_url"] and left["video_url"] == right["video_url"])
    exact_doi = bool(left["doi"] and left["doi"] == right["doi"])
    exact_text = (left["transcript_token_count"] > 0 and left["transcript_sha256"] == right["transcript_sha256"])
    jaccard = overlap / union if union else 0.0
    containment = overlap / smaller if smaller else 0.0
    # A shared series stem or author is evidence of relation, not duplication.
    if exact_doi or exact_source or exact_video or exact_text or jaccard >= 0.80:
        review = "probable_same_source_or_content"
    elif jaccard >= 0.30 or containment >= 0.80:
        review = "high_content_similarity_review"
    elif left["series_stem"] and left["series_stem"] == right["series_stem"]:
        review = "possible_series_review"
    else:
        review = "shared_metadata_only"
    return {
        "exact_doi": exact_doi, "exact_source_url": exact_source,
        "exact_video_url": exact_video, "exact_transcript_hash": exact_text,
        "same_source_host": bool(left["source_host"] and left["source_host"] == right["source_host"]),
        "same_series_stem": bool(left["series_stem"] and left["series_stem"] == right["series_stem"]),
        "fivegram_intersection": overlap,
        "fivegram_jaccard": round(jaccard, 6),
        "fivegram_containment_shorter": round(containment, 6),
        "review_class": review,
        "action": "review_no_auto_exclusion",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    by_id, groups, archive_sha = read_queue()
    ids = {identity for members in groups.values() for identity in members}
    rows, counts = fetch_queue(ids)
    pairs = {}
    group_rows = []
    for (field, normalized_value), members in sorted(groups.items()):
        cross_pairs = [(a, b) for a, b in combinations(sorted(members), 2) if a[0] != b[0]]
        classes = Counter()
        for a, b in cross_pairs:
            pair_key = tuple(sorted((a, b)))
            evidence = score_pair(rows[a], rows[b])
            classes[evidence["review_class"]] += 1
            if pair_key not in pairs:
                pairs[pair_key] = {
                    "left_split": pair_key[0][0], "left_index": pair_key[0][1],
                    "left_doi": rows[pair_key[0]]["doi"],
                    "left_source_url": rows[pair_key[0]]["source_url"],
                    "left_title": rows[pair_key[0]]["title"],
                    "left_series_stem": rows[pair_key[0]]["series_stem"],
                    "left_transcript_sha256": rows[pair_key[0]]["transcript_sha256"],
                    "left_transcript_tokens": rows[pair_key[0]]["transcript_token_count"],
                    "right_split": pair_key[1][0], "right_index": pair_key[1][1],
                    "right_doi": rows[pair_key[1]]["doi"],
                    "right_source_url": rows[pair_key[1]]["source_url"],
                    "right_title": rows[pair_key[1]]["title"],
                    "right_series_stem": rows[pair_key[1]]["series_stem"],
                    "right_transcript_sha256": rows[pair_key[1]]["transcript_sha256"],
                    "right_transcript_tokens": rows[pair_key[1]]["transcript_token_count"],
                    **evidence, "shared_fields": field,
                }
            elif field not in pairs[pair_key]["shared_fields"].split("|"):
                pairs[pair_key]["shared_fields"] += "|" + field
        group_rows.append({
            "field": field, "normalized_value": normalized_value,
            "member_count": len(members),
            "split_counts": json.dumps(dict(Counter(split for split, _ in members)), sort_keys=True),
            "cross_split_pair_count": len(cross_pairs),
            "review_classes": json.dumps(dict(classes), sort_keys=True),
            "member_ids": "|".join(f"{split}:{index}" for split, index in sorted(members)),
            "action": "review_no_auto_exclusion",
        })
    OUT.mkdir(parents=True, exist_ok=True)
    pair_rows = list(pairs.values())
    write_csv(OUT / "cross_split_pair_evidence.csv", pair_rows)
    write_csv(OUT / "cross_split_group_evidence.csv", group_rows)
    summary = {
        "dataset": DATASET, "revision": REVISION, "source_splits_scanned": counts,
        "source_total": sum(counts.values()), "queue_archive_sha256": archive_sha,
        "group_counts": dict(Counter(row["field"] for row in group_rows)),
        "queued_unique_record_count": len(ids), "unique_cross_split_pairs": len(pair_rows),
        "pair_review_classes": dict(Counter(row["review_class"] for row in pair_rows)),
        "test_abstracts_inspected": False, "transcript_normalization": "casefold Unicode word tokens joined by spaces",
        "similarity": "set of contiguous 5-word shingles; Jaccard and containment in shorter set",
        "auto_excluded_count": 0,
        "status": "source_group_review_evidence_not_a_final_cohort_gate",
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
