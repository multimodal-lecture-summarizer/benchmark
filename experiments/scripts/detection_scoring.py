"""Detection scoring for benchmark 03a: pycocotools mAP@[.50:.95] plus a paired-bootstrap-ready cache.

Primary numbers always come from pycocotools (`coco_summary`). `DetectionCache` re-derives the
same AP from the per-image matches pycocotools already computed, so the bootstrap can resample
images/groups without re-running matching. Equality with pycocotools (and with a physically
replicated dataset) is unit-tested.
"""

from __future__ import annotations

import contextlib
import io
import re
from typing import Any, Iterable, Sequence

import numpy as np

STAT_NAMES = ["ap_50_95", "ap50", "ap75", "ap_small", "ap_medium", "ap_large",
              "ar_1", "ar_10", "ar_100", "ar_small", "ar_medium", "ar_large"]


def _coco(gt: dict[str, Any]):
    from pycocotools.coco import COCO
    coco = COCO()
    coco.dataset = {k: v for k, v in gt.items()}
    coco.dataset.setdefault("info", {})
    coco.dataset.setdefault("licenses", [])
    with contextlib.redirect_stdout(io.StringIO()):
        coco.createIndex()
    return coco


def _load_res(coco, preds: list[dict]):
    with contextlib.redirect_stdout(io.StringIO()):
        return coco.loadRes(preds)


def clean_predictions(preds: Iterable[dict], image_ids: set[int] | None = None,
                      cat_ids: set[int] | None = None) -> list[dict]:
    """Keep only predictions for evaluated images/classes; normalise to COCO result format."""
    out = []
    for p in preds:
        if image_ids is not None and p["image_id"] not in image_ids:
            continue
        if cat_ids is not None and p["category_id"] not in cat_ids:
            continue
        out.append(dict(image_id=int(p["image_id"]), category_id=int(p["category_id"]),
                        bbox=[float(v) for v in p["bbox"]], score=float(p["score"])))
    return out


def is_score_less(preds: Sequence[dict]) -> bool:
    """True when every box carries the same score (e.g. Florence-2 <OD>): AP is then bounded."""
    return len(preds) > 0 and len({round(float(p["score"]), 9) for p in preds}) == 1


def apply_failure_policy(preds: Iterable[dict], image_ids: Sequence[int], failed: Iterable[int]) -> dict[str, Any]:
    """Failed images keep their GT but contribute no predictions (counted as misses).

    Returns the predictions to score on all images and the list of successful image ids, so both
    'all images, failures = misses' and 'successful images only' can be reported.
    """
    failed = set(failed)
    all_ids = [i for i in image_ids]
    preds_all = [p for p in preds if p["image_id"] not in failed]
    ok = [i for i in all_ids if i not in failed]
    return dict(preds=preds_all, image_ids_all=all_ids, image_ids_success=ok, n_failed=len(failed & set(all_ids)))


def coco_summary(gt: dict[str, Any], preds: list[dict], image_ids: Sequence[int] | None = None,
                 cat_ids: Sequence[int] | None = None) -> dict[str, float]:
    """Standard pycocotools bbox evaluation; returns the 12 summary statistics (-1 where undefined)."""
    from pycocotools.cocoeval import COCOeval
    coco = _coco(gt)
    image_ids = list(image_ids) if image_ids is not None else sorted(coco.getImgIds())
    cat_ids = list(cat_ids) if cat_ids is not None else sorted(coco.getCatIds())
    preds = clean_predictions(preds, set(image_ids), set(cat_ids))
    if not preds:
        return {name: 0.0 for name in STAT_NAMES}
    dt = _load_res(coco, preds)
    ev = COCOeval(coco, dt, "bbox")
    ev.params.imgIds, ev.params.catIds = image_ids, cat_ids
    with contextlib.redirect_stdout(io.StringIO()):
        ev.evaluate()
        ev.accumulate()
        ev.summarize()
    return dict(zip(STAT_NAMES, (float(s) for s in ev.stats)))


class DetectionCache:
    """Per-image match results from pycocotools, re-aggregated under image multiplicities.

    Only the headline setting is cached (area range 'all', maxDets = 100, IoU .50:.05:.95).
    """

    def __init__(self, gt: dict[str, Any], preds: list[dict], image_ids: Sequence[int] | None = None,
                 cat_ids: Sequence[int] | None = None, max_dets: int = 100):
        from pycocotools.cocoeval import COCOeval
        coco = _coco(gt)
        self.image_ids = list(image_ids) if image_ids is not None else sorted(coco.getImgIds())
        self.cat_ids = list(cat_ids) if cat_ids is not None else sorted(coco.getCatIds())
        self.cat_names = {c["id"]: c["name"] for c in gt["categories"] if c["id"] in set(self.cat_ids)}
        preds = clean_predictions(preds, set(self.image_ids), set(self.cat_ids))
        self.rec_thrs = np.linspace(0.0, 1.0, 101)
        n_img = len(self.image_ids)
        T = 10
        self.per_cat: dict[int, dict[str, np.ndarray]] = {}
        if preds:
            dt = _load_res(coco, preds)
        else:   # no detections at all: only the GT counts matter
            dt = _load_res(coco, [dict(image_id=self.image_ids[0], category_id=self.cat_ids[0], bbox=[0, 0, 1, 1], score=0.0)])
            dt.dataset["annotations"] = []
            dt.anns, dt.imgToAnns = {}, {}
        ev = COCOeval(coco, dt, "bbox")
        ev.params.imgIds, ev.params.catIds = self.image_ids, self.cat_ids
        ev.params.areaRng, ev.params.areaRngLbl = [[0 ** 2, 1e5 ** 2]], ["all"]
        ev.params.maxDets = [max_dets]
        with contextlib.redirect_stdout(io.StringIO()):
            ev.evaluate()
        for k, cid in enumerate(self.cat_ids):
            scores, tp, ign, img_idx = [], [], [], []
            npig_img = np.zeros(n_img, dtype=np.int64)
            for i in range(n_img):
                e = ev.evalImgs[k * n_img + i]
                if e is None:
                    continue
                npig_img[i] = int((np.asarray(e["gtIgnore"]) == 0).sum())
                d = len(e["dtScores"])
                if d:
                    scores.append(np.asarray(e["dtScores"], dtype=float))
                    tp.append(np.asarray(e["dtMatches"]) > 0)
                    ign.append(np.asarray(e["dtIgnore"], dtype=bool))
                    img_idx.append(np.full(d, i, dtype=np.int64))
            self.per_cat[cid] = dict(
                scores=np.concatenate(scores) if scores else np.zeros(0),
                tp=np.concatenate(tp, axis=1) if tp else np.zeros((T, 0), dtype=bool),
                ign=np.concatenate(ign, axis=1) if ign else np.zeros((T, 0), dtype=bool),
                img_idx=np.concatenate(img_idx) if img_idx else np.zeros(0, dtype=np.int64),
                npig_img=npig_img)
            # Stable score order computed once: weights only repeat detections, so the sort never has to be redone.
            self.per_cat[cid]["order"] = np.argsort(-self.per_cat[cid]["scores"], kind="mergesort")

    def _class_ap(self, c: dict[str, np.ndarray], w: np.ndarray) -> np.ndarray | None:
        """AP per IoU threshold for one class under integer image weights; None if no GT."""
        npig = int((w * c["npig_img"]).sum())
        if npig == 0:
            return None
        reps = w[c["img_idx"]]
        order = c["order"]
        sel = np.repeat(order, reps[order])         # copies of one detection stay adjacent, as in a replicated dataset
        if len(sel) == 0:
            return np.zeros(c["tp"].shape[0])
        tp, ign = c["tp"][:, sel], c["ign"][:, sel]
        tps = tp & ~ign
        fps = ~tp & ~ign
        tp_sum = np.cumsum(tps, axis=1).astype(float)
        fp_sum = np.cumsum(fps, axis=1).astype(float)
        ap = np.zeros(tp.shape[0])
        nd = tp.shape[1]
        for t in range(tp.shape[0]):
            rc = tp_sum[t] / npig
            pr = tp_sum[t] / (fp_sum[t] + tp_sum[t] + np.spacing(1))
            pr = np.maximum.accumulate(pr[::-1])[::-1]
            inds = np.searchsorted(rc, self.rec_thrs, side="left")
            q = np.where(inds < nd, pr[np.minimum(inds, nd - 1)], 0.0)
            ap[t] = q.mean()
        return ap

    def metrics(self, weights: np.ndarray | None = None) -> dict[str, Any]:
        n = len(self.image_ids)
        w = np.ones(n, dtype=np.int64) if weights is None else np.asarray(weights, dtype=np.int64)
        per_class = {}
        for cid, c in self.per_cat.items():
            ap = self._class_ap(c, w)
            if ap is not None:
                per_class[self.cat_names.get(cid, cid)] = ap
        if not per_class:
            return dict(map_50_95=float("nan"), ap50=float("nan"), per_class_ap={})
        mat = np.stack(list(per_class.values()))
        return dict(map_50_95=float(mat.mean()), ap50=float(mat[:, 0].mean()), ap75=float(mat[:, 5].mean()),
                    per_class_ap={k: float(v.mean()) for k, v in per_class.items()},
                    per_class_ap50={k: float(v[0]) for k, v in per_class.items()})

    def map_fn(self, key: str = "map_50_95"):
        return lambda w: self.metrics(w)[key]

    def precision_recall(self, conf: float, weights: np.ndarray | None = None) -> dict[str, float]:
        """Diagnostic only: pooled precision/recall at IoU 0.5 for detections with score >= conf."""
        n = len(self.image_ids)
        w = np.ones(n, dtype=np.int64) if weights is None else np.asarray(weights, dtype=np.int64)
        tp_tot = fp_tot = gt_tot = 0
        for c in self.per_cat.values():
            keep = (c["scores"] >= conf) & ~c["ign"][0]
            wt = w[c["img_idx"]][keep]
            tp_tot += int((wt * c["tp"][0][keep]).sum())
            fp_tot += int((wt * ~c["tp"][0][keep]).sum())
            gt_tot += int((w * c["npig_img"]).sum())
        p = tp_tot / (tp_tot + fp_tot) if tp_tot + fp_tot else 0.0
        r = tp_tot / gt_tot if gt_tot else 0.0
        return dict(precision=p, recall=r, tp=tp_tot, fp=fp_tot, fn=gt_tot - tp_tot)


# --------------------------------------------------------------------------
# Open-vocabulary label mapping (frozen taxonomy map)
# --------------------------------------------------------------------------
_ARTICLES = re.compile(r"^(a|an|the)\s+", re.I)


def normalise_label(label: str) -> str:
    return re.sub(r"\s+", " ", _ARTICLES.sub("", label.strip().lower()))


def map_open_vocab(preds: Iterable[dict], taxonomy_map: dict[str, list[str]],
                   name_to_id: dict[str, int]) -> dict[str, Any]:
    """Map free-text `label` of each prediction to a taxonomy category id.

    Unmapped labels are kept out of scoring but counted (`unknown_concept_rate`); the reported
    `taxonomy_mapping_coverage` is the share of predicted boxes whose label was mapped.
    """
    lookup = {normalise_label(s): cat for cat, syns in taxonomy_map.items() for s in syns}
    lookup.update({normalise_label(cat): cat for cat in taxonomy_map})
    mapped, unknown, total = [], 0, 0
    for p in preds:
        total += 1
        cat = lookup.get(normalise_label(p["label"]))
        if cat is None:
            unknown += 1
            continue
        mapped.append(dict(image_id=p["image_id"], category_id=name_to_id[cat], bbox=p["bbox"], score=p["score"]))
    return dict(preds=mapped, unknown_concept_rate=unknown / total if total else 0.0,
                taxonomy_mapping_coverage=(total - unknown) / total if total else 0.0, n_boxes=total)
