"""Scene-boundary bake-off runner for notebook 02a (smoke/full)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from experiments.scripts.benchmark_artifacts import parse_context, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import (
    collar_boundary_f1,
    load_eligible_units,
    mean,
    rank_shortlist,
    require_media,
    write_stage_quartet,
)


def _video_duration_sec(path: Path) -> float:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video {path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if fps <= 0 or frames <= 0:
            raise RuntimeError(f"video {path} has invalid fps/frame count")
        return frames / fps
    finally:
        capture.release()


def _detect_histogram_cuts(path: Path, *, threshold: float = 0.55) -> list[float]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video {path}")
    cuts: list[float] = []
    previous = None
    index = 0
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            if previous is not None:
                distance = float(cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA))
                if distance >= threshold:
                    cuts.append(index / fps)
            previous = hist
            index += 1
            if index > 300:
                break
    finally:
        capture.release()
    return cuts


def _detect_pyscenedetect(path: Path, detector: str) -> list[float]:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import AdaptiveDetector, ContentDetector

    video = open_video(str(path))
    manager = SceneManager()
    if detector == "adaptive":
        manager.add_detector(AdaptiveDetector())
    else:
        manager.add_detector(ContentDetector(threshold=27.0))
    manager.detect_scenes(video, frame_skip=2)
    scenes = manager.get_scene_list()
    cuts: list[float] = []
    for start, _end in scenes:
        seconds = float(start.get_seconds())
        if seconds > 0:
            cuts.append(seconds)
    return cuts


def _fixed_grid(path: Path, interval_sec: float = 1.0) -> list[float]:
    duration = _video_duration_sec(path)
    return list(np.arange(interval_sec, duration, interval_sec))


def _reference_boundaries(unit: dict[str, Any]) -> list[float]:
    raw = unit.get("scene_boundaries_sec") or unit.get("scene_boundaries") or []
    values = [float(item) for item in raw]
    if not values:
        raise RuntimeError(f"unit {unit['unit_id']!r} missing scene_boundaries_sec")
    return values


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "02a_scene_boundary_benchmark", argv)
        units = load_eligible_units(context)
        if context.profile == "smoke":
            candidates = (
                ("histogram_bhat", lambda path: _detect_histogram_cuts(path)),
                ("fixed_grid_1s", lambda path: _fixed_grid(path, 1.0)),
            )
        else:
            candidates = (
                ("histogram_bhat", lambda path: _detect_histogram_cuts(path)),
                ("pyscenedetect_content", lambda path: _detect_pyscenedetect(path, "content")),
                ("fixed_grid_1s", lambda path: _fixed_grid(path, 1.0)),
            )

        predictions: list[dict[str, Any]] = []
        per_unit: list[dict[str, Any]] = []
        by_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            media = require_media(unit, "media_path", "video_path", "path")
            reference = _reference_boundaries(unit)
            for candidate, detector in candidates:
                pred = detector(media)
                metrics = collar_boundary_f1(pred, reference, collar_sec=2.0)
                predictions.append(
                    {
                        "unit_id": unit["unit_id"],
                        "dataset_id": unit.get("dataset_id"),
                        "candidate": candidate,
                        "predictions": {
                            "boundaries_sec": pred,
                            "reference_boundaries_sec": reference,
                            "media_path": media.as_posix(),
                        },
                        "model_loaded": True,
                        "execution_mode": "real",
                    }
                )
                per_unit.append(
                    {
                        "unit_id": unit["unit_id"],
                        "candidate": candidate,
                        "metrics": metrics,
                    }
                )
                by_candidate.setdefault(candidate, []).append(metrics)

        aggregate_metrics = {
            candidate: {
                "boundary_f1": mean(row["boundary_f1"] for row in rows),
                "boundary_precision": mean(row["boundary_precision"] for row in rows),
                "boundary_recall": mean(row["boundary_recall"] for row in rows),
            }
            for candidate, rows in by_candidate.items()
        }
        aggregate = [
            {"candidate": candidate, "metrics": metrics, "unit_count": len(by_candidate[candidate])}
            for candidate, metrics in aggregate_metrics.items()
        ]
        shortlist = rank_shortlist(aggregate_metrics, "boundary_f1", higher_better=True)
        write_stage_quartet(
            context,
            "scene",
            predictions=predictions,
            per_unit_metrics=per_unit,
            aggregate=aggregate,
            shortlist=shortlist,
        )
        write_run_manifest(context)
        print(f"[OK] scene boundary benchmark: {len(units)} unit(s), {len(aggregate)} candidate(s)")
        return 0
    except Exception as exc:
        print(f"[FAIL] scene boundary benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
