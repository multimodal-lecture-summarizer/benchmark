"""Exact batched backend receipts, without loading a model."""
from types import SimpleNamespace

from experiments.scripts.rq2_local_hf_backend import LocalHfUsageBackend


def test_batch_trims_all_model_terminal_ids_before_padding():
    import torch

    class Tokenizer:
        pad_token_id = eos_token_id = 2

        def __call__(self, prompts, **kwargs):
            return {"input_ids": torch.tensor([[1, 3], [1, 4]]),
                    "attention_mask": torch.ones((2, 2), dtype=torch.long)}

        def encode(self, text, **kwargs):
            return text.split()

        def decode(self, ids, **kwargs):
            return " ".join(str(i) for i in ids if i not in {2, 99})

    backend = object.__new__(LocalHfUsageBackend)
    backend.tokenizer = Tokenizer()
    backend.device = "cpu"
    backend.context_limit = 20
    backend.model = SimpleNamespace(
        generation_config=SimpleNamespace(eos_token_id=[2, 99]),
        generate=lambda **kwargs: torch.tensor([[1, 3, 7, 99, 2], [1, 4, 8, 9, 99]]))
    responses = backend.generate_batch(["first", "second"], max_output_tokens=3,
                                       temperature=0, seed=42)
    assert [row["attempts"][0]["output_tokens"] for row in responses] == [2, 3]
    assert [row["attempts"][0]["content_tokens"] for row in responses] == [1, 2]
    assert [row["text"] for row in responses] == ["7", "8 9"]


def test_batch_token_count_uses_unpadded_untruncated_raw_inputs():
    backend = object.__new__(LocalHfUsageBackend)
    captured = {}
    def tokenize(texts, **kwargs):
        captured.update(kwargs)
        return {"input_ids": [list(text) for text in texts]}
    backend.tokenizer = tokenize
    assert backend.count_tokens_batch(["a", "abc"]) == [1, 3]
    assert captured["padding"] is False
    assert captured["truncation"] is False
    assert captured["add_special_tokens"] is False
    assert backend.count_tokens_batch([]) == []
