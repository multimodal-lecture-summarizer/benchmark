"""Create diagnostic dataset artifacts from fully verified TED-LIUM eval audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

from experiments.scripts.asr_full_corpus import _sha256_file
from experiments.scripts.benchmark_artifacts import RunnerContext, write_json_artifact, write_run_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = PROJECT_ROOT / "experiments/outputs/asr_a0_a5_benchmark_261003_pinned"


def prepare(metadata_dir: Path, media_dir: Path, artifact_root: Path) -> dict:
    receipt_path = media_dir / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if (receipt.get("status") != "complete" or
            hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() != receipt.get("receipt_sha256")):
        raise ValueError("media qualification receipt is incomplete or has an invalid hash")
    metadata_receipt = json.loads((metadata_dir / "receipt.json").read_text(encoding="utf-8"))
    metadata_records_path = (metadata_dir / metadata_receipt["cohort_path"]).resolve()
    metadata_records_path.relative_to(metadata_dir.resolve())
    if _sha256_file(metadata_records_path) != metadata_receipt.get("cohort_sha256"):
        raise ValueError("metadata cohort changed after inventory")
    if receipt["metadata_receipt_sha256"] != _sha256_file(metadata_dir / "receipt.json"):
        raise ValueError("metadata inventory receipt changed after media verification")
    records_path = (media_dir / receipt["cohort_path"]).resolve()
    records_path.relative_to(media_dir.resolve())
    if receipt["cohort_sha256"] != _sha256_file(records_path):
        raise ValueError("verified evaluation cohort changed")
    units = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    shard_hashes = {item["path"]: item["sha256"] for item in metadata_receipt["shards"]}
    expected_count = sum(receipt["counts"].values())
    if len(units) != expected_count or expected_count != 1662:
        raise ValueError(f"expected 1662 verified evaluation rows, found {len(units)}")
    if any(not row.get("canonical_audio_path") or not row.get("decoded_audio_sha256") or
           not row.get("reference_sha256") for row in units):
        raise ValueError("verified cohort row is missing media or ground-truth identity")
    for row in units:
        row["arrow_sha256"] = shard_hashes[row["arrow_path"]]
        cached_audio = Path(row["canonical_audio_path"])
        if not cached_audio.is_absolute():
            cached_audio = PROJECT_ROOT / cached_audio
        cached_audio = cached_audio.resolve()
        if not cached_audio.is_file() or not cached_audio.is_relative_to(PROJECT_ROOT.resolve()):
            raise ValueError(f"canonical audio cache is missing or outside workspace: {row['unit_id']}")
    ids = [row["unit_id"] for row in units]
    if len(ids) != len(set(ids)):
        raise ValueError("evaluation cohort has duplicate IDs")
    for split in ("validation", "final_test"):
        if sum(row["split"] == split for row in units) != receipt["counts"][split]:
            raise ValueError(f"split count mismatch for {split}")
    if artifact_root.exists() and any(artifact_root.iterdir()):
        raise FileExistsError("ASR benchmark artifact root must be new and empty")

    source_shard_manifest_sha256 = hashlib.sha256(json.dumps(
        metadata_receipt["shards"], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    # Open only a bounded diagnostic gate from the verified split-identity scan
    # and complete evaluation-media decode. Train waveform duplicates remain an
    # explicit limitation; they are not represented as audited.
    screen_complete = _diagnostic_metadata_screen_complete(metadata_receipt, receipt)
    unit_records = [{"dataset_id": "tedlium3", "asr_eligible": True, **unit} for unit in units]
    local_source_revision = f"local-arrow-sha256:{source_shard_manifest_sha256}"
    source_revision = local_source_revision
    frozen_record = {
        "dataset_id": "tedlium3", "freeze_status": "eligible",
        "scientific_selection_eligible": False, "diagnostic_selection_eligible": screen_complete,
        "unit_ids": [unit["unit_id"] for unit in unit_records],
        "unit_records": unit_records,
        "source_revision": source_revision,
        "local_snapshot_id": local_source_revision,
        "reference_provenance": {
            split: "TED-LIUM Release 3 Arrow reference field; source provenance not independently audited"
            for split in ("train", "validation", "test")
        } if screen_complete else None,
        "train_evaluation_media_audit_status": (
            "metadata_screened_audio_overlap_unverified" if screen_complete else "blocked_metadata_screen"),
        "metadata_cohort_sha256": metadata_receipt["cohort_sha256"],
        "media_cohort_sha256": receipt["cohort_sha256"],
        "source_shard_manifest_sha256": source_shard_manifest_sha256,
        "metadata_receipt_sha256": _sha256_file(metadata_dir / "receipt.json"),
        "media_receipt_sha256": _sha256_file(receipt_path),
        "train_evaluation_media_audit_sha256": None,
        "eligible_split_counts": receipt["counts"],
        "excluded_source_counts": metadata_receipt["counts"],
        "historical_final_test_contaminated": True,
        "eligibility_reason": ("diagnostic full-corpus ASR; historical native test exposure; "
                               "diagnostic metadata screen passed; train waveform exact/near duplicates and reference provenance remain unverified"
                               if screen_complete else "blocked: split identity/media metadata screen incomplete"),
    }
    registry_record = {
        "dataset_id": "tedlium3", "revision": source_revision,
        "local_snapshot_id": local_source_revision,
        "release": "TED-LIUM Release 3", "rights": "CC BY-NC-ND 3.0; non-commercial academic use",
        "scientific_selection_eligible": False, "diagnostic_selection_eligible": screen_complete,
        "media_status": "all_validation_and_test_waveforms_decoded_and_hashed",
        "train_audio_status": "metadata split screen only; waveform overlap unverified",
        "train_evaluation_media_audit_sha256": None,
        "train_evaluation_media_audit_status": (
            "metadata_screened_audio_overlap_unverified" if screen_complete else "blocked_metadata_screen"),
        "metadata_cohort_sha256": metadata_receipt["cohort_sha256"],
        "media_cohort_sha256": receipt["cohort_sha256"],
        "metadata_rows": 270323, "scorable_evaluation_rows": 1662,
    }
    endpoint_record = {
        "dataset_id": "tedlium3", "endpoint": "asr_benchmark",
        "scientific_selection_eligible": False, "diagnostic_selection_eligible": screen_complete,
        "train_evaluation_media_audit_sha256": None,
        "train_evaluation_media_audit_status": (
            "metadata_screened_audio_overlap_unverified" if screen_complete else "blocked_metadata_screen"),
        "metadata_cohort_sha256": metadata_receipt["cohort_sha256"],
        "media_cohort_sha256": receipt["cohort_sha256"],
        "eligibility": "diagnostic_full_corpus_asr" if screen_complete else "blocked_metadata_screen",
        "reason": frozen_record["eligibility_reason"],
    }
    source_hash = hashlib.sha256("".join(sorted(s["sha256"] for s in metadata_receipt["shards"])).encode()).hexdigest()
    config_hash = hashlib.sha256((PROJECT_ROOT / "experiments/registry/candidates.yaml").read_bytes() +
                                 (PROJECT_ROOT / "experiments/evaluation/asr_selection_scoring.py").read_bytes()).hexdigest()
    dependency_hash = hashlib.sha256((metadata_receipt["cohort_sha256"] + receipt["cohort_sha256"]).encode()).hexdigest()
    context = RunnerContext(
        profile="full", run_namespace="diagnostic", status="real", artifact_root=artifact_root,
        notebook_id="00c_dataset_eda_and_freeze", run_id=str(uuid.uuid4()),
        source_sha256=source_hash, config_sha256=config_hash,
        dependency_state_sha256=dependency_hash,
    )
    artifact_root.mkdir(parents=True, exist_ok=True)
    write_json_artifact(context, "dataset.frozen_manifest", [frozen_record],
                        metadata={"diagnostic_only": True, "media_validation": receipt["media_validation"]})
    write_json_artifact(context, "dataset.registry", [registry_record])
    write_json_artifact(context, "dataset.endpoint_matrix", [endpoint_record])
    write_run_manifest(context)
    return {"artifact_root": str(artifact_root.resolve()), "run_id": context.run_id,
            "unit_count": len(units), "split_counts": receipt["counts"],
            "scientific_selection_eligible": False,
            "diagnostic_selection_eligible": screen_complete,
            "dataset_frozen_manifest_sha256": _sha256_file(context.namespace_root / "payloads/dataset.frozen_manifest.json")}


def _diagnostic_metadata_screen_complete(metadata_receipt, media_receipt):
    """Validate the bounded diagnostic gate without claiming train audio audit."""
    identity_overlap = metadata_receipt.get("train_evaluation_identity_overlap", {})
    split_overlap = metadata_receipt.get("validation_test_identity_overlap", {})
    counts = metadata_receipt.get("counts", {})
    identity_keys = ("speaker_id", "talk_id", "source_id")
    return all((
        metadata_receipt.get("dataset_id") == "tedlium3",
        metadata_receipt.get("row_count") == 270323,
        counts.get("train", {}).get("rows") == 268263,
        counts.get("validation", {}).get("rows") == 591,
        counts.get("test", {}).get("rows") == 1469,
        isinstance(identity_overlap, dict) and all(identity_overlap.get(key) == [] for key in identity_keys),
        isinstance(split_overlap, dict) and all(split_overlap.get(key) == [] for key in identity_keys),
        media_receipt.get("status") == "complete",
        media_receipt.get("row_count") == 1662,
        media_receipt.get("counts") == {"validation": 507, "final_test": 1155},
        media_receipt.get("media_validation") == "all_evaluation_waveforms_decoded_and_hashed",
    ))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path,
                        default=PROJECT_ROOT / "experiments/outputs/asr_full_corpus_qualification_261003/metadata")
    parser.add_argument("--media-dir", type=Path,
                        default=PROJECT_ROOT / "experiments/outputs/asr_full_corpus_qualification_261003/media")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.metadata_dir, args.media_dir, args.artifact_root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
