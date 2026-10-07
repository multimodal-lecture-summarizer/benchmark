"""Bind the eight frozen RQ1 train sources to their verified source inputs.

This is an input handoff, not learned feature extraction or checkpoint proof.
Validation and final-test labels are never written to the handoff.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.scripts.benchmark_artifacts import sha256_file


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans/reports"
SPLIT = REPORTS / "rq1-split-260930-8-4-8-locked.json"
FREEZE = REPORTS / "rq1-d2-freeze-receipt-260930-twenty-units.json"
SOURCE = REPORTS / "rq1-d2-source-bundle-260930-twenty-units.json"
MATERIALIZATION = REPO / "experiments/outputs/rq1_locked_mixed_20/shared_inputs/materialization.receipt.json"
DEFAULT_OUTPUT = REPO / "experiments/outputs/rq1_locked_mixed_20/train_inputs/train-source.handoff.json"


def _load(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def build_handoff() -> dict:
    freeze = _load(FREEZE)
    if freeze["status"] != "D2_dataset_frozen":
        raise ValueError("RQ1 D2 freeze is not closed")
    for path, field in ((SPLIT, "split_sha256"), (SOURCE, "source_bundle_sha256")):
        if sha256_file(path) != freeze[field]:
            raise ValueError(f"frozen {field} changed")
    split = _load(SPLIT)
    source = _load(SOURCE)
    materialized = _load(MATERIALIZATION)
    if (source["split_sha256"] != freeze["split_sha256"]
            or materialized["source_bundle_sha256"] != freeze["source_bundle_sha256"]
            or materialized["status"] != "source_inputs_only_no_model_scoring"):
        raise ValueError("source or materialization is not bound to D2")

    split_by_id = {row["video_id"]: row for row in split}
    source_by_id = {row["unit"]["unit_id"]: row for row in source["units"]}
    receipt_by_id = {row["unit_id"]: row for row in materialized["units"]}
    if (len(split_by_id), len(source_by_id), len(receipt_by_id)) != (20, 20, 12):
        raise ValueError("expected 20 frozen units and 12 materialized development units")
    if set(source_by_id) != set(split_by_id):
        raise ValueError("source and locked split IDs differ")
    train_ids = sorted(uid for uid, row in split_by_id.items() if row["split"] == "train")
    dev_ids = {uid for uid, row in split_by_id.items() if row["split"] in {"train", "validation"}}
    if len(train_ids) != 8 or set(receipt_by_id) != dev_ids:
        raise ValueError("train/development receipt count or identity changed")

    units = []
    for uid in train_ids:
        split_row = split_by_id[uid]
        source_row = source_by_id[uid]
        unit = source_row["unit"]
        receipt = receipt_by_id[uid]
        if (unit["split"] != "train" or receipt["split"] != "train"
                or unit["course_id"] != split_row["course_id"]
                or unit["sha256"] != receipt["media_sha256"]
                or unit["sha256"] != source_row["media"]["sha256"]):
            raise ValueError(f"train source/split/media mismatch: {uid}")
        paths = {
            "media": (source_row["media"]["local_path"], unit["sha256"]),
            "transcript": (receipt["transcript_file"], receipt["transcript_file_sha256"]),
            "video_features": (receipt["video_features_file"], receipt["video_features_file_sha256"]),
        }
        for kind, (path, expected_sha) in paths.items():
            file = Path(path)
            if not file.is_file() or sha256_file(file) != expected_sha:
                raise ValueError(f"train {kind} missing or changed: {uid}")
        units.append({
            "unit_id": uid,
            "dataset_id": unit["dataset_id"],
            "course_id": unit["course_id"],
            "lecturer_ids": split_row["lecturer_ids"],
            "duration_sec": unit["duration_sec"],
            "chapter_boundaries_sec": unit["chapter_boundaries_sec"],
            "media_path": paths["media"][0],
            "media_sha256": paths["media"][1],
            "transcript_file": paths["transcript"][0],
            "transcript_file_sha256": paths["transcript"][1],
            "video_features_file": paths["video_features"][0],
            "video_features_file_sha256": paths["video_features"][1],
        })
    return {
        "schema": "rq1-train-source-handoff/1",
        "status": "train_sources_bound_learned_tensors_pending",
        "d2_freeze_receipt_sha256": sha256_file(FREEZE),
        "locked_split_sha256": sha256_file(SPLIT),
        "d2_source_bundle_sha256": sha256_file(SOURCE),
        "materialization_receipt_sha256": sha256_file(MATERIALIZATION),
        "train_unit_count": len(units),
        "units": units,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    expected = build_handoff()
    if args.verify:
        if _load(args.output) != expected:
            raise SystemExit("RQ1 train source handoff changed")
        print(f"verified {args.output} (8 train units)")
        return
    if args.output.exists():
        raise SystemExit("RQ1 train source handoff exists; use --verify or a new output path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} (8 train units; learned tensors pending)")


if __name__ == "__main__":
    main()
