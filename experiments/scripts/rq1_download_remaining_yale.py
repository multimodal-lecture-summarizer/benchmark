"""Download only source-valid media in the locked remaining-Yale manifest."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
DEFAULT_PREFIX = "rq1-yale-remaining-260929"
CHUNK_BYTES = 4 * 1024 * 1024


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(row: dict[str, str], media_dir: Path) -> dict[str, object]:
    filename = row["filename"]
    if Path(filename).name != filename or row["acquisition_action"] != "download":
        raise ValueError(f"not a locked media row: {row}")
    destination = media_dir / filename
    expected = int(row["expected_bytes"])
    if not destination.exists():
        ranges = [(start, min(expected - 1, start + CHUNK_BYTES - 1)) for start in range(0, expected, CHUNK_BYTES)]

        def fetch_range(index: int, start: int, end: int) -> Path:
            part = media_dir / f"{filename}.range-{index:04d}"
            if part.exists() and part.stat().st_size == end - start + 1:
                return part
            for attempt in range(3):
                if part.exists():
                    part.unlink()
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                request = urllib.request.Request(row["source_url"], headers={
                    "User-Agent": "RQ1 media qualification/1.0", "Range": f"bytes={start}-{end}",
                })
                try:
                    with opener.open(request, timeout=120) as response, part.open("xb") as target:
                        exact_range = f"bytes {start}-{end}/{expected}"
                        if response.status != 206 or response.headers.get("Content-Range") != exact_range:
                            raise ValueError(f"publisher byte range changed: {row['source_url']}")
                        while chunk := response.read(1024 * 1024):
                            target.write(chunk)
                    if part.stat().st_size == end - start + 1:
                        return part
                except OSError:
                    if attempt == 2:
                        raise
                if attempt < 2:
                    time.sleep(attempt + 1)
            raise ValueError(f"incomplete publisher range after retries: {part}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(fetch_range, index, start, end): index for index, (start, end) in enumerate(ranges)}
            parts = {futures[future]: future.result() for future in as_completed(futures)}
        partial = media_dir / f"{filename}.partial"
        if partial.exists():
            if partial.stat().st_size != 0:
                raise FileExistsError(f"partial assembly needs inspection: {partial}")
            partial.unlink()
        with partial.open("xb") as target:
            for index in range(len(ranges)):
                with parts[index].open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        target.write(chunk)
        if partial.stat().st_size != expected:
            raise ValueError(f"incomplete publisher file: {partial}")
        partial.replace(destination)
        for part in parts.values():
            part.unlink()
    if destination.stat().st_size != expected:
        raise ValueError(f"local bytes differ from lock: {destination}")
    print(f"DOWNLOADED {row['course_code']} {expected}", flush=True)
    return {"video_id": row["video_id"], "course_code": row["course_code"], "local_path": str(destination.resolve()), "source_url": row["source_url"], "bytes": expected, "sha256": sha_file(destination)}


def decode(item: dict[str, object]) -> dict[str, object]:
    path = str(item["local_path"])
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=index,codec_type,codec_name,width,height", "-of", "json", path,
    ], capture_output=True, text=True, timeout=90, check=True)
    info = json.loads(probe.stdout)
    if int(info["format"]["size"]) != item["bytes"]:
        raise ValueError(f"probe size mismatch: {path}")
    if not {"audio", "video"} <= {stream["codec_type"] for stream in info["streams"]}:
        raise ValueError(f"audio/video stream absent: {path}")
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", path, "-map", "0:v", "-map", "0:a", "-f", "null", "NUL",
    ], capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError(f"decode failed for {path}: {result.stderr[-500:]}")
    item.update({"duration_sec": float(info["format"]["duration"]), "streams": info["streams"], "full_audio_video_decode": "pass", "decode_warning": result.stderr.strip()})
    print(f"DECODED {item['course_code']} {item['duration_sec']:.3f}s", flush=True)
    return item


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--expected", type=int, default=10)
    parser.add_argument("--media-subdir", default="remaining_batch")
    args = parser.parse_args()
    manifest = REPORTS / f"{args.prefix}-media-acquisition.csv"
    output = REPORTS / f"{args.prefix}-full-media-decode-receipt.json"
    media_dir = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / args.media_subdir
    if output.exists():
        raise FileExistsError(output)
    with manifest.open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["acquisition_action"] == "download"]
    if len(rows) != args.expected:
        raise ValueError(f"expected {args.expected} source-valid media rows, got {len(rows)}")
    media_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(download, row, media_dir): row for row in rows}
        acquired = [future.result() for future in as_completed(futures)]
    by_video = {item["video_id"]: item for item in acquired}
    verified = [decode(by_video[row["video_id"]]) for row in rows]
    schema = "rq1-yale-remaining-full-media-decode/1" if args.prefix == DEFAULT_PREFIX else "rq1-yale-full-media-decode/1"
    payload = {"schema": schema, "qualification_only": True,
               "created_utc": datetime.now(timezone.utc).isoformat(), "manifest_sha256": sha_file(manifest), "files": verified}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
