"""Stage-level (selection300/final523) allocation checks and generation budget guard.

Generalises the Pilot40 budget without touching it: the numeric contract comes from the allocation itself
(no fixed 11.5 h / 2-session ceilings, no `pilot_*` fields) and the four approved profiles replace the five.
Sampling, atomic writes, runtime pins and asset admission are reused from tib_pilot_resources.
"""
import math
from pathlib import Path
import shutil

from .tib_benchmark_checkpoint import digest
from .tib_pilot_resources import (  # noqa: F401  re-exported for the runtime
    GIB, PilotBudget, ResourceSample, admit_assets, atomic_json, boot_id, require, runtime_environment,
)
from .tib_selection300_binding import validate_allocation as _validate_numbers


def validate_stage_allocation(value):
    """Numeric contract + the operating floors every generation session relies on."""
    try:
        _validate_numbers(value)
    except ValueError as error:
        raise ValueError("REQUIRED_NO_START: " + str(error)) from error
    require(float(value["max_sessions"]).is_integer() and value["max_sessions"] >= 1, "Invalid session count")
    require(0 < value["session_wall_hours"] <= 11.5, "Colab 11.5h hard session bound")
    require(value["minimum_local_free_bytes"] >= 32 * GIB and value["local_working_storage_bytes"] > 0,
            "At least 32GiB free disk and a positive working storage cap required")
    require(value["checkpoint_flush_seconds"] > 0 or value.get("checkpoint_flush_policy") == "fsync_after_every_committed_node",
            "Zero flush interval requires fsync after every committed node")
    return value


def allocated_stage(value, wall_hours):
    validate_stage_allocation(value)
    require(0 < wall_hours <= value["session_wall_hours"], "Requested wall hours exceed the session grant")
    return value


class StageBudget(PilotBudget):
    """PilotBudget with the stage allocation contract; sampling/flush/usage behaviour is inherited."""

    def __init__(self, output, allocation, candidate, wall_hours, *, dependencies=None):
        import time
        import json
        self.output, self.allocation, self.candidate = Path(output), allocated_stage(allocation, wall_hours), candidate
        self.dependencies = dependencies
        self.path = self.output.parent / "resource_ledger.json"
        self.ledger = json.loads(self.path.read_text(encoding="utf-8"))
        self.clock = dependencies.clock if dependencies else time.monotonic
        self.cpu_clock = dependencies.cpu_clock if dependencies else time.process_time
        require(self.ledger["allocation_sha256"] == digest(allocation), "Allocation/ledger identity mismatch")
        require(self.ledger["boot_id"] == (dependencies.boot_id if dependencies else boot_id()), "Session boot changed")
        # A closed session must never keep generating: its wall time would no longer be accounted.
        require(self.ledger.get("session_status") == "active", "Ledger session is not active; open a new session first")
        for field in ("cpu_seconds", "gpu_seconds", "transfer_bytes", "checkpoint_bytes", "checkpoint_flush_seconds"):
            require(type(self.ledger.get(field)) in (int, float) and math.isfinite(self.ledger[field])
                    and self.ledger[field] >= 0, "Invalid ledger: " + field)
        require(isinstance(self.ledger.get("candidate_runs"), list), "Invalid candidate ledger")
        self.started, self.cpu_started = self.clock(), self.cpu_clock()
        self.initial_cpu, self.initial_gpu = self.ledger["cpu_seconds"], self.ledger["gpu_seconds"]
        self.storage_snapshot = None
        start = self.ledger["session_started_monotonic"]
        require(type(start) in (int, float) and math.isfinite(start) and start <= self.started, "Invalid session clock")
        require(len(self.ledger["session_runs"]) <= allocation["max_sessions"], "Authorized session count exceeded")
        # Generation may use whatever the scorer and recovery reserves leave inside the shared total.
        self.session_remaining_wall = ((allocation["total_wall_hours"] - allocation["recovery_time_hours"]
                                        - allocation["scoring_wall_hours"]) * 3600
                                       - self.ledger["completed_session_wall_seconds"])
        self.deadline = min(self.started + wall_hours * 3600,
                            start + min(allocation["session_wall_hours"] * 3600, self.ledger["session_limit_seconds"])
                            * (1 - allocation["session_headroom_fraction"]),
                            start + self.session_remaining_wall)

    def guard(self, *, check_memory=True, forecast_seconds=0, checkpoint_reserve_bytes=0):
        self.usage()
        a, l = self.allocation, self.ledger
        require(math.isfinite(forecast_seconds) and forecast_seconds >= 0, "Invalid node forecast")
        require(self.clock() + forecast_seconds < self.deadline, "Stage wall quota/headroom reached")
        require(l["cpu_seconds"] + forecast_seconds * 2 < (a["total_cpu_hours"] - a["scoring_cpu_hours"]) * 3600,
                "Reserved scorer CPU budget protected")
        require(l["gpu_seconds"] + forecast_seconds < (a["total_gpu_hours"] - a["scoring_gpu_hours"]) * 3600,
                "Reserved scorer GPU budget protected")
        require(l["checkpoint_bytes"] + checkpoint_reserve_bytes <= a["checkpoint_bytes"], "Projected checkpoint quota reached")
        require(l["transfer_bytes"] < a["transfer_bytes"], "Stage quota reached: transfer_bytes")
        require(l["checkpoint_bytes"] < a["checkpoint_bytes"], "Stage quota reached: checkpoint_bytes")
        if self.dependencies:
            return
        import psutil
        working = Path(l["local_working_root"])
        require(working.is_absolute() and working.is_relative_to(Path("/content")), "Invalid local cache root")
        if self.storage_snapshot is None or self.clock() - self.storage_snapshot["at"] >= 10:
            self.storage_snapshot = {
                "at": self.clock(), "checkpoint_bytes": l["checkpoint_bytes"],
                "local_free": shutil.disk_usage("/content").free,
                "working_bytes": sum(p.stat().st_size for p in working.rglob("*") if p.is_file()),
                "drive_free": shutil.disk_usage(self.output.parent).free,
                "stored_bytes": sum(p.stat().st_size for p in self.output.parent.rglob("*") if p.is_file())}
        disk = self.storage_snapshot
        growth = max(0, l["checkpoint_bytes"] - disk["checkpoint_bytes"]) + checkpoint_reserve_bytes
        require(disk["local_free"] >= a["minimum_local_free_bytes"], "Local free working storage quota")
        require(disk["working_bytes"] <= a["local_working_storage_bytes"], "Local working storage cap reached")
        require(disk["drive_free"] - growth >= a["persistent_storage_bytes"], "Drive free storage quota")
        require(disk["stored_bytes"] + growth < a["persistent_storage_bytes"], "Persistent stage storage quota reached")
        if check_memory:
            require(psutil.virtual_memory().available >= 2 * GIB, "Host available memory below 2GiB")
            if self.candidate in ("bart", "led"):
                import torch
                require(torch.cuda.mem_get_info()[0] >= GIB, "VRAM available below 1GiB")
