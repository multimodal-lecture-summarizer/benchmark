"""Source-verified scene and slide-text features for the RQ1 pilot."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


SCENE_EXTRACTOR = "ai_workers.modules.visual_v2.scene_detector.SceneDetector"
OCR_EXTRACTOR = "PaddleOCR"
EASYOCR_EXTRACTOR = "EasyOCR"
SCENE_CONFIG = {"detector": "content", "threshold": 27.0, "frame_skip": 4}
OCR_CONFIG = {"lang": "en", "use_angle_cls": True, "sampling": "scene_midpoints_single_scene_grid_v2"}
EASYOCR_CONFIG = {"lang": "en", "gpu": False, "detail": 0, "sampling": "scene_midpoints_single_scene_grid_v2"}
VISUAL_EXTRACTOR = "OpenCV sparse grayscale frame difference"
ACOUSTIC_EXTRACTOR = "FFmpeg PCM window RMS change"
VISUAL_CONFIG = {"sample_interval_sec": 20, "width": 64, "height": 36, "change_score": "mean_absolute_pixel_difference/255", "min_decoded_fraction": 0.95}
ACOUSTIC_CONFIG = {"window_sec": 10, "sample_rate_hz": 8000, "change_score": "adjacent_rms_db_difference/40_clipped"}
# The existing scene/OCR implementation was shipped as an untracked pilot file.
# This digest is recorded by its source-bound cache envelopes, not inferred from GT.
LEGACY_SCENE_OCR_SOURCE_SHA256 = "1a938942ad06e56fdf04653c7190f2c36b050d781645b03158925fb064da5d0a"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _feature_digest(content: Any, extractor: str, config: dict[str, Any]) -> str:
    return _digest({"content": content, "extractor": extractor, "config": config})


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=128)
def _stat_bound_sha256(path: str, size: int, modified_ns: int) -> str:
    return _file_sha256(Path(path))


def _cached_file_sha256(path: Path) -> str:
    stat = path.stat()
    return _stat_bound_sha256(str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def _implementation_identity(cache_dir: Path | None = None) -> dict[str, Any]:
    """Bind cached features to the extractor code and installed model packages."""
    app = Path(__file__).resolve().parents[3] / "multimodal-lecture-summarizer"
    versions: dict[str, str] = {}
    for package in ("opencv-python", "scenedetect", "paddleocr", "paddlepaddle", "easyocr", "numpy"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    model_root = Path.home() / ".paddleocr" / "whl"
    model_hashes = {
        str(path.relative_to(model_root)).replace("\\", "/"): _cached_file_sha256(path)
        for path in sorted(model_root.rglob("inference.pdmodel")) + sorted(model_root.rglob("inference.pdiparams"))
    } if model_root.is_dir() else {}
    easyocr_root = Path(cache_dir) / "easyocr_models" if cache_dir is not None else None
    easyocr_hashes = {
        str(path.relative_to(easyocr_root)).replace("\\", "/"): _cached_file_sha256(path)
        for path in sorted(easyocr_root.rglob("*")) if path.is_file()
    } if easyocr_root is not None and easyocr_root.is_dir() else {}
    ffmpeg_path = shutil.which("ffmpeg")
    ffmpeg_identity = None
    if ffmpeg_path:
        version = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]
        ffmpeg_identity = {"path": str(Path(ffmpeg_path).resolve()), "version": version, "sha256": _cached_file_sha256(Path(ffmpeg_path))}
    return {
        "rq1_extractor_source_sha256": _file_sha256(Path(__file__)),
        "scene_detector_source_sha256": _file_sha256(
            app / "ai_workers/modules/visual_v2/scene_detector.py"
        ),
        "package_versions": versions,
        "cached_paddle_model_sha256": model_hashes,
        "cached_easyocr_model_sha256": easyocr_hashes,
        "ffmpeg": ffmpeg_identity,
    }


def _valid_feature(feature: Any, key: str, config: dict[str, Any], extractor: str) -> bool:
    if not isinstance(feature, dict) or feature.get("config") != config or feature.get("extractor") != extractor:
        return False
    content = feature.get(key)
    return isinstance(content, list) and feature.get("sha256") == _feature_digest(content, extractor, config) and isinstance(feature.get("available"), bool)


def _duration_sec(media_path: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(media_path))
    try:
        if not cap.isOpened():
            raise OSError("OpenCV could not open video")
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not fps or not frames or fps <= 0 or frames <= 0:
            raise ValueError("video duration unavailable")
        return frames / fps
    finally:
        cap.release()


def _numeric_feature(observations: list[dict[str, float]], extractor: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(observations), "observations": observations,
        "sha256": _feature_digest(observations, extractor, config),
        "extractor": extractor, "config": config.copy(),
    }


def _visual_feature(media_path: Path) -> dict[str, Any]:
    """Compare source frames at fixed times without using captions or labels."""
    import cv2

    observations: list[dict[str, float]] = []
    decoded = 0
    expected = 0
    try:
        duration = _duration_sec(media_path)
        cap = cv2.VideoCapture(str(media_path))
        try:
            if not cap.isOpened():
                raise OSError("OpenCV could not open video")
            previous = None
            sample_times = range(0, math.ceil(duration), VISUAL_CONFIG["sample_interval_sec"])
            expected = len(sample_times)
            for second in sample_times:
                cap.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
                success, frame = cap.read()
                if not success:
                    continue
                decoded += 1
                gray = cv2.cvtColor(cv2.resize(frame, (64, 36)), cv2.COLOR_BGR2GRAY)
                if previous is not None:
                    score = float(cv2.absdiff(gray, previous).mean() / 255.0)
                    observations.append({"time_sec": float(second), "change_score": round(score, 6)})
                previous = gray
        finally:
            cap.release()
    except Exception as exc:
        reason = f"visual extraction failed: {type(exc).__name__}: {exc}"
    else:
        if decoded < 2:
            reason = "fewer than two video frames decoded"
        elif decoded / expected < VISUAL_CONFIG["min_decoded_fraction"]:
            reason = f"insufficient visual sample coverage: {decoded}/{expected}"
        else:
            reason = None
    if reason:
        observations = []
    result = _numeric_feature(observations, VISUAL_EXTRACTOR, VISUAL_CONFIG)
    result["sample_coverage"] = {"decoded": decoded, "expected": expected}
    if reason:
        result["reason"] = reason
    return result


def _acoustic_feature(media_path: Path) -> dict[str, Any]:
    """Stream decoded source audio and measure adjacent-window energy changes."""
    import numpy as np

    observations: list[dict[str, float]] = []
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        result = _numeric_feature([], ACOUSTIC_EXTRACTOR, ACOUSTIC_CONFIG)
        result["reason"] = "ffmpeg unavailable"
        return result
    window_samples = ACOUSTIC_CONFIG["window_sec"] * ACOUSTIC_CONFIG["sample_rate_hz"]
    command = [ffmpeg, "-nostdin", "-v", "error", "-i", str(media_path), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    previous_db = None
    index = 0
    try:
        assert process.stdout is not None
        while True:
            block = process.stdout.read(window_samples * 2)
            if not block:
                break
            count = len(block) // 2
            if count < window_samples // 2:
                break
            samples = np.frombuffer(block[:count * 2], dtype="<i2").astype(np.float64)
            rms = float(np.sqrt(np.mean(samples * samples)) / 32768.0)
            db = 20 * math.log10(max(rms, 1e-6))
            if previous_db is not None:
                observations.append({"time_sec": float(index * ACOUSTIC_CONFIG["window_sec"]), "change_score": round(min(1.0, abs(db - previous_db) / 40.0), 6)})
            previous_db = db
            index += 1
        _, stderr = process.communicate()
        if process.returncode:
            raise OSError(stderr.decode("utf-8", errors="replace")[-500:])
        reason = "fewer than two audio windows decoded" if not observations else None
    except Exception as exc:
        process.kill()
        process.communicate()
        observations = []
        reason = f"acoustic extraction failed: {type(exc).__name__}: {exc}"
    result = _numeric_feature(observations, ACOUSTIC_EXTRACTOR, ACOUSTIC_CONFIG)
    if reason:
        result["reason"] = reason
    return result


def _scene_feature(media_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ai_workers.modules.visual_v2.scene_detector import SceneDetector

    try:
        scenes = SceneDetector({"detector": "content", "threshold": 27.0}).detect_scenes(str(media_path))
        boundaries = sorted({float(scene["start_seconds"]) for scene in scenes if float(scene["start_seconds"]) > 0})
        if not all(math.isfinite(value) for value in boundaries):
            raise ValueError("non-finite scene boundary")
        available = bool(boundaries)
        reason = None if available else "scene detector found no boundaries"
    except Exception as exc:
        scenes, boundaries = [], []
        available, reason = False, f"scene extraction failed: {type(exc).__name__}: {exc}"
    feature = {
        "available": available,
        "boundaries_sec": boundaries,
        "sha256": _feature_digest(boundaries, SCENE_EXTRACTOR, SCENE_CONFIG),
        "extractor": SCENE_EXTRACTOR,
        "config": SCENE_CONFIG.copy(),
    }
    if reason:
        feature["reason"] = reason
    return feature, scenes


def _sample_times(media_path: Path, scenes: list[dict[str, Any]], limit: int) -> list[float]:
    import cv2

    intervals = [(float(s["start_seconds"]), float(s["end_seconds"])) for s in scenes]
    intervals = [(start, end) for start, end in intervals if math.isfinite(start) and math.isfinite(end) and end > start]
    if not intervals:
        cap = cv2.VideoCapture(str(media_path))
        try:
            if not cap.isOpened():
                raise OSError("OpenCV could not open video")
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if not fps or not frames or fps <= 0 or frames <= 0:
                raise ValueError("video duration unavailable")
            intervals = [(0.0, frames / fps)]
        finally:
            cap.release()
    if len(intervals) == 1 and limit > 1:
        start, end = intervals[0]
        return [start + (index + 0.5) * (end - start) / limit for index in range(limit)]
    if len(intervals) > limit:
        indices = [round(index * (len(intervals) - 1) / (limit - 1)) for index in range(limit)] if limit > 1 else [len(intervals) // 2]
        intervals = [intervals[index] for index in indices]
    return [(start + end) / 2 for start, end in intervals]


def _import_paddleocr() -> Any:
    """Expose NumPy's removed legacy type lists only while importing imgaug."""
    import numpy as np

    original = getattr(np, "sctypes", None)
    if original is None:
        np.sctypes = {
            "int": [np.int8, np.int16, np.int32, np.int64],
            "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
            "float": [np.float16, np.float32, np.float64],
        }
    try:
        from paddleocr import PaddleOCR

        return PaddleOCR
    finally:
        if original is None:
            del np.sctypes


def _recognize_frames(media_path: Path, times: list[float], extractor: str, cache_dir: Path) -> list[dict[str, Any]]:
    import cv2

    if extractor == OCR_EXTRACTOR:
        PaddleOCR = _import_paddleocr()

        engine = PaddleOCR(lang="en", use_angle_cls=True, show_log=False)

        def recognize(frame: Any) -> str:
            result = engine.ocr(frame, cls=True)
            lines = result[0] if result and result[0] else []
            return " | ".join(str(line[1][0]) for line in lines).strip()
    else:
        import easyocr

        model_dir = cache_dir / "easyocr_models"
        model_dir.mkdir(parents=True, exist_ok=True)
        engine = easyocr.Reader(["en"], gpu=False, model_storage_directory=str(model_dir), verbose=False)

        def recognize(frame: Any) -> str:
            return " | ".join(str(text) for text in engine.readtext(frame, detail=0)).strip()

    cap = cv2.VideoCapture(str(media_path))
    observations: list[dict[str, Any]] = []
    try:
        if not cap.isOpened():
            raise OSError("OpenCV could not open video")
        for time_sec in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, time_sec * 1000)
            success, frame = cap.read()
            if not success:
                raise OSError(f"OpenCV could not read frame at {time_sec:.3f}s")
            observations.append({"time_sec": time_sec, "text": recognize(frame)})
    finally:
        cap.release()
    if not observations or not any(item["text"] for item in observations):
        raise ValueError("no OCR text recognized from sampled frames")
    return observations


def _ocr_feature(media_path: Path, scenes: list[dict[str, Any]], max_ocr_frames: int, cache_dir: Path) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    extractor = OCR_EXTRACTOR
    failures = []
    try:
        times = _sample_times(media_path, scenes, max_ocr_frames)
        for candidate in (OCR_EXTRACTOR, EASYOCR_EXTRACTOR):
            try:
                observations = _recognize_frames(media_path, times, candidate, cache_dir)
                extractor = candidate
                break
            except Exception as exc:
                failures.append(f"{candidate}: {type(exc).__name__}: {exc}")
        else:
            observations = []
    except Exception as exc:
        failures.append(f"frame sampling: {type(exc).__name__}: {exc}")
    config = {**(OCR_CONFIG if extractor == OCR_EXTRACTOR else EASYOCR_CONFIG), "max_ocr_frames": max_ocr_frames}
    feature = {
        "available": bool(observations),
        "observations": observations,
        "sha256": _feature_digest(observations, extractor, config),
        "extractor": extractor,
        "config": config,
    }
    if not observations:
        feature["reason"] = "OCR unavailable: " + "; ".join(failures)
    return feature


def _reuse_legacy_scene_ocr(cache_dir: Path, source_sha256: str, implementation: dict[str, Any], max_ocr_frames: int) -> dict[str, Any] | None:
    """Reuse old source-bound features only with matching dependency provenance."""
    for path in cache_dir.glob("rq1-video-features-*.json"):
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            identity, candidate = envelope["identity"], envelope["features"]
            old_impl = identity["implementation"]
            if identity["source_sha256"] != source_sha256 or candidate["source_sha256"] != source_sha256:
                continue
            if old_impl.get("rq1_extractor_source_sha256") != LEGACY_SCENE_OCR_SOURCE_SHA256:
                continue
            if any(old_impl.get(key) != implementation.get(key) for key in (
                "scene_detector_source_sha256", "package_versions", "cached_paddle_model_sha256"
            )):
                continue
            if identity.get("scene_config") != SCENE_CONFIG or identity.get("scene_extractor") != SCENE_EXTRACTOR:
                continue
            if identity.get("ocr_configs") != [
                {**OCR_CONFIG, "max_ocr_frames": max_ocr_frames},
                {**EASYOCR_CONFIG, "max_ocr_frames": max_ocr_frames},
            ]:
                continue
            scene, ocr = candidate.get("scene"), candidate.get("ocr")
            if not isinstance(ocr, dict) or ocr.get("extractor") != OCR_EXTRACTOR:
                # The old cache did not bind EasyOCR model weights.
                continue
            ocr_valid = any(_valid_feature(ocr, "observations", config, extractor) for extractor, config in zip(identity["ocr_extractor_strategy"], identity["ocr_configs"]))
            if _valid_feature(scene, "boundaries_sec", SCENE_CONFIG, SCENE_EXTRACTOR) and ocr_valid:
                return {"scene": scene, "ocr": ocr}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def extract_rq1_video_features(
    media_path: Path, expected_sha256: str, cache_dir: Path, *, max_ocr_frames: int = 12
) -> dict[str, Any]:
    """Extract real video features, rejecting a missing or changed MP4 before cache use."""
    media_path, cache_dir = Path(media_path), Path(cache_dir)
    if not media_path.is_file():
        raise FileNotFoundError(media_path)
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256.lower()):
        raise ValueError("expected_sha256 must be a 64-character hex digest")
    if not isinstance(max_ocr_frames, int) or isinstance(max_ocr_frames, bool) or max_ocr_frames < 1:
        raise ValueError("max_ocr_frames must be a positive integer")
    actual_sha256 = _file_sha256(media_path)
    if actual_sha256 != expected_sha256.lower():
        raise ValueError(f"media SHA256 mismatch: {media_path}")
    identity = {
        "source_sha256": actual_sha256,
        "implementation": _implementation_identity(cache_dir),
        "scene_extractor": SCENE_EXTRACTOR,
        "scene_config": SCENE_CONFIG,
        "ocr_extractor_strategy": [OCR_EXTRACTOR, EASYOCR_EXTRACTOR],
        "ocr_configs": [
            {**OCR_CONFIG, "max_ocr_frames": max_ocr_frames},
            {**EASYOCR_CONFIG, "max_ocr_frames": max_ocr_frames},
        ],
        "visual_extractor": VISUAL_EXTRACTOR,
        "visual_config": VISUAL_CONFIG,
        "acoustic_extractor": ACOUSTIC_EXTRACTOR,
        "acoustic_config": ACOUSTIC_CONFIG,
    }
    cache_path = cache_dir / f"rq1-video-features-{_digest(identity)}.json"
    cached: dict[str, Any] | None = None
    if cache_path.is_file():
        try:
            envelope = json.loads(cache_path.read_text(encoding="utf-8"))
            candidate = envelope["features"]
            if envelope["identity"] == identity and candidate["source_sha256"] == actual_sha256:
                cached = candidate
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if cached is None:
        cached = _reuse_legacy_scene_ocr(cache_dir, actual_sha256, identity["implementation"], max_ocr_frames)
    scene = cached.get("scene") if cached else None
    if not _valid_feature(scene, "boundaries_sec", SCENE_CONFIG, SCENE_EXTRACTOR) or not scene["available"]:
        scene, scenes = _scene_feature(media_path)
    else:
        scenes = []
    ocr = cached.get("ocr") if cached else None
    ocr_valid = any(
        _valid_feature(ocr, "observations", config, extractor)
        for extractor, config in zip(identity["ocr_extractor_strategy"], identity["ocr_configs"])
    )
    if not ocr_valid or not ocr["available"]:
        # Cached boundaries alone cannot recover scene intervals, so detect them
        # again when OCR needs frame sampling.
        if not scenes and scene["available"]:
            _, scenes = _scene_feature(media_path)
        ocr = _ocr_feature(media_path, scenes, max_ocr_frames, cache_dir)
    visual = cached.get("visual") if cached else None
    if not _valid_feature(visual, "observations", VISUAL_CONFIG, VISUAL_EXTRACTOR) or not visual["available"]:
        visual = _visual_feature(media_path)
    acoustic = cached.get("acoustic") if cached else None
    if not _valid_feature(acoustic, "observations", ACOUSTIC_CONFIG, ACOUSTIC_EXTRACTOR) or not acoustic["available"]:
        acoustic = _acoustic_feature(media_path)
    features = {"source_sha256": actual_sha256, "scene": scene, "ocr": ocr, "visual": visual, "acoustic": acoustic}
    # OCR can initialize/download weights after the first identity snapshot.
    # Write under the final dependency identity, never the stale pre-extraction one.
    identity["implementation"] = _implementation_identity(cache_dir)
    cache_path = cache_dir / f"rq1-video-features-{_digest(identity)}.json"
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"identity": identity, "features": features}, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(cache_path)
    return features
