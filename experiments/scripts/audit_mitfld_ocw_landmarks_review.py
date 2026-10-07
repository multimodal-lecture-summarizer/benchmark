"""Inspect neighboring A/V windows for initially low-correlation landmark samples."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from experiments.scripts import audit_mitfld_ocw_landmarks as audit


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "plans/reports/mitfld-rq1-35-260928-1214-three-landmark-ledger.csv"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1250-low-correlation-neighbors.csv"
FIELDS = ("original_video_id", "original_mark_role", "original_frag_s", "offset_s") + audit.FIELDS


def main() -> None:
    source_bytes = audit.SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != audit.SOURCE_SHA256:
        raise ValueError("source ledger changed")
    source = {row["video_id"]: row for row in csv.DictReader(io.StringIO(source_bytes.decode("utf-8")))}
    original = list(csv.DictReader(ORIGINAL.open(encoding="utf-8", newline="")))
    review = [row for row in original if row["status"] == "review_low_correlation"]
    if len(source) != 35 or len(original) != 105 or len(review) != 3:
        raise ValueError("unexpected cohort or review sample count")
    results: list[dict[str, object]] = []
    for row in review:
        for offset in (-5.0, 5.0):
            second = float(row["frag_s"]) + offset
            if second <= 0:
                raise ValueError("neighbor time must be positive")
            result = audit.check_one(source[row["video_id"]], [(row["mark_role"], second)])[0]
            result = {
                "original_video_id": row["video_id"],
                "original_mark_role": row["mark_role"],
                "original_frag_s": row["frag_s"],
                "offset_s": offset,
                **result,
            }
            print(f"neighbor {row['video_id']} {row['mark_role']} {offset:+.0f}: {result['status']}", flush=True)
            results.append(result)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(results)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError(f"neighbor artifact already differs: {OUTPUT}")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    print(f"rows={len(results)} sha256={hashlib.sha256(content).hexdigest()}")


if __name__ == "__main__":
    main()
