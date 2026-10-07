"""Regression gates for honest local dataset qualification evidence."""

from collections import namedtuple
import hashlib
import json
from pathlib import Path

import pytest

from experiments.scripts import dataset_freeze_evidence as evidence


def test_content_identity_changes_for_edits_and_renames(tmp_path: Path):
    source = tmp_path / "source.py"
    source.write_text("first", encoding="utf-8")
    before = evidence.content_hash([source], tmp_path)
    source.write_text("second", encoding="utf-8")
    assert evidence.content_hash([source], tmp_path) != before
    before = evidence.content_hash([source], tmp_path)
    renamed = source.rename(tmp_path / "renamed.py")
    assert evidence.content_hash([renamed], tmp_path) != before


def test_peak_cannot_consume_reserved_space(tmp_path, monkeypatch):
    usage = namedtuple("Usage", "total used free")
    gib = 1024**3
    monkeypatch.setattr(evidence.shutil, "disk_usage", lambda _: usage(200*gib, 95*gib, 105*gib))
    assert evidence.disk_preflight([tmp_path], 5*gib)["disk_gate_passed"]
    blocked = evidence.disk_preflight([tmp_path], 6*gib)
    assert not blocked["disk_gate_passed"]
    assert blocked["disk"][0]["remaining_after_peak_bytes"] == 99*gib


def test_full_audio_decode_reads_payload(tmp_path):
    import wave

    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 1600)
    decoded = evidence.decode_audio(path)
    assert decoded["frames"] == 1600
    assert decoded["duration_sec"] == 0.1
    # A readable header plus partial samples must never count as a full decode.
    path.write_bytes(path.read_bytes()[:1600])
    with pytest.raises((ValueError, RuntimeError)):
        evidence.decode_audio(path)


def test_provenance_binds_config_and_dependency_contents(tmp_path):
    scripts = tmp_path / "experiments/scripts"
    scripts.mkdir(parents=True)
    driver = scripts / "driver.py"
    driver.write_text("pass", encoding="utf-8")
    config = tmp_path / "experiments/registry/datasets/example_d2.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("dataset_id: example", encoding="utf-8")
    lock = tmp_path / "requirements.lock.txt"
    lock.write_text("example==1", encoding="utf-8")
    first = evidence.provenance(tmp_path, driver, "example")
    config.write_text("dataset_id: example\nrevision: 2", encoding="utf-8")
    second = evidence.provenance(tmp_path, driver, "example")
    assert second["config_sha256"] != first["config_sha256"]
    assert second["source_sha256"] == first["source_sha256"]
    lock.write_text("example==2", encoding="utf-8")
    assert evidence.provenance(tmp_path, driver, "example")["dependency_state_sha256"] != second["dependency_state_sha256"]


def test_upstream_identity_binds_receipts_and_rejects_stale_payload(tmp_path):
    namespace = tmp_path / "official/full"
    namespace.mkdir(parents=True)
    for name in ("environment.profile", "environment.preflight_receipt"):
        payload = namespace / f"{name}.json"
        payload.write_text('{"records": [{"status": "passed"}]}', encoding="utf-8")
        receipt = {"artifact_id": name, "payload_path": payload.relative_to(tmp_path).as_posix(),
                   "sha256": hashlib.sha256(payload.read_bytes()).hexdigest()}
        (namespace / f"{name}.receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    before = evidence.upstream_evidence_hash(tmp_path, "00b_dataset_feasibility")
    path = namespace / "environment.profile.receipt.json"
    receipt = json.loads(path.read_text())
    receipt["run_id"] = "changed"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    assert evidence.upstream_evidence_hash(tmp_path, "00b_dataset_feasibility") != before
    (namespace / "environment.profile.json").write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        evidence.upstream_evidence_hash(tmp_path, "00b_dataset_feasibility")
