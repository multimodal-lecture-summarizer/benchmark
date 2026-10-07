"""Extract model-grade RQ1 tensors for the frozen train and validation units.

The eight final-test units are never admitted here. Each output is immutable,
source-bound, and can be resumed one unit at a time. DINOv2 and OCR use the
same 1 fps fallback frames; transcript and log-mel features use a 2 s grid.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import subprocess
from pathlib import Path, PureWindowsPath

import numpy as np

from experiments.scripts.benchmark_artifacts import sha256_file
from experiments.scripts.rq1_train_source_handoff import FREEZE, MATERIALIZATION, REPO, SOURCE, SPLIT


TEXT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TEXT_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
VISUAL_MODEL = "facebook/dinov2-small"
VISUAL_REVISION = "ed25f3a31f01632728cabb09d1542f84ab7b0056"
STEP_SEC = 2.0
FRAME_INTERVAL_SEC = 1.0
DEFAULT_OUTPUT = REPO / "experiments/outputs/rq1_locked_mixed_20/learned_features"
PUBLISHED_ROOT = REPO / "experiments/outputs/rq1_locked_mixed_20/notebook_artifacts/official/full"
PUBLISHED_MANIFEST = PUBLISHED_ROOT / "payloads/dataset.frozen_manifest.json"
PUBLISHED_RECEIPT = PUBLISHED_ROOT / "dataset.frozen_manifest.receipt.json"


def _read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_source_path(recorded_path: str) -> Path:
    """Rebase a frozen Windows path onto a copied repo; hashes are checked by caller."""
    original = Path(recorded_path)
    if original.is_file():
        return original
    parts = PureWindowsPath(recorded_path).parts
    if "experiments" not in parts:
        raise ValueError(f"frozen input is outside experiments: {recorded_path}")
    relative = Path(*parts[parts.index("experiments"):])
    local = (REPO / relative).resolve()
    if not local.is_relative_to(REPO.resolve()) or not local.is_file():
        raise FileNotFoundError(f"frozen input missing after repo rebase: {relative}")
    return local


def published_development_targets() -> dict[str, list[float]]:
    """Read only the selection-safe 00c artifact; final-test records have no GT."""
    receipt = _read(PUBLISHED_RECEIPT)
    if (receipt["producer_notebook_id"] != "00c_rq1_d2_inputs"
            or receipt["run_namespace"] != "official"
            or receipt["status"] != "real"
            or receipt["sha256"] != sha256_file(PUBLISHED_MANIFEST)):
        raise ValueError("published 00c selection manifest changed")
    frozen = _read(PUBLISHED_MANIFEST)["records"][0]
    units = frozen["unit_records"]
    if len(units) != 20:
        raise ValueError("published 00c cohort count changed")
    for row in units:
        if row["split"] == "final_test" and any(
            key in row for key in ("chapter_boundaries_sec", "chapter_gt", "media_path",
                                "transcript", "rq1_video_features")
        ):
            raise ValueError("final-test data leaked into selection manifest")
    return {row["unit_id"]: row["chapter_boundaries_sec"] for row in units
            if row["split"] in {"train", "validation"}}


def development_sources() -> list[dict]:
    """Return exactly the frozen 8/4 development records with verified inputs."""
    freeze = _read(FREEZE)
    if freeze["status"] != "D2_dataset_frozen":
        raise ValueError("D2 is not frozen")
    for path, field in ((SPLIT, "split_sha256"), (SOURCE, "source_bundle_sha256")):
        if sha256_file(path) != freeze[field]:
            raise ValueError(f"D2 {field} changed")
    split = {row["video_id"]: row for row in _read(SPLIT)}
    published_development_targets()
    published = _read(PUBLISHED_MANIFEST)["records"][0]["unit_records"]
    source = {row["unit_id"]: row for row in published}
    receipt = _read(MATERIALIZATION)
    if (len(split), len(source), len(receipt["units"])) != (20, 20, 12):
        raise ValueError("expected frozen 20/12 cohort")
    if receipt["source_bundle_sha256"] != sha256_file(SOURCE):
        raise ValueError("materialization belongs to another D2 source")
    materialized = {row["unit_id"]: row for row in receipt["units"]}
    allowed = {uid for uid, row in split.items() if row["split"] in {"train", "validation"}}
    if set(materialized) != allowed or {split[uid]["split"] for uid in allowed} != {"train", "validation"}:
        raise ValueError("materialization is not exactly train plus validation")
    if sum(split[uid]["split"] == "train" for uid in allowed) != 8:
        raise ValueError("expected eight train units")
    records = []
    for uid in sorted(allowed):
        unit, mat = source[uid], materialized[uid]
        if (unit["split"] != split[uid]["split"] or mat["split"] != unit["split"]
                or unit["course_id"] != split[uid]["course_id"]
                or unit["sha256"] != mat["media_sha256"]):
            raise ValueError(f"D2 split/media mismatch: {uid}")
        paths = ((unit["media_path"], unit["sha256"]),
                 (mat["transcript_file"], mat["transcript_file_sha256"]),
                 (mat["video_features_file"], mat["video_features_file_sha256"]))
        local_paths = []
        for path, expected in paths:
            local = _local_source_path(path)
            if sha256_file(local) != expected:
                raise ValueError(f"D2 input missing or changed: {uid}: {path}")
            local_paths.append(local)
        records.append({"unit_id": uid, "split": unit["split"],
                        "course_id": unit["course_id"], "lecturer_ids": split[uid]["lecturer_ids"],
                        "duration_sec": unit["duration_sec"], "media_path": str(local_paths[0]),
                        "media_sha256": paths[0][1], "transcript_path": str(local_paths[1]),
                        "transcript_file_sha256": paths[1][1],
                        "source_feature_path": str(local_paths[2]),
                        "source_feature_file_sha256": paths[2][1]})
    return records


def _grid(duration_sec: float) -> np.ndarray:
    if not math.isfinite(duration_sec) or duration_sec <= STEP_SEC:
        raise ValueError("invalid lecture duration")
    return np.arange(STEP_SEC / 2, duration_sec, STEP_SEC, dtype=np.float32)


def _text_windows(segments: list[dict], times: np.ndarray) -> list[str]:
    windows = []
    for t in times:
        # Centered six-second context keeps words near the boundary visible.
        words = [str(seg["text"]).strip() for seg in segments
                 if float(seg["start_sec"]) < float(t) + 3
                 and float(seg["end_sec"]) > float(t) - 3]
        windows.append(" ".join(word for word in words if word))
    return windows


def _encode_text(model, texts: list[str]) -> np.ndarray:
    vectors = np.zeros((len(texts), 384), dtype=np.float32)
    nonempty = [i for i, value in enumerate(texts) if value]
    if nonempty:
        encoded = model.encode([texts[i] for i in nonempty], batch_size=32,
                               convert_to_numpy=True, normalize_embeddings=True,
                               show_progress_bar=False)
        vectors[nonempty] = np.asarray(encoded, dtype=np.float32)
    return vectors


def _audio_logmel(media: Path, times: np.ndarray) -> np.ndarray:
    from scipy.signal import stft

    sample_rate = 16000
    window_samples = int(STEP_SEC * sample_rate)
    frequencies = np.fft.rfftfreq(400, 1 / sample_rate)
    mel_edges = np.linspace(0, 2595 * np.log10(1 + 8000 / 700), 34)
    hz_edges = 700 * (10 ** (mel_edges / 2595) - 1)
    filters = np.zeros((32, len(frequencies)), dtype=np.float32)
    for band in range(32):
        left, center, right = hz_edges[band:band + 3]
        filters[band] = np.maximum(0, np.minimum(
            (frequencies - left) / max(center - left, 1e-8),
            (right - frequencies) / max(right - center, 1e-8)))
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(media),
               "-t", str(len(times) * STEP_SEC), "-vn",
               "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rows = []
    assert process.stdout is not None
    try:
        for _ in times:
            raw = process.stdout.read(window_samples * 4)
            signal = np.frombuffer(raw, dtype="<f4")
            if signal.size < window_samples:
                signal = np.pad(signal, (0, window_samples - signal.size))
            _, _, spectrum = stft(signal, fs=sample_rate, nperseg=400,
                                  noverlap=240, boundary=None, padded=False)
            mel = filters @ (np.abs(spectrum) ** 2)
            rows.append(np.log1p(mel).mean(axis=1).astype(np.float32))
        process.stdout.close()
        error = process.stderr.read() if process.stderr else b""
        if process.wait() != 0:
            raise RuntimeError(f"FFmpeg audio decode failed: {error[-500:]!r}")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return np.stack(rows)


def _frame_embeddings(media: Path, duration: float, visual_model, processor,
                      ocr_engine, device: str, cached_ocr: tuple[list[str], list[str]] | None = None,
                      batch_size: int = 8
                      ) -> tuple[np.ndarray, np.ndarray, list[float]]:
    import cv2
    import torch

    cap = cv2.VideoCapture(str(media))
    if not cap.isOpened():
        raise OSError(f"cannot open {media}")
    frame_times, visuals, ocr_texts = [], [], []
    pending = []

    def flush() -> None:
        if not pending:
            return
        inputs = processor(images=[cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for frame in pending],
                           return_tensors="pt").to(device)
        with torch.inference_mode():
            outputs = visual_model(**inputs).last_hidden_state[:, 0, :]
        visuals.extend(outputs.cpu().numpy().astype(np.float32))
        pending.clear()

    try:
        for sec in range(max(1, math.floor(duration))):
            cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
            ok, frame = cap.read()
            if not ok:
                raise OSError(f"missing 1 fps frame at {sec}s in {media}")
            if cached_ocr is None:
                result = ocr_engine.ocr(frame, cls=True)
                lines = result[0] if result and result[0] else []
                ocr_texts.append(" | ".join(str(line[1][0]).strip() for line in lines
                                            if float(line[1][1]) >= 0.6 and str(line[1][0]).strip()))
            else:
                from experiments.scripts.rq1_ocr_resume import sha256_bytes
                if sha256_bytes(frame.tobytes()) != cached_ocr[1][sec]:
                    raise ValueError(f"OCR/DINO frame mismatch at {sec}s: {media}")
                ocr_texts.append(cached_ocr[0][sec])
            frame_times.append(float(sec))
            pending.append(frame)
            if len(pending) == batch_size:
                flush()
            if sec and sec % 300 == 0:
                print(f"  DINOv2/OCR frames: {sec}/{math.floor(duration)}", flush=True)
        flush()
    finally:
        cap.release()
    if len(frame_times) < math.ceil(duration * 0.95):
        raise ValueError("insufficient 1 fps frame coverage")
    # An empty OCR stream is a measured modality outcome, not a media failure.
    return np.stack(visuals), np.asarray(ocr_texts, dtype=object), frame_times


def extract_unit(row: dict, *, text_model, visual_model, processor, ocr_engine,
                 device: str, cached_ocr: tuple[list[str], list[str]] | None = None,
                 visual_batch_size: int = 8) -> dict:
    import torch

    times = _grid(float(row["duration_sec"]))
    transcript = _read(Path(row["transcript_path"]))
    if transcript["unit_id"] != row["unit_id"] or transcript["source_sha256"] != row["media_sha256"]:
        raise ValueError("transcript/source mismatch")
    text = _encode_text(text_model, _text_windows(transcript["segments"], times))
    acoustic = _audio_logmel(Path(row["media_path"]), times)
    frames, ocr_texts, frame_times = _frame_embeddings(
        Path(row["media_path"]), float(row["duration_sec"]), visual_model, processor,
        ocr_engine, device, cached_ocr, visual_batch_size)
    ocr = _encode_text(text_model, ocr_texts.tolist())
    indices = np.rint(times / FRAME_INTERVAL_SEC).astype(int)
    indices = np.clip(indices, 0, len(frame_times) - 1)
    arrays = {"text_features": text, "visual_features": frames[indices],
              "ocr_features": ocr[indices], "acoustic_features": acoustic}
    if any(value.shape != (len(times), dim) or not np.isfinite(value).all()
           for value, dim in ((text, 384), (arrays["visual_features"], 384),
                              (arrays["ocr_features"], 384), (acoustic, 32))):
        raise ValueError("nonfinite or wrong-shaped learned features")
    return {"unit_id": row["unit_id"], "split": row["split"],
            "timestamps": torch.from_numpy(times.copy()),
            **{key: torch.from_numpy(value.copy()) for key, value in arrays.items()}}


def _models(device: str, ocr_gpu: bool = False, include_ocr: bool = True):
    import torch
    from sentence_transformers import SentenceTransformer
    from transformers import AutoImageProcessor, AutoModel

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA unavailable; use --device cpu")
    if include_ocr:
        import paddle
        if ocr_gpu and not paddle.is_compiled_with_cuda():
            raise RuntimeError("PaddleOCR CUDA unavailable; omit --ocr-gpu or install CUDA PaddlePaddle")

    cache_dir = REPO / "experiments/outputs/rq1_locked_mixed_20/model_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_text = (Path.home() / ".cache/huggingface/hub"
                  / "models--sentence-transformers--all-MiniLM-L6-v2"
                  / "snapshots" / TEXT_REVISION)
    text = (SentenceTransformer(str(local_text), device=device) if local_text.is_dir()
            else SentenceTransformer(TEXT_MODEL, revision=TEXT_REVISION,
                                     cache_folder=str(cache_dir), device=device))
    processor = AutoImageProcessor.from_pretrained(
        VISUAL_MODEL, revision=VISUAL_REVISION, cache_dir=str(cache_dir), use_fast=False)
    visual = AutoModel.from_pretrained(
        VISUAL_MODEL, revision=VISUAL_REVISION, cache_dir=str(cache_dir)).to(device).eval()
    ocr = None
    if include_ocr:
        from experiments.scripts.rq1_source_feature_extraction import _import_paddleocr
        ocr_cache = cache_dir / "paddleocr"
        ocr = _import_paddleocr()(
            lang="ch", ocr_version="PP-OCRv4", use_angle_cls=True,
            det_model_dir=str(ocr_cache / "det"),
            rec_model_dir=str(ocr_cache / "rec"),
            cls_model_dir=str(ocr_cache / "cls"),
            use_gpu=ocr_gpu, show_log=False)
    return text, visual, processor, ocr


def _ocr_weight_hashes() -> dict[str, str]:
    root = REPO / "experiments/outputs/rq1_locked_mixed_20/model_cache/paddleocr"
    files = {f"{stage}/{name}": root / stage / name
             for stage in ("det", "rec", "cls")
             for name in ("inference.pdmodel", "inference.pdiparams")}
    if not all(path.is_file() for path in files.values()):
        raise FileNotFoundError("PaddleOCR model weights missing from workspace cache")
    return {name: sha256_file(path) for name, path in files.items()}


def materialize(output: Path, unit_id: str | None, verify: bool, device: str,
                ocr_gpu: bool = False, ocr_python: Path | None = None,
                visual_batch_size: int = 8) -> None:
    import torch

    if visual_batch_size < 1:
        raise ValueError("visual batch size must be positive")

    rows = development_sources()
    selected = [row for row in rows if unit_id is None or row["unit_id"] == unit_id]
    if not selected:
        raise ValueError("unit ID is not in frozen development split")
    models = None
    output.mkdir(parents=True, exist_ok=True)
    if ocr_python is not None and not ocr_python.is_file():
        raise FileNotFoundError(f"OCR interpreter missing: {ocr_python}")
    if ocr_python is not None:
        ocr_python = ocr_python.resolve()
    if ocr_gpu and ocr_python is None:
        raise ValueError("GPU OCR requires --ocr-python for process isolation")
    for row in selected:
        uid = row["unit_id"]
        tensor_path, receipt_path = output / f"{uid}.pt", output / f"{uid}.receipt.json"
        # An interrupted write has no receipt and is never reused as evidence.
        if not verify and tensor_path.exists() != receipt_path.exists():
            (tensor_path if tensor_path.exists() else receipt_path).unlink()
        if tensor_path.exists() or receipt_path.exists():
            if not tensor_path.is_file() or not receipt_path.is_file():
                raise ValueError(f"partial learned feature output: {uid}")
            receipt = _read(receipt_path)
            if (receipt["tensor_sha256"] != sha256_file(tensor_path)
                    or receipt["media_sha256"] != row["media_sha256"]
                    or receipt["transcript_file_sha256"] != row["transcript_file_sha256"]
                    or receipt["source_feature_file_sha256"] != row["source_feature_file_sha256"]
                    or receipt["split_sha256"] != sha256_file(SPLIT)
                    or receipt["extractor_sha256"] != sha256_file(Path(__file__))):
                raise ValueError(f"learned feature receipt drifted: {uid}")
            print(f"verified {uid}")
            continue
        if verify:
            raise ValueError(f"learned features missing: {uid}")
        ocr_weight_hashes = _ocr_weight_hashes()
        cached_ocr = None
        ocr_manifest_sha256 = None
        if ocr_python is not None:
            from experiments.scripts.rq1_ocr_resume import load_cache
            cache = output / "ocr_chunks" / uid
            weights_path = cache / "weights.json"
            if weights_path.is_file() and _read(weights_path) != ocr_weight_hashes:
                raise ValueError(f"OCR weights changed: {uid}")
            if not weights_path.is_file():
                weights_path.parent.mkdir(parents=True, exist_ok=True)
                weights_path.write_text(json.dumps(ocr_weight_hashes, sort_keys=True) + "\n",
                                        encoding="utf-8")
            command = [str(ocr_python), "-m", "experiments.scripts.rq1_ocr_resume",
                       "--media", row["media_path"], "--duration", str(row["duration_sec"]),
                       f"--unit-id={uid}", "--media-sha256", row["media_sha256"],
                       "--cache", str(cache), "--model-root", str(
                           REPO / "experiments/outputs/rq1_locked_mixed_20/model_cache/paddleocr"),
                       "--weights-json", str(weights_path)]
            if ocr_gpu:
                command.append("--gpu")
            subprocess.run(command, cwd=REPO, check=True)
            texts, hashes, ocr_manifest_sha256 = load_cache(
                cache, unit_id=uid, media_sha256=row["media_sha256"],
                duration=float(row["duration_sec"]), weights=ocr_weight_hashes,
                compute="gpu" if ocr_gpu else "cpu")
            cached_ocr = texts, hashes
        if models is None:
            models = _models(device, ocr_gpu, include_ocr=ocr_python is None)
        tensor = extract_unit(row, text_model=models[0], visual_model=models[1],
                              processor=models[2], ocr_engine=models[3], device=device,
                              cached_ocr=cached_ocr, visual_batch_size=visual_batch_size)
        tensor_tmp = tensor_path.with_suffix(".pt.partial")
        torch.save(tensor, tensor_tmp)
        tensor_tmp.replace(tensor_path)
        receipt = {"schema": "rq1-learned-feature-receipt/1", "unit_id": uid,
                   "split": row["split"], "course_id": row["course_id"],
                   "media_sha256": row["media_sha256"],
                   "transcript_file_sha256": row["transcript_file_sha256"],
                   "source_feature_file_sha256": row["source_feature_file_sha256"],
                   "split_sha256": sha256_file(SPLIT), "extractor_sha256": sha256_file(Path(__file__)),
                   "text_model": TEXT_MODEL, "text_revision": TEXT_REVISION,
                   "visual_model": VISUAL_MODEL, "visual_revision": VISUAL_REVISION,
                   "ocr_model": "PaddleOCR ch_PP-OCRv4 confidence>=0.6",
                   "ocr_weight_sha256": ocr_weight_hashes,
                   "paddleocr_version": importlib.metadata.version("paddleocr"),
                   "ocr_compute": "gpu" if ocr_gpu else "cpu",
                   "visual_compute": device, "visual_batch_size": visual_batch_size,
                   "ocr_worker_sha256": (sha256_file(
                       REPO / "experiments/scripts/rq1_ocr_resume.py")
                       if ocr_python is not None else None),
                   "ocr_manifest_sha256": ocr_manifest_sha256,
                   "dependencies": {name: importlib.metadata.version(name) for name in (
                       "torch", "transformers", "sentence-transformers", "opencv-python",
                       "scipy", "numpy")},
                   "frame_sampling": "1fps fallback; same frames for DINOv2 and OCR",
                   "audio": "FFmpeg mono 16kHz; 32-band log-mel mean per 2s",
                   "grid_step_sec": STEP_SEC,
                   "tensor_sha256": sha256_file(tensor_path)}
        receipt_tmp = receipt_path.with_suffix(".json.partial")
        receipt_tmp.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        receipt_tmp.replace(receipt_path)
        print(f"materialized learned features {uid}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--unit-id")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--visual-batch-size", type=int, default=8)
    parser.add_argument("--ocr-gpu", action="store_true")
    parser.add_argument("--ocr-python", type=Path,
                        help="Run resumable OCR in this separate Python interpreter")
    args = parser.parse_args()
    materialize(args.output, args.unit_id, args.verify, args.device,
                args.ocr_gpu, args.ocr_python, args.visual_batch_size)


if __name__ == "__main__":
    main()
