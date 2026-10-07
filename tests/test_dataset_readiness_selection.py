"""Selection is immutable, group-disjoint and independent of decoding outcomes."""
import json
import io
from pathlib import Path

import pytest

from experiments.scripts.dataset_readiness_ted import select_ted
from experiments.scripts.dataset_readiness_iiit import select_iiit
from experiments.scripts.dataset_readiness_selection import extract_inputs, _extract_image


def row(index, split="validation", speaker=None, talk=None):
    return {"unit_id": f"{split}:unit{index}<tag>", "split": split,
            "speaker_id": speaker or f"speaker{index}", "talk_id": talk or f"talk{index}",
            "source_id": f"{talk or f'talk{index}'}.sph"}


def fixture_rows():
    history = [row(i) for i in range(20)]
    candidates = [row(i) for i in range(20, 60)] + [row(i, "final_test") for i in range(60, 90)]
    return history, candidates


def test_deterministic_rank_and_entire_historical_groups_excluded():
    history, candidates = fixture_rows()
    leaked = [row(100, speaker="speaker0"), row(101, talk="talk1")]
    ids = [r["unit_id"].replace("<", "_").replace(">", "_") for r in history]
    first = select_ted(history + candidates + leaked, ids, {})
    second = select_ted(list(reversed(history + candidates + leaked)), ids, {})
    assert first["selected"] == second["selected"]
    assert len(first["selected"]) == 50
    assert not {r["unit_id"] for r in leaked} & {r["unit_id"] for r in first["selected"]}
    assert len(first["historical"]) == 20


def test_missing_or_ambiguous_historical_identity_fails():
    history, candidates = fixture_rows()
    ids = [r["unit_id"] for r in history]
    with pytest.raises(ValueError, match="uniquely"):
        select_ted(history[1:] + candidates, ids, {})
    with pytest.raises(ValueError, match="uniquely"):
        select_ted(history + history[:1] + candidates, ids, {})


def test_insufficient_candidates_are_not_refilled():
    history, candidates = fixture_rows()
    result = select_ted(history + candidates[:3], [r["unit_id"] for r in history], {})
    assert len(result["selected"]) == 3
    assert len(result["issues"]) == 2


def test_native_group_overlap_fails_closed():
    history, _ = fixture_rows()
    with pytest.raises(ValueError, match="overlap"):
        select_ted(history + [row(100), row(101, "final_test", speaker="speaker100")],
                   [r["unit_id"] for r in history], {})


def test_iiit_orphan_is_recorded_as_blocking(tmp_path):
    frames = tmp_path / "experiments/datasets/iiit_cvid/IIIT-CVid/Frames"
    for split, course in (("val", "2"), ("test", "3")):
        directory = frames / split / course / "1"
        directory.mkdir(parents=True)
        (directory / "frame.png").write_bytes(b"not decoded during selection")
        (directory / "frame.xml").write_text("not parsed during selection")
    (frames / "val/2/1/orphan.xml").write_text("orphan")
    selected = select_iiit(tmp_path)
    assert selected["selection_status"] == "blocked"
    assert selected["issues"][0]["reason"] == "orphan_annotation"
    assert len(selected["selected"]) == 2


def test_extract_requires_exact_frozen_selection(tmp_path):
    (tmp_path / "selection.json").write_text(json.dumps({"protocol": {"seed": 1}}))
    with pytest.raises(ValueError, match="exact protocol"):
        extract_inputs(tmp_path, tmp_path, {"protocol": {"seed": 2}})


def test_image_corruption_and_missing_gt_are_explicit(tmp_path):
    (tmp_path / "broken.png").write_bytes(b"not an image")
    result = _extract_image(tmp_path, {"input_media_path": "broken.png", "annotation_path": "missing.xml"})
    assert not result["decoded"]
    assert result["decode_error"]
    assert result["ground_truth_error"]
    assert result["reference_text"] == ""


@pytest.mark.parametrize("format,subtype", [("WAV", "PCM_16"), ("WAV", "FLOAT"), ("FLAC", "PCM_16")])
def test_embedded_audio_declared_samples_and_truncation(tmp_path, monkeypatch, format, subtype):
    import numpy as np
    import soundfile as sf
    from experiments.scripts import dataset_readiness_selection as selection
    from experiments.scripts.dataset_readiness_audio import declared_audio_frames

    buffer = io.BytesIO()
    sf.write(buffer, np.sin(np.arange(1600) * 0.071), 16000, format=format, subtype=subtype)
    encoded = buffer.getvalue()
    assert declared_audio_frames(encoded) == 1600
    record = {"unit_id": "validation:valid", "reference_text": "official text",
              "arrow_path": "fixture.arrow", "arrow_batch": 0, "arrow_row": 0}
    monkeypatch.setattr(selection, "audio_bytes", lambda *_: iter([(record, {"bytes": encoded})]))
    valid = selection._extract_ted(tmp_path, tmp_path, [record])
    assert len(valid) == 1 and valid[0]["decoded"]
    assert valid[0]["frames"] == 1600
    assert valid[0]["duration_sec"] == 0.1
    truncated = encoded[:len(encoded) // 2]
    monkeypatch.setattr(selection, "audio_bytes", lambda *_: iter([(record, {"bytes": truncated})]))
    failed = selection._extract_ted(tmp_path, tmp_path, [record])
    assert len(failed) == 1 and not failed[0]["decoded"]
    assert failed[0]["decode_error"]
    assert failed[0]["media_path"] is None


def test_unknown_container_rejected():
    from experiments.scripts.dataset_readiness_audio import declared_audio_frames

    with pytest.raises(ValueError, match="unsupported or unverified"):
        declared_audio_frames(b"ID3-not-a-verified-format")
