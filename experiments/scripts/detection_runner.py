"""Runner for benchmark 03a (object detection): adapters, resumable inference, scoring and budget gate.

Model-specific imports are lazy, so the scoring/bookkeeping logic is importable and unit-testable
without a GPU. All adapters share one decoding path (PIL RGB, no EXIF rotation) and one output
contract: a list of {label, bbox=[x, y, w, h] in pixels, score}.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from experiments.scripts import detection_scoring as ds

# SHA-256 of the vendored Florence-2 checkout used by the product (florence_runtime.py).
FLORENCE_ASSET_SHA256 = {
    "model.safetensors": "03075d2d2d2bbd3e180b9ba0afae4aa8563226e2d32911656966e05b2f2ee060",
    "config.json": "c666d0fe0172d46e115e8fba6cd93cd83714575b33a73005cab8d24ce2a3aa8f",
    "configuration_florence2.py": "4b351d78012df1bcd0f21ce8b8cb3a82fa6f1790a65b2985d21d6e626f76b603",
    "modeling_florence2.py": "d0bd64290a87a46cbb9f4eccfa8c58227b1fd301b9039b1b687d413ead6effac",
    "preprocessor_config.json": "2f5921bbc53c7cc04251e1027b45b1cec726276be6db23d1bb40641bfbe2cf29",
    "processing_florence2.py": "f146023a507c009f425a49ee39aa037f4f25c64e14336e3e4f3f1d7377a68e98",
    "tokenizer.json": "847bbeab6174d66a88898f729d52fa8d355fafe1bea101cf960dd404581df70e",
    "tokenizer_config.json": "79ffcf43af8ebda99d165f61d243180da2e2639952e41e71e11611c18770489c",
    "vocab.json": "394fdc63c71aabe0a9b97117f5d62fb5fcc4d59b2b3ea929a3929e6a53217b3c",
}

# Fixed inference settings (registered before any score is seen).
DEFAULTS = dict(
    conf=0.001,         # mAP needs the full precision-recall curve; 0.25 is only for P/R diagnostics
    iou_nms=0.7,        # ultralytics default NMS IoU
    max_det=100,
    diag_conf=0.25,
    imgsz=640,
    gdino_box_threshold=0.01,
    florence_task="<OD>",
    florence_num_beams=3,
    florence_max_new_tokens=1024,
    warmup_images=3,
    max_seconds_per_image=120.0,
)


@dataclass
class Candidate:
    id: str
    display: str
    family: str
    vocabulary: str               # 'closed' (COCO-80 names) or 'open' (free text mapped to the taxonomy)
    adapter: str
    params: dict[str, Any] = field(default_factory=dict)
    score_less: bool = False
    tracks: tuple[str, ...] = ("D-A", "D-B")   # closed COCO models have no LVVO classes: D-B only


CANDIDATES: list[Candidate] = [
    Candidate("yolov8n", "YOLOv8n (COCO-80)", "cnn_realtime", "closed", "yolo", dict(weights="yolov8n.pt"), tracks=("D-B",)),
    Candidate("yolo11n", "YOLO11n (COCO-80)", "cnn_realtime", "closed", "yolo", dict(weights="yolo11n.pt"), tracks=("D-B",)),
    Candidate("rtdetr_r18", "RT-DETR-R18vd (COCO-80, HF PekingU/rtdetr_r18vd)", "detr_realtime", "closed", "rtdetr_hf",
              dict(repo="PekingU/rtdetr_r18vd"), tracks=("D-B",)),
    Candidate("florence2_base", "Florence-2-base <OD> (open, score-less)", "vlm", "open", "florence",
              dict(task=DEFAULTS["florence_task"]), score_less=True),
    # Extra D-A baseline: <OD> has a fixed vocabulary without table/chart/photo/illustration (smoke shows 0 mapped
    # boxes), so prompted detection is added for D-A only. It deviates from the registered <OD>-only decision and
    # must be approved before it enters any ranking.
    Candidate("florence2_base_ovd", "Florence-2-base <OPEN_VOCABULARY_DETECTION> (open, score-less)", "vlm", "open",
              "florence", dict(task="<OPEN_VOCABULARY_DETECTION>"), score_less=True, tracks=("D-A",)),
    Candidate("grounding_dino_base", "GroundingDINO-base (open)", "open_vocab_detector", "open", "gdino",
              dict(repo="IDEA-Research/grounding-dino-base")),
]


# --------------------------------------------------------------------------
# Image decoding shared by all adapters
# --------------------------------------------------------------------------
def load_rgb(path: str | Path) -> np.ndarray:
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"))


def xyxy_to_xywh(box: Sequence[float]) -> list[float]:
    x1, y1, x2, y2 = (float(v) for v in box)
    return [round(x1, 2), round(y1, 2), round(x2 - x1, 2), round(y2 - y1, 2)]


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------
class Adapter:
    """predict(rgb) -> list[{label, bbox, score}]; load() may be slow; close() frees memory."""
    device = "cpu"

    def load(self) -> None: ...

    def predict(self, rgb: np.ndarray) -> list[dict]:
        raise NotImplementedError

    def close(self) -> None:
        import gc
        for attr in ("model", "processor"):
            if hasattr(self, attr):
                setattr(self, attr, None)
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


class YoloAdapter(Adapter):
    def __init__(self, weights: str, device: str = "cuda", half: bool = True, imgsz: int = DEFAULTS["imgsz"], **_):
        self.weights, self.device, self.half, self.imgsz = weights, device, half and device == "cuda", imgsz

    def load(self):
        from ultralytics import YOLO
        self.model = YOLO(self.weights)

    def predict(self, rgb):
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])          # ultralytics treats ndarrays as BGR
        r = self.model.predict(bgr, imgsz=self.imgsz, conf=DEFAULTS["conf"], iou=DEFAULTS["iou_nms"],
                               max_det=DEFAULTS["max_det"], half=self.half, device=self.device, verbose=False)[0]
        names = r.names
        return [dict(label=names[int(c)], bbox=xyxy_to_xywh(b), score=float(s))
                for b, s, c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy(), r.boxes.cls.cpu().numpy())]


class RtDetrHfAdapter(Adapter):
    def __init__(self, repo: str, device: str = "cuda", half: bool = True, **_):
        self.repo, self.device, self.half = repo, device, half and device == "cuda"

    def load(self):
        import torch
        from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
        self.processor = RTDetrImageProcessor.from_pretrained(self.repo)
        self.model = RTDetrForObjectDetection.from_pretrained(self.repo).to(self.device).eval()
        if self.half:
            self.model = self.model.half()
        self.id2label = self.model.config.id2label
        self._torch = torch

    def predict(self, rgb):
        torch = self._torch
        h, w = rgb.shape[:2]
        inputs = self.processor(images=rgb, return_tensors="pt").to(self.device)
        if self.half:
            inputs["pixel_values"] = inputs["pixel_values"].half()
        with torch.no_grad():
            out = self.model(**inputs)
        res = self.processor.post_process_object_detection(out, target_sizes=[(h, w)], threshold=DEFAULTS["conf"])[0]
        order = np.argsort(-res["scores"].float().cpu().numpy())[:DEFAULTS["max_det"]]
        return [dict(label=self.id2label[int(res["labels"][i])], bbox=xyxy_to_xywh(res["boxes"][i].float().cpu().numpy()),
                     score=float(res["scores"][i])) for i in order]


def find_phrase_spans(prompt_ids: Sequence[int], phrase_ids: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """Token span of each phrase inside the tokenised prompt, searched left to right in prompt order.

    The prompt is "p1. p2. p3." so phrases appear in the order given; a phrase that cannot be found
    raises, because a silently missing class would change the benchmark.
    """
    spans, pos = [], 0
    for k, ids in enumerate(phrase_ids):
        ids = list(ids)
        for start in range(pos, len(prompt_ids) - len(ids) + 1):
            if list(prompt_ids[start:start + len(ids)]) == ids:
                spans.append((start, start + len(ids)))
                pos = start + len(ids)
                break
        else:
            raise ValueError(f"phrase #{k} not found in the tokenised prompt")
    return spans


class GroundingDinoAdapter(Adapter):
    """Open-vocabulary detector. `phrases` are joined into one prompt ("a. b. c.").

    Each of the 900 queries is assigned the prompt phrase with the highest token score (max over the phrase's
    tokens); queries below `gdino_box_threshold` are dropped. Phrase-level assignment replaces the library's
    text-threshold labels, which at a low threshold concatenate many phrases into one unusable label.
    """

    def __init__(self, repo: str, phrases: Sequence[str], device: str = "cuda", half: bool = False, **_):
        self.repo, self.phrases, self.device, self.half = repo, list(phrases), device, half and device == "cuda"

    def load(self):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        self.processor = AutoProcessor.from_pretrained(self.repo)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(self.repo).to(self.device).eval()
        if self.half:
            self.model = self.model.half()
        self._torch = torch
        self.prompt = ". ".join(self.phrases) + "."
        tok = self.processor.tokenizer
        prompt_ids = tok(self.prompt)["input_ids"]
        self.spans = find_phrase_spans(prompt_ids, [tok(p, add_special_tokens=False)["input_ids"] for p in self.phrases])

    def predict(self, rgb):
        torch = self._torch
        h, w = rgb.shape[:2]
        inputs = self.processor(images=rgb, text=self.prompt, return_tensors="pt").to(self.device)
        if self.half:
            inputs["pixel_values"] = inputs["pixel_values"].half()
        with torch.no_grad():
            out = self.model(**inputs)
        prob = out.logits[0].float().sigmoid()                                   # (queries, tokens)
        phrase_score = torch.stack([prob[:, a:b].max(dim=1).values for a, b in self.spans], dim=1)
        best, which = phrase_score.max(dim=1)
        keep = torch.nonzero(best >= DEFAULTS["gdino_box_threshold"]).flatten()
        order = keep[torch.argsort(-best[keep])][:DEFAULTS["max_det"]]
        boxes = out.pred_boxes[0].float()[order].cpu().numpy()                    # normalised cx, cy, w, h
        scores, idx = best[order].cpu().numpy(), which[order].cpu().numpy()
        res = []
        for (cx, cy, bw, bh), s, k in zip(boxes, scores, idx):
            x1, y1, x2, y2 = (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h
            x1, x2 = float(np.clip(x1, 0, w)), float(np.clip(x2, 0, w))
            y1, y2 = float(np.clip(y1, 0, h)), float(np.clip(y2, 0, h))
            if x2 > x1 and y2 > y1:
                res.append(dict(label=self.phrases[int(k)], bbox=xyxy_to_xywh((x1, y1, x2, y2)), score=float(s)))
        return res


class FlorenceAdapter(Adapter):
    """Vendored Florence-2-base, `<OD>` task, same loading path as the product (fp32, eager attention).

    Frames are padded to a square with black bars (the vendored model needs square feature maps) and the
    boxes are mapped back. Florence-2 returns no confidence: every box gets score 1.0 (score-less AP).
    """

    def __init__(self, model_dir: str | Path, device: str = "cuda", task: str = DEFAULTS["florence_task"],
                 phrases: Sequence[str] | None = None, **_):
        self.model_dir, self.device, self.task = str(model_dir), device, task
        self.phrases = list(phrases or [])      # only used by <OPEN_VOCABULARY_DETECTION>: one prompt per phrase

    def load(self):
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoProcessor
        for cls in (getattr(transformers, "PreTrainedTokenizer", None), getattr(transformers, "PreTrainedTokenizerFast", None)):
            if cls is not None and not hasattr(cls, "additional_special_tokens"):
                cls.additional_special_tokens = property(lambda s: [str(t) for t in getattr(s, "added_tokens_encoder", {}).keys()])
        self._torch = torch
        self.processor = AutoProcessor.from_pretrained(self.model_dir, trust_remote_code=True, use_fast=True)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_dir, dtype=torch.float32, trust_remote_code=True,
                                                          attn_implementation="eager").to(self.device).eval()
        if hasattr(self.model, "language_model") and hasattr(self.model.language_model, "tie_weights"):
            self.model.language_model.tie_weights()

    def _generate(self, canvas, text: str, side: int):
        torch = self._torch
        inputs = self.processor(text=text, images=canvas, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            ids = self.model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"],
                                      max_new_tokens=DEFAULTS["florence_max_new_tokens"],
                                      num_beams=DEFAULTS["florence_num_beams"], do_sample=False,
                                      eos_token_id=self.processor.tokenizer.eos_token_id,
                                      pad_token_id=self.processor.tokenizer.pad_token_id)
        decoded = self.processor.batch_decode(ids, skip_special_tokens=False)[0]
        return self.processor.post_process_generation(decoded, task=self.task, image_size=(side, side))[self.task]

    def predict(self, rgb):
        from PIL import Image
        h, w = rgb.shape[:2]
        side = max(h, w)
        ox, oy = (side - w) // 2, (side - h) // 2
        canvas = Image.new("RGB", (side, side), (0, 0, 0))
        canvas.paste(Image.fromarray(rgb), (ox, oy))
        if self.task == "<OPEN_VOCABULARY_DETECTION>":
            runs = [(self._generate(canvas, self.task + phrase, side), phrase) for phrase in self.phrases]
        else:
            runs = [(self._generate(canvas, self.task, side), None)]
        out = []
        for parsed, phrase in runs:
            boxes = parsed.get("bboxes", [])
            labels = [phrase] * len(boxes) if phrase is not None else parsed.get("labels", [])
            for box, label in zip(boxes, labels):
                x1, x2 = (float(v) for v in np.clip([box[0] - ox, box[2] - ox], 0, w))
                y1, y2 = (float(v) for v in np.clip([box[1] - oy, box[3] - oy], 0, h))
                if x2 > x1 and y2 > y1:
                    out.append(dict(label=str(label), bbox=xyxy_to_xywh((x1, y1, x2, y2)), score=1.0))
        return out


def build_adapter(c: Candidate, device: str, florence_dir: str | Path | None = None,
                  phrases: Sequence[str] | None = None) -> Adapter:
    if c.adapter == "yolo":
        return YoloAdapter(device=device, **c.params)
    if c.adapter == "rtdetr_hf":
        return RtDetrHfAdapter(device=device, **c.params)
    if c.adapter == "gdino":
        return GroundingDinoAdapter(device=device, phrases=phrases or [], **c.params)
    if c.adapter == "florence":
        if florence_dir is None:
            raise ValueError("Florence-2 needs the verified vendored directory")
        return FlorenceAdapter(florence_dir, device=device, phrases=phrases, **c.params)
    raise ValueError(c.adapter)


# --------------------------------------------------------------------------
# Florence asset verification (same rule as florence_runtime.verify_florence_model)
# --------------------------------------------------------------------------
def florence_asset_digest(path: Path, name: str) -> str:
    digest = hashlib.sha256()
    if name != "model.safetensors":                       # text assets are hashed with normalised newlines
        digest.update(Path(path).read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    else:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    return digest.hexdigest()


def verify_florence_assets(model_dir: str | Path) -> dict[str, bool]:
    root = Path(model_dir)
    return {name: (root / name).is_file() and florence_asset_digest(root / name, name) == expected
            for name, expected in FLORENCE_ASSET_SHA256.items()}


# --------------------------------------------------------------------------
# Resumable inference with failure bookkeeping
# --------------------------------------------------------------------------
def _cuda_sync():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except ImportError:
        pass


def read_rows(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def run_track(adapter: Adapter, items: Sequence[tuple[int, Path, tuple[int, int]]], out_path: Path,
              warmup: int = DEFAULTS["warmup_images"], max_seconds: float = DEFAULTS["max_seconds_per_image"],
              progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    """Run `adapter` on (image_id, path, (width, height)) items, appending one JSON line per image.

    Resumable: ids already present in `out_path` are skipped. Failures (decode error, size mismatch,
    exception, OOM, soft timeout) are recorded with a reason and never dropped.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {r["image_id"] for r in read_rows(out_path)}
    todo = [it for it in items if it[0] not in done]
    peak_mb = None
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        torch = None
    # warm-up on the first images (results discarded) so latency excludes one-off compilation/cache effects
    for _, path, _size in todo[:warmup]:
        try:
            adapter.predict(load_rgb(path))
        except Exception:
            break
    with open(out_path, "a", encoding="utf-8") as fh:
        for n, (image_id, path, (w, h)) in enumerate(todo):
            row: dict[str, Any] = dict(image_id=image_id, ok=False, reason=None, latency_ms=None, dets=[])
            try:
                rgb = load_rgb(path)
                if rgb.shape[1] != w or rgb.shape[0] != h:
                    row["reason"] = f"size_mismatch:{rgb.shape[1]}x{rgb.shape[0]}!={w}x{h}"
                else:
                    _cuda_sync()
                    t0 = time.perf_counter()
                    dets = adapter.predict(rgb)
                    _cuda_sync()
                    dt = time.perf_counter() - t0
                    row["latency_ms"] = round(dt * 1000, 2)
                    if dt > max_seconds:
                        row["reason"] = "timeout"
                    else:
                        row.update(ok=True, dets=dets)
            except Exception as exc:  # noqa: BLE001 - every failure is recorded, none hidden
                row["reason"] = f"{type(exc).__name__}:{str(exc)[:160]}"
                if "out of memory" in str(exc).lower():
                    row["reason"] = "oom"
                    try:
                        import torch as _t
                        _t.cuda.empty_cache()
                    except Exception:
                        pass
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            if progress and (n % 50 == 0):
                progress(n, len(todo))
    try:
        import torch as _t
        if _t.cuda.is_available():
            peak_mb = round(_t.cuda.max_memory_allocated() / 1e6, 1)
    except ImportError:
        pass
    rows = read_rows(out_path)
    return dict(n_items=len(items), n_rows=len(rows), n_ok=sum(r["ok"] for r in rows), peak_vram_mb=peak_mb)


# --------------------------------------------------------------------------
# Scoring one candidate on one track
# --------------------------------------------------------------------------
def latency_stats(rows: Sequence[dict]) -> dict[str, float]:
    v = np.array([r["latency_ms"] for r in rows if r.get("ok") and r.get("latency_ms") is not None], dtype=float)
    if len(v) == 0:
        return dict(n=0)
    return dict(n=int(len(v)), median_ms=float(np.median(v)), mean_ms=float(v.mean()), p95_ms=float(np.quantile(v, .95)),
                total_s=float(v.sum() / 1000))


def score_track(gt: dict[str, Any], rows: Sequence[dict], vocabulary: str, taxonomy_map: dict[str, list[str]],
                image_ids: Sequence[int] | None = None, score_less: bool = False) -> dict[str, Any]:
    """Score raw rows against `gt`.

    Closed vocabularies are matched by exact class name; open vocabularies go through the frozen taxonomy
    map. Failed images keep their GT and count as misses ('all images'); 'successful only' is reported too.
    """
    name_to_id = {c["name"]: c["id"] for c in gt["categories"]}
    image_ids = list(image_ids) if image_ids is not None else [im["id"] for im in gt["images"]]
    idset = set(image_ids)
    failed = {r["image_id"] for r in rows if not r["ok"] and r["image_id"] in idset}
    seen = {r["image_id"] for r in rows}
    missing = idset - seen                                   # never attempted: also counted, not dropped
    raw = [dict(image_id=r["image_id"], label=d["label"], bbox=d["bbox"], score=d["score"])
           for r in rows if r["ok"] and r["image_id"] in idset for d in r["dets"]]
    tmap = {n: [n] for n in name_to_id} if vocabulary == "closed" else taxonomy_map
    if vocabulary == "closed":
        keep = [p for p in raw if p["label"] in name_to_id]
        outside = len(raw) - len(keep)
        mapped = dict(preds=[dict(image_id=p["image_id"], category_id=name_to_id[p["label"]], bbox=p["bbox"], score=p["score"]) for p in keep],
                      unknown_concept_rate=outside / len(raw) if raw else 0.0,
                      taxonomy_mapping_coverage=(len(raw) - outside) / len(raw) if raw else 1.0, n_boxes=len(raw))
        mapped["outside_taxonomy_boxes"] = outside          # closed models also predict COCO classes outside the 10
    else:
        mapped = ds.map_open_vocab(raw, tmap, name_to_id)
    policy = ds.apply_failure_policy(mapped["preds"], image_ids, failed | missing)
    all_stats = ds.coco_summary(gt, policy["preds"], policy["image_ids_all"])
    ok_stats = ds.coco_summary(gt, policy["preds"], policy["image_ids_success"]) if policy["image_ids_success"] else None
    cache = ds.DetectionCache(gt, policy["preds"], policy["image_ids_all"])
    m = cache.metrics()
    return dict(
        n_images=len(image_ids), n_failed=len(failed), n_not_attempted=len(missing),
        failure_reasons={k: sum(1 for r in rows if not r["ok"] and (r["reason"] or "").split(":")[0] == k)
                         for k in {(r["reason"] or "").split(":")[0] for r in rows if not r["ok"]}},
        scored=all_stats, scored_success_only=ok_stats, per_class_ap=m["per_class_ap"], per_class_ap50=m.get("per_class_ap50", {}),
        diagnostic_at_conf=dict(conf=DEFAULTS["diag_conf"], **cache.precision_recall(DEFAULTS["diag_conf"])),
        mapping=dict(coverage=mapped["taxonomy_mapping_coverage"], unknown_rate=mapped["unknown_concept_rate"],
                     n_boxes=mapped["n_boxes"], outside_taxonomy=mapped.get("outside_taxonomy_boxes")),
        score_less=bool(score_less or ds.is_score_less(mapped["preds"])), latency=latency_stats(rows),
        n_predictions=len(mapped["preds"]))


# --------------------------------------------------------------------------
# Budget gate (registered rule: stop and ask when the measured estimate exceeds the budget)
# --------------------------------------------------------------------------
def estimate_gpu_hours(median_ms: dict[str, float], n_images: dict[str, int], overhead: float = 1.3,
                       load_minutes: float = 3.0) -> dict[str, Any]:
    """median_ms keys 'candidate|track'; n_images keys by track. Returns per-job and total GPU hours."""
    jobs = {}
    for key, ms in median_ms.items():
        track = key.split("|")[1]
        jobs[key] = (ms / 1000 * n_images[track] * overhead + load_minutes * 60) / 3600
    return dict(per_job_hours=jobs, total_hours=float(sum(jobs.values())))
