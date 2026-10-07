"""Figure appends must preserve provenance and refuse corrupted input bundles."""

import hashlib
import json
import uuid
from pathlib import Path

import pytest

from experiments.scripts.artifact_enrichment import append_figure_manifest, load_validated_manifest
from experiments.scripts.benchmark_artifacts import (
    RunnerContext, sha256_file, write_json_artifact, write_run_manifest,
)


def bundle(tmp_path):
    context = RunnerContext("full", "official", "real", tmp_path,
                            "00c_dataset_eda_and_freeze", str(uuid.uuid4()),
                            *[hashlib.sha256(v.encode()).hexdigest() for v in ("code", "config", "inputs")])
    fig = tmp_path / "official/full/figures/one.svg"
    fig.parent.mkdir(parents=True)
    fig.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    row = {"dataset_id": "fixture", "figure_id": "one", "path": fig.relative_to(tmp_path).as_posix(),
           "sha256": sha256_file(fig)}
    write_json_artifact(context, "dataset.figure_manifest", [row])
    for artifact in ("dataset.unit_profile", "dataset.statistics"):
        write_json_artifact(context, artifact, [{"dataset_id": "fixture", "n": 1}])
    write_run_manifest(context)
    return context, row


def extra_row(tmp_path):
    fig = tmp_path / "official/full/figures/two.svg"
    fig.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>two</text></svg>')
    fig.with_suffix(".json").write_text(json.dumps({"measure": "test-fixture", "n": 1}))
    return {"dataset_id": "fixture", "figure_id": "two", "path": fig.relative_to(tmp_path).as_posix(),
            "sha256": sha256_file(fig)}


def test_append_updates_receipt_but_preserves_original_run(tmp_path):
    context, row = bundle(tmp_path)
    manifest = context.namespace_root / "runs/00c_dataset_eda_and_freeze.run.json"
    before = manifest.read_bytes()
    append_figure_manifest(tmp_path, [row, extra_row(tmp_path)], tool_path=Path(__file__))
    assert len(load_validated_manifest(tmp_path)["records"]) == 2
    receipt = json.loads((context.namespace_root / "dataset.figure_manifest.receipt.json").read_text())
    assert receipt["record_count"] == receipt["denominator"] == 2
    assert receipt["run_id"] == context.run_id
    assert receipt["enrichments"][0]["tool_sha256"] == sha256_file(Path(__file__))
    assert manifest.read_bytes() == before


def test_append_refuses_stale_payload_instead_of_reblessing(tmp_path):
    context, row = bundle(tmp_path)
    payload = context.namespace_root / "payloads/dataset.figure_manifest.json"
    payload.write_text(payload.read_text() + " ")
    before = payload.read_bytes()
    with pytest.raises(ValueError, match="checksum mismatch"):
        append_figure_manifest(tmp_path, [row, extra_row(tmp_path)], tool_path=Path(__file__))
    assert payload.read_bytes() == before


def test_appended_history_detects_dependency_tamper(tmp_path):
    context, row = bundle(tmp_path)
    append_figure_manifest(tmp_path, [row, extra_row(tmp_path)], tool_path=Path(__file__))
    (tmp_path / "official/full/figures/two.svg").write_text("tampered")
    with pytest.raises(ValueError, match="enrichment input checksum mismatch"):
        load_validated_manifest(tmp_path)


def test_append_rejects_replacing_existing_figure(tmp_path):
    _, row = bundle(tmp_path)
    with pytest.raises(ValueError, match="append without changing"):
        append_figure_manifest(tmp_path, [extra_row(tmp_path), row], tool_path=Path(__file__))
