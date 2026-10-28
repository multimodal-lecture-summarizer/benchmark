"""Tracking runner for benchmark 03b: frozen tracker specs, detection I/O, one-sequence runs, scoring and decisions.

Pure functions; heavy imports (`trackers`, `supervision`, `cv2`) are lazy so the module imports anywhere.
Two tiers (see the phase plan): tier A produces fixed detections (GPU, once); tier B (this module) tracks and scores
on CPU. The tracker search space comes from the frozen registry file and is refused unless its status is `approved`.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from experiments.scripts import paired_bootstrap as pb
from experiments.scripts import tracking_scoring as ts

PRACTICAL_HOTA_THRESHOLD = 2.0     # HOTA points; pre-registered in the DanceTrack registry
DEFAULT_WARMUP_FRAMES = 5
BUDGET_OVERHEAD = 1.3

# Source (b) detector input, settled by the Colab smoke (precision 0.864 / recall 0.986 vs GT; raw BGR gave 0.003 / 0.041).
YOLOX_INPUT_SIZE = (800, 1440)
YOLOX_MEAN = (0.485, 0.456, 0.406)
YOLOX_STD = (0.229, 0.224, 0.225)
YOLOX_NMS = 0.7
DET_SCORE_FLOOR = 0.1             # ByteTrack-style trackers need low-score boxes
UNVERIFIED_FLAG = "DETECTOR_TRAIN_DATA_UNVERIFIED"


# --------------------------------------------------------------------------
# Detection I/O (MOT det rows: frame, id=-1, x, y, w, h, conf)
# --------------------------------------------------------------------------
def det_rows(frame: int, boxes_xywh: np.ndarray, scores: np.ndarray) -> np.ndarray:
    boxes_xywh = np.asarray(boxes_xywh, float).reshape(-1, 4)
    out = np.full((len(boxes_xywh), 7), -1.0)
    out[:, 0], out[:, 2:6], out[:, 6] = frame, boxes_xywh, np.asarray(scores, float).reshape(-1)
    return out


def write_mot_dets(path: str | Path, rows: np.ndarray) -> np.ndarray:
    """Write MOT det rows and return the values as stored (6 significant digits).

    Checksum and track on the returned array, never on `rows`: the file is what is frozen, and a checksum of the
    unrounded input would not match what is read back later.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(ts.format_mot_rows(np.asarray(rows, float).reshape(-1, 7)) + "\n", encoding="utf-8")
    return read_mot_dets(path)


def read_mot_dets(path: str | Path) -> np.ndarray:
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return np.zeros((0, 7))
    return np.array([[float(v) for v in line.split(",")[:7]] for line in text.splitlines()], dtype=float)


def dets_checksum(rows: np.ndarray) -> str:
    """Content hash of a detection set: stable across file formatting, changes when any value changes."""
    rows = np.ascontiguousarray(np.asarray(rows, dtype="<f8").reshape(-1, 7))
    return hashlib.sha256(rows.tobytes()).hexdigest()


def dets_by_frame(rows: np.ndarray, seq_length: int) -> list[np.ndarray]:
    return ts._split_by_frame(np.asarray(rows, float).reshape(-1, 7), seq_length)


# --------------------------------------------------------------------------
# Source (b): YOLOX input / output handling
# --------------------------------------------------------------------------
def yolox_letterbox(img_bgr: np.ndarray, size: tuple[int, int] = YOLOX_INPUT_SIZE) -> tuple[np.ndarray, float]:
    """(1,3,H,W) float32 network input: letterbox pad 114, BGR->RGB, /255, ImageNet mean/std. Returns (input, scale)."""
    import cv2

    scale = min(size[0] / img_bgr.shape[0], size[1] / img_bgr.shape[1])
    resized = cv2.resize(img_bgr, (int(img_bgr.shape[1] * scale), int(img_bgr.shape[0] * scale)))
    canvas = np.full((*size, 3), 114, dtype=np.uint8)
    canvas[:resized.shape[0], :resized.shape[1]] = resized
    x = canvas[:, :, ::-1].astype("float32") / 255.0
    x = (x - np.array(YOLOX_MEAN, "float32")) / np.array(YOLOX_STD, "float32")
    return np.ascontiguousarray(x.transpose(2, 0, 1), dtype="float32")[None], scale


def yolox_outputs_to_rows(out: np.ndarray | None, scale: float, frame: int) -> np.ndarray:
    """YOLOX `postprocess` rows (x1,y1,x2,y2,obj,cls,cls_id) in letterbox pixels -> MOT det rows in image pixels."""
    if out is None or len(out) == 0:
        return np.zeros((0, 7))
    out = np.asarray(out, float)
    xyxy = out[:, :4] / scale
    xywh = np.column_stack([xyxy[:, 0], xyxy[:, 1], xyxy[:, 2] - xyxy[:, 0], xyxy[:, 3] - xyxy[:, 1]])
    return det_rows(frame, xywh, out[:, 4] * out[:, 5])


# --------------------------------------------------------------------------
# Tracker specs and search-space sampling
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class TrackerSpec:
    id: str                              # sort | bytetrack | ocsort | botsort
    cls: str                             # e.g. trackers.SORTTracker
    defaults: dict[str, Any]
    search: dict[str, dict[str, Any]]
    needs_frame: bool = False            # BoT-SORT skips CMC silently when no frame is passed
    version: str = ""


def load_specs(path: str | Path) -> dict[str, TrackerSpec]:
    """Specs from the frozen search-space registry. Refuses a file that was not approved by the user."""
    reg = json.loads(Path(path).read_text(encoding="utf-8"))
    if reg.get("status") != "approved":
        raise ValueError(f"search space is {reg.get('status')!r}, not 'approved': refuse to run before the freeze")
    version = reg["library"]["version"]
    return {fam: TrackerSpec(id=fam, cls=body["cls"], defaults=dict(body["defaults"]), search=dict(body["search"]),
                             needs_frame=(fam == "botsort"), version=version)
            for fam, body in reg["trackers"].items()}


def _draw(param: str, rule: dict[str, Any], seed: int, index: int):
    """One parameter value, drawn from a stream keyed by (seed, config index, parameter name).

    Keying by name makes a shared parameter (e.g. lost_track_buffer) identical across trackers for the same config
    index, and adding a parameter to one tracker never shifts the draws of another.
    """
    key = int(hashlib.sha256(param.encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng([seed, index, key])
    if rule["type"] == "choice":
        return rule["values"][int(rng.integers(len(rule["values"])))]
    if rule["type"] == "uniform":
        return round(float(rng.uniform(rule["low"], rule["high"])), 4)
    raise ValueError(f"unknown search rule {rule['type']!r} for {param}")


def sample_configs(spec: TrackerSpec, n: int, seed: int) -> list[dict[str, Any]]:
    """Config 0 = published defaults (reported separately); configs 1..n = seeded random search."""
    configs = [dict(spec.defaults)]
    for i in range(1, n + 1):
        cfg = dict(spec.defaults)
        cfg.update({p: _draw(p, rule, seed, i) for p, rule in sorted(spec.search.items())})
        configs.append(cfg)
    return configs


def params_digest(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True, default=float).encode()).hexdigest()


def build_tracker(spec: TrackerSpec, params: dict[str, Any], frame_rate: float):
    """Instantiate the library tracker. `frame_rate` is the sequence rate (the library default 30 would mis-scale buffers)."""
    import trackers

    cls = getattr(trackers, spec.cls.split(".")[-1])
    return cls(**{**params, "frame_rate": float(frame_rate)})


# --------------------------------------------------------------------------
# Running one sequence
# --------------------------------------------------------------------------
def _to_detections(rows: np.ndarray):
    import supervision as sv

    if len(rows) == 0:
        return sv.Detections.empty()
    xyxy = np.column_stack([rows[:, 2], rows[:, 3], rows[:, 2] + rows[:, 4], rows[:, 3] + rows[:, 5]])
    return sv.Detections(xyxy=xyxy, confidence=rows[:, 6], class_id=np.zeros(len(rows), dtype=int))


def run_sequence(tracker, dets: np.ndarray, seq_length: int, frames: Callable[[int], np.ndarray | None] | None = None,
                 needs_frame: bool = False, warmup: int = DEFAULT_WARMUP_FRAMES) -> dict[str, Any]:
    """Track one sequence. Only `tracker.update` is timed (decode and detector excluded).

    Unconfirmed tracks (`tracker_id == -1`) are dropped. Failures are returned with a reason, never raised:
    `exception:*`, `duplicate_id_in_frame:<t>`, `frame_missing:<t>`.
    """
    per_frame = dets_by_frame(dets, seq_length)
    out_rows: list[np.ndarray] = []
    times: list[float] = []
    n_unconfirmed = 0
    result: dict[str, Any] = dict(ok=True, reason=None, n_frames=seq_length)
    for t in range(1, seq_length + 1):
        image = frames(t) if (frames is not None and needs_frame) else None
        if needs_frame and image is None:
            result.update(ok=False, reason=f"frame_missing:{t}")
            break
        try:
            detections = _to_detections(per_frame[t - 1])
            t0 = time.perf_counter()
            tracked = tracker.update(detections, image) if needs_frame else tracker.update(detections)
            times.append(time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001 - every failure is recorded with its reason
            result.update(ok=False, reason=f"exception:{type(exc).__name__}:{str(exc)[:160]}")
            break
        if len(tracked) == 0:
            continue
        ids = np.asarray(tracked.tracker_id if tracked.tracker_id is not None else [], dtype=int)
        keep = ids >= 0
        n_unconfirmed += int((~keep).sum())
        ids, xyxy = ids[keep], np.asarray(tracked.xyxy, float)[keep]
        conf = np.asarray(tracked.confidence if tracked.confidence is not None else np.ones(len(keep)), float)[keep]
        if len(set(ids.tolist())) != len(ids):
            result.update(ok=False, reason=f"duplicate_id_in_frame:{t}")
            break
        if len(ids):
            out_rows.append(np.column_stack([np.full(len(ids), t), ids, xyxy[:, 0], xyxy[:, 1],
                                             xyxy[:, 2] - xyxy[:, 0], xyxy[:, 3] - xyxy[:, 1], conf]))
    rows = np.vstack(out_rows) if out_rows else np.zeros((0, 7))
    timed = times[warmup:] if len(times) > warmup else times
    result.update(rows=rows, n_unconfirmed_dropped=n_unconfirmed, update_seconds=float(sum(times)),
                  median_update_ms=float(np.median(timed) * 1000) if timed else None,
                  fps=(len(timed) / sum(timed)) if timed and sum(timed) > 0 else None)
    return result


# --------------------------------------------------------------------------
# Resumable store: (tracker, config, sequence)
# --------------------------------------------------------------------------
def run_path(store: str | Path, tracker_id: str, config_index: int, seq: str) -> Path:
    return Path(store) / tracker_id / f"cfg{config_index:02d}" / seq


def run_or_load(store: str | Path, tracker_id: str, config_index: int, seq: str, params: dict[str, Any],
                dets: np.ndarray, run: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Reuse a finished run only if its parameters and detection checksum match; otherwise rerun and overwrite.

    Failed runs are stored too (with their reason) but are retried, so a transient crash does not stick.
    """
    base = run_path(store, tracker_id, config_index, seq)
    meta_file, rows_file = base.with_suffix(".json"), base.with_suffix(".txt")
    want = dict(params_sha256=params_digest(params), dets_sha256=dets_checksum(dets))
    if meta_file.exists() and rows_file.exists():
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("ok") and all(meta.get(k) == v for k, v in want.items()):
            text = rows_file.read_text(encoding="utf-8").strip()
            rows = np.array([[float(v) for v in ln.split(",")] for ln in text.splitlines()]) if text else np.zeros((0, 7))
            return {**meta, "rows": rows, "loaded": True}
    res = run()
    base.parent.mkdir(parents=True, exist_ok=True)
    rows = res.get("rows", np.zeros((0, 7)))
    meta = {k: v for k, v in res.items() if k != "rows"} | want | dict(tracker=tracker_id, config=config_index, seq=seq)
    rows_file.write_text(ts.format_mot_rows(rows) + "\n", encoding="utf-8")
    meta_file.write_text(json.dumps(meta, indent=1, default=float), encoding="utf-8")
    return {**meta, "rows": rows, "loaded": False}


# --------------------------------------------------------------------------
# Scoring and decisions
# --------------------------------------------------------------------------
def score_run(gt: np.ndarray, run: dict[str, Any], seq_length: int) -> dict[str, Any]:
    """Per-sequence TrackEval result of one run, kept for video-level bootstrap. A failed run is not scored as zero."""
    if not run.get("ok"):
        return dict(ok=False, reason=run.get("reason"), result=None)
    return dict(ok=True, reason=None, result=ts.evaluate_sequence(gt, run["rows"], seq_length))


def score_config(scored: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Pooled score over sequences. If any sequence failed there is no score: the failures are listed instead."""
    failed = {seq: s["reason"] for seq, s in scored.items() if not s["ok"]}
    if failed:
        return dict(score=None, failed=failed)
    return dict(score=ts.score_sequences([s["result"] for s in scored.values()]), failed={})


def paired_decision(per_seq_a: Sequence[dict], per_seq_b: Sequence[dict], resamples: int = 10_000, seed: int = 0,
                    key: str = "HOTA", threshold: float = PRACTICAL_HOTA_THRESHOLD) -> dict[str, Any]:
    """Paired video bootstrap of a - b with the pre-registered rule (CI excludes 0 and |delta| >= threshold)."""
    assert len(per_seq_a) == len(per_seq_b), "paired comparison needs the same sequences"
    mult = pb.cluster_multiplicities(len(per_seq_a), None, resamples, seed)
    res = pb.paired_bootstrap(ts.metric_on_resample(per_seq_a, key), ts.metric_on_resample(per_seq_b, key), mult)
    return {**res, "decision": pb.decide_difference(res, threshold), "threshold": threshold, "metric": key}


def estimate_budget(update_ms: dict[str, float], n_frames: int, configs_per_tracker: dict[str, int],
                    max_hours: float | None = None, overhead: float = BUDGET_OVERHEAD) -> dict[str, Any]:
    """Tier B wall-clock hours from measured median `update` ms (smoke). Per tracker: ms * frames * configs * overhead."""
    per = {k: update_ms[k] / 1000 * n_frames * configs_per_tracker[k] * overhead / 3600 for k in update_ms}
    total = float(sum(per.values()))
    return dict(per_tracker_hours=per, total_hours=total, within_budget=None if max_hours is None else total <= max_hours)
