"""Check pinned MITFLD fragment/transcript timing for the selected RQ1 cohort."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import urllib.request
from pathlib import Path


REVISION = "f5a5047e040ecf0f80a3cb67d64e324407f323ec"
BASE = f"https://huggingface.co/datasets/robotwang/MITFLD/resolve/{REVISION}"
ROOT = Path(__file__).resolve().parents[2]
SELECTED = ROOT / "plans/reports/mitfld-rq1-35-260928-1120-selected.csv"
SELECTED_SHA256 = "ed658ca8fe4fce47b780ef72195d2e0bdc58a60a141e622b1d9f73128fd1b49d"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1126-annotation-ledger.csv"
FIELDS = (
    "video_id", "course_id", "split_proposed", "frags_http", "frags_sha256",
    "frags_count", "frags_first_s", "frags_last_s", "frags_strictly_increasing",
    "transcript_http", "transcript_sha256", "transcript_segments", "transcript_end_s",
    "frags_within_transcript", "annotation_structure_status", "error",
)


def fetch_json(kind: str, video_id: str) -> tuple[object, str, int]:
    url = f"{BASE}/{kind}/{video_id}.json"
    request = urllib.request.Request(url, headers={"User-Agent": "rq1-mitfld-qualification/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError(f"{kind} JSON exceeds 2 MB cap")
        return json.loads(body), hashlib.sha256(body).hexdigest(), response.status


def numeric(value: object) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def inspect(video_id: str, course_id: str, split: str) -> dict[str, object]:
    row: dict[str, object] = {"video_id": video_id, "course_id": course_id, "split_proposed": split}
    try:
        frags, row["frags_sha256"], row["frags_http"] = fetch_json("frags", video_id)
        transcript, row["transcript_sha256"], row["transcript_http"] = fetch_json("transcripts", video_id)
        if not isinstance(frags, list) or not frags or not all(numeric(x) and x >= 0 for x in frags):
            raise ValueError("frags is not a nonempty nonnegative numeric list")
        row["frags_count"] = len(frags)
        row["frags_first_s"] = frags[0]
        row["frags_last_s"] = frags[-1]
        increasing = all(a < b for a, b in zip(frags, frags[1:]))
        row["frags_strictly_increasing"] = increasing
        if not isinstance(transcript, list) or not transcript:
            raise ValueError("transcript is not a nonempty list")
        ends = []
        for segment in transcript:
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                raise ValueError("transcript segment lacks text")
            start, duration = segment.get("start"), segment.get("duration")
            if not numeric(start) or not numeric(duration) or start < 0 or duration < 0:
                raise ValueError("transcript segment has invalid timing")
            ends.append(start + duration)
        row["transcript_segments"] = len(ends)
        row["transcript_end_s"] = max(ends)
        within = frags[-1] <= max(ends)
        row["frags_within_transcript"] = within
        row["annotation_structure_status"] = "valid" if increasing and within else "review_timing"
    except Exception as exc:
        row["annotation_structure_status"] = "fetch_or_parse_failed"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def main() -> None:
    selected_bytes = SELECTED.read_bytes()
    if hashlib.sha256(selected_bytes).hexdigest() != SELECTED_SHA256:
        raise ValueError("selected cohort hash changed")
    selected = list(csv.DictReader(io.StringIO(selected_bytes.decode("utf-8"))))
    if len(selected) != 35 or len({row["video_id"] for row in selected}) != 35:
        raise ValueError("selected cohort must contain 35 unique IDs")
    results = [inspect(row["video_id"], row["course_id"], row["split_proposed"]) for row in selected]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(results)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError(f"locked audit artifact differs: {OUTPUT}")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    counts = {status: sum(row["annotation_structure_status"] == status for row in results)
              for status in ("valid", "review_timing", "fetch_or_parse_failed")}
    print(f"rows={len(results)} status={counts} output={OUTPUT}")


if __name__ == "__main__":
    main()
