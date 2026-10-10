"""Offline integrity and standalone-notebook checks for reusable TIB data."""

import ast
import copy
import gzip
import hashlib
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tib = importlib.import_module("experiments.scripts.rq2_tib_benchmark_dataset")
bundles = importlib.import_module("experiments.scripts.rq2_tib_benchmark_bundle")
NOTEBOOK = ROOT / "experiments/notebooks/rq2-tib-benchmark-colab.ipynb"


def record(reference, *, texts=None, starts=None, ends=None, genre="Lecture"):
    texts = ["first source paragraph", "final source paragraph"] if texts is None else texts
    return {"doi": reference, "abstract": reference, "genre": genre,
            "transcript": " ".join(texts), "transcript_segments": {
                "text": texts, "start": [0, 2] if starts is None else starts,
                "end": [1, 3] if ends is None else ends}}


@pytest.fixture
def prepared():
    return tib.prepare_dataset({
        "test": [record("test-only abstract", genre="Webinar/Tutorial")],
        "valid": [record("valid-only abstract"), record("SHARED ABSTRACT")],
        "train": [record("train-only abstract", genre="Conference/Talk"),
                  record("shared  abstract"), record(""),
                  record("broken timing", starts=[0, -1])],
    }, verify_counts=False)


@pytest.fixture
def bundle(prepared):
    return bundles.build_benchmark_bundle(prepared)


def test_automatic_maximal_pool_preserves_all_splits_and_flagged_short_abstracts(prepared, bundle):
    assert [(r["split"], r["source_index"]) for r in bundle["items"]] == [
        ("train", 0), ("valid", 0), ("test", 0)]
    assert bundle["metadata"]["selected_count"] == prepared["broad_pool_count"] == 3
    assert bundle["metadata"]["source_count"] == 7
    assert bundle["metadata"]["diversity"] == prepared["broad_pool_diversity"]
    exclusions = {(r["split"], r["source_index"]): r["reasons"]
                  for r in bundle["metadata"]["excluded"]}
    assert "reused_abstract" in exclusions["train", 1]
    assert "reused_abstract" in exclusions["valid", 1]
    assert "empty_abstract" in exclusions["train", 2]
    assert "invalid_segment_times" in exclusions["train", 3]
    assert all("short_abstract_under_30_words" in r["audit_flags"] for r in bundle["items"])
    bundles.validate_bundle(bundle)


def test_partial_split_scan_is_rejected():
    prepared = tib.prepare_dataset({"valid": [record("one")]}, verify_counts=False)
    with pytest.raises(ValueError, match="all three"):
        bundles.build_benchmark_bundle(prepared)


def test_source_adapter_has_no_reference_and_owns_segment_arrays(bundle):
    item = bundle["items"][0]
    source = bundles.generation_input(item)
    assert set(source) == {"id", "split", "source_index", "doi", "source_sha256",
                           "transcript", "transcript_segments"}
    assert source["transcript"] == item["source_text"]
    assert source["transcript_segments"]["text"] == list(item["segment_texts"])
    assert source["transcript_segments"]["start"] == list(item["segment_starts_seconds"])
    target = bundles.evaluation_target(item)
    assert target == {"id": source["id"], "reference_text": item["reference_text"],
                      "reference_sha256": item["reference_sha256"]}
    source["transcript_segments"]["text"][0] = "changed"
    assert item["segment_texts"][0] == "first source paragraph"


def test_token_counts_measure_full_long_source_and_unicode_reference():
    texts = ["αβ " * 12000, "last sentinel"]
    prepared = tib.prepare_dataset({s: [record(f"reference {s}", texts=texts)]
                                   for s in tib.SPLITS}, verify_counts=False)
    bundle = bundles.build_benchmark_bundle(prepared)
    before = copy.deepcopy(bundle["items"])
    seen = []

    def encode(text):
        seen.append(text)
        return list(text.encode("utf-8"))

    assert bundles.add_token_counts(bundle, encode, tokenizer_id="test", tokenizer_revision="pinned") is bundle
    for old, item in zip(before, bundle["items"]):
        assert item["source_text"] == old["source_text"]
        assert item["source_text"].endswith("last sentinel")
        assert item["source_tokens"] == len(item["source_text"].encode("utf-8"))
        assert item["reference_tokens"] == len(item["reference_text"].encode("utf-8"))
    assert len(seen) == 6
    assert bundle["metadata"]["tokenizer"]["truncation"] is False
    for identity in (("", "pin"), ("name", "")):
        with pytest.raises(ValueError, match="tokenizer"):
            bundles.add_token_counts(bundle, encode, tokenizer_id=identity[0], tokenizer_revision=identity[1])


def test_gzip_roundtrip_preserves_content_counts_identity_and_payload_digest(bundle, tmp_path):
    path = tmp_path / "nested" / "data.jsonl.gz"
    receipt = bundles.save_benchmark_bundle(bundle, path)
    loaded = bundles.load_benchmark_bundle(path)
    assert loaded == json.loads(json.dumps(bundle))
    assert receipt["records"] == len(bundle["items"])
    assert receipt["bytes"] == path.stat().st_size
    with gzip.open(path, "rb") as stream:
        lines = stream.readlines()
    actual = hashlib.sha256(b"".join(lines[:-1])).hexdigest()
    assert actual == receipt["payload_sha256"] == json.loads(lines[-1])["sha256"]
    assert loaded["metadata"]["selection_sha256"] == bundle["metadata"]["selection_sha256"]


@pytest.mark.parametrize("damage", ["truncate_gzip", "remove_checksum", "tamper", "trailing", "entry_order"])
def test_corrupt_or_incomplete_bundle_rejected(bundle, tmp_path, damage):
    path = tmp_path / "data.gz"
    bundles.save_benchmark_bundle(bundle, path)
    if damage == "truncate_gzip":
        path.write_bytes(path.read_bytes()[:-8])
    else:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            lines = stream.readlines()
        if damage == "remove_checksum":
            lines.pop()
        elif damage == "tamper":
            lines[1] = lines[1].replace("first source paragraph", "other source paragraph")
        elif damage == "trailing":
            lines.append(lines[1])
        else:
            lines[0], lines[1] = lines[1], lines[0]
        with gzip.open(path, "wt", encoding="utf-8") as stream:
            stream.writelines(lines)
    with pytest.raises((ValueError, EOFError, OSError)):
        bundles.load_benchmark_bundle(path)


@pytest.mark.parametrize("starts,ends", [([-1, 2], [1, 3]), ([False, 2], [1, 3]),
    ([0, float("nan")], [1, 3]), ([0, 2], [1, float("inf")]),
    ([2, 0], [3, 1]), ([0, 2], [1, 1]), ([0], [1, 3]), (["0", 2], [1, 3])])
def test_validation_rejects_malformed_timing(bundle, starts, ends):
    bundle["items"][0]["segment_starts_seconds"] = starts
    bundle["items"][0]["segment_ends_seconds"] = ends
    with pytest.raises(ValueError, match="source|times"):
        bundles.validate_bundle(bundle)


def test_validation_rejects_empty_segment(bundle):
    bundle["items"][0]["segment_texts"] = ["", "final source paragraph"]
    with pytest.raises(ValueError, match="Empty source segment"):
        bundles.validate_bundle(bundle)


@pytest.mark.parametrize("damage", ["count", "duplicate", "order", "source", "reference", "identity", "revision"])
def test_validation_rejects_integrity_changes(bundle, damage):
    if damage == "count":
        bundle["metadata"]["selected_count"] += 1
    elif damage == "duplicate":
        bundle["items"][1] = copy.deepcopy(bundle["items"][0])
    elif damage == "order":
        bundle["items"].reverse()
    elif damage == "source":
        bundle["items"][0]["source_text"] += " changed"
    elif damage == "reference":
        bundle["items"][0]["reference_text"] += " changed"
    elif damage == "revision":
        bundle["metadata"]["revision"] = "wrong"
    else:
        bundle["metadata"]["selection_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        bundles.validate_bundle(bundle)


def test_overwrite_and_atomic_failure_leave_original_and_clean_temp(bundle, tmp_path, monkeypatch):
    path = tmp_path / "data.gz"
    bundles.save_benchmark_bundle(bundle, path)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        bundles.save_benchmark_bundle(bundle, path)
    bundle["metadata"]["extra"] = "replacement"
    real_replace = bundles.os.replace

    def fail_replace(source, target):
        assert Path(source).parent == path.parent
        assert path.read_bytes() == original
        raise OSError("simulated replace failure")

    monkeypatch.setattr(bundles.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        bundles.save_benchmark_bundle(bundle, path, overwrite=True)
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    monkeypatch.setattr(bundles.os, "replace", real_replace)
    bundles.save_benchmark_bundle(bundle, path, overwrite=True)
    assert bundles.load_benchmark_bundle(path)["metadata"]["extra"] == "replacement"


def test_save_rechecks_existing_target_after_writing_temp(bundle, tmp_path, monkeypatch):
    path = tmp_path / "data.gz"
    real_exists = Path.exists
    calls = 0

    def exists(candidate):
        nonlocal calls
        if candidate == path:
            calls += 1
            if calls == 2:
                path.write_bytes(b"concurrent writer")
        return real_exists(candidate)

    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(FileExistsError):
        bundles.save_benchmark_bundle(bundle, path)
    assert path.read_bytes() == b"concurrent writer"
    assert list(tmp_path.iterdir()) == [path]


def test_standalone_notebook_embedded_sources_are_exact_and_compile():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = {}
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        # User-executed evidence may coexist with updated source cells.
        assert isinstance(cell["outputs"], list)
        code = "".join(cell["source"])
        compile(code, f"cell-{index}", "exec")
        for statement in ast.parse(code).body:
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        sources[target.id] = statement.value.value
    for variable, name in (("PREPARATION_SOURCE", "rq2_tib_benchmark_dataset.py"),
                           ("BUNDLE_SOURCE", "rq2_tib_benchmark_bundle.py")):
        assert sources[variable] == (ROOT / "experiments/scripts" / name).read_text(encoding="utf-8")
        compile(sources[variable], name, "exec")


@pytest.mark.parametrize("cached", [False, True])
def test_preparation_notebook_executes_offline_and_reuses_saved_bundle(bundle, tmp_path, monkeypatch, cached):
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    ns = {"sys": sys, "Path": Path, "pd": pd, "plt": plt,
          "display": lambda value: None, "tqdm": lambda rows, **kwargs: rows}
    # Attribute embedded code to its real source for accurate coverage reporting.
    ns["compile"] = lambda source, filename, mode: compile(
        source, str(ROOT / "experiments/scripts" / filename), mode)
    monkeypatch.setattr(plt, "show", lambda: None)
    # Execute genuine bootstrap in an isolated module registry, restored by monkeypatch.
    for name in ("experiments", "experiments.scripts", *(
            "experiments.scripts." + short for short in (
                "rq2_tib_benchmark_dataset", "rq2_tib_benchmark_bundle", "rq2_controlled_validation",
                "rq2_local_hf_backend", "rq2_tib_benchmark_results", "rq2_tib_benchmark_pair",
                "rq2_tib_benchmark_metrics", "rq2_tib_benchmark"))):
        monkeypatch.setitem(sys.modules, name, sys.modules.get(name, types.ModuleType(name)))
        monkeypatch.delitem(sys.modules, name, raising=False)
    exec("".join(notebook["cells"][5]["source"]), ns)
    data_module, bundle_module = ns["data_module"], ns["bundle_module"]
    fake_transformers = types.ModuleType("transformers")

    class OfflineTokenizer:
        @classmethod
        def from_pretrained(cls, name, **kwargs):
            assert name == "offline-tokenizer" and kwargs == {"revision": "pinned"}
            return cls()

        def encode(self, text, **kwargs):
            assert kwargs == {"add_special_tokens": False, "truncation": False, "verbose": False}
            return list(text.encode("utf-8"))

    fake_transformers.AutoTokenizer = OfflineTokenizer
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    ns.update(BUNDLE_PATH=tmp_path / "data.gz", REBUILD_DATA=False,
              MODEL_ID="offline-tokenizer", MODEL_REVISION="pinned",
              BENCHMARK_CONFIG={"primary_metric": "rouge_l_f1_against_creator_abstract"})
    rows = {s: [record(f"unique {s}")] for s in tib.SPLITS}
    monkeypatch.setattr(data_module, "EXPECTED_COUNTS", {s: 1 for s in tib.SPLITS})

    def load(splits):
        assert tuple(splits) == tib.SPLITS
        if cached:
            pytest.fail("Cached preparation must not download corpus")
        return rows

    monkeypatch.setattr(data_module, "load_pinned_splits", load)
    if cached:
        bundles.add_token_counts(bundle, lambda text: list(text.encode("utf-8")),
                                tokenizer_id="offline-tokenizer", tokenizer_revision="pinned")
        bundle["metadata"]["benchmark_config"] = ns["BENCHMARK_CONFIG"]
        bundles.save_benchmark_bundle(bundle, ns["BUNDLE_PATH"])
        monkeypatch.setattr(OfflineTokenizer, "from_pretrained", lambda *a, **k: pytest.fail("Cached token counts must be reused"))
    for index in (7, 9, 11, 13, 15):
        exec(compile("".join(notebook["cells"][index]["source"]), f"cell-{index}", "exec"), ns)
    assert ns["ready"]["status"] == "data_prepared"
    assert ns["ready"]["records"] == 3
    assert len(list(ns["benchmark_inputs"])) == len(ns["benchmark_targets"]) == 3
    assert list(tmp_path.iterdir()) == [ns["BUNDLE_PATH"]]
    assert bundles.load_benchmark_bundle(ns["BUNDLE_PATH"])["metadata"]["selected_count"] == 3
