"""Focused tests for full Arrow metadata qualification and bounded audio access."""

import hashlib
import io
import json

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
import pytest
import soundfile as sf

from experiments.scripts.asr_full_corpus import (
    decode_selected, freeze_evaluation_media, inventory, write_diagnostic,
)
from experiments.scripts.prepare_asr_full_corpus import _diagnostic_metadata_screen_complete


def _fixture(tmp_path, *, marker="ignore_time_segment_in_scoring"):
    rows_by_split = {
        "train": [{"id": "Train-0.0-0.1-<x>", "text": "training words",
                   "speaker_id": "train_speaker", "file": "train.sph"}],
        "validation": [{"id": "Valid-0.0-0.1-<x>", "text": "spoken words",
                        "speaker_id": "valid_speaker", "file": "valid.sph"},
                       {"id": "Valid-0.1-0.2-<x>", "text": marker,
                        "speaker_id": "valid_speaker", "file": "valid.sph"}],
        "test": [{"id": "Test-0.0-0.1-<x>", "text": "held words",
                  "speaker_id": "test_speaker", "file": "test.sph"}],
    }
    buffer = io.BytesIO()
    stereo = np.stack([np.ones(800) * 0.25, np.ones(800) * 0.75], axis=1)
    sf.write(buffer, stereo, 8000, format="WAV", subtype="PCM_16")
    for split, rows in rows_by_split.items():
        directory = tmp_path / split
        directory.mkdir()
        for row in rows:
            row["audio"] = {"bytes": buffer.getvalue(), "path": None}
        table = pa.Table.from_pylist(rows)
        with (directory / "data.arrow").open("wb") as stream:
            with ipc.new_stream(stream, table.schema) as writer:
                writer.write_table(table)
        (directory / "state.json").write_text(
            json.dumps({"_data_files": [{"filename": "data.arrow"}]}), encoding="utf-8")
    return {"train": (1, 1, 0), "validation": (2, 1, 1), "test": (1, 1, 0)}


def test_full_inventory_reconciles_and_preserves_native_split(tmp_path):
    expected = _fixture(tmp_path)
    first = inventory(tmp_path, expected)
    second = inventory(tmp_path, expected)
    assert first == second
    assert len(first["records"]) == 4
    test = next(row for row in first["records"] if row["original_split"] == "test")
    assert test["split"] == "final_test"
    assert test["arrow_path"] == "test/data.arrow"
    ignored = next(row for row in first["records"] if not row["asr_eligible"])
    assert ignored["exclusion_reason"] == "ignore_marker"
    assert ignored["reference_text"] is None
    assert len(first["shards"]) == 3
    assert all(len(shard["sha256"]) == 64 for shard in first["shards"])


def test_receipt_requires_complete_counts_and_is_diagnostic(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    expected = _fixture(root)
    destination = tmp_path / "qualified"
    with pytest.raises(ValueError, match="count mismatch"):
        write_diagnostic(root, destination, {**expected, "test": (2, 2, 0)})
    assert not destination.exists()
    receipt = write_diagnostic(root, destination, expected)
    assert receipt["row_count"] == 4
    assert receipt["asr_eligible_count"] == 3
    assert receipt["scientific_selection_eligible"] is False
    assert receipt["media_validation"] == "selected_rows_only"
    assert (destination / "receipt.json").is_file()
    assert len((destination / "cohort.jsonl").read_text().splitlines()) == 4


def test_selected_row_decodes_canonical_audio_and_hashes(tmp_path):
    expected = _fixture(tmp_path)
    records = inventory(tmp_path, expected)["records"]
    selected = next(row for row in records if row["original_split"] == "validation"
                    and row["asr_eligible"])
    evidence, audio = decode_selected(tmp_path, selected)
    assert evidence["source_rate_hz"] == 8000
    assert evidence["sample_rate_hz"] == 16000
    assert evidence["channels"] == 1
    assert evidence["frames"] == 1600
    assert audio.dtype == np.dtype("float32")
    assert np.allclose(audio[30:-30], .5, atol=.002)
    assert evidence["canonical_audio_sha256"] == hashlib.sha256(audio.tobytes()).hexdigest()
    assert evidence["reference_sha256"] == hashlib.sha256(b"spoken words").hexdigest()
    ignored = next(row for row in records if not row["asr_eligible"])
    with pytest.raises(ValueError, match="not ASR eligible"):
        decode_selected(tmp_path, ignored)
    with pytest.raises(ValueError, match="locator changed"):
        decode_selected(tmp_path, dict(selected, reference_text="changed"))
    with pytest.raises(ValueError, match="locator changed"):
        decode_selected(tmp_path, dict(selected, talk_id="forged-talk"))


def test_media_freeze_verifies_every_eligible_evaluation_row(tmp_path):
    expected_native = _fixture(tmp_path)
    metadata = tmp_path / "metadata"
    write_diagnostic(tmp_path, metadata, expected_native)
    expected_scored = {"train": (1, 1, 0), "validation": (2, 1, 1), "test": (1, 1, 0)}
    destination = tmp_path / "media"
    receipt = freeze_evaluation_media(tmp_path, metadata, destination, expected_scored)
    assert receipt["counts"] == {"validation": 1, "final_test": 1}
    assert receipt["row_count"] == 2
    assert receipt["train_waveforms_decoded"] is False
    rows = [json.loads(line) for line in (destination / "evaluation_units.jsonl").read_text().splitlines()]
    assert all(len(row["decoded_audio_sha256"]) == 64 for row in rows)
    assert all(len(row["reference_sha256"]) == 64 for row in rows)


def test_media_freeze_rejects_changed_metadata_cohort(tmp_path):
    expected = _fixture(tmp_path)
    metadata = tmp_path / "metadata"
    write_diagnostic(tmp_path, metadata, expected)
    with (metadata / "cohort.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    with pytest.raises(ValueError, match="metadata cohort changed"):
        freeze_evaluation_media(tmp_path, metadata, tmp_path / "media", expected)


def test_diagnostic_gate_accepts_bounded_metadata_screen_with_unverified_train_audio():
    metadata_receipt = {"cohort_sha256": "metadata-hash",
                        "dataset_id": "tedlium3", "row_count": 270323,
                        "counts": {"train": {"rows": 268263}, "validation": {"rows": 591},
                                   "test": {"rows": 1469}},
                        "train_evaluation_identity_overlap": {key: [] for key in (
                            "speaker_id", "talk_id", "source_id")},
                        "validation_test_identity_overlap": {key: [] for key in (
                            "speaker_id", "talk_id", "source_id")}}
    media_receipt = {"cohort_sha256": "media-hash", "row_count": 1662,
                     "status": "complete", "media_validation": "all_evaluation_waveforms_decoded_and_hashed",
                     "counts": {"validation": 507, "final_test": 1155}}
    assert _diagnostic_metadata_screen_complete(metadata_receipt, media_receipt)
    assert not _diagnostic_metadata_screen_complete(
        {**metadata_receipt, "train_evaluation_identity_overlap": {"source_id": ["same"]}},
        media_receipt)
    incomplete_receipt = {key: value for key, value in metadata_receipt.items()
                          if key != "train_evaluation_identity_overlap"}
    assert not _diagnostic_metadata_screen_complete(incomplete_receipt, media_receipt)
