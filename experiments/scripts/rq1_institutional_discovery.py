"""Bounded metadata discovery from the original VidChapters pickle opcodes.

Never unpickles or executes the release. Searches only predeclared institutional
description terms; output is discovery metadata, not qualification or D2 GT.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import mmap
import pickletools
import re
from pathlib import Path


TERMS = {
    "mit_ocw": b"ocw.mit.edu/",
    "open_yale": b"oyc.yale.edu",
    "stanford": b"see.stanford.edu",
    "harvard_cs50": b"cs50.harvard.edu",
}
ID_OPCODE = b"X\x0b\x00\x00\x00"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
COURSE_CODE = re.compile(r"\(([A-Z]{2,5}\s?\d{2,3}[A-Z]?)\)")


def _candidate_offsets(source: Path) -> dict[int, set[str]]:
    offsets: dict[int, set[str]] = {}
    with source.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for bucket, term in TERMS.items():
            pos = 0
            while (pos := data.find(term, pos)) >= 0:
                start = data.rfind(ID_OPCODE, max(0, pos - 8192), pos)
                if start >= 0:
                    video_id = data[start + len(ID_OPCODE):start + len(ID_OPCODE) + 11].decode("ascii", "replace")
                    if VIDEO_ID.fullmatch(video_id):
                        offsets.setdefault(start, set()).add(bucket)
                pos += len(term)
    return offsets


def _metadata_at(source: Path, offset: int) -> dict[str, str | int | float]:
    with source.open("rb") as stream:
        stream.seek(offset)
        strings: list[str] = []
        duration: float | None = None
        duration_after_chapters: float | None = None
        chapter_count = 0
        in_chapters = False
        just_closed_chapters = False
        for opcode, value, position in pickletools.genops(stream):
            if position - offset > 65536:
                raise ValueError(f"record at {offset} exceeds bounded metadata window")
            if position > offset and opcode.name == "BINUNICODE" and isinstance(value, str) and VIDEO_ID.fullmatch(value):
                break
            if opcode.name == "BINUNICODE" and isinstance(value, str):
                strings.append(value)
            if duration is None and opcode.name == "BINFLOAT":
                duration = float(value)
            if just_closed_chapters and opcode.name in {"BININT", "BININT1", "BININT2", "BINFLOAT"}:
                duration_after_chapters = float(value)
                just_closed_chapters = False
            if opcode.name == "EMPTY_LIST" and not in_chapters:
                in_chapters = True
            elif opcode.name == "APPENDS" and in_chapters:
                in_chapters = False
                just_closed_chapters = True
            elif opcode.name == "EMPTY_DICT" and in_chapters:
                chapter_count += 1
        duration = duration if duration is not None else duration_after_chapters
        if not strings or not VIDEO_ID.fullmatch(strings[0]) or len(strings) < 3 or duration is None:
            raise ValueError(f"record at {offset} lacks expected original fields")
        description_index = max(range(1, len(strings)), key=lambda index: len(strings[index]))
        description = strings[description_index]
        title = strings[description_index - 1] if description_index > 1 else ""
        code = COURSE_CODE.search(description)
        first_line = description.splitlines()[0].strip()
        return {
            "video_id": strings[0], "annotation_byte_offset": offset,
            "title": title, "description_first_line": first_line,
            "course_code_hint": code.group(1).replace(" ", "") if code else "",
            "duration_seconds": duration, "chapter_count": chapter_count,
        }


def discover(source: Path, output: Path) -> dict[str, int | str]:
    offsets = _candidate_offsets(source)
    rows = []
    for offset in sorted(offsets):
        record = _metadata_at(source, offset)
        if record["chapter_count"] < 2:
            continue
        rows.append({"bucket_hints": ";".join(sorted(offsets[offset])), **record})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["bucket_hints", "video_id", "annotation_byte_offset", "title", "description_first_line", "course_code_hint", "duration_seconds", "chapter_count"])
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {"metadata_rows": len(rows), "output_sha256": digest,
            "mit_ocw": sum("mit_ocw" in row["bucket_hints"] for row in rows),
            "open_yale": sum("open_yale" in row["bucket_hints"] for row in rows),
            "stanford": sum("stanford" in row["bucket_hints"] for row in rows),
            "harvard_cs50": sum("harvard_cs50" in row["bucket_hints"] for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(discover(args.source, args.output))


if __name__ == "__main__":
    main()
