"""Publish the frozen RQ1 D2 cohort and verified development inputs for 04a/04b."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.scripts.benchmark_artifacts import (
    RunnerContext, parse_context, sha256_file, write_json_artifact, write_run_manifest,
)
from experiments.scripts.chapter_benchmark_contract import build_input_feature_record
from experiments.scripts.rq1_freeze_input_recipe import DEFAULT_OUTPUT as RECIPE_PATH


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans/reports"
FREEZE_RECEIPT = REPORTS / "rq1-d2-freeze-receipt-260930-twenty-units.json"
SOURCE_BUNDLE = REPORTS / "rq1-d2-source-bundle-260930-twenty-units.json"
FROZEN_DATASET = REPORTS / "rq1-d2-frozen-dataset-260930-twenty-units.json"
MATERIALIZATION = REPO / "experiments/outputs/rq1_locked_mixed_20/shared_inputs/materialization.receipt.json"
NOTEBOOK_ID = "00c_rq1_d2_inputs"
DATASET_ID = "rq1_locked_mixed_20"
DEVELOPMENT_SPLITS = frozenset({"train", "validation"})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_artifacts() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    freeze = _read_json(FREEZE_RECEIPT)
    if freeze.get("status") != "D2_dataset_frozen":
        raise ValueError("D2 freeze receipt is not closed")
    for path, field in ((SOURCE_BUNDLE, "source_bundle_sha256"),
                        (FROZEN_DATASET, "frozen_dataset_sha256")):
        if sha256_file(path) != freeze.get(field):
            raise ValueError(f"D2 freeze input changed: {path}")
    source = _read_json(SOURCE_BUNDLE)
    frozen = _read_json(FROZEN_DATASET)
    recipe = _read_json(RECIPE_PATH)
    if recipe.get("d2_source_bundle_sha256") != freeze["source_bundle_sha256"]:
        raise ValueError("shared input recipe belongs to another D2 source")
    materialized = _read_json(MATERIALIZATION)
    if (materialized.get("recipe_file_sha256") != sha256_file(RECIPE_PATH)
            or materialized.get("source_bundle_sha256") != freeze["source_bundle_sha256"]
            or materialized.get("status") != "source_inputs_only_no_model_scoring"):
        raise ValueError("materialization receipt source/recipe mismatch")
    from experiments.scripts import rq1_materialize_shared_inputs as producer

    if materialized.get("materializer_source_sha256") != sha256_file(Path(producer.__file__)):
        raise ValueError("materializer source changed after input creation")
    source_by_id = {row["unit"]["unit_id"]: row for row in source["units"]}
    receipt_by_id = {row["unit_id"]: row for row in materialized["units"]}
    if len(source_by_id) != 20 or len(receipt_by_id) != 12:
        raise ValueError("expected 20 frozen units and 12 development input receipts")
    expected_dev_ids = {uid for uid, row in source_by_id.items()
                        if row["unit"]["split"] in DEVELOPMENT_SPLITS}
    if set(receipt_by_id) != expected_dev_ids:
        raise ValueError("materialization must cover exactly train and validation, never final test")
    if Counter(row["unit"]["split"] for row in source["units"]) != {
        "train": 8, "validation": 4, "final_test": 8,
    }:
        raise ValueError("frozen split count changed")

    records = []
    for base in frozen["units"]:
        uid = base["unit_id"]
        source_row = source_by_id[uid]
        original = source_row["unit"]
        for field in ("split", "course_id", "speaker_id", "duration_sec",
                      "chapter_boundaries_sec", "chapter_gt", "sha256"):
            if base.get(field) != original.get(field):
                raise ValueError(f"frozen/source unit mismatch for {uid}: {field}")
        media = source_row["media"]
        media_path = Path(media["local_path"])
        if (media["sha256"] != base["sha256"] or not media_path.is_file()
                or sha256_file(media_path) != base["sha256"]):
            raise ValueError(f"D2 media missing or misbound: {uid}")
        if base["split"] in DEVELOPMENT_SPLITS:
            record = {**base, "media_path": str(media_path)}
            receipt = receipt_by_id[uid]
            if receipt["split"] != base["split"] or receipt["media_sha256"] != base["sha256"]:
                raise ValueError(f"development input/media mismatch: {uid}")
            transcript_path = Path(receipt["transcript_file"])
            feature_path = Path(receipt["video_features_file"])
            for path, expected in ((transcript_path, receipt["transcript_file_sha256"]),
                                   (feature_path, receipt["video_features_file_sha256"])):
                if not path.is_file() or sha256_file(path) != expected:
                    raise ValueError(f"development payload changed: {uid}: {path}")
            transcript = _read_json(transcript_path)
            video = _read_json(feature_path)
            if (transcript["unit_id"] != uid or transcript["source_sha256"] != base["sha256"]
                    or transcript["transcript_sha256"] != receipt["transcript_sha256"]
                    or video["source_sha256"] != base["sha256"]):
                raise ValueError(f"development payload identity mismatch: {uid}")
            for modality in ("scene", "ocr", "visual", "acoustic"):
                if (video[modality]["sha256"] != receipt["feature_sha256"][modality]
                        or video[modality]["available"] is not True):
                    raise ValueError(f"development modality changed/unavailable: {uid}: {modality}")
            record.update({
                "transcript": transcript["transcript"],
                "transcript_sha256": transcript["transcript_sha256"],
                "rq1_video_features": video,
            })
            # Reuse the scorer-facing contract to validate timestamps and digests
            # before publishing any eligible unit to the official namespace.
            build_input_feature_record(record, evaluation_mode="selection", code_sha256=sha256_file(Path(__file__)))
        else:
            # Selection can count sealed IDs without exposing target labels,
            # media paths, or source inputs in its published artifact.
            record = {key: base[key] for key in (
                "dataset_id", "unit_id", "split", "course_id", "speaker_id",
            )}
            if uid in receipt_by_id:
                raise ValueError(f"final-test input leaked into selection manifest: {uid}")
        records.append(record)
    frozen_record = {**frozen["frozen_manifest"][0], "unit_records": records}
    if frozen_record["dataset_id"] != DATASET_ID or len(frozen_record["unit_ids"]) != 20:
        raise ValueError("frozen manifest dataset/count mismatch")
    metadata = {
        "d2_freeze_receipt_sha256": sha256_file(FREEZE_RECEIPT),
        "d2_frozen_dataset_sha256": sha256_file(FROZEN_DATASET),
        "shared_input_recipe_sha256": sha256_file(RECIPE_PATH),
        "development_materialization_receipt_sha256": sha256_file(MATERIALIZATION),
        "development_unit_count": 12,
        "final_test_inputs_materialized": False,
        "final_test_gt_embedded": False,
    }
    return [frozen_record], frozen["registry"], frozen["endpoint_matrix"], metadata


def run(context: RunnerContext) -> dict[str, Any]:
    if context.profile != "full" or context.run_namespace != "official" or context.status != "real":
        raise ValueError("RQ1 D2 input publication requires official/full/real")
    if context.notebook_id != NOTEBOOK_ID:
        raise ValueError("wrong producer notebook ID")
    if any((context.namespace_root / name).exists() for name in (
        "dataset.frozen_manifest.receipt.json", "dataset.registry.receipt.json",
        "dataset.endpoint_matrix.receipt.json", f"runs/{NOTEBOOK_ID}.run.json",
    )):
        raise ValueError("RQ1 00c namespace is immutable; use a fresh artifact root")
    frozen, registry, matrix, metadata = build_artifacts()
    for artifact, payload in (("dataset.frozen_manifest", frozen),
                              ("dataset.registry", registry),
                              ("dataset.endpoint_matrix", matrix)):
        write_json_artifact(context, artifact, payload, metadata=metadata)
    write_run_manifest(context)
    return {"dataset_id": DATASET_ID, **metadata}


def main() -> None:
    context = parse_context(__doc__ or "", NOTEBOOK_ID)
    print(json.dumps(run(context), indent=2))


if __name__ == "__main__":
    main()
