"""Cap350 receipt logic on a miniature evidence ZIP, and admission constants against the declared P4 contract."""
import json
import zipfile

import pytest

from experiments.scripts import tib_selection300_admission as admission
from experiments.scripts import tib_selection300_binding as binding


def make_zip(path, *, capped=0, forced=0, lexrank_capped=0):
    with zipfile.ZipFile(path, "w") as z:
        for profile in binding.PROFILE_ORDER:
            records = {}
            for i, stratum in enumerate(("short", "medium", "long")):
                is_lex = profile == "lexrank"
                records[f"valid:{i}"] = {
                    "status": "completed", "source_stratum": stratum,
                    "result": {"delivery": {"raw_words": 40 + i, "delivered_words": 40 + i,
                                            "capped": (lexrank_capped if is_lex else capped) and i == 0,
                                            "forced_word_boundary": bool(forced) and profile == "bart" and i == 0}},
                    "validation": {"acceptance": {"warnings": []}}}
            records["valid:9"] = {"status": "failed", "source_stratum": "long"}
            z.writestr(f"pilot/{profile}/candidate_receipt.json", json.dumps({"records": records}))


def receipt(tmp_path, **kw):
    path = tmp_path / "e.zip"
    make_zip(path, **kw)
    return admission.build_cap_receipt(path, binding.sha256_file(path))


def test_clean_pilot_allows_lock_and_ignores_failed_cells(tmp_path):
    r = receipt(tmp_path)
    assert r["cap_lock_allowed"] and r["usable_outputs"] == 12
    assert r["by_profile_stratum"]["bart|long"]["raw_words"]["max"] == 42


def test_forced_word_cut_blocks_the_lock(tmp_path):
    assert receipt(tmp_path, forced=1)["cap_lock_allowed"] is False


def test_capping_a_non_lexrank_profile_blocks_but_lexrank_reaching_cap_does_not(tmp_path):
    assert receipt(tmp_path, capped=1)["cap_lock_allowed"] is False
    assert receipt(tmp_path, lexrank_capped=1)["cap_lock_allowed"] is True


def test_changed_evidence_hash_is_rejected(tmp_path):
    path = tmp_path / "e.zip"
    make_zip(path)
    with pytest.raises(ValueError, match="hash changed"):
        admission.build_cap_receipt(path, "0" * 64)


def test_admission_constants_match_declared_contract():
    rules = admission.build_admission_rules()
    assert rules["ratified"] is False and rules["selection_start_authorized"] is False
    assert (rules["config_coverage"]["overall_min"], rules["config_coverage"]["per_stratum_min"]) == (0.95, 0.90)
    assert rules["common_coverage"]["overall_min"] == 0.90 and rules["common_coverage"]["per_stratum_min"] == 0.80
    assert rules["common_coverage"]["common_n_min"] == 180 and rules["common_coverage"]["per_nonempty_stratum_n_min"] == 20
    assert rules["tier_b"]["leader_margin_rouge_l_min"] == 0.01 and rules["tier_b"]["lead3_guard_delta_min"] == 0.0
    assert rules["K_models"] == 3 and rules["K_total"] == 4 and rules["max_paired_contrasts"] == 6
    assert rules["validation_set"]["selection_n"] == 300
    assert rules["validation_set"]["quotas"] == {"short": 100, "medium": 90, "long": 110}


def test_output_policy_v2_keeps_cap_and_old_file_hash():
    policy = admission.build_output_policy_v2("a" * 64)
    assert policy["derived_global_word_cap"] == 350 and policy["state"] == "locked_before_selection"
    assert policy["supersedes_state_of"]["sha256"] == binding.sha256_file(admission.OLD_POLICY)
    assert policy["validation_or_test_references_used_for_cap"] is False


def test_thresholds_appear_in_the_declared_p4_contract_text():
    """Compare the encoded constants with the prose of the pre-declared selection contract."""
    path = binding.ROOT.parent / "plans/261019-0035-summarization-model-benchmark/phase-04-candidate-selection-and-t4-benchmark-protocol.md"
    text = path.read_text(encoding="utf-8")
    for phrase in ("scored coverage≥95% overall và≥90% mỗi", "≥90% overall,≥80% mỗi", "commonN≥180 và≥20 mỗi",
                   "hơn mỗi rival model representative≥0.01 absolute ROUGE-L", "delta≥0"):
        assert phrase in text, phrase


def test_rules_state_control_coverage_stratum_direction_and_family_failure():
    rules = admission.build_admission_rules()
    assert "lead3" in " ".join(rules["config_coverage"]["applies_to"])
    assert "no_selection" in rules["stratum_direction"] and "not representative" in rules["tier_a_failure"]
