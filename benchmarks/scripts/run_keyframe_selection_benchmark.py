"""Keyframe selection bake-off runner for notebook 02b (smoke/full)."""

from __future__ import annotations

from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import parse_context, read_json_artifact, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
    mean,
    rank_shortlist,
    require_media,
    required_scene_f1,
    write_stage_quartet,
)


def _scene_predictions_by_unit(context) -> dict[str, list[float]]:
    payload = read_json_artifact(context, "scene.raw_predictions")
    best: dict[str, list[float]] = {}
    for record in payload["records"]:
        unit_id = str(record.get("unit_id"))
        predictions = record.get("predictions") or {}
        boundaries = predictions.get("boundaries_sec") or []
        if unit_id not in best:
            best[unit_id] = [float(value) for value in boundaries]
    if not best:
        raise RuntimeError("scene.raw_predictions contained no usable boundaries")
    return best


def _midpoint_keyframes(boundaries: Sequence[float], duration_sec: float) -> list[dict[str, Any]]:
    points = [0.0, *[float(value) for value in boundaries if value > 0], float(duration_sec)]
    points = sorted({round(value, 3) for value in points if value >= 0})
    frames: list[dict[str, Any]] = []
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        if end <= start:
            continue
        frames.append(
            {
                "scene_id": f"s{index}",
                "timestamp_sec": (start + end) / 2.0,
                "start_sec": start,
                "end_sec": end,
            }
        )
    if not frames:
        raise RuntimeError("unable to derive keyframes from scene boundaries")
    return frames


def _uniform_keyframes(duration_sec: float, budget: int) -> list[dict[str, Any]]:
    if duration_sec <= 0:
        raise RuntimeError("video duration must be positive")
    step = duration_sec / max(budget, 1)
    return [
        {
            "scene_id": f"u{index}",
            "timestamp_sec": min(duration_sec, step * (index + 0.5)),
            "start_sec": step * index,
            "end_sec": min(duration_sec, step * (index + 1)),
        }
        for index in range(budget)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "02b_keyframe_selection_benchmark", argv)
        units = load_eligible_units(context)
        scene_by_unit = _scene_predictions_by_unit(context)
        predictions: list[dict[str, Any]] = []
        per_unit: list[dict[str, Any]] = []
        by_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            media = require_media(unit, "media_path", "video_path", "path")
            required = [str(item) for item in (unit.get("required_scene_ids") or [])]
            if not required:
                required = ["s0"]
            duration = float(unit.get("duration_sec") or 0.0)
            if duration <= 0:
                import cv2

                capture = cv2.VideoCapture(str(media))
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
                frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
                capture.release()
                duration = frames / fps if fps > 0 else 2.0
            boundaries = scene_by_unit.get(str(unit["unit_id"]), [])
            candidate_map = {
                "scene_midpoint": _midpoint_keyframes(boundaries, duration),
                "uniform_budget": _uniform_keyframes(duration, max(1, len(required))),
            }
            for candidate, keyframes in candidate_map.items():
                selected_ids = [frame["scene_id"] for frame in keyframes]
                metrics = required_scene_f1(selected_ids, required)
                metrics["keyframe_count"] = float(len(keyframes))
                predictions.append(
                    {
                        "unit_id": unit["unit_id"],
                        "dataset_id": unit.get("dataset_id"),
                        "candidate": candidate,
                        "predictions": {
                            "keyframes": keyframes,
                            "required_scene_ids": required,
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
                "required_scene_f1": mean(row["required_scene_f1"] for row in rows),
                "keyframe_precision": mean(row["keyframe_precision"] for row in rows),
                "scene_coverage": mean(row["scene_coverage"] for row in rows),
            }
            for candidate, rows in by_candidate.items()
        }
        aggregate = [
            {"candidate": candidate, "metrics": metrics, "unit_count": len(by_candidate[candidate])}
            for candidate, metrics in aggregate_metrics.items()
        ]
        shortlist = rank_shortlist(aggregate_metrics, "required_scene_f1", higher_better=True)
        write_stage_quartet(
            context,
            "keyframe",
            predictions=predictions,
            per_unit_metrics=per_unit,
            aggregate=aggregate,
            shortlist=shortlist,
        )
        write_run_manifest(context)
        print(f"[OK] keyframe selection benchmark: {len(units)} unit(s), {len(aggregate)} candidate(s)")
        return 0
    except Exception as exc:
        print(f"[FAIL] keyframe selection benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
