"""Minimal reversible text normalization for the new TIB study only."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pyarrow.parquet as pq

REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_with_offsets(raw: str) -> tuple[str, list[list], dict]:
    """NFC/whitespace only; normalized character intervals map to raw intervals.

    Identity runs merge; changed NFC/whitespace runs preserve their whole raw
    interval rather than pretend character-for-character equivalence.
    """
    if not isinstance(raw, str):
        raise ValueError("Canonical text must be a string")
    pieces, spans, position, previous_end = [], [], 0, None

    def append(piece, begin, end):
        nonlocal position
        kind = "identity" if raw[begin:end] == piece else "technical_change"
        if (spans and kind == spans[-1][4] == "identity"
                and spans[-1][1] == position and spans[-1][3] == begin):
            spans[-1][1], spans[-1][3] = position + len(piece), end
        else:
            spans.append([position, position + len(piece), begin, end, kind])
        pieces.append(piece)
        position += len(piece)

    first = None
    for match in re.finditer(r"\S+", raw):
        if first is None:
            first = match.start()
        if previous_end is not None:
            append(" ", previous_end, match.start())
        append(unicodedata.normalize("NFC", match.group()), match.start(), match.end())
        previous_end = match.end()
    removed = {"leading_raw_span": [0, first or 0],
               "trailing_raw_span": [previous_end or 0, len(raw)]}
    return "".join(pieces), spans, removed


def iter_released(snapshot: Path):
    if snapshot.name != REVISION:
        raise ValueError("Only the declared pinned TIB snapshot is accepted")
    expected = {"train": 7282, "valid": 910, "test": 911}
    for split, count in expected.items():
        ordinal = 0
        for path in sorted((snapshot / "data").glob(f"{split}-*.parquet")):
            for batch in pq.ParquetFile(path).iter_batches(batch_size=32):
                for raw in batch.to_pylist():
                    yield split, ordinal, path.name, raw
                    ordinal += 1
        if ordinal != count:
            raise ValueError(f"Wrong pinned split count: {split}={ordinal}")


def canonical_record(split: str, index: int, filename: str, raw: dict) -> dict:
    source_raw, reference_raw = raw.get("transcript"), raw.get("abstract")
    flags = []
    if source_raw is None:
        source_raw = ""
        flags.append("null_transcript")
    if reference_raw is None:
        reference_raw = ""
        flags.append("null_reference")
    source, source_offsets, source_trim = normalize_with_offsets(source_raw)
    reference, reference_offsets, reference_trim = normalize_with_offsets(reference_raw)
    if not source:
        flags.append("empty_transcript")
    if not reference:
        flags.append("empty_reference")
    if "\ufffd" in source_raw or "\ufffd" in reference_raw:
        flags.append("replacement_character_no_automatic_repair")
    segments = raw.get("transcript_segments")
    segments = segments if isinstance(segments, dict) else {}
    arrays = [segments.get(key, []) for key in ("text", "start", "end")]
    if any(not isinstance(value, (list, tuple)) for value in arrays):
        flags.append("invalid_segment_sidecar_shape")
    texts, starts, ends = (value if isinstance(value, (list, tuple)) else [] for value in arrays)
    if not (len(texts) == len(starts) == len(ends)):
        flags.append("segment_array_length_mismatch")
    elif any(not isinstance(value, str) or not value.strip() for value in texts):
        flags.append("empty_segment_text")
    if not texts:
        flags.append("missing_segment_sidecar")
    try:
        import math
        valid_times = (len(starts) == len(ends) and all(
            type(a) in (float, int) and type(b) in (float, int)
            and math.isfinite(a) and math.isfinite(b) and 0 <= a <= b
            for a, b in zip(starts, ends)))
        if not valid_times:
            flags.append("invalid_segment_time")
        elif any(starts[i] < starts[i - 1] for i in range(1, len(starts))):
            flags.append("unordered_segment_time")
        if valid_times and any(starts[i] < ends[i - 1] for i in range(1, len(starts))):
            flags.append("overlapping_segment_time")
    except (TypeError, ValueError):
        flags.append("invalid_segment_time")
    joined = " ".join(value for value in texts if isinstance(value, str))
    normalized_segments = " ".join(unicodedata.normalize("NFC", joined).split())
    if source != normalized_segments:
        flags.append("transcript_segment_mismatch")
    return {
        "record_id": f"{split}:{index}", "split": split, "source_index": index,
        "source_file": filename, "revision": REVISION,
        "doi": raw.get("doi"), "source_url": raw.get("url"),
        "title": raw.get("title"), "author": raw.get("author"),
        "genre": raw.get("genre"), "subject": raw.get("subject"), "language": raw.get("language"),
        "source_raw": source_raw, "source_normalized": source,
        "reference_raw": reference_raw, "reference_normalized": reference,
        "source_raw_sha256": text_hash(source_raw), "source_normalized_sha256": text_hash(source),
        "reference_raw_sha256": text_hash(reference_raw), "reference_normalized_sha256": text_hash(reference),
        "source_offset_runs": source_offsets, "reference_offset_runs": reference_offsets,
        "source_trim": source_trim, "reference_trim": reference_trim,
        "source_words": len(source.split()), "reference_words": len(reference.split()),
        "segment_count": len(texts), "quality_flags": sorted(set(flags)),
        "structure_pass": bool(source), "primary_prompt_timestamps": False,
    }
