"""Offline event coverage; observation leaves scores and resume receipts intact."""

import sys
from types import SimpleNamespace

import pytest

from experiments.scripts import rq2_tib_benchmark_pair as pair
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig
from experiments.scripts.rq2_tib_benchmark_metrics import (
    SemanticScorer, BERT_MODEL, SBERT_MODEL,
)
from test_rq2_tib_benchmark_costs import Backend, source
from test_rq2_tib_benchmark_metrics import BertAdapter, SentenceAdapter


def test_generation_events_preserve_receipts_and_checkpoint_calls(monkeypatch):
    monkeypatch.setattr(pair.time, "perf_counter", lambda: 0.0)
    events, checkpoints = [], []
    expected = pair.run_source_pair(source(), Backend(), BenchmarkConfig())
    actual = pair.run_source_pair(source(), Backend(), BenchmarkConfig(),
                                  on_event=events.append, on_progress=checkpoints.append)
    assert actual == expected
    assert [list(checkpoint["arms"]) for checkpoint in checkpoints] == [["S1"], ["S1", "S3"]]
    assert [(event["arm"], event["status"]) for event in events
            if event["stage"] == "segmentation"] == [
                (arm, status) for arm in ("S1", "S3") for status in ("started", "completed")]
    for arm in ("S1", "S3"):
        generated = [event for event in events if event["stage"] == "generation" and event["arm"] == arm]
        assert [(event["step"], event["status"]) for event in generated] == [
            ("map", "started"), ("map", "completed"), ("reduce", "started"), ("reduce", "completed")]
        assert generated[0]["chunk_index"] == generated[0]["chunk_total"] == 1
        assert generated[1]["elapsed_seconds"] == 0


@pytest.mark.parametrize("fail_at,step", [(1, "map"), (2, "reduce")])
def test_generation_failure_event_keeps_partial_usage(fail_at, step):
    events = []
    with pytest.raises(pair.PairGenerationError) as raised:
        pair.run_source_pair(source(), Backend(fail_at=fail_at), BenchmarkConfig(), on_event=events.append)
    assert events[-1]["status"] == "failed"
    assert events[-1]["step"] == step
    assert events[-1]["error_type"] == "RuntimeError"
    assert not raised.value.partial_arm["usage_complete"]


def test_segmentation_failure_is_reported(monkeypatch):
    events = []
    def fail(*args):
        raise ValueError("bad source")
    monkeypatch.setattr(pair, "_fixed_chunks", fail)
    with pytest.raises(ValueError, match="bad source"):
        pair.run_source_pair(source(), Backend(), BenchmarkConfig(), on_event=events.append)
    assert [(event["stage"], event["status"]) for event in events] == [
        ("segmentation", "started"), ("segmentation", "failed")]


def test_resumed_arm_emits_reuse_without_generation():
    original = pair.run_source_pair(source(), Backend(), BenchmarkConfig())
    events = []
    backend = Backend()
    resumed = pair.run_source_pair(source(), backend, BenchmarkConfig(), original["arms"], on_event=events.append)
    assert backend.requests == 0
    assert [event for event in events if event["stage"] == "generation"] == [
        {"stage": "generation", "status": "reused", "arm": arm} for arm in ("S1", "S3")]
    assert resumed["arms"]["S1"] == {**original["arms"]["S1"], "reused": True}


def test_metric_events_report_all_source_sentences_and_preserve_scores():
    events = []
    metric = SemanticScorer(batch_size=2, bert_adapter=BertAdapter(),
                            sentence_adapter=SentenceAdapter(), on_event=events.append)
    plain = SemanticScorer(batch_size=2, bert_adapter=BertAdapter(), sentence_adapter=SentenceAdapter())
    arms = {"S1": {"summary": "b."}, "S3": {"summary": "a."}}
    transcript = "a.\nb.\naaaaaaaaaaa.\nbbbbbbbbbb.\na."
    metadata = metric.metadata
    assert metric.score_pair(arms, "a.", transcript) == plain.score_pair(arms, "a.", transcript)
    assert metric.metadata == metadata == plain.metadata
    for stage in ("bertscore", "sbertscore"):
        assert [event["arm"] for event in events if event["stage"] == stage
                and event["status"] == "completed"] == ["S1", "S3"]
        assert all("score" in event for event in events if event["stage"] == stage
                   and event["status"] == "completed")
    batches = [event for event in events if event["stage"] == "source_embedding"]
    assert [event["processed_sentences"] for event in batches] == [0, 2, 4, 5]
    assert all(event["total_sentences"] == 5 for event in batches)
    windows = [event for event in events if event["stage"] == "sentence_windows"]
    assert [event["sentence_index"] for event in windows] == [3, 4]
    assert all(event["window_count"] == 3 and event["input_kind"] == "source" for event in windows)


def test_lazy_model_loading_events_are_emitted_once_without_downloads(monkeypatch):
    events = []
    monkeypatch.setitem(sys.modules, "bert_score", SimpleNamespace(BERTScorer=lambda **kwargs: BertAdapter()))
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=lambda *a, **k: "offline"))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(
        SentenceTransformer=lambda *a, **k: SentenceAdapter()))
    metric = SemanticScorer(on_event=events.append)
    assert metric.load() is metric
    assert metric.load() is metric
    assert [(event["model"], event["status"]) for event in events] == [
        (model, status) for model in (BERT_MODEL, SBERT_MODEL) for status in ("started", "completed")]
