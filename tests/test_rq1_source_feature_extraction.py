"""Focused source and cache contract checks for RQ1 visual features."""

from __future__ import annotations

import hashlib
import json
import sys
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.scripts import rq1_source_feature_extraction as features


def _media(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "lecture.mp4"
    path.write_bytes(b"source video bytes")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _scene() -> tuple[dict, list[dict]]:
    boundaries = [12.5]
    return {
        "available": True,
        "boundaries_sec": boundaries,
        "sha256": features._feature_digest(boundaries, features.SCENE_EXTRACTOR, features.SCENE_CONFIG),
        "extractor": features.SCENE_EXTRACTOR,
        "config": features.SCENE_CONFIG.copy(),
    }, [{"start_seconds": 0.0, "end_seconds": 12.5}, {"start_seconds": 12.5, "end_seconds": 20.0}]


def _ocr(limit: int = 12) -> dict:
    observations = [{"time_sec": 6.25, "text": "lecture slide"}]
    config = {**features.OCR_CONFIG, "max_ocr_frames": limit}
    return {
        "available": True,
        "observations": observations,
        "sha256": features._feature_digest(observations, features.OCR_EXTRACTOR, config),
        "extractor": features.OCR_EXTRACTOR,
        "config": config,
    }


def _numeric(extractor: str, config: dict) -> dict:
    observations = [{"time_sec": 10.0, "change_score": 0.2}]
    return {
        "available": True, "observations": observations,
        "sha256": features._feature_digest(observations, extractor, config),
        "extractor": extractor, "config": config.copy(),
    }


def test_missing_and_changed_media_fail_before_extraction(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    with pytest.raises(FileNotFoundError):
        features.extract_rq1_video_features(media.with_name("missing.mp4"), digest, tmp_path / "cache")
    with pytest.raises(ValueError, match="mismatch"):
        features.extract_rq1_video_features(media, "0" * 64, tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


def test_cache_reused_only_when_identity_and_content_digest_match(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    cache = tmp_path / "cache"
    with patch.object(features, "_scene_feature", return_value=_scene()) as scene, patch.object(features, "_ocr_feature", return_value=_ocr()) as ocr, patch.object(features, "_visual_feature", return_value=_numeric(features.VISUAL_EXTRACTOR, features.VISUAL_CONFIG)), patch.object(features, "_acoustic_feature", return_value=_numeric(features.ACOUSTIC_EXTRACTOR, features.ACOUSTIC_CONFIG)):
        first = features.extract_rq1_video_features(media, digest, cache)
        second = features.extract_rq1_video_features(media, digest, cache)
        assert first == second
        assert scene.call_count == 1
        assert ocr.call_count == 1

        cache_path = next(cache.glob("*.json"))
        envelope = json.loads(cache_path.read_text(encoding="utf-8"))
        envelope["features"]["scene"]["boundaries_sec"] = [999.0]
        cache_path.write_text(json.dumps(envelope), encoding="utf-8")
        features.extract_rq1_video_features(media, digest, cache)
        assert scene.call_count == 2


def test_numeric_modalities_are_source_bound_and_cache_digest_checked(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    cache = tmp_path / "cache"
    with patch.object(features, "_scene_feature", return_value=_scene()), patch.object(features, "_ocr_feature", return_value=_ocr()), patch.object(features, "_visual_feature", return_value=_numeric(features.VISUAL_EXTRACTOR, features.VISUAL_CONFIG)) as visual, patch.object(features, "_acoustic_feature", return_value=_numeric(features.ACOUSTIC_EXTRACTOR, features.ACOUSTIC_CONFIG)) as acoustic:
        first = features.extract_rq1_video_features(media, digest, cache)
        assert first["source_sha256"] == digest
        assert first["visual"]["observations"][0]["change_score"] == 0.2
        features.extract_rq1_video_features(media, digest, cache)
        assert visual.call_count == acoustic.call_count == 1
        path = next(cache.glob("*.json"))
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["features"]["visual"]["observations"][0]["change_score"] = 0.9
        path.write_text(json.dumps(envelope), encoding="utf-8")
        features.extract_rq1_video_features(media, digest, cache)
        assert visual.call_count == 2
        assert acoustic.call_count == 1


def test_legacy_scene_ocr_reuse_requires_source_and_provenance(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    del media
    cache = tmp_path / "cache"
    cache.mkdir()
    implementation = features._implementation_identity()
    prior = {**implementation, "rq1_extractor_source_sha256": features.LEGACY_SCENE_OCR_SOURCE_SHA256}
    identity = {
        "source_sha256": digest, "implementation": prior,
        "scene_config": features.SCENE_CONFIG, "scene_extractor": features.SCENE_EXTRACTOR,
        "ocr_extractor_strategy": [features.OCR_EXTRACTOR, features.EASYOCR_EXTRACTOR],
        "ocr_configs": [
            {**features.OCR_CONFIG, "max_ocr_frames": 12},
            {**features.EASYOCR_CONFIG, "max_ocr_frames": 12},
        ],
    }
    envelope = {"identity": identity, "features": {"source_sha256": digest, "scene": _scene()[0], "ocr": _ocr()}}
    path = cache / "rq1-video-features-old.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    assert features._reuse_legacy_scene_ocr(cache, digest, implementation, 12) is not None
    envelope["features"]["ocr"]["observations"][0]["text"] = "tampered"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    assert features._reuse_legacy_scene_ocr(cache, digest, implementation, 12) is None


def test_extractor_identity_change_invalidates_cache(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    cache = tmp_path / "cache"
    with patch.object(features, "_implementation_identity", side_effect=[
        {"revision": "old"}, {"revision": "old"},
        {"revision": "new"}, {"revision": "new"},
    ]), patch.object(features, "_scene_feature", return_value=_scene()) as scene, patch.object(
        features, "_ocr_feature", return_value=_ocr()
    ) as ocr:
        features.extract_rq1_video_features(media, digest, cache)
        features.extract_rq1_video_features(media, digest, cache)
    assert scene.call_count == 2
    assert ocr.call_count == 2


def test_post_extraction_identity_used_for_cache_write(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    cache = tmp_path / "cache"
    with patch.object(features, "_implementation_identity", side_effect=[
        {"model": "before"}, {"model": "after"},
        {"model": "after"}, {"model": "after"},
    ]), patch.object(features, "_scene_feature", return_value=_scene()) as scene, patch.object(features, "_ocr_feature", return_value=_ocr()) as ocr, patch.object(features, "_visual_feature", return_value=_numeric(features.VISUAL_EXTRACTOR, features.VISUAL_CONFIG)), patch.object(features, "_acoustic_feature", return_value=_numeric(features.ACOUSTIC_EXTRACTOR, features.ACOUSTIC_CONFIG)):
        features.extract_rq1_video_features(media, digest, cache)
        features.extract_rq1_video_features(media, digest, cache)
    assert scene.call_count == ocr.call_count == 1
    assert len(list(cache.glob("*.json"))) == 1


def test_visual_requires_near_complete_sample_coverage(tmp_path: Path) -> None:
    import numpy as np

    class SparseCapture:
        index = -1

        def isOpened(self):
            return True

        def set(self, *_):
            self.index += 1

        def read(self):
            return (True, np.zeros((36, 64, 3), dtype=np.uint8)) if self.index < 2 else (False, None)

        def release(self):
            pass

    with patch.object(features, "_duration_sec", return_value=100.0), patch("cv2.VideoCapture", return_value=SparseCapture()):
        result = features._visual_feature(tmp_path / "unused.mp4")
    assert result["available"] is False
    assert result["sample_coverage"] == {"decoded": 2, "expected": 5}
    assert "insufficient visual sample coverage" in result["reason"]


def test_implementation_identity_tracks_easyocr_weights(tmp_path: Path) -> None:
    model = tmp_path / "easyocr_models" / "english_g2.pth"
    model.parent.mkdir()
    model.write_bytes(b"old weights")
    before = features._implementation_identity(tmp_path)
    model.write_bytes(b"new weights")
    after = features._implementation_identity(tmp_path)
    assert before["cached_easyocr_model_sha256"] != after["cached_easyocr_model_sha256"]
    assert after["ffmpeg"] is None or len(after["ffmpeg"]["sha256"]) == 64


def test_ocr_unavailable_keeps_scene_and_is_retried(tmp_path: Path) -> None:
    media, digest = _media(tmp_path)
    unavailable = _ocr()
    unavailable.update(available=False, observations=[], reason="OCR unavailable: ImportError")
    unavailable["sha256"] = features._feature_digest([], features.OCR_EXTRACTOR, unavailable["config"])
    with patch.object(features, "_scene_feature", return_value=_scene()), patch.object(features, "_ocr_feature", side_effect=[unavailable, _ocr()]) as ocr:
        first = features.extract_rq1_video_features(media, digest, tmp_path / "cache")
        second = features.extract_rq1_video_features(media, digest, tmp_path / "cache")
    assert first["scene"]["available"] is True
    assert first["ocr"]["available"] is False
    assert "reason" in first["ocr"]
    assert second["ocr"]["available"] is True
    assert ocr.call_count == 2


def test_scene_midpoints_cover_full_lecture_with_frame_limit(tmp_path: Path) -> None:
    intervals = [{"start_seconds": float(i * 10), "end_seconds": float((i + 1) * 10)} for i in range(20)]
    times = features._sample_times(tmp_path / "unused.mp4", intervals, 4)
    assert times == [5.0, 65.0, 135.0, 195.0]


def test_single_scene_still_samples_multiple_times(tmp_path: Path) -> None:
    intervals = [{"start_seconds": 0.0, "end_seconds": 120.0}]
    assert features._sample_times(tmp_path / "unused.mp4", intervals, 4) == [15.0, 45.0, 75.0, 105.0]


def test_easyocr_fallback_records_actual_extractor_and_content_hash(tmp_path: Path) -> None:
    media, _ = _media(tmp_path)
    observations = [{"time_sec": 5.0, "text": "Real slide title"}]
    with patch.object(features, "_sample_times", return_value=[5.0]), patch.object(
        features, "_recognize_frames", side_effect=[AttributeError("np.sctypes"), observations]
    ) as recognize:
        result = features._ocr_feature(media, [], 1, tmp_path / "cache")
    assert [call.args[2] for call in recognize.call_args_list] == ["PaddleOCR", "EasyOCR"]
    assert result["available"] is True
    assert result["extractor"] == "EasyOCR"
    assert result["observations"] == observations
    assert result["sha256"] == features._feature_digest(observations, "EasyOCR", result["config"])


def test_paddle_import_legacy_numpy_types_are_temporary(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    sentinel = object()
    module = ModuleType("paddleocr")
    module.PaddleOCR = sentinel
    monkeypatch.setitem(sys.modules, "paddleocr", module)
    monkeypatch.delattr(np, "sctypes", raising=False)
    assert features._import_paddleocr() is sentinel
    assert not hasattr(np, "sctypes")
