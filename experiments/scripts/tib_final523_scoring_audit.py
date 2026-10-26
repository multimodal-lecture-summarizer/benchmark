"""Offline audit of the returned final523 scoring evidence: integrity, resume provenance, coverage and cost; no scores.

No metric call is made and, by decision, NO score value, mean, delta or ranking is computed or stored: nothing about
scores is seen before the final analysis rules are declared. Counts come from the scoring contract (rows minus the
declared failed cells), never from constants. The resume checks cover the pre-run partial-resume policy: reuse accounting
reconciled against the checkpoints' provenance, checkpoint binding and coverage, the drift canary, quarantined torn writes,
runtime agreement across the contributing sessions and the policy hash. Coverage floors are shown for information only; they
are not the tier A/B decision. The CLI extracts the returned ZIP itself (evidence/, bundle/), so the audited files are exactly
the ones whose hash goes into the outcome; unreadable or malformed evidence fails a named check instead of raising.
"""
import argparse
import json
import tempfile
from pathlib import Path

from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts.tib_final523_generation_audit import UNREADABLE, extract_zip
from experiments.scripts.tib_final523_scorer_validation import FINAL_STAGE, RESUME_POLICY
from experiments.scripts.tib_pilot40_scoring_audit import PROFILES, VIEW_METRICS, finite, read_jsonl
from experiments.scripts.tib_pilot40_scoring_audit import sha256 as sha
from experiments.scripts.tib_scorer_colab_checkpoint import digest
from experiments.scripts.tib_selection300_scoring_audit import coverage, timing

PROTOCOL_ID = "tib-final523-scoring-261024-v1"
OUTCOME_NAME = "final523_scoring_outcome.json"
RECEIPT = FINAL_STAGE["receipt"]
CLOSED_STATUS = "scoring_evidence_exported"
METRICS = VIEW_METRICS + ("source_sentence_similarity_v1",)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def short(reason):
    """A reason reduced to its class or code: receipts can carry free exception text, the outcome must not."""
    return str(reason).split(":")[0][:60]


def checkpoint_scan(folder):
    """Payloads of every checkpoint file plus counters. A bad envelope, a wrong file name or an undecodable file is counted."""
    payloads, corrupt, duplicates, seen = [], 0, 0, set()
    for path in sorted(Path(folder).glob("*.json")) if Path(folder).exists() else []:
        try:
            envelope = _load(path)
            payload = envelope["payload"]
            intact = (set(envelope) == {"payload", "sha256"} and digest(payload) == envelope["sha256"]
                      and path.name == digest(payload["key"]) + ".json" and isinstance(payload["key"]["sample_id"], str))
        except UNREADABLE:
            intact = False
        if not intact:
            corrupt += 1
            continue
        sample = payload["key"]["sample_id"]
        duplicates += sample in seen
        seen.add(sample)
        payloads.append(payload)
    return payloads, corrupt, duplicates


def pinned_names(bundle_dir):
    amendment = _load(Path(bundle_dir) / "runtime_amendment.json")
    return {n.lower().replace("_", "-") for n in {**amendment["runtime_pins"], **amendment.get("support_package_pins", {})}}


def run_overview(runs_dir):
    """One entry per archived run directory; a killed session leaves a directory without a receipt."""
    entries = []
    for folder in sorted(Path(runs_dir).glob("*")) if Path(runs_dir).exists() else []:
        entry = {"run_id": folder.name, "has_receipt": False}
        try:
            if (folder / RECEIPT).exists():
                receipt = _load(folder / RECEIPT)
                metrics = read_jsonl(folder / "metrics.jsonl") if (folder / "metrics.jsonl").exists() else []
                costs = _load(folder / "cost_evidence.json") if (folder / "cost_evidence.json").exists() else {}
                entry.update(has_receipt=True, delivered_status=receipt.get("delivered_status"), views_status=receipt.get("views_status"),
                             reasons=[short(r) for r in receipt.get("reasons") or []],
                             rows_scored_fresh=sum(r["scoring_status"] == "completed" and not r.get("reused") for r in metrics),
                             rows_reused=sum(bool(r.get("reused")) for r in metrics), total_wall_seconds=costs.get("total_wall_seconds"),
                             runtime=receipt.get("runtime") or {}, quarantined=list(receipt.get("quarantined") or []))
        except UNREADABLE:
            entry.update(has_receipt=False, unreadable=True)
        entries.append(entry)
    return entries


def ledger_review(ledger, allocation, contract, runner_wall_seconds):
    """Anomalies in the shared ledger after the scoring session(s); an empty list means nothing unusual."""
    anomalies, runs = [], ledger["session_runs"]
    if ledger.get("bundle_sha256") != contract["generation_bundle_manifest_sha256"]:
        anomalies.append("ledger_bound_to_another_bundle")
    if len(runs) > allocation["max_sessions"]:
        anomalies.append("session_count_above_allocation")
    if ledger["gpu_seconds"] > allocation["total_gpu_hours"] * 3600:
        anomalies.append("cumulative_gpu_above_allocation")
    last = runs[-1]
    if last["status"] == "active":
        anomalies.append("scoring_session_still_active")
    elif last["status"] != CLOSED_STATUS:
        anomalies.append(f"scoring_session_closed_as_{last['status']}")
    measured = last.get("measured_wall_seconds")
    if runner_wall_seconds is None:
        anomalies.append("runner_wall_unavailable")
    elif measured is None or measured + 1 < runner_wall_seconds:
        anomalies.append("session_wall_shorter_than_runner_wall")
    elif measured > last["granted_wall_seconds"]:
        anomalies.append("session_wall_above_granted")
    if not any(r["status"] == CLOSED_STATUS for r in runs):
        anomalies.append("no_scoring_session_closed_with_evidence")
    return anomalies


def resume_checks(receipt, rows, root, bundle_dir, contract, policy_path, runs):
    """Reuse accounting, checkpoint provenance, canary, quarantine and runtime agreement. Fresh and replay runs are checked too."""
    partial = bool(receipt.get("partial_resume_requested"))
    replay = bool(receipt.get("cached_replay_verified")) and not partial
    scoreable = {r["sample_id"] for r in rows if r["scoring_status"] == "completed"}
    reused_flags = {r["sample_id"] for r in rows if r.get("reused")}
    run_id = str(receipt["run_id"])
    contributing = (set(map(str, receipt.get("run_ids") or [])) | {run_id}) if partial else {run_id}
    dirs = {r["run_id"]: r for r in runs}
    scores, bad_s, dup_s = checkpoint_scan(root / "checkpoints")
    views, bad_v, dup_v = checkpoint_scan(root / "view_checkpoints")
    binding = receipt["binding"]
    provenance = [p.get("provenance") or {} for p in scores + views]
    this_run = sum((p.get("provenance") or {}).get("run_id") == run_id for p in scores)
    checks = {}
    checks["checkpoints_intact_unique_and_bound_to_the_receipt"] = (
        bad_s == bad_v == dup_s == dup_v == 0 and all(p["key"]["binding"] == binding for p in scores + views))
    checks["checkpoints_cover_exactly_the_scored_cells"] = (
        {p["key"]["sample_id"] for p in scores} == scoreable and {p["key"]["sample_id"] for p in views} == {s + "__views" for s in scoreable})
    if partial:
        checks["checkpoint_runs_are_the_contributing_runs"] = bool(provenance) and {str(p.get("run_id")) for p in provenance} <= contributing
        checks["every_contributing_run_has_an_archived_directory"] = contributing <= set(dirs)
        checks["reuse_accounting_adds_up_and_matches_the_checkpoints"] = (
            receipt["reused_rows"] + receipt["fresh_rows"] == len(scoreable) and len(reused_flags) == receipt["reused_rows"]
            and this_run == receipt["fresh_rows"] and len(scores) - this_run == receipt["reused_rows"])
    elif replay:
        checks["checkpoint_runs_are_known_run_directories"] = bool(provenance) and {str(p.get("run_id")) for p in provenance} <= set(dirs) | {run_id}
        checks["replay_reused_every_scored_row"] = reused_flags == scoreable
    else:
        checks["fresh_run_checkpoints_all_belong_to_this_run"] = bool(provenance) and {str(p.get("run_id")) for p in provenance} == {run_id}
        checks["fresh_run_reused_nothing"] = not reused_flags and not receipt.get("reused_rows")
    policy = _load(bundle_dir / RESUME_POLICY) if (bundle_dir / RESUME_POLICY).exists() else {}
    registry_hash = sha(policy_path) if policy_path and Path(policy_path).exists() else None
    checks["resume_policy_is_the_users_pre_run_declaration"] = (
        bool(policy) and sha(bundle_dir / RESUME_POLICY) == contract.get("resume_policy_sha256") == registry_hash
        and policy.get("declared_by") == "user" and policy.get("post_hoc") is False and policy.get("partial_resume_allowed") is True
        and policy["canary"]["rows"] == runner.CANARY_ROWS and policy["canary"]["tolerance_absolute_per_metric"] == runner.CANARY_TOLERANCE
        and tuple(policy["runtime_binding"]["bound"]) == runner.PORTABLE_RUNTIME_FIELDS)
    if partial and receipt.get("reused_rows"):
        canary = receipt.get("canary") or {}
        checks["drift_canary_ran_and_passed"] = (
            bool(canary) and canary.get("passed") is True and 0 < len(canary["sample_ids"]) <= runner.CANARY_ROWS
            and set(canary["sample_ids"]) <= reused_flags and canary["max_abs_diff"] <= runner.CANARY_TOLERANCE
            and canary["tolerance"] == runner.CANARY_TOLERANCE)
    checks["no_reused_failed_rows"] = (receipt.get("reused_failed_rows") or 0) == 0
    quarantined = [p for folder in ("checkpoints", "view_checkpoints") for p in (root / folder).glob("*.quarantined-*")]
    listed = set(receipt.get("quarantined") or []) | {q for r in runs for q in r.get("quarantined", [])}
    on_disk = {p.name for p in quarantined}
    checks["quarantined_files_are_listed_and_their_rows_scored"] = (
        all((p.parent / p.name.split(".partial.quarantined-")[0]).exists() for p in quarantined)
        and on_disk <= listed and set(receipt.get("quarantined") or []) <= on_disk)
    pinned = pinned_names(bundle_dir)
    runtimes = [dirs[r]["runtime"] for r in contributing if r in dirs and dirs[r].get("runtime")] + [receipt["runtime"]]
    checks["contributing_runs_agree_on_the_compute_runtime"] = len(
        {runner.runtime_binding_digest(rt, FINAL_STAGE, pinned) for rt in runtimes}) == 1
    differing = sorted({k for rt in runtimes for k in set(rt) | set(receipt["runtime"]) if rt.get(k) != receipt["runtime"].get(k)})
    return checks, {
        "score_checkpoints": len(scores), "view_checkpoints": len(views), "quarantined_files": len(quarantined),
        "score_checkpoints_by_run": {r: sum(str((p.get("provenance") or {}).get("run_id")) == r for p in scores) for r in sorted(contributing)},
        "mixed_runtime": len({digest(rt) for rt in runtimes}) > 1 or bool(receipt.get("mixed_runtime")),
        "runtime_fields_that_differ_between_runs": differing,
        "compute_fields_that_differ_between_runs": sorted(set(differing) & set(runner.PORTABLE_RUNTIME_FIELDS))}


def _audit(extracted, expected_bundle_manifest_sha, contract, rules, ledger, allocation, policy_path):
    root, bundle_dir = Path(extracted) / "evidence", Path(extracted) / "bundle"
    receipt, costs = _load(root / RECEIPT), _load(root / "cost_evidence.json")
    rows, views = read_jsonl(root / "metrics.jsonl"), read_jsonl(root / "view_metrics.jsonl")
    runtime = receipt["runtime"]
    expected_rows, expected_scoreable = contract["expected_rows"], contract["expected_scoreable"]
    scoreable = [r for r in rows if r["scoring_status"] == "completed"]
    failed_cells = [r for r in rows if r["scoring_status"] == "not_scoreable_generation_failed"]
    resources = costs.get("resources") or {}
    runs = run_overview(root / "runs")
    matrix = [(i, p) for i in contract["selection_ids"] for p in contract["profile_order"]]
    # The runner writes rows in its scoring order (long sources first), not in contract order: what matters is that the rows are
    # exactly the contract's (record, profile) cells, each once, with unique sample ids.
    cells = [(r["record_id"], r["profile_id"]) for r in rows]
    matrix_ok = len(cells) == len(set(cells)) and set(cells) == set(matrix) and len({r["sample_id"] for r in rows}) == len(rows)
    checks = {
        "contract_is_final523_and_unauthorized": (
            contract.get("stage") == "final523" and contract["scoring_start_authorized"] is False and contract["selection_rule_applied"] is False),
        "shipped_contract_is_the_registry_contract": _load(bundle_dir / "scoring_contract.json") == contract,
        "receipt_delivered_pass": receipt["delivered_status"] == "PASS" and not receipt["reasons"]
                                  and receipt.get(FINAL_STAGE["ready_key"]) is True,
        "views_complete": receipt["views_status"] == "COMPLETE",
        "actual_colab_t4": bool(runtime.get("google_colab_imported") and runtime.get("T4_device_observed")
                                and runtime.get("device_name") == "Tesla T4") and receipt.get("T4_verified") is True,
        "not_injected": receipt["testing_dependency_injection"] is False,
        "fixtures_pass": str(receipt["fixtures"].get("status")).lower() == "pass",
        "bundle_manifest_bound": receipt["binding"]["package_manifest_sha256"] == expected_bundle_manifest_sha,
        "generation_evidence_bound": receipt["binding"]["evidence_zip_sha256"] == contract["generation_evidence_zip_sha256"],
        "artifact_hashes_match": bool(receipt["artifact_sha256"]) and all(sha(root / n) == h for n, h in receipt["artifact_sha256"].items()),
        "rows_are_the_contract_matrix_with_unique_sample_ids": matrix_ok,
        "row_counts": len(rows) == expected_rows and len(scoreable) == expected_scoreable
                      and len(failed_cells) == expected_rows - expected_scoreable == contract["expected_failed"],
        "failed_cells_are_the_declared_ones": sorted(r["sample_id"] for r in failed_cells) == sorted(contract["failed_cells"])
                                              and all(r["failures"].get("record") for r in failed_cells),
        "profiles_fixed_no_qwen3": all(r["profile_id"] in PROFILES for r in rows) and receipt["qwen3_scored"] is False,
        "five_metrics_finite": all(all(finite(r["metrics"].get(m)) for m in METRICS) and not r["failures"] for r in scoreable),
        "failed_cells_null": all(all(v is None for v in r["metrics"].values()) for r in failed_cells),
        "view_rows_finite_and_complete": len(views) == expected_scoreable and all(
            finite(s["metrics"].get(m)) and not s["failures"] for v in views for s in v["views"].values() for m in VIEW_METRICS)
            and all(set(v["views"]) == {"S", "M", "L"} for v in views),
        "no_generation_no_selection": receipt["generation_executed"] is False and receipt["selection_start_authorized"] is False,
        "resources_measured": all(finite(resources.get(k)) and resources[k] > 0
                                  for k in ("wall_seconds", "cpu_seconds", "cuda_peak_reserved_bytes")),
    }
    resume, resume_counts = resume_checks(receipt, rows, root, bundle_dir, contract, policy_path, runs)
    checks.update(resume)
    anomalies = ledger_review(ledger, allocation, contract, costs.get("total_wall_seconds"))
    fresh_seconds = sum(r.get("new_scoring_wall_seconds") or 0.0 for r in rows if not r.get("reused"))
    mode = "partial" if receipt.get("partial_resume_requested") else "replay" if receipt.get("cached_replay_verified") else "fresh"
    return {
        "checks": checks, "audit_pass": all(checks.values()) and not anomalies, "anomalies": anomalies,
        "counts": {"cells": len(rows), "scored": receipt["successful_metric_records"], "failed_generation_cells": len(failed_cells)},
        "resume": {"mode": mode, "partial_resume_used": bool(receipt.get("partial_resume_used")), "reused_rows": receipt.get("reused_rows", 0),
                   "fresh_rows": receipt.get("fresh_rows", len(scoreable)), "reused_failed_rows": receipt.get("reused_failed_rows", 0),
                   "canary": receipt.get("canary"), "quarantined": receipt.get("quarantined", []), "checkpoint_counts": resume_counts,
                   "mixed_runtime": resume_counts["mixed_runtime"],
                   "runtime_fields_that_differ_between_runs": resume_counts["runtime_fields_that_differ_between_runs"],
                   "compute_fields_that_differ_between_runs": resume_counts["compute_fields_that_differ_between_runs"],
                   "reused_original_scoring_seconds": receipt.get("reused_original_scoring_seconds", 0.0), "fresh_scoring_seconds": fresh_seconds},
        "run_timeline": [{k: v for k, v in r.items() if k not in ("runtime", "quarantined")} for r in runs],
        "runs_without_receipt": sum(not r["has_receipt"] for r in runs),
        "coverage": coverage(rows, contract, rules) if matrix_ok else None,
        "timing_seconds_fresh_rows_only": timing(rows),
        "wall": {"last_run_total_hours": (costs.get("total_wall_seconds") or 0.0) / 3600},
        "ledger": {"sessions": [{"status": r["status"], "accounted_wall_seconds": r.get("accounted_wall_seconds")} for r in ledger["session_runs"]],
                   "gpu_seconds": ledger["gpu_seconds"]},
        "rule_applied": False, "scores_included": False,
    }


def audit(extracted, expected_bundle_manifest_sha, contract, rules, ledger, allocation, policy_path=None):
    """Audit result; evidence that cannot be read or has an unexpected shape fails the named check `evidence_readable`."""
    try:
        return _audit(extracted, expected_bundle_manifest_sha, contract, rules, ledger, allocation, policy_path)
    except UNREADABLE as error:
        return {"checks": {"evidence_readable": False}, "audit_pass": False, "anomalies": [],
                "unreadable": f"{type(error).__name__}: {str(error)[:160]}", "rule_applied": False, "scores_included": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path, help="the returned scoring evidence ZIP; the audit extracts it itself")
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--contract", required=True, type=Path, help="the registry scoring_contract.json")
    parser.add_argument("--rules", required=True, type=Path, help="admission_rules_v2.json (floors shown for information)")
    parser.add_argument("--policy", required=True, type=Path, help="the registry scorer_resume_policy_final523_v1.json")
    parser.add_argument("--ledger", required=True, type=Path, help="resource_ledger_after_scoring.json")
    parser.add_argument("--allocation", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("outcome already exists; the audit is recorded once")
    with tempfile.TemporaryDirectory() as scratch:
        extracted = extract_zip(args.zip, scratch)
        result = audit(extracted, args.manifest_sha, _load(args.contract), _load(args.rules), _load(args.ledger), _load(args.allocation), args.policy)
    result.update(schema_version=1, protocol_id=PROTOCOL_ID, evidence_zip_sha256=sha(args.zip),
                  scope="text-free summary of final523 scoring evidence: integrity, resume provenance, coverage and cost; no scores",
                  claim_limit="no score value, ranking, model selection or tier A/B decision is made or stored here")
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": result["audit_pass"], "failed": [k for k, v in result["checks"].items() if not v],
                      "anomalies": result["anomalies"]}))


if __name__ == "__main__":
    main()
