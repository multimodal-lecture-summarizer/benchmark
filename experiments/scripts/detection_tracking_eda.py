"""Statistics for the detection/tracking EDA notebook (compute only, no plotting).

Every function is deterministic for a fixed seed and unit-tested on cases with a
hand-derived answer. Cluster-aware statistics are used wherever units are not
independent (LVVO source groups, MOT sequences).
"""

from __future__ import annotations

import io
from collections import OrderedDict
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from experiments.scripts.detection_tracking_qualification import iou_matrix_xywh


# --------------------------------------------------------------------------
# Dependence between units
# --------------------------------------------------------------------------
def design_effect(groups: Sequence, values: Sequence[float]) -> dict[str, float]:
    """One-way ANOVA estimate of the intra-class correlation and the design effect.

    deff = 1 + (m - 1) * icc with m = sum(n_i^2) / N; n_eff = N / deff.
    """
    g = np.asarray(groups)
    v = np.asarray(values, dtype=float)
    uniq, inv, n_i = np.unique(g, return_inverse=True, return_counts=True)
    k, n = len(uniq), len(v)
    if k < 2 or n <= k:
        return dict(n=n, k=k, icc=float("nan"), deff=float("nan"), n_eff=float("nan"))
    means = np.bincount(inv, weights=v) / n_i
    grand = v.mean()
    msb = (n_i * (means - grand) ** 2).sum() / (k - 1)
    msw = ((v - means[inv]) ** 2).sum() / (n - k)
    n0 = (n - (n_i ** 2).sum() / n) / (k - 1)
    denom = msb + (n0 - 1) * msw
    icc = 0.0 if denom <= 0 else max(0.0, (msb - msw) / denom)
    m = (n_i ** 2).sum() / n
    deff = 1 + (m - 1) * icc
    return dict(n=n, k=k, icc=float(icc), deff=float(deff), n_eff=float(n / deff))


def cluster_bootstrap_mean_ci(groups: Sequence, values: Sequence[float], resamples: int = 5000,
                              seed: int = 0, level: float = 0.95) -> dict[str, float]:
    """Percentile CI for the pooled mean, resampling whole groups (ratio estimator)."""
    g = np.asarray(groups)
    v = np.asarray(values, dtype=float)
    uniq, inv = np.unique(g, return_inverse=True)
    sums = np.bincount(inv, weights=v)
    counts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, len(uniq), size=(resamples, len(uniq)))
    est = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
    lo, hi = np.quantile(est, [(1 - level) / 2, 1 - (1 - level) / 2])
    return dict(mean=float(v.mean()), lo=float(lo), hi=float(hi), groups=int(len(uniq)))


class _UnionFind:
    def __init__(self):
        self.parent: dict = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def connected_components(nodes: Iterable, edges: Iterable[tuple]) -> dict:
    """Map every node to a component label (smallest member). Isolated nodes are their own component."""
    uf = _UnionFind()
    for n in nodes:
        uf.find(n)
    for a, b in edges:
        uf.union(a, b)
    return {n: uf.find(n) for n in uf.parent}


def merged_group_labels(items_to_group: dict, edges: Iterable[tuple]) -> dict:
    """Merge source groups that are linked by at least one near-duplicate edge between items."""
    uf = _UnionFind()
    for item, grp in items_to_group.items():
        uf.find(grp)
    for a, b in edges:
        uf.union(items_to_group[a], items_to_group[b])
    return {item: uf.find(grp) for item, grp in items_to_group.items()}


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    """Normalised cross-correlation of two equally-sized arrays (objective similarity, in [-1, 1])."""
    x = np.asarray(a, dtype=float).ravel()
    y = np.asarray(b, dtype=float).ravel()
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return 0.0 if d == 0 else float((x * y).sum() / d)


def content_crop(gray: np.ndarray, dark: float = 12.0) -> np.ndarray:
    """Remove letter/pillar-box bars: drop outer rows/columns that are uniformly very dark."""
    g = np.asarray(gray, dtype=float)
    cols = np.flatnonzero((g.mean(axis=0) > dark) | (g.std(axis=0) > 6))
    rows = np.flatnonzero((g.mean(axis=1) > dark) | (g.std(axis=1) > 6))
    if len(cols) == 0 or len(rows) == 0:
        return g
    return g[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


def _resize(arr: np.ndarray, size: int) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((size, size), Image.Resampling.BILINEAR), dtype=float)


def ink_mask(gray: np.ndarray, size: int = 128, delta: float = 40.0) -> np.ndarray:
    """Foreground ('ink') mask of a slide-like frame after removing bars: |pixel - median| > delta."""
    small = _resize(content_crop(gray), size)
    return np.abs(small - np.median(small)) > delta


def slide_jaccard(a: np.ndarray, b: np.ndarray, size: int = 128, delta: float = 40.0) -> float:
    """Jaccard overlap of the ink masks of the central slide region of two frames, in [0, 1].

    Letter/pillar bars are removed and only the central 60% x 80% of the remaining frame is compared, so
    window chrome, participant lists and webcam overlays at the edges (shared by all frames of a lecture)
    do not inflate the score. It is a weak screening measure, not proof of identity: the notebook shows
    calibration examples because it can still score different slides with a similar layout highly.
    """
    def central(g):
        c = content_crop(g)
        h, w = c.shape
        return c[int(.1 * h):int(.9 * h), int(.12 * w):int(.72 * w)]

    ma, mb = ink_mask(central(a), size, delta), ink_mask(central(b), size, delta)
    union = (ma | mb).sum()
    return float((ma & mb).sum() / union) if union else 0.0

# --------------------------------------------------------------------------
# Two-sample comparison with multiplicity control
# --------------------------------------------------------------------------
def compare_samples(a: Sequence[float], b: Sequence[float]) -> dict[str, float]:
    """KS statistic, Mann-Whitney p and Cliff's delta (positive: a tends to exceed b)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ks = stats.ks_2samp(a, b)
    mw = stats.mannwhitneyu(a, b, alternative="two-sided")
    return dict(n_a=len(a), n_b=len(b), median_a=float(np.median(a)), median_b=float(np.median(b)),
                ks=float(ks.statistic), p_ks=float(ks.pvalue), p_mw=float(mw.pvalue),
                cliffs_delta=float(2 * mw.statistic / (len(a) * len(b)) - 1))


def holm_adjust(p: Sequence[float]) -> np.ndarray:
    """Holm-Bonferroni adjusted p-values (monotone, capped at 1)."""
    p = np.asarray(p, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def effect_label(delta: float) -> str:
    """Romano thresholds for |Cliff's delta|."""
    d = abs(delta)
    return "negligible" if d < 0.147 else "small" if d < 0.33 else "medium" if d < 0.474 else "large"


def max_overlap_stats(boxes: np.ndarray) -> dict[str, np.ndarray]:
    """For (n,4) xywh boxes of one image: per-box max IoU and max containment with any other box.

    Containment = intersection / area of the smaller box (1.0 means one box lies inside the other).
    """
    n = len(boxes)
    if n < 2:
        return dict(max_iou=np.zeros(n), max_containment=np.zeros(n))
    x1, y1 = boxes[:, 0], boxes[:, 1]
    x2, y2 = x1 + boxes[:, 2], y1 + boxes[:, 3]
    iw = np.clip(np.minimum(x2[:, None], x2[None]) - np.maximum(x1[:, None], x1[None]), 0, None)
    ih = np.clip(np.minimum(y2[:, None], y2[None]) - np.maximum(y1[:, None], y1[None]), 0, None)
    inter = iw * ih
    area = boxes[:, 2] * boxes[:, 3]
    smaller = np.minimum(area[:, None], area[None])
    contain = np.divide(inter, smaller, out=np.zeros_like(inter, dtype=float), where=smaller > 0)
    np.fill_diagonal(contain, 0.0)
    return dict(max_iou=iou_matrix_xywh(boxes).max(axis=1), max_containment=contain.max(axis=1))


# --------------------------------------------------------------------------
# MOT ground-truth analytics
# --------------------------------------------------------------------------
def mot_track_table(gt: np.ndarray) -> pd.DataFrame:
    """One row per identity: appearances, span, number and length of gaps, median height."""
    frames, ids = gt[:, 0].astype(int), gt[:, 1].astype(int)
    rows = []
    order = np.lexsort((frames, ids))
    f_sorted, i_sorted, h_sorted = frames[order], ids[order], gt[order, 5]
    bounds = np.flatnonzero(np.diff(i_sorted)) + 1
    for f, h, tid in zip(np.split(f_sorted, bounds), np.split(h_sorted, bounds),
                         i_sorted[np.r_[0, bounds]]):
        gaps = np.diff(f) - 1
        gaps = gaps[gaps > 0]
        rows.append(dict(id=int(tid), n_frames=len(f), span=int(f[-1] - f[0] + 1), n_gaps=len(gaps),
                         max_gap=int(gaps.max()) if len(gaps) else 0, missing=int(gaps.sum()),
                         h_median=float(np.median(h))))
    return pd.DataFrame(rows)


def mot_gap_lengths(gt: np.ndarray) -> np.ndarray:
    """Lengths (frames) of every interruption of an identity (re-appearance after absence)."""
    frames, ids = gt[:, 0].astype(int), gt[:, 1].astype(int)
    order = np.lexsort((frames, ids))
    f, i = frames[order], ids[order]
    d = np.diff(f) - 1
    same = i[1:] == i[:-1]
    return d[same & (d > 0)]


def mot_motion(gt: np.ndarray, moving_eps: float = 0.01) -> dict[str, np.ndarray]:
    """Per-step normalised speed (centre displacement / box height per frame) and turn angles.

    Only consecutive frames are used. Turn angle (deg, 0-180) is computed for pairs of steps
    where both speeds exceed `moving_eps`; large angles indicate non-linear motion.
    """
    frames, ids = gt[:, 0].astype(int), gt[:, 1].astype(int)
    order = np.lexsort((frames, ids))
    f, i, g = frames[order], ids[order], gt[order]
    cx, cy, h = g[:, 2] + g[:, 4] / 2, g[:, 3] + g[:, 5] / 2, np.maximum(g[:, 5], 1e-6)
    step = (i[1:] == i[:-1]) & (f[1:] - f[:-1] == 1)
    dx, dy = (cx[1:] - cx[:-1])[step], (cy[1:] - cy[:-1])[step]
    speed = np.hypot(dx, dy) / h[1:][step]
    # angle between consecutive steps of the same track
    idx = np.flatnonzero(step)
    pair = (idx[1:] == idx[:-1] + 1)
    d1x, d1y, d2x, d2y = dx[:-1][pair], dy[:-1][pair], dx[1:][pair], dy[1:][pair]
    s1, s2 = speed[:-1][pair], speed[1:][pair]
    ok = (s1 > moving_eps) & (s2 > moving_eps)
    cos = (d1x * d2x + d1y * d2y)[ok] / (np.hypot(d1x, d1y)[ok] * np.hypot(d2x, d2y)[ok])
    return dict(speed=speed, turn_deg=np.degrees(np.arccos(np.clip(cos, -1, 1))))


def mot_frame_overlap(gt: np.ndarray, close_iou: float = 0.5, occ_iou: float = 0.3) -> dict[str, np.ndarray]:
    """Per-box max IoU with another GT box in the same frame, and per-frame close-pair counts."""
    frames = gt[:, 0].astype(int)
    boxes = gt[:, 2:6]
    max_iou = np.zeros(len(gt))
    uniq, start = np.unique(frames, return_index=True)
    order = np.argsort(frames, kind="stable")
    sorted_frames = frames[order]
    bounds = np.r_[np.searchsorted(sorted_frames, uniq, side="left"), len(order)]
    close_pairs = np.zeros(len(uniq), dtype=int)
    for k in range(len(uniq)):
        rows = order[bounds[k]:bounds[k + 1]]
        if len(rows) < 2:
            continue
        iou = iou_matrix_xywh(boxes[rows])
        max_iou[rows] = iou.max(axis=1)
        close_pairs[k] = int((np.triu(iou, 1) > close_iou).sum())
    return dict(max_iou=max_iou, close_pairs=close_pairs, frames=uniq,
                occluded=max_iou > occ_iou)


def id_lifelines(gt: np.ndarray, occ_iou: float = 0.3) -> pd.DataFrame:
    """Run-length segments per identity: (id, start, end, occluded).

    A segment is a maximal run of consecutive frames with the same occlusion flag (box IoU > occ_iou
    with another box of that frame). Gaps in presence split segments, so absences stay blank in a Gantt.
    """
    occ = mot_frame_overlap(gt, occ_iou=occ_iou)["max_iou"] > occ_iou
    frames, ids = gt[:, 0].astype(int), gt[:, 1].astype(int)
    order = np.lexsort((frames, ids))
    f, i, o = frames[order], ids[order], occ[order]
    brk = np.flatnonzero((np.diff(i) != 0) | (np.diff(f) != 1) | (o[1:] != o[:-1])) + 1
    starts, ends = np.r_[0, brk], np.r_[brk, len(f)] - 1
    return pd.DataFrame(dict(id=i[starts], start=f[starts], end=f[ends], occluded=o[starts]))


def id_confusion_pairs(gt: np.ndarray, near: float = 0.5, cross_near: float = 1.0) -> dict[str, float]:
    """Counts that predict ID switches: how often two identities are close, and how often they swap sides.

    close_pair_frames: (pair, frame) cases with centre distance < near * mean box height.
    crossings: consecutive co-present frames where the x-order of two identities flips while the pair is
    within cross_near * mean box height at both frames (trajectories cross, not just drift far apart).
    """
    frames = gt[:, 0].astype(int)
    order = np.argsort(frames, kind="stable")
    uniq, start = np.unique(frames[order], return_index=True)
    bounds = np.r_[start, len(order)]
    close = crossings = 0
    prev: dict[tuple[int, int], tuple[int, float]] = {}
    for k, fr in enumerate(uniq):
        g = gt[order[bounds[k]:bounds[k + 1]]]
        if len(g) < 2:
            continue
        ids = g[:, 1].astype(int)
        cx, cy, h = g[:, 2] + g[:, 4] / 2, g[:, 3] + g[:, 5] / 2, g[:, 5]
        hm = (h[:, None] + h[None]) / 2
        dx = cx[:, None] - cx[None]
        dist = np.hypot(dx, cy[:, None] - cy[None]) / np.maximum(hm, 1e-6)
        for a, b in zip(*np.triu_indices(len(g), 1)):
            key = (min(ids[a], ids[b]), max(ids[a], ids[b]))
            sign = dx[a, b] if ids[a] < ids[b] else -dx[a, b]
            near_now = dist[a, b] < cross_near
            close += dist[a, b] < near
            if key in prev and prev[key][0] == fr - 1 and near_now and prev[key][2] and sign * prev[key][1] < 0:
                crossings += 1
            prev[key] = (fr, sign, near_now)
    return dict(close_pair_frames=int(close), crossings=int(crossings))


# --------------------------------------------------------------------------
# Frozen stratification and dev subset (decided on train before any tracker score exists)
# --------------------------------------------------------------------------
def tertile_edges(train_values: Sequence[float]) -> tuple[float, float]:
    """Cut points at the 1/3 and 2/3 quantiles of the train distribution."""
    lo, hi = np.quantile(np.asarray(train_values, dtype=float), [1 / 3, 2 / 3])
    return float(lo), float(hi)


def assign_tier(values: Sequence[float], edges: tuple[float, float]) -> list[str]:
    """low: v <= e1 < mid: v <= e2 < high. Edges come from train and are applied unchanged to val."""
    lo, hi = edges
    return ["low" if v <= lo else "mid" if v <= hi else "high" for v in values]


def stratify_sequences(df: pd.DataFrame, axes: dict[str, str], moving_px: float = 1.0,
                       cam_col: str = "cam_shift_median") -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    """Add one tier column per axis (name -> feature column) plus `camera` (static/moving).

    Edges use train rows only. No composite difficulty score is built.
    """
    train = df[df.split == "train"]
    edges = {name: tertile_edges(train[col]) for name, col in axes.items()}
    out = df.copy()
    for name, col in axes.items():
        out[f"tier_{name}"] = assign_tier(out[col], edges[name])
    out["camera"] = np.where(out[cam_col] > moving_px, "moving", "static")
    return out, edges


def select_dev_subset(strata: pd.DataFrame, n: int, seed: int, tier_cols: Sequence[str],
                      min_per_tier: int = 2, require_moving: bool = True, max_tries: int = 20000) -> list[str]:
    """Seeded random draw of n train sequences covering every tier of every axis >= min_per_tier times.

    The first draw satisfying the constraints is returned (deterministic for a seed). Raises if none exists.
    """
    pool = strata[strata.split == "train"].reset_index(drop=True)
    rng = np.random.default_rng(seed)
    for _ in range(max_tries):
        pick = pool.iloc[rng.choice(len(pool), size=n, replace=False)]
        if require_moving and not (pick.camera == "moving").any():
            continue
        if all((pick[c].value_counts().reindex(["low", "mid", "high"]).fillna(0) >= min_per_tier).all() for c in tier_cols):
            return sorted(pick.seq.tolist())
    raise ValueError("no dev subset satisfies the coverage constraints; relax min_per_tier or n")


def coverage_vs_reference(dev: pd.DataFrame, ref: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Per feature: dev range, reference range, and the dev sequences outside the reference range."""
    rows = {}
    for c in cols:
        lo, hi = ref[c].min(), ref[c].max()
        out = dev[(dev[c] < lo) | (dev[c] > hi)]
        rows[c] = dict(dev_min=dev[c].min(), dev_max=dev[c].max(), ref_min=lo, ref_max=hi,
                       n_outside=len(out), outside=",".join(out.seq))
    return pd.DataFrame(rows).T


# --------------------------------------------------------------------------
# HTTP range access to a remote ZIP (read only the members we need)
# --------------------------------------------------------------------------
class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over an HTTP server that supports Range requests."""

    def __init__(self, url: str, block: int = 1 << 20, cache_blocks: int = 64, session=None):
        import requests
        self.url, self.block = url, block
        self.session = session or requests.Session()
        head = self.session.get(url, headers={"Range": "bytes=0-0"}, timeout=60)
        head.raise_for_status()
        self.size = int(head.headers["Content-Range"].split("/")[-1])
        self.pos = 0
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._max = cache_blocks

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def _block(self, index: int) -> bytes:
        if index in self._cache:
            self._cache.move_to_end(index)
            return self._cache[index]
        start = index * self.block
        end = min(start + self.block, self.size) - 1
        last = None
        for attempt in range(4):
            try:
                r = self.session.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
                r.raise_for_status()
                break
            except Exception as exc:  # retry transient network errors
                last = exc
        else:
            raise ConnectionError(f"{self.url}: {last!r}")
        self._cache[index] = r.content
        if len(self._cache) > self._max:
            self._cache.popitem(last=False)
        return r.content

    def read(self, n=-1):
        if n < 0 or self.pos + n > self.size:
            n = self.size - self.pos
        if n <= 0:
            return b""
        out = bytearray()
        while n > 0:
            idx, off = divmod(self.pos, self.block)
            chunk = self._block(idx)[off:off + n]
            if not chunk:
                break
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)
