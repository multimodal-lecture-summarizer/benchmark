"""Verify completed upstream audit receipts before a development ID seal."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_receipts(root: Path, registry: Path):
    reference = json.loads((registry / "reference_review_validation_v2.json").read_text())
    if reference["status"] != "pass" or reference["historical_reviewed_count"] != 225:
        raise ValueError("Historical reference adjudication is incomplete")
    for name, expected in reference["preserved_files"].items():
        if sha(root / name) != expected:
            raise ValueError(f"Reference review receipt mismatch: {name}")
    rights = json.loads((root / "rights_validation_review_fix_receipt.json").read_text())
    if rights.get("replay_equals_frozen_ledger") is not True or rights.get("input_hashes_revalidated") is not True:
        raise ValueError("Rights replay validation failed")
    if (sha(root / "source_use_ledger.jsonl") != rights["original_ledger_sha256"]
            or sha(registry / "source_use_policy.json") != rights["policy_sha256"]):
        raise ValueError("Rights validation receipt mismatch")
    eda = json.loads((root / "eda/receipt.json").read_text())
    if eda["state"] != "executed_eda_not_cohort_seal":
        raise ValueError("EDA audit incomplete")
    for name, expected in eda["files"].items():
        path = (root / "eda" / name).resolve()
        if (root / "eda").resolve() not in path.parents or sha(path) != expected:
            raise ValueError(f"EDA receipt mismatch: {name}")
    group = json.loads((root / "source_group_summary.json").read_text())
    replay = json.loads((root / "group_validation_review_fix_receipt.json").read_text())
    if replay.get("status") != "pass":
        raise ValueError("Group implementation replay is incomplete")
    for flag in ("all_9103_hashes_revalidated", "accepted_pairs_revalidated", "graph_reconstruction_identical"):
        if replay.get(flag) is not True:
            raise ValueError(f"Group replay did not pass: {flag}")
    replay_files = {
        "original_summary_sha256": root / "source_group_summary.json",
        "source_group_ledger_sha256": root / "source_group_ledger.jsonl",
        "source_group_pairs_sha256": root / "source_group_pairs.jsonl",
        "policy_sha256": registry / "group_policy.json",
        "current_runner_sha256": Path(__file__).with_name("tib_model_benchmark_groups.py"),
        "current_core_sha256": Path(__file__).with_name("tib_model_benchmark_group_core.py"),
    }
    if any(sha(path) != replay[key] for key, path in replay_files.items()):
        raise ValueError("Group replay receipt hash mismatch")
    if (group.get("status") != "completed" or group.get("records") != 9103
            or group.get("historical_pairs_checked") != 2658
            or group.get("known_three_edges_reproduced") is not True):
        raise ValueError("Source-group audit or historical replication incomplete")
    if (sha(root / "source_group_ledger.jsonl") != group["source_group_ledger_sha256"]
            or sha(root / "source_group_pairs.jsonl") != group["source_group_pairs_sha256"]
            or sha(registry / "group_policy.json") != group["policy_sha256"]):
        raise ValueError("Source-group evidence hash mismatch")
