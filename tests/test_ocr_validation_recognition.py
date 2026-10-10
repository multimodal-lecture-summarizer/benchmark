import json

import pytest

from experiments.scripts.ocr_validation_recognition import (
    NORMALIZER,
    SOURCE_SHA256,
    edit_distance,
    normalize,
    read_completed,
)
from experiments.scripts.summarize_ocr_validation import group_ids, load, score


def test_cer_normalization_keeps_digits_and_punctuation():
    reference = normalize("  Café  2.0! ")
    prediction = normalize("CAFE 2.0?")
    assert reference == "café 2.0!"
    assert edit_distance(reference, prediction) == 2
    assert edit_distance(reference, "") == len(reference)


def test_resume_rejects_other_dataset_identity(tmp_path):
    checkpoint = tmp_path / "predictions.jsonl"
    crop_id = "Crops/val/11/1/1.png"
    cohort = [(crop_id, tmp_path / "1.png", "word")]
    row = {
        "crop_id": crop_id,
        "engine": "easyocr",
        "engine_version": "1.7.2",
        "source_sha256": "different",
        "normalizer": NORMALIZER,
        "split": "val",
        "reference": "word",
        "prediction": "word",
        "reference_chars": 4,
        "edit_distance": 0,
        "error": None,
    }
    checkpoint.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        read_completed(checkpoint, "easyocr", "1.7.2", cohort)
    row["source_sha256"] = SOURCE_SHA256
    checkpoint.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert list(read_completed(checkpoint, "easyocr", "1.7.2", cohort)) == [crop_id]
    with pytest.raises(ValueError, match="identity mismatch"):
        read_completed(checkpoint, "easyocr", "1.7.3", cohort)
    row["edit_distance"] = 2
    checkpoint.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="score mismatch"):
        read_completed(checkpoint, "easyocr", "1.7.2", cohort)
    row["edit_distance"] = 0
    row["reference"] = "other"
    checkpoint.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reference mismatch"):
        read_completed(checkpoint, "easyocr", "1.7.2", cohort)


def test_summary_uses_source_video_and_counts_empty_prediction():
    assert group_ids("Crops/val/11/7/24.png") == ("11", "11/7")
    result = score([
        {"reference_chars": 4, "edit_distance": 0, "prediction": "word", "error": None},
        {"reference_chars": 2, "edit_distance": 2, "prediction": "", "error": "failed"},
    ])
    assert result["micro_cer"] == pytest.approx(2 / 6)
    assert result["exact_word_rate"] == 0.5
    assert result["empty_predictions"] == result["failures"] == 1


def test_summary_rejects_corrupt_saved_score(tmp_path):
    crop_id = "Crops/val/11/1/1.png"
    row = {
        "crop_id": crop_id,
        "engine": "easyocr_cpu",
        "engine_version": "1.7.2",
        "source_sha256": SOURCE_SHA256,
        "normalizer": NORMALIZER,
        "split": "val",
        "reference": "word",
        "prediction": "ward",
        "reference_chars": 4,
        "edit_distance": 1,
        "error": None,
    }
    path = tmp_path / "easyocr_cpu_full.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert list(load("easyocr_cpu", tmp_path, {crop_id: "word"})) == [crop_id]
    row["edit_distance"] = 0
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="score mismatch"):
        load("easyocr_cpu", tmp_path, {crop_id: "word"})
