"""Synthetic contract tests, never reported as empirical feasibility measurements."""
import hashlib
import json
from pathlib import Path

import pytest

from experiments.scripts.tib_benchmark_budget import CANDIDATES, GPU, QUOTAS, project, validate_profile, verify_measurement_files


def inputs():
    config = json.loads(Path("experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/compute_budget.json").read_text())
    # Populate every unknown only in this synthetic unit-test fixture.
    for key, value in list(config.items()):
        if value is None:
            config[key] = 0
    config.update({key: 100000000 for key in QUOTAS})
    config.update(session_wall_hours=12, session_headroom_fraction=.25, checkpoint_flush_seconds=30,
                  retry_limit_per_node=1, retry_cost_reserve=1, checkpoint_bytes_per_record=100,
                  artifact_bytes_per_record=100, artifact_bytes_per_call=100,
                  store_write_readback_verified=True, store_restore_verified=True,
                  remote_source_use_authorized=True, scorer_ready=True,
                  scorer_receipt_sha256="a"*64, store_receipt_sha256="b"*64, trial_registry_sha256="c"*64,
                  admission_receipt_sha256="d"*64, admitted_candidate_ids=sorted(CANDIDATES))
    profiles = []
    for candidate in sorted(CANDIDATES):
        profile = dict(candidate_id=candidate, profile_id=candidate+"-p1", profile_sha256="d"*64,
                       measurement_receipt_sha256="e"*64, isolated_process=True, inference_executed=True,
                       capacity_pass=True, model_identity_verified=True, full_source_coverage_verified=True,
                       full_source_available_verified=True, control_algorithm_verified=True,
                       model_id=candidate, model_revision="f"*40, ram_peak_bytes=100,
                       ram_available_bytes=1000, device_memory_bytes=1000,
                       generation_gpu_hours=None, vram_peak_bytes=100 if candidate in GPU else None,
                       device_name="Tesla T4" if candidate in GPU else "CPU", dtype="fp16", backend="test",
                       context_tokens=1024, init_wall_seconds=1, strata={})
        for name in ("short", "medium", "long"):
            profile["strata"][name] = dict(records_measured=3, successes=3, failures=0,
                                           cpu_seconds_per_record_p95=1)
            for node in ("map", "reduce", "final"):
                profile["strata"][name][node] = dict(calls_per_record_upper=1,
                    input_tokens_per_call_upper=100, output_tokens_per_call_upper=10, wall_seconds_per_call_p95=1)
        profiles.append(profile)
    config["final_profile_ids"] = [p["profile_id"] for p in profiles]
    config["development_trials"] = [dict(profile_id=p["profile_id"], stage=stage,
        stratum_counts=counts, repetitions=1) for p in profiles for stage, counts in
        (("pilot", dict(short=13, medium=13, long=14)), ("selection", dict(short=100, medium=100, long=100)))]
    config["final_stratum_counts"] = {"523": dict(short=174,medium=174,long=175),
        "500": dict(short=166,medium=167,long=167), "400": dict(short=133,medium=133,long=134)}
    return config, profiles


def test_unset_template_is_no_start():
    config = json.loads(Path("experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/compute_budget.json").read_text())
    assert project(config, [])["state"] == "REQUIRED_NO_START"


def test_full_523_first_diagnostics_not_added():
    config, profiles = inputs()
    result = project(config, profiles)
    assert result["recommended_size"] == 523 and not result["final_cohort_sealed"]
    assert result["options"][0]["accounting"]["final_outputs"] == 5*(40+300+523)
    assert result["options"][0]["accounting"]["calls"] == 3*5*(40+300+523)


@pytest.mark.parametrize("target", [500,400,None])
def test_largest_permitted_fit_or_blocked(target):
    config, profiles = inputs()
    estimates = project(config, profiles)["options"]
    index = {500:1,400:2,None:2}[target]
    config["total_gpu_hours"] = estimates[index]["gpu_hours"] + (1e-6 if target else -1e-6)
    result = project(config, profiles)
    assert result["recommended_size"] == target
    assert (result["state"] == "REQUIRED_NO_START") == (target is None)


@pytest.mark.parametrize("field", ["store_write_readback_verified", "store_restore_verified", "scorer_ready", "remote_source_use_authorized"])
def test_gates_are_strict_booleans(field):
    config, profiles = inputs(); config[field] = "yes"
    assert project(config, profiles)["state"] == "REQUIRED_NO_START"


def test_4050_is_not_T4_and_missing_or_zero_measurements_block():
    config, profiles = inputs()
    profiles[0]["device_name"] = "NVIDIA GeForce RTX 4050 Laptop GPU"
    assert "T4" in project(config,profiles)["reason"]
    config, profiles = inputs(); profiles[0]["strata"]["long"]["successes"] = 0
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"
    config, profiles = inputs(); profiles[0]["isolated_process"] = False
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"


def test_retry_and_storage_reserves_fail_closed():
    config, profiles = inputs(); config["retry_cost_reserve"] = 0
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"
    config, profiles = inputs(); config["persistent_storage_bytes"] = 1
    assert project(config,profiles)["recommended_size"] is None
    config, profiles = inputs(); config["fixed_working_bytes"] = config["local_working_storage_bytes"]
    assert project(config,profiles)["recommended_size"] is None


def test_every_config_trial_cost_and_cpu_cost_are_required():
    config, profiles = inputs(); config["development_trials"].pop()
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"
    config, profiles = inputs(); profiles[-1]["strata"]["short"]["cpu_seconds_per_record_p95"] = 0
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"
    config, profiles = inputs(); cpu = next(p for p in profiles if p["candidate_id"] == "lead3")
    cpu["vram_peak_bytes"] = 0
    with pytest.raises(ValueError, match="N/A"):
        validate_profile(cpu)
    config, profiles = inputs(); profiles[0]["vram_peak_bytes"] = 1001
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"


def test_extra_trials_repetitions_and_reload_increase_projection():
    config, profiles = inputs(); before = project(config,profiles)["options"][0]
    config["development_trials"][0]["repetitions"] = 3
    config["per_session_reload_gpu_hours"] = .1
    config["per_session_reload_wall_hours"] = .1
    after = project(config,profiles)["options"][0]
    assert after["gpu_hours"] > before["gpu_hours"]
    assert after["accounting"]["calls"] > before["accounting"]["calls"]


def test_actual_measurement_file_hash_and_fields_must_match(tmp_path):
    _, profiles = inputs(); profile = profiles[0]
    measured = {key: value for key,value in profile.items() if key != "measurement_receipt_sha256"}
    raw = json.dumps(measured).encode(); (tmp_path / "receipt.json").write_bytes(raw)
    profile.update(measurement_receipt_path="receipt.json", measurement_receipt_sha256=hashlib.sha256(raw).hexdigest())
    verify_measurement_files([profile], tmp_path)
    profile["context_tokens"] += 1
    with pytest.raises(ValueError, match="mismatch"):
        verify_measurement_files([profile], tmp_path)
    profile["measurement_receipt_path"] = "../outside.json"
    with pytest.raises(ValueError, match="outside"):
        verify_measurement_files([profile], tmp_path)


def test_bound_admission_subset_includes_fixed_control_and_not_duplicate_family():
    config, profiles = inputs()
    config["final_profile_ids"] = ["bart-p1", "lead3-p1"]
    config["admitted_candidate_ids"] = ["bart", "lead3"]
    assert project(config,profiles)["recommended_size"] == 523
    config["admitted_candidate_ids"] = ["bart"]
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"
    config, profiles = inputs(); config["final_profile_ids"] = ["bart-p1", "bart-p1", "lead3-p1"]
    assert project(config,profiles)["state"] == "REQUIRED_NO_START"


def test_lead3_available_source_control_does_not_claim_map_coverage():
    _, profiles = inputs(); lead = next(p for p in profiles if p["candidate_id"] == "lead3")
    lead["full_source_coverage_verified"] = False
    validate_profile(lead)
    lead["control_algorithm_verified"] = False
    with pytest.raises(ValueError, match="control_algorithm"):
        validate_profile(lead)


def test_per_node_checkpoints_attempt_ledger_and_retry_storage_are_budgeted():
    config, profiles = inputs(); before = project(config, profiles)["options"][0]
    config["attempt_ledger_bytes_per_call"] = 100
    config["checkpoint_bytes_per_call"] = 100
    after = project(config, profiles)["options"][0]
    assert after["artifact_bytes"] == before["artifact_bytes"] + before["accounting"]["calls"]*200
    assert after["checkpoint_bytes"] == before["checkpoint_bytes"] + before["accounting"]["calls"]*200
