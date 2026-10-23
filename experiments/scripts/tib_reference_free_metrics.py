"""Reference-free summary metrics against a source transcript.

Coverage and temporal coverage use a salient-fact inventory; the unsupported
rate checks summary numbers and capitalized names against the source. None of
them reads a reference, and none is a factual-correctness measure.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.scripts.tib_benchmark_output import sentence_spans
from experiments.scripts.tib_fact_inventory import (
    POSITION_BINS, Inventory, key_set, stem, tokenize,
)


def coverage(inventory: Inventory, summary_text: str) -> float | None:
    """Salience-weighted share of inventory facts present in the summary."""
    total = inventory.total_weight
    if not inventory.facts or total <= 0:
        return None
    present = key_set(summary_text)
    return sum(weight for key, weight, _ in inventory.facts if key in present) / total


def temporal_coverage(inventory: Inventory, summary_text: str) -> float | None:
    """Share of source position bins touched by at least one covered fact."""
    populated = set().union(*(bins for _, _, bins in inventory.facts)) if inventory.facts else set()
    if not populated:
        return None
    present = key_set(summary_text)
    touched = set()
    for key, _, bins in inventory.facts:
        if key in present:
            touched |= bins
    return len(touched & populated) / len(populated)


def auc(c_s: float, c_m: float, c_l: float) -> float:
    """Trapezoid area over equally spaced log2 budgets, normalized to [0, 1]."""
    return (c_s + 2 * c_m + c_l) / 4


@dataclass(frozen=True)
class SourceIndex:
    """Lookup of what the source says, for the unsupported-content check."""
    words: frozenset
    numbers: frozenset


def index_source(source_text: str) -> SourceIndex:
    words, numbers = set(), set()
    for tok in tokenize(source_text):
        if tok.kind == "num":
            numbers.add(tok.norm)
        elif tok.kind == "word":
            words.add(tok.norm)
    return SourceIndex(frozenset(words), frozenset(numbers))


def _names_and_numbers(summary_text: str):
    """Numbers and capitalized mid-sentence or all-caps words of a summary."""
    first_starts = {start for start, _ in sentence_spans(summary_text)}
    for tok in tokenize(summary_text):
        if tok.kind == "num":
            yield "n", tok.norm
        elif tok.kind == "word":
            raw = tok.raw
            acronym = len(raw) >= 2 and raw.isupper()
            capitalized = raw[0].isupper() and tok.start not in first_starts
            if acronym or capitalized:
                yield "w", tok.norm


def unsupported_rate(source: SourceIndex, summary_text: str) -> float | None:
    """Share of summary numbers and names that never occur in the source."""
    items = list(_names_and_numbers(summary_text))
    if not items:
        return None
    missing = sum(1 for kind, norm in items
                  if norm not in (source.numbers if kind == "n" else source.words))
    return missing / len(items)


def score_view(inventory: Inventory, source: SourceIndex, summary_text: str) -> dict:
    return {
        "coverage": coverage(inventory, summary_text),
        "temporal_coverage": temporal_coverage(inventory, summary_text),
        "unsupported_rate": unsupported_rate(source, summary_text),
        "words": len(summary_text.split()),
    }


def score_views(inventory: Inventory, source: SourceIndex, views: dict[str, str]) -> dict:
    """Score S/M/L view texts; the AUC needs all three coverages."""
    scores = {name: score_view(inventory, source, text) for name, text in views.items()}
    triple = [scores.get(name, {}).get("coverage") for name in ("S", "M", "L")]
    scores["auc"] = None if any(v is None for v in triple) else auc(*triple)
    scores["monotone"] = None if any(v is None for v in triple) else (
        triple[0] <= triple[1] <= triple[2])
    return scores
