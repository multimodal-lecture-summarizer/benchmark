"""Source-group boundaries independent of corpus outcomes."""
from experiments.scripts.tib_model_benchmark_group_core import (
    canonical, component_ledger, confirm_pair, fingerprints, intersection_count, near_pass, stats,
)
import numpy as np
import pytest
from experiments.scripts import tib_model_benchmark_groups as runner

POLICY = {"minimum_shared_fivegrams": 100, "jaccard_threshold": .30,
          "containment_threshold": .80}


def test_load_rows_runtime_wiring_reaches_accounting_check(monkeypatch):
    class FakeData:
        def glob(self, pattern):
            return ["fixture.parquet"] if pattern.startswith("train") else []

    class FakeBatch:
        def to_pylist(self):
            return [{"transcript": "cafe\u0301  presentation", "doi": "", "url": "",
                     "video_url": "", "author": "", "title": ""}]

    class FakeParquet:
        def __init__(self, path):
            pass

        def iter_batches(self, **kwargs):
            return iter([FakeBatch()])

    monkeypatch.setattr(runner, "DATA", FakeData())
    monkeypatch.setattr(runner.pq, "ParquetFile", FakeParquet)
    # A tiny real-shaped record must pass canonical/hash/fingerprint wiring first.
    with pytest.raises(ValueError, match="Unexpected source accounting"):
        runner.load_rows()


def test_compiled_sorted_merge_matches_exact_numpy_intersection():
    rng = np.random.default_rng(2718)
    for a, b in ((0, 100), (100, 0), (3000, 15000), (40000, 1000)):
        left = np.unique(rng.integers(0, 100000, a, dtype=np.uint64))
        right = np.unique(rng.integers(0, 100000, b, dtype=np.uint64))
        assert intersection_count(left, right) == len(np.intersect1d(left, right))


def row(identity, text, **metadata):
    return {"record_id": identity, "source_normalized": canonical(text),
            "doi": "", "source_url": "", "video_url": "", **metadata}


def confirm(left, right):
    return confirm_pair(left, right, fingerprints(left["source_normalized"]),
                        fingerprints(right["source_normalized"]), POLICY)


def text(prefix, count):
    return " ".join(f"{prefix}{i}" for i in range(count))


def test_canonical_exact_with_unicode_whitespace():
    left = row("train:1", "cafe\u0301\n  presentation")
    right = row("test:1", "café presentation")
    assert confirm(left, right)["reasons"] == ["exact_normalized_transcript"]


def test_near_overlap_confirmed_beyond_shared_author():
    common = text("common", 200)
    result = confirm(row("a", common + " " + text("a", 100)),
                     row("b", common + " " + text("b", 100)))
    assert result["shared_fivegrams"] == 196
    assert result["reasons"] == ["confirmed_near_transcript"]


def test_same_author_title_never_automatically_groups():
    assert not confirm(row("a", text("a", 300), author_flag_key="same", title_flag_key="same"),
                       row("b", text("b", 300), author_flag_key="same", title_flag_key="same"))["accepted"]


def test_threshold_and_minimum_shared_are_inclusive():
    assert near_pass(stats(300, 500, 800), POLICY)
    assert near_pass(stats(100, 100, 333), POLICY)
    assert near_pass(stats(100, 125, 1000), POLICY)
    assert not near_pass(stats(99, 99, 100), POLICY)
    assert not near_pass(stats(100, 200, 400), POLICY)


def test_fingerprint_collision_cannot_create_near_group():
    fake_fingerprints = fingerprints(text("fake", 200))
    result = confirm_pair(row("a", text("left", 200)), row("b", text("right", 200)),
                          fake_fingerprints, fake_fingerprints, POLICY)
    assert not result["accepted"]
    assert result["shared_fivegrams"] == 0


def test_empty_sources_not_grouped_but_exact_doi_supported():
    assert not confirm(row("a", ""), row("b", ""))["accepted"]
    assert confirm(row("a", "a", doi="10.1/same"), row("b", "b", doi="10.1/same"))["reasons"] == ["doi"]


def test_connected_component_identity_stable_under_row_and_edge_order():
    rows = [row("train:2", "a"), row("valid:3", "b"), row("test:4", "c"), row("test:8", "d")]
    edges = [("train:2", "valid:3"), ("valid:3", "test:4")]
    first = component_ledger(rows, edges)
    second = component_ledger(list(reversed(rows)), [(b, a) for a, b in reversed(edges)])
    assert first == second
    assert [r["group_size"] for r in first] == [3, 1, 3, 3]
