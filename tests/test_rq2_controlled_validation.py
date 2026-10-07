"""Contract checks for the validation-only RQ2 controlled runner."""

import hashlib
import json

import pytest

from experiments.scripts import rq2_controlled_validation as runner


class MeteredBackend:
    model_id = "real-model-fixture"
    tokenizer_id = "exact-fixture-tokenizer"

    def __init__(self, retry=False, corrupt=False, special_output=False,
                 expanded_decoding=False):
        self.retry = retry
        self.corrupt = corrupt
        self.special_output = special_output
        self.expanded_decoding = expanded_decoding
        self.limits = []

    def count_tokens(self, text):
        return len(text.split())

    def generate(self, prompt, *, max_output_tokens, temperature, seed):
        self.limits.append(max_output_tokens)
        count = self.count_tokens(prompt)
        attempts = ([{"prompt_tokens": count, "output_tokens": 0, "status": "retry"}]
                    if self.retry else [])
        attempts.append({"prompt_tokens": count + int(self.corrupt),
                         "output_tokens": 1 if self.expanded_decoding else (3 if self.special_output else 2),
                         "content_tokens": 2, "status": "success"})
        return {"text": "source summary", "attempts": attempts}


@pytest.fixture
def receipt(tmp_path):
    selected = [{"doi": f"10.5446/{index} (DOI)"} for index in range(1, 21)]
    dois = [item["doi"] for item in selected]
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps({"dataset": runner.DATASET, "revision": runner.REVISION,
        "split_read": "valid", "test_content_accessed": False,
        "selected": selected,
        "selected_doi_sha256": hashlib.sha256(json.dumps(dois, ensure_ascii=False).encode()).hexdigest()}),
        encoding="utf-8")
    return path


def config(**changes):
    values = dict(model_id=MeteredBackend.model_id, tokenizer_id=MeteredBackend.tokenizer_id,
                  max_source_tokens=100, cumulative_prompt_budget=500,
                  allowed_prompt_imbalance=100, chunk_tokens=8, max_output_tokens=10)
    values.update(changes)
    return runner.RunConfig(**values)


def record():
    return {"doi": "10.5446/1 (DOI)", "transcript_segments": {
        "text": ["one two three", "four five six", "seven eight nine"],
        "start": [0, 10, 20], "end": [8, 18, 28]}}


def test_preflight_blocks_missing_backend_and_test_split(receipt):
    assert runner.preflight(receipt_path=receipt)["status"] == "blocked_backend_unavailable"
    data = json.loads(receipt.read_text())
    data["split_read"] = "test"
    receipt.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="validation-only"):
        runner.preflight(receipt_path=receipt)


def test_pair_has_same_source_and_resumes_exact_identity(receipt, tmp_path):
    backend = MeteredBackend(retry=True)
    result = runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                             config(), tmp_path / "output", receipt)
    assert result["status"] == "paired_diagnostic"
    assert result["source_tokens"] == 9
    assert result["arms"]["S1"]["prompt_tokens"] > 0
    assert result["arms"]["S3"]["prompt_tokens"] > 0
    assert any(call["status"] == "retry" for call in result["arms"]["S1"]["calls"])
    assert runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                           config(), tmp_path / "output", receipt) == result
    with pytest.raises(ValueError, match="unsafe resume"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                        config(chunk_tokens=7), tmp_path / "output", receipt)
    saved = tmp_path / "output" / "10-5446-1-DOI.json"
    altered = json.loads(saved.read_text())
    altered["arms"]["S1"]["summary"] = "tampered"
    saved.write_text(json.dumps(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="unsafe resume"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                        config(), tmp_path / "output", receipt)


def test_rejects_bad_usage_budget_and_source(receipt, tmp_path):
    with pytest.raises(ValueError, match="usage disagrees"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [10], MeteredBackend(corrupt=True),
                        config(), tmp_path / "bad", receipt)
    with pytest.raises(ValueError, match="budget exceeded"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [10], MeteredBackend(),
                        config(cumulative_prompt_budget=1), tmp_path / "budget", receipt)
    with pytest.raises(ValueError, match="source span exceeds"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [10], MeteredBackend(),
                        config(max_source_tokens=1), tmp_path / "source", receipt)
    with pytest.raises(ValueError, match="outside declared"):
        runner.run_pair(record(), "10.5446/999 (DOI)", [10], MeteredBackend(),
                        config(), tmp_path / "outside", receipt)
    with pytest.raises(ValueError, match="source-only predicted"):
        runner.run_pair(record(), "10.5446/1 (DOI)", [20], MeteredBackend(),
                        config(), tmp_path / "oracle", receipt)


def test_raw_generation_usage_may_include_decoded_eos(receipt, tmp_path):
    result = runner.run_pair(record(), "10.5446/1 (DOI)", [10],
                             MeteredBackend(special_output=True), config(),
                             tmp_path / "eos", receipt)
    assert result["arms"]["S1"]["calls"][-1]["output_tokens"] == 3
    assert result["arms"]["S1"]["calls"][-1]["content_tokens"] == 2


def test_decoded_text_can_reencode_to_more_tokens(receipt, tmp_path):
    result = runner.run_pair(record(), "10.5446/1 (DOI)", [10],
                             MeteredBackend(expanded_decoding=True), config(),
                             tmp_path / "expanded", receipt)
    assert result["arms"]["S1"]["calls"][-1]["output_tokens"] == 1
    assert result["arms"]["S1"]["calls"][-1]["content_tokens"] == 2


def test_final_summary_has_separate_output_budget(receipt, tmp_path):
    backend = MeteredBackend()
    runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                    config(max_output_tokens=10, final_output_tokens=30),
                    tmp_path / "long_final", receipt)
    assert backend.limits.count(30) == 2
    assert backend.limits.count(10) == len(backend.limits) - 2


def test_batched_map_generation_keeps_per_prompt_receipts(receipt, tmp_path):
    class BatchedBackend(MeteredBackend):
        def __init__(self):
            super().__init__()
            self.batch_sizes = []

        def format_prompt(self, prompt):
            return prompt

        def generate_batch(self, prompts, *, max_output_tokens, temperature, seed):
            self.batch_sizes.append(len(prompts))
            return [self.generate(prompt, max_output_tokens=max_output_tokens,
                                  temperature=temperature, seed=seed)
                    for prompt in prompts]

    backend = BatchedBackend()
    result = runner.run_pair(record(), "10.5446/1 (DOI)", [10], backend,
                             config(map_batch_size=2), tmp_path / "batched", receipt)
    assert result["status"] == "paired_diagnostic"
    assert backend.batch_sizes == [2, 2]
    assert all(call["prompt_tokens"] > 0 for arm in result["arms"].values()
               for call in arm["calls"])
    assert all(len(arm["calls"]) == arm["chunk_count"] + 1
               for arm in result["arms"].values())
