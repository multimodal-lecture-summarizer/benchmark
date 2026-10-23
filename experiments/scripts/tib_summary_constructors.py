"""Train-source sampling and mechanical test summaries for checking published metrics.

Nothing here scores a summary. The constructors only build inputs whose
expected ordering is known (source extracts versus off-topic text), so a
published metric can be checked before it is trusted.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
from pathlib import Path

from experiments.scripts.tib_benchmark_output import select_delivered, sentence_spans

SAMPLE_SALT = "p4e-validity-v1:"
TERTILE_CUTPOINTS = (3635, 6131)  # train source-word tertiles


def load_train_sources(path: str | Path, min_words: int = 1000) -> list[dict]:
    """Train records that pass the structure check. Only source text is kept."""
    records = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["split"] == "train" and row["structure_pass"] and row["source_words"] >= min_words:
                records.append({"id": row["record_id"], "words": row["source_words"],
                                "text": row["source_normalized"]})
    return records


def draw_sample(records: list[dict], per_tertile: int, salt: str = SAMPLE_SALT) -> list[dict]:
    """Deterministic hash-ordered sample per source-length tertile."""
    low, high = TERTILE_CUTPOINTS
    groups: dict[str, list[dict]] = {"short": [], "medium": [], "long": []}
    for rec in records:
        name = "short" if rec["words"] < low else "medium" if rec["words"] < high else "long"
        groups[name].append(rec)
    order = lambda rec: hashlib.sha256((salt + rec["id"]).encode()).hexdigest()
    sample = []
    for name, group in groups.items():
        sample += [{**rec, "tertile": name} for rec in sorted(group, key=order)[:per_tertile]]
    return sample


def split_sentences(text: str) -> list[str]:
    return [text[a:b] for a, b in sentence_spans(text)]


def _words(sentence: str) -> int:
    return len(sentence.split())


def lead(source: str, budget: int) -> str:
    return select_delivered(source, budget)["text"]


def uniform(sentences: list[str], budget: int) -> str:
    total = sum(map(_words, sentences)) or 1
    take = min(max(1, int(budget / (total / len(sentences)))), len(sentences))
    step = len(sentences) / take
    picked = sorted({min(int(i * step), len(sentences) - 1) for i in range(take)})
    while len(picked) > 1 and sum(_words(sentences[i]) for i in picked) > budget:
        picked.pop()
    return " ".join(sentences[i] for i in picked)


def random_pick(sentences: list[str], budget: int, rng: random.Random) -> str:
    order = list(range(len(sentences)))
    rng.shuffle(order)
    picked, used = [], 0
    for i in order:
        if used + _words(sentences[i]) <= budget:
            picked.append(i)
            used += _words(sentences[i])
    return " ".join(sentences[i] for i in sorted(picked))


def foreign_sentences(partner_sentences: list[str], count: int) -> str:
    """The first sentences of another record that contain a digit or a capital mid-sentence."""
    def has_item(sentence: str) -> bool:
        words = sentence.split()
        return any(ch.isdigit() for ch in sentence) or any(w[:1].isupper() for w in words[1:])
    return " ".join([s for s in partner_sentences if has_item(s)][:count])
