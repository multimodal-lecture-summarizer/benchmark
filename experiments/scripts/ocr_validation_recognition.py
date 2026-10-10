"""Run real OCR recognition on the complete IIIT-CVID validation word crops.

The source labels are the released Crops/val/<course>/Id-Label.txt files.
This runner does not score detection or use the test split.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image


EXPECTED_VALIDATION_CROPS = 15379
SOURCE_SHA256 = "b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489"
NORMALIZER = "NFKC_casefold_collapse_whitespace_v1"


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def load_cohort(root: Path) -> list[tuple[str, Path, str]]:
    crop_root = root / "Crops" / "val"
    if not crop_root.is_dir():
        raise FileNotFoundError(crop_root)
    labels: dict[str, str] = {}
    for label_file in sorted(crop_root.glob("*/Id-Label.txt")):
        for line in label_file.read_text(encoding="utf-8-sig").splitlines():
            relative, separator, label = line.partition(" ")
            if not separator or not label.strip():
                raise ValueError(f"missing crop label in {label_file}")
            key = relative.replace("\\", "/")
            if key in labels:
                raise ValueError(f"duplicate crop label: {key}")
            labels[key] = label.strip()
    images = {p.relative_to(root).as_posix(): p for p in crop_root.rglob("*.png")}
    if len(images) != EXPECTED_VALIDATION_CROPS or images.keys() != labels.keys():
        raise ValueError(
            f"cohort mismatch: {len(images)} images, {len(labels)} labels, "
            f"{len(images.keys() - labels.keys())} unlabeled, "
            f"{len(labels.keys() - images.keys())} missing images"
        )
    return [(key, images[key], labels[key]) for key in sorted(images)]


def load_engine(name: str):
    if name in ("easyocr", "easyocr_cpu"):
        import easyocr

        reader = easyocr.Reader(
            ["en"], gpu=name == "easyocr", detector=False, recognizer=True,
            download_enabled=False, verbose=False,
            model_storage_directory="research-data/ocr-models/easyocr",
        )

        def predict(images: list[np.ndarray]) -> list[str]:
            predictions = []
            for image in images:
                height, width = image.shape[:2]
                output = reader.recognize(
                    image, horizontal_list=[[0, width, 0, height]],
                    free_list=[], detail=0,
                )
                predictions.append(str(output[0]) if output else "")
            return predictions

        return predict, easyocr.__version__, 1

    if name == "paddleocr":
        import paddleocr

        reader = paddleocr.PaddleOCR(
            use_angle_cls=False, lang="en", det=False, rec=True,
            use_gpu=False, show_log=False,
        )

        def predict(images: list[np.ndarray]) -> list[str]:
            output = reader.ocr(images, det=False, cls=False)
            if len(output) != 1 or len(output[0]) != len(images):
                raise RuntimeError("PaddleOCR returned a different batch length")
            return [str(item[0]) if item else "" for item in output[0]]

        return predict, paddleocr.__version__, 32

    raise ValueError(f"unknown engine: {name}")


def read_completed(
    path: Path, engine: str, version: str, cohort: list[tuple[str, Path, str]],
) -> dict[str, dict]:
    completed: dict[str, dict] = {}
    references = {crop_id: reference for crop_id, _, reference in cohort}
    if not path.exists():
        return completed
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if (
            row["engine"] != engine
            or row["engine_version"] != version
            or row["source_sha256"] != SOURCE_SHA256
            or row["normalizer"] != NORMALIZER
            or row["split"] != "val"
        ):
            raise ValueError(f"checkpoint identity mismatch at line {line_number}")
        if row["crop_id"] in completed:
            raise ValueError(f"duplicate checkpoint row: {row['crop_id']}")
        reference = references.get(row["crop_id"])
        if reference is None or row["reference"] != reference:
            raise ValueError(f"checkpoint reference mismatch at line {line_number}")
        normalized_reference = normalize(reference)
        if (
            row["reference_chars"] != len(normalized_reference)
            or row["edit_distance"] != edit_distance(
                normalized_reference, normalize(row["prediction"])
            )
            or (row["error"] is not None and row["prediction"] != "")
        ):
            raise ValueError(f"checkpoint score mismatch at line {line_number}")
        completed[row["crop_id"]] = row
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("easyocr", "easyocr_cpu", "paddleocr"), required=True)
    parser.add_argument(
        "--dataset-root", type=Path,
        default=Path("experiments/datasets/iiit_cvid/IIIT-CVid"),
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("experiments/outputs/ocr_validation_261009"),
    )
    parser.add_argument("--limit", type=int, help="Diagnostic prefix only; not a benchmark")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")

    cohort = load_cohort(args.dataset_root)
    if args.limit:
        cohort = cohort[: args.limit]
    args.output_root.mkdir(parents=True, exist_ok=True)
    suffix = f"diagnostic_{args.limit}" if args.limit else "full"
    output = args.output_root / f"{args.engine}_{suffix}.jsonl"
    predictor, version, batch_size = load_engine(args.engine)
    completed = read_completed(output, args.engine, version, cohort)
    print(
        f"engine={args.engine} version={version} selected={len(cohort)} "
        f"resume={len(completed)} output={output}", flush=True,
    )
    started = time.perf_counter()
    with output.open("a", encoding="utf-8") as handle:
        for start in range(0, len(cohort), batch_size):
            batch = [item for item in cohort[start : start + batch_size] if item[0] not in completed]
            if not batch:
                continue
            pixels = []
            for _, image_path, _ in batch:
                with Image.open(image_path) as image:
                    pixels.append(np.asarray(image.convert("RGB")))
            try:
                predictions = predictor(pixels)
                errors = [None] * len(batch)
            except Exception as exc:
                predictions, errors = [], []
                for image in pixels:
                    try:
                        predictions.append(predictor([image])[0])
                        errors.append(None)
                    except Exception as single_exc:
                        predictions.append("")
                        errors.append(f"{type(single_exc).__name__}: {single_exc}; batch: {exc}")
            for (crop_id, _, reference), prediction, error in zip(batch, predictions, errors):
                normalized_reference = normalize(reference)
                normalized_prediction = normalize(prediction)
                row = {
                    "crop_id": crop_id,
                    "split": "val",
                    "engine": args.engine,
                    "engine_version": version,
                    "source_sha256": SOURCE_SHA256,
                    "normalizer": NORMALIZER,
                    "reference": reference,
                    "prediction": prediction,
                    "reference_chars": len(normalized_reference),
                    "edit_distance": edit_distance(normalized_reference, normalized_prediction),
                    "error": error,
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                completed[crop_id] = row
            handle.flush()
            index = min(start + batch_size, len(cohort))
            if index % 100 == 0 or index == len(cohort):
                print(f"{args.engine}: {index}/{len(cohort)} elapsed={time.perf_counter()-started:.1f}s", flush=True)

    rows = [completed[crop_id] for crop_id, _, _ in cohort]
    denominator = sum(row["reference_chars"] for row in rows)
    summary = {
        "engine": args.engine,
        "engine_version": version,
        "split": "val",
        "profile": "diagnostic" if args.limit else "full",
        "source_sha256": SOURCE_SHA256,
        "normalizer": NORMALIZER,
        "selected_crops": len(cohort),
        "evaluated_crops": len(rows),
        "failures": sum(row["error"] is not None for row in rows),
        "empty_predictions": sum(not normalize(row["prediction"]) for row in rows),
        "reference_chars": denominator,
        "edit_distance": sum(row["edit_distance"] for row in rows),
        "micro_cer": sum(row["edit_distance"] for row in rows) / denominator,
        "predictions_path": output.as_posix(),
    }
    summary_path = args.output_root / f"{args.engine}_{suffix}.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
