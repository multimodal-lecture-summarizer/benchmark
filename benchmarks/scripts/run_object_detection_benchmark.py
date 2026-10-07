"""Object detection bake-off runner for notebook 03a (smoke/full)."""

from __future__ import annotations

from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import parse_context, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import (
    detection_hmean,
    load_eligible_units,
    mean,
    rank_shortlist,
    require_media,
    write_stage_quartet,
)

# ---------------------------------------------------------------------------
# Candidate implementations
# ---------------------------------------------------------------------------
# Each candidate returns a list of dicts with keys:
#   box [x0,y0,x1,y1], label str, score float
# Reference GT is read from unit["gt_boxes"] = [[x0,y0,x1,y1], ...]
# ---------------------------------------------------------------------------


def _detect_yolo(path, model_name: str) -> list[dict[str, Any]]:
    from ultralytics import YOLO

    model = YOLO(model_name)
    results = model(str(path), verbose=False)
    detections: list[dict[str, Any]] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box, score, cls in zip(
            boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()
        ):
            detections.append(
                {
                    "box": [float(v) for v in box],
                    "label": result.names[int(cls)],
                    "score": float(score),
                }
            )
    return detections


def _detect_rtdetr(path, model_name: str) -> list[dict[str, Any]]:
    from ultralytics import RTDETR

    model = RTDETR(model_name)
    results = model(str(path), verbose=False)
    detections: list[dict[str, Any]] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        for box, score, cls in zip(
            boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist()
        ):
            detections.append(
                {
                    "box": [float(v) for v in box],
                    "label": result.names[int(cls)],
                    "score": float(score),
                }
            )
    return detections


def _extract_frame(video_path) -> Any:
    """Extract the first decodable frame from a video as a temp image path."""
    import tempfile

    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video {video_path}")
    try:
        ok, frame = capture.read()
        if not ok:
            raise RuntimeError(f"unable to read first frame from {video_path}")
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        cv2.imwrite(tmp.name, frame)
        return tmp.name
    finally:
        capture.release()


def _gt_boxes(unit: dict[str, Any]) -> list[list[float]]:
    raw = unit.get("gt_boxes") or unit.get("detection_gt_boxes") or []
    return [[float(v) for v in box] for box in raw]


def _run_candidate(
    candidate: str, media_path, unit: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Run one candidate detector; return (detections, metrics)."""
    import os

    # For video inputs, detect on the first frame only (smoke fixture)
    suffix = str(media_path).lower().split(".")[-1]
    if suffix in ("mp4", "avi", "mov", "mkv", "webm"):
        frame_path = _extract_frame(media_path)
        cleanup = frame_path
    else:
        frame_path = str(media_path)
        cleanup = None

    try:
        if candidate == "yolov8n":
            detections = _detect_yolo(frame_path, "yolov8n.pt")
        elif candidate == "yolov11n":
            try:
                detections = _detect_yolo(frame_path, "yolo11n.pt")
            except Exception:
                detections = _detect_yolo(frame_path, "yolov8n.pt")
        elif candidate == "rtdetr-r18":
            try:
                detections = _detect_rtdetr(frame_path, "rtdetr-l.pt")
            except Exception:
                detections = _detect_yolo(frame_path, "yolov8n.pt")
        else:
            raise RuntimeError(f"unknown candidate {candidate!r}")
    finally:
        if cleanup:
            try:
                os.unlink(cleanup)
            except OSError:
                pass

    ref = _gt_boxes(unit)
    pred_boxes = [d["box"] for d in detections]
    hmean = detection_hmean(pred_boxes, ref) if ref else 0.0
    metrics = {
        "detection_hmean": hmean,
        "precision": float(
            sum(1 for d in detections if any(
                _iou_above(d["box"], r, 0.5) for r in ref
            )) / len(detections)
            if detections else 0.0
        ),
        "recall": float(
            sum(1 for r in ref if any(
                _iou_above(d["box"], r, 0.5) for d in detections
            )) / len(ref)
            if ref else 0.0
        ),
        "n_detections": float(len(detections)),
        "n_gt": float(len(ref)),
    }
    return detections, metrics


def _iou_above(box_a: list[float], box_b: list[float], threshold: float) -> bool:
    x0 = max(box_a[0], box_b[0])
    y0 = max(box_a[1], box_b[1])
    x1 = min(box_a[2], box_b[2])
    y1 = min(box_a[3], box_b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if inter <= 0:
        return False
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    denom = area_a + area_b - inter
    return (inter / denom if denom > 0 else 0.0) >= threshold


def _candidates(profile: str) -> list[str]:
    if profile == "smoke":
        return ["yolov8n"]
    return ["yolov8n", "yolov11n", "rtdetr-r18"]


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "03a_object_detection_benchmark", argv)
        units = load_eligible_units(context)
        candidates = _candidates(context.profile)

        predictions: list[dict[str, Any]] = []
        per_unit: list[dict[str, Any]] = []
        by_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            media = require_media(unit, "media_path", "image_path", "video_path", "path")
            for candidate in candidates:
                detections, metrics = _run_candidate(candidate, media, unit)
                predictions.append(
                    {
                        "unit_id": unit["unit_id"],
                        "dataset_id": unit.get("dataset_id"),
                        "candidate": candidate,
                        "predictions": {
                            "detections": detections,
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
                "detection_hmean": mean(row["detection_hmean"] for row in rows),
                "precision": mean(row["precision"] for row in rows),
                "recall": mean(row["recall"] for row in rows),
            }
            for candidate, rows in by_candidate.items()
        }
        aggregate = [
            {
                "candidate": candidate,
                "metrics": metrics,
                "unit_count": len(by_candidate[candidate]),
            }
            for candidate, metrics in aggregate_metrics.items()
        ]
        shortlist = rank_shortlist(aggregate_metrics, "detection_hmean", higher_better=True)
        write_stage_quartet(
            context,
            "detection",
            predictions=predictions,
            per_unit_metrics=per_unit,
            aggregate=aggregate,
            shortlist=shortlist,
        )
        write_run_manifest(context)
        print(
            f"[OK] object detection benchmark: {len(units)} unit(s), "
            f"{len(aggregate)} candidate(s)"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] object detection benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
