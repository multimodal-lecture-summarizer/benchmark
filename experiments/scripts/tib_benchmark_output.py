"""One source-independent delivery cap; never accept a reference argument."""
from __future__ import annotations

import hashlib
import math
import re

SPLITTER_ID = "punctuation_whitespace_newline_v1"
BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|[\r\n]+")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return original character spans with a fixed resource-free splitter."""
    if not isinstance(text, str):
        raise TypeError("Text must be a string")
    spans, start = [], 0
    for boundary in BOUNDARY.finditer(text):
        end = boundary.start()
        left = start + len(text[start:end]) - len(text[start:end].lstrip())
        right = end - (len(text[start:end]) - len(text[start:end].rstrip()))
        if right > left:
            spans.append((left, right))
        start = boundary.end()
    left = start + len(text[start:]) - len(text[start:].lstrip())
    right = len(text.rstrip())
    if right > left:
        spans.append((left, right))
    return spans


def select_delivered(raw_text: str, word_cap: int) -> dict:
    """Keep a sentence prefix; if none fits, flag a forced word-boundary cut.

    This fallback covers ASR run-on outputs without quietly discarding them.
    No punctuation or model-generated text is appended by the selector.
    """
    if type(word_cap) is not int or word_cap < 1:
        raise ValueError("word_cap must be a positive integer")
    spans = sentence_spans(raw_text)
    if not spans:
        raise ValueError("Empty generated output")
    words = list(re.finditer(r"\S+", raw_text))
    capped = len(words) > word_cap
    fallback = False
    start, end = spans[0][0], spans[-1][1]
    if capped:
        limit = words[word_cap - 1].end()
        eligible = [right for _, right in spans if right <= limit]
        if eligible:
            end = eligible[-1]
        else:
            end, fallback = limit, True
    delivered = raw_text[start:end].strip()
    if not delivered or len(delivered.split()) > word_cap:
        raise ValueError("Output selector violated its cap")
    return {
        "text": delivered, "raw_words": len(words),
        "delivered_words": len(delivered.split()), "word_cap": word_cap,
        "capped": capped, "forced_word_boundary": fallback,
        "raw_character_span": [start, end], "splitter_id": SPLITTER_ID,
        "raw_sha256": hashlib.sha256(raw_text.encode()).hexdigest(),
        "delivered_sha256": hashlib.sha256(delivered.encode()).hexdigest(),
    }


def derive_word_cap(train_reference_words, *, percentile=95, rounding=25):
    """Nearest-rank train percentile, rounded up; an operating choice, not power."""
    values = sorted(train_reference_words)
    if not values or any(type(v) is not int or v < 1 for v in values):
        raise ValueError("Eligible training references must be positive word counts")
    if not 0 < percentile <= 100 or type(rounding) is not int or rounding < 1:
        raise ValueError("Invalid percentile or rounding")
    observed = values[math.ceil(percentile / 100 * len(values)) - 1]
    return {"n": len(values), "nearest_rank_percentile": percentile,
            "percentile_words": observed, "rounding_words": rounding,
            "word_cap": math.ceil(observed / rounding) * rounding}
