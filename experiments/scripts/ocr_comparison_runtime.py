"""Pinned CPU recognition wrapper; keeps the historical OCR runner unchanged."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
import os
import platform
import sys
from pathlib import Path

try:
    from . import ocr_validation_recognition as runner
except ImportError:
    import ocr_validation_recognition as runner


MODEL_HASHES = {
    "easyocr_cpu": {
        "easyocr/english_g2.pth": "e2272681d9d67a04e2dff396b6e95077bc19001f8f6d3593c307b9852e1c29e8",
    },
    "paddleocr": {
        "paddleocr/en_PP-OCRv4_rec_infer/inference.pdiparams": "75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56",
        "paddleocr/en_PP-OCRv4_rec_infer/inference.pdmodel": "85b952f05f709af259cfe4254012aa7208bef0998f71f57a15495446f25ccd43",
        "paddleocr/en_PP-OCRv4_rec_infer/inference.pdiparams.info": "710d9f3d7c503067ae708f4bc3adc6973c0d6391adb7a1470c36eb70da6b5b83",
    },
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_models(engine: str, model_root: Path) -> dict[str, str]:
    hashes = {name: file_sha256(model_root / name) for name in MODEL_HASHES[engine]}
    if hashes != MODEL_HASHES[engine]:
        raise ValueError(f"model SHA256 mismatch for {engine}: {hashes}")
    return hashes


def bind_identity(output_root: Path, engine: str, identity: dict) -> Path:
    """Never attach a new receipt to unverified existing predictions."""
    output_root.mkdir(parents=True, exist_ok=True)
    receipt = output_root / f"{engine}_full.identity.json"
    predictions = output_root / f"{engine}_full.jsonl"
    if receipt.exists():
        if json.loads(receipt.read_text(encoding="utf-8")) != identity:
            raise ValueError("run identity mismatch; choose a new output root")
    else:
        if predictions.exists():
            raise ValueError("existing predictions have no run identity; choose a new output root")
        # Exclusive creation avoids accidentally replacing another session's receipt.
        with receipt.open("x", encoding="utf-8") as handle:
            json.dump(identity, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return receipt


@contextmanager
def engine_lock(output_root: Path, engine: str):
    """Prevent concurrent appends; stale locks require deliberate recovery."""
    output_root.mkdir(parents=True, exist_ok=True)
    lock = output_root / f"{engine}.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(
            f"OCR session lock exists: {lock}. Stop the old session first; "
            f"if it has stopped, manually remove only {lock} and resume."
        ) from exc
    try:
        with handle:
            json.dump({"pid": os.getpid(), "hostname": platform.node()}, handle)
        yield lock
    finally:
        lock.unlink()


def run_identity(engine: str, model_root: Path, cohort: list) -> dict:
    libraries = ("easyocr", "torch", "torchvision") if engine == "easyocr_cpu" else ("paddleocr", "paddlepaddle")
    library_versions = {name: version(name) for name in (*libraries, "numpy", "Pillow", "scipy")}
    import cv2

    library_versions["opencv_runtime"] = cv2.__version__
    expected = {"easyocr": "1.7.2", "paddleocr": "2.8.1", "paddlepaddle": "2.6.2"}
    for name, actual in library_versions.items():
        if name in expected and actual != expected[name]:
            raise ValueError(f"expected {name}=={expected[name]}, found {actual}")
    references = [(crop_id, reference) for crop_id, _, reference in cohort]
    return {
        "schema": "ocr_comparison_cpu_v1", "engine": engine, "device": "cpu",
        "source_sha256": runner.SOURCE_SHA256, "normalizer": runner.NORMALIZER,
        "split": "val", "selected_crops": len(cohort),
        "cohort_reference_sha256": hashlib.sha256(json.dumps(references, ensure_ascii=False).encode()).hexdigest(),
        "model_sha256": verify_models(engine, model_root),
        "implementation_sha256": {
            "runtime": file_sha256(Path(__file__)),
            "runner": file_sha256(Path(runner.__file__)),
        },
        "libraries": library_versions, "python": platform.python_version(),
        "platform": platform.platform(), "machine": platform.machine(),
        "recognition_only": True, "labels": "released_unmodified",
        "batch_size": 1 if engine == "easyocr_cpu" else 32,
        "inference_threads": 1,
        "decoder": "greedy_default", "lexicon": None,
    }


def load_engine(engine: str, model_root: Path):
    if engine == "easyocr_cpu":
        import easyocr
        import torch

        torch.set_num_threads(1)

        reader = easyocr.Reader(
            ["en"], gpu=False, detector=False, recognizer=True,
            download_enabled=False, verbose=False,
            model_storage_directory=str(model_root / "easyocr"),
        )

        def predict(images):
            predictions = []
            for image in images:
                height, width = image.shape[:2]
                output = reader.recognize(image, horizontal_list=[[0, width, 0, height]], free_list=[], detail=0)
                predictions.append(str(output[0]) if output else "")
            return predictions

        return predict, easyocr.__version__, 1

    import paddleocr

    reader = paddleocr.PaddleOCR(
        use_angle_cls=False, lang="en", det=False, rec=True, use_gpu=False,
        show_log=False, ocr_version="PP-OCRv4",
        cpu_threads=1,
        rec_model_dir=str(model_root / "paddleocr" / "en_PP-OCRv4_rec_infer"),
    )

    def predict(images):
        output = reader.ocr(images, det=False, cls=False)
        if len(output) != 1 or len(output[0]) != len(images):
            raise RuntimeError("PaddleOCR returned a different batch length")
        return [str(item[0]) if item else "" for item in output[0]]

    return predict, paddleocr.__version__, 32


def export_failures(output_root: Path, engine: str) -> None:
    predictions = output_root / f"{engine}_full.jsonl"
    with predictions.open(encoding="utf-8") as source:
        rows = [json.loads(line) for line in source]
    failures = [row for row in rows if row["error"] is not None]
    target = output_root / f"{engine}_full.failures.jsonl"
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failures), encoding="utf-8")
    artifacts = {
        name: file_sha256(output_root / name)
        for name in (predictions.name, f"{engine}_full.summary.json", target.name)
    }
    (output_root / f"{engine}_full.artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=tuple(MODEL_HASHES), required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    args = parser.parse_args()
    cohort = runner.load_cohort(args.dataset_root)
    identity = run_identity(args.engine, args.model_root, cohort)
    previous_loader, previous_argv = runner.load_engine, sys.argv
    try:
        with engine_lock(args.output_root, args.engine):
            bind_identity(args.output_root, args.engine, identity)
            runner.load_engine = lambda name: load_engine(name, args.model_root)
            sys.argv = [str(Path(runner.__file__)), "--engine", args.engine,
                        "--dataset-root", str(args.dataset_root), "--output-root", str(args.output_root)]
            runner.main()
            export_failures(args.output_root, args.engine)
    finally:
        runner.load_engine, sys.argv = previous_loader, previous_argv


if __name__ == "__main__":
    main()
