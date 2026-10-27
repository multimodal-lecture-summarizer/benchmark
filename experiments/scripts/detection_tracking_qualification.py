"""Dataset qualification helpers for detection (03a) and tracking (03b).

Pure functions so the Colab notebook and the unit tests share one implementation.
Nothing here downloads data or runs a model.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

# Frozen by the claim-freeze decision report (2026-10-26).
COCO_TAXONOMY = {  # COCO category id -> name
    1: "person", 44: "bottle", 62: "chair", 72: "tv", 73: "laptop",
    74: "mouse", 76: "keyboard", 77: "cell phone", 84: "book", 85: "clock",
}
PRACTICAL_THRESHOLDS = {"delta_map_50_95": 0.02, "delta_hota": 2.0}
BOOTSTRAP = {"resamples": 10000, "ci": 0.95, "method": "paired_percentile"}
COCO_SIZE_EDGES = (32 ** 2, 96 ** 2)  # COCO small/medium/large area edges


# --------------------------------------------------------------------------
# Hashing, archives
# --------------------------------------------------------------------------
def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def safe_extract(archive: Path, destination: Path,
                 keep: Callable[[str], bool] = lambda name: True) -> list[str]:
    """Extract members accepted by `keep`; reject traversal and symlinks. CRC checked."""
    destination = Path(destination).resolve()
    extracted: list[str] = []
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename
            if info.is_dir() or name.startswith("__MACOSX/") or name.endswith(".DS_Store"):
                continue
            if not keep(name):
                continue
            target = (destination / name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError(f"Unsafe archive path: {name}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Symlink in archive: {name}")
            if target.exists() and target.stat().st_size == info.file_size:
                extracted.append(name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as dst:
                dst.write(src.read())
            extracted.append(name)
    return extracted


def reconcile(raw: int, eligible: int, excluded: int, unresolved: int) -> dict[str, int]:
    """Enforce raw = eligible + excluded + unresolved; never drop units silently."""
    if raw != eligible + excluded + unresolved:
        raise ValueError(
            f"Denominator mismatch: raw={raw} eligible={eligible} "
            f"excluded={excluded} unresolved={unresolved}")
    return dict(raw=raw, eligible=eligible, excluded=excluded, unresolved=unresolved)


def exact_overlap(left: Iterable[str], right: Iterable[str]) -> list[str]:
    return sorted(set(left) & set(right))


# --------------------------------------------------------------------------
# Box helpers
# --------------------------------------------------------------------------
def size_stratum(area: float) -> str:
    small, medium = COCO_SIZE_EDGES
    return "small" if area < small else "medium" if area < medium else "large"


def iou_matrix_xywh(boxes: np.ndarray) -> np.ndarray:
    """Pairwise IoU for an (n,4) xywh array; diagonal set to 0."""
    n = len(boxes)
    if n == 0:
        return np.zeros((0, 0))
    x1, y1 = boxes[:, 0], boxes[:, 1]
    x2, y2 = x1 + boxes[:, 2], y1 + boxes[:, 3]
    iw = np.clip(np.minimum(x2[:, None], x2[None]) - np.maximum(x1[:, None], x1[None]), 0, None)
    ih = np.clip(np.minimum(y2[:, None], y2[None]) - np.maximum(y1[:, None], y1[None]), 0, None)
    inter = iw * ih
    area = boxes[:, 2] * boxes[:, 3]
    union = area[:, None] + area[None] - inter
    iou = np.divide(inter, union, out=np.zeros_like(inter, dtype=float), where=union > 0)
    np.fill_diagonal(iou, 0.0)
    return iou


# --------------------------------------------------------------------------
# Detection A: LVVO -> COCO
# --------------------------------------------------------------------------
def lvvo_to_coco(dataset_root: Path) -> dict[str, Any]:
    """Convert the released LVVO 1k four-class labels to COCO JSON.

    Image ids are 1-based over sorted file stems (stable). Invalid boxes and
    unreadable pairs go to `excluded`, never silently dropped. Images with zero
    valid boxes stay in the image list as valid negatives.
    """
    from PIL import Image

    root = Path(dataset_root)
    meta = json.loads((root / "dataset_info.json").read_text(encoding="utf-8"))
    categories = [{"id": int(v), "name": k} for k, v in sorted(meta["categories"].items(), key=lambda kv: int(kv[1]))]
    class_names = {c["id"]: c["name"] for c in categories}
    image_paths = {p.stem: p for p in (root / "images").glob("*.jpg")}
    label_paths = {p.stem: p for p in (root / "labels").glob("*.json")}
    images, annotations, excluded, ledger = [], [], [], []
    next_ann = 1
    for index, stem in enumerate(sorted(image_paths.keys() | label_paths.keys()), start=1):
        ip, lp = image_paths.get(stem), label_paths.get(stem)
        if ip is None or lp is None:
            excluded.append(dict(stem=stem, reason="missing_pair"))
            continue
        try:
            with Image.open(ip) as im:
                im.load()
                width, height = im.size
            labels = json.loads(lp.read_text(encoding="utf-8"))
        except Exception as exc:  # decode/parse failure is counted, not hidden
            excluded.append(dict(stem=stem, reason=f"read_error:{type(exc).__name__}"))
            continue
        valid_boxes = 0
        for obj in labels.get("objects", []):
            b = obj.get("boundingBox", {})
            x1, y1, x2, y2 = (b.get(k) for k in ("xmin", "ymin", "xmax", "ymax"))
            numeric = all(isinstance(v, (int, float)) for v in (x1, y1, x2, y2))
            cid = obj.get("class")
            if not (numeric and 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height) or cid not in class_names:
                excluded.append(dict(stem=stem, reason="invalid_box_or_class", box=[x1, y1, x2, y2], cls=cid))
                continue
            w, h = x2 - x1, y2 - y1
            annotations.append(dict(id=next_ann, image_id=index, category_id=int(cid),
                                    bbox=[float(x1), float(y1), float(w), float(h)],
                                    area=float(w * h), iscrowd=0))
            next_ann += 1
            valid_boxes += 1
        images.append(dict(id=index, file_name=ip.name, width=width, height=height))
        inst = re.match(r"i(\d+)_", stem)
        course = re.search(r"_c(\d+)_", stem)
        video = re.search(r"_v(\d+)_", stem)
        ledger.append(dict(image_id=index, stem=stem, file_name=ip.name, width=width, height=height,
                           n_boxes=valid_boxes,
                           group="/".join(f"{k}{m.group(1)}" for k, m in
                                          (("i", inst), ("c", course), ("v", video)) if m),
                           sha256=sha256_file(ip)))
    return dict(coco=dict(images=images, annotations=annotations, categories=categories),
                excluded=excluded, ledger=ledger, class_names=class_names,
                stems_total=len(image_paths.keys() | label_paths.keys()),
                released_images=len(image_paths), released_labels=len(label_paths))


def dhash64(path: Path) -> int:
    from PIL import Image
    with Image.open(path) as im:
        arr = np.asarray(im.convert("L").resize((9, 8), Image.Resampling.LANCZOS))
    bits = (arr[:, 1:] > arr[:, :-1]).ravel()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def near_duplicate_pairs(hashes: dict[str, int], groups: dict[str, str],
                         sha: dict[str, str], max_distance: int = 4) -> list[dict[str, Any]]:
    """All non-identical pairs within dHash Hamming distance; review flags only."""
    keys = sorted(hashes)
    values = np.array([hashes[k] for k in keys], dtype=np.uint64)
    pairs = []
    for i in range(len(keys) - 1):
        xor = values[i] ^ values[i + 1:]
        dist = np.array([int(v).bit_count() for v in xor])
        for j in np.nonzero(dist <= max_distance)[0]:
            other = keys[i + 1 + int(j)]
            if sha[keys[i]] == sha[other]:
                continue
            pairs.append(dict(left=keys[i], right=other, distance=int(dist[j]),
                              same_group=groups[keys[i]] == groups[other]))
    return pairs


# --------------------------------------------------------------------------
# Detection B: COCO subset
# --------------------------------------------------------------------------
def select_coco_subset(coco: dict[str, Any], n_images: int, seed: int,
                       taxonomy: dict[int, str] = COCO_TAXONOMY) -> dict[str, Any]:
    """Seeded subset: per-class quota of images, balanced over box-size strata, then fill.

    Eligible image = at least one non-crowd taxonomy box. Result is deterministic
    for (coco, n_images, seed).
    """
    rng = np.random.default_rng(seed)
    by_image: dict[int, list[dict]] = {}
    for ann in coco["annotations"]:
        if ann["category_id"] in taxonomy and not ann.get("iscrowd", 0):
            by_image.setdefault(ann["image_id"], []).append(ann)
    eligible = sorted(by_image)
    # (class, stratum) -> sorted candidate image ids
    cell: dict[tuple[int, str], list[int]] = {}
    for image_id in eligible:
        for ann in by_image[image_id]:
            cell.setdefault((ann["category_id"], size_stratum(ann["area"])), []).append(image_id)
    cell = {k: sorted(set(v)) for k, v in cell.items()}
    class_images = {c: sorted({i for (cc, _), v in cell.items() if cc == c for i in v}) for c in taxonomy}
    quota = max(1, n_images // len(taxonomy))
    selected: set[int] = set()
    for cid in sorted(taxonomy, key=lambda c: (len(class_images[c]), c)):  # rarest first
        members = set(class_images[cid])
        have = lambda: len(selected & members)
        strata = [s for s in ("small", "medium", "large") if cell.get((cid, s))]
        pools = {s: list(rng.permutation(cell[(cid, s)])) for s in strata}
        while strata and have() < quota and len(selected) < n_images:
            for s in list(strata):
                while pools[s] and pools[s][-1] in selected:
                    pools[s].pop()
                if not pools[s]:
                    strata.remove(s)
                    continue
                selected.add(int(pools[s].pop()))
                if have() >= quota or len(selected) >= n_images:
                    break
    remaining = [i for i in eligible if i not in selected]
    need = min(n_images, len(eligible)) - len(selected)
    if need > 0:
        selected.update(int(i) for i in rng.permutation(remaining)[:need])
    ids = sorted(selected)
    keep = set(ids)
    anns = [a for a in coco["annotations"] if a["image_id"] in keep and a["category_id"] in taxonomy]
    return dict(image_ids=ids, annotations=anns,
                eligible_images=len(eligible), seed=seed, n_images=n_images,
                quota_per_class=quota)


# --------------------------------------------------------------------------
# Tracking: MOT-format GT
# --------------------------------------------------------------------------
MOT_MEMBER = re.compile(
    r"(?:^|.*/)(?P<split>train|val|test)/(?P<seq>[^/]+)/"
    r"(?P<kind>seqinfo\.ini|gt/gt\.txt|img1/(?P<frame>\d+)\.jpg)$")


_MEMBER_TAIL = re.compile(
    r"(?:^|.*/)(?P<seq>[^/]+)/(?P<kind>seqinfo\.ini|gt/gt\.txt|img1/(?P<frame>\d+)\.jpg)$")
_SPLIT_DIR = re.compile(r"^(train|val|test)\d*$", re.I)


def parse_mot_member(name: str, default_split: str | None = None) -> dict[str, str] | None:
    """Classify an archive member of a MOT-style dataset.

    The split is the nearest ancestor directory named train*/val*/test* (so `train1/seq/...`
    counts as train), else `default_split` (typically taken from the archive file name).
    """
    m = _MEMBER_TAIL.match(name)
    if not m or m["seq"] in (".", ".."):
        return None
    dirs = name.split("/")
    ancestors = dirs[: -(2 if m["kind"] == "seqinfo.ini" else 3)]  # drop seq dir (+ gt/img1) and file
    split = next((_SPLIT_DIR.match(p).group(1).lower() for p in reversed(ancestors) if _SPLIT_DIR.match(p)),
                 default_split)
    if split is None:
        return None
    return dict(split=split, seq=m["seq"], kind=m["kind"], frame=m["frame"])


def parse_seqinfo(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def sample_frame_indices(seq_length: int, pairs: int = 8) -> list[int]:
    """Frame numbers (1-based): first, last, and `pairs` consecutive pairs spread over the video."""
    if seq_length <= 0:
        return []
    picks = {1, seq_length}
    for k in range(pairs):
        t = 1 + int(round(k * max(seq_length - 2, 0) / max(pairs, 1)))
        picks.update({t, min(t + 1, seq_length)})
    return sorted(picks)


def parse_mot_gt(text: str) -> np.ndarray:
    rows = [r for r in (line.strip().split(",") for line in text.splitlines()) if len(r) >= 6]
    if not rows:
        return np.zeros((0, 9))
    width = max(len(r) for r in rows)
    arr = np.full((len(rows), max(width, 9)), np.nan)
    for i, r in enumerate(rows):
        arr[i, :len(r)] = [float(v) for v in r]
    return arr


def mot_sequence_stats(gt: np.ndarray, seq_length: int, im_width: int, im_height: int) -> dict[str, Any]:
    """Per-sequence EDA: density, track lengths, ID integrity, occlusion proxy."""
    if len(gt) == 0:
        return dict(boxes=0, tracks=0, issues=["empty_gt"])
    frames, ids = gt[:, 0].astype(int), gt[:, 1].astype(int)
    boxes = gt[:, 2:6]
    dup_frame_id = len(gt) - len({(f, i) for f, i in zip(frames, ids)})
    bad_size = int(((boxes[:, 2] <= 0) | (boxes[:, 3] <= 0)).sum())
    out_of_range = int(((frames < 1) | (frames > seq_length)).sum())
    off_image = int(((boxes[:, 0] + boxes[:, 2] < 0) | (boxes[:, 1] + boxes[:, 3] < 0) |
                     (boxes[:, 0] > im_width) | (boxes[:, 1] > im_height)).sum())
    track_len, gap_tracks = [], 0
    for tid in np.unique(ids):
        f = np.sort(frames[ids == tid])
        track_len.append(len(f))
        if f[-1] - f[0] + 1 != len(f):
            gap_tracks += 1
    per_frame = np.bincount(frames[(frames >= 1) & (frames <= seq_length)], minlength=seq_length + 1)[1:]
    occluded = 0
    for f in np.unique(frames):
        b = boxes[frames == f]
        if len(b) > 1:
            occluded += int((iou_matrix_xywh(b).max(axis=1) > 0.3).sum())
    conf = gt[:, 6] if gt.shape[1] > 6 else np.ones(len(gt))
    return dict(
        boxes=int(len(gt)), tracks=int(len(track_len)), frames_with_boxes=int((per_frame > 0).sum()),
        seq_length=int(seq_length), boxes_per_frame_mean=float(per_frame.mean()),
        boxes_per_frame_max=int(per_frame.max()),
        track_len_min=int(min(track_len)), track_len_median=float(np.median(track_len)),
        track_len_max=int(max(track_len)), tracks_with_gaps=int(gap_tracks),
        duplicate_frame_id_rows=int(dup_frame_id), nonpositive_size_rows=bad_size,
        frame_out_of_range_rows=out_of_range, off_image_rows=off_image,
        ignored_conf0_rows=int((np.nan_to_num(conf, nan=1.0) == 0).sum()),
        occluded_box_fraction=float(occluded / len(gt)),
        box_height_median=float(np.median(boxes[:, 3])),
        ids_valid=bool((ids >= 0).all() and (gt[:, 1] == ids).all()),  # DanceTrack ids start at 0
    )


def mot_blocking_issues(stats: dict[str, Any]) -> int:
    return int(stats.get("duplicate_frame_id_rows", 0) + stats.get("nonpositive_size_rows", 0)
               + stats.get("frame_out_of_range_rows", 0) + (0 if stats.get("ids_valid", True) else 1)
               + (1 if "empty_gt" in stats.get("issues", []) else 0))


def camera_motion_pixels(gray_pairs: list[tuple[np.ndarray, np.ndarray]]) -> float:
    """Median global shift (px) between consecutive frames via phase correlation.

    A descriptive proxy for static vs moving camera, not a ground-truth label.
    """
    import cv2

    shifts = []
    for a, b in gray_pairs:
        (dx, dy), _ = cv2.phaseCorrelate(np.float32(a), np.float32(b))
        shifts.append(float(np.hypot(dx, dy)))
    return float(np.median(shifts)) if shifts else float("nan")


# --------------------------------------------------------------------------
# Decision
# --------------------------------------------------------------------------
def qualification_decision(*, license_verified: bool, license_ack: bool, blocking_qa: int,
                           exact_leakage: int, acquired: bool, claim_scope_ok: bool = True) -> dict[str, str]:
    """keep / repair / restrict / reject for one dataset, with the reason."""
    if not acquired:
        return dict(decision="HOLD", reason="data not acquired in this run")
    if not license_verified:
        return dict(decision="REJECT", reason="license not verified from official source (plan rule)")
    if not license_ack:
        return dict(decision="HOLD", reason="license text shown but not acknowledged by the user")
    if exact_leakage:
        return dict(decision="REPAIR", reason=f"{exact_leakage} exact dev/eval overlaps")
    if blocking_qa:
        return dict(decision="REPAIR", reason=f"{blocking_qa} blocking QA issues")
    if not claim_scope_ok:
        return dict(decision="RESTRICT", reason="claim scope narrower than requested")
    return dict(decision="KEEP", reason="all gates passed for the scoped protocol")
