"""Sample the full locked Yale lecture for component-rights review.

This is visual evidence, not a license determination or a model input.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from experiments.scripts.rq1_locked_yale_boundary_diagnostics import frame, media_rows, source_rows
from experiments.scripts.rq1_locked_yale_media_receipt import sha256_file


INTERVAL_SEC = 120
COLUMNS = 6
CELL_WIDTH = 320
CELL_HEIGHT = 205


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    course_to_id, _ = source_rows()
    media = media_rows(course_to_id)
    if args.video_id not in media:
        raise ValueError(f"outside locked batches: {args.video_id}")
    path, manifest = media[args.video_id]
    if not path.is_file() or path.stat().st_size != int(manifest["expected_bytes"]):
        raise ValueError(f"complete exact-byte media required: {path}")
    image_path = args.output_dir / f"{args.video_id}-rights-storyboard.jpg"
    receipt_path = args.output_dir / f"{args.video_id}-rights-storyboard.json"
    if image_path.exists() or receipt_path.exists():
        raise FileExistsError(f"storyboard exists: {args.video_id}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])
    times = list(range(0, math.ceil(duration), INTERVAL_SEC))
    rows = math.ceil(len(times) / COLUMNS)
    sheet = Image.new("RGB", (COLUMNS * CELL_WIDTH, rows * CELL_HEIGHT), "white")
    draw = ImageDraw.Draw(sheet)
    for index, second in enumerate(times):
        left = index % COLUMNS * CELL_WIDTH
        top = index // COLUMNS * CELL_HEIGHT
        draw.text((left + 3, top + 3), f"{args.video_id} {second}s", fill="black")
        sheet.paste(frame(path, second), (left, top + 25))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sheet.save(image_path, quality=85)
    receipt = {
        "schema": "rq1-locked-yale-rights-storyboard/1",
        "qualification_only": True,
        "video_id": args.video_id,
        "media_sha256": sha256_file(path),
        "duration_sec": duration,
        "sample_interval_sec": INTERVAL_SEC,
        "sample_times_sec": times,
        "image_path": str(image_path.resolve()),
        "image_sha256": sha256_file(image_path),
        "rights_decision": "human_review_pending",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"{args.video_id}: {len(times)} full-lecture samples", flush=True)


if __name__ == "__main__":
    main()
