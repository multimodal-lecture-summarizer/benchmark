"""Lock alternatives for seven held Yale lecturer groups before their GT/media review."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


REPORTS = Path(__file__).resolve().parents[2] / "plans" / "reports"
PREFIX = "rq1-yale-alternative-260930"


def digest(content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def csv_rows(filename: str) -> list[dict[str, str]]:
    with (REPORTS / filename).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    output = REPORTS / f"{PREFIX}-locked.csv"
    receipt = REPORTS / f"{PREFIX}-selection-receipt.json"
    if output.exists() or receipt.exists():
        raise FileExistsError("alternative tranche already locked")
    prior = csv_rows("rq1-yale-remaining-260929-locked.csv")
    gates = {row["lecturer"]: row for row in csv_rows("rq1-yale-remaining-260929-final-gates.csv")}
    snapshots = json.loads((REPORTS / "rq1-yale-remaining-260929-course-snapshot.json").read_text(encoding="utf-8"))
    by_url = {row["course_url"]: row for row in snapshots["source_pages"]}
    selected = []
    source_snapshot = []
    for row in prior:
        if gates[row["lecturer"]]["qualification_status"] == "pass":
            continue
        page = by_url[row["course_url"]]
        urls = page["lecture_urls"]
        alternatives = [url for url in urls if url != row["lecture_url"]]
        if not alternatives:
            raise ValueError(f"no alternate lecture: {row['lecturer']}")
        chosen = min(alternatives, key=digest)
        selected.append({"course_code": row["course_code"], "course_url": row["course_url"], "lecturer": row["lecturer"],
            "previous_lecture_url": row["lecture_url"], "alternative_lecture_url": chosen,
            "source_course_page_sha256": page["html_sha256"], "alternative_url_sha256": digest(chosen),
            "selection_status": "locked_before_alternative_lecture_gt_or_media"})
        source_snapshot.append({"course_url": row["course_url"], "source": "prior_locked_course_snapshot",
            "course_html_sha256": page["html_sha256"], "candidate_url_count": len(alternatives),
            "all_lecture_urls_sha256": page["lecture_urls_sha256"]})
    # PHYS 200 L19 was a preselected nine-course QA unit and failed the
    # boundary gate; use the same URL-hash choice for its first alternative.
    qa = csv_rows("rq1-yale-qa-existing-260930-final-gates.csv")
    phys = next(row for row in qa if row["course_id"] == "phys200")
    if phys["qualification_status"] != "hold_boundary":
        raise ValueError("PHYS 200 prior hold changed")
    course_url = "https://oyc.yale.edu/physics/phys-200"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(course_url, timeout=30) as response:
        if response.status != 200:
            raise ValueError(f"course HTTP {response.status}")
        course_html = response.read()
    soup = BeautifulSoup(course_html, "html.parser")
    urls = sorted({urllib.parse.urljoin(course_url, anchor["href"])
        for anchor in soup.select('a[href*="/lecture-"]')
        if re.search(r"/lecture-\d+/?$", anchor.get("href", ""))})
    alternatives = [url for url in urls if url != phys["publisher_page"]]
    if len(alternatives) < 2:
        raise ValueError("PHYS 200 course page has insufficient lectures")
    chosen = min(alternatives, key=digest)
    selected.append({"course_code": "PHYS 200", "course_url": course_url, "lecturer": phys["lecturer"],
        "previous_lecture_url": phys["publisher_page"], "alternative_lecture_url": chosen,
        "source_course_page_sha256": digest(course_html), "alternative_url_sha256": digest(chosen),
        "selection_status": "locked_before_alternative_lecture_gt_or_media"})
    source_snapshot.append({"course_url": course_url, "source": "publisher_course_page_at_lock",
        "course_html_sha256": digest(course_html), "candidate_url_count": len(alternatives),
        "all_lecture_urls_sha256": digest("\n".join(urls) + "\n")})
    if len(selected) != 7 or len({row["lecturer"] for row in selected}) != 7:
        raise ValueError("expected seven distinct held lecturer groups")
    selected.sort(key=lambda row: digest(row["lecturer"].lower()))
    with output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    receipt.write_text(json.dumps({"schema": "rq1-yale-alternative-tranche-lock/1",
        "qualification_only": True, "selection_rule": "six held groups from prior remaining tranche plus held PHYS200 QA group; choose minimum SHA256 lecture URL within same course excluding previously reviewed URL; no alternative lecture page/GT/media read before lock",
        "prior_lock_sha256": digest((REPORTS / "rq1-yale-remaining-260929-locked.csv").read_bytes()),
        "prior_gate_sha256": digest((REPORTS / "rq1-yale-remaining-260929-final-gates.csv").read_bytes()),
        "prior_qa_gate_sha256": digest((REPORTS / "rq1-yale-qa-existing-260930-final-gates.csv").read_bytes()),
        "locked_csv_sha256": digest(output.read_bytes()), "source_course_pages": source_snapshot}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"locked {len(selected)} alternatives before GT/media review")


if __name__ == "__main__":
    main()
