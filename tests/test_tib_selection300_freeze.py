"""Decision recording and readiness gates; the receipt can never authorize a start."""
import json

import pytest

from experiments.scripts import tib_selection300_freeze as freeze

GOOD = {"D1": "ratify_verbatim", "D2": "report_all_three_views", "D3": "exclude_minicheck", "D4": "freeze_v2"}


def test_decisions_must_cover_all_four_with_allowed_values(tmp_path):
    with pytest.raises(ValueError, match="D1-D4"):
        freeze.record_decisions({"D1": "ratify_verbatim"}, tmp_path)
    with pytest.raises(ValueError, match="D1-D4"):
        freeze.record_decisions({**GOOD, "D2": "whatever"}, tmp_path)


@pytest.mark.parametrize("key,value", [("D1", "change_post_hoc"), ("D3", "include_minicheck"), ("D4", "not_frozen")])
def test_answers_that_reopen_thresholds_budget_or_scorer_are_refused(tmp_path, key, value):
    with pytest.raises(ValueError, match="re-plan"):
        freeze.record_decisions({**GOOD, key: value}, tmp_path)


def test_record_keeps_start_unauthorized_and_notes_the_non_default_view_choice(tmp_path):
    record = freeze.record_decisions(GOOD, tmp_path)
    assert record["selection_start_authorized"] is False and record["post_hoc"]["D1"] is False
    assert "all three views" in record["note_D2"]
    assert json.loads((tmp_path / "decisions_261023_v1.json").read_text())["answers"] == GOOD


def test_view_policy_encodes_only_the_chosen_policy():
    policy = freeze.build_view_policy(GOOD)
    assert policy["budgets_words"] == {"S": 60, "M": 120, "L": 240} and policy["selection_start_authorized"] is False
    with pytest.raises(ValueError):
        freeze.build_view_policy({**GOOD, "D2": "report_changing_views_only"})


def test_empty_registry_has_no_binding_gate_passing_and_start_stays_unauthorized(tmp_path):
    receipt = freeze.build_readiness_receipt(tmp_path)
    assert receipt["binding_gates_pass"] is False and receipt["selection_start_authorized"] is False
    assert all(g["status"] == "OPEN" for g in receipt["gates"].values())


def test_real_receipt_passes_binding_gates_but_leaves_runtime_gates_open():
    path = freeze.REGISTRY / "selection300_readiness_receipt.json"
    if not path.exists():
        pytest.skip("receipt not built")
    receipt = json.loads(path.read_text())
    assert receipt["binding_gates_pass"] is True and receipt["selection_start_authorized"] is False
    assert set(receipt["blocking_open_gates"]) == set(freeze.OPEN_GATES)


def test_no_registry_artifact_authorizes_a_start():
    for path in freeze.REGISTRY.glob("*.json"):
        data = json.loads(path.read_text())
        assert data.get("selection_start_authorized", False) is False, path.name


def test_changing_views_only_answer_is_refused_before_anything_is_written(tmp_path):
    with pytest.raises(ValueError, match="re-plan"):
        freeze.build_all({**GOOD, "D2": "report_changing_views_only"}, tmp_path)
    assert list(tmp_path.iterdir()) == []


def _copy_registry(tmp_path):
    import shutil
    dest = tmp_path / "registry"
    shutil.copytree(freeze.REGISTRY, dest)
    return dest


def _needs_built_registry():
    if not (freeze.REGISTRY / "selection300_readiness_receipt.json").exists():
        pytest.skip("registry not built")


def test_stale_admission_v2_or_edited_freeze_turns_its_gate_open(tmp_path):
    _needs_built_registry()
    registry = _copy_registry(tmp_path)
    assert freeze.build_readiness_receipt(registry)["binding_gates_pass"] is True
    rules = json.loads((registry / "admission_rules_v1.json").read_text())
    rules["note"] = "edited after v2 was built"
    (registry / "admission_rules_v1.json").write_text(json.dumps(rules))
    assert freeze.build_readiness_receipt(registry)["gates"]["admission_rules_ratified"]["status"] == "OPEN"


def test_hand_edited_scorer_freeze_turns_its_gate_open(tmp_path):
    _needs_built_registry()
    registry = _copy_registry(tmp_path)
    data = json.loads((registry / "scorer_freeze_receipt.json").read_text())
    data["runtime_amendments"]["p4b_sha256"] = "0" * 64
    (registry / "scorer_freeze_receipt.json").write_text(json.dumps(data))
    assert freeze.build_readiness_receipt(registry)["gates"]["scorer_frozen"]["status"] == "OPEN"


def test_changed_profile_list_invalidates_the_allocation_gate(tmp_path):
    _needs_built_registry()
    registry = _copy_registry(tmp_path)
    data = json.loads((registry / "selection300_profiles_v2.json").read_text())
    data["note"] = "changed"
    (registry / "selection300_profiles_v2.json").write_text(json.dumps(data))
    assert freeze.build_readiness_receipt(registry)["gates"]["allocations_selection300_final523"]["status"] == "OPEN"
