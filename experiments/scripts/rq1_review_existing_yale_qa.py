"""Finish source-only diagnostics for two preselected Yale QA MOV files."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

from experiments.scripts.rq1_locked_yale_boundary_diagnostics import process
from experiments.scripts.rq1_locked_yale_media_receipt import sha256_file
from experiments.scripts.rq1_review_remaining_yale_media import storyboard


REPO = Path(__file__).resolve().parents[2]
REPORTS = REPO.parent / "plans" / "reports"
OUTPUT = REPO / "experiments" / "datasets" / "yale_rq1_qualification" / "qa_existing_diagnostics"
BRIDGE = REPORTS / "rq1-yale-qa-existing-260929-source-bridge.json"
RECEIPTS = {
    "econ159": "rq1-yale-260928-2157-econ159-l2-local-mov-receipt.json",
    "phys200": "rq1-yale-260929-0827-phys200-l19-local-mov-receipt.json",
}


def main() -> None:
    from faster_whisper import WhisperModel

    if BRIDGE.exists():
        raise FileExistsError(BRIDGE)
    snapshot = json.loads((REPORTS / "rq1-yale-260929-1111-source-gt-snapshot-receipt.json").read_text(encoding="utf-8"))
    by_course = {item["course_id"]: item for item in snapshot["files"]}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    prepared = []
    for course_id, receipt_name in RECEIPTS.items():
        receipt = json.loads((REPORTS / receipt_name).read_text(encoding="utf-8"))
        source = by_course[course_id]
        path = Path(receipt["local_path"])
        if not path.is_file() or path.stat().st_size != receipt["file_size_bytes"] or sha256_file(path) != receipt["sha256"]:
            raise ValueError(f"previous exact local MOV changed: {path}")
        if receipt["full_video_audio_decode_exit_code"] != 0:
            raise ValueError(f"previous full decode absent: {path}")
        with opener.open(source["source_url"], timeout=30) as response:
            html = response.read()
        soup = BeautifulSoup(html, "html.parser")
        block = soup.select_one("#block-yale-oyc-views-block-session-lecture-chapters-block-1")
        names = [node.get_text(" ", strip=True) for node in block.select(".views-field-field-session-chapters-name .field-content")]
        starts = [int(node.get_text(" ", strip=True)) for node in block.select(".views-field-field-session-chapter-start-time .field-content")]
        if [(name, second) for name, second in zip(names, starts)] != [(item["title"], item["start_s"]) for item in source["publisher_chapters"]] or len(names) != len(starts):
            raise ValueError(f"publisher GT drift or pair mismatch: {course_id}")
        iframe = soup.select_one('iframe[src*="youtube.com/embed/"]')
        match = re.search(r"/embed/([A-Za-z0-9_-]{11})", iframe.get("src", "") if iframe else "")
        if not match:
            raise ValueError(f"publisher video ID absent: {course_id}")
        video_id = match.group(1)
        prepared.append({"video_id": video_id, "course_id": course_id, "lecturer": "Ben Polak" if course_id == "econ159" else "Ramamurti Shankar", "lecture_no": receipt["lecture_no"], "publisher_page": source["source_url"], "page_html_sha256_current": hashlib.sha256(html).hexdigest(), "page_html_sha256_prior": source["source_html_sha256"], "publisher_gt_sha256_prior": source["publisher_chapters_sha256"], "local_media_path": str(path.resolve()), "local_media_sha256": receipt["sha256"], "previous_full_decode_exit_code": 0, "pairs": [{"chapter_index": index, "original_label": item["title"], "original_time_sec": item["start_s"]} for index, item in enumerate(source["publisher_chapters"], 1)]})
    BRIDGE.write_text(json.dumps({"schema": "rq1-yale-existing-qa-source-bridge/1", "qualification_only": True, "source_selection": "preselected nine-course Yale QA sample; no replacement", "files": prepared}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8", local_files_only=True)
    for item in prepared:
        path = Path(item["local_media_path"])
        manifest = {"expected_bytes": path.stat().st_size}
        process(item["video_id"], path, manifest, item["pairs"], model, OUTPUT)
        import subprocess
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True, timeout=30)
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        storyboard(item["video_id"], path, duration, OUTPUT)
        print(f"REVIEW MATERIAL {item['course_id']} {item['video_id']}", flush=True)


if __name__ == "__main__":
    main()
