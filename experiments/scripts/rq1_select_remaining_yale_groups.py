"""Lock one publisher-native lecture per remaining, uninspected Yale lecturer group.

Reads course pages only. It never opens lecture pages, chapter GT, or media.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup


REPORTS = Path(__file__).resolve().parents[2] / "plans" / "reports"
INVENTORY = REPORTS / "rq1-yale-publisher-course-inventory-260929.csv"
OUTPUT = REPORTS / "rq1-yale-remaining-260929-locked.csv"
RECEIPT = REPORTS / "rq1-yale-remaining-260929-course-snapshot.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (REPORTS / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def course_key(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1].replace("-", "")


def fetch_course(url: str) -> tuple[bytes, list[str]]:
    # The caller's terminal may have an inactive localhost proxy. Use the
    # publisher connection directly; no selected lecture page is requested.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, headers={"User-Agent": "RQ1 metadata qualification/1.0"})
    with opener.open(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"course HTTP {response.status}: {url}")
        html = response.read()
    soup = BeautifulSoup(html, "html.parser")
    links = {
        urllib.parse.urljoin(url, anchor["href"])
        for anchor in soup.select('a[href*="/lecture-"]')
        if re.search(r"/lecture-\d+/?$", anchor.get("href", ""))
    }
    if not links:
        raise ValueError(f"no lecture links: {url}")
    return html, sorted(links)


def main() -> None:
    if OUTPUT.exists() or RECEIPT.exists():
        raise FileExistsError("selection is already locked")
    inventory = read_csv(INVENTORY.name)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in inventory:
        grouped[row["lecturer"]].append(row)
    if len(grouped) != 36:
        raise ValueError(f"unexpected Yale group count: {len(grouped)}")

    prior_native = {row["lecturer"] for row in read_csv("rq1-yale-native-batch-260929-locked.csv")}
    prior_courses = {
        row["course_id"] for row in read_csv("rq1-yale-260928-1952-nine-course-qa-sample.csv")
    }
    prior_courses |= {
        row["course_id"].removeprefix("yale-")
        for row in read_csv("rq1-expansion-batch-260929-2015-locked.csv")
    }
    previously_inspected = prior_native | {
        row["lecturer"] for row in inventory if course_key(row["course_url"]) in prior_courses
    }
    remaining = sorted(set(grouped) - previously_inspected, key=lambda lecturer: sha256_text(lecturer.lower()))
    if len(remaining) != 11:
        raise ValueError(f"unexpected remaining new groups: {len(remaining)}")

    selected = []
    source_pages = []
    for order, lecturer in enumerate(remaining, 1):
        course = min(grouped[lecturer], key=lambda row: sha256_text(row["course_url"]))
        html, lectures = fetch_course(course["course_url"])
        chosen = min(lectures, key=sha256_text)
        source_pages.append({
            "course_url": course["course_url"],
            "html_sha256": sha256_bytes(html),
            "lecture_urls_sha256": sha256_text("\n".join(lectures) + "\n"),
            "lecture_urls": lectures,
        })
        selected.append({
            "order": order,
            "course_code": course["course_code"],
            "course_url": course["course_url"],
            "lecturer": lecturer,
            "lecture_url": chosen,
            "course_lecture_count": len(lectures),
            "lecturer_sha256": sha256_text(lecturer.lower()),
            "course_html_sha256": sha256_bytes(html),
            "lecture_url_sha256": sha256_text(chosen),
            "status": "locked_before_lecture_gt_or_media",
        })
        print(f"{order:02d} {course['course_code']} {chosen}", flush=True)

    columns = list(selected[0])
    with OUTPUT.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(selected)
    receipt = {
        "schema": "rq1-yale-remaining-course-metadata-lock/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection_rule": "remaining uninspected Yale lecturer groups; sha256(lowercase lecturer), min sha256(course URL), min sha256(lecture URL)",
        "inventory_sha256": sha256_bytes(INVENTORY.read_bytes()),
        "previously_inspected_lecturer_count": len(previously_inspected),
        "remaining_new_lecturer_count": len(remaining),
        "locked_csv_sha256": sha256_bytes(OUTPUT.read_bytes()),
        "source_pages": source_pages,
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
