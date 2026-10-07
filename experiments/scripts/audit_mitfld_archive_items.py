"""Check Archive item metadata for exact OCW-linked selected MITFLD MP4s."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "plans/reports/mitfld-rq1-35-260928-1135-ocw-source-rights-ledger.csv"
SOURCE_SHA256 = "36419f9a3209405647a854032ce7b7acd654dad7fc4086d68aedcb7b44019d10"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1143-archive-item-metadata.csv"
FIELDS = (
    "video_id", "course_id", "item_id", "item_metadata_url", "mp4_filename",
    "creator", "uploader", "licenseurl", "file_listed", "file_source", "file_size_bytes",
    "metadata_status", "error",
)


def fetch_item(item_id: str) -> dict:
    request = urllib.request.Request(
        f"https://archive.org/metadata/{item_id}",
        headers={"User-Agent": "rq1-mitfld-qualification/1.0"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(5_000_001)
    if len(body) > 5_000_000:
        raise ValueError("item metadata exceeds 5 MB cap")
    return json.loads(body)


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("source rights ledger hash changed")
    source = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8"))))
    if len(source) != 35 or len({row["video_id"] for row in source}) != 35:
        raise ValueError("source rights ledger must contain 35 unique selected IDs")
    archive = [row for row in source if urlparse(row["ocw_mp4_url"]).hostname == "archive.org"]
    if len(archive) != 27:
        raise ValueError("expected 27 OCW-linked Archive MP4s")
    results = []
    cache: dict[str, dict] = {}
    for row in archive:
        item_id = urlparse(row["archive_item_url"]).path.rstrip("/").split("/")[-1]
        filename = unquote(urlparse(row["ocw_mp4_url"]).path.rsplit("/", 1)[-1])
        result = {
            "video_id": row["video_id"], "course_id": row["course_id"],
            "item_id": item_id, "item_metadata_url": f"https://archive.org/metadata/{item_id}",
            "mp4_filename": filename,
        }
        try:
            if item_id not in cache:
                cache[item_id] = fetch_item(item_id)
            data = cache[item_id]
            meta = data.get("metadata", {})
            match = next((f for f in data.get("files", []) if f.get("name") == filename), None)
            result.update({
                "creator": meta.get("creator", ""), "uploader": meta.get("uploader", ""),
                "licenseurl": meta.get("licenseurl", ""), "file_listed": bool(match),
                "file_source": match.get("source", "") if match else "",
                "file_size_bytes": match.get("size", "") if match else "",
            })
            license_url = urlparse(str(result["licenseurl"]))
            result["metadata_status"] = (
                "ocw_uploaded_cc_by_nc_sa_original_file"
                if result["creator"] == "MIT OpenCourseWare"
                and result["uploader"] == "ocw-prod@mit.edu"
                and license_url.hostname == "creativecommons.org"
                and license_url.path == "/licenses/by-nc-sa/4.0/"
                and result["file_source"] == "original"
                else "review_item_or_file"
            )
        except Exception as exc:
            result["metadata_status"] = "fetch_failed"
            result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(results)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError(f"locked audit artifact differs: {OUTPUT}")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    counts = {status: sum(row["metadata_status"] == status for row in results)
              for status in ("ocw_uploaded_cc_by_nc_sa_original_file", "review_item_or_file", "fetch_failed")}
    print(f"archive_videos={len(results)} archive_items={len(cache)} status={counts} sha256={hashlib.sha256(content).hexdigest()}")


if __name__ == "__main__":
    main()
