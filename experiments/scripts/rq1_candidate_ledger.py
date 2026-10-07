"""Bounded, resumable RQ1 source-qualification probes (diagnostic, Phase 1).

This module builds a per-lecture candidate ledger for the RQ1 chaptering study.
It performs metadata-scale network requests only: HTML pages, JSON APIs and
container headers read by ``ffprobe``.  It never downloads full media, never
edits or invents boundary timestamps and never infers rights for one unit from
another unit.

Every request is logged to ``probe_log.jsonl`` and cached under ``http_cache/``
so a re-run is resumable and reproducible from the same bytes.

Ledger record fields (one record per lecture/unit):
    source_id, course_id, lecture_id, boundary_origin, video_url, gt_url,
    rights_url, rights_status, access_status, exclusion_reason, evidence

Usage::

    python -m experiments.scripts.rq1_candidate_ledger --output-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

USER_AGENT = "mls-rq1-qualification-probe/1 (metadata-only research probe)"
DEFAULT_TIMEOUT_SEC = 45
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
DEFAULT_DELAY_SEC = 0.25

# Predeclared selection rules.  They are fixed before any model output exists.
OCW_COURSES: tuple[str, ...] = (
    # Named by the AVLectures paper (Sec. 3.2, footnote 6) as a timed-TOC course.
    "18-01sc-single-variable-calculus-fall-2010",
)
OCW_MAX_PAGES_PER_COURSE = 400
OCW_MEDIA_PROBE_SAMPLE = 6          # lectures selected by sha256(lecture_id) order
YTSEG_SAMPLE_OFFSETS = (0, 700)     # per split, 20 rows per offset
YTSEG_SAMPLE_LENGTH = 20
YTSEG_SPLITS = ("validation", "test")

AVLECTURES_README = "https://raw.githubusercontent.com/Darshansingh11/AVLectures/main/README.md"
AVLECTURES_LICENSE = "https://raw.githubusercontent.com/Darshansingh11/AVLectures/main/LICENSE"
AVLECTURES_COMMITS = "https://api.github.com/repos/Darshansingh11/AVLectures/commits?per_page=1"
AVLECTURES_IDP_ID = "52e67bb5-5acd-438d-a13b-f255cee17432"
AVLECTURES_IDP_PAGE = f"https://india-data.org/dataset-details/{AVLECTURES_IDP_ID}"
AVLECTURES_IDP_API = f"https://india-data.org/core/dataset/get-versions?dataset_id={AVLECTURES_IDP_ID}"

YTSEG_API = "https://huggingface.co/api/datasets/retkowski/ytseg"
YTSEG_ROWS = (
    "https://datasets-server.huggingface.co/rows?dataset=retkowski/ytseg"
    "&config=text&split={split}&offset={offset}&length={length}"
)

_RESERVED_RE = re.compile(
    r"(?i)(all rights reserved|excluded from our creative commons license)"
)
_LICENSE_RE = re.compile(r'"license"\s*:\s*"(https://creativecommons\.org/licenses/[^"]+)"')
_YT_EMBED_RE = re.compile(r"youtube\.com/embed/([A-Za-z0-9_\-]{6,})")
_START_RE = re.compile(r'"start"\s*:\s*([0-9]+(?:\.[0-9]+)?)')
_END_RE = re.compile(r'"end"\s*:\s*([0-9]+(?:\.[0-9]+)?)')
_DOWNLOAD_RE = re.compile(r'data-downloadlink\s*=\s*"([^"]+)"')
_VTT_RE = re.compile(r'<track[^>]+src="([^"]+\.vtt)"')
_TITLE_RE = re.compile(r'<meta property="og:title" content="([^"]+)"')
_PARENT_RE = re.compile(r'<div class="course-content-parent-title">([^<]+)</div>')
_FROM_LECTURE_RE = re.compile(
    r'From (?:Lecture|Recitation) ([0-9]+) of <a href="(/courses/[^"/]+)/'
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProbeResult:
    url: str
    status: int | None
    body: bytes
    error: str | None
    sha256: str | None
    from_cache: bool

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text())


@dataclass
class Prober:
    """Bounded HTTP client with request log and content cache (resumable)."""

    output_dir: Path
    timeout_sec: float = DEFAULT_TIMEOUT_SEC
    max_bytes: int = DEFAULT_MAX_BYTES
    delay_sec: float = DEFAULT_DELAY_SEC
    offline: bool = False
    request_count: int = 0
    network_bytes: int = 0
    _log_path: Path = field(init=False)
    _cache_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self.output_dir / "probe_log.jsonl"
        self._cache_dir = self.output_dir / "http_cache"
        self._cache_dir.mkdir(exist_ok=True)

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{key}.body", self._cache_dir / f"{key}.meta.json"

    def _log(self, record: dict[str, Any]) -> None:
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def get(self, url: str) -> ProbeResult:
        body_path, meta_path = self._cache_paths(url)
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            body = body_path.read_bytes() if body_path.is_file() else b""
            return ProbeResult(url, meta.get("status"), body, meta.get("error"),
                               meta.get("sha256"), True)
        if self.offline:
            return ProbeResult(url, None, b"", "offline: not cached", None, True)
        time.sleep(self.delay_sec)
        status: int | None = None
        error: str | None = None
        body = b""
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                status = int(response.status)
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    error = f"truncated: response exceeds {self.max_bytes} bytes"
                    body = body[: self.max_bytes]
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            try:
                body = exc.read(64 * 1024)
            except Exception:  # pragma: no cover - defensive
                body = b""
            error = f"HTTP {exc.code}"
        except Exception as exc:  # network error, timeout, DNS
            error = f"{type(exc).__name__}: {exc}"
        self.request_count += 1
        self.network_bytes += len(body)
        digest = hashlib.sha256(body).hexdigest() if body else None
        body_path.write_bytes(body)
        meta = {"url": url, "status": status, "error": error, "sha256": digest,
                "bytes": len(body), "fetched_at": _now()}
        meta_path.write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
        self._log({"kind": "http_get", **meta})
        return ProbeResult(url, status, body, error, digest, False)

    def ffprobe_duration(self, url: str) -> dict[str, Any]:
        """Read container duration from remote media headers (no full download)."""
        cache = self._cache_dir / (hashlib.sha256(("ffprobe:" + url).encode()).hexdigest() + ".ffprobe.json")
        if cache.is_file():
            return json.loads(cache.read_text(encoding="utf-8"))
        if self.offline:
            return {"url": url, "duration_sec": None, "error": "offline: not cached"}
        exe = shutil.which("ffprobe")
        result: dict[str, Any] = {"url": url, "duration_sec": None, "error": None,
                                  "probed_at": _now()}
        if not exe:
            result["error"] = "ffprobe not installed"
        else:
            try:
                completed = subprocess.run(
                    [exe, "-v", "error", "-show_entries", "format=duration,size,format_name",
                     "-of", "json", url],
                    capture_output=True, text=True, timeout=120, check=False,
                )
                if completed.returncode != 0:
                    result["error"] = (completed.stderr or "ffprobe failed").strip()[:400]
                else:
                    fmt = json.loads(completed.stdout or "{}").get("format", {})
                    result["duration_sec"] = float(fmt["duration"]) if fmt.get("duration") else None
                    result["size_bytes"] = int(fmt["size"]) if fmt.get("size") else None
                    result["format_name"] = fmt.get("format_name")
            except subprocess.TimeoutExpired:
                result["error"] = "ffprobe timeout after 120s"
        self.request_count += 1
        cache.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
        self._log({"kind": "ffprobe", **result})
        return result


def _ledger_record(**kwargs: Any) -> dict[str, Any]:
    record = {
        "source_id": None, "course_id": None, "lecture_id": None, "boundary_origin": None,
        "video_url": None, "gt_url": None, "rights_url": None, "rights_status": "unknown",
        "access_status": "unknown", "exclusion_reason": None, "evidence": {},
    }
    record.update(kwargs)
    return record


# ---------------------------------------------------------------------------
# AVLectures (author archive)
# ---------------------------------------------------------------------------


def probe_avlectures(prober: Prober) -> dict[str, Any]:
    readme = prober.get(AVLECTURES_README)
    license_file = prober.get(AVLECTURES_LICENSE)
    commits = prober.get(AVLECTURES_COMMITS)
    idp_page = prober.get(AVLECTURES_IDP_PAGE)
    idp_api = prober.get(AVLECTURES_IDP_API)

    readme_text = readme.text()
    license_text = license_file.text()
    revision = None
    try:
        revision = commits.json()[0]["sha"]
    except Exception:
        pass
    readme_license = None
    match = re.search(r"License:\s*([A-Z\- 0-9\.]+?)\]", readme_text)
    if match:
        readme_license = match.group(1).strip()
    license_file_kind = "CC0-1.0" if "CC0 1.0 Universal" in license_text else (
        "unknown" if not license_text else "other")
    api_body = idp_api.text()[:300]
    token_required = idp_api.status == 401 or "access token" in api_body.lower()
    access_status = "blocked_access" if token_required or idp_api.status != 200 else "unverified"
    return _ledger_record(
        source_id="avlectures_cws",
        course_id="*",
        lecture_id="*",
        boundary_origin="author_segments_ts_txt (timed-TOC or joined-clip, per course)",
        video_url=None,
        gt_url="segmentation/segments_ts.txt inside per-course tar (not retrieved)",
        rights_url=AVLECTURES_LICENSE,
        rights_status="conflicting_repository_license_and_unknown_video_rights",
        access_status=access_status,
        exclusion_reason=(
            "archive download requires an authenticated india-data.org account "
            "(API returned access-token error); no course tar, video or segments_ts.txt "
            "was retrieved, so no per-lecture rights or boundaries can be verified"
        ),
        evidence={
            "repository_revision": revision,
            "readme_sha256": readme.sha256,
            "readme_license_badge": readme_license,
            "license_file_kind": license_file_kind,
            "license_file_sha256": license_file.sha256,
            "license_note": (
                "repository LICENSE file is CC0-1.0 while README badge declares CC BY-NC 4.0; "
                "neither covers MIT OCW video rights"
            ),
            "download_page": AVLECTURES_IDP_PAGE,
            "download_page_status": idp_page.status,
            "download_api": AVLECTURES_IDP_API,
            "download_api_status": idp_api.status,
            "download_api_body_excerpt": api_body,
            "cws_structure": "15 CwS courses: 5 timed-TOC (web-scraped TOC), 10 re-assembled joined clips",
            "joined_clip_stratum": "separate sensitivity stratum; excluded from primary pilot",
        },
    )


# ---------------------------------------------------------------------------
# MIT OCW timed table of contents (clip offsets into full lectures)
# ---------------------------------------------------------------------------


def parse_ocw_clip_page(page_html: str) -> dict[str, Any]:
    """Extract published clip offsets and rights notices from one OCW resource page."""
    unescaped = html.unescape(page_html)
    video_idx = unescaped.find("<video")
    video_block = unescaped[video_idx: video_idx + 4000] if video_idx >= 0 else ""
    start = _START_RE.search(video_block)
    end = _END_RE.search(video_block)
    yt = _YT_EMBED_RE.search(video_block)
    download = _DOWNLOAD_RE.search(video_block)
    vtt = _VTT_RE.search(video_block)
    title = _TITLE_RE.search(unescaped)
    parent = _PARENT_RE.search(unescaped)
    from_lecture = _FROM_LECTURE_RE.search(unescaped)
    licence = _LICENSE_RE.search(unescaped)
    return {
        "title": title.group(1).split(" | ")[0].strip() if title else None,
        "parent_title": parent.group(1).strip() if parent else None,
        "youtube_id": yt.group(1) if yt else None,
        "start_sec": float(start.group(1)) if start else None,
        "end_sec": float(end.group(1)) if end else None,
        "download_url": download.group(1) if download else None,
        "caption_vtt": vtt.group(1) if vtt else None,
        "source_lecture_number": int(from_lecture.group(1)) if from_lecture else None,
        "source_course_path": from_lecture.group(2) if from_lecture else None,
        "license_url": licence.group(1) if licence else None,
        "reserved_marking": bool(_RESERVED_RE.search(unescaped)),
    }


def derive_boundaries(segments: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """Derive inter-chapter boundaries from published (start, end) clip offsets.

    A boundary is the published start time of every clip after the first.  The
    offsets are used exactly as published; gaps and overlaps are counted, never
    repaired.
    """
    unique = sorted({(float(s), float(e)) for s, e in segments})
    starts = [s for s, _ in unique]
    gaps: list[float] = []
    overlaps = 0
    invalid = 0
    for s, e in unique:
        if not e > s:
            invalid += 1
    for (s0, e0), (s1, _e1) in zip(unique, unique[1:]):
        if s1 < e0:
            overlaps += 1
        elif s1 > e0:
            gaps.append(round(s1 - e0, 3))
    duplicate_starts = len(starts) - len(set(starts))
    boundaries = sorted(set(starts[1:])) if len(starts) > 1 else []
    return {
        "segments": [[s, e] for s, e in unique],
        "chapter_boundaries_sec": boundaries,
        "first_start_sec": starts[0] if starts else None,
        "last_end_sec": unique[-1][1] if unique else None,
        "gap_count": len(gaps),
        "max_gap_sec": max(gaps) if gaps else 0.0,
        "overlap_count": overlaps,
        "invalid_segment_count": invalid,
        "duplicate_start_count": duplicate_starts,
    }


def _ocw_sitemap_resource_urls(sitemap_xml: str, course: str) -> list[str]:
    urls = re.findall(r"<loc>([^<]+)</loc>", sitemap_xml)
    base = f"https://ocw.mit.edu/courses/{course}/resources/"
    return sorted({u for u in urls if u.startswith(base) and "/resources/clip-" in u})


def probe_ocw_course(prober: Prober, course: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sitemap_url = f"https://ocw.mit.edu/courses/{course}/sitemap.xml"
    sitemap = prober.get(sitemap_url)
    course_summary: dict[str, Any] = {
        "course": course, "sitemap_url": sitemap_url, "sitemap_status": sitemap.status,
        "sitemap_sha256": sitemap.sha256,
    }
    if sitemap.status != 200:
        course_summary["error"] = sitemap.error
        return [], course_summary
    clip_urls = _ocw_sitemap_resource_urls(sitemap.text(), course)
    course_summary["clip_page_count"] = len(clip_urls)
    truncated = len(clip_urls) > OCW_MAX_PAGES_PER_COURSE
    clip_urls = clip_urls[:OCW_MAX_PAGES_PER_COURSE]
    course_summary["clip_pages_probed"] = len(clip_urls)
    course_summary["clip_page_cap_hit"] = truncated

    clips: list[dict[str, Any]] = []
    failed_pages = 0
    for url in clip_urls:
        page = prober.get(url)
        if page.status != 200:
            failed_pages += 1
            continue
        parsed = parse_ocw_clip_page(page.text())
        parsed["page_url"] = url
        parsed["page_sha256"] = page.sha256
        clips.append(parsed)
    course_summary["failed_pages"] = failed_pages
    course_summary["clips_without_offsets"] = sum(1 for c in clips if c["start_sec"] is None)

    by_video: dict[str, list[dict[str, Any]]] = {}
    for clip in clips:
        if clip["youtube_id"]:
            by_video.setdefault(clip["youtube_id"], []).append(clip)

    records: list[dict[str, Any]] = []
    for youtube_id, video_clips in sorted(by_video.items()):
        timed = [c for c in video_clips if c["start_sec"] is not None and c["end_sec"] is not None]
        lecture_numbers = sorted({c["source_lecture_number"] for c in video_clips
                                  if c["source_lecture_number"] is not None})
        source_courses = sorted({c["source_course_path"] for c in video_clips
                                 if c["source_course_path"]})
        downloads = sorted({c["download_url"] for c in video_clips if c["download_url"]})
        licences = sorted({c["license_url"] or "missing" for c in video_clips})
        reserved = any(c["reserved_marking"] for c in video_clips)
        derived = derive_boundaries([(c["start_sec"], c["end_sec"]) for c in timed])
        exclusion: list[str] = []
        if not timed:
            exclusion.append("no_published_offsets")
        elif len(timed) < 2:
            exclusion.append("single_clip_no_internal_boundary")
        if len(timed) < len(video_clips):
            exclusion.append("some_clips_without_offsets")
        if derived["overlap_count"] or derived["invalid_segment_count"]:
            exclusion.append("overlapping_or_invalid_offsets")
        if len(lecture_numbers) > 1 or len(source_courses) > 1:
            exclusion.append("ambiguous_source_lecture_mapping")
        if not downloads:
            exclusion.append("no_media_download_url")
        if reserved:
            exclusion.append("reserved_rights_marking")
        if licences != ["https://creativecommons.org/licenses/by-nc-sa/4.0/"]:
            exclusion.append("license_not_uniform_cc_by_nc_sa_4.0")
        rights_status = (
            "cc_by_nc_sa_4.0_page_notice_per_clip_no_reserved_marking"
            if not reserved and licences == ["https://creativecommons.org/licenses/by-nc-sa/4.0/"]
            else ("blocked_rights" if reserved else "unknown")
        )
        lecture_id = (
            f"{source_courses[0].rsplit('/', 1)[-1]}:lec{lecture_numbers[0]:02d}"
            if len(lecture_numbers) == 1 and len(source_courses) == 1
            else f"youtube:{youtube_id}"
        )
        records.append(_ledger_record(
            source_id="mit_ocw_timed_toc",
            course_id=source_courses[0].rsplit("/", 1)[-1] if len(source_courses) == 1 else course,
            lecture_id=lecture_id,
            boundary_origin="ocw_published_clip_offsets (editorial excerpt start times)",
            video_url=downloads[0] if downloads else f"https://www.youtube.com/watch?v={youtube_id}",
            gt_url=[c["page_url"] for c in timed],
            rights_url=[c["page_url"] for c in video_clips],
            rights_status=rights_status,
            access_status="media_url_published" if downloads else "unknown",
            exclusion_reason=";".join(exclusion) or None,
            evidence={
                "publishing_course": course,
                "youtube_id": youtube_id,
                "clip_count": len(video_clips),
                "timed_clip_count": len(timed),
                "clip_titles": [c["title"] for c in sorted(timed, key=lambda c: c["start_sec"])],
                "licenses": licences,
                "reserved_marking": reserved,
                "caption_vtt": sorted({c["caption_vtt"] for c in video_clips if c["caption_vtt"]}),
                "download_urls": downloads,
                "page_sha256": sorted(c["page_sha256"] for c in video_clips if c["page_sha256"]),
                **derived,
            },
        ))
    return records, course_summary


def select_media_probe_sample(records: Sequence[dict[str, Any]], k: int) -> list[str]:
    """Deterministic, outcome-independent sample: first k lecture_ids by sha256."""
    eligible = [r["lecture_id"] for r in records if not r["exclusion_reason"]]
    return sorted(eligible, key=lambda lid: hashlib.sha256(lid.encode()).hexdigest())[:k]


_ARCHIVE_ITEM_RE = re.compile(r"archive\.org/download/([^/]+)/")


def attach_media_rights(prober: Prober, record: dict[str, Any]) -> None:
    """Record the media host's own licence for this exact media item."""
    match = _ARCHIVE_ITEM_RE.search(str(record["video_url"]))
    evidence = record["evidence"]
    if not match:
        evidence["media_item_rights"] = {"status": "unknown", "reason": "media not on archive.org"}
        return
    url = f"https://archive.org/metadata/{match.group(1)}/metadata"
    response = prober.get(url)
    try:
        meta = response.json().get("result", {})
    except Exception:
        meta = {}
    evidence["media_item_rights"] = {
        "metadata_url": url,
        "status": response.status,
        "identifier": meta.get("identifier"),
        "licenseurl": meta.get("licenseurl"),
        "creator": meta.get("creator"),
        "rights": meta.get("rights"),
    }
    licence = str(meta.get("licenseurl") or "")
    if "by-nc-sa" not in licence:
        reasons = [r for r in (record["exclusion_reason"] or "").split(";") if r]
        reasons.append("media_item_license_not_cc_by_nc_sa")
        record["exclusion_reason"] = ";".join(reasons)
    elif record["rights_status"].startswith("cc_by_nc_sa"):
        record["rights_status"] = (
            "cc_by_nc_sa: ocw clip pages 4.0 + archive.org media item "
            f"{licence.rstrip('/').rsplit('/', 1)[-1]}; no reserved marking; human review pending"
        )


def attach_media_probe(prober: Prober, record: dict[str, Any]) -> None:
    url = record["video_url"]
    probe = prober.ffprobe_duration(url)
    evidence = record["evidence"]
    evidence["media_probe"] = probe
    attach_media_rights(prober, record)
    duration = probe.get("duration_sec")
    reasons = [r for r in (record["exclusion_reason"] or "").split(";") if r]
    if duration is None:
        reasons.append("media_duration_unverified")
        record["access_status"] = "media_probe_failed"
    else:
        boundaries = evidence["chapter_boundaries_sec"]
        out_of_range = [b for b in boundaries if not 0 < b < duration]
        last_end = evidence.get("last_end_sec") or 0.0
        evidence["boundaries_within_duration"] = not out_of_range
        evidence["last_clip_end_vs_duration_sec"] = round(duration - last_end, 3)
        record["access_status"] = "media_header_decoded"
        if out_of_range:
            reasons.append("boundary_outside_media_duration")
        if last_end > duration + 1.0:
            reasons.append("clip_end_after_media_end")
    record["exclusion_reason"] = ";".join(reasons) or None


# ---------------------------------------------------------------------------
# YTSeg (official splits, creator chapters)
# ---------------------------------------------------------------------------


_SUSPICIOUS_TITLE_RE = re.compile(r"(?i)(help us add time stamps|subscribe|sponsor)")


def probe_ytseg(prober: Prober) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    meta = prober.get(YTSEG_API)
    summary: dict[str, Any] = {"api_status": meta.status}
    try:
        payload = meta.json()
        summary.update({
            "revision": payload.get("sha"),
            "last_modified": payload.get("lastModified"),
            "gated": payload.get("gated"),
            "license_tags": [t for t in payload.get("tags", []) if t.startswith("license:")],
            "has_video_files": any(
                str(s.get("rfilename", "")).endswith((".mp4", ".mkv", ".webm"))
                for s in payload.get("siblings", [])
            ),
            "has_download_videos_script": any(
                s.get("rfilename") == "download_videos.py" for s in payload.get("siblings", [])
            ),
        })
    except Exception as exc:
        summary["error"] = f"metadata parse failed: {exc}"
    records: list[dict[str, Any]] = []
    split_totals: dict[str, int | None] = {}
    for split in YTSEG_SPLITS:
        for offset in YTSEG_SAMPLE_OFFSETS:
            url = YTSEG_ROWS.format(split=split, offset=offset, length=YTSEG_SAMPLE_LENGTH)
            page = prober.get(url)
            if page.status != 200:
                summary.setdefault("row_errors", []).append({"url": url, "error": page.error})
                continue
            rows = page.json()
            split_totals[split] = rows.get("num_rows_total")
            for row in rows.get("rows", []):
                item = row["row"]
                duration = float(item.get("duration") or 0.0)
                raw_ts = item.get("chapter_timestamps") or []
                if isinstance(raw_ts, str):
                    raw_ts = raw_ts.split()
                boundaries = [float(v) for v in raw_ts]
                ordered = all(a < b for a, b in zip(boundaries, boundaries[1:]))
                out_of_range = [b for b in boundaries if not 0 < b < duration]
                titles = str(item.get("chapter_titles") or "")
                reasons = ["video_rights_not_cleared_multimodal"]
                if not boundaries:
                    reasons.append("no_chapter_boundary")
                if not ordered:
                    reasons.append("unsorted_boundaries")
                if out_of_range:
                    reasons.append("boundary_outside_duration")
                if _SUSPICIOUS_TITLE_RE.search(titles):
                    reasons.append("suspicious_editorial_chapter_title")
                records.append(_ledger_record(
                    source_id="ytseg",
                    course_id=f"channel:{item.get('channel_id')}",
                    lecture_id=f"ytseg:{item.get('video_id')}",
                    boundary_origin="creator_youtube_chapters (editorial, not expert-annotated)",
                    video_url=f"https://www.youtube.com/watch?v={item.get('video_id')}",
                    gt_url=url,
                    rights_url="https://huggingface.co/datasets/retkowski/ytseg",
                    rights_status="dataset_cc_by_nc_sa_4.0_text_audio;video_copyright_not_owned_by_dataset",
                    access_status="text_available_video_not_distributed",
                    exclusion_reason=";".join(reasons),
                    evidence={
                        "official_split": split,
                        "sample_offset": offset,
                        "channel_id": item.get("channel_id"),
                        "duration_sec": duration,
                        "chapter_boundaries_sec": boundaries,
                        "boundary_count": len(boundaries),
                        "audio_path": item.get("audio_path"),
                        "speaker_category": item.get("speaker_category"),
                        "lecture_science_filter": "not_available_in_metadata",
                    },
                ))
    summary["split_totals"] = split_totals
    by_split: dict[str, set[str]] = {}
    for rec in records:
        by_split.setdefault(rec["evidence"]["official_split"], set()).add(rec["course_id"])
    if len(by_split) == 2:
        a, b = (by_split[s] for s in YTSEG_SPLITS)
        summary["sample_channel_overlap_validation_test"] = sorted(a & b)
    summary["sampled_units"] = len(records)
    return records, summary


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


def decide(ledger: Sequence[dict[str, Any]], context: dict[str, Any]) -> dict[str, Any]:
    ocw = [r for r in ledger if r["source_id"] == "mit_ocw_timed_toc"]
    ocw_ok = [r for r in ocw if not r["exclusion_reason"]
              and r["evidence"].get("media_probe", {}).get("duration_sec")]
    ocw_courses = sorted({r["course_id"] for r in ocw_ok})
    av = [r for r in ledger if r["source_id"] == "avlectures_cws"]
    decision = {
        "avlectures_archive": av[0]["access_status"] if av else "not_probed",
        "ocw_timed_toc": {
            "lectures_found": len(ocw),
            "lectures_without_exclusion": sum(1 for r in ocw if not r["exclusion_reason"]),
            "media_verified_lectures": len(ocw_ok),
            "independent_source_courses": ocw_courses,
            "status": (
                "diagnostic_pilot_candidate (baseline-only; single source course)"
                if ocw_ok and len(ocw_courses) < 3 else
                ("pilot_candidate" if ocw_ok else "blocked_gt")
            ),
        },
        "ytseg": {
            "multimodal_video": "blocked_rights",
            "text_audio": "candidate (creator chapters; official splits)",
        },
        "course_disjoint_learned_study": (
            "blocked_data" if len(ocw_courses) < 3 else "feasibility_unmeasured"
        ),
        "official_multimodal_rq1": "BLOCKED",
        "official_blockers": [
            "AVLectures archive requires authenticated access (blocked_access)",
            "only one timed-TOC source course verified; course-disjoint train/validation/"
            "final_test split impossible (blocked_data)",
            "OCW rights are page-level CC BY-NC-SA notices; human rights review still pending",
            "YTSeg video is not distributed and source-video rights are not cleared (blocked_rights)",
            "research decision required before any primary-dataset change (master plan names YTSeg)",
        ],
    }
    overlap = context.pop("ytseg_channel_overlap", None)
    if overlap:
        decision["ytseg"]["official_split_source_disjoint"] = False
        decision["official_blockers"].append(
            f"YTSeg official validation/test splits share {len(overlap)} channel(s) in the "
            "bounded sample; channel-disjoint learned-model claims need a re-split decision"
        )
    decision.update(context)
    return decision


def build_ledger(output_dir: Path, *, offline: bool = False,
                 courses: Iterable[str] = OCW_COURSES) -> dict[str, Any]:
    prober = Prober(output_dir=output_dir, offline=offline)
    started = _now()
    ledger: list[dict[str, Any]] = [probe_avlectures(prober)]
    course_summaries = []
    ocw_records: list[dict[str, Any]] = []
    for course in courses:
        records, summary = probe_ocw_course(prober, course)
        ocw_records.extend(records)
        course_summaries.append(summary)
    sample_ids = select_media_probe_sample(ocw_records, OCW_MEDIA_PROBE_SAMPLE)
    for record in ocw_records:
        if record["lecture_id"] in sample_ids:
            attach_media_probe(prober, record)
            record["evidence"]["media_probe_sample"] = True
    ledger.extend(ocw_records)
    ytseg_records, ytseg_summary = probe_ytseg(prober)
    ledger.extend(ytseg_records)
    decision = decide(ledger, {
        "ocw_media_probe_sample": sample_ids,
        "ytseg_channel_overlap": ytseg_summary.get("sample_channel_overlap_validation_test"),
    })
    bundle = {
        "schema_version": 1,
        "kind": "rq1_candidate_ledger",
        "diagnostic_only": True,
        "started_at": started,
        "completed_at": _now(),
        "selection_rules": {
            "ocw_courses": list(courses),
            "ocw_media_probe_sample": f"first {OCW_MEDIA_PROBE_SAMPLE} unexcluded lecture_ids by sha256",
            "ytseg_sample": {"splits": list(YTSEG_SPLITS), "offsets": list(YTSEG_SAMPLE_OFFSETS),
                             "length": YTSEG_SAMPLE_LENGTH},
        },
        "network": {"new_requests_this_invocation": prober.request_count,
                    "new_bytes_this_invocation": prober.network_bytes,
                    "offline_replay": offline,
                    "request_log": "probe_log.jsonl (cumulative across resumable runs)"},
        "ocw_course_summaries": course_summaries,
        "ytseg_summary": ytseg_summary,
        "decision": decision,
        "records": ledger,
    }
    (output_dir / "candidate_ledger.json").write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return bundle


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path,
                        default=Path("experiments/outputs/diagnostic/rq1_qualification"))
    parser.add_argument("--offline", action="store_true",
                        help="replay only cached responses; never touch the network")
    args = parser.parse_args(argv)
    bundle = build_ledger(args.output_dir, offline=args.offline)
    print(json.dumps(bundle["decision"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
