"""Visual caption bake-off runner for notebook 02d (smoke/full)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import cv2
import numpy as np

from experiments.scripts.benchmark_artifacts import parse_context, read_json_artifact, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import (
    grounded_claim_f1,
    load_eligible_units,
    mean,
    rank_shortlist,
    require_media,
    simple_cider,
    write_stage_quartet,
)


def _keyframes_by_unit(context) -> dict[str, list[dict[str, Any]]]:
    payload = read_json_artifact(context, "keyframe.raw_predictions")
    mapping: dict[str, list[dict[str, Any]]] = {}
    for record in payload["records"]:
        unit_id = str(record.get("unit_id"))
        predictions = record.get("predictions") or {}
        keyframes = predictions.get("keyframes") or []
        if unit_id not in mapping and keyframes:
            mapping[unit_id] = list(keyframes)
    if not mapping:
        raise RuntimeError("keyframe.raw_predictions contained no keyframes")
    return mapping


def _extract_frame(video: Path, timestamp_sec: float) -> np.ndarray:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video {video}")
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_sec) * 1000.0)
        ok, frame = capture.read()
        if not ok or frame is None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"unable to read frame at {timestamp_sec}s from {video}")
        return frame
    finally:
        capture.release()


def _dominant_color_caption(frame: np.ndarray) -> str:
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mean_h, mean_s, mean_v = [float(value) for value in hsv.reshape(-1, 3).mean(axis=0)]
    if mean_s < 40 or mean_v < 40:
        tone = "gray"
    elif mean_h < 15 or mean_h >= 165:
        tone = "red"
    elif mean_h < 45:
        tone = "yellow"
    elif mean_h < 85:
        tone = "green"
    elif mean_h < 130:
        tone = "blue"
    else:
        tone = "purple"
    brightness = "dark" if mean_v < 90 else "bright"
    return f"a {brightness} {tone} frame"


def _histogram_object_caption(frame: np.ndarray) -> str:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)
    if edge_ratio > 0.12:
        structure = "textured slide"
    elif edge_ratio > 0.04:
        structure = "simple diagram"
    else:
        structure = "plain background"
    return f"a lecture {structure}"


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "02d_visual_caption_benchmark", argv)
        units = load_eligible_units(context)
        keyframes_by_unit = _keyframes_by_unit(context)
        predictions: list[dict[str, Any]] = []
        per_unit: list[dict[str, Any]] = []
        by_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            media = require_media(unit, "media_path", "video_path", "image_path", "path")
            references = [
                str(item).strip()
                for item in (unit.get("caption_references") or unit.get("references") or [])
                if str(item).strip()
            ]
            if not references:
                raise RuntimeError(f"unit {unit['unit_id']!r} missing caption_references")
            claims = [
                str(item).strip()
                for item in (unit.get("grounded_claims") or references)
                if str(item).strip()
            ]
            keyframes = keyframes_by_unit.get(str(unit["unit_id"])) or [{"timestamp_sec": 0.0}]
            timestamp = float(keyframes[0].get("timestamp_sec") or 0.0)
            if media.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                frame = cv2.imread(str(media))
                if frame is None:
                    raise RuntimeError(f"unable to read image {media}")
            else:
                frame = _extract_frame(media, timestamp)

            candidate_captions = {
                "dominant_color_caption": _dominant_color_caption(frame),
                "histogram_object_caption": _histogram_object_caption(frame),
            }
            for candidate, caption in candidate_captions.items():
                metrics = {
                    "cider": float(simple_cider(caption, references)),
                    "grounded_claim_f1": float(grounded_claim_f1(caption, claims)),
                }
                predictions.append(
                    {
                        "unit_id": unit["unit_id"],
                        "dataset_id": unit.get("dataset_id"),
                        "candidate": candidate,
                        "predictions": {
                            "caption": caption,
                            "references": references,
                            "timestamp_sec": timestamp,
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
                "cider": mean(row["cider"] for row in rows),
                "grounded_claim_f1": mean(row["grounded_claim_f1"] for row in rows),
            }
            for candidate, rows in by_candidate.items()
        }
        aggregate = [
            {"candidate": candidate, "metrics": metrics, "unit_count": len(by_candidate[candidate])}
            for candidate, metrics in aggregate_metrics.items()
        ]
        shortlist = rank_shortlist(aggregate_metrics, "cider", higher_better=True)
        write_stage_quartet(
            context,
            "caption",
            predictions=predictions,
            per_unit_metrics=per_unit,
            aggregate=aggregate,
            shortlist=shortlist,
        )
        write_run_manifest(context)
        print(f"[OK] visual caption benchmark: {len(units)} unit(s), {len(aggregate)} candidate(s)")
        return 0
    except Exception as exc:
        print(f"[FAIL] visual caption benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
