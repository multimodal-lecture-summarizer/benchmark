"""Retry only transient decode failures from the immutable first landmark pass."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from experiments.scripts import audit_mitfld_ocw_landmarks as audit


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "plans/reports/mitfld-rq1-35-260928-1214-three-landmark-ledger.csv"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1245-three-landmark-verified.csv"
FIELDS = audit.FIELDS + ("original_status", "retry_attempts")


def main() -> None:
    source_bytes = audit.SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != audit.SOURCE_SHA256:
        raise ValueError("source ledger changed")
    source = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8"))))
    by_id = {row["video_id"]: row for row in source}
    original_bytes = ORIGINAL.read_bytes()
    original = list(csv.DictReader(io.StringIO(original_bytes.decode("utf-8"))))
    if len(source) != 35 or len(original) != 105:
        raise ValueError("expected 35 sources and 105 landmark rows")
    if {(row["video_id"], row["mark_role"]) for row in original} != {
        (video_id, role) for video_id in by_id for role in ("first", "middle", "last")
    }:
        raise ValueError("original landmark keys do not match selected cohort")

    verified: list[dict[str, str]] = []
    for row in original:
        current = dict(row)
        current["original_status"] = row["status"]
        current["retry_attempts"] = "0"
        if row["status"] == "decode_or_compare_failed":
            for attempt in (1, 2):
                retry = audit.check_one(
                    by_id[row["video_id"]],
                    [(row["mark_role"], float(row["frag_s"]))],
                )[0]
                current.update({key: str(value) for key, value in retry.items()})
                current["retry_attempts"] = str(attempt)
                print(f"retry {row['video_id']} {row['mark_role']} {attempt}: {current['status']}", flush=True)
                if current["status"] != "decode_or_compare_failed":
                    break
        verified.append(current)

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(verified)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError(f"verified artifact already differs: {OUTPUT}")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    print(f"original_sha256={hashlib.sha256(original_bytes).hexdigest()}")
    for status in sorted({row["status"] for row in verified}):
        print(f"{status}={sum(row['status'] == status for row in verified)}")
    print(f"output_sha256={hashlib.sha256(content).hexdigest()}")


if __name__ == "__main__":
    main()
