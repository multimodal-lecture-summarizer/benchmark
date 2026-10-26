"""Validate the private final523 scoring bundle before any output is scored.

Same checks as the selection300 stage on the 523 sealed test IDs x the four fixed profiles (2,092 cells). The
scoreable count is not a constant: it is rows minus the failed-generation cells the contract lists, and the rows
themselves must agree (a failed cell stays in the denominator with NULL metrics, nothing is retried or dropped).
Imports are relative so the same file runs inside the shipped bundle next to tib_selection300_scorer_validation.
"""
import json
import re
from pathlib import Path

from .tib_scorer_colab_checkpoint import file_sha
from .tib_stage_session import digest
from .tib_selection300_scorer_validation import (  # noqa: F401  re-exported for the runner and the notebook
    CONTRACT, OUTPUTS, PROFILES, STATUSES, VIEW_NAMES, WORD_CAP, _check_files, _check_row, check_ledger_ready,
    interleaved_order, sample_id,
)

FINAL_QUOTAS = {"short": 182, "medium": 172, "long": 169}
EXPECTED_IDS = 523
EXPECTED_ROWS = EXPECTED_IDS * len(PROFILES)
FINAL_STAGE = {
    "name": "final523", "receipt": "scorer_final523_receipt.json", "ready_key": "scorer_final523_ready",
    "scope": "Final523 reference scoring of 2,092 generation cells; confirms the locked choice, selection rule not re-run",
    # Policy opt-ins the runner honors only for this stage (scorer_resume_policy_final523_v1.json).
    "partial_resume_allowed": True, "portable_binding": True}
RESUME_POLICY = "scorer_resume_policy_final523_v1.json"
BUDGET_DECISION = "scoring_budget_decision_final523_v1.json"
# Ceilings the scoring allocation carves out of the generation allocation: used by generation + scoring ceiling <= approved total.
CARVED = (("total_gpu_hours", "gpu_seconds", 3600), ("total_cpu_hours", "cpu_seconds", 3600),
          ("total_wall_hours", "completed_session_wall_seconds", 3600), ("transfer_bytes", "transfer_bytes", 1))


def check_scoring_ledger_ready(ledger_path, allocation, generation_manifest_sha, boot_id=None):
    """Read-only precheck on the scoring ledger; a missing ledger is the first scoring session and is created by begin_session."""
    path = Path(ledger_path)
    if not path.exists():
        return {"sessions_used": 0, "max_sessions": allocation["max_sessions"], "gpu_hours_used": 0.0,
                "total_gpu_hours": allocation["total_gpu_hours"], "new_ledger": True}
    return check_ledger_ready(json.loads(path.read_text(encoding="utf-8")), allocation, generation_manifest_sha, boot_id)


def _check_carve_out(root, contract, allocation):
    """The scoring allocation must be the user's declared carve-out of what generation left, never a larger budget."""
    carve = allocation.get("carved_from_generation")
    decision = json.loads((root / BUDGET_DECISION).read_text(encoding="utf-8"))
    if (not isinstance(carve, dict) or file_sha(root / BUDGET_DECISION) != contract.get("scoring_budget_decision_sha256")
            or carve.get("decision_sha256") != contract.get("scoring_budget_decision_sha256")
            or decision.get("declared_by") != "user" or decision.get("post_hoc") is not False
            or decision.get("scoring_max_sessions") != allocation["max_sessions"] or allocation["max_sessions"] < 1):
        raise ValueError("Scoring budget decision missing, changed, not user-declared, or not the allocation's session cap")
    if carve.get("generation_allocation_sha256") != contract.get("generation_allocation_sha256"):
        raise ValueError("Scoring allocation is carved from another generation allocation")
    used, approved = carve["generation_ledger_used"], carve["generation_approved"]
    for total_key, used_key, unit in CARVED:
        if used[used_key] + allocation[total_key] * unit > approved[total_key] * unit + 1e-6:
            raise ValueError(f"Scoring ceiling {total_key} plus generation use exceeds the approved total")
    if allocation["max_sessions"] * allocation["session_wall_hours"] < allocation["total_gpu_hours"]:
        raise ValueError("Scoring session slices cannot supply the scoring hours")


def _check_contract(contract, amendment):
    if tuple(contract["profile_order"]) != PROFILES or tuple(amendment["profile_ids"]) != PROFILES:
        raise ValueError("Wrong profile universe or order")
    ids = contract["selection_ids"]
    if len(ids) != EXPECTED_IDS or len(set(ids)) != EXPECTED_IDS:
        raise ValueError("Wrong final ID universe")
    failed = contract["failed_cells"]
    scoreable = EXPECTED_ROWS - len(failed)
    if (contract["expected_rows"] != EXPECTED_ROWS or amendment["expected_output_count"] != EXPECTED_ROWS
            or contract["expected_failed"] != len(failed) or len(set(failed)) != len(failed)
            or contract["expected_scoreable"] != scoreable or amendment["expected_scoreable_count"] != scoreable):
        raise ValueError("Wrong output count in contract/amendment")
    if contract["scoring_start_authorized"] is not False or amendment.get("selection_start_authorized") is not False:
        raise ValueError("Bundle must not self-authorize scoring")
    for key in ("generation_evidence_zip_sha256", "generation_bundle_manifest_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", str(contract[key])):
            raise ValueError("Contract lacks the generation hash binding: " + key)
    strata = contract["source_strata"]
    if set(strata) != set(ids) or {k: sum(v == k for v in strata.values()) for k in FINAL_QUOTAS} != FINAL_QUOTAS:
        raise ValueError("Source strata differ from the 182/172/169 quotas")
    return ids, strata


def validate_final_scoring_bundle(root):
    """Reject modified code, inputs or denominators; return (manifest, spec, amendment, rows)."""
    root = Path(root).resolve()
    manifest = _check_files(root)
    files = manifest["files"]
    spec = json.loads((root / "frozen_scorer_spec.json").read_text(encoding="utf-8"))
    amendment = json.loads((root / "runtime_amendment.json").read_text(encoding="utf-8"))
    contract = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    if amendment["frozen_spec_sha256"] != file_sha(root / "frozen_scorer_spec.json"):
        raise ValueError("Frozen scorer spec binding mismatch")
    for name, expected in spec["code_sha256"].items():
        if files.get(name) != expected:
            raise ValueError("Frozen scorer code mismatch: " + name)
    ids, strata = _check_contract(contract, amendment)
    policy = json.loads((root / RESUME_POLICY).read_text(encoding="utf-8"))
    if (file_sha(root / RESUME_POLICY) != contract.get("resume_policy_sha256") or policy.get("partial_resume_allowed") is not True
            or policy.get("declared_by") != "user" or policy.get("post_hoc") is not False or policy.get("flag") != "--resume-partial"):
        raise ValueError("Resume policy missing, changed, not user-declared, or not the pre-run partial-resume policy")
    allocation = json.loads((root / "selection_allocation.json").read_text(encoding="utf-8"))
    if contract.get("stage") != "final523" or allocation.get("stage") != "final523" or digest(allocation) != contract["allocation_sha256"]:
        raise ValueError("Contract or allocation is not the final523 stage (or the allocation hash differs)")
    _check_carve_out(root, contract, allocation)
    rows = [json.loads(line) for line in (root / OUTPUTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != EXPECTED_ROWS:
        raise ValueError("Wrong profile universe or output count")
    if [(r["record_id"], r["profile_id"]) for r in rows] != [(i, p) for i in ids for p in PROFILES]:
        raise ValueError("Incomplete or reordered final matrix")
    if len({r["sample_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate sample_id")
    reference_of = {}
    for row in rows:
        _check_row(row, strata)
        if reference_of.setdefault(row["record_id"], (row["source_sha256"], row["reference_sha256"])) != (
                row["source_sha256"], row["reference_sha256"]):
            raise ValueError("Different source/reference for the same record")
    if sorted(r["sample_id"] for r in rows if not r["scoreable"]) != sorted(contract["failed_cells"]):
        raise ValueError("Failed cells differ between the rows and the contract")
    return manifest, spec, amendment, rows
