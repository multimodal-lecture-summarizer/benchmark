"""Batched token counting must preserve the legacy first-overflow split."""

import hashlib

import pytest

from experiments.scripts.rq2_controlled_validation import _fixed_chunks


class ScalarCounter:
    def __init__(self, counter):
        self.counter = counter
        self.calls = 0

    def count_tokens(self, text):
        self.calls += 1
        return self.counter(text)


class BatchCounter(ScalarCounter):
    def __init__(self, counter):
        super().__init__(counter)
        self.batches = []

    def count_tokens_batch(self, texts):
        self.batches.append(texts)
        return [self.counter(text) for text in texts]


def legacy_chunks(text, backend, limit):
    chunks, current = [], []
    for word in text.split():
        candidate = " ".join((*current, word))
        if backend.count_tokens(candidate) > limit:
            if not current or backend.count_tokens(word) > limit:
                raise ValueError("A source word exceeds the per-call token cap")
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def irregular_count(text):
    # Some appended words reduce the count; larger prefixes can fit again
    # after the first overflow. Only the first overflow defines a boundary.
    jitter = hashlib.sha256(text.encode()).digest()[0] % 7 - 3
    return max(1, len(text.split()) + jitter)


@pytest.mark.parametrize("counter", [lambda text: len(text.split()), irregular_count])
@pytest.mark.parametrize("limit", [4, 7, 31, 32, 33, 128])
@pytest.mark.parametrize("text", ["", "   ", "bài\tgiảng\nnaïve 中文",
                                    " ".join(f"word{i}" for i in range(257))])
def test_batch_matches_original_greedy_boundaries(text, limit, counter):
    batched = BatchCounter(counter)
    expected = legacy_chunks(text, ScalarCounter(counter), limit)
    assert _fixed_chunks(text, batched, limit) == expected
    assert all(len(batch) <= 32 for batch in batched.batches)
    assert " ".join(expected) == " ".join(text.split())


@pytest.mark.parametrize("text", ["oversized", "one two oversized four"])
@pytest.mark.parametrize("backend_class", [ScalarCounter, BatchCounter])
def test_oversized_word_raises_in_both_paths(text, backend_class):
    def count(value):
        return 99 if "oversized" in value.split() else len(value.split())
    with pytest.raises(ValueError, match="source word exceeds"):
        _fixed_chunks(text, backend_class(count), 3)


def test_batch_reduces_python_tokenizer_calls_without_changing_chunks():
    text = " ".join(f"w{i}" for i in range(500))
    scalar = ScalarCounter(lambda value: len(value.split()))
    batch = BatchCounter(scalar.counter)
    assert _fixed_chunks(text, batch, 128) == _fixed_chunks(text, scalar, 128)
    assert batch.calls + len(batch.batches) < scalar.calls / 10


def test_nonmonotonic_counter_stops_at_first_overflow():
    counts = {"a": 1, "a b": 3, "a b c": 2, "b": 1, "b c": 2}
    assert _fixed_chunks("a b c", BatchCounter(counts.__getitem__), 2) == ["a", "b c"]


def test_mismatched_batch_count_is_rejected():
    backend = BatchCounter(lambda value: 1)
    backend.count_tokens_batch = lambda texts: []
    with pytest.raises(ValueError, match="do not match"):
        _fixed_chunks("one two", backend, 8)
