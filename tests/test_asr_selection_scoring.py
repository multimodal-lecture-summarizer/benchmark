"""Regression contracts for validation-only ASR selection, without model downloads."""

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from benchmarks.scripts import run_asr_model_benchmark as bakeoff
from benchmarks.scripts import run_asr_preprocessing_ablation as ablation
from experiments.evaluation.asr_selection_scoring import (
    normalize_english_asr, require_selection_metadata, score_asr_pairs,
    scoring_metadata, selection_metadata, validation_units,
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


@pytest.mark.parametrize("runner,notebook_id", [
    (bakeoff, "01a_asr_model_benchmark"),
    (ablation, "01b_asr_preprocessing_ablation"),
])
@pytest.mark.parametrize("profile", ["smoke", "full"])
def test_runners_never_infer_or_select_on_test(tmp_path, monkeypatch, runner, notebook_id, profile):
    context = _context(tmp_path, notebook_id, profile)
    if runner is bakeoff:
        context = replace(context, run_namespace="diagnostic")
    valid = _unit()
    units = [_unit("test:secret", "final_test", "do not inspect"), valid]
    monkeypatch.setattr(runner, "parse_context", lambda *args: context)
    def load_units(context, *, limit_smoke):
        assert limit_smoke is False
        return units

    monkeypatch.setattr(runner, "load_eligible_units", load_units)
    seen = []

    def media(unit, *args):
        seen.append(unit["unit_id"])
        assert unit["split"] == "validation"
        return Path("validation.wav")

    if runner is bakeoff:
        producer = replace(context, notebook_id="00c_dataset_eda_and_freeze")
        write_json_artifact(producer, "dataset.frozen_manifest", [{
            "dataset_id": "fixture", "unit_records": [valid], "unit_ids": [valid["unit_id"]],
        }])
        write_run_manifest(producer)
        from experiments.evaluation.asr_candidate_adapters import TranscriptResult

        class FakeAdapter:
            def __init__(self, candidate):
                self.id = candidate["id"]
                self.model_size = "fixture"
                self.device = "cpu"
                self.load_seconds = 0.
                self.dependency_versions = {"fixture": "1"}

            def load(self):
                pass

            def transcribe(self, audio):
                return TranscriptResult("HELLO, world!", .1)

            def close(self):
                pass

        monkeypatch.setattr(runner, "ADAPTER_FACTORY", FakeAdapter)
        monkeypatch.setattr(runner, "_audio", lambda unit, **kwargs: (seen.append(unit["unit_id"]) or __import__("numpy").ones(16000, dtype="float32"), 1., "a" * 64))
    else:
        monkeypatch.setattr(runner, "require_media", media)
        monkeypatch.setattr(runner, "_audio_duration_sec", lambda path: 1.)
        monkeypatch.setattr(runner, "_transcribe", lambda *args, **kwargs: ("HELLO, world!", .1))
        monkeypatch.setattr(runner, "read_json_artifact", lambda *args: {"records": [
            {"candidate": "faster-whisper-tiny.en", "selected": True, **selection_metadata([valid])}
        ]})
    assert runner.main([]) == 0
    assert set(seen) == {valid["unit_id"]}
    if runner is bakeoff:
        assert seen.count(valid["unit_id"]) == 6
    payloads = list((context.namespace_root / "payloads").glob("asr.*.json"))
    assert len(payloads) == (5 if runner is bakeoff else 3)
    for payload in payloads:
        records = json.loads(payload.read_text())["records"]
        for record in records:
            assert record["selection_split"] == "validation"
            assert record["selection_unit_count"] == 1
            assert record["scoring"] == scoring_metadata()
            assert record.get("unit_id", valid["unit_id"]) == valid["unit_id"]
            if "metrics" in record and record["metrics"]:
                assert record["metrics"].get("wer", record["metrics"].get("corpus_wer")) == 0


@pytest.mark.parametrize("runner", [bakeoff, ablation])
def test_runners_reject_bad_splits_before_media_or_model(monkeypatch, runner):
    monkeypatch.setattr(runner, "parse_context", lambda *args: object())
    monkeypatch.setattr(runner, "load_eligible_units", lambda context, **kwargs: [_unit(), _unit("bad", None)])
    seen = []
    monkeypatch.setattr(runner, "require_media", lambda *args: seen.append("media"))
    assert runner.main([]) == 1
    assert seen == []


def test_ablation_rejects_historical_shortlist_before_inference(monkeypatch):
    monkeypatch.setattr(ablation, "read_json_artifact", lambda *args: {"records": [
        {"candidate": "faster-whisper-tiny.en", "selected": True}
    ]})
    with pytest.raises(RuntimeError, match="regenerate on validation"):
        ablation._resolve_shortlisted_model(object(), [_unit()])


def test_ablation_emits_typed_block_for_new_asr_candidate(tmp_path, monkeypatch):
    context = _context(tmp_path, "01b_asr_preprocessing_ablation", "smoke")
    unit = _unit()
    monkeypatch.setattr(ablation, "parse_context", lambda *args: context)
    monkeypatch.setattr(ablation, "load_eligible_units", lambda *args, **kwargs: [unit])
    monkeypatch.setattr(ablation, "read_json_artifact", lambda *args: {"records": [
        {"candidate": "RQ0_A.A0_WhisperBase", "selected": True,
         **selection_metadata([unit])},
    ]})

    assert ablation.main([]) == 2
    for artifact in ("asr.ablation_predictions", "asr.ablation_metrics", "asr.frozen_configuration"):
        payload = json.loads((context.namespace_root / "payloads" / f"{artifact}.json").read_text())
        assert payload["records"][0]["status"] == "blocked_unsupported_candidate"


@pytest.mark.parametrize("selected_flags", [[False], [True, True]])
def test_ablation_rejects_ambiguous_selection(monkeypatch, selected_flags):
    records = [{"candidate": "faster-whisper-tiny.en", "selected": selected,
                **selection_metadata([_unit()])} for selected in selected_flags]
    monkeypatch.setattr(ablation, "read_json_artifact", lambda *args: {"records": records})
    with pytest.raises(RuntimeError, match="exactly one"):
        ablation._resolve_shortlisted_model(object(), [_unit()])


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
