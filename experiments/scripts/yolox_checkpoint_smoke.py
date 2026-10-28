"""Colab smoke for detection source (b): can the DanceTrack YOLOX checkpoint be loaded and does it detect the dancers?

Run in Colab (GPU optional). Checks only what `detection_source_b.smoke_acceptance` lists: load + sha256, boxes that
agree with the GT of a few val frames, and what the checkpoint says about its own training. It never claims val is
unseen; the training-data question stays open unless the checkpoint or the upstream exp file settles it.

Two preprocessings are run because the right one is not assumed: the one that agrees with GT is reported.

    PYTHONPATH=<YOLOX 0.3.0 source> python yolox_checkpoint_smoke.py --frames f1.jpg f2.jpg --gt gt.json
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO, FILE = "noahcao/dancetrack_models", "bytetrack_models/bytetrack_model.pth.tar"
EXPECTED_BYTES = 792_835_731
VARIANTS = ("raw_bgr", "imagenet_rgb")


def sha256(path, chunk=1 << 24):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def describe_checkpoint(ckpt):
    """Metadata a checkpoint carries about itself; absent keys are reported as absent, not guessed."""
    state = ckpt.get("model", ckpt)
    head = {k: tuple(v.shape) for k, v in state.items() if "cls_preds" in k}
    stem = next((tuple(v.shape) for k, v in state.items() if k.endswith("stem.conv.conv.weight")), None)
    return dict(
        top_level_keys=sorted(ckpt.keys()) if isinstance(ckpt, dict) else None,
        n_tensors=len(state), stem_conv_shape=stem, cls_pred_shapes=head,
        start_epoch=ckpt.get("start_epoch"),
        # yolox_x has stem out-channels 80 (width 1.25 * 64); num_classes = cls_preds out-channels
        num_classes=next(iter(head.values()))[0] if head else None,
        has_exp_or_train_args=[k for k in ("exp", "args", "exp_name", "dataset") if isinstance(ckpt, dict) and k in ckpt])


def iou_matrix(a, b):
    """a: Nx4, b: Mx4 as x1,y1,x2,y2."""
    import numpy as np
    a, b = np.asarray(a, float).reshape(-1, 4), np.asarray(b, float).reshape(-1, 4)
    lt, rb = np.maximum(a[:, None, :2], b[None, :, :2]), np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(rb - lt, 0, None), axis=2)
    area = lambda x: (x[:, 2] - x[:, 0]) * (x[:, 3] - x[:, 1])
    return inter / (area(a)[:, None] + area(b)[None] - inter + 1e-9)


def build_model(state):
    import torch
    from yolox.models import YOLOX, YOLOPAFPN, YOLOXHead
    depth, width, ncls = 1.33, 1.25, 1  # yolox_x; checked against the checkpoint shapes by load_state_dict(strict=True)
    model = YOLOX(YOLOPAFPN(depth, width, in_channels=[256, 512, 1024]), YOLOXHead(ncls, width, in_channels=[256, 512, 1024]))
    model.load_state_dict(state, strict=True)
    return model.to("cuda" if torch.cuda.is_available() else "cpu").eval(), ncls


def preprocess(img, size, variant):
    """raw_bgr: letterbox 114, BGR 0-255 (original YOLOX eval). imagenet_rgb: RGB /255 then ImageNet mean/std."""
    import cv2
    import numpy as np
    scale = min(size[0] / img.shape[0], size[1] / img.shape[1])
    resized = cv2.resize(img, (int(img.shape[1] * scale), int(img.shape[0] * scale)))
    canvas = 114 * np.ones((*size, 3), dtype="uint8")
    canvas[:resized.shape[0], :resized.shape[1]] = resized
    x = canvas.astype("float32")
    if variant == "imagenet_rgb":
        x = x[:, :, ::-1] / 255.0
        x = (x - np.array([0.485, 0.456, 0.406], "float32")) / np.array([0.229, 0.224, 0.225], "float32")
    return np.ascontiguousarray(x.transpose(2, 0, 1), dtype="float32")[None], scale


def detect(model, ncls, frame_path, gt_xywh, variant, size=(800, 1440), nms=0.7):
    """Detections at several score thresholds, with precision/recall at IoU 0.5 against the frame GT."""
    import cv2
    import numpy as np
    import torch
    from yolox.utils import postprocess
    img = cv2.imread(str(frame_path))
    assert img is not None, f"cannot read {frame_path}"
    x, scale = preprocess(img, size, variant)
    dev = next(model.parameters()).device
    t = time.time()
    with torch.no_grad():
        out = postprocess(model(torch.from_numpy(x).to(dev)), ncls, 0.1, nms)[0]
    seconds = round(time.time() - t, 3)
    det = out.cpu().numpy() if out is not None else np.zeros((0, 7))
    score, boxes = det[:, 4] * det[:, 5], det[:, :4] / scale
    gt = [[x0, y0, x0 + w, y0 + h] for x0, y0, w, h in gt_xywh]
    res = dict(seconds=seconds, n_gt=len(gt), by_threshold={})
    for thr in (0.3, 0.5, 0.7):
        keep = boxes[score >= thr]
        if len(keep) and gt:
            m = iou_matrix(keep, gt)
            tp_det, tp_gt = int((m.max(1) >= 0.5).sum()), int((m.max(0) >= 0.5).sum())
        else:
            tp_det = tp_gt = 0
        res["by_threshold"][str(thr)] = dict(n_det=int(len(keep)), precision=round(tp_det / max(len(keep), 1), 3),
                                             recall=round(tp_gt / max(len(gt), 1), 3))
    return res


def mean_at_half(report, variant, key):
    rows = [r["by_threshold"]["0.5"][key] for r in report.get("inference", {}).get(variant, {}).values()]
    return round(sum(rows) / len(rows), 3) if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True, nargs="+", help="DanceTrack val frames (jpg)")
    ap.add_argument("--gt", required=True, help="json {frame file name: [[x,y,w,h], ...]} for those frames")
    ap.add_argument("--out", default="yolox-checkpoint-smoke.json")
    a = ap.parse_args()
    from huggingface_hub import hf_hub_download
    import torch
    path = hf_hub_download(REPO, FILE)
    size = Path(path).stat().st_size
    report = dict(repo=REPO, file=FILE, bytes=size, bytes_match_registry=size == EXPECTED_BYTES, sha256=sha256(path),
                  loaded_strict=False)
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    report["checkpoint"] = describe_checkpoint(ckpt)
    try:
        model, ncls = build_model(ckpt.get("model", ckpt))
        report["loaded_strict"] = True
        gt = json.loads(Path(a.gt).read_text(encoding="utf-8"))
        report["inference"] = {v: {Path(f).name: detect(model, ncls, f, gt[Path(f).name], v) for f in a.frames}
                               for v in VARIANTS}
    except Exception as e:  # report the failure; the verdict is the plan owner's call
        report["error"] = f"{type(e).__name__}: {e}"[:600]
    agree = {v: dict(precision=mean_at_half(report, v, "precision"), recall=mean_at_half(report, v, "recall"))
             for v in VARIANTS}
    report["agreement_with_gt_at_score_0.5"] = agree
    best = max(agree, key=lambda v: ((agree[v]["recall"] or 0), (agree[v]["precision"] or 0))) if report.get("inference") else None
    report["verdict_inputs"] = dict(loads=report["loaded_strict"], best_variant=best,
                                    training_data_documented=bool(report["checkpoint"]["has_exp_or_train_args"]))
    Path(a.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["loaded_strict"] else 1


if __name__ == "__main__":
    sys.exit(main())
