"""Record exact publisher GT and media HEAD metadata after the Yale lock."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


REPORTS = Path(__file__).resolve().parents[2] / "plans" / "reports"
DEFAULT_PREFIX = "rq1-yale-remaining-260929"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request(url: str, method: str = "GET") -> urllib.response.addinfourl:
    return OPENER.open(urllib.request.Request(url, method=method, headers={"User-Agent": "RQ1 source qualification/1.0"}), timeout=40)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def media_head(mp3_url: str) -> tuple[str, int]:
    match = re.search(r"/courses/([^/]+)/([^/]+)/mp3/+([^/]+)\.mp3", mp3_url)
    if not match:
        raise ValueError(f"unrecognized publisher audio path: {mp3_url}")
    base = f"https://openmedia.yale.edu/projects/courses/{match[1]}/{match[2]}"
    for directory in ("iphone", "m4v", "mov"):
        suffix = "mov" if directory == "mov" else "m4v"
        url = f"{base}/{directory}/{match[3]}.{suffix}"
        try:
            with request(url, "HEAD") as response:
                size = int(response.headers.get("Content-Length", "0"))
                if response.status == 200 and size > 0 and response.headers.get("Content-Type", "").startswith("video/"):
                    return url, size
        except (OSError, ValueError):
            continue
    raise ValueError(f"no exact publisher video HEAD for {mp3_url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--expected", type=int, default=11)
    parser.add_argument("--lecture-url-field", default="lecture_url")
    args = parser.parse_args()
    metadata_path = REPORTS / f"{args.prefix}-source-metadata.csv"
    pairs_path = REPORTS / f"{args.prefix}-source-pairs.csv"
    acquisition_path = REPORTS / f"{args.prefix}-media-acquisition.csv"
    if any(path.exists() for path in (metadata_path, pairs_path, acquisition_path)):
        raise FileExistsError("Yale source probe already exists")
    with (REPORTS / f"{args.prefix}-locked.csv").open(encoding="utf-8", newline="") as stream:
        locked = list(csv.DictReader(stream))
    if len(locked) != args.expected:
        raise ValueError(f"unexpected lock count: {len(locked)}")
    metadata: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []
    acquisition: list[dict[str, object]] = []
    for index, row in enumerate(locked, 1):
        lecture_url = row[args.lecture_url_field]
        with request(lecture_url) as response:
            html = response.read()
            if response.geturl() != lecture_url:
                raise ValueError(f"publisher URL moved: {lecture_url}")
        soup = BeautifulSoup(html, "html.parser")
        chapter_block = soup.select_one("#block-yale-oyc-views-block-session-lecture-chapters-block-1")
        if chapter_block is None:
            raise ValueError(f"chapter block absent: {lecture_url}")
        labels = [node.get_text(" ", strip=True) for node in chapter_block.select(".views-field-field-session-chapters-name .field-content")]
        times_text = [node.get_text(" ", strip=True) for node in chapter_block.select(".views-field-field-session-chapter-start-time .field-content")]
        times = [int(value) for value in times_text] if all(value.isdigit() for value in times_text) else []
        valid = len(labels) == len(times) and len(times) >= 2 and times[0] == 0 and all(a < b for a, b in zip(times, times[1:]))
        iframe = soup.select_one('iframe[src*="youtube.com/embed/"]')
        video_id_match = re.search(r"/embed/([A-Za-z0-9_-]{11})", iframe.get("src", "") if iframe else "")
        video_id = video_id_match.group(1) if video_id_match else ""
        mp3 = [urllib.parse.urljoin(lecture_url, node["href"]) for node in soup.select('a[href$=".mp3"]')]
        credit_urls = [urllib.parse.urljoin(lecture_url, node["href"]) for node in soup.select("a[href]") if "credit" in node.get_text(" ", strip=True).lower()]
        media_url, media_bytes = media_head(mp3[0]) if mp3 else ("", 0)
        status = "source_gt_present_media_head_pass" if valid and video_id and media_url else "hold_source_gt_or_identity"
        pair_payload = [{"label": label, "time": second} for label, second in zip(labels, times)] if valid else []
        pair_hash = sha(json.dumps(pair_payload, ensure_ascii=False, separators=(",", ":")).encode()) if valid else ""
        metadata.append({
            "order": index, "course_code": row["course_code"], "lecturer": row["lecturer"],
            "lecture_url": lecture_url, "video_id": video_id,
            "source_html_sha256": sha(html), "gt_block_sha256": sha(str(chapter_block).encode()),
            "label_count": len(labels), "time_count": len(times_text),
            "original_times_s": ";".join(times_text), "source_pairs_sha256": pair_hash,
            "source_status": status, "publisher_mp3_url": mp3[0] if mp3 else "",
            "publisher_credit_urls": ";".join(credit_urls),
        })
        if valid:
            for pair_index, (label, second) in enumerate(zip(labels, times), 1):
                pairs.append({
                    "video_id": video_id, "course_code": row["course_code"],
                    "lecturer": row["lecturer"], "publisher_page": lecture_url,
                    "chapter_index": pair_index, "original_label": label,
                    "original_time_sec": second, "structural_zero": pair_index == 1,
                    "source_pairs_sha256": pair_hash,
                })
        acquisition.append({
            "order": index, "course_code": row["course_code"], "lecturer": row["lecturer"],
            "lecture_url": lecture_url, "video_id": video_id,
            "source_url": media_url, "expected_bytes": media_bytes,
            "filename": urllib.parse.urlparse(media_url).path.rsplit("/", 1)[-1] if media_url else "",
            "source_status": status, "acquisition_action": "download" if status == "source_gt_present_media_head_pass" else "hold_source",
        })
        print(f"{index} {row['course_code']} {video_id} {len(labels)}/{len(times_text)} {status}", flush=True)
    write_csv(metadata_path, metadata)
    write_csv(pairs_path, pairs)
    write_csv(acquisition_path, acquisition)


if __name__ == "__main__":
    main()
