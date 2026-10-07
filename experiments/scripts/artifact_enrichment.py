"""Append presentation evidence without inventing a new historical inference run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.scripts.benchmark_artifacts import (
    RunnerContext, read_json_artifact, sha256_file,
)


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def validate_enrichment(root: Path, receipt: dict[str, Any]) -> None:
    """Validate the append history as well as the final figure payload."""
    previous_output = None
    for event in receipt.get("enrichments", []):
        if previous_output and event["parent_payload_sha256"] != previous_output:
            raise ValueError("enrichment history is not contiguous")
        parent = _inside(root, event["parent_payload_path"])
        if sha256_file(parent) != event["parent_payload_sha256"]:
            raise ValueError("enrichment parent payload checksum mismatch")
        parent_receipt = _inside(root, event["parent_receipt_path"])
        if sha256_file(parent_receipt) != event["parent_receipt_sha256"]:
            raise ValueError("enrichment parent receipt checksum mismatch")
        prior = json.loads(parent_receipt.read_text(encoding="utf-8"))
        if prior["sha256"] != event["parent_payload_sha256"]:
            raise ValueError("enrichment parent receipt does not bind parent payload")
        for dependency in event["inputs"]:
            if sha256_file(_inside(root, dependency["path"])) != dependency["sha256"]:
                raise ValueError("enrichment input checksum mismatch")
        previous_output = event["output_sha256"]
    if previous_output and previous_output != receipt["sha256"]:
        raise ValueError("enrichment output checksum mismatch")


def load_validated_manifest(root: Path) -> dict[str, Any]:
    """Read an intact source bundle; stale historical receipts must be rebuilt."""
    namespace = root / "official" / "full"
    receipt = json.loads((namespace / "dataset.figure_manifest.receipt.json").read_text())
    context = RunnerContext(
        profile="full", run_namespace="official", status="real", artifact_root=root,
        notebook_id=receipt["producer_notebook_id"], run_id=receipt["run_id"],
        source_sha256=receipt["source_sha256"], config_sha256=receipt["config_sha256"],
        dependency_state_sha256=receipt["dependency_state_sha256"],
    )
    payload = read_json_artifact(context, "dataset.figure_manifest")
    for artifact in ("dataset.unit_profile", "dataset.statistics"):
        read_json_artifact(context, artifact)
    return payload


def append_figure_manifest(
    root: Path, records: list[dict[str, Any]], *, tool_path: Path,
) -> None:
    """Preserve original producer identity and record a verified append operation.

    The original payload/receipt are retained by content hash. Updating only a
    figure manifest must not reattribute the dataset freeze or ASR predictions.
    Readers fail closed if interrupted between the atomic payload/receipt writes.
    """
    root = root.resolve()
    existing = load_validated_manifest(root)
    before = existing["records"]
    if records[:len(before)] != before or len(records) <= len(before):
        raise ValueError("figure enrichment must append without changing existing records")
    ids = [(row["dataset_id"], row["figure_id"]) for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate figure identity")
    namespace = root / "official" / "full"
    payload_path = namespace / "payloads/dataset.figure_manifest.json"
    receipt_path = namespace / "dataset.figure_manifest.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    history = namespace / "enrichment_history"
    history.mkdir(parents=True, exist_ok=True)
    old_payload = history / f"{sha256_file(payload_path)}.payload.json"
    old_receipt = history / f"{sha256_file(receipt_path)}.receipt.json"
    old_payload.write_bytes(payload_path.read_bytes())
    old_receipt.write_bytes(receipt_path.read_bytes())
    inputs = []
    for path in [namespace / "payloads/dataset.unit_profile.json",
                 namespace / "payloads/dataset.statistics.json"]:
        inputs.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)})
    for index, row in enumerate(records):
        path = _inside(root, row["path"])
        if sha256_file(path) != row["sha256"]:
            raise ValueError("figure checksum mismatch before enrichment")
        inputs.append({"path": row["path"], "sha256": row["sha256"]})
        sidecar = path.with_suffix(".json")
        if index >= len(before) and not sidecar.is_file():
            raise ValueError("new figure requires a measurement/provenance sidecar")
        if sidecar.is_file():
            inputs.append({"path": sidecar.relative_to(root).as_posix(), "sha256": sha256_file(sidecar)})
    existing["records"] = records
    temporary = payload_path.with_suffix(".json.enrich.tmp")
    temporary.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    new_hash = sha256_file(temporary)
    event = {
        "operation": "append_figures", "recorded_at": datetime.now(timezone.utc).isoformat(),
        "tool": tool_path.name, "tool_sha256": sha256_file(tool_path),
        "helper_sha256": sha256_file(Path(__file__)),
        "parent_payload_path": old_payload.relative_to(root).as_posix(),
        "parent_payload_sha256": sha256_file(old_payload),
        "parent_receipt_path": old_receipt.relative_to(root).as_posix(),
        "parent_receipt_sha256": sha256_file(old_receipt),
        "inputs": inputs, "output_sha256": new_hash,
    }
    receipt.setdefault("enrichments", []).append(event)
    receipt.update(sha256=new_hash, record_count=len(records), denominator=len(records))
    temporary.replace(payload_path)
    receipt_tmp = receipt_path.with_suffix(".json.enrich.tmp")
    receipt_tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt_tmp.replace(receipt_path)
