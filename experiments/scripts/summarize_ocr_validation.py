"""Summarize paired full-validation OCR word recognition results by source video."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path

from experiments.scripts.ocr_validation_recognition import (
    NORMALIZER, SOURCE_SHA256, edit_distance, load_cohort, normalize,
)


EXPECTED = 15379
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261009


def verify_archive(path: Path) -> None:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != SOURCE_SHA256:
        raise ValueError(f"source archive SHA-256 mismatch: {path}")


def verify_extraction(archive: Path, root: Path) -> int:
    crop_root = root / "Crops" / "val"
    files = sorted(crop_root.rglob("*.png")) + sorted(crop_root.glob("*/Id-Label.txt"))
    with zipfile.ZipFile(archive) as source:
        for path in files:
            member = "IIIT-CVid/" + path.relative_to(root).as_posix()
            info = source.getinfo(member)
            crc = 0
            size = 0
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    crc = zlib.crc32(chunk, crc)
                    size += len(chunk)
            if size != info.file_size or crc != info.CRC:
                raise ValueError(f"extracted source mismatch: {path}")
    return len(files)


def load(name: str, root: Path, references: dict[str, str]) -> dict[str, dict]:
    path = root / f"{name}_full.jsonl"
    rows: dict[str, dict] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        key = row["crop_id"]
        if key in rows:
            raise ValueError(f"{name} duplicate crop at line {line_number}: {key}")
        if (
            row["engine"] != name or row["split"] != "val"
            or row["source_sha256"] != SOURCE_SHA256
            or row["normalizer"] != NORMALIZER
        ):
            raise ValueError(f"{name} identity mismatch at line {line_number}")
        reference = references.get(key)
        if reference is None or row["reference"] != reference:
            raise ValueError(f"{name} reference mismatch at line {line_number}")
        if (
            row["reference_chars"] != len(normalize(reference))
            or row["edit_distance"] != edit_distance(
                normalize(reference), normalize(row["prediction"])
            )
            or (row["error"] is not None and row["prediction"] != "")
        ):
            raise ValueError(f"{name} score mismatch at line {line_number}")
        rows[key] = row
    if rows.keys() != references.keys():
        raise ValueError(f"{name} cohort mismatch: {len(rows)}/{len(references)} crops")
    if len({row["engine_version"] for row in rows.values()}) != 1:
        raise ValueError(f"{name} mixed engine versions")
    return rows


def score(rows: list[dict]) -> dict:
    reference_chars = sum(row["reference_chars"] for row in rows)
    return {
        "crops": len(rows),
        "reference_chars": reference_chars,
        "edit_distance": sum(row["edit_distance"] for row in rows),
        "micro_cer": sum(row["edit_distance"] for row in rows) / reference_chars,
        "exact_word_rate": sum(row["edit_distance"] == 0 for row in rows) / len(rows),
        "empty_predictions": sum(not row["prediction"].strip() for row in rows),
        "failures": sum(row["error"] is not None for row in rows),
    }


def group_ids(crop_id: str) -> tuple[str, str]:
    parts = Path(crop_id).parts
    if len(parts) != 5 or parts[:2] != ("Crops", "val"):
        raise ValueError(f"unexpected crop ID: {crop_id}")
    return parts[2], f"{parts[2]}/{parts[3]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("experiments/outputs/ocr_validation_261009"))
    parser.add_argument("--dataset-root", type=Path, default=Path("experiments/datasets/iiit_cvid/IIIT-CVid"))
    parser.add_argument("--source-archive", type=Path, default=Path("research-data/iiit-cvid-source/IIIT-CVid.zip"))
    args = parser.parse_args()
    verify_archive(args.source_archive)
    verified_source_files = verify_extraction(args.source_archive, args.dataset_root)
    references = {crop_id: reference for crop_id, _, reference in load_cohort(args.dataset_root)}
    if len(references) != EXPECTED:
        raise ValueError(f"unexpected cohort size: {len(references)}")
    easy = load("easyocr_cpu", args.output_root, references)
    paddle = load("paddleocr", args.output_root, references)
    if easy.keys() != paddle.keys():
        raise ValueError("candidate cohorts differ")
    keys = sorted(easy)
    for key in keys:
        if (
            easy[key]["reference"] != paddle[key]["reference"]
            or easy[key]["reference_chars"] != paddle[key]["reference_chars"]
            or easy[key]["source_sha256"] != paddle[key]["source_sha256"]
            or easy[key]["normalizer"] != paddle[key]["normalizer"]
        ):
            raise ValueError(f"candidate reference/protocol mismatch: {key}")

    by_course: dict[str, list[str]] = defaultdict(list)
    by_video: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        course, video = group_ids(key)
        by_course[course].append(key)
        by_video[video].append(key)
    video_ids = sorted(by_video)
    # Resample source videos, preserving every word crop within each video.
    video_totals = {
        video: (
            sum(easy[k]["edit_distance"] for k in ids),
            sum(paddle[k]["edit_distance"] for k in ids),
            sum(easy[k]["reference_chars"] for k in ids),
        )
        for video, ids in by_video.items()
    }
    rng = random.Random(BOOTSTRAP_SEED)
    differences = []
    for _ in range(BOOTSTRAP_DRAWS):
        sample = [video_totals[rng.choice(video_ids)] for _ in video_ids]
        denominator = sum(item[2] for item in sample)
        differences.append(
            (sum(item[1] for item in sample) - sum(item[0] for item in sample))
            / denominator
        )
    differences.sort()
    easy_score = score([easy[key] for key in keys])
    paddle_score = score([paddle[key] for key in keys])
    interval = [
        differences[int(0.025 * BOOTSTRAP_DRAWS)],
        differences[int(0.975 * BOOTSTRAP_DRAWS) - 1],
    ]
    result = {
        "scope": "IIIT-CVID released validation word crops only",
        "source_sha256": easy[keys[0]]["source_sha256"],
        "verified_extracted_source_files": verified_source_files,
        "normalizer": easy[keys[0]]["normalizer"],
        "unit": "word crop",
        "paired_cluster": "source video",
        "engine_versions": {
            "easyocr": easy[keys[0]]["engine_version"],
            "paddleocr": paddle[keys[0]]["engine_version"],
        },
        "device_note": "CPU assignment from runner configuration and runtime log; per-row device metadata was not recorded",
        "videos": len(video_ids),
        "courses": len(by_course),
        "easyocr": easy_score,
        "paddleocr": paddle_score,
        "paddle_minus_easy_micro_cer": paddle_score["micro_cer"] - easy_score["micro_cer"],
        "paired_video_bootstrap_95_interval": interval,
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "by_course": {
            course: {
                "easyocr": score([easy[key] for key in ids]),
                "paddleocr": score([paddle[key] for key in ids]),
            }
            for course, ids in sorted(by_course.items())
        },
    }
    output = args.output_root / "paired_full.summary.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
