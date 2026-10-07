"""Regression contracts for validation-only ASR selection, without model downloads."""

import hashlib
import json
import sys
from dataclasses import replace

import pytest

from benchmarks.scripts import run_asr_model_benchmark as bakeoff
from experiments.evaluation.asr_selection_scoring import (
    normalize_english_asr, require_selection_metadata, score_asr_pairs,
    selection_metadata, validation_units,
)
from experiments.scripts.benchmark_artifacts import (
    RunnerContext, read_json_artifact, write_json_artifact, write_run_manifest,
)


def _unit(unit_id="validation:one", split="validation", reference="hello world"):
    return {"unit_id": unit_id, "dataset_id": "dataset", "split": split,
            "reference_text": reference, "media_path": f"{unit_id}.wav"}


@pytest.mark.parametrize("reference,hypothesis", [
    ("Hello, WORLD!", "hello world"),
    ("It 's fine; don't worry.", "IT’S fine dont worry"),
    ("the u s economy", "The US economy."),
    ("the u s economy", "the U.S. economy"),
    ("Ｆｉｎｅ\t weather", "fine weather"),
])
def test_formatting_invariance(reference, hypothesis):
    score = score_asr_pairs([(reference, hypothesis)])
    assert score["wer"] == score["cer"] == 0


def test_us_pronoun_and_genuine_errors_are_preserved():
    assert normalize_english_asr("help us") == "help us"
    assert normalize_english_asr("help US") == "help u s"
    score = score_asr_pairs([("the cat sits", "the dog sits")])
    assert score["word_errors"] == 1
    assert score["wer"] == pytest.approx(1 / 3)
    assert score_asr_pairs([("can go", "cannot go")])["wer"] > 0


def test_unit_boundaries_and_micro_cer_denominators():
    # Concatenation would give the erroneous score zero.
    score = score_asr_pairs([("a b", "a"), ("c", "b c")])
    assert score["word_errors"] == 2
    assert score["wer"] == pytest.approx(2 / 3)
    assert score_asr_pairs([("a", "b"), ("bbb", "bbb")])["cer"] == .25
    assert score_asr_pairs([("two words", "")])["wer"] == 1


@pytest.mark.parametrize("pairs", [[], [("...", "anything")], [("", "")]])
def test_empty_reference_or_corpus_fails(pairs):
    with pytest.raises(ValueError):
        score_asr_pairs(pairs)


def test_optional_jiwer_never_changes_scores(monkeypatch):
    pairs = [("a b", "a"), ("c", "b c")]
    expected = score_asr_pairs(pairs)
    monkeypatch.setitem(sys.modules, "jiwer", None)
    assert score_asr_pairs(pairs) == expected
    monkeypatch.setitem(sys.modules, "jiwer", object())
    assert score_asr_pairs(pairs) == expected


@pytest.mark.parametrize("split", [None, "", "test", "Validation", [], 1])
def test_unknown_or_missing_split_fails_even_when_not_selected(split):
    with pytest.raises(RuntimeError, match="split"):
        validation_units([_unit(), _unit("other", split)])


def test_validation_isolation_and_duplicates():
    valid = _unit()
    test = _unit("final_test:one", "final_test", "SECRET TEST REFERENCE")
    assert validation_units([test, valid, _unit("train:one", "train")]) == [valid]
    with pytest.raises(RuntimeError, match="validation units"):
        validation_units([test])
    with pytest.raises(RuntimeError, match="duplicate"):
        validation_units([valid, valid])


def test_shortlist_requires_matching_version_and_validation_identity():
    units = [_unit()]
    good = selection_metadata(units)
    require_selection_metadata(good, units)
    for key in good:
        incomplete = {k: v for k, v in good.items() if k != key}
        with pytest.raises(RuntimeError, match="shortlist"):
            require_selection_metadata(incomplete, units)
    with pytest.raises(RuntimeError):
        require_selection_metadata({**good, "scoring": {"normalizer": "legacy"}}, units)
    with pytest.raises(RuntimeError):
        require_selection_metadata(good, [_unit("validation:other")])
    with pytest.raises(RuntimeError):
        selection_metadata([_unit(), _unit("test", "final_test")])


def _context(tmp_path, notebook_id, profile):
    return RunnerContext(profile=profile, run_namespace="official", status="real",
                         artifact_root=tmp_path, notebook_id=notebook_id, run_id="test-run",
                         source_sha256=hashlib.sha256(b"fixture-source").hexdigest(),
                         config_sha256=hashlib.sha256(b"fixture-config").hexdigest(),
                         dependency_state_sha256=hashlib.sha256(b"fixture-dependency").hexdigest())


@pytest.mark.parametrize("field,sentinel", [
    ("source_sha256", "a" * 64),
    ("config_sha256", "b" * 64),
    ("dependency_state_sha256", "c" * 64),
])
def test_official_historical_sentinel_rejected_before_inference(tmp_path, monkeypatch, field, sentinel):
    """Matching payload/receipt/run cannot legitimize fabricated provenance."""
    consumer = _context(tmp_path, "01a_asr_model_benchmark", "full")
    producer = replace(consumer, notebook_id="00c_dataset_eda_and_freeze")
    write_json_artifact(producer, "dataset.frozen_manifest", [{
        "dataset_id": "dataset", "freeze_status": "eligible",
        "scientific_selection_eligible": True, "unit_ids": [_unit()["unit_id"]],
        "unit_records": [_unit()], "reason": "validation fixture", "profile": "full",
    }])
    write_json_artifact(producer, "dataset.registry", [{"dataset_id": "dataset", "revision": "v1"}])
    write_json_artifact(producer, "dataset.endpoint_matrix", [{
        "dataset_id": "dataset", "endpoint": "asr_benchmark",
        "scientific_selection_eligible": True, "eligibility": "eligible_d2",
        "reason": "validation fixture",
    }])
    write_run_manifest(producer)
    assert read_json_artifact(consumer, "dataset.frozen_manifest")["records"]

    receipt_path = producer.namespace_root / "dataset.frozen_manifest.receipt.json"
    run_path = producer.namespace_root / "runs" / "00c_dataset_eda_and_freeze.run.json"
    # Reproduce historical sentinel metadata without altering the valid payload.
    for path in (receipt_path, run_path):
        document = json.loads(path.read_text())
        document[field] = sentinel
        path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        read_json_artifact(consumer, "dataset.frozen_manifest")

    monkeypatch.setattr(bakeoff, "parse_context", lambda *args: consumer)
    accessed = []
    monkeypatch.setattr(bakeoff, "require_media", lambda *args: accessed.append("media"))
    monkeypatch.setattr(bakeoff, "ADAPTER_FACTORY", lambda *args: accessed.append("model"))
    assert bakeoff.main([]) == 1
    assert accessed == []
