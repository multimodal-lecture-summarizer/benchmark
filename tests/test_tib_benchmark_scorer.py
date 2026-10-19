"""Deterministic scorer fixtures; neural doubles never prove checkpoint readiness."""

import json

import numpy as np
import pytest

from experiments.scripts.tib_benchmark_scorer import (
    LocalSemanticScorer, score_record, sha256, source_similarity, validate_assets,
)
from experiments.scripts.rq2_tib_benchmark_metrics import token_alignment_f1


def test_actual_rouge_identity_and_stemming():
    result = score_record("The cats are running.", "The cat is run.", "source")
    assert result["metrics"]["rouge1_f1"] == pytest.approx(.75)
    assert result["metrics"]["rouge2_f1"] == pytest.approx(1 / 3)
    assert result["metrics"]["rougeL_f1"] == pytest.approx(.75)
    exact = score_record("cat dog bird", "cat dog bird", "source")
    assert [exact["metrics"][m] for m in ("rouge1_f1", "rouge2_f1", "rougeL_f1")] == [1, 1, 1]
    assert exact["metrics"]["bertscore_f1"] is None


def test_rouge_l_is_sequence_not_lsum_and_unicode_policy():
    result = score_record("a b c", "c b a", "source")
    assert result["metrics"]["rouge1_f1"] == 1
    assert result["metrics"]["rouge2_f1"] == 0
    assert result["metrics"]["rougeL_f1"] == pytest.approx(1 / 3)
    # Official Google's default ASCII tokenizer, explicitly pinned in the spec.
    assert score_record("中文", "中文", "source")["metrics"]["rouge1_f1"] == 0


@pytest.mark.parametrize("field", range(3))
def test_empty_input_null_not_zero(field):
    inputs = ["summary", "reference", "source"]
    inputs[field] = "  "
    result = score_record(*inputs)
    assert all(v is None for v in result["metrics"].values())
    assert "record" in result["failures"]


def test_source_similarity_formula_and_batch_invariance():
    summary = [[1, 0], [0, 1]]
    source = [[1, 0], [-1, 0]]
    assert source_similarity(summary, [source]) == pytest.approx(.5)
    assert source_similarity(summary, [[[1, 0]], [[-1, 0]]]) == pytest.approx(.5)
    assert source_similarity([[1, 0]], [[[-1, 0]]]) == -1


@pytest.mark.parametrize("summary,batches", [([], [[[1, 0]]]), ([[1, 0]], []),
                                            ([[0, 0]], [[[1, 0]]]), ([[1, 0]], [[[float('nan'), 0]]])])
def test_invalid_vectors_fail_closed(summary, batches):
    with pytest.raises(ValueError):
        source_similarity(summary, batches)


def test_greedy_alignment_fixture_excludes_wrappers_only_from_weights():
    candidate = np.array([[1, 0], [0, 1], [-1, 0]])
    reference = np.array([[1, 0], [0, 1], [-1, 0]])
    assert token_alignment_f1(candidate, reference, candidate_weights=[0, 1, 0],
                              reference_weights=[0, 1, 0]) == pytest.approx(1)


def test_no_implicit_semantic_load_and_nonfinite_is_null():
    class InvalidBackend:
        def score_one(self, *args):
            return float("nan"), .5
    result = score_record("cat", "cat", "cat", semantic=InvalidBackend())
    assert result["metrics"]["rouge1_f1"] == 1
    assert result["metrics"]["bertscore_f1"] is None
    assert "semantic" in result["failures"]


def test_asset_manifest_revision_hash_and_complete_inventory(tmp_path):
    (tmp_path / "model.safetensors").write_bytes(b"fixture-file-not-a-model")
    receipt = {"model": "fixture", "revision": "abc", "files": {
        "model.safetensors": sha256(tmp_path / "model.safetensors")}}
    path = tmp_path / "asset_manifest.json"
    path.write_text(json.dumps(receipt))
    assert validate_assets(tmp_path, model="fixture", revision="abc") == tmp_path
    with pytest.raises(ValueError, match="revision"):
        validate_assets(tmp_path, model="fixture", revision="different")
    (tmp_path / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="complete"):
        validate_assets(tmp_path, model="fixture", revision="abc")


def test_local_scorer_defaults_are_cpu_batch_one():
    metric = LocalSemanticScorer(bert_adapter=object(), sentence_adapter=object())
    assert metric.device == "cpu" and metric.batch_size == 1
