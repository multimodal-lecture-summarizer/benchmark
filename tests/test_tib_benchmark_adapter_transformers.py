import json
from pathlib import Path

import pytest

from experiments.scripts.tib_benchmark_adapter_budget import AdapterFailure, Budget
from experiments.scripts.tib_benchmark_adapter_transformers import LoadedGenerator, causal_chat_wrapper


class TokenizerFixture:
    pad_token_id = 0

    def decode(self, ids, **kwargs):
        return " ".join(str(value) for value in ids)


def test_actual_loaded_generator_callable_strips_causal_prompt():
    torch = pytest.importorskip("torch")

    class ModelFixture:
        def eval(self):
            return self

        def generate(self, **kwargs):
            assert kwargs["max_new_tokens"] == 2
            assert "global_attention_mask" not in kwargs
            assert kwargs["input_ids"].tolist() == [[11, 12]]
            return torch.tensor([[11, 12, 21, 22]])

    loaded = LoadedGenerator(ModelFixture(), TokenizerFixture(), architecture="causal",
                             device="cpu", decode_parameters={"do_sample": False})
    batch = Budget("causal", 4, 2).prepare([11, 12], lambda ids, stage: ids, "map")
    assert loaded(batch, 2, "map") == "21 22"
    assert loaded.last_receipt["generated_native_tokens"] == 2


def test_encdec_binding_uses_padded_led_mask_and_omits_decoder_start():
    torch = pytest.importorskip("torch")

    class ModelFixture:
        def eval(self):
            return self

        def generate(self, **kwargs):
            assert kwargs["global_attention_mask"].tolist() == [[1, 0, 0, 0]]
            assert kwargs["attention_mask"].tolist() == [[1, 1, 0, 0]]
            return torch.tensor([[2, 21, 22]])

    loaded = LoadedGenerator(ModelFixture(), TokenizerFixture(), architecture="encoder_decoder",
                             device="cpu", decode_parameters={}, led_global_attention=True)
    batch = Budget("encoder_decoder", 4, 2, decoder_cap=4, padding_multiple=4,
                   global_first_token=True).prepare([11, 12], lambda ids, stage: ids, "map")
    assert loaded(batch, 2, "map") == "21 22"


def test_backend_cannot_override_boundaries():
    with pytest.raises(ValueError, match="override"):
        LoadedGenerator(None, None, architecture="causal", device="cpu",
                        decode_parameters={"max_length": 40})


def test_loaded_generation_records_config_and_terminal_eos_without_decode_changes():
    torch = pytest.importorskip("torch")

    class ModelFixture:
        generation_config = {"num_beams": 4, "eos_token_id": [2, 3]}

        def eval(self):
            return self

        def generate(self, **kwargs):
            assert kwargs["num_beams"] == 1
            assert kwargs["max_new_tokens"] == 2
            return torch.tensor([[11, 12, 21, 3]])

    loaded = LoadedGenerator(ModelFixture(), TokenizerFixture(), architecture="causal",
                             device="cpu", decode_parameters={"num_beams": 1})
    batch = Budget("causal", 4, 2).prepare([11, 12], lambda ids, stage: ids, "map")
    assert loaded(batch, 2, "map") == "21 3"
    assert loaded.last_receipt["eos_observed"] is True
    assert loaded.last_receipt["token_budget_exhausted"] is False
    assert loaded.last_receipt["base_generation_config"]["num_beams"] == 4
    assert loaded.last_receipt["effective_generation_config"]["num_beams"] == 1


def test_failed_node_cannot_inherit_previous_success_telemetry(tmp_path):
    import time
    from experiments.scripts.tib_benchmark_checkpoint import NodeCheckpointGenerator
    torch = pytest.importorskip("torch")

    class ModelFixture:
        calls = 0
        generation_config = {"eos_token_id": 2}

        def eval(self):
            return self

        def generate(self, **kwargs):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("next node failed")
            return torch.tensor([[11, 12, 21, 2]])

    loaded = LoadedGenerator(ModelFixture(), TokenizerFixture(), architecture="causal",
                             device="cpu", decode_parameters={})
    wrapper = NodeCheckpointGenerator(loaded, tmp_path, {}, time.monotonic() + 60)
    batch = Budget("causal", 4, 2).prepare([11, 12], lambda ids, stage: ids, "map")
    wrapper.set_node_context({"layer": 0, "node": 0})
    assert wrapper(batch, 2, "map") == "21 2"
    assert loaded.last_receipt["generated_native_tokens"] == 2
    wrapper.set_node_context({"layer": 0, "node": 1})
    with pytest.raises(RuntimeError, match="next node failed"):
        wrapper(batch, 2, "map")
    assert loaded.last_receipt is None
    assert wrapper.events[-1]["status"] == "failed"
    assert wrapper.events[-1]["backend_receipt"] is None
    assert wrapper.events[0]["backend_receipt"]["generated_native_tokens"] == 2


def test_profiles_match_exact_five_candidate_ids_and_no_T4_admission():
    root = Path(__file__).resolve().parents[1]
    profiles = json.loads((root / "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/candidate_profiles.json").read_text())
    current = json.loads((root / "experiments/registry/models/tib-summarization-pipelines-v1.json").read_text())
    assert [p["candidate_id"] for p in profiles["pipelines"]] == [p["candidate_id"] for p in current["pipelines"]]
    assert profiles["T4_verified"] is profiles["runtime_admission"] is False
    assert all(p["runtime_admitted"] is False for p in profiles["pipelines"])


def test_chat_scaffolding_preserves_byte_fragment_ids_without_decoding():
    class ChatFixture:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["tokenize"] is False
            return "PREFIX" + messages[1]["content"] + "SUFFIX"

        def encode(self, text, **kwargs):
            return [ord(value) for value in text]

        def decode(self, *args, **kwargs):
            raise AssertionError("Never decode a source-token fragment")

    wrap = causal_chat_wrapper(ChatFixture(), {"map": "instruction"})
    for fragment in ([56252], [253], [247], [378], [235]):
        prefix, suffix = wrap.scaffold_ids["map"]
        assert wrap(fragment, "map") == prefix + fragment + suffix


def test_actual_qwen_unicode_split_native_ids_preserved_offline():
    root = Path(__file__).resolve().parents[1]
    tokenizer_path = root / "research-data/tib-qualification-261019-1703/tokenizers/qwen3"
    if not tokenizer_path.exists():
        pytest.skip("Optional pinned local tokenizer assets unavailable")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True, use_fast=True)
    ids = tokenizer.encode("\U0001d7d9", add_special_tokens=False)
    assert len(ids) > 1
    wrap = causal_chat_wrapper(tokenizer, {"map": "Summarize."})
    prefix, suffix = wrap.scaffold_ids["map"]
    assert any("\ufffd" in tokenizer.decode([value]) for value in ids)
    for value in ids:
        assert wrap([value], "map") == prefix + [value] + suffix
