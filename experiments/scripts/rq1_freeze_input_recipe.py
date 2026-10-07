"""Freeze and verify the shared source-input recipe for RQ1 04a/04b.

This locks producer revisions and preprocessing; it does not claim that
transcripts or video features have already been materialized.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

from experiments.scripts import rq1_source_feature_extraction as features


REPO = Path(__file__).resolve().parents[2]
OUTER = REPO.parent
SOURCE_BUNDLE = OUTER / "plans/reports/rq1-d2-source-bundle-260930-twenty-units.json"
ASR_SELECTION = REPO / "experiments/outputs/phase2_tedlium_d2/official/full/payloads/asr.frozen_configuration.json"
ASR_RECEIPT = REPO / "experiments/outputs/phase2_tedlium_d2/official/full/asr.frozen_configuration.receipt.json"
DEFAULT_OUTPUT = OUTER / "plans/reports/rq1-04ab-shared-input-recipe-260930.json"
MODEL_REVISION = "0d3d19a32d3338f10357c0889762bd8d64bbdeba"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_recipe() -> dict:
    source = json.loads(SOURCE_BUNDLE.read_text(encoding="utf-8"))
    if source.get("unit_count") != 20 or len(source.get("units", [])) != 20:
        raise ValueError("expected the frozen 20-unit D2 source bundle")
    asr = json.loads(ASR_SELECTION.read_text(encoding="utf-8"))["records"]
    if len(asr) != 1 or (asr[0]["frozen_model"], asr[0]["frozen_beam_size"], asr[0]["frozen_temperature"]) != ("tiny.en", 5, 0.0):
        raise ValueError("ASR selection changed")
    model_dir = Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-tiny.en/snapshots" / MODEL_REVISION
    model_files = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")
    if not all((model_dir / name).is_file() for name in model_files):
        raise FileNotFoundError(f"cached model revision incomplete: {model_dir}")
    identity = features._implementation_identity(None)
    if identity["ffmpeg"] is None:
        raise RuntimeError("FFmpeg is required to lock acoustic preprocessing")
    units = []
    for row in source["units"]:
        unit, media = row["unit"], row["media"]
        if unit["sha256"] != media["sha256"]:
            raise ValueError(f"D2 media mismatch: {unit['unit_id']}")
        units.append({
            "dataset_id": unit["dataset_id"], "unit_id": unit["unit_id"],
            "split": unit["split"], "media_sha256": media["sha256"],
            "transcript_output_sha256": None, "video_features_output_sha256": None,
        })
    return {
        "schema": "rq1-04ab-shared-input-recipe/1",
        "status": "recipe_locked_payloads_pending",
        "consumers": ["04a_chaptering_benchmark", "04b_chaptering_modality_ablation"],
        "generator_sha256": sha256(Path(__file__)),
        "d2_source_bundle_sha256": sha256(SOURCE_BUNDLE),
        "asr_selection": {
            "source": "phase2_tedlium_d2/official/full/asr.frozen_configuration",
            "payload_sha256": sha256(ASR_SELECTION),
            "receipt_file_sha256": sha256(ASR_RECEIPT),
            "model": "Systran/faster-whisper-tiny.en",
            "revision": MODEL_REVISION,
            "files_sha256": {name: sha256(model_dir / name) for name in model_files},
            "faster_whisper_version": importlib.metadata.version("faster-whisper"),
            "ctranslate2_version": importlib.metadata.version("ctranslate2"),
        },
        "transcript_preprocessing": {
            "input": "exact D2 media bytes, audio decoded by faster-whisper/PyAV at 16000 Hz mono",
            "language": "en", "beam_size": 5, "temperature": 0.0,
            "vad_filter": False, "condition_on_previous_text": True,
            "word_timestamps": False, "compute_device": "cpu", "compute_type": "int8",
            "text_join": "single space between stripped segment texts",
            "timestamps": "retain original segment start/end seconds without retiming",
        },
        "video_feature_preprocessing": {
            "implementation": identity,
            "scene": {"extractor": features.SCENE_EXTRACTOR, "config": features.SCENE_CONFIG},
            "ocr": {"primary": features.OCR_EXTRACTOR, "fallback": features.EASYOCR_EXTRACTOR,
                    "primary_config": features.OCR_CONFIG, "fallback_config": features.EASYOCR_CONFIG,
                    "max_ocr_frames": 12},
            "visual": {"extractor": features.VISUAL_EXTRACTOR, "config": features.VISUAL_CONFIG},
            "acoustic": {"extractor": features.ACOUSTIC_EXTRACTOR, "config": features.ACOUSTIC_CONFIG},
        },
        "units": units,
        "output_policy": "Populate output SHA256 only after source-only materialization and verification; no model outcomes or GT-based sample decisions.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    expected = build_recipe()
    if args.verify:
        actual = json.loads(args.output.read_text(encoding="utf-8"))
        if actual != expected:
            raise SystemExit("RQ1 shared input recipe drifted; stop before 04a/04b")
        print(f"verified {args.output} ({len(expected['units'])} units)")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output} ({len(expected['units'])} units; payloads pending)")


if __name__ == "__main__":
    main()
