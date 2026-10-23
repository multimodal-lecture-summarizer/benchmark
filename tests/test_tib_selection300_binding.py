"""Profile list and allocation checks against the pinned Pilot40 evidence and the measured projection."""
import copy
import json

import pytest

from experiments.scripts import tib_selection300_binding as binding

pytestmark = pytest.mark.skipif(not binding.EVIDENCE_ZIP.exists(), reason="private Pilot40 evidence not present")


@pytest.fixture(scope="module")
def profile_list():
    return binding.build_profile_list()


@pytest.fixture(scope="module")
def outcome():
    return json.loads(binding.SCORING_OUTCOME.read_text(encoding="utf-8"))


def test_exactly_four_profiles_without_qwen3(profile_list):
    ids = [p["candidate_id"] for p in profile_list["profiles"]]
    assert ids == ["lead3", "lexrank", "bart", "led"] and "qwen3" in profile_list["excluded"]
    assert profile_list["K_models"] == 3 and profile_list["K_total"] == 4
    assert profile_list["selection_start_authorized"] is False and profile_list["historical_import_used"] is False
    assert all(len(p["profile_sha256"]) == 64 for p in profile_list["profiles"])


def test_failures_in_pilot40_were_historical_imports_only(profile_list):
    for profile in profile_list["profiles"]:
        assert set(profile["ran_in_pilot40"]["failed_by_origin"]) <= {"historical_import"}


def test_neural_profiles_carry_runtime_identity(profile_list):
    neural = [p for p in profile_list["profiles"] if p["candidate_id"] in binding.NEURAL]
    assert all(p["dtype"] == "torch.float16" and p["model_revision"] and p["device_map"] for p in neural)


def test_changed_evidence_hash_is_rejected():
    with pytest.raises(ValueError, match="hash changed"):
        binding.build_profile_list(expected_sha="0" * 64)


@pytest.mark.parametrize("stage", ["selection300", "final523"])
def test_allocations_are_complete_and_consistent_with_projection(stage, outcome):
    allocation = binding.validate_allocation(binding.build_allocation(stage, "a" * 64), outcome)
    assert allocation["total_wall_hours"] == allocation["total_gpu_hours"]
    assert {"selection300": 15, "final523": 21}[stage] == allocation["total_gpu_hours"]
    assert {"selection300": 3, "final523": 4}[stage] == allocation["max_sessions"]


@pytest.mark.parametrize("field", binding.REQUIRED_NUMBERS)
def test_any_missing_numeric_field_is_rejected(field, outcome):
    allocation = binding.build_allocation("selection300", "a" * 64)
    allocation[field] = None
    with pytest.raises(ValueError):
        binding.validate_allocation(allocation, outcome)


def test_ceiling_below_projection_or_extra_retries_is_rejected(outcome):
    low = binding.build_allocation("final523", "a" * 64)
    low["total_gpu_hours"] = low["total_wall_hours"] = 15
    with pytest.raises(ValueError, match="lost-session"):
        binding.validate_allocation(low, outcome)
    retry = copy.deepcopy(binding.build_allocation("selection300", "a" * 64))
    retry["retry_limit_per_node"] = 1
    with pytest.raises(ValueError, match="retries"):
        binding.validate_allocation(retry, outcome)


def test_qwen3_cannot_re_enter_the_profile_universe(outcome):
    allocation = binding.build_allocation("selection300", "a" * 64)
    allocation["profile_ids"] = allocation["profile_ids"] + ["qwen3"]
    with pytest.raises(ValueError, match="four approved"):
        binding.validate_allocation(allocation, outcome)


def test_duplicate_profile_ids_are_rejected(outcome):
    allocation = binding.build_allocation("selection300", "a" * 64)
    allocation["profile_ids"] = ["lead3", "lead3", "bart", "led"]
    with pytest.raises(ValueError, match="four approved"):
        binding.validate_allocation(allocation, outcome)


def test_profile_hash_is_recomputed_from_profile_content(profile_list):
    assert all(p["profile_content_rehashed"] for p in profile_list["profiles"])
