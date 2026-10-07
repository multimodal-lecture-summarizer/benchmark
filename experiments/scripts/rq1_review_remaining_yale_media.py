"""Generate source-only boundary and full-lecture visual review material."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw

from experiments.scripts.rq1_locked_yale_boundary_diagnostics import frame, process
from experiments.scripts.rq1_locked_yale_media_receipt import sha256_file
from experiments.scripts.rq1_locked_yale_rights_storyboard import CELL_HEIGHT, CELL_WIDTH, COLUMNS, INTERVAL_SEC


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
OUTPUT = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / "remaining_diagnostics"
DEFAULT_PREFIX = "rq1-yale-remaining-260929"


def storyboard(video_id: str, path: Path, duration: float, output_dir: Path = OUTPUT) -> None:
    image_path = output_dir / f"{video_id}-rights-storyboard.jpg"
    receipt_path = output_dir / f"{video_id}-rights-storyboard.json"
    if image_path.exists() or receipt_path.exists():
        raise FileExistsError(f"storyboard exists: {video_id}")
    times = list(range(0, math.ceil(duration), INTERVAL_SEC))
    sheet = Image.new("RGB", (COLUMNS * CELL_WIDTH, math.ceil(len(times) / COLUMNS) * CELL_HEIGHT), "white")
    draw = ImageDraw.Draw(sheet)
    for index, second in enumerate(times):
        x, y = index % COLUMNS * CELL_WIDTH, index // COLUMNS * CELL_HEIGHT
        draw.text((x + 3, y + 3), f"{video_id} {second}s", fill="black")
        sheet.paste(frame(path, second), (x, y + 25))
    sheet.save(image_path, quality=85)
    receipt_path.write_text(json.dumps({
        "schema": "rq1-yale-remaining-rights-storyboard/1", "qualification_only": True,
        "video_id": video_id, "media_sha256": sha256_file(path),
        "duration_sec": duration, "sample_interval_sec": INTERVAL_SEC,
        "sample_times_sec": times, "image_path": str(image_path.resolve()),
        "image_sha256": sha256_file(image_path), "rights_decision": "human_review_pending",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"STORYBOARD {video_id}: {len(times)} frames", flush=True)


def main() -> None:
    from faster_whisper import WhisperModel

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--media-subdir", default="remaining_batch")
    parser.add_argument("--diagnostic-subdir", default="remaining_diagnostics")
    args = parser.parse_args()
    media_dir = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / args.media_subdir
    output_dir = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / args.diagnostic_subdir
    with (REPORTS / f"{args.prefix}-media-acquisition.csv").open(encoding="utf-8", newline="") as stream:
        manifest = {row["video_id"]: row for row in csv.DictReader(stream) if row["acquisition_action"] == "download"}
    with (REPORTS / f"{args.prefix}-source-pairs.csv").open(encoding="utf-8", newline="") as stream:
        pairs = defaultdict(list)
        for row in csv.DictReader(stream):
            pairs[row["video_id"]].append(row)
    receipt_path = REPORTS / f"{args.prefix}-full-media-decode-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
    durations = {item["video_id"]: item["duration_sec"] for item in receipt["files"]} if receipt else {}
    if set(manifest) != set(pairs) or (receipt and set(manifest) != set(durations)):
        raise ValueError("manifest/GT/decode video IDs do not match")
    if args.video_id and args.video_id not in manifest:
        raise ValueError(f"outside locked source-valid batch: {args.video_id}")
    output_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8", local_files_only=True)
    for video_id, row in manifest.items():
        if args.video_id and video_id != args.video_id:
            continue
        path = media_dir / row["filename"]
        if not path.exists() or path.stat().st_size != int(row["expected_bytes"]):
            raise ValueError(f"complete exact-byte media required: {path}")
        if not (output_dir / f"{video_id}-boundary-diagnostic.json").exists():
            process(video_id, path, row, pairs[video_id], model, output_dir)
        if not (output_dir / f"{video_id}-rights-storyboard.json").exists():
            duration = durations.get(video_id)
            if duration is None:
                probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=30)
                duration = float(json.loads(probe.stdout)["format"]["duration"])
            storyboard(video_id, path, duration, output_dir)


if __name__ == "__main__":
    main()
