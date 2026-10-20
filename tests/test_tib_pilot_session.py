"""CPU-only persistent session-budget contracts; no pretrained assets or inference."""
import json

import pytest

from experiments.scripts.tib_pilot_session import (
    begin_session, digest, finish_session, record_setup, validate_allocation,
)


@pytest.fixture
def allocation():
    return {"state": "ALLOCATED", "total_gpu_hours": 11.5, "total_cpu_hours": 23,
            "total_wall_hours": 11.5, "max_sessions": 2, "session_wall_hours": 11.5,
            "persistent_storage_bytes": 2 * 1024**3, "checkpoint_bytes": 2 * 1024**3,
            "minimum_local_free_bytes": 32 * 1024**3, "local_working_storage_bytes": 24 * 1024**3,
            "transfer_bytes": 16 * 1024**3, "checkpoint_flush_seconds": 0,
            "recovery_time_hours": 0.5, "retry_limit_per_node": 0, "retry_cost_reserve": 0,
            "session_headroom_fraction": 0.15, "scoring_gpu_hours": 1.5, "scoring_cpu_hours": 3,
            "scoring_wall_hours": 1.5, "transfer_wall_hours": 0.1, "checkpoint_wall_hours": 0.1,
            "pilot_metric_tuning_trial_cap_per_candidate": 0, "pilot_feasibility_probe_cap_per_candidate": 1,
            "pilot_total_profile_cap": 5}


def observation(boot="first", monotonic=100, epoch_ns=1000000000000):
    return {"boot_id": boot, "monotonic": monotonic, "epoch_ns": epoch_ns, "logical_cpu_count": 2}


def start(path, allocation, **kwargs):
    return begin_session(path, allocation, "a" * 64, observation=kwargs.pop("observation", observation()),
                         local_working_root="/content/tib-pilot-work", **kwargs)


def read(path):
    return json.loads(path.read_text())


def test_begin_explicit_binding_bounded_slice_and_same_vm_no_reset(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    first = start(path, allocation)
    assert first["allocation_sha256"] == digest(allocation)
    assert first["session_limit_seconds"] == first["session_wall_budget_seconds"] == 5.75 * 3600
    assert len(first["session_runs"]) == 1
    charged = record_setup(path, 10, 12345, 30)
    again = start(path, allocation, observation=observation(monotonic=1000))
    assert again["cpu_seconds"] == charged["cpu_seconds"]
    assert again["gpu_seconds"] == 900
    assert len(again["session_runs"]) == 1
    assert again["session_started_monotonic"] == 100
    assert again["cpu_seconds"] == 10 and again["transfer_bytes"] == 12345
    assert again["local_working_root"] == "/content/tib-pilot-work"
    assert again["initial_local_working_bytes"] == 0


@pytest.mark.parametrize("key", ["total_gpu_hours", "total_cpu_hours", "total_wall_hours", "max_sessions",
                                "transfer_bytes", "scoring_cpu_hours", "scoring_wall_hours", "recovery_time_hours"])
def test_missing_quota_does_not_create_ledger(tmp_path, allocation, key):
    allocation.pop(key)
    path = tmp_path / "ledger.json"
    with pytest.raises(ValueError):
        start(path, allocation)
    assert not path.exists()


@pytest.mark.parametrize("key,value", [("total_wall_hours", 23), ("total_gpu_hours", 12),
    ("total_cpu_hours", 24), ("max_sessions", 3), ("session_wall_hours", 12),
    ("total_gpu_hours", float("nan")), ("transfer_bytes", float("inf")), ("checkpoint_flush_seconds", -1),
    ("total_cpu_hours", True), ("scoring_gpu_hours", 12), ("scoring_cpu_hours", 24),
    ("scoring_wall_hours", 11), ("minimum_local_free_bytes", 24 * 1024**3),
    ("local_working_storage_bytes", 32 * 1024**3), ("session_headroom_fraction", .1),
    ("retry_limit_per_node", 1), ("retry_cost_reserve", 1), ("scoring_gpu_hours", 0),
    ("session_overhead_hours", 11)])
def test_phase_budget_and_numeric_validation(tmp_path, allocation, key, value):
    allocation[key] = value
    with pytest.raises(ValueError):
        start(tmp_path / "ledger.json", allocation)


def test_clean_close_charges_measured_wall_and_preserves_attempts(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation)
    record_setup(path, 5, 100, 10)
    ledger = read(path)
    ledger.update(gpu_seconds=20, cpu_seconds=30,
                  candidate_runs=[{"node": "failed-attempt", "status": "failed"}])
    path.write_text(json.dumps(ledger))
    closed = finish_session(path, "partial", observation=observation(monotonic=400))
    assert closed["completed_session_wall_seconds"] == 300
    assert closed["cpu_seconds"] == 30 and closed["gpu_seconds"] == 300
    assert closed["unobserved_loss_reserve"] == {"cpu_seconds": 0, "gpu_seconds": 0, "wall_seconds": 0}
    assert closed["session_runs"][0]["measured_wall_seconds"] == 300
    assert finish_session(path, "partial", observation=observation(monotonic=500)) == closed
    with pytest.raises(ValueError, match="cannot be reset"):
        start(path, allocation, observation=observation(monotonic=600))
    resumed = start(path, allocation, observation=observation("second", 50, 10**18))
    assert len(resumed["session_runs"]) == 2
    assert resumed["completed_session_wall_seconds"] == 300
    assert resumed["candidate_runs"] == [{"node": "failed-attempt", "status": "failed"}]
    assert resumed["session_started_monotonic"] == 50


def test_interruption_reserves_full_slice_without_overnight_charge(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation)
    ledger = record_setup(path, 100, 200, 10)
    ledger["gpu_seconds"] = 50
    path.write_text(json.dumps(ledger))
    resumed = start(path, allocation, observation=observation("second", 10, 10**18))
    slice_seconds = 5.75 * 3600
    assert resumed["completed_session_wall_seconds"] == slice_seconds
    assert resumed["gpu_seconds"] == slice_seconds
    assert resumed["cpu_seconds"] == 2 * slice_seconds
    assert resumed["unobserved_loss_reserve"]["cpu_seconds"] == 2 * slice_seconds - 100
    assert resumed["unobserved_loss_reserve"]["gpu_seconds"] == slice_seconds - 50
    assert resumed["observed_usage"] == {"cpu_seconds": 100, "gpu_seconds": 50, "completed_wall_seconds": 0}
    assert resumed["session_runs"][0]["measured_wall_seconds"] is None
    assert resumed["session_runs"][0]["unobserved_interruption_cost"] == "unknown_conservatively_reserved"
    assert resumed["transfer_bytes"] == 200
    # No third VM; still account the loss of session2 before denying admission.
    with pytest.raises(ValueError, match="Two-session"):
        start(path, allocation, observation=observation("third", 1, 10**19))
    denied = read(path)
    assert len(denied["session_runs"]) == 2
    assert denied["completed_session_wall_seconds"] == 11.5 * 3600
    assert denied["cpu_seconds"] == 23 * 3600
    assert denied["gpu_seconds"] == 11.5 * 3600


def test_bindings_and_malformed_ledger_hold(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation)
    with pytest.raises(ValueError, match="binding"):
        begin_session(path, allocation, "b" * 64, observation=observation(), local_working_root="/content/tib-pilot-work")
    changed = dict(allocation, transfer_bytes=10 * 1024**3)
    with pytest.raises(ValueError, match="binding"):
        start(path, changed)
    ledger = read(path)
    ledger["cpu_seconds"] = -1
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError):
        start(path, allocation)


def test_partial_ledger_no_automatic_repair(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    path.with_suffix(".json.partial").write_text("incomplete")
    with pytest.raises(ValueError, match="Partial"):
        start(path, allocation)
    assert not path.exists()


def test_finished_session_cannot_charge_setup_or_finish_other_vm(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation)
    with pytest.raises(ValueError, match="different VM"):
        finish_session(path, observation=observation("other"))
    finish_session(path, observation=observation(monotonic=101))
    with pytest.raises(ValueError, match="active session"):
        record_setup(path, 1, 2, 3)


def test_smaller_per_session_ceiling_and_valid_reserves(allocation):
    allocation["session_wall_hours"] = 4
    assert validate_allocation(allocation) == allocation


def test_setup_and_cpu_only_active_wall_consume_t4_capacity_without_double_charge(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation)
    setup = record_setup(path, 100, 1000, 1200)
    assert setup["gpu_seconds"] == 1200
    assert setup["candidate_runs"] == []
    active = start(path, allocation, observation=observation(monotonic=1900))
    assert active["gpu_seconds"] == 1800
    closed = finish_session(path, observation=observation(monotonic=1900))
    assert closed["gpu_seconds"] == closed["completed_session_wall_seconds"] == 1800
    assert closed["session_runs"][0]["observed_gpu_seconds"] == 1800
    assert allocation["total_gpu_hours"] * 3600 - closed["gpu_seconds"] < allocation["total_gpu_hours"] * 3600


@pytest.mark.parametrize("cores", [None, 0, 3, True, 1.5])
def test_missing_or_excess_actual_cpu_core_bound_holds_before_ledger(tmp_path, allocation, cores):
    path = tmp_path / "ledger.json"
    observed = dict(observation(), logical_cpu_count=cores)
    with pytest.raises(ValueError, match="logical_cpu_count"):
        start(path, allocation, observation=observed)
    assert not path.exists()


def test_interrupted_cpu_reservation_uses_observed_one_core(tmp_path, allocation):
    path = tmp_path / "ledger.json"
    start(path, allocation, observation=dict(observation(), logical_cpu_count=1))
    resumed = start(path, allocation, observation=observation("second", 1))
    assert resumed["cpu_seconds"] == 5.75 * 3600
    assert resumed["session_runs"][0]["logical_cpu_count"] == 1


def test_actual_builder_allocation_accepts_boolean_control_metadata(tmp_path):
    from experiments.scripts.tib_pilot_bundle import pilot_allocation
    allocation = pilot_allocation()
    assert allocation["automatic_retries"] is False
    assert allocation["reserves_inside_totals"] is True
    assert validate_allocation(allocation) == allocation
    ledger = start(tmp_path / "ledger.json", allocation)
    assert ledger["allocation_sha256"] == digest(allocation)
    assert ledger["session_wall_budget_seconds"] == 5.75 * 3600


@pytest.mark.parametrize("key", ["default_session_slice_hours", "session_overhead_hours", "storage_capacity_bytes"])
def test_optional_numeric_budgets_still_reject_boolean_values(allocation, key):
    allocation[key] = True
    with pytest.raises(ValueError, match="invalid budget"):
        validate_allocation(allocation)
