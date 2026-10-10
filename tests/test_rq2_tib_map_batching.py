"""Offline map batching preserves allocations, order and exact usage checks."""

import pytest

from experiments.scripts.rq2_controlled_validation import RunConfig
from experiments.scripts.rq2_tib_benchmark_pair import _summarize, PairGenerationError


class Backend:
    map_batch_size = 3

    def __init__(self, corruption=None):
        self.requests = []
        self.corruption = corruption

    def count_tokens(self, text):
        return len(text.split())

    def response(self, prompt):
        text = "section" + prompt.split("section ", 1)[1].split()[0]
        return {"text": text, "attempts": [{"status": "success",
            "prompt_tokens": self.count_tokens(prompt), "output_tokens": 1}]}

    def generate(self, prompt, **kwargs):
        self.requests.append(([prompt], kwargs["max_output_tokens"]))
        if prompt.startswith("Synthesize"):
            return {"text": "final", "attempts": [{"status": "success",
                "prompt_tokens": self.count_tokens(prompt), "output_tokens": 1}]}
        return self.response(prompt)

    def generate_batch(self, prompts, **kwargs):
        self.requests.append((prompts, kwargs["max_output_tokens"]))
        if self.corruption == "failure":
            raise RuntimeError("device failure")
        responses = [self.response(prompt) for prompt in prompts]
        if self.corruption == "length":
            return responses[:-1]
        if self.corruption == "usage":
            responses[1]["attempts"][0]["prompt_tokens"] += 1
        if self.corruption == "cap":
            responses[1]["attempts"][0]["output_tokens"] = kwargs["max_output_tokens"] + 1
        return responses


def config():
    return RunConfig(model_id="fixture", tokenizer_id="fixture",
        max_source_tokens=100, cumulative_prompt_budget=10000, allowed_prompt_imbalance=10000)


def summarize(backend, on_event=None):
    return _summarize(["a", "b", "c", "d", "e"], backend, config(),
                      12, 4, 0.0, "S1", on_event)


def test_groups_keep_exact_caps_and_original_order():
    backend = Backend()
    events = []
    receipt = summarize(backend, events.append)
    assert [(len(prompts), cap) for prompts, cap in backend.requests] == [(2, 3), (3, 2), (1, 4)]
    assert receipt["map_output_caps"] == [3, 3, 2, 2, 2]
    assert receipt["section_summaries"] == ["section1", "section2", "section3", "section4", "section5"]
    assert "\n".join(receipt["section_summaries"]) in backend.requests[-1][0][0]
    assert receipt["map_output_budget"] == 12
    assert receipt["call_count"] == 6
    assert receipt["generation_request_count"] == 3
    assert receipt["reported_attempt_count"] == 6
    assert receipt["output_tokens"] == 6
    assert receipt["usage_complete"]
    assert receipt["map_batch_size"] == 3
    assert [e["batch_size"] for e in events if e["step"] == "map" and e["status"] == "completed"] == [2, 3]


def test_serial_and_batch_have_equal_fixture_text_and_usage():
    batched = summarize(Backend())
    serial_backend = Backend()
    serial_backend.map_batch_size = 1
    serial = summarize(serial_backend)
    for key in ("summary", "section_summaries", "calls", "prompt_tokens", "output_tokens", "map_output_caps"):
        assert batched[key] == serial[key]
    assert serial["generation_request_count"] == 6


def test_backend_without_batch_support_falls_back_to_serial():
    backend = Backend()
    backend.generate_batch = None
    receipt = summarize(backend)
    assert receipt["map_batch_size"] == 1
    assert receipt["generation_request_count"] == 6


@pytest.mark.parametrize("corruption", ["length", "usage", "cap", "failure"])
def test_batch_failure_keeps_partial_usage_and_is_incomplete(corruption):
    with pytest.raises(PairGenerationError) as raised:
        summarize(Backend(corruption))
    receipt = raised.value.partial_arm
    assert receipt["status"] == "failed"
    assert receipt["usage_complete"] is False
    assert receipt["generation_request_count"] == 1
    assert receipt["call_count"] == 2
    assert len(receipt["calls"]) == (1 if corruption in {"usage", "cap"} else 0)


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_invalid_batch_size_rejected_before_generation(size):
    backend = Backend()
    backend.map_batch_size = size
    with pytest.raises(ValueError, match="positive integer"):
        summarize(backend)
    assert not backend.requests
