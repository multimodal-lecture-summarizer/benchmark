"""Exercise real temporary Parquet files, missing inputs and immutable CLI outputs."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from experiments.scripts.tib_model_benchmark_snapshot import (
    REVISION, inspect_shard, inspect_snapshot,
)
from experiments.scripts import tib_model_benchmark_snapshot as audit


def make_snapshot(tmp_path):
    root = tmp_path / REVISION
    root.mkdir()
    (root / "README.md").write_text("declared counts are not observed counts\n", encoding="utf-8")
    return root


def test_card_only_snapshot_never_invents_observed_rows_or_rights(tmp_path):
    snapshot = make_snapshot(tmp_path)
    manifest, rights = inspect_snapshot(snapshot)
    assert manifest["observed_counts"] == {"train": None, "valid": None, "test": None}
    assert manifest["g1_status"] == "HOLD"
    assert manifest["selected_ids"] == []
    assert manifest["canonicalization_executed"] is False
    assert manifest["card"]["sha256"] == hashlib.sha256((snapshot / "README.md").read_bytes()).hexdigest()
    assert rights["observed_record_count"] == 0
    assert rights["dataset_text_use_status"] == "HOLD"
    manifest["expected_counts"]["train"] = 1
    later, _ = inspect_snapshot(snapshot)
    assert later["expected_counts"]["train"] == 7282


def test_real_parquet_schema_row_count_license_and_checksum(tmp_path):
    snapshot = make_snapshot(tmp_path)
    (snapshot / "data").mkdir()
    path = snapshot / "data/train-00000.parquet"
    pq.write_table(pa.table({
        "doi": ["10.example/item"], "title": ["Talk"], "url": ["https://example.org/item"],
        "license": ["CC BY"], "abstract": ["An abstract"],
        "transcript": ["Canonical transcript differs from sidecar"],
        "transcript_segments": [{"text": ["Sidecar"], "start": [0.0], "end": [1.0]}],
    }), path)
    before = path.read_bytes()
    shard, rows = inspect_shard(path, "train")
    assert shard["num_rows"] == 1 and not shard["schema_errors"]
    assert shard["sha256"] == hashlib.sha256(before).hexdigest()
    assert rows[0]["released_license_raw"] == "CC BY"
    assert rows[0]["text_use_status"] == "HOLD"
    assert "transcript" not in rows[0] and "abstract" not in rows[0]
    manifest, rights = inspect_snapshot(snapshot)
    assert path.read_bytes() == before
    assert manifest["observed_counts"]["train"] == 1
    assert "unverified_split_count:train" in manifest["blocking_reasons"]
    assert rights["observed_record_count"] == 1


def test_wrong_schema_and_revision_fail_closed(tmp_path):
    snapshot = make_snapshot(tmp_path)
    (snapshot / "data").mkdir()
    path = snapshot / "data/test-00000.parquet"
    pq.write_table(pa.table({"transcript": [42]}), path)
    shard, rights = inspect_shard(path, "test")
    assert "not_string:transcript" in shard["schema_errors"]
    assert "missing:abstract" in shard["schema_errors"]
    assert rights == []
    with pytest.raises(ValueError, match="snapshot directory"):
        inspect_snapshot(tmp_path)


@pytest.mark.parametrize("segments,valid", [
    ([42], False),
    ([[{"text": "Sidecar"}]], False),
    ([[{"text": "Sidecar", "start": 0.0, "end": 1.0}]], True),
    ([{"text": ["Sidecar"], "start": [0.0], "end": [1.0]}], True),
])
def test_segment_shape_validation(tmp_path, segments, valid):
    path = tmp_path / "train-00000.parquet"
    pq.write_table(pa.table({"transcript_segments": segments}), path)
    shard, _ = inspect_shard(path, "train")
    assert ("invalid_nested_schema:transcript_segments" not in shard["schema_errors"]) is valid


def test_input_change_during_audit_fails_closed(tmp_path, monkeypatch):
    path = tmp_path / "train-00000.parquet"
    pq.write_table(pa.table({"transcript": ["canonical"]}), path)
    inspect_original = audit._inspect_open_shard

    def inspect_then_change(handle, current_path, split):
        result = inspect_original(handle, current_path, split)
        with current_path.open("ab") as output:
            output.write(b"changed")
        return result

    monkeypatch.setattr(audit, "_inspect_open_shard", inspect_then_change)
    with pytest.raises(ValueError, match="changed during audit"):
        inspect_shard(path, "train")


def test_cli_writes_pending_receipts_and_refuses_overwrite(tmp_path):
    snapshot = make_snapshot(tmp_path)
    output = tmp_path / "audit"
    command = [sys.executable, "-m", "experiments.scripts.tib_model_benchmark_audit",
               "--snapshot", str(snapshot), "--output", str(output)]
    cwd = Path(__file__).resolve().parents[1]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert run.returncode == 2
    manifest = json.loads((output / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["g1_status"] == "HOLD"
    before = (output / "dataset_manifest.json").read_bytes()
    receipt = json.loads((output / "audit_receipt.json").read_text(encoding="utf-8"))
    assert receipt["export_complete"] is True and receipt["state"] == "audit_unsealed"
    assert receipt["files"]["dataset_manifest.json"] == hashlib.sha256(before).hexdigest()
    again = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    assert again.returncode == 2 and "Output exists" in again.stderr
    assert (output / "dataset_manifest.json").read_bytes() == before


def test_cli_refuses_output_inside_source_snapshot(tmp_path):
    snapshot = make_snapshot(tmp_path)
    output = snapshot / "new-audit"
    run = subprocess.run(
        [sys.executable, "-m", "experiments.scripts.tib_model_benchmark_audit",
         "--snapshot", str(snapshot), "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
    )
    assert run.returncode == 2 and "immutable snapshot" in run.stderr
    assert not output.exists()
