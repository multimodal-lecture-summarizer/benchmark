from copy import deepcopy
from types import SimpleNamespace

import pytest

from experiments.scripts.tib_benchmark_acceptance import (
    POLICY_VERSION, node_acceptance, record_acceptance,
)
from experiments.scripts.tib_benchmark_generation_telemetry import generation_receipt


def native(text="Notes.", ids=(7, 2), reserve=4, forced=None):
    model = SimpleNamespace(generation_config={"eos_token_id": 2, "forced_eos_token_id": forced})
    result = generation_receipt(model, object(), {}, list(ids), reserve, text)
    result.update(generated_ids=list(ids), generated_native_tokens=len(ids))
    return result


def test_clean_terminal_eos_below_cap_completed():
    result = node_acceptance("Notes.", native())
    assert result["status"] == "completed"
    assert result["policy_version"] == POLICY_VERSION
    assert result["warnings"] == []


def test_eos_exact_cap_is_warning_not_token_exhaustion():
    result = node_acceptance("Notes.", native(ids=(7, 8, 9, 2), forced=2))
    assert result["status"] == "completed_with_warning"
    assert "output_reserve_reached" in result["warnings"]
    assert "possible_forced_terminal_eos" in result["warnings"]
    assert "token_budget_exhausted" not in result["warnings"]
    assert result["usable_output"] is True


@pytest.mark.parametrize("ids,exhausted", [((7, 8, 9, 10), True), ((7, 8), False)])
def test_no_eos_retains_usable_output_and_denominator(ids, exhausted):
    result = node_acceptance("Useful notes.", native("Useful notes.", ids))
    assert result["status"] == "completed_with_warning"
    assert "no_terminal_eos" in result["warnings"]
    assert ("token_budget_exhausted" in result["warnings"]) is exhausted
    assert result["usable_output"] is result["retain_in_denominator"] is True
    assert result["automatic_retry"] is False


@pytest.mark.parametrize("text", ["", "   ", "\x00\x01\n", "... !!!"])
def test_empty_control_or_punctuation_only_output_failed(text):
    assert node_acceptance(text, native(text))["status"] == "failed"


def test_unicode_letter_and_number_are_technically_usable():
    for text in ("Ý.", "研究。", "٣."):
        assert node_acceptance(text, native(text))["usable_output"] is True


@pytest.mark.parametrize("updates", [
    {"generated_ids": [-1, 2]}, {"generated_ids": [True, 2]},
    {"generated_ids": []}, {"generated_native_tokens": 3},
    {"generation_config_complete": False}, {"valid_eos_token_ids": None},
    {"eos_observed": False}, {"output_reserve_reached": True},
    {"token_budget_exhausted": True}, {"repetition_flag": True},
    {"sentence_completion_flag": True}, {"terminal_eos_is_forced_candidate": True},
])
def test_invalid_or_inconsistent_native_telemetry_failed(updates):
    value = native()
    value.update(updates)
    assert node_acceptance("Notes.", value)["status"] == "failed"


def test_missing_legacy_telemetry_and_reserve_overflow_fail_prospective_only():
    legacy = {"generated_ids": [7, 2], "generated_native_tokens": 2}
    unchanged = deepcopy(legacy)
    assert node_acceptance("Notes.", legacy)["status"] == "failed"
    assert legacy == unchanged
    overflow = native(ids=(7, 8, 9, 2))
    overflow["effective_generation_config"]["max_new_tokens"] = 3
    assert node_acceptance("Notes.", overflow)["status"] == "failed"


def test_repetition_and_sentence_flags_warn_without_quality_rejection():
    text = "The role of women in open source. " * 3 + "A fragment"
    result = node_acceptance(text, native(text))
    assert result["status"] == "completed_with_warning"
    assert "repetition" in result["warnings"]
    assert "sentence_ending" in result["warnings"]
    assert result["factuality_verified"] is False


def test_external_context_hash_lineage_error_or_backend_error_fail_closed():
    assert node_acceptance("Notes.", native(), technical_valid=False)["status"] == "failed"
    assert node_acceptance("Notes.", native(), technical_error="CUDA OOM")["status"] == "failed"


def test_record_failure_union_and_warning_union_and_global_word_cap():
    clean = node_acceptance("Notes.", native())
    warning = node_acceptance("Notes.", native(ids=(7, 8)))
    failed = node_acceptance("", native(""))
    assert record_acceptance([clean], "Final summary.")["status"] == "completed"
    result = record_acceptance([clean, warning], "Final summary.")
    assert result["status"] == "completed_with_warning"
    assert result["warnings"] == warning["warnings"]
    assert record_acceptance([clean, failed], "Final.")["status"] == "failed"
    assert record_acceptance([clean], "word " * 350)["status"] == "completed"
    assert record_acceptance([clean], "word " * 351)["status"] == "failed"
    for decisions, delivered in (([], "Final."), ([clean], ""), ([clean], "\x00")):
        assert record_acceptance(decisions, delivered)["status"] == "failed"
    assert record_acceptance([clean], "Final.", technical_valid=False)["status"] == "failed"


def test_semantic_diagnostic_does_not_auto_fail_and_no_reference_score_predicate():
    value = native()
    value["semantic_coverage_review"] = "possible first-map semantic clone"
    result = node_acceptance("Notes.", value)
    assert result["status"] == "completed"
    # Acceptance consumes technical artifacts only; original receipt stays intact.
    assert value["semantic_coverage_review"] == "possible first-map semantic clone"
