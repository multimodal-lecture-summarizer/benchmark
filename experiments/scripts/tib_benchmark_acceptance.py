"""Prospective technical acceptance: warnings retain outputs, never trigger retry."""
from .tib_benchmark_generation_telemetry import text_diagnostics

POLICY_VERSION = "tib-intermediate-acceptance-v1"
ACCEPTANCE_POLICY = {
    "version": POLICY_VERSION,
    "scope": "prospective; do not rewrite historical raw statuses",
    "usable_text": "decoded string containing at least one Unicode letter or number",
    "warnings": ["no_terminal_eos", "token_budget_exhausted", "output_reserve_reached",
                 "possible_forced_terminal_eos", "repetition", "sentence_ending"],
    "warning_effect": "retain valid output and denominator; no automatic retry",
    "quality_claim": "automatic flags do not establish factuality or semantic coverage",
}


def _usable(text):
    return isinstance(text, str) and any(character.isalnum() for character in text)


def _integer(value):
    return type(value) is int and value >= 0


def _ids(value):
    return isinstance(value, (list, tuple)) and bool(value) and all(_integer(x) for x in value)


def _decision(errors, warnings):
    return {"policy_version": POLICY_VERSION,
            "status": "failed" if errors else "completed_with_warning" if warnings else "completed",
            "technical_errors": errors, "warnings": list(dict.fromkeys(warnings)),
            "usable_output": not bool(errors), "retain_in_denominator": True,
            "automatic_retry": False, "factuality_verified": False}


def node_acceptance(text, native, technical_error=None, technical_valid=True):
    """Validate telemetry and classify a node without references or score inputs."""
    errors, warnings = [], []
    if technical_valid is not True:
        errors.append("external_technical_validation_failed")
    if technical_error is not None:
        errors.append("generation_technical_error")
    if not _usable(text):
        errors.append("empty_or_unusable_decoded_output")
    if not isinstance(native, dict):
        return _decision(errors + ["missing_native_telemetry"], warnings)
    config = native.get("effective_generation_config")
    if native.get("generation_config_complete") is not True or not isinstance(config, dict):
        return _decision(errors + ["incomplete_generation_config"], warnings)
    generated, count = native.get("generated_ids"), native.get("generated_native_tokens")
    reserve, eos_ids = config.get("max_new_tokens"), native.get("valid_eos_token_ids")
    if not _ids(generated) or not _integer(count) or count != len(generated):
        errors.append("invalid_native_token_ids_or_count")
    if not _integer(reserve) or reserve == 0 or (_integer(count) and count > reserve):
        errors.append("invalid_or_exceeded_native_reserve")
    if not _ids(eos_ids):
        errors.append("missing_valid_eos_ids")
    configured_eos = config.get("eos_token_id")
    if configured_eos is not None:
        configured_eos = [configured_eos] if _integer(configured_eos) else configured_eos
        if not _ids(configured_eos) or not _ids(eos_ids) or set(configured_eos) != set(eos_ids):
            errors.append("configured_eos_ids_mismatch")
    if errors:
        return _decision(errors, warnings)
    eos, reached = generated[-1] in eos_ids, count == reserve
    exhausted = reached and not eos
    forced = config.get("forced_eos_token_id")
    forced_ids = [forced] if _integer(forced) else forced if isinstance(forced, (list, tuple)) else []
    possible_forced = bool(eos and reached and generated[-1] in forced_ids)
    expected = {"eos_observed": eos, "output_reserve_reached": reached,
                "token_budget_exhausted": exhausted,
                "terminal_eos_is_forced_candidate": possible_forced}
    diagnostics = text_diagnostics(text)
    expected.update({key: diagnostics[key] for key in ("repetition_flag", "sentence_completion_flag")})
    for key, value in expected.items():
        if type(native.get(key)) is not bool or native[key] is not value:
            errors.append("inconsistent_or_missing_" + key)
    if not eos:
        warnings.append("no_terminal_eos")
    for flag, warning in ((exhausted, "token_budget_exhausted"), (reached, "output_reserve_reached"),
                          (possible_forced, "possible_forced_terminal_eos"),
                          (diagnostics["repetition_flag"], "repetition"),
                          (diagnostics["sentence_completion_flag"], "sentence_ending")):
        if flag:
            warnings.append(warning)
    return _decision(errors, warnings)


def record_acceptance(node_decisions, delivered, word_cap=350, technical_valid=True):
    """Union node failures and warnings; delivered text must meet the shared cap."""
    errors, warnings = [], []
    if technical_valid is not True:
        errors.append("external_technical_validation_failed")
    if not _usable(delivered):
        errors.append("empty_or_unusable_delivered_output")
    if not _integer(word_cap) or word_cap == 0:
        errors.append("invalid_word_cap")
    elif isinstance(delivered, str) and len(delivered.split()) > word_cap:
        errors.append("delivered_word_cap_exceeded")
    if not isinstance(node_decisions, (list, tuple)) or not node_decisions:
        errors.append("missing_node_decisions")
    else:
        for decision in node_decisions:
            if (not isinstance(decision, dict) or decision.get("policy_version") != POLICY_VERSION
                    or decision.get("status") not in {"completed", "completed_with_warning"}):
                errors.append("failed_or_invalid_node")
                continue
            reasons = decision.get("warnings")
            if not isinstance(reasons, list) or not all(isinstance(x, str) for x in reasons):
                errors.append("invalid_node_warning_telemetry")
            else:
                warnings.extend(reasons)
                if decision["status"] == "completed_with_warning" and not reasons:
                    errors.append("warning_node_missing_warning_reason")
    return _decision(errors, warnings)
