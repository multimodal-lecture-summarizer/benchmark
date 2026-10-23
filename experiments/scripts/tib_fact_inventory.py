"""Deterministic salient-fact inventory from a source transcript.

Facts are numbers and one- or two-stem content phrases. Salience comes from
the source and from train document frequencies only; no reference text, model
output or candidate selection algorithm is used.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

POSITION_BINS = 10
TOP_K = 100
DF_CEILING_A = 0.20
MIN_FREQUENCY = 2
MIN_WORD_LENGTH = 3

TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[A-Za-z][A-Za-z0-9-]*")
_STEMMER = PorterStemmer()


@lru_cache(maxsize=200_000)
def stem(word: str) -> str:
    return _STEMMER.stem(word)


@dataclass(frozen=True)
class Token:
    kind: str  # "num", "word" or "stop"
    norm: str  # normalized number, stem, or lowercase stop word
    start: int
    raw: str


def tokenize(text: str) -> list[Token]:
    tokens = []
    for match in TOKEN.finditer(text):
        raw = match.group()
        if raw[0].isdigit():
            norm = raw.replace(",", "")
            tokens.append(Token("num", norm, match.start(), raw))
            continue
        lower = raw.lower()
        if len(lower) < MIN_WORD_LENGTH or lower in ENGLISH_STOP_WORDS:
            tokens.append(Token("stop", lower, match.start(), raw))
        else:
            tokens.append(Token("word", stem(lower), match.start(), raw))
    return tokens


def fact_keys(tokens: list[Token]):
    """Yield (key, token_start) for numbers and for 1- and 2-stem windows
    inside maximal runs of content words."""
    run: list[Token] = []

    def flush():
        for i, tok in enumerate(run):
            yield ("u", tok.norm), tok.start
            if i + 1 < len(run):
                yield ("b", tok.norm, run[i + 1].norm), tok.start

    for tok in tokens:
        if tok.kind == "word":
            run.append(tok)
            continue
        yield from flush()
        run = []
        if tok.kind == "num":
            yield ("n", tok.norm), tok.start
    yield from flush()


def key_set(text: str) -> set:
    """All fact keys present in a text (used for summaries)."""
    return {key for key, _ in fact_keys(tokenize(text))}


@dataclass(frozen=True)
class DocumentFrequency:
    n_documents: int
    counts: dict

    def ratio(self, key) -> float:
        return self.counts.get(key, 0) / self.n_documents if self.n_documents else 0.0


def build_document_frequency(texts) -> DocumentFrequency:
    counts: Counter = Counter()
    n = 0
    for text in texts:
        counts.update(key_set(text))
        n += 1
    return DocumentFrequency(n, dict(counts))


@dataclass(frozen=True)
class Inventory:
    definition: str
    facts: tuple  # (key, weight, frozenset(bins)) ordered by weight desc

    @property
    def total_weight(self) -> float:
        return sum(weight for _, weight, _ in self.facts)

    def __len__(self) -> int:
        return len(self.facts)


def build_inventory(text: str, definition: str, df: DocumentFrequency,
                    top_k: int = TOP_K, bins: int = POSITION_BINS) -> Inventory:
    """Rank source facts by salience definition "A" or "B".

    A: ln(1+frequency) * occupied_bins / bins, for facts that recur, spread
       over at least two bins and are not generic across the train sources.
    B: frequency * inverse train document frequency, for facts that recur.
    """
    if definition not in ("A", "B"):
        raise ValueError("definition must be 'A' or 'B'")
    if not text.strip():
        return Inventory(definition, ())
    length = max(len(text), 1)
    occurrences: dict = {}
    for key, start in fact_keys(tokenize(text)):
        occurrences.setdefault(key, []).append(min(int(start / length * bins), bins - 1))
    scored = []
    for key, positions in occurrences.items():
        frequency = len(positions)
        if frequency < MIN_FREQUENCY:
            continue
        occupied = frozenset(positions)
        if definition == "A":
            if len(occupied) < 2 or df.ratio(key) > DF_CEILING_A:
                continue
            weight = math.log1p(frequency) * len(occupied) / bins
        else:
            idf = math.log((1 + df.n_documents) / (1 + df.counts.get(key, 0))) + 1
            weight = frequency * idf
        scored.append((key, weight, occupied))
    scored.sort(key=lambda item: (-item[1], repr(item[0])))
    return Inventory(definition, tuple(scored[:top_k]))
