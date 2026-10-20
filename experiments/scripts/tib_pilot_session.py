"""Persistent two-session pilot budget lifecycle; no inference or automatic retries."""
import hashlib
import json
import math
import os
from pathlib import Path
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _number(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError("Missing/nonfinite/invalid budget: " + name)
    return value


def validate_allocation(allocation):
    """Validate explicit quotas; reserves are inside their corresponding totals."""
    positive = ("total_gpu_hours", "total_cpu_hours", "total_wall_hours", "max_sessions",
                "session_wall_hours", "persistent_storage_bytes", "minimum_local_free_bytes",
                "local_working_storage_bytes", "transfer_bytes", "checkpoint_bytes")
    nonnegative = ("checkpoint_flush_seconds", "recovery_time_hours", "retry_limit_per_node",
                   "retry_cost_reserve", "session_headroom_fraction", "scoring_gpu_hours",
                   "scoring_cpu_hours", "scoring_wall_hours", "transfer_wall_hours", "checkpoint_wall_hours",
                   "pilot_metric_tuning_trial_cap_per_candidate", "pilot_feasibility_probe_cap_per_candidate",
                   "pilot_total_profile_cap")
    for name in positive + nonnegative:
        _number(allocation.get(name), name, positive=name in positive)
    for name in ("default_session_slice_hours", "session_overhead_hours", "storage_capacity_bytes",
                 "node_forecast_safety_factor", "max_records_per_pipeline"):
        if name in allocation:
            _number(allocation[name], name)
    # Check additional numeric fields too; NaN/negative values must never enter a receipt.
    for name, value in allocation.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            _number(value, name)
    if allocation.get("state") != "ALLOCATED":
        raise ValueError("Explicit ALLOCATED state required")
    limits = {"total_gpu_hours": 11.5, "total_cpu_hours": 23, "total_wall_hours": 11.5,
              "session_wall_hours": 11.5, "max_sessions": 2,
              "persistent_storage_bytes": 2 * 1024**3, "checkpoint_bytes": 2 * 1024**3,
              "transfer_bytes": 16 * 1024**3, "local_working_storage_bytes": 24 * 1024**3}
    if any(allocation[key] > limit for key, limit in limits.items()):
        raise ValueError("Pilot allocation exceeds user-authorized operating ceiling")
    if allocation["max_sessions"] != int(allocation["max_sessions"]):
        raise ValueError("max_sessions must be an integer")
    if not 0.15 <= allocation["session_headroom_fraction"] < 1:
        raise ValueError("At least15percent session headroom required")
    if allocation["minimum_local_free_bytes"] < 32 * 1024**3:
        raise ValueError("Minimum local free32GiB required; distinct from24GiB working cap")
    if allocation["retry_limit_per_node"] != 0 or allocation["retry_cost_reserve"] != 0:
        raise ValueError("Automatic retries/reserved retry trials are not authorized")
    if allocation["scoring_gpu_hours"] < 1.5 or allocation["scoring_cpu_hours"] < 3 or allocation["recovery_time_hours"] < 0.5:
        raise ValueError("User-authorized scoring/recovery reserves must be retained")
    if (allocation["scoring_gpu_hours"] > allocation["total_gpu_hours"]
            or allocation["scoring_cpu_hours"] > allocation["total_cpu_hours"]
            or sum(allocation[key] for key in ("recovery_time_hours", "scoring_wall_hours",
                    "transfer_wall_hours", "checkpoint_wall_hours")) + allocation.get("session_overhead_hours", 0)
                    >= allocation["total_wall_hours"]
            or allocation["checkpoint_bytes"] > allocation["persistent_storage_bytes"]):
        raise ValueError("Phase reserves must fit inside total allocation")
    return allocation


def _observation(observation):
    result = observation if observation is not None else {
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "monotonic": time.monotonic(), "epoch_ns": time.time_ns(), "logical_cpu_count": os.cpu_count()}
    if not isinstance(result.get("boot_id"), str) or not result["boot_id"].strip():
        raise ValueError("Observed VM boot_id required")
    _number(result.get("monotonic"), "observed monotonic")
    _number(result.get("epoch_ns"), "observed epoch_ns", positive=True)
    cores = result.get("logical_cpu_count")
    if isinstance(cores, bool) or not isinstance(cores, int) or not 1 <= cores <= 2:
        raise ValueError("Actual observed logical_cpu_count1..2 required for CPU allocation bound")
    return result


def _load(path):
    path = Path(path)
    if path.with_suffix(path.suffix + ".partial").exists():
        raise ValueError("Partial ledger requires investigation; no automatic repair")
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, ledger):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(ledger, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if _load(path) != ledger:
        raise ValueError("Ledger persisted readback differs")
    return ledger


def _validate_ledger(ledger):
    validate_allocation(ledger["allocation"])
    if digest(ledger["allocation"]) != ledger["allocation_sha256"]:
        raise ValueError("Ledger allocation binding differs")
    for name in ("cpu_seconds", "gpu_seconds", "transfer_bytes", "checkpoint_bytes",
                 "checkpoint_flush_seconds", "completed_session_wall_seconds", "session_started_monotonic",
                 "session_limit_seconds", "session_wall_budget_seconds", "setup_wall_seconds", "session_setup_wall_seconds"):
        _number(ledger.get(name), name)
    if (ledger["session_limit_seconds"] != ledger["session_wall_budget_seconds"]
            or not isinstance(ledger["candidate_runs"], list)
            or not isinstance(ledger["session_runs"], list)
            or not 1 <= len(ledger["session_runs"]) <= ledger["allocation"]["max_sessions"]):
        raise ValueError("Invalid session history/budget aliases")
    for name in ("cpu_seconds", "gpu_seconds", "wall_seconds"):
        _number(ledger["unobserved_loss_reserve"].get(name), "unobserved reserve " + name)
    for run in ledger["session_runs"]:
        cores = run.get("logical_cpu_count")
        if isinstance(cores, bool) or not isinstance(cores, int) or not 1 <= cores <= 2:
            raise ValueError("Session missing observed CPU-core bound")
        for name in ("started_monotonic", "granted_wall_seconds", "cpu_seconds_at_start", "gpu_seconds_at_start"):
            _number(run.get(name), name)
        if run["granted_wall_seconds"] > ledger["allocation"]["session_wall_hours"] * 3600:
            raise ValueError("Session history exceeds per-session ceiling")
    latest = ledger["session_runs"][-1]
    if any(ledger[root] != latest[history] for root, history in (
            ("boot_id", "boot_id"), ("session_started_monotonic", "started_monotonic"),
            ("session_limit_seconds", "granted_wall_seconds"), ("session_status", "status"),
            ("logical_cpu_count", "logical_cpu_count"))):
        raise ValueError("Current session/history identity differs")
    return ledger


def _observed_usage(ledger):
    ledger["observed_usage"] = {key: ledger[key] - ledger["unobserved_loss_reserve"][key]
                                 for key in ("cpu_seconds", "gpu_seconds")}
    ledger["observed_usage"]["completed_wall_seconds"] = (
        ledger["completed_session_wall_seconds"] - ledger["unobserved_loss_reserve"]["wall_seconds"])


def _gpu_capacity_floor(ledger, current_elapsed=0.0):
    """Attached T4 capacity includes setup/CPU/wait time; never add elapsed twice."""
    _number(current_elapsed, "active T4 session elapsed")
    ledger["gpu_seconds"] = max(ledger["gpu_seconds"], ledger["completed_session_wall_seconds"] + current_elapsed)


def _close(ledger, observed, status, *, interrupted=False):
    run = ledger["session_runs"][-1]
    extra_reserved = {"cpu_seconds": 0.0, "gpu_seconds": 0.0}
    if interrupted:
        wall = run["granted_wall_seconds"]
        for name, multiplier in (("cpu_seconds", run["logical_cpu_count"]), ("gpu_seconds", 1)):
            extra = max(0.0, multiplier * wall - (ledger[name] - run[name + "_at_start"]))
            ledger[name] += extra
            ledger["unobserved_loss_reserve"][name] += extra
            extra_reserved[name] = extra
        ledger["unobserved_loss_reserve"]["wall_seconds"] += wall
        run.update(measured_wall_seconds=None, unobserved_interruption_cost="unknown_conservatively_reserved",
                   accounting="Upper bounds; no elapsed overnight/offline time charged")
    else:
        wall = observed["monotonic"] - run["started_monotonic"]
        _number(wall, "session elapsed wall")
        _gpu_capacity_floor(ledger, wall)
        run.update(measured_wall_seconds=wall, accounting="Observed active session wall and persisted CPU/GPU usage")
    run.update(status=status, closed_epoch_ns=observed["epoch_ns"], accounted_wall_seconds=wall,
               observed_cpu_seconds=ledger["cpu_seconds"] - run["cpu_seconds_at_start"] - extra_reserved["cpu_seconds"],
               observed_gpu_seconds=ledger["gpu_seconds"] - run["gpu_seconds_at_start"] - extra_reserved["gpu_seconds"],
               additional_conservative_cpu_seconds=extra_reserved["cpu_seconds"],
               additional_conservative_gpu_seconds=extra_reserved["gpu_seconds"])
    ledger["completed_session_wall_seconds"] += wall
    _gpu_capacity_floor(ledger)
    ledger["session_status"] = status
    _observed_usage(ledger)


def begin_session(ledger_path, allocation, bundle_sha256, *, observation=None, local_working_root=None):
    """Open at most two VM sessions; matching active same-VM re-entry is unchanged."""
    validate_allocation(allocation)
    if not isinstance(bundle_sha256, str) or len(bundle_sha256) != 64 or any(c not in "0123456789abcdef" for c in bundle_sha256):
        raise ValueError("Exact bundle SHA256 required")
    observed, path = _observation(observation), Path(ledger_path)
    if path.with_suffix(path.suffix + ".partial").exists():
        raise ValueError("Partial ledger requires investigation")
    if path.exists():
        ledger = _validate_ledger(_load(path))
        if ledger["allocation_sha256"] != digest(allocation) or ledger["bundle_sha256"] != bundle_sha256:
            raise ValueError("Cumulative ledger allocation/bundle binding mismatch")
        if local_working_root is not None and ledger["local_working_root"] != str(local_working_root):
            raise ValueError("Local working-root binding mismatch")
        if ledger["boot_id"] == observed["boot_id"]:
            if ledger["session_status"] != "active":
                raise ValueError("Closed VM session cannot be reset/reopened")
            if observed["monotonic"] < ledger["session_started_monotonic"]:
                raise ValueError("Same-VM monotonic clock moved backwards")
            if observed["logical_cpu_count"] != ledger["logical_cpu_count"]:
                raise ValueError("Same-VM observed CPU-core binding changed")
            _gpu_capacity_floor(ledger, observed["monotonic"] - ledger["session_started_monotonic"])
            _observed_usage(ledger)
            return _save(path, ledger)
        if ledger["session_status"] == "active":
            _close(ledger, observed, "interrupted", interrupted=True)
            _save(path, ledger)  # Keep conservative loss charges even if admission fails.
        if len(ledger["session_runs"]) >= allocation["max_sessions"]:
            raise ValueError("Two-session allocation exhausted; no automatic new session")
    else:
        if local_working_root is None or not str(local_working_root).strip():
            raise ValueError("Full local working-root path required")
        ledger = {"allocation": allocation, "allocation_sha256": digest(allocation), "bundle_sha256": bundle_sha256,
                  "cpu_seconds": 0.0, "gpu_seconds": 0.0, "transfer_bytes": 0, "checkpoint_bytes": 0,
                  "checkpoint_flush_seconds": 0.0, "candidate_runs": [], "session_runs": [],
                  "completed_session_wall_seconds": 0.0, "setup_wall_seconds": 0.0,
                  "local_working_root": str(local_working_root), "initial_local_working_bytes": 0,
                  "unobserved_loss_reserve": {"cpu_seconds": 0.0, "gpu_seconds": 0.0, "wall_seconds": 0.0}}
    remaining = allocation["total_wall_hours"] * 3600 - ledger["completed_session_wall_seconds"]
    if (remaining <= 0 or ledger["gpu_seconds"] >= allocation["total_gpu_hours"] * 3600
            or ledger["cpu_seconds"] >= allocation["total_cpu_hours"] * 3600):
        raise ValueError("Cumulative allocation exhausted")
    limit = min(allocation["session_wall_hours"] * 3600,
                allocation["total_wall_hours"] * 3600 / allocation["max_sessions"], remaining)
    ledger.update(boot_id=observed["boot_id"], session_started_monotonic=observed["monotonic"],
                  session_limit_seconds=limit, session_wall_budget_seconds=limit, session_status="active",
                  logical_cpu_count=observed["logical_cpu_count"], session_setup_wall_seconds=0.0)
    ledger["session_runs"].append({"boot_id": observed["boot_id"], "started_monotonic": observed["monotonic"],
        "started_epoch_ns": observed["epoch_ns"], "granted_wall_seconds": limit, "status": "active",
        "logical_cpu_count": observed["logical_cpu_count"],
        "cpu_seconds_at_start": ledger["cpu_seconds"], "gpu_seconds_at_start": ledger["gpu_seconds"]})
    _observed_usage(ledger)
    return _save(path, _validate_ledger(ledger))


def record_setup(ledger_path, cpu_seconds, transfer_bytes, wall_seconds):
    """Charge observed setup once; its wall duration already belongs to the session clock."""
    for name, value in (("cpu_seconds", cpu_seconds), ("transfer_bytes", transfer_bytes), ("wall_seconds", wall_seconds)):
        _number(value, name)
    ledger = _validate_ledger(_load(ledger_path))
    if ledger["session_status"] != "active":
        raise ValueError("Setup costs require an active session")
    ledger["cpu_seconds"] += cpu_seconds
    ledger["transfer_bytes"] += transfer_bytes
    ledger["setup_wall_seconds"] += wall_seconds
    ledger["session_setup_wall_seconds"] += wall_seconds
    _gpu_capacity_floor(ledger, ledger["session_setup_wall_seconds"])
    _observed_usage(ledger)
    return _save(ledger_path, ledger)


def finish_session(ledger_path, status="stopped", *, observation=None):
    """Persist a clean measured stop; repeated close is idempotent and never retries work."""
    if not isinstance(status, str) or not status.strip() or status == "active":
        raise ValueError("Explicit non-active stop status required")
    ledger, observed = _validate_ledger(_load(ledger_path)), _observation(observation)
    if observed["boot_id"] != ledger["boot_id"]:
        raise ValueError("Cannot clean-finish a different VM; begin_session accounts interruption")
    if observed["logical_cpu_count"] != ledger["logical_cpu_count"]:
        raise ValueError("Observed CPU-core binding changed")
    if ledger["session_status"] != "active":
        return ledger
    _close(ledger, observed, status)
    return _save(ledger_path, ledger)
