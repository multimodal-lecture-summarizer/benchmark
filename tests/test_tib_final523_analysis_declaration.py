"""The final523 analysis declaration stays bound to the files it was written against and consistent with the ratified rules."""
import hashlib
import json
from pathlib import Path

import pytest

PROTOCOLS = Path(__file__).resolve().parents[1] / "experiments" / "registry" / "protocols"
FOLDER = PROTOCOLS / "tib-final523-analysis-261024-v1"
DECLARATION = FOLDER / "analysis_declarations_final523_261024_v1.json"
DECISIONS = FOLDER / "final523_use_decisions_261024_v1.json"
RECEIPT = FOLDER / "final523_analysis_declaration_receipt.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_bound_files_are_unchanged():
    decl = load(DECLARATION)
    assert set(decl["bound_hashes"]) == set(decl["bound_paths_relative_to_protocols_dir"])
    for key, relative in decl["bound_paths_relative_to_protocols_dir"].items():
        assert sha(PROTOCOLS / relative) == decl["bound_hashes"][key], key


def test_receipt_pins_both_files():
    receipt = load(RECEIPT)
    assert receipt["declaration_sha256"] == sha(DECLARATION)
    assert receipt["use_decisions_sha256"] == sha(DECISIONS)


def test_thresholds_equal_the_ratified_rules():
    decl, rules = load(DECLARATION), load(PROTOCOLS / "tib-selection300-binding-261023-v1" / "admission_rules_v2.json")
    floors = decl["declarations"]["3_populations_and_missing_cells"]["floors"]
    assert f"coverage >= {rules['config_coverage']['overall_min']} overall" in floors
    assert f"{rules['config_coverage']['per_stratum_min']:.2f} per stratum" in floors
    assert f">= {rules['common_coverage']['overall_min']:.2f} of 523" in floors
    assert f">= {rules['common_coverage']['per_stratum_min']:.2f} per stratum" in floors
    assert f"|C_final| >= {rules['common_coverage']['common_n_min']}" in floors
    assert f">= {rules['common_coverage']['per_nonempty_stratum_n_min']} members" in floors
    assert f">= {rules['tier_b']['leader_margin_rouge_l_min']} (the selection300 margin)" in \
        decl["declarations"]["5_reported_but_not_gating"]["practical_margin"]
    assert sorted(decl["profiles"]["rivals"] + [decl["profiles"]["leader"], decl["profiles"]["control"]]) == sorted(rules["families"] + [rules["fixed_control"]])


def test_leader_is_the_locked_choice():
    decl = load(DECLARATION)
    contract = load(PROTOCOLS / "tib-final523-generation-261024-v1" / "selection_contract.json")
    assert decl["locked_choice"]["selected_profile_id"] == contract["locked_choice"]["selected_profile_id"]
    assert decl["profiles"]["candidate_to_profile_id"][decl["profiles"]["leader"]] == decl["locked_choice"]["selected_profile_id"]


@pytest.mark.parametrize("path", [DECLARATION, DECISIONS])
def test_nothing_is_authorised(path):
    doc = load(path)
    assert doc["final_test_authorized"] is False and doc["selection_start_authorized"] is False
    assert doc["post_hoc"] is False
