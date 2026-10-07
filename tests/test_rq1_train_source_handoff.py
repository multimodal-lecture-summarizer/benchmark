"""Train handoff must bind the frozen eight without publishing held-out labels."""

import json
from pathlib import Path

import pytest

from experiments.scripts import rq1_train_source_handoff as handoff
from experiments.scripts.benchmark_artifacts import sha256_file


def _write(path: Path, value: dict | list) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def frozen_inputs(tmp_path, monkeypatch):
    split_path = tmp_path / "split.json"
    source_path = tmp_path / "source.json"
    materialized_path = tmp_path / "materialized.json"
    freeze_path = tmp_path / "freeze.json"
    split, source_units, receipts = [], [], []
    for index in range(20):
        uid = f"unit-{index:02d}"
        group = "train" if index < 8 else "validation" if index < 12 else "final_test"
        media = tmp_path / f"{uid}.mp4"
        media.write_bytes(uid.encode())
        media_sha = sha256_file(media)
        split.append({"video_id": uid, "split": group, "course_id": f"course-{index}",
                      "lecturer_ids": [f"lecturer-{index}"]})
        source_units.append({"unit": {"unit_id": uid, "dataset_id": "sample",
                                      "split": group, "course_id": f"course-{index}",
                                      "sha256": media_sha, "duration_sec": 100.0,
                                      "chapter_boundaries_sec": [30.0]},
                             "media": {"local_path": str(media), "sha256": media_sha}})
        if group != "final_test":
            transcript = tmp_path / f"{uid}-transcript.json"
            features = tmp_path / f"{uid}-features.json"
            _write(transcript, {"text": uid})
            _write(features, {"visual": uid})
            receipts.append({"unit_id": uid, "split": group, "media_sha256": media_sha,
                             "transcript_file": str(transcript),
                             "transcript_file_sha256": sha256_file(transcript),
                             "video_features_file": str(features),
                             "video_features_file_sha256": sha256_file(features)})
    _write(split_path, split)
    _write(source_path, {"split_sha256": sha256_file(split_path), "units": source_units})
    _write(materialized_path, {"status": "source_inputs_only_no_model_scoring",
                               "source_bundle_sha256": sha256_file(source_path), "units": receipts})
    _write(freeze_path, {"status": "D2_dataset_frozen",
                         "split_sha256": sha256_file(split_path),
                         "source_bundle_sha256": sha256_file(source_path)})
    for key, path in (("SPLIT", split_path), ("SOURCE", source_path),
                      ("MATERIALIZATION", materialized_path), ("FREEZE", freeze_path)):
        monkeypatch.setattr(handoff, key, path)
    return {"split": split_path, "source": source_path, "receipt": materialized_path,
            "freeze": freeze_path, "transcript": tmp_path / "unit-00-transcript.json"}


def test_handoff_contains_exact_train_only(frozen_inputs):
    result = handoff.build_handoff()
    assert result["train_unit_count"] == 8
    assert {unit["unit_id"] for unit in result["units"]} == {f"unit-{i:02d}" for i in range(8)}
    assert all(unit["chapter_boundaries_sec"] == [30.0] for unit in result["units"])
    assert "unit-08" not in json.dumps(result)
    assert "unit-12" not in json.dumps(result)
    assert result["status"] == "train_sources_bound_learned_tensors_pending"


def test_handoff_rejects_changed_train_payload(frozen_inputs):
    frozen_inputs["transcript"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="train transcript missing or changed"):
        handoff.build_handoff()


def test_handoff_rejects_changed_split(frozen_inputs):
    frozen_inputs["split"].write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="frozen split_sha256 changed"):
        handoff.build_handoff()
