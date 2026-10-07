"""Probe OCW-published MP4 durations for the pinned 35-video RQ1 cohort."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "plans/reports/mitfld-rq1-35-260928-1135-ocw-source-rights-ledger.csv"
SOURCE_SHA256 = "36419f9a3209405647a854032ce7b7acd654dad7fc4086d68aedcb7b44019d10"
HF_PROBE = ROOT / "plans/reports/mitfld-rq1-35-260928-1135-hf-media-probe.csv"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1214-ocw-duration-ledger.csv"
FIELDS = (
    "video_id", "course_id", "ocw_mp4_url", "hf_duration_sec", "ocw_duration_sec",
    "ocw_minus_hf_sec", "frags_last_sec", "ocw_margin_sec", "probe_status", "error",
)


def probe(row: dict[str, str], hf: dict[str, str]) -> dict[str, object]:
    result: dict[str, object] = {
        "video_id": row["video_id"], "course_id": row["course_id"],
        "ocw_mp4_url": row["ocw_mp4_url"],
        "hf_duration_sec": hf["hf_duration_sec"], "frags_last_sec": hf["frags_last_sec"],
    }
    env = os.environ.copy()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(name, None)
    try:
        done = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", row["ocw_mp4_url"]],
            capture_output=True, text=True, timeout=45, env=env, check=True,
        )
        duration = float(done.stdout.strip())
        margin = duration - float(hf["frags_last_sec"])
        result.update({
            "ocw_duration_sec": f"{duration:.6f}",
            "ocw_minus_hf_sec": f"{duration - float(hf['hf_duration_sec']):.6f}",
            "ocw_margin_sec": f"{margin:.6f}",
            "probe_status": "probe_ok_boundary_in_range" if margin > 0 else "review_boundary_out_of_range",
        })
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["probe_status"] = "probe_failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("source rights ledger hash changed")
    source = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8"))))
    hf_rows = list(csv.DictReader(HF_PROBE.open(encoding="utf-8", newline="")))
    hf_by_id = {row["video_id"]: row for row in hf_rows}
    if len(source) != 35 or len(hf_by_id) != 35 or set(hf_by_id) != {row["video_id"] for row in source}:
        raise ValueError("source and HF duration ledgers must match the 35-video cohort")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda row: probe(row, hf_by_id[row["video_id"]]), source))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(results)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError(f"locked audit artifact differs: {OUTPUT}")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    counts = {status: sum(row["probe_status"] == status for row in results)
              for status in ("probe_ok_boundary_in_range", "review_boundary_out_of_range", "probe_failed")}
    print(f"rows={len(results)} status={counts} output={OUTPUT}")


if __name__ == "__main__":
    main()
