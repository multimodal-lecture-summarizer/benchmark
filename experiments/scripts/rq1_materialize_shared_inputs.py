"""Materialize source-only RQ1 transcript and video features under one recipe.

Default scope is train plus validation. Final-test input creation requires an
explicit flag and must follow the protocol's checkpoint/config lock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.scripts.rq1_freeze_input_recipe import (
    DEFAULT_OUTPUT as RECIPE_PATH,
    MODEL_REVISION,
    SOURCE_BUNDLE,
    build_recipe,
    sha256,
)
from experiments.scripts.rq1_source_feature_extraction import extract_rq1_video_features


REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO / "experiments/outputs/rq1_locked_mixed_20/shared_inputs"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def materialize_unit(row: dict, recipe: dict, output_dir: Path, model: object) -> dict:
    unit, media = row["unit"], row["media"]
    unit_id = unit["unit_id"]
    source_path = Path(media["local_path"])
    if not source_path.is_file() or sha256(source_path) != media["sha256"]:
        raise ValueError(f"missing or changed D2 media: {unit_id}")
    transcript_path = output_dir / "transcripts" / f"{unit_id}.json"
    feature_path = output_dir / "video_features" / f"{unit_id}.json"
    if not transcript_path.is_file():
        config = recipe["transcript_preprocessing"]
        segments_iter, info = model.transcribe(
            str(source_path), language=config["language"], beam_size=config["beam_size"],
            temperature=config["temperature"], vad_filter=config["vad_filter"],
            condition_on_previous_text=config["condition_on_previous_text"],
            word_timestamps=config["word_timestamps"],
        )
        segments = [{"start_sec": float(item.start), "end_sec": float(item.end),
                     "text": item.text.strip()} for item in segments_iter]
        transcript = " ".join(item["text"] for item in segments if item["text"])
        if not transcript:
            raise RuntimeError(f"empty transcript: {unit_id}")
        write_json(transcript_path, {
            "unit_id": unit_id, "source_sha256": media["sha256"],
            "language": info.language, "transcript": transcript,
            "transcript_sha256": hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
            "segments": segments,
        })
    if not feature_path.is_file():
        extracted = extract_rq1_video_features(
            source_path, media["sha256"], output_dir / "cache", max_ocr_frames=12
        )
        write_json(feature_path, extracted)
    transcript_data = json.loads(transcript_path.read_text(encoding="utf-8"))
    feature_data = json.loads(feature_path.read_text(encoding="utf-8"))
    if transcript_data.get("source_sha256") != media["sha256"] or feature_data.get("source_sha256") != media["sha256"]:
        raise ValueError(f"source binding mismatch: {unit_id}")
    if hashlib.sha256(transcript_data["transcript"].encode("utf-8")).hexdigest() != transcript_data["transcript_sha256"]:
        raise ValueError(f"transcript digest mismatch: {unit_id}")
    return {
        "unit_id": unit_id, "split": unit["split"], "media_sha256": media["sha256"],
        "transcript_file": str(transcript_path.resolve()), "transcript_file_sha256": sha256(transcript_path),
        "transcript_sha256": transcript_data["transcript_sha256"],
        "video_features_file": str(feature_path.resolve()), "video_features_file_sha256": sha256(feature_path),
        "feature_sha256": {key: feature_data[key]["sha256"] for key in ("scene", "ocr", "visual", "acoustic")},
        "feature_available": {key: feature_data[key]["available"] for key in ("scene", "ocr", "visual", "acoustic")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-final-test", action="store_true")
    parser.add_argument("--unit-id", help="Restrict to one source unit for an integration check")
    parser.add_argument("--verify", action="store_true", help="Verify source-input receipts without decoding")
    args = parser.parse_args()
    recipe = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
    if recipe != build_recipe():
        raise SystemExit("shared input recipe drifted; regenerate and review before materialization")
    source = json.loads(SOURCE_BUNDLE.read_text(encoding="utf-8"))
    allowed = {"train", "validation"}
    if args.include_final_test:
        allowed.add("final_test")
    rows = [row for row in source["units"] if row["unit"]["split"] in allowed
            and (args.unit_id is None or row["unit"]["unit_id"] == args.unit_id)]
    if not rows:
        raise SystemExit("no eligible source units selected")
    output_dir = args.output_dir.resolve()
    receipt_path = output_dir / "materialization.receipt.json"
    prior = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
    recipe_sha = sha256(RECIPE_PATH)
    if prior is not None and (prior.get("recipe_file_sha256") != recipe_sha
                              or prior.get("source_bundle_sha256") != sha256(SOURCE_BUNDLE)):
        raise SystemExit("existing materialization receipt belongs to a different recipe")
    if prior is not None and prior.get("materializer_source_sha256") not in (None, sha256(Path(__file__))):
        raise SystemExit("existing materialization used a different materializer revision")
    if args.verify and (prior is None or prior.get("materializer_source_sha256") != sha256(Path(__file__))):
        raise SystemExit("materializer revision missing or changed in receipt")
    receipts = {item["unit_id"]: item for item in prior.get("units", [])} if prior else {}
    if args.verify and any(row["unit"]["unit_id"] not in receipts for row in rows):
        raise SystemExit("materialization receipt is incomplete for selected units")
    if not args.verify:
        from faster_whisper import WhisperModel

        model_dir = Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-tiny.en/snapshots" / MODEL_REVISION
        model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", local_files_only=True)
    for row in rows:
        unit_id = row["unit"]["unit_id"]
        for kind, field in (("transcripts", "transcript_file_sha256"),
                            ("video_features", "video_features_file_sha256")):
            path = output_dir / kind / f"{unit_id}.json"
            if path.is_file() and (unit_id not in receipts or sha256(path) != receipts[unit_id][field]):
                raise SystemExit(f"unreceipted or changed output: {path}")
            if args.verify and not path.is_file():
                raise SystemExit(f"missing output: {path}")
        if args.verify:
            continue
        item = materialize_unit(row, recipe, output_dir, model)
        receipts[item["unit_id"]] = item
        write_json(receipt_path, {
            "schema": "rq1-04ab-materialization/1", "status": "source_inputs_only_no_model_scoring",
            "recipe_file_sha256": recipe_sha, "source_bundle_sha256": sha256(SOURCE_BUNDLE),
            "materializer_source_sha256": sha256(Path(__file__)),
            "units": sorted(receipts.values(), key=lambda entry: entry["unit_id"]),
        })
        print(f"materialized {item['split']} {item['unit_id']}", flush=True)
    print(f"{'verified' if args.verify else 'receipt'}: {receipt_path} ({len(rows)} selected units)")


if __name__ == "__main__":
    main()
