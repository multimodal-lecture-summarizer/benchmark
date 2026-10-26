"""Validate the private selection300 scoring bundle before any output is scored.

Pure checks on files only (no model, no GPU). The bundle holds exactly 1,200 cells: 300 sealed selection
records x the four fixed profiles, 1,197 scoreable and 3 failed-generation cells that stay in the
denominator with NULL metrics. The module also fixes the scoring order and the receipt names of the stage.
Imports are relative so the same file runs inside the shipped bundle.
"""
import hashlib
import json
import re
from pathlib import Path

from .tib_scorer_colab_checkpoint import file_sha

# Fixed by protocol (Qwen3 dropped 2026-10-23); the bundle's own amendment cannot widen them.
PROFILES = ("lead3", "lexrank", "bart", "led")
STRATUM_ORDER = {"long": 0, "medium": 1, "short": 2}
QUOTAS = {"short": 100, "medium": 90, "long": 110}
STATUSES = {"completed", "completed_with_warning", "failed"}
VIEW_NAMES = ("S", "M", "L")
EXPECTED_IDS, EXPECTED_ROWS, EXPECTED_SCOREABLE = 300, 1200, 1197
WORD_CAP = 350
OUTPUTS = "scoring_outputs.jsonl"
CONTRACT = "scoring_contract.json"
# Names and wording the runner uses for this stage (the Pilot40 stage keeps its own defaults).
SELECTION_STAGE = {
    "name": "selection300", "receipt": "scorer_selection300_receipt.json", "ready_key": "scorer_selection300_ready",
    "scope": "Selection300 reference scoring of 1,200 generation cells; descriptive, selection rule not applied"}


def sha_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sample_id(profile, record_id):
    return f"{profile}__{record_id.replace(':', '-')}"


def _check_files(root):
    manifest = json.loads((root / "package_manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
              and p.name != "package_manifest.json"
              and not ("__pycache__" in p.parts and p.suffix == ".pyc")}
    if not files or set(files) != actual:
        raise ValueError("Package manifest file set mismatch")
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or file_sha(path) != expected:
            raise ValueError("Package hash/path mismatch: " + name)
    return manifest


def _check_contract(contract, amendment):
    if tuple(contract["profile_order"]) != PROFILES or tuple(amendment["profile_ids"]) != PROFILES:
        raise ValueError("Wrong profile universe or order")
    ids = contract["selection_ids"]
    if len(ids) != EXPECTED_IDS or len(set(ids)) != EXPECTED_IDS:
        raise ValueError("Wrong selection ID universe")
    if (contract["expected_rows"] != EXPECTED_ROWS or amendment["expected_output_count"] != EXPECTED_ROWS
            or contract["expected_scoreable"] != EXPECTED_SCOREABLE
            or amendment["expected_scoreable_count"] != EXPECTED_SCOREABLE):
        raise ValueError("Wrong output count in contract/amendment")
    if contract["scoring_start_authorized"] is not False or amendment.get("selection_start_authorized") is not False:
        raise ValueError("Bundle must not self-authorize scoring")
    for key in ("generation_evidence_zip_sha256", "generation_bundle_manifest_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", str(contract[key])):
            raise ValueError("Contract lacks the generation hash binding: " + key)
    strata = contract["source_strata"]
    if set(strata) != set(ids) or {k: sum(v == k for v in strata.values()) for k in QUOTAS} != QUOTAS:
        raise ValueError("Source strata differ from the 100/90/110 quotas")
    return ids, strata


def _check_row(row, strata):
    record_id, profile = row["record_id"], row["profile_id"]
    if (row["candidate_id"] != profile or row["sample_id"] != sample_id(profile, record_id)
            or not re.fullmatch(r"[a-f0-9]{64}", str(row["source_receipt_sha256"]))):
        raise ValueError("Candidate/profile/sample binding invalid")
    for text, key in (("source", "source_sha256"), ("reference", "reference_sha256")):
        if not isinstance(row[text], str) or sha_text(row[text]) != row[key]:
            raise ValueError("Stored text/hash mismatch: " + text)
    if row["generation_status"] not in STATUSES or row["source_stratum"] != strata[record_id]:
        raise ValueError("Invalid status or stratum")
    if row["scoreable"] != (row["generation_status"] != "failed"):
        raise ValueError("Scoreable flag disagrees with generation status")
    if not row["scoreable"]:
        if not row.get("failure_reason") or row["delivered_summary"] is not None or row["views"] is not None:
            raise ValueError("Failed cell without recorded reason or with leftover output")
        return
    delivered = row["delivered_summary"]
    if (not isinstance(delivered, str) or not delivered.strip() or sha_text(delivered) != row["delivered_sha256"]
            or len(delivered.split()) > WORD_CAP):
        raise ValueError("Delivered summary hash/cap mismatch")
    views = row.get("views")
    if (not views or set(views) != set(VIEW_NAMES)
            or not all(isinstance(t, str) and t.strip() for t in views.values())):
        raise ValueError("Scoreable row lacks non-empty S/M/L views")


def validate_selection_scoring_bundle(root):
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
    rows = [json.loads(line) for line in (root / OUTPUTS).read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != EXPECTED_ROWS:
        raise ValueError("Wrong profile universe or output count")
    # File order is part of the contract: sealed record order, fixed profile order inside each record.
    if [(r["record_id"], r["profile_id"]) for r in rows] != [(i, p) for i in ids for p in PROFILES]:
        raise ValueError("Incomplete or reordered selection matrix")
    if len({r["sample_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate sample_id")
    reference_of = {}
    for row in rows:
        _check_row(row, strata)
        if reference_of.setdefault(row["record_id"], (row["source_sha256"], row["reference_sha256"])) != (
                row["source_sha256"], row["reference_sha256"]):
            raise ValueError("Different source/reference for the same record")
    if sum(r["scoreable"] for r in rows) != EXPECTED_SCOREABLE:
        raise ValueError("Scoreable count differs from the contract")
    return manifest, spec, amendment, rows


def check_ledger_ready(state, allocation, generation_manifest_sha, boot_id=None):
    """Read-only precheck before the notebook may open a session on the shared generation ledger.

    An active session is accepted only for re-entry from the same VM (same boot_id), e.g. after a kernel restart;
    begin_session then returns it unchanged, so RESUME can replay a complete cache.
    """
    from .tib_stage_session import digest
    if state["bundle_sha256"] != generation_manifest_sha:
        raise ValueError("Ledger is bound to another bundle")
    if state["allocation_sha256"] != digest(allocation):
        raise ValueError("Ledger allocation differs from the bundle allocation")
    reentry = state["session_status"] == "active" and boot_id is not None and state.get("boot_id") == boot_id
    if state["session_status"] == "active" and not reentry:
        raise ValueError("Ledger shows an active session; investigate before scoring")
    if not reentry and len(state["session_runs"]) >= allocation["max_sessions"]:
        raise ValueError("No authorized session left")
    return {"sessions_used": len(state["session_runs"]), "max_sessions": allocation["max_sessions"],
            "gpu_hours_used": state["gpu_seconds"] / 3600, "total_gpu_hours": allocation["total_gpu_hours"]}


def interleaved_order(rows):
    """Long sources first; each source scores all four profiles back to back (stable sort keeps file order).

    A deadline then leaves the profiles with equal coverage (within one row) instead of one profile missing.
    Failed cells are never scored.
    """
    return sorted((r for r in rows if r["scoreable"]), key=lambda r: STRATUM_ORDER[r["source_stratum"]])
