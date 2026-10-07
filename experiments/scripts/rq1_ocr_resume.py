"""Resumable 1 fps OCR for frozen RQ1 development media.

This process imports Paddle but never Torch. Completed 100-frame chunks are
immutable and source-bound; the visual pass checks each decoded frame hash.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path


CHUNK_FRAMES = 100
MODEL_NAME = "PaddleOCR ch_PP-OCRv4 confidence>=0.6"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def worker_sha256() -> str:
    return sha256_file(Path(__file__))


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _context(unit_id: str, media_sha256: str, duration: float, weights: dict,
             compute: str) -> dict:
    return {"schema": "rq1-ocr-chunk/1", "unit_id": unit_id,
            "media_sha256": media_sha256, "frame_count": max(1, math.floor(duration)),
            "worker_sha256": worker_sha256(), "model": MODEL_NAME,
            "weights": weights, "compute": compute,
            "paddleocr_version": importlib.metadata.version("paddleocr")}


def _validated_chunk(path: Path, context: dict, start: int, end: int) -> dict:
    chunk = json.loads(path.read_text(encoding="utf-8"))
    if (any(chunk.get(key) != value for key, value in context.items())
            or chunk.get("start_sec") != start or chunk.get("end_sec") != end
            or len(chunk.get("texts", [])) != end - start
            or len(chunk.get("frame_sha256", [])) != end - start
            or any(not isinstance(value, str) for value in chunk["texts"])
            or any(not isinstance(value, str) or len(value) != 64
                   for value in chunk["frame_sha256"])):
        raise ValueError(f"OCR chunk provenance mismatch: {path}")
    return chunk


def load_cache(cache: Path, *, unit_id: str, media_sha256: str, duration: float,
               weights: dict, compute: str) -> tuple[list[str], list[str], str]:
    """Verify complete cache and return texts, frame hashes, manifest hash."""
    context = _context(unit_id, media_sha256, duration, weights, compute)
    manifest_path = cache / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"OCR cache incomplete: {unit_id}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if any(manifest.get(key) != value for key, value in context.items()):
        raise ValueError(f"OCR cache manifest provenance mismatch: {unit_id}")
    expected = list(range(0, context["frame_count"], CHUNK_FRAMES))
    if [row.get("start_sec") for row in manifest.get("chunks", [])] != expected:
        raise ValueError(f"OCR cache chunk coverage mismatch: {unit_id}")
    texts, hashes = [], []
    for row in manifest["chunks"]:
        start = row["start_sec"]
        path = cache / f"{start:06d}.json"
        if row.get("sha256") != sha256_file(path):
            raise ValueError(f"OCR chunk changed: {path}")
        chunk = _validated_chunk(path, context, start,
                                 min(start + CHUNK_FRAMES, context["frame_count"]))
        texts.extend(chunk["texts"])
        hashes.extend(chunk["frame_sha256"])
    return texts, hashes, sha256_file(manifest_path)


def _preload_cuda11_dlls() -> None:
    """Windows Paddle requires CUDA 11 DLLs loaded before its first GPU op."""
    if os.name != "nt":
        return
    import ctypes
    import sys

    root = Path(sys.prefix) / "Lib/site-packages/nvidia"
    ordered = ["cuda_runtime/bin/cudart64_110.dll",
               "cublas/bin/cublas64_11.dll", "cublas/bin/cublasLt64_11.dll"]
    ordered += [f"cudnn/bin/{name}64_8.dll" for name in (
        "cudnn_ops_infer", "cudnn_ops_train", "cudnn_cnn_infer",
        "cudnn_cnn_train", "cudnn_adv_infer", "cudnn_adv_train", "cudnn")]
    if not all((root / relative).is_file() for relative in ordered):
        raise RuntimeError("CUDA 11.8, cuBLAS 11, or cuDNN 8 DLLs missing from OCR venv")
    directories = [root / name / "bin" for name in ("cuda_runtime", "cublas", "cudnn")]
    os.environ["PATH"] = os.pathsep.join(map(str, directories)) + os.pathsep + os.environ["PATH"]
    # Keep both directory handles and DLL handles alive through inference.
    _preload_cuda11_dlls.handles = [os.add_dll_directory(str(path)) for path in directories]
    _preload_cuda11_dlls.handles += [ctypes.WinDLL(str(root / relative)) for relative in ordered]


def extract(media: Path, duration: float, unit_id: str, media_sha256: str,
            cache: Path, model_root: Path, weights: dict, gpu: bool) -> Path:
    import cv2

    compute = "gpu" if gpu else "cpu"
    context = _context(unit_id, media_sha256, duration, weights, compute)
    cache.mkdir(parents=True, exist_ok=True)
    starts = list(range(0, context["frame_count"], CHUNK_FRAMES))
    missing = []
    for start in starts:
        path = cache / f"{start:06d}.json"
        end = min(start + CHUNK_FRAMES, context["frame_count"])
        if path.is_file():
            _validated_chunk(path, context, start, end)
        else:
            missing.append(start)
    if missing:
        if gpu:
            _preload_cuda11_dlls()
        from experiments.scripts.rq1_source_feature_extraction import _import_paddleocr

        if gpu:
            import paddle
            if not paddle.is_compiled_with_cuda():
                raise RuntimeError("OCR interpreter has CPU Paddle; GPU required")
        engine = _import_paddleocr()(
            lang="ch", ocr_version="PP-OCRv4", use_angle_cls=True,
            det_model_dir=str(model_root / "det"),
            rec_model_dir=str(model_root / "rec"),
            cls_model_dir=str(model_root / "cls"),
            use_gpu=gpu, show_log=False)
        cap = cv2.VideoCapture(str(media))
        if not cap.isOpened():
            raise OSError(f"cannot open {media}")
        try:
            for start in missing:
                end = min(start + CHUNK_FRAMES, context["frame_count"])
                texts, hashes = [], []
                for sec in range(start, end):
                    cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
                    ok, frame = cap.read()
                    if not ok:
                        raise OSError(f"missing 1 fps frame at {sec}s in {media}")
                    hashes.append(sha256_bytes(frame.tobytes()))
                    result = engine.ocr(frame, cls=True)
                    lines = result[0] if result and result[0] else []
                    texts.append(" | ".join(str(line[1][0]).strip() for line in lines
                                            if float(line[1][1]) >= 0.6
                                            and str(line[1][0]).strip()))
                _atomic_json(cache / f"{start:06d}.json",
                             {**context, "start_sec": start, "end_sec": end,
                              "texts": texts, "frame_sha256": hashes})
                print(f"  OCR frames: {end}/{context['frame_count']}", flush=True)
        finally:
            cap.release()
    chunks = [{"start_sec": start, "sha256": sha256_file(cache / f"{start:06d}.json")}
              for start in starts]
    _atomic_json(cache / "manifest.json", {**context, "chunks": chunks})
    load_cache(cache, unit_id=unit_id, media_sha256=media_sha256,
               duration=duration, weights=weights, compute=compute)
    return cache / "manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media", type=Path, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--media-sha256", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--weights-json", type=Path, required=True)
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()
    weights = json.loads(args.weights_json.read_text(encoding="utf-8"))
    print(extract(args.media, args.duration, args.unit_id, args.media_sha256,
                  args.cache, args.model_root, weights, args.gpu))


if __name__ == "__main__":
    main()
