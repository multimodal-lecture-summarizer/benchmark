"""Offline cost measurements, CUDA boundaries and partial-arm resume accounting."""

import sys
from types import SimpleNamespace

import pytest

from experiments.scripts import rq2_tib_benchmark_pair as pair
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig


class Backend:
    model_id = "fixture"
    tokenizer_id = "fixture"
    device = "cpu"

    def __init__(self, fail_at=None):
        self.requests = 0
        self.fail_at = fail_at

    def count_tokens(self, text):
        return len(text.split())

    def generate(self, prompt, **kwargs):
        self.requests += 1
        if self.requests == self.fail_at:
            raise RuntimeError("unreported usage on failure")
        return {"text": "summary", "attempts": [{"status": "success",
            "prompt_tokens": self.count_tokens(prompt), "output_tokens": 1}]}


def source():
    return {"transcript": "alpha beta gamma delta", "transcript_segments": {
        "text": ["alpha beta", "gamma delta"], "start": [0, 5]}}


def test_cpu_costs_and_complete_call_counts():
    result = pair.run_source_pair(source(), Backend(), BenchmarkConfig())
    assert result["shared_preparation_seconds"] >= 0
    for arm in result["arms"].values():
        assert arm["segmentation_seconds"] >= 0
        assert arm["generation_seconds"] >= 0
        assert arm["wall_seconds"] == arm["segmentation_seconds"] + arm["generation_seconds"]
        assert arm["call_count"] == arm["chunk_count"] + 1
        assert arm["reported_attempt_count"] == len(arm["calls"])
        assert arm["peak_gpu_allocated_bytes"] is None
        assert arm["peak_gpu_reserved_bytes"] is None
        assert arm["usage_complete"]


def test_s3_predictor_cost_is_charged_to_s3(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(pair.time, "perf_counter", lambda: clock[0])
    original = pair.predict_source_boundaries

    def timed_predictor(*args):
        clock[0] += 3.0
        return original(*args)

    monkeypatch.setattr(pair, "predict_source_boundaries", timed_predictor)
    result = pair.run_source_pair(source(), Backend(), BenchmarkConfig())
    assert result["arms"]["S1"]["segmentation_seconds"] == 0
    assert result["arms"]["S3"]["segmentation_seconds"] == 3
    assert result["shared_preparation_seconds"] == 0


def test_partial_failure_unknown_usage_and_reuse_preserve_original_costs():
    with pytest.raises(pair.PairGenerationError) as raised:
        pair.run_source_pair(source(), Backend(fail_at=3), BenchmarkConfig())
    partial = raised.value.partial_pair
    failed = partial["arms"]["S3"]
    assert failed["status"] == "failed"
    assert failed["call_count"] == 1
    assert failed["reported_attempt_count"] == 0
    assert not failed["usage_complete"]  # Zero recorded tokens is not zero actual usage.
    original = partial["arms"]["S1"]
    backend = Backend()
    resumed = pair.run_source_pair(source(), backend, BenchmarkConfig(), partial["arms"])
    reused = resumed["arms"]["S1"]
    assert reused == {**original, "reused": True}
    assert backend.requests == resumed["arms"]["S3"]["call_count"]


def test_cuda_synchronizes_each_arm_and_captures_absolute_peaks(monkeypatch):
    events = []
    cuda = SimpleNamespace(is_available=lambda: True, is_initialized=lambda: True,
        synchronize=lambda: events.append("sync"),
        reset_peak_memory_stats=lambda: events.append("reset"),
        max_memory_allocated=lambda: 1234, max_memory_reserved=lambda: 5678)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    backend = Backend()
    backend.device = "cuda"
    result = pair.run_source_pair(source(), backend, BenchmarkConfig())
    assert events == ["sync", "reset", "sync"] * 2
    for arm in result["arms"].values():
        assert arm["peak_gpu_allocated_bytes"] == 1234
        assert arm["peak_gpu_reserved_bytes"] == 5678


def test_uninitialized_cuda_has_no_peak_measurement(monkeypatch):
    cuda = SimpleNamespace(is_available=lambda: True, is_initialized=lambda: False)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda))
    backend = Backend()
    backend.device = "cuda"
    result = pair.run_source_pair(source(), backend, BenchmarkConfig())
    assert result["arms"]["S1"]["peak_gpu_allocated_bytes"] is None
