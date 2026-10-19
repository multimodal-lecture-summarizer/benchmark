"""Descriptive generation telemetry; these flags never certify summary quality."""
from collections import Counter
from copy import deepcopy
import re


QUALITY_RULE_SPEC = {
    "version": "p41-generation-diagnostics-v1",
    "word_regex": r"\b\w+\b",
    "normalization": "unicode_casefold",
    "ngram_size": 4,
    "repetition_count_threshold": 3,
    "repetition_rule": "casefold_unicode_word_4gram_count_gte_3_v1",
    "sentence_completion_rule": "flag_missing_terminal_sentence_punctuation_v1",
    "eos_observed_rule": "last_generated_token_is_valid_eos",
    "token_budget_exhausted_rule": "generated_count_equals_reserve_and_no_terminal_eos",
    "forced_eos_rule": "at_reserve_and_last_token_in_configured_forced_eos_ids_is_candidate_only",
    "acceptance_effect": "diagnostic_only_no_retry_or_rejection",
}


def configuration_receipt(model, decode_parameters, max_new_tokens):
    """Record supplied configuration without claiming access to generate internals."""
    configuration = getattr(model, "generation_config", None)
    if hasattr(configuration, "to_dict"):
        base = deepcopy(configuration.to_dict())
    elif isinstance(configuration, dict):
        base = deepcopy(configuration)
    else:
        base = None
    overrides = {**deepcopy(decode_parameters), "max_new_tokens": max_new_tokens}
    return {
        "base_generation_config": base,
        "explicit_generation_overrides": overrides,
        "effective_generation_config": {**(base or {}), **overrides},
        "generation_config_complete": base is not None,
        "effective_generation_config_provenance": "base_plus_explicit_overrides",
        "generation_internal_adjustments_observed": False,
        "generation_internal_adjustments_note": (
            "generate may derive max_length, special-token fallbacks or other internal "
            "values; these are not observed by this receipt"),
    }


def text_diagnostics(text):
    """Fixed rules applied to decoded output, never used for acceptance/retry."""
    words = re.findall(r"\b\w+\b", text.casefold())
    counts = Counter(tuple(words[i:i + 4]) for i in range(max(0, len(words) - 3)))
    maximum = max(counts.values(), default=0)
    # This intentionally flags an end without sentence punctuation, not a
    # grammatical verdict: abbreviations/fragments can fool either direction.
    terminal = text.rstrip().rstrip('"\'”’)]}').rstrip()
    incomplete = bool(terminal) and terminal[-1] not in ".!?…"
    return {
        "repetition_flag": maximum >= 3,
        "repetition_rule": QUALITY_RULE_SPEC["repetition_rule"],
        "maximum_repeated_4gram_count": maximum,
        "sentence_completion_flag": incomplete,
        "sentence_completion_rule": QUALITY_RULE_SPEC["sentence_completion_rule"],
        "automatic_flags_are_quality_proof": False,
    }


def generation_receipt(model, tokenizer, decode_parameters, generated, maximum, text):
    receipt = configuration_receipt(model, decode_parameters, maximum)
    config = receipt["effective_generation_config"]
    eos = config.get("eos_token_id")
    provenance = "merged_generation_config"
    if eos is None:
        eos = getattr(tokenizer, "eos_token_id", None)
        provenance = "tokenizer_fallback_inferred_not_generate_observed"
    eos_ids = ([eos] if isinstance(eos, int) else list(eos)
               if isinstance(eos, (list, tuple)) else [])
    valid = [value for value in eos_ids if isinstance(value, int) and value >= 0]
    terminal_eos = (bool(generated) and generated[-1] in valid) if valid else None
    forced = config.get("forced_eos_token_id")
    forced_ids = ([forced] if isinstance(forced, int) else list(forced)
                  if isinstance(forced, (list, tuple)) else [])
    reached = len(generated) == maximum
    forced_candidate = bool(reached and generated and generated[-1] in forced_ids)
    receipt.update({
        "valid_eos_token_ids": valid or None,
        "eos_token_ids_provenance": provenance if valid else "unknown",
        "eos_observed": terminal_eos,
        "eos_observed_rule": QUALITY_RULE_SPEC["eos_observed_rule"],
        "output_reserve_reached": reached,
        "terminal_eos_is_forced_candidate": (forced_candidate if terminal_eos else False)
            if receipt["generation_config_complete"] and terminal_eos is not None else None,
        "forced_eos_provenance_note": (
            "Configured forced EOS at the reserve is only a candidate explanation; "
            "the actual stopping mechanism and natural completion are unobserved"),
        "natural_completion_verified": False,
        "token_budget_exhausted": (len(generated) == maximum and not terminal_eos)
            if terminal_eos is not None else None,
    })
    receipt.update(text_diagnostics(text))
    return receipt
