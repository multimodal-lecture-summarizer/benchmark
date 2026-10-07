"""Extract source-media evidence around locked Yale chapter starts.

Outputs frames and diagnostic ASR for human pre-score qualification. No chapter
candidate, prediction, or metric is loaded, and no boundary is auto-approved.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from experiments.scripts.rq1_locked_yale_media_receipt import BATCHES, DATASETS, REPORTS, sha256_file


FRAME_OFFSETS = (-6, -3, 0, 3, 6)
FRAME_SIZE = (320, 180)
ROW_HEIGHT = 205
AUDIO_PAD = 12


def canonical_course(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().removeprefix("yale-"))


def source_rows() -> tuple[dict[tuple[str, int], str], dict[str, list[dict[str, str]]]]:
    course_to_id: dict[tuple[str, int], str] = {}
    with (REPORTS / "rq1-expansion-batch-260929-2015-locked.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (canonical_course(row["course_id"]), int(row["publisher_resource"].rsplit("-", 1)[1]))
            course_to_id[key] = row["video_id"]
    with (REPORTS / "rq1-yale-native-batch-260929-source-metadata.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (canonical_course(row["course_code"]), int(row["lecture_url"].rsplit("-", 1)[1]))
            if key in course_to_id:
                raise ValueError(f"duplicate course/lecture: {key}")
            course_to_id[key] = row["video_id"]
    pairs: dict[str, list[dict[str, str]]] = defaultdict(list)
    for name in ("rq1-expansion-batch-260929-source-pairs.csv", "rq1-yale-native-batch-260929-source-pairs.csv"):
        with (REPORTS / name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                pairs[row["video_id"]].append(row)
    return course_to_id, pairs


def media_rows(course_to_id: dict[tuple[str, int], str]) -> dict[str, tuple[Path, dict[str, str]]]:
    media = {}
    for manifest_name, directory in BATCHES:
        with (REPORTS / manifest_name).open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                key = (canonical_course(row["course_id"]), int(row["lecture_no"]))
                video_id = course_to_id[key]
                if video_id in media:
                    raise ValueError(f"duplicate video ID: {video_id}")
                media[video_id] = (DATASETS / directory / row["filename"], row)
    return media


def frame(media: Path, second: float) -> Image.Image:
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0.0, second):.3f}",
        "-i", str(media), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "mjpeg", "-",
    ], capture_output=True, timeout=40)
    if result.returncode or not result.stdout:
        raise RuntimeError(f"frame extraction failed for {media} at {second}: {result.stderr[-500:]!r}")
    with Image.open(io.BytesIO(result.stdout)) as img:
        image = img.convert("RGB")
    image.thumbnail(FRAME_SIZE)
    canvas = Image.new("RGB", FRAME_SIZE, "black")
    canvas.paste(image, ((FRAME_SIZE[0] - image.width) // 2, (FRAME_SIZE[1] - image.height) // 2))
    return canvas


def audio_clip(media: Path, start: float, length: float) -> np.ndarray:
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-i", str(media),
        "-t", f"{length:.3f}", "-vn", "-ac", "1", "-ar", "16000",
        "-acodec", "pcm_f32le", "-f", "f32le", "-",
    ], capture_output=True, timeout=50)
    if result.returncode or not result.stdout:
        raise RuntimeError(f"audio extraction failed for {media} at {start}: {result.stderr[-500:]!r}")
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def process(video_id: str, media: Path, manifest: dict[str, str], pairs: list[dict[str, str]], model: object, output: Path) -> None:
    if not media.is_file() or media.stat().st_size != int(manifest["expected_bytes"]):
        raise ValueError(f"exact complete media required: {media}")
    image_path = output / f"{video_id}-boundary-contact-sheet.jpg"
    json_path = output / f"{video_id}-boundary-diagnostic.json"
    if image_path.exists() or json_path.exists():
        raise FileExistsError(f"diagnostic already exists for {video_id}")
    internal = [row for row in pairs if int(row["original_time_sec"]) > 0]
    if len(internal) != len(pairs) - 1:
        raise ValueError(f"unexpected structural starts for {video_id}")
    sheet = Image.new("RGB", (FRAME_SIZE[0] * len(FRAME_OFFSETS), ROW_HEIGHT * len(internal)), "white")
    draw = ImageDraw.Draw(sheet)
    evidence = []
    for index, row in enumerate(internal):
        second = float(row["original_time_sec"])
        frame_times = [max(0.0, second + offset) for offset in FRAME_OFFSETS]
        for column, timestamp in enumerate(frame_times):
            sheet.paste(frame(media, timestamp), (column * FRAME_SIZE[0], index * ROW_HEIGHT + 25))
            draw.text((column * FRAME_SIZE[0] + 3, index * ROW_HEIGHT + 4), f"{video_id} t={second:g} {FRAME_OFFSETS[column]:+d}s", fill="black")
        clip_start = max(0.0, second - AUDIO_PAD)
        segments, _ = model.transcribe(audio_clip(media, clip_start, AUDIO_PAD * 2), beam_size=1, language="en", vad_filter=False)
        speech = [{"start_sec": round(clip_start + item.start, 3), "end_sec": round(clip_start + item.end, 3), "text": item.text.strip()} for item in segments]
        evidence.append({"chapter_index": int(row["chapter_index"]), "original_label": row["original_label"], "original_time_sec": second, "frame_times_sec": frame_times, "audio_window_sec": [clip_start, clip_start + AUDIO_PAD * 2], "diagnostic_asr_segments": speech, "boundary_decision": "human_review_pending"})
        print(f"{video_id} {index + 1}/{len(internal)} t={second:g}", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    sheet.save(image_path, quality=85)
    payload = {"schema": "rq1-locked-yale-boundary-diagnostic/1", "qualification_only": True, "video_id": video_id, "media_path": str(media.resolve()), "media_sha256": sha256_file(media), "contact_sheet": str(image_path.resolve()), "contact_sheet_sha256": sha256_file(image_path), "boundaries": evidence}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    course_to_id, pairs = source_rows()
    media = media_rows(course_to_id)
    if args.video_id not in media:
        raise ValueError(f"video ID is outside locked batches: {args.video_id}")
    from faster_whisper import WhisperModel

    model = WhisperModel("tiny.en", device="cpu", compute_type="int8", local_files_only=True)
    path, manifest = media[args.video_id]
    process(args.video_id, path, manifest, pairs[args.video_id], model, args.output_dir)


if __name__ == "__main__":
    main()
