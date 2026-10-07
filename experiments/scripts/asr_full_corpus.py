"""Inventory all local TED-LIUM Arrow rows without decoding their waveforms.

The inventory is diagnostic preparation. Only explicitly selected rows are decoded;
neither function establishes scientific eligibility or an untouched final test.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from experiments.scripts.dataset_readiness_audio import declared_audio_frames


SOURCE_SPLITS = {"train": "train", "validation": "validation", "test": "final_test"}
EXPECTED_COUNTS = {
    "train": (268263, 268263, 0),
    "validation": (591, 507, 84),
    "test": (1469, 1155, 314),
}
IGNORE_MARKER = "ignore_time_segment_in_scoring"
TIMING = re.compile(r"-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-<")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=64)
def _cached_shard_sha256(path_text: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    return _sha256_file(Path(path_text))


def _shards(split_dir: Path) -> list[Path]:
    state = json.loads((split_dir / "state.json").read_text(encoding="utf-8"))
    names = [entry["filename"] for entry in state["_data_files"]]
    if not names or len(names) != len(set(names)):
        raise ValueError(f"missing or repeated Arrow shards: {split_dir}")
    paths = [(split_dir / name).resolve() for name in names]
    for path in paths:
        path.relative_to(split_dir.resolve())
        if not path.is_file() or path.suffix != ".arrow":
            raise ValueError(f"invalid Arrow shard: {path}")
    return paths


def inventory(root: Path, expected: dict | None = None) -> dict:
    """Scan every native split; return row locators and source-shard hashes.

    ``expected`` is mandatory in tests with synthetic fixtures; production uses
    the observed full-release counts above. A mismatch raises before any receipt.
    """
    import pyarrow as pa
    import pyarrow.ipc as ipc

    root = root.resolve()
    expected = EXPECTED_COUNTS if expected is None else expected
    if set(expected) != set(SOURCE_SPLITS):
        raise ValueError("expected counts must cover all three native splits")
    records, shards, counts, identities = [], [], {}, set()
    for native, split in SOURCE_SPLITS.items():
        split_dir = root / native
        counter = Counter()
        for path in _shards(split_dir):
            relative = path.relative_to(root).as_posix()
            shard_sha256 = _sha256_file(path)
            shards.append({"path": relative, "bytes": path.stat().st_size,
                           "sha256": shard_sha256})
            with pa.memory_map(str(path), "r") as source:
                for batch_index, batch in enumerate(ipc.open_stream(source)):
                    required = {"id", "text", "speaker_id", "file", "audio"}
                    if not required <= set(batch.schema.names):
                        raise ValueError(f"missing TED-LIUM columns in {relative}")
                    # Project only metadata; converting the audio column would decode 53 GB.
                    metadata = batch.select(["id", "text", "speaker_id", "file"]).to_pylist()
                    for row_index, row in enumerate(metadata):
                        counter["rows"] += 1
                        identity = row["id"]
                        if not isinstance(identity, str) or not identity:
                            raise ValueError(f"missing source ID in {relative}")
                        unit_id = f"{split}:{identity}"
                        if unit_id in identities:
                            raise ValueError(f"duplicate unit ID: {unit_id}")
                        identities.add(unit_id)
                        text = row["text"]
                        if not isinstance(text, str):
                            raise ValueError(f"missing reference: {unit_id}")
                        text = text.strip()
                        ignored = text == IGNORE_MARKER
                        gap = identity.startswith("inter_segment_gap")
                        match = TIMING.search(identity)
                        timed = bool(match and float(match[2]) > float(match[1]))
                        speaker = row["speaker_id"]
                        source_file = row["file"]
                        if not isinstance(speaker, str) or not speaker.strip():
                            raise ValueError(f"missing speaker: {unit_id}")
                        if not isinstance(source_file, str) or not source_file.strip():
                            raise ValueError(f"missing source file: {unit_id}")
                        eligible = bool(text and not ignored and not gap and timed)
                        counter["ignored"] += ignored
                        counter["gap"] += gap
                        counter["eligible"] += eligible
                        records.append({"unit_id": unit_id, "original_split": native,
                                        "split": split, "speaker_id": speaker,
                                        "source_id": Path(source_file.replace("\\", "/")).name,
                                        "talk_id": Path(source_file.replace("\\", "/")).stem,
                                        "start_seconds": float(match[1]) if match else None,
                                        "end_seconds": float(match[2]) if match else None,
                                        "reference_text": text if eligible else None,
                                        "asr_eligible": eligible, "exclusion_reason":
                                        None if eligible else ("ignore_marker" if ignored else
                                                               "inter_segment_gap" if gap else
                                                               "missing_reference" if not text else "invalid_timing"),
                                        "arrow_path": relative, "arrow_batch": batch_index,
                                        "arrow_row": row_index, "arrow_sha256": shard_sha256})
        actual = (counter["rows"], counter["eligible"], counter["ignored"])
        if actual != tuple(expected[native]):
            raise ValueError(f"full-corpus count mismatch for {native}: {actual} != {expected[native]}")
        counts[native] = dict(counter)
    by_split = {split: [row for row in records if row["original_split"] == split]
                for split in SOURCE_SPLITS}
    evaluation = by_split["validation"] + by_split["test"]
    overlap_audit = {}
    for field in ("speaker_id", "talk_id", "source_id"):
        train_values = {row[field] for row in by_split["train"]}
        evaluation_values = {row[field] for row in evaluation}
        overlap_audit[field] = sorted(train_values & evaluation_values)
    split_overlap = {field: sorted({row[field] for row in by_split["validation"]} &
                                   {row[field] for row in by_split["test"]})
                     for field in ("speaker_id", "talk_id", "source_id")}
    return {"dataset_id": "tedlium3", "scope": "full_arrow_metadata_only",
            "scientific_selection_eligible": False, "media_validation": "selected_rows_only",
            "counts": counts, "shards": shards, "train_evaluation_identity_overlap": overlap_audit,
            "validation_test_identity_overlap": split_overlap, "records": records}


def decode_selected(root: Path, record: dict, *, verify_shard: bool = True) -> tuple[dict, "object"]:
    """Decode one inventory locator into canonical mono 16 kHz float32 samples."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.ipc as ipc
    import soundfile as sf
    from scipy.signal import resample_poly

    if not record.get("asr_eligible"):
        raise ValueError("selected row is not ASR eligible")
    root = root.resolve()
    path = (root / record["arrow_path"]).resolve()
    path.relative_to(root)
    if verify_shard and record.get("arrow_sha256"):
        current_shard_sha = _cached_shard_sha256(str(path), path.stat().st_size, path.stat().st_mtime_ns)
        if current_shard_sha != record["arrow_sha256"]:
            raise ValueError("Arrow shard hash changed after inventory")
    with pa.memory_map(str(path), "r") as source:
        reader = ipc.open_stream(source)
        for index, batch in enumerate(reader):
            if index != record["arrow_batch"]:
                continue
            row_index = record["arrow_row"]
            if row_index < 0 or row_index >= len(batch):
                break
            row = batch.slice(row_index, 1).to_pylist()[0]
            expected_native = record.get("original_split")
            expected_contract_split = SOURCE_SPLITS.get(expected_native)
            expected_source = Path(str(row.get("file") or "").replace("\\", "/"))
            match = TIMING.search(str(row.get("id") or ""))
            actual_start = float(match[1]) if match else None
            actual_end = float(match[2]) if match else None
            if (f"{record['split']}:{row['id']}" != record["unit_id"] or
                    row["text"].strip() != record["reference_text"] or
                    record.get("split") != expected_contract_split or
                    row.get("speaker_id") != record.get("speaker_id") or
                    expected_source.name != record.get("source_id") or
                    expected_source.stem != record.get("talk_id") or
                    actual_start != record.get("start_seconds") or
                    actual_end != record.get("end_seconds")):
                raise ValueError("Arrow locator changed after inventory")
            embedded = row["audio"]
            encoded = embedded.get("bytes") if isinstance(embedded, dict) else None
            if not isinstance(encoded, bytes) or not encoded:
                raise ValueError("selected row lacks encoded audio")
            declared = declared_audio_frames(encoded)
            with sf.SoundFile(io.BytesIO(encoded)) as stream:
                samples = stream.read(dtype="float32", always_2d=True)
                rate = stream.samplerate
            if len(samples) != declared or not len(samples) or not np.isfinite(samples).all():
                raise ValueError("incomplete or nonfinite audio decode")
            mono = samples.mean(axis=1, dtype=np.float64)
            if rate != 16000:
                divisor = math.gcd(rate, 16000)
                mono = resample_poly(mono, 16000 // divisor, rate // divisor)
            canonical = np.asarray(mono, dtype="<f4")
            if not len(canonical) or not np.isfinite(canonical).all():
                raise ValueError("invalid canonical audio")
            evidence = {"unit_id": record["unit_id"], "source_audio_sha256":
                        hashlib.sha256(encoded).hexdigest(), "reference_sha256":
                        hashlib.sha256(record["reference_text"].encode("utf-8")).hexdigest(),
                        "canonical_audio_sha256": hashlib.sha256(canonical.tobytes()).hexdigest(),
                        "source_rate_hz": rate, "source_frames": declared,
                        "sample_rate_hz": 16000, "channels": 1,
                        "frames": len(canonical), "dtype": "float32"}
            return evidence, canonical
    raise ValueError("Arrow locator does not resolve")


def write_diagnostic(root: Path, destination: Path, expected: dict | None = None) -> dict:
    """Write a fresh metadata cohort and receipt only after full-count reconciliation."""
    if destination.exists():
        raise FileExistsError("diagnostic destination must be fresh")
    result = inventory(root, expected)
    destination.mkdir(parents=True)
    rows = destination / "cohort.jsonl"
    with rows.open("x", encoding="utf-8", newline="\n") as stream:
        for row in result.pop("records"):
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    receipt = dict(result, cohort_path=rows.name, cohort_sha256=_sha256_file(rows),
                   row_count=sum(x["rows"] for x in result["counts"].values()),
                   asr_eligible_count=sum(x["eligible"] for x in result["counts"].values()),
                   note="Metadata qualification only; waveforms and independent holdout unverified")
    (destination / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def freeze_evaluation_media(root: Path, metadata_dir: Path, destination: Path,
                            expected_counts: dict | None = None) -> dict:
    """Decode/hash every eligible validation and native-test waveform before model use."""
    if destination.exists():
        raise FileExistsError("media verification destination must be fresh")
    root, metadata_dir = root.resolve(), metadata_dir.resolve()
    receipt = json.loads((metadata_dir / "receipt.json").read_text(encoding="utf-8"))
    metadata_cohort = (metadata_dir / receipt["cohort_path"]).resolve()
    metadata_cohort.relative_to(metadata_dir)
    if _sha256_file(metadata_cohort) != receipt.get("cohort_sha256"):
        raise ValueError("metadata cohort changed after inventory")
    for shard in receipt["shards"]:
        path = (root / shard["path"]).resolve()
        path.relative_to(root)
        if _sha256_file(path) != shard["sha256"]:
            raise ValueError(f"Arrow shard changed after metadata inventory: {shard['path']}")
    destination.mkdir(parents=True)
    rows = [json.loads(line) for line in metadata_cohort.read_text(
        encoding="utf-8").splitlines()]
    eligible = [row for row in rows if row["asr_eligible"] and row["split"] in {"validation", "final_test"}]
    verified, failures = [], []
    cache_dir = destination / "audio_cache"
    for row in eligible:
        try:
            evidence, audio = decode_selected(root, row, verify_shard=False)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / (hashlib.sha256(row["unit_id"].encode()).hexdigest() + ".npy")
            with cache_file.open("wb") as stream:
                import numpy as np
                np.save(stream, audio, allow_pickle=False)
            project_root = Path(__file__).resolve().parents[2]
            try:
                cache_reference = cache_file.resolve().relative_to(project_root).as_posix()
            except ValueError:
                cache_reference = cache_file.resolve().as_posix()
            verified.append({**row, "decoded_audio_sha256": evidence["canonical_audio_sha256"],
                             "source_audio_sha256": evidence["source_audio_sha256"],
                             "reference_sha256": evidence["reference_sha256"],
                             "sample_rate_hz": evidence["sample_rate_hz"],
                             "audio_frames": evidence["frames"],
                             "audio_duration_seconds": evidence["frames"] / 16000.0,
                             "canonical_audio_path": cache_reference})
        except Exception as exc:
            failures.append({"unit_id": row["unit_id"], "reason": f"{type(exc).__name__}: {exc}"})
    frozen_counts = EXPECTED_COUNTS if expected_counts is None else expected_counts
    expected = {"validation": frozen_counts["validation"][1],
                "final_test": frozen_counts["test"][1]}
    counts = {split: sum(row["split"] == split for row in verified) for split in expected}
    if failures or counts != expected:
        raise RuntimeError(f"evaluation media incomplete; decoded={counts}, expected={expected}, failures={len(failures)}")
    cohort_path = destination / "evaluation_units.jsonl"
    with cohort_path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in verified:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    media_receipt = {"status": "complete", "scientific_selection_eligible": False,
                     "metadata_receipt_sha256": _sha256_file(metadata_dir / "receipt.json"),
                     "row_count": len(verified), "counts": counts, "failures": failures,
                     "cohort_path": cohort_path.name, "cohort_sha256": _sha256_file(cohort_path),
                     "media_validation": "all_evaluation_waveforms_decoded_and_hashed",
                     "train_waveforms_decoded": False,
                     "independent_holdout": False}
    media_receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(media_receipt, sort_keys=True).encode("utf-8")).hexdigest()
    (destination / "receipt.json").write_text(
        json.dumps(media_receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return media_receipt


def main(argv=None) -> int:
    import argparse

    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path,
                        default=project_root / "experiments/datasets/tedlium3")
    parser.add_argument("--output", type=Path,
                        default=project_root / "experiments/outputs/asr_full_corpus_qualification_261003/metadata")
    parser.add_argument("--verify-evaluation-media", action="store_true",
                        help="decode and hash all eligible validation and native test rows")
    parser.add_argument("--metadata-dir", type=Path,
                        default=project_root / "experiments/outputs/asr_full_corpus_qualification_261003/metadata")
    args = parser.parse_args(argv)
    if args.verify_evaluation_media:
        receipt = freeze_evaluation_media(args.dataset_root, args.metadata_dir,
                                          args.output.parent / "media")
        print(json.dumps(receipt, indent=2))
        return 0
    receipt = write_diagnostic(args.dataset_root, args.output)
    print(json.dumps({"output": str(args.output.resolve()),
                      "row_count": receipt["row_count"],
                      "asr_eligible_count": receipt["asr_eligible_count"],
                      "counts": receipt["counts"],
                      "train_evaluation_identity_overlap": receipt["train_evaluation_identity_overlap"],
                      "validation_test_identity_overlap": receipt["validation_test_identity_overlap"],
                      "media_validation": receipt["media_validation"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
