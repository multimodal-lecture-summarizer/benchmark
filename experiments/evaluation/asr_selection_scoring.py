"""Versioned English ASR scoring and validation-only selection contracts.

No optional metric packages: sum edit counts within each unit before dividing.
CER includes normalized spaces. Apostrophes within words are ignored; uppercase
US and dotted U.S. are spelled as ``u s``, while the pronoun ``us`` stays ``us``.
No number verbalization, stemming, or semantic substitutions are performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

NORMALIZER_VERSION = "english-asr-nfkc-apostrophe-us-v1"
SCORER_VERSION = "per-unit-levenshtein-micro-v1"


def scoring_metadata() -> dict[str, str]:
    return {"normalizer": NORMALIZER_VERSION, "scorer": SCORER_VERSION,
            "cer_policy": "normalized_characters_including_spaces"}


def normalize_english_asr(text: str) -> str:
    """Normalize spelling format, retaining ordinary lexical errors."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\bUS\b|\b[Uu]\.[Ss]\.?(?!\w)", "u s", text)
    text = text.replace("’", "'").replace("‘", "'").replace("ʼ", "'")
    text = re.sub(r"(?<=\w)\s*'\s*(?=\w)", "", text)
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.casefold().split())


def _distance(reference: Sequence, hypothesis: Sequence) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def score_asr_pairs(pairs: Iterable[tuple[str, str]]) -> dict[str, int | float]:
    """Score raw reference/hypothesis pairs; suitable for diagnostic re-scoring.

    Empty normalized references fail closed. Empty hypotheses count deletions.
    A unit boundary never permits edit alignment to a neighboring unit.
    """
    word_errors = character_errors = words = characters = unit_count = 0
    for reference, hypothesis in pairs:
        ref, hyp = normalize_english_asr(reference), normalize_english_asr(hypothesis)
        if not ref:
            raise ValueError("ASR reference is empty after normalization")
        ref_words, hyp_words = ref.split(), hyp.split()
        word_errors += _distance(ref_words, hyp_words)
        character_errors += _distance(ref, hyp)
        words += len(ref_words)
        characters += len(ref)
        unit_count += 1
    if not unit_count:
        raise ValueError("ASR scoring requires at least one unit")
    return {"wer": word_errors / words, "cer": character_errors / characters,
            "word_errors": word_errors, "reference_words": words,
            "character_errors": character_errors, "reference_characters": characters,
            "unit_count": unit_count}


def validation_units(units: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject ambiguous split membership before any inference or media access."""
    seen: set[tuple[str, str]] = set()
    selected = []
    for unit in units:
        split = unit.get("split")
        if not isinstance(split, str) or split not in {"train", "validation", "final_test"}:
            raise RuntimeError(f"ASR unit {unit.get('unit_id')!r} has missing/unknown split")
        if not isinstance(unit.get("unit_id"), str) or not unit["unit_id"].strip():
            raise RuntimeError("ASR unit has missing unit_id")
        identity = (str(unit.get("dataset_id") or ""), unit["unit_id"])
        if identity in seen:
            raise RuntimeError(f"ASR unit has duplicate identity: {identity}")
        seen.add(identity)
        if split == "validation":
            if not normalize_english_asr(str(unit.get("reference_text") or "")):
                raise RuntimeError(f"ASR validation unit {unit['unit_id']!r} missing reference_text")
            selected.append(unit)
    if not selected:
        raise RuntimeError("ASR selection requires validation units")
    return selected


def selection_metadata(units: Sequence[dict[str, Any]]) -> dict[str, Any]:
    selected = validation_units(units)
    if len(selected) != len(units):
        raise RuntimeError("ASR selection metadata must describe validation only")
    identities = sorted((str(u.get("dataset_id") or ""), u["unit_id"]) for u in units)
    fingerprint = hashlib.sha256(json.dumps(identities, separators=(",", ":"),
                                            ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"selection_split": "validation", "selection_unit_count": len(units),
            "selection_unit_ids_sha256": fingerprint, "scoring": scoring_metadata()}


def require_selection_metadata(record: Mapping[str, Any], units: Sequence[dict[str, Any]]) -> None:
    """Historical/mismatched shortlist rows cannot select an ablation model."""
    for key, expected in selection_metadata(units).items():
        if record.get(key) != expected:
            raise RuntimeError(f"ASR shortlist missing/incompatible {key}; regenerate on validation")
