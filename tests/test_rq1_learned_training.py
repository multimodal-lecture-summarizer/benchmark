"""Locked-split and tensor provenance checks for learned RQ1 training."""

import json
from pathlib import Path

import pytest
import torch
from torch import nn

from benchmarks.models.chaptering import BaseChapteringModel, ChapteringOutput
from experiments.scripts import rq1_train_learned as trainer
from experiments.scripts import rq1_learned_features as feature_extractor
from experiments.scripts.benchmark_artifacts import sha256_file


@pytest.fixture
def tensor_cohort(tmp_path, monkeypatch):
    feature_dir = tmp_path / "features"
    feature_dir.mkdir()
    split_path = tmp_path / "split.json"
    split_path.write_text("[]", encoding="utf-8")
    rows = []
    for i in range(12):
        uid = f"dev-{i:02d}"
        split = "train" if i < 8 else "validation"
        rows.append({"unit_id": uid, "split": split, "course_id": f"course-{i}",
                     "lecturer_ids": [f"speaker-{i}"], "duration_sec": 12.0,
                     "media_sha256": f"media-{i}", "transcript_file_sha256": f"transcript-{i}",
                     "source_feature_file_sha256": None})
        data = {"unit_id": uid, "split": split,
                "timestamps": torch.arange(1, 12, 2, dtype=torch.float32),
                "text_features": torch.rand(6, 384),
                "visual_features": torch.rand(6, 384),
                "ocr_features": torch.rand(6, 384),
                "acoustic_features": torch.rand(6, 32)}
        tensor_path = feature_dir / f"{uid}.pt"
        torch.save(data, tensor_path)
        receipt = {"unit_id": uid, "split": split, "media_sha256": f"media-{i}",
                   "transcript_file_sha256": f"transcript-{i}",
                   "source_feature_file_sha256": None,
                   "split_sha256": sha256_file(split_path),
                   "tensor_sha256": sha256_file(tensor_path),
                   "extractor_sha256": sha256_file(
                       trainer.REPO / "experiments/scripts/rq1_learned_features.py"),
                   "text_model": trainer.TEXT_MODEL, "text_revision": trainer.TEXT_REVISION,
                   "visual_model": trainer.VISUAL_MODEL, "visual_revision": trainer.VISUAL_REVISION,
                   "ocr_model": "PaddleOCR ch_PP-OCRv4 confidence>=0.6",
                   "ocr_weight_sha256": {
                       f"{stage}/{name}": "fixture-hash"
                       for stage in ("det", "rec", "cls")
                       for name in ("inference.pdmodel", "inference.pdiparams")},
                   "frame_sampling": "1fps fallback; same frames for DINOv2 and OCR",
                   "audio": "FFmpeg mono 16kHz; 32-band log-mel mean per 2s",
                   "paddleocr_version": "fixture", "ocr_compute": "cpu",
                   "visual_compute": "cpu", "visual_batch_size": 8,
                   "dependencies": {"fixture": "1"}}
        (feature_dir / f"{uid}.receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    monkeypatch.setattr(trainer, "development_sources", lambda: rows)
    monkeypatch.setattr(trainer, "published_development_targets",
                        lambda: {row["unit_id"]: [5.0] for row in rows})
    monkeypatch.setattr(trainer, "SPLIT", split_path)
    return feature_dir


def test_only_eight_train_and_four_validation_tensors_are_loaded(tensor_cohort):
    train, validation, fingerprint = trainer.load_units(tensor_cohort)
    assert len(train) == 8 and len(validation) == 4
    assert all(unit["row"]["split"] == "train" for unit in train)
    assert all(unit["row"]["split"] == "validation" for unit in validation)
    assert all(unit["data"]["targets"].sum().item() == 1 for unit in train + validation)
    assert "sealed-test" not in json.dumps([unit["row"] for unit in train + validation])
    assert len(fingerprint) == 64


def test_changed_tensor_is_rejected(tensor_cohort):
    (tensor_cohort / "dev-00.pt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="tensor provenance mismatch"):
        trainer.load_units(tensor_cohort)


def test_frozen_windows_path_rebases_to_identical_repo_relative_file(tmp_path, monkeypatch):
    target = tmp_path / "experiments" / "datasets" / "lecture.mp4"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"frozen fixture")
    monkeypatch.setattr(feature_extractor, "REPO", tmp_path)
    assert feature_extractor._local_source_path(
        r"C:\old\repo\experiments\datasets\lecture.mp4") == target


def test_one_epoch_train_uses_real_text_model(tensor_cohort):
    train, validation, _ = trainer.load_units(tensor_cohort)
    model, state, loss, epoch = trainer.train_one(
        "C1", 42, train, validation, "cpu", epochs=1, patience=1)
    assert model.__class__.__name__ == "C1_TextOnlyChapterer"
    assert state and epoch == 1 and 0 <= loss < float("inf")


def test_prediction_batch_has_no_targets(tensor_cohort):
    _, validation, _ = trainer.load_units(tensor_cohort)
    batch = trainer._batch(validation[0]["data"], 0, 3, "cpu", "C5",
                           include_targets=False)
    assert batch.targets is None


def test_smoke_writes_train_only_checkpoint_provenance_and_validation_scores(
    tensor_cohort, tmp_path, monkeypatch
):
    class TinyChapterer(BaseChapteringModel):
        seen_target_flags = []

        def __init__(self):
            super().__init__()
            self.head = nn.Linear(384, 1)

        def forward(self, batch, threshold=0.4):
            self.seen_target_flags.append(batch.targets is not None)
            logits = self.head(batch.text_features).squeeze(-1)
            probabilities = torch.sigmoid(logits)
            return ChapteringOutput(
                logits=logits, probabilities=probabilities,
                loss=(self.compute_loss(logits, batch.targets, batch.mask)
                      if batch.targets is not None else None),
                predicted_boundaries=self.extract_boundaries(
                    probabilities, batch.timestamps, batch.mask, threshold))

    monkeypatch.setattr(trainer, "_factory", lambda candidate: TinyChapterer)
    interrupted = tmp_path / "training" / "smoke" / "C1.seed42.pt"
    interrupted.parent.mkdir(parents=True)
    interrupted.write_bytes(b"incomplete checkpoint without provenance")
    result = trainer.run(tensor_cohort, tmp_path / "training", device="cpu",
                         smoke=True, preload_features=True)
    repeated = trainer.run(tensor_cohort, tmp_path / "training", device="cpu",
                           smoke=True, preload_features=True)
    assert repeated == result
    assert False in TinyChapterer.seen_target_flags
    (tmp_path / "training" / "smoke" / "selected.json").unlink()
    resumed = trainer.run(tensor_cohort, tmp_path / "training", device="cpu",
                          smoke=True, preload_features=True)
    assert resumed == result
    assert set(result["selected"]) == {"C1", "C2", "C3", "C4", "C5", "C6"}
    assert result["final_test_accessed"] is False
    output = tmp_path / "training" / "smoke"
    scores = json.loads((output / "validation_scores.json").read_text(encoding="utf-8"))
    assert len(scores) == 24
    assert {row["unit_id"] for row in scores} == {f"dev-{i:02d}" for i in range(8, 12)}
    provenance = json.loads((output / "C5.seed42.provenance.json").read_text(encoding="utf-8"))
    assert provenance["train_unit_ids"] == [f"dev-{i:02d}" for i in range(8)]
    assert provenance["validation_unit_ids"] == [f"dev-{i:02d}" for i in range(8, 12)]
    assert provenance["candidate"] == "C5_cross_attention"
    assert provenance["checkpoint_sha256"] == sha256_file(output / "C5.seed42.pt")
    assert provenance["training_config_sha256"] == sha256_file(output / "configuration.json")
