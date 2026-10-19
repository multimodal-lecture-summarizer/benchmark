"""Conservative, evidence-gated cost projection; never seals cohorts or runs models."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from experiments.scripts.tib_benchmark_budget_receipts import verify_gate_files, verify_measurement_files

CANDIDATES = {"bart", "lead3", "led", "lexrank", "qwen3"}
GPU = {"bart", "led", "qwen3"}
STRATA = ("short", "medium", "long")
NODES = ("map", "reduce", "final")
QUOTAS = ("total_gpu_hours", "total_cpu_hours", "total_wall_hours", "max_sessions", "session_wall_hours",
          "persistent_storage_bytes", "local_working_storage_bytes", "transfer_bytes", "checkpoint_bytes")


def number(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"Missing/invalid numeric {label}")
    return value


def digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_profile(profile):
    candidate = profile.get("candidate_id")
    if candidate not in CANDIDATES or not digest(profile.get("profile_sha256")):
        raise ValueError("Unknown candidate or unbound profile identity")
    coverage = (("full_source_available_verified", "control_algorithm_verified") if candidate == "lead3"
                else ("full_source_coverage_verified",))
    for key in ("isolated_process", "inference_executed", "model_identity_verified", "capacity_pass", *coverage):
        if profile.get(key) is not True:
            raise ValueError(f"Profile evidence missing: {key}")
    revision = profile.get("model_revision", "")
    if (not digest(profile.get("measurement_receipt_sha256")) or not profile.get("model_id") or
            not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is None):
        raise ValueError("Missing measured model/code identity")
    ram = number(profile.get("ram_peak_bytes"), "RAM peak", True)
    if ram > number(profile.get("ram_available_bytes"), "available RAM", True):
        raise ValueError("RAM peak exceeds measured available capacity")
    if candidate in GPU:
        if profile.get("device_name") not in ("Tesla T4", "NVIDIA Tesla T4", "NVIDIA T4"):
            raise ValueError("Actual T4 required; RTX 4050 is not T4 evidence")
        vram = number(profile.get("vram_peak_bytes"), "VRAM peak", True)
        if vram > number(profile.get("device_memory_bytes"), "device capacity", True):
            raise ValueError("VRAM peak exceeds measured device capacity")
        if not profile.get("dtype") or not profile.get("backend"):
            raise ValueError("Missing dtype/backend")
        number(profile.get("context_tokens"), "context tokens", True)
    elif profile.get("generation_gpu_hours") is not None or profile.get("vram_peak_bytes") is not None:
        raise ValueError("CPU generation GPU/VRAM must be null (N/A)")
    for stratum in STRATA:
        measured = profile.get("strata", {}).get(stratum, {})
        n = number(measured.get("records_measured"), "records measured", True)
        success = number(measured.get("successes"), "successful measurements", True)
        failures = number(measured.get("failures"), "failure measurements")
        if success + failures != n:
            raise ValueError("Measured sample support/failures mismatch")
        number(measured.get("cpu_seconds_per_record_p95"), "CPU record cost", True)
        calls = 0
        for node in NODES:
            item = measured.get(node, {})
            count = number(item.get("calls_per_record_upper"), f"{node} calls")
            for field in ("input_tokens_per_call_upper", "output_tokens_per_call_upper", "wall_seconds_per_call_p95"):
                number(item.get(field), f"{node} {field}", positive=count > 0)
            calls += count
        if calls == 0:
            raise ValueError("No measured execution calls")
    number(profile.get("init_wall_seconds"), "initialization time", True)
    return profile


def cohort(value, expected):
    if not isinstance(value, dict) or set(value) != set(STRATA):
        raise ValueError("Missing predeclared source-stratum counts")
    for count in value.values():
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ValueError("Stratum counts must be positive integers")
    if sum(value.values()) != expected:
        raise ValueError("Cohort size mismatch")
    return value


def project(config, profiles):
    """Return blocked for unknown evidence. Inputs must be signed off before final seal."""
    try:
        if config.get("eligible_test_count") != 523 or config.get("fallback_order") != [523, 500, 400]:
            raise ValueError("Current policy is full 523 then 500 then 400")
        if config.get("diagnostics_inside_final") is not True or config.get("diagnostic_cases") != 40:
            raise ValueError("40 diagnostics must be inside final cohort")
        for key in QUOTAS:
            number(config.get(key), key, True)
        for key in ("retry_limit_per_node", "checkpoint_flush_seconds", "recovery_time_hours", "retry_cost_reserve",
                    "session_overhead_hours", "scoring_gpu_hours", "scoring_cpu_hours", "scoring_wall_hours",
                    "transfer_wall_hours", "checkpoint_wall_hours", "measured_probe_gpu_hours", "measured_probe_cpu_hours",
                    "measured_probe_wall_hours", "checkpoint_bytes_per_record", "artifact_bytes_per_record",
                    "artifact_bytes_per_call", "attempt_ledger_bytes_per_call", "checkpoint_bytes_per_call",
                    "fixed_working_bytes", "fixed_persistent_bytes",
                    "per_session_reload_gpu_hours", "per_session_reload_cpu_hours", "per_session_reload_wall_hours"):
            number(config.get(key), key)
        headroom = number(config.get("session_headroom_fraction"), "headroom")
        if any(not isinstance(config[key], int) or isinstance(config[key], bool)
               for key in ("retry_limit_per_node", "max_sessions")):
            raise ValueError("Retry/session limits must be integers")
        if headroom >= 1 or config["retry_cost_reserve"] < config["retry_limit_per_node"]:
            raise ValueError("Invalid headroom or retry reserve below full retry cap")
        for key in ("store_write_readback_verified", "store_restore_verified", "remote_source_use_authorized", "scorer_ready"):
            if config.get(key) is not True:
                raise ValueError(f"Missing gate {key}")
        for key in ("scorer_receipt_sha256", "store_receipt_sha256", "trial_registry_sha256", "admission_receipt_sha256"):
            if not digest(config.get(key)):
                raise ValueError(f"Missing receipt binding {key}")
        indexed = {}
        for profile in profiles:
            validate_profile(profile)
            identifier = profile.get("profile_id")
            if not identifier or identifier in indexed:
                raise ValueError("Missing/duplicate profile ID")
            indexed[identifier] = profile
        finals = [indexed[key] for key in config["final_profile_ids"]]
        admitted = config.get("admitted_candidate_ids")
        candidates = [p["candidate_id"] for p in finals]
        if (not isinstance(admitted, list) or len(candidates) != len(set(candidates)) or
                not 2 <= len(candidates) <= 5 or "lead3" not in candidates or
                set(candidates) != set(admitted) or len(admitted) != len(set(admitted))):
            raise ValueError("Finals must match bound admitted families plus fixed Lead-3")
        trials = config.get("development_trials")
        if not trials:
            raise ValueError("All development profile/config trials must be enumerated")
        if config.get("selection_count") not in (200, 300):
            raise ValueError("Selection count must be sealed 300 or justified fallback 200")
        for stage, required in (("pilot", set(indexed)), ("selection", set(config["final_profile_ids"]))):
            if not required.issubset({trial.get("profile_id") for trial in trials if trial.get("stage") == stage}):
                raise ValueError(f"Missing {stage} trial costs for registered profiles")
        options = []
        for size in config["fallback_order"]:
            runs = []
            for trial in trials:
                if trial["stage"] not in ("pilot", "selection"):
                    raise ValueError("Unknown development stage")
                counts = cohort(trial["stratum_counts"], 40 if trial["stage"] == "pilot" else config["selection_count"])
                repeats = trial.get("repetitions")
                if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
                    raise ValueError("Positive integer trial repetitions required")
                runs.append((indexed[trial["profile_id"]], counts, repeats))
            counts = cohort(config["final_stratum_counts"][str(size)], size)
            runs.extend((profile, counts, 1) for profile in finals)
            totals = {"gpu_seconds": config["measured_probe_gpu_hours"] * 3600,
                      "cpu_seconds": config["measured_probe_cpu_hours"] * 3600,
                      "wall_seconds": config["measured_probe_wall_hours"] * 3600,
                      "calls": 0, "input_tokens": 0, "output_tokens": 0, "final_outputs": 0}
            for profile, counts, repeats in runs:
                init = profile["init_wall_seconds"] * repeats
                totals["wall_seconds"] += init
                totals["gpu_seconds" if profile["candidate_id"] in GPU else "cpu_seconds"] += init
                for stratum, count in counts.items():
                    measured = profile["strata"][stratum]
                    scale = count * repeats
                    totals["final_outputs"] += scale
                    totals["cpu_seconds"] += measured["cpu_seconds_per_record_p95"] * scale
                    for node in NODES:
                        item = measured[node]
                        calls = item["calls_per_record_upper"] * scale
                        elapsed = calls * item["wall_seconds_per_call_p95"]
                        totals["calls"] += calls
                        totals["wall_seconds"] += elapsed
                        if profile["candidate_id"] in GPU:
                            totals["gpu_seconds"] += elapsed
                        for field in ("input_tokens", "output_tokens"):
                            totals[field] += calls * item[f"{field}_per_call_upper"]
            # Reserve covers retries for generation AND initialization/probes, conservatively.
            reserve = 1 + config["retry_cost_reserve"]
            gpu = totals["gpu_seconds"] / 3600 * reserve + config["scoring_gpu_hours"]
            cpu = totals["cpu_seconds"] / 3600 * reserve + config["scoring_cpu_hours"]
            wall = (totals["wall_seconds"] / 3600 * reserve + config["scoring_wall_hours"] +
                    config["transfer_wall_hours"] + config["checkpoint_wall_hours"] + config["recovery_time_hours"])
            useful_session = config["session_wall_hours"] * (1 - headroom) - config["session_overhead_hours"]
            if useful_session <= 0:
                raise ValueError("No usable session time")
            sessions = math.ceil(wall / useful_session)
            # Conservative all-profile reload allowance measured per session, including resumes.
            reload_wall = config["per_session_reload_wall_hours"]
            if reload_wall >= useful_session:
                raise ValueError("Session reload allowance exhausts usable session")
            sessions = math.ceil(wall / (useful_session - reload_wall))
            gpu += sessions * config["per_session_reload_gpu_hours"]
            cpu += sessions * config["per_session_reload_cpu_hours"]
            wall += sessions * reload_wall
            wall += sessions * config["session_overhead_hours"]
            storage = (totals["final_outputs"] * config["artifact_bytes_per_record"] +
                       totals["calls"] * (config["artifact_bytes_per_call"] + config["attempt_ledger_bytes_per_call"])) * reserve
            checkpoint = (totals["final_outputs"] * config["checkpoint_bytes_per_record"] +
                          totals["calls"] * config["checkpoint_bytes_per_call"]) * reserve
            fits = (gpu <= config["total_gpu_hours"] and cpu <= config["total_cpu_hours"] and
                    wall <= config["total_wall_hours"] and sessions <= config["max_sessions"] and
                    storage + checkpoint + config["fixed_persistent_bytes"] <= config["persistent_storage_bytes"] and
                    checkpoint <= config["checkpoint_bytes"] and
                    storage + checkpoint + config["fixed_working_bytes"] <= config["local_working_storage_bytes"] and
                    storage + checkpoint <= config["transfer_bytes"])
            options.append({"records": size, "gpu_hours": gpu, "cpu_hours": cpu, "wall_hours": wall,
                            "sessions": sessions, "artifact_bytes": storage, "checkpoint_bytes": checkpoint,
                            "accounting": totals, "fits": fits})
        selected = next((row["records"] for row in options if row["fits"]), None)
        return {"state": "projection_only_not_final_seal" if selected else "REQUIRED_NO_START",
                "recommended_size": selected, "final_cohort_sealed": False, "options": options,
                "reason": None if selected else "No permitted cohort fits conservative quotas"}
    except (ValueError, KeyError, TypeError) as exc:
        return {"state": "REQUIRED_NO_START", "recommended_size": None, "final_cohort_sealed": False, "reason": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profiles = json.loads(args.profiles.read_text(encoding="utf-8"))
    try:
        config = json.loads(args.budget.read_text(encoding="utf-8"))
        verify_gate_files(config, args.evidence_root)
        verify_measurement_files(profiles, args.evidence_root)
        result = project(config, profiles)
    except (ValueError, OSError) as exc:
        result = {"state": "REQUIRED_NO_START", "reason": str(exc), "final_cohort_sealed": False}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
