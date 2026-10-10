"""Reusable, self-contained TIB benchmark data bundles and source-only inputs."""

import gzip
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

from experiments.scripts import rq2_tib_benchmark_dataset as tib

FORMAT = "rq2-tib-benchmark-data-v1"


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _identity(items):
    return [{key: row[key] for key in
             ("split", "source_index", "doi", "source_sha256", "reference_sha256")}
            for row in items]


def build_benchmark_bundle(prepared):
    """Select the complete EDA pool automatically, without manual-review gates."""
    if not prepared.get("all_splits_scanned"):
        raise ValueError("Read all three pinned splits before building the benchmark data")
    cohort = tib.freeze_abstract_agreement_cohort(prepared, prepared["broad_pool_ids"])
    excluded = []
    for row in prepared["records"]:
        if not row["unique_reference_candidate"]:
            reasons = list(row["structural_reasons"]) + list(row["reference_reasons"])
            if row["text_usable"] and row["reference_text"] and not row["unique_reference_candidate"]:
                reasons.append("reused_abstract")
            excluded.append({"split": row["split"], "source_index": row["source_index"],
                             "doi": row["doi"], "reasons": reasons})
    metadata = {
        "format": FORMAT, "dataset": tib.DATASET, "revision": tib.REVISION,
        "source_count": prepared["source_count"], "selected_count": cohort["selected_count"],
        "selection_sha256": cohort["selection_sha256"],
        "broad_pool_sha256": prepared["broad_pool_sha256"],
        "counts_by_split": prepared["counts_by_split"],
        "diversity": prepared["broad_pool_diversity"], "excluded": excluded,
        "reference_policy": "nonempty_unique_normalized_abstract",
        "source_policy": "full_ordered_segment_text_no_truncation",
        "arms": ["S1", "S3"], "primary_metric": "rouge_l_f1_against_creator_abstract",
        "evaluation_unit": "split/source_index", "status": "prepared",
    }
    return {"metadata": metadata, "items": cohort["items"]}


def add_token_counts(bundle, encode, *, tokenizer_id, tokenizer_revision):
    """Measure full source/reference lengths; never truncate or exclude long talks."""
    if not tokenizer_id or not tokenizer_revision:
        raise ValueError("Declare the tokenizer and its pinned revision")
    for row in bundle["items"]:
        row["source_tokens"] = len(encode(row["source_text"]))
        row["reference_tokens"] = len(encode(row["reference_text"]))
    bundle["metadata"]["tokenizer"] = {"id": tokenizer_id, "revision": tokenizer_revision,
                                         "add_special_tokens": False, "truncation": False}
    return bundle


def validate_bundle(bundle):
    """Check identity, complete source content and references after save/reload."""
    metadata, items = bundle["metadata"], bundle["items"]
    if (metadata.get("format") != FORMAT or metadata.get("dataset") != tib.DATASET
            or metadata.get("revision") != tib.REVISION):
        raise ValueError("Unexpected TIB bundle format or revision")
    if not items or metadata.get("selected_count") != len(items):
        raise ValueError("Incomplete benchmark item count")
    keys = [(row["split"], row["source_index"]) for row in items]
    if len(set(keys)) != len(keys) or keys != sorted(keys, key=lambda x: (tib.SPLITS.index(x[0]), x[1])):
        raise ValueError("Duplicate or unordered benchmark IDs")
    for row in items:
        texts, starts, ends = (row[key] for key in
                              ("segment_texts", "segment_starts_seconds", "segment_ends_seconds"))
        if len(texts) < 2 or len(texts) != len(starts) or len(texts) != len(ends):
            raise ValueError("Incomplete timed source")
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Empty source segment")
        if (any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x)
                for x in list(starts) + list(ends))
                or any(a < 0 or b < a for a, b in zip(starts, ends))
                or any(starts[i] < starts[i - 1] for i in range(1, len(starts)))):
            raise ValueError("Invalid or unordered source times")
        if " ".join(texts) != row["source_text"] or not row["reference_text"].strip():
            raise ValueError("Source segments or reference changed")
        for field, digest_field in (("source_text", "source_sha256"), ("reference_text", "reference_sha256")):
            if hashlib.sha256(row[field].encode("utf-8")).hexdigest() != row[digest_field]:
                raise ValueError("Source/reference checksum mismatch")
    actual = hashlib.sha256(_json(_identity(items)).encode("utf-8")).hexdigest()
    if actual != metadata["selection_sha256"]:
        raise ValueError("Cohort identity checksum mismatch")
    return bundle


def save_benchmark_bundle(bundle, path, *, overwrite=False):
    """Atomically save one gzip JSONL file: config, dataset, exclusions, checksum."""
    validate_bundle(bundle)
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    os.close(fd)
    digest = hashlib.sha256()
    try:
        with gzip.open(temporary, "wt", encoding="utf-8", newline="\n") as stream:
            for entry in ({"kind": "metadata", "value": bundle["metadata"]},):
                line = _json(entry) + "\n"; digest.update(line.encode("utf-8")); stream.write(line)
            for item in bundle["items"]:
                line = _json({"kind": "item", "value": item}) + "\n"
                digest.update(line.encode("utf-8")); stream.write(line)
            stream.write(_json({"kind": "checksum", "sha256": digest.hexdigest()}) + "\n")
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"path": str(target.resolve()), "bytes": target.stat().st_size,
            "payload_sha256": digest.hexdigest(), "records": len(bundle["items"])}


def load_benchmark_bundle(path):
    """Reload the single reusable file and verify every saved payload byte."""
    digest = hashlib.sha256()
    metadata, items, complete = None, [], False
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        for line in stream:
            entry = json.loads(line)
            if complete:
                raise ValueError("Unexpected data after bundle checksum")
            if entry.get("kind") == "checksum":
                if entry.get("sha256") != digest.hexdigest():
                    raise ValueError("Bundle payload checksum mismatch")
                complete = True
                continue
            digest.update(line.encode("utf-8"))
            if entry.get("kind") == "metadata" and metadata is None and not items:
                metadata = entry["value"]
            elif entry.get("kind") == "item" and metadata is not None:
                items.append(entry["value"])
            else:
                raise ValueError("Unexpected bundle entry order")
    if not complete or metadata is None:
        raise ValueError("Incomplete benchmark bundle")
    return validate_bundle({"metadata": metadata, "items": items})


def generation_input(item):
    """The shared S1/S3 source adapter intentionally contains no reference text."""
    return {"id": f"{item['split']}/{item['source_index']}", "split": item["split"],
            "source_index": item["source_index"], "doi": item["doi"],
            "source_sha256": item["source_sha256"], "transcript": item["source_text"],
            "transcript_segments": {"text": list(item["segment_texts"]),
                                    "start": list(item["segment_starts_seconds"]),
                                    "end": list(item["segment_ends_seconds"])}}


def evaluation_target(item):
    return {"id": f"{item['split']}/{item['source_index']}",
            "reference_text": item["reference_text"], "reference_sha256": item["reference_sha256"]}
