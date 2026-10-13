"""Real file contracts for guarded OCR resume, without inference dependencies."""
import json

import pytest

from experiments.scripts.ocr_comparison_runtime import (
    bind_identity, engine_lock, export_failures, file_sha256, verify_models,
)


def test_identity_resume_requires_same_weights_and_environment(tmp_path):
    identity = {"model_sha256": {"weight": "abc"}, "python": "3.11", "device": "cpu"}
    path = bind_identity(tmp_path, "easyocr_cpu", identity)
    before = path.read_bytes()
    assert bind_identity(tmp_path, "easyocr_cpu", identity) == path
    assert path.read_bytes() == before
    for changed in ({**identity, "python": "3.12"}, {**identity, "model_sha256": {"weight": "changed"}}):
        with pytest.raises(ValueError, match="identity mismatch"):
            bind_identity(tmp_path, "easyocr_cpu", changed)
    assert path.read_bytes() == before


def test_existing_predictions_cannot_acquire_new_receipt(tmp_path):
    predictions = tmp_path / "paddleocr_full.jsonl"
    predictions.write_text("existing evidence\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no run identity"):
        bind_identity(tmp_path, "paddleocr", {})
    assert not (tmp_path / "paddleocr_full.identity.json").exists()
    assert predictions.read_text(encoding="utf-8") == "existing evidence\n"


def test_model_hash_rejects_different_actual_weights(tmp_path):
    folder = tmp_path / "easyocr"
    folder.mkdir()
    (folder / "english_g2.pth").write_bytes(b"different checkpoint")
    with pytest.raises(ValueError, match="model SHA256 mismatch"):
        verify_models("easyocr_cpu", tmp_path)


def test_failure_export_preserves_failed_and_empty_predictions(tmp_path):
    rows = [
        {"crop_id": "one", "prediction": "", "error": "RuntimeError: failed"},
        {"crop_id": "two", "prediction": "", "error": None},
    ]
    prediction_path = tmp_path / "easyocr_cpu_full.jsonl"
    prediction_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    summary_path = tmp_path / "easyocr_cpu_full.summary.json"
    summary_path.write_text('{"failures": 1}', encoding="utf-8")
    export_failures(tmp_path, "easyocr_cpu")
    ledger = tmp_path / "easyocr_cpu_full.failures.jsonl"
    assert [json.loads(line) for line in ledger.read_text().splitlines()] == rows[:1]
    artifacts = json.loads((tmp_path / "easyocr_cpu_full.artifacts.json").read_text())
    assert artifacts[prediction_path.name] == file_sha256(prediction_path)
    assert artifacts[ledger.name] == file_sha256(ledger)


def test_lock_refuses_second_session_without_removing_owner_lock(tmp_path):
    with engine_lock(tmp_path, "easyocr_cpu") as lock:
        metadata = json.loads(lock.read_text())
        assert metadata["pid"] > 0
        with pytest.raises(RuntimeError, match="Stop the old session first"):
            with engine_lock(tmp_path, "easyocr_cpu"):
                pytest.fail("second session acquired existing lock")
        assert lock.exists()
    assert not lock.exists()


def test_lock_releases_after_exception(tmp_path):
    with pytest.raises(ValueError, match="inference failed"):
        with engine_lock(tmp_path, "paddleocr"):
            raise ValueError("inference failed")
    assert not (tmp_path / "paddleocr.lock").exists()
    with engine_lock(tmp_path, "paddleocr") as lock:
        assert lock.exists()
