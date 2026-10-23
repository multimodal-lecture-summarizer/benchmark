"""Bind the four-profile list and the approved selection300/final523 allocations as new versioned artifacts.

Pure functions over already-pinned evidence: no model is loaded, nothing is generated or scored, and no
existing registry file is modified. The approved ceilings come from the 2026-10-23 19:40 decision.
"""
import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments/registry/protocols/tib-selection300-binding-261023-v1"
EVIDENCE_ZIP = ROOT / "research-data/tib-pilot40-261020-v1/results/tib-pilot40-evidence-20261023T074252Z.zip"
EVIDENCE_SHA256 = "39cc411bd3304041a478c1fb55b55b2417764538a62df69aa15472ab0980dbce"
SCORING_OUTCOME = ROOT / "experiments/registry/protocols/tib-pilot40-scoring-261023-v1/pilot40_scoring_outcome.json"

PROFILE_ORDER = ("lead3", "lexrank", "bart", "led")
NEURAL = ("bart", "led")
GIB = 1024 ** 3
DECISION = "plans/reports/protocol-decision-261023-1940-tib-keep-scorer-v2-approve-budget-ceilings-report.md"
EXCLUDED = {"qwen3": "protocol decision 2026-10-23 18:42: dropped from selection300/final523 (resource subset)"}
LOSS_SLICE_HOURS = 5.75

# Approved ceilings (decision 19:40) plus the estimated, not measured, per-stage fields from the budget report.
STAGES = {
    "selection300": {"total_gpu_hours": 15, "total_cpu_hours": 30, "max_sessions": 3,
                     "scoring_gpu_hours": 3.1, "scoring_cpu_hours": 6.2, "scoring_wall_hours": 3.1,
                     "transfer_bytes": 16 * GIB, "recovery_time_hours": 1.0, "checkpoint_flush_seconds": 228,
                     "artifact_bytes_estimate": 114_000_000, "records": 300},
    "final523": {"total_gpu_hours": 21, "total_cpu_hours": 42, "max_sessions": 4,
                 "scoring_gpu_hours": 5.1, "scoring_cpu_hours": 10.2, "scoring_wall_hours": 5.1,
                 "transfer_bytes": 24 * GIB, "recovery_time_hours": 1.5, "checkpoint_flush_seconds": 398,
                 "artifact_bytes_estimate": 199_000_000, "records": 523},
}
COMMON = {"session_wall_hours": 5.75, "session_headroom_fraction": 0.15, "session_overhead_hours": 0.75,
          "persistent_storage_bytes": 2 * GIB, "checkpoint_bytes": 1 * GIB,
          "local_working_storage_bytes": 24 * GIB, "minimum_local_free_bytes": 32 * GIB,
          "retry_limit_per_node": 0, "retry_cost_reserve": 0, "automatic_retries": False,
          "node_forecast_safety_factor": 1.5, "selection_trial_cap_per_candidate": 0,
          "selection_total_profile_cap": 4}
REQUIRED_NUMBERS = ("total_gpu_hours", "total_cpu_hours", "total_wall_hours", "max_sessions", "session_wall_hours",
                    "session_headroom_fraction", "session_overhead_hours", "persistent_storage_bytes",
                    "local_working_storage_bytes", "minimum_local_free_bytes", "transfer_bytes",
                    "scoring_gpu_hours", "scoring_cpu_hours", "scoring_wall_hours", "checkpoint_bytes",
                    "checkpoint_flush_seconds", "recovery_time_hours", "retry_limit_per_node", "retry_cost_reserve",
                    "selection_trial_cap_per_candidate", "selection_total_profile_cap")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def digest_compact(value):
    """Hash convention of the Pilot40 bundle builder for profile content."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def failed_by_origin(receipt):
    """Pilot40 failures were all historical imports (not used by selection300); fresh generations all succeeded."""
    counts = {}
    for record in receipt["records"].values():
        if record["status"] == "failed":
            counts[record["origin"]] = counts.get(record["origin"], 0) + 1
    return counts


def build_profile_list(evidence_zip=EVIDENCE_ZIP, expected_sha=EVIDENCE_SHA256):
    """Four profiles bound to the identities that actually ran on the Colab T4 in Pilot40."""
    if sha256_file(evidence_zip) != expected_sha:
        raise ValueError("Pilot40 evidence ZIP hash changed")
    profiles = []
    with zipfile.ZipFile(evidence_zip) as archive:
        package = json.loads(archive.read("package/original_generation/candidate_profiles.json"))
        declared = {p["candidate_id"]: p for p in package["pipelines"]}
        contract = {p["candidate_id"]: p for p in json.loads(archive.read("package/pilot_contract.json"))["profiles"]}
        for candidate in PROFILE_ORDER:
            identity = json.loads(archive.read(f"pilot/{candidate}/run_identity.json"))
            if digest(identity["payload"]) != identity["sha256"] or identity["payload"]["candidate_id"] != candidate:
                raise ValueError(f"{candidate}: run identity corrupt or mismatched")
            receipt = json.loads(archive.read(f"pilot/{candidate}/candidate_receipt.json"))
            payload, entry = identity["payload"], declared[candidate]
            # Recompute the profile hash from the profile content itself, as the Pilot40 bundle builder did.
            content_sha = digest_compact(contract[candidate]["profile"])
            if not (content_sha == contract[candidate]["profile_sha256"] == payload["profile_sha256"]
                    and contract[candidate]["profile_id"] == payload["profile_id"]
                    and receipt["candidate_id"] == candidate):
                raise ValueError(f"{candidate}: profile content, contract and run identity disagree")
            row = {"candidate_id": candidate, "profile_id": payload["profile_id"],
                   "profile_sha256": payload["profile_sha256"], "profile_content_rehashed": True,
                   "role": entry["role"],
                   "generation_device": entry["generation_device"], "checkpoint": entry["checkpoint"],
                   "run_identity_sha256": identity["sha256"],
                   "acceptance_policy_sha256": payload["acceptance_policy_sha256"],
                   "pilot_bundle_sha256": payload["pilot_bundle_sha256"],
                   "ran_in_pilot40": {"status": receipt["status"], "records": len(receipt["records"]),
                                      "failed_by_origin": failed_by_origin(receipt)}}
            if candidate in NEURAL:
                env = receipt["environment"]
                row.update(model_revision=receipt["asset_admission"]["revision"],
                           dtype=env["actual_parameter_dtype"], attention_backend=env["actual_attention_backend"],
                           device_map=env["actual_device_map"])
            profiles.append(row)
    return {"schema_version": 1, "state": "BOUND_PENDING_READINESS_RECEIPT", "scope": "selection300 and final523",
            "pilot40_evidence_zip_sha256": expected_sha, "profiles": profiles,
            "allowed_config_list_sha256": digest([p["profile_sha256"] for p in profiles]),
            "excluded": EXCLUDED, "K_models": 3, "K_total": 4, "max_paired_contrasts": 6,
            "selection_trial_cap_per_candidate": 0, "selection_total_profile_cap": 4,
            "config_priority_for_exact_ties": [p["profile_id"] for p in profiles],
            "tie_priority_note": "last-resort tie break only; stable profile ID follows",
            "historical_import_used": False, "selection_start_authorized": False,
            "decision": DECISION}


def build_allocation(stage, profile_list_sha256):
    if stage not in STAGES:
        raise ValueError("Unknown stage")
    spec = dict(STAGES[stage])
    records = spec.pop("records")
    spec.pop("artifact_bytes_estimate")
    allocation = {"schema_version": 1, "state": "ALLOCATED", "stage": stage,
                  "authorization": "User decision 2026-10-23 19:40: operating ceiling, not a measured need",
                  "decision": DECISION, "profile_list_sha256": profile_list_sha256,
                  **COMMON, **spec, "total_wall_hours": spec["total_gpu_hours"],
                  "ceilings_are_not_measured_needs": True, "reserves_inside_totals": True,
                  "accounting_scope": "generation and scorer v2 (SBERT included); MiniCheck excluded",
                  "estimated_not_measured": ["checkpoint_flush_seconds", "transfer_bytes per session (~5.3 GB)",
                                             "artifact_bytes"],
                  "records_per_pipeline": records, "profile_ids": list(PROFILE_ORDER),
                  "selection_start_authorized": False}
    if stage == "final523":
        allocation.update(final_cohort_sealed=False, fallback_order=[523, 500, 400],
                          trial_cap_note="no config search; value kept 0 to satisfy numeric contract")
    return allocation


def validate_allocation(allocation, scoring_outcome=None):
    """Every numeric P4 field present and finite; ceilings consistent with the measured projection."""
    for name in REQUIRED_NUMBERS:
        value = allocation.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Missing/invalid numeric field: " + name)
    for name in ("total_gpu_hours", "total_cpu_hours", "max_sessions", "session_wall_hours", "checkpoint_bytes"):
        if allocation[name] <= 0:
            raise ValueError("Field must be positive: " + name)
    if allocation["state"] != "ALLOCATED" or allocation["selection_start_authorized"] is not False:
        raise ValueError("State must be ALLOCATED with selection_start_authorized false")
    if (len(allocation["profile_ids"]) != len(set(allocation["profile_ids"])) or "qwen3" in allocation["profile_ids"]
            or set(allocation["profile_ids"]) != set(PROFILE_ORDER)):
        raise ValueError("Profile universe must be exactly the four approved profiles")
    if allocation["total_wall_hours"] != allocation["total_gpu_hours"]:
        raise ValueError("Colab wall hours equal GPU hours")
    if allocation["retry_limit_per_node"] != 0 or allocation["retry_cost_reserve"] != 0 or allocation["automatic_retries"]:
        raise ValueError("No retries are authorized")
    if allocation["checkpoint_bytes"] > allocation["persistent_storage_bytes"]:
        raise ValueError("Checkpoint cap exceeds persistent store")
    if not 0 < allocation["session_headroom_fraction"] < 1 or allocation["scoring_wall_hours"] > allocation["total_wall_hours"]:
        raise ValueError("Invalid headroom or scoring wall hours")
    if allocation["total_gpu_hours"] > allocation["session_wall_hours"] * allocation["max_sessions"]:
        raise ValueError("Total hours exceed what the session slices can supply")
    if allocation["scoring_gpu_hours"] > allocation["total_gpu_hours"] or allocation["scoring_cpu_hours"] > allocation["total_cpu_hours"]:
        raise ValueError("Scoring reserve must fit inside the totals")
    if scoring_outcome is not None:
        projected = scoring_outcome["projection_scorer_v2_as_is"][allocation["stage"] + "|conservative"]
        if allocation["total_gpu_hours"] < projected["wall_equals_gpu_hours"] + LOSS_SLICE_HOURS:
            raise ValueError("Ceiling below measured conservative projection plus one lost-session slice")
        if allocation["max_sessions"] < projected["sessions"] + 1:
            raise ValueError("Session cap below projected sessions plus one spare")
        if allocation["scoring_gpu_hours"] < projected["scoring_hours"]:
            raise ValueError("Scoring reserve below measured conservative scoring hours")
    return allocation


def build_all(out=REGISTRY):
    out = Path(out)
    profiles = build_profile_list()
    write_json(out / "selection300_profiles_v2.json", profiles)
    profile_sha = sha256_file(out / "selection300_profiles_v2.json")
    outcome = json.loads(SCORING_OUTCOME.read_text(encoding="utf-8"))
    for stage in STAGES:
        write_json(out / f"compute_budget_{stage}.json",
                   validate_allocation(build_allocation(stage, profile_sha), outcome))
    return {"profiles_sha256": profile_sha,
            "allocations": {s: sha256_file(out / f"compute_budget_{s}.json") for s in STAGES}}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build_all(), indent=2))
