"""Verify exact locked Yale media bytes and decode every audio/video stream.

This is qualification evidence only. It never reads model predictions or
promotes a video into D2.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
DATASETS = REPO / "experiments" / "datasets" / "yale_rq1_qualification"
BATCHES = (
    ("rq1-yale-vidchapters-media-acquisition-260929.csv", "vidchapters_batch"),
    ("rq1-yale-vidchapters-media-acquisition-b-260929.csv", "vidchapters_batch_b"),
    ("rq1-yale-native-media-acquisition-260929.csv", "native_batch"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checked(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr[-1200:]}")
    return result


def verify_one(row: dict[str, str], directory: Path) -> dict[str, object]:
    filename = row["filename"]
    if Path(filename).name != filename:
        raise ValueError(f"unsafe filename: {filename}")
    media = directory / filename
    if not media.is_file():
        raise FileNotFoundError(media)
    expected = int(row["expected_bytes"])
    size = media.stat().st_size
    if size != expected:
        raise ValueError(f"incomplete media: {media}: {size}/{expected}")
    probe = run_checked([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=index,codec_type,codec_name,width,height",
        "-of", "json", str(media),
    ])
    info = json.loads(probe.stdout)
    streams = info["streams"]
    if not any(item["codec_type"] == "video" for item in streams):
        raise ValueError(f"no video stream: {media}")
    if not any(item["codec_type"] == "audio" for item in streams):
        raise ValueError(f"no audio stream: {media}")
    if int(info["format"]["size"]) != expected:
        raise ValueError(f"probe byte mismatch: {media}")
    decoded_duration = float(info["format"]["duration"])
    manifest_duration = float(row["duration_s"])
    if abs(decoded_duration - manifest_duration) > 1.0:
        raise ValueError(f"publisher duration mismatch: {media}: {decoded_duration} vs {manifest_duration}")
    decode = run_checked([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(media),
        "-map", "0:v", "-map", "0:a", "-f", "null", "NUL",
    ])
    return {
        "course_id": row["course_id"],
        "lecture_no": int(row["lecture_no"]),
        "publisher_media_url": row["source_url"],
        "local_path": str(media.resolve()),
        "bytes": size,
        "sha256": sha256_file(media),
        "manifest_duration_sec": manifest_duration,
        "decoded_duration_sec": decoded_duration,
        "streams": streams,
        "ffprobe_warning": probe.stderr.strip(),
        "ffmpeg_warning": decode.stderr.strip(),
        "full_audio_video_decode": "pass",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    rows: list[dict[str, object]] = []
    manifests: list[dict[str, str]] = []
    for name, directory in BATCHES:
        manifest = REPORTS / name
        manifests.append({"path": str(manifest.resolve()), "sha256": sha256_file(manifest)})
        with manifest.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                verified = verify_one(row, DATASETS / directory)
                rows.append(verified)
                print(f"PASS {verified['course_id']} {verified['lecture_no']} {verified['sha256']}", flush=True)
    if len(rows) != 18:
        raise ValueError(f"expected 18 locked files, found {len(rows)}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "rq1-locked-yale-media-decode/1",
        "qualification_only": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "manifests": manifests,
        "files": rows,
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
