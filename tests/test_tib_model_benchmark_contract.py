"""Guard the five-pipeline and pre-outcome reference contracts offline."""

import json

import pytest

from experiments.scripts.tib_model_benchmark_contract import (
    comparison_contract, load_registry, reference_disposition,
)


def test_all_comparison_masks_and_resources_share_five_ids():
    registry = load_registry()
    contract = comparison_contract(registry)
    assert len(contract["candidate_ids"]) == 5
    assert len(contract["paired_contrasts"]) == 10
    assert contract["candidate_ids"] == contract["between_family_candidate_ids"]
    assert set(contract["generation_devices"]) == set(contract["candidate_ids"])
    assert "lead3" not in contract["recommendation_ids"]
    assert "lead3" not in contract["config_selection_family_ids"]
    assert len(contract["recommendation_ids"]) == 4
    assert sum("lead3" in pair for pair in contract["paired_contrasts"]) == 4
    assert registry["global_output_word_cap"] is None
    assert registry["profile_revisions"] is None
    assert registry["scorer_ready_receipt"] is None


@pytest.mark.parametrize("change", ["missing_control", "duplicate_id", "tuned_control", "timestamps"])
def test_registry_rejects_inconsistent_control_or_input(tmp_path, change):
    registry = load_registry()
    if change == "missing_control":
        registry["pipelines"].pop(0)
    elif change == "duplicate_id":
        registry["pipelines"][1]["candidate_id"] = "lead3"
    elif change == "tuned_control":
        registry["pipelines"][0]["config_search"] = True
    else:
        registry["prompt_timestamps"] = True
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)


def test_short_unreviewed_reference_is_flagged_but_eligible_not_c():
    row = reference_disposition("A brief abstract", rights_pass=True, structure_pass=True)
    assert row["reference_usability"] == "B"
    assert row["eligibility_status"] == "flagged"
    assert row["primary_eligible"] is True
    assert row["reference_policy_state"] == "proposed_uncalibrated"


def test_uncertain_reference_cannot_bypass_rights_or_structure_hold():
    for rights, structure in ((False, True), (True, False), (False, False)):
        row = reference_disposition("An abstract", rights_pass=rights, structure_pass=structure)
        assert row["reference_usability"] == "B"
        assert row["eligibility_status"] == "HOLD"
        assert row["primary_eligible"] is False


@pytest.mark.parametrize("rights,structure", [("HOLD", "FAIL"), (1, True), (True, None)])
def test_truthy_or_unknown_values_cannot_bypass_gate(rights, structure):
    with pytest.raises(ValueError, match="explicit booleans"):
        reference_disposition("An abstract", rights_pass=rights, structure_pass=structure)


def test_empty_is_c_but_nonempty_a_or_c_requires_review_evidence():
    empty = reference_disposition(" \n", rights_pass=True, structure_pass=True)
    assert empty["reference_usability"] == "C"
    assert empty["primary_eligible"] is False
    for label in ("A", "C"):
        with pytest.raises(ValueError, match="evidence"):
            reference_disposition("An abstract", label=label)
    reviewed = reference_disposition("An abstract", label="C", evidence="review:wrong_record",
                                     rights_pass=True, structure_pass=True)
    assert reviewed["eligibility_status"] == "excluded"
    # Model outcomes have no accepted input in the policy decision API.
    with pytest.raises(TypeError):
        reference_disposition("An abstract", rouge=0.01)
