"""Tracking scoring for benchmark 03b: HOTA / CLEAR / Identity via the pinned TrackEval metric code.

Sequences are scored from in-memory MOT arrays (frame,id,x,y,w,h,conf,...), reproducing the
`MotChallenge2DBox` data path with preprocessing disabled (ground-truth rows with flag 0 are dropped,
all tracker rows kept, ids made contiguous, IoU similarity on xywh boxes). Per-sequence results are
kept so combined scores can be recomputed on video bootstrap resamples. Agreement with the official
TrackEval evaluator is unit-tested on randomised sequences.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

PINNED_TRACKEVAL_COMMIT = "12c8791b303e0a0b50f753af204249e622d0281a"
INSTALL_HINT = (f"pip install --no-deps https://github.com/JonathonLuiten/TrackEval/archive/"
                f"{PINNED_TRACKEVAL_COMMIT}.zip")
HOTA_ALPHAS = np.arange(0.05, 0.99, 0.05)  # 19 localisation thresholds used by TrackEval


def load_trackeval():
    """Import TrackEval, restoring the NumPy aliases (np.float/np.int/np.bool) that its 2022 code uses."""
    import builtins

    import numpy

    for name in ("float", "int", "bool"):
        if name not in numpy.__dict__:
            setattr(numpy, name, getattr(builtins, name))
    try:
        import trackeval
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError(f"TrackEval is not installed. Install the pinned commit: {INSTALL_HINT}") from exc
    return trackeval


def box_iou_xywh(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU matrix (len(a), len(b)) for xywh boxes."""
    a, b = np.atleast_2d(a).reshape(-1, 4), np.atleast_2d(b).reshape(-1, 4)
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    ax2, ay2, bx2, by2 = a[:, 0] + a[:, 2], a[:, 1] + a[:, 3], b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
    iw = np.clip(np.minimum(ax2[:, None], bx2[None]) - np.maximum(a[:, 0][:, None], b[:, 0][None]), 0, None)
    ih = np.clip(np.minimum(ay2[:, None], by2[None]) - np.maximum(a[:, 1][:, None], b[:, 1][None]), 0, None)
    inter = iw * ih
    union = (a[:, 2] * a[:, 3])[:, None] + (b[:, 2] * b[:, 3])[None] - inter
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


def _split_by_frame(arr: np.ndarray, seq_length: int) -> list[np.ndarray]:
    frames = arr[:, 0].astype(int) if len(arr) else np.zeros(0, int)
    if len(arr) and (frames.min() < 1 or frames.max() > seq_length):
        raise ValueError(f"frame index outside 1..{seq_length}")
    return [arr[frames == t + 1] for t in range(seq_length)]


def prepare_sequence(gt: np.ndarray, pred: np.ndarray, seq_length: int) -> dict[str, Any]:
    """Build the TrackEval `data` dict for one sequence (no distractor preprocessing)."""
    gt = np.asarray(gt, dtype=float).reshape(-1, max(np.asarray(gt).shape[-1], 6)) if len(gt) else np.zeros((0, 9))
    pred = np.asarray(pred, dtype=float).reshape(-1, max(np.asarray(pred).shape[-1], 6)) if len(pred) else np.zeros((0, 7))
    if gt.shape[1] > 6:
        gt = gt[np.nan_to_num(gt[:, 6], nan=1.0) != 0]          # zero-marked ground-truth rows are not evaluated
    gt_frames, pred_frames = _split_by_frame(gt, seq_length), _split_by_frame(pred, seq_length)
    gt_ids_all = np.unique(gt[:, 1].astype(int)) if len(gt) else np.zeros(0, int)
    pr_ids_all = np.unique(pred[:, 1].astype(int)) if len(pred) else np.zeros(0, int)
    gmap = {v: i for i, v in enumerate(gt_ids_all)}
    pmap = {v: i for i, v in enumerate(pr_ids_all)}
    data: dict[str, Any] = dict(num_timesteps=seq_length, gt_ids=[], tracker_ids=[], similarity_scores=[],
                                num_gt_ids=len(gt_ids_all), num_tracker_ids=len(pr_ids_all),
                                num_gt_dets=int(len(gt)), num_tracker_dets=int(len(pred)))
    for g, p in zip(gt_frames, pred_frames):
        g_ids = np.array([gmap[int(i)] for i in g[:, 1]], dtype=int)
        p_ids = np.array([pmap[int(i)] for i in p[:, 1]], dtype=int)
        if len(set(g_ids.tolist())) != len(g_ids) or len(set(p_ids.tolist())) != len(p_ids):
            raise ValueError("an identity appears twice in the same frame")
        data["gt_ids"].append(g_ids)
        data["tracker_ids"].append(p_ids)
        data["similarity_scores"].append(box_iou_xywh(g[:, 2:6], p[:, 2:6]))
    return data


def _metrics(threshold: float):
    te = load_trackeval()
    return [te.metrics.HOTA(), te.metrics.CLEAR({"THRESHOLD": threshold, "PRINT_CONFIG": False}),
            te.metrics.Identity({"THRESHOLD": threshold, "PRINT_CONFIG": False})]


def evaluate_sequence(gt: np.ndarray, pred: np.ndarray, seq_length: int, threshold: float = 0.5) -> dict[str, dict]:
    """Per-sequence raw TrackEval results, keyed by metric name (HOTA, CLEAR, Identity)."""
    data = prepare_sequence(gt, pred, seq_length)
    return {m.get_name(): m.eval_sequence(data) for m in _metrics(threshold)}


def combine(results: Sequence[dict[str, dict]], threshold: float = 0.5) -> dict[str, dict]:
    """Combine per-sequence results the way TrackEval does (pooled counts, not an average of scores)."""
    keyed = {f"s{i}": r for i, r in enumerate(results)}
    return {m.get_name(): m.combine_sequences({k: v[m.get_name()] for k, v in keyed.items()})
            for m in _metrics(threshold)}


def summarize(combined: dict[str, dict]) -> dict[str, float]:
    """Headline scalars in percent (HOTA family averaged over the 19 alphas, as TrackEval reports)."""
    h, c, i = combined["HOTA"], combined["CLEAR"], combined["Identity"]
    return dict(
        HOTA=100 * float(np.mean(h["HOTA"])), DetA=100 * float(np.mean(h["DetA"])),
        AssA=100 * float(np.mean(h["AssA"])), LocA=100 * float(np.mean(h["LocA"])),
        IDF1=100 * float(i["IDF1"]), IDP=100 * float(i["IDP"]), IDR=100 * float(i["IDR"]),
        MOTA=100 * float(c["MOTA"]), IDSW=int(c["IDSW"]), Frag=int(c["Frag"]),
        MT=int(c["MT"]), PT=int(c["PT"]), ML=int(c["ML"]),
        TP=int(c["CLR_TP"]), FN=int(c["CLR_FN"]), FP=int(c["CLR_FP"]))


def score_sequences(per_seq: Sequence[dict[str, dict]]) -> dict[str, float]:
    return summarize(combine(per_seq))


def metric_on_resample(per_seq: Sequence[dict[str, dict]], key: str = "HOTA"):
    """Metric function for `paired_bootstrap`: combined score of the videos in a multiplicity vector."""
    def fn(weights: np.ndarray) -> float:
        picked = [per_seq[i] for i, w in enumerate(np.asarray(weights, dtype=int)) for _ in range(w)]
        return float("nan") if not picked else summarize(combine(picked))[key]
    return fn


def format_mot_rows(rows: np.ndarray) -> str:
    """Serialise (frame,id,x,y,w,h,conf,...) rows to MOT text."""
    return "\n".join(",".join(f"{v:.6g}" for v in r) for r in rows)
