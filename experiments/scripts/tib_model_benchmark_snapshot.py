"""Inspect local released Parquet shards only; no network or dataset loader."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
EXPECTED_COUNTS = {"train": 7282, "valid": 910, "test": 911}
STRING_FIELDS = ("doi", "title", "url", "license", "abstract", "transcript")


def digest_stream(handle) -> str:
    digest = hashlib.sha256()
    handle.seek(0)
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    handle.seek(0)
    return digest.hexdigest()


def digest_file(path: Path) -> str:
    with path.open("rb") as handle:
        return digest_stream(handle)


def _segment_schema_valid(dtype, pa) -> bool:
    """Allow the declared sequence as struct-of-arrays or list-of-struct.

    This validates shape only, not row-level timing/order/content usability.
    """
    is_list = lambda value: pa.types.is_list(value) or pa.types.is_large_list(value)
    arrays = pa.types.is_struct(dtype)
    element = dtype if arrays else dtype.value_type if is_list(dtype) else None
    if element is None or not pa.types.is_struct(element):
        return False
    for name in ("text", "start", "end"):
        if name not in [field.name for field in element]:
            return False
        field_type = element.field(name).type
        if arrays:
            if not is_list(field_type):
                return False
            field_type = field_type.value_type
        if name == "text":
            if not (pa.types.is_string(field_type) or pa.types.is_large_string(field_type)):
                return False
        elif not (pa.types.is_floating(field_type) or pa.types.is_integer(field_type)):
            return False
    return True


def _file_identity(stat) -> tuple:
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _inspect_open_shard(handle, path: Path, split: str) -> tuple[dict, list[dict]]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(handle)
    schema = parquet.schema_arrow
    errors = []
    for name in STRING_FIELDS:
        if name not in schema.names:
            errors.append(f"missing:{name}")
        elif not (pa.types.is_string(schema.field(name).type)
                  or pa.types.is_large_string(schema.field(name).type)):
            errors.append(f"not_string:{name}")
    if "transcript_segments" not in schema.names:
        errors.append("missing:transcript_segments")
    elif not _segment_schema_valid(schema.field("transcript_segments").type, pa):
        errors.append("invalid_nested_schema:transcript_segments")
    rights = []
    if not errors:
        index = 0
        for batch in parquet.iter_batches(columns=["doi", "url", "license"], batch_size=512):
            for row in batch.to_pylist():
                rights.append({
                    "native_file": path.name, "file_row": index, "split": split,
                    "doi": row["doi"], "source_url": row["url"],
                    "released_license_raw": row["license"],
                    "text_use_status": "HOLD", "abstract_use_status": "HOLD",
                    "media_use_status": "not_reviewed_outside_primary",
                    "reason": "released_label_is_evidence_not_reviewed_permission",
                })
                index += 1
    return {
        "path": str(path.resolve()), "filename": path.name,
        "num_rows": parquet.metadata.num_rows,
        "schema": str(schema), "schema_errors": errors,
    }, rights


def inspect_shard(path: Path, split: str) -> tuple[dict, list[dict]]:
    """Bind footer/ledger and checksum to one stable local file version."""
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        first_hash = digest_stream(handle)
        shard, rights = _inspect_open_shard(handle, path, split)
        final_hash = digest_stream(handle)
        after = os.fstat(handle.fileno())
        if (first_hash != final_hash or _file_identity(before) != _file_identity(after)
                or _file_identity(after) != _file_identity(path.stat())):
            raise ValueError(f"Shard changed during audit: {path}")
    shard.update(bytes=after.st_size, sha256=final_hash)
    return shard, rights


def inspect_snapshot(snapshot: Path) -> tuple[dict, dict]:
    """Produce an unsealed evidence receipt; missing evidence never passes G1."""
    if not snapshot.is_dir() or snapshot.name != REVISION:
        raise ValueError(f"Expected local snapshot directory named {REVISION}")
    card = snapshot / "README.md"
    manifest = {
        "schema_version": 1, "study_id": "tib-text-model-benchmark-v1",
        "dataset": DATASET, "requested_revision": REVISION,
        "revision_evidence": "local_directory_name_only_not_remote_verified",
        "state": "audit_unsealed", "g1_status": "HOLD",
        "expected_counts": dict(EXPECTED_COUNTS), "observed_counts": {},
        "source_bytes_modified": False, "network_access": False,
        "canonicalization_executed": False, "selected_ids": [],
        "card": None, "splits": {}, "blocking_reasons": [],
    }
    if card.is_file():
        manifest["card"] = {"path": str(card.resolve()), "sha256": digest_file(card),
                            "bytes": card.stat().st_size}
    else:
        manifest["blocking_reasons"].append("missing_pinned_card")
    rights = {"schema_version": 1, "state": "unreviewed", "records": [],
              "dataset_text_use_status": "HOLD", "dataset_abstract_use_status": "HOLD"}
    for split, expected in EXPECTED_COUNTS.items():
        paths = sorted((snapshot / "data").glob(f"{split}-*.parquet"))
        shards = []
        for path in paths:
            shard, rows = inspect_shard(path, split)
            shards.append(shard)
            rights["records"].extend(rows)
        observed = sum(row["num_rows"] for row in shards) if shards else None
        manifest["observed_counts"][split] = observed
        manifest["splits"][split] = {"files": shards, "expected_rows": expected,
                                    "observed_rows": observed}
        if observed != expected:
            manifest["blocking_reasons"].append(f"unverified_split_count:{split}")
        if any(row["schema_errors"] for row in shards):
            manifest["blocking_reasons"].append(f"invalid_schema:{split}")
    manifest["blocking_reasons"].extend([
        "remote_revision_and_file_hash_binding_unverified",
        "transcript_and_abstract_reuse_rights_unreviewed",
        "paper_source_accounting_pending",
    ])
    rights["observed_record_count"] = len(rights["records"])
    return manifest, rights
