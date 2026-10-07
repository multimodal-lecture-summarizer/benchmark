"""Freeze metadata selection before selected-media extraction; no model inference."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from experiments.scripts.dataset_readiness_ted import metadata_rows, select_ted, audio_bytes
from experiments.scripts.dataset_readiness_iiit import select_iiit, _parse_frame_transcriptions
from experiments.scripts.dataset_readiness_audio import declared_audio_frames


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_inputs(project_root: Path, protocol: dict) -> dict:
    root = Path(project_root).resolve()
    history_path = root / protocol.get("historical_manifest",
        "experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.frozen_manifest.json")
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    records = [r for r in payload["records"] if r["dataset_id"] == "tedlium3"]
    if len(records) != 1:
        raise ValueError("historical manifest must identify one TED dataset")
    historical_ids = records[0].get("unit_ids") or [r["unit_id"] for r in records[0].get("unit_records", [])]
    rows = metadata_rows(root)
    ted = select_ted(rows, historical_ids, protocol)
    source_files = sorted({r["arrow_path"] for r in rows})
    return {"protocol": protocol, "historical_manifest_sha256": sha256_file(history_path),
            "ted_arrow_sha256": {p: sha256_file(root / p) for p in source_files},
            "datasets": {"tedlium3": ted, "iiit_cvid": select_iiit(root)}}


def _base(record: dict) -> dict:
    return {**record, "decoded": False, "bytes": None, "sha256": None,
            "media_path": None, "reference_text": record.get("reference_text", ""),
            "decode_error": None, "ground_truth_error": None}


def _extract_ted(root: Path, destination: Path, records: list[dict]) -> list[dict]:
    import soundfile as sf

    result = []
    for record, audio in audio_bytes(root, records):
        row = _base(record)
        try:
            encoded = audio.get("bytes") if isinstance(audio, dict) else None
            if not isinstance(encoded, bytes):
                raise ValueError("TED selected row has no embedded audio bytes")
            row["source_audio_sha256"] = hashlib.sha256(encoded).hexdigest()
            expected_frames = declared_audio_frames(encoded)
            samples, rate = sf.read(io.BytesIO(encoded), dtype="float32", always_2d=True)
            if not len(samples) or len(samples) != expected_frames:
                raise ValueError("TED empty or incomplete decoded audio")
            path = destination / (hashlib.sha256(record["unit_id"].encode()).hexdigest() + ".wav")
            # FLOAT WAV preserves decoded samples instead of adding PCM16 quantization.
            sf.write(path, samples, rate, subtype="FLOAT")
            with sf.SoundFile(path) as decoded:
                count = sum(len(block) for block in decoded.blocks(blocksize=65536))
                if count != len(samples):
                    raise ValueError("TED extracted audio frame mismatch")
                row.update(duration_sec=count / decoded.samplerate, sample_rate_hz=decoded.samplerate,
                           channels=decoded.channels, frames=count)
            row.update(bytes=path.stat().st_size, sha256=sha256_file(path), media_path=str(path), decoded=True)
        except Exception as exc:
            row["decode_error"] = f"{type(exc).__name__}: {exc}"
        if not row["reference_text"].strip() or row["reference_text"].strip() == "ignore_time_segment_in_scoring":
            row["ground_truth_error"] = "empty_or_ignore_reference"
        row["annotation_sha256"] = hashlib.sha256(row["reference_text"].encode()).hexdigest()
        row["annotation_source"] = f"{record['arrow_path']}#text:{record['arrow_batch']}:{record['arrow_row']}"
        result.append(row)
    if len(result) != len(records):
        raise ValueError("TED extraction lost selected rows; no replacement permitted")
    return result


def _extract_image(root: Path, record: dict) -> dict:
    from PIL import Image

    row = _base(record)
    path, annotation = root / record["input_media_path"], root / record["annotation_path"]
    row["media_path"] = str(path)
    try:
        row.update(bytes=path.stat().st_size, sha256=sha256_file(path))
        with Image.open(path) as image:
            image.load()
            row.update(image_width_px=image.width, image_height_px=image.height,
                       image_mode=image.mode, decoded=True)
    except Exception as exc:
        row["decode_error"] = f"{type(exc).__name__}: {exc}"
    try:
        row["annotation_sha256"] = sha256_file(annotation)
        row["annotation_source"] = record["annotation_path"]
        row["reference_text"], row["text_line_count"] = _parse_frame_transcriptions(annotation)
        if not row["reference_text"].strip():
            row["ground_truth_error"] = "empty_reference"
    except Exception as exc:
        row["ground_truth_error"] = f"{type(exc).__name__}: {exc}"
    return row


def extract_inputs(project_root: Path, run_root: Path, selection: dict) -> dict:
    root, run_root = Path(project_root).resolve(), Path(run_root).resolve()
    frozen = json.loads((run_root / "selection.json").read_text(encoding="utf-8"))
    if frozen != selection:
        raise ValueError("selection.json must freeze the exact protocol/IDs before decoding")
    for relative, expected in selection["ted_arrow_sha256"].items():
        if sha256_file(root / relative) != expected:
            raise ValueError("TED source changed after selection")
    destination = run_root / "media/tedlium3"
    destination.mkdir(parents=True, exist_ok=False)
    result = json.loads(json.dumps(selection))
    ted = result["datasets"]["tedlium3"]
    for key in ("selected", "historical"):
        ted[key] = _extract_ted(root, destination, ted[key])
    iiit = result["datasets"]["iiit_cvid"]
    iiit["selected"] = [_extract_image(root, row) for row in iiit["selected"]]
    return result
