from types import SimpleNamespace
import time

from experiments.scripts.tib_benchmark_generation_telemetry import (
    configuration_receipt, generation_receipt, text_diagnostics,
)
from experiments.scripts.tib_benchmark_checkpoint import NodeCheckpointGenerator


def receipt(ids, maximum=4, eos=(2, 3)):
    model = SimpleNamespace(generation_config={"eos_token_id": list(eos), "num_beams": 4})
    return generation_receipt(model, SimpleNamespace(), {}, ids, maximum, "Notes.")


def test_terminal_eos_and_exhaustion_are_separate():
    assert receipt([7, 8, 9, 2])["eos_observed"] is True
    assert receipt([7, 8, 9, 2])["token_budget_exhausted"] is False
    assert receipt([7, 8, 9, 3])["eos_observed"] is True
    assert receipt([2, 8, 9, 7])["eos_observed"] is False
    assert receipt([2, 8, 9, 7])["token_budget_exhausted"] is True
    assert receipt([7, 8])["token_budget_exhausted"] is False


def test_eos_at_reserve_does_not_certify_natural_completion():
    model = SimpleNamespace(generation_config={"eos_token_id": 2, "forced_eos_token_id": 2})
    result = generation_receipt(model, object(), {}, [7, 8, 9, 2], 4, "Notes.")
    assert result["eos_observed"] is True
    assert result["token_budget_exhausted"] is False
    assert result["output_reserve_reached"] is True
    assert result["terminal_eos_is_forced_candidate"] is True
    assert result["natural_completion_verified"] is False
    short = generation_receipt(model, object(), {}, [7, 2], 4, "Notes.")
    assert short["output_reserve_reached"] is False
    assert short["terminal_eos_is_forced_candidate"] is False
    assert short["natural_completion_verified"] is False


def test_explicit_overrides_and_stage_budget_win_without_mutating_model():
    base = {"num_beams": 4, "max_new_tokens": 12, "eos_token_id": 2,
            "forced_eos_token_id": 2, "length_penalty": 2.0}
    model = SimpleNamespace(generation_config=SimpleNamespace(to_dict=lambda: base))
    result = configuration_receipt(model, {"num_beams": 1, "length_penalty": 1.0}, 384)
    assert result["base_generation_config"] == base
    assert result["effective_generation_config"]["max_new_tokens"] == 384
    assert result["effective_generation_config"]["num_beams"] == 1
    assert result["effective_generation_config"]["length_penalty"] == 1.0
    assert result["effective_generation_config"]["forced_eos_token_id"] == 2
    assert base["num_beams"] == 4 and base["max_new_tokens"] == 12
    assert result["generation_config_complete"] is True
    assert result["generation_internal_adjustments_observed"] is False


def test_missing_config_and_eos_are_honestly_unknown():
    result = generation_receipt(object(), object(), {}, [1, 4], 2, "Notes")
    assert result["base_generation_config"] is None
    assert result["generation_config_complete"] is False
    assert result["eos_observed"] is None
    assert result["token_budget_exhausted"] is None
    assert result["valid_eos_token_ids"] is None
    inferred = generation_receipt(object(), SimpleNamespace(eos_token_id=4), {}, [1, 4], 2, "Notes")
    assert inferred["eos_observed"] is True
    assert "inferred" in inferred["eos_token_ids_provenance"]


def test_repetition_and_sentence_heuristics_do_not_claim_quality():
    repeated = text_diagnostics("The role of women in open source. " * 3)
    assert repeated["repetition_flag"] is True
    assert repeated["sentence_completion_flag"] is False
    assert repeated["automatic_flags_are_quality_proof"] is False
    assert text_diagnostics("A unique complete sentence.")["repetition_flag"] is False
    assert text_diagnostics("A fragment ending in the")["sentence_completion_flag"] is True
    assert text_diagnostics('He said, “Done.”')["sentence_completion_flag"] is False


def test_resume_restores_saved_telemetry_without_doublecounting(tmp_path):
    class Backend:
        calls = 0
        last_receipt = None

        def __call__(self, batch, maximum, stage):
            self.calls += 1
            self.last_receipt = receipt([7, 8, 9, 2])
            return "Notes."

    backend = Backend()
    fresh = NodeCheckpointGenerator(backend, tmp_path, {"profile": "telemetry"}, time.monotonic() + 60)
    fresh.set_node_context({"layer": 0, "node": 0})
    fresh({"input_ids": [1]}, 4, "map")
    resumed = NodeCheckpointGenerator(backend, tmp_path, {"profile": "telemetry"}, time.monotonic() + 60)
    resumed.set_node_context({"layer": 0, "node": 0})
    assert resumed({"input_ids": [1]}, 4, "map") == "Notes."
    event = resumed.events[0]
    assert backend.calls == 1
    assert event["backend_receipt"] == fresh.events[0]["backend_receipt"]
    assert event["new_attempt_wall_seconds"] == 0
    assert event["original_wall_seconds"] == fresh.events[0]["new_attempt_wall_seconds"]
