"""Offline audit of the returned final523 generation evidence; no model, no scoring, no generation, no score values.

Checks identity (ZIP vs bundle), the 523 x 4 denominator, per-record integrity and binding to the run identity, delivery/cap
behaviour, authorization, the shared ledger and measured time. Everything numeric comes from the bundle contract. Records
the runtime left `started` (a session ended mid-record; never retried) and failed cells are DISCLOSED, not failed: no retry
can recover them, and the admission floors (shown for information only) decide later. Text-free output.
The last evidence ZIP is authoritative (the export zips the whole Drive folder). The CLI extracts that ZIP itself, so the
audited files are exactly the ones whose hash goes into the outcome. Unreadable or malformed evidence fails a named check
instead of raising.
"""
import argparse
import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_selection300_generation_audit import FINISHED, STRATA, describe, sha

PROTOCOL_ID = "tib-final523-generation-261024-v1"
OUTCOME_NAME = "final523_generation_outcome.json"
NEURAL = ("bart", "led")
KNOWN_STATUSES = {"completed", "completed_with_warning", "failed", "started"}
FORBIDDEN_KEY_PARTS = ("reference", "abstract")
UNREADABLE = (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_zip(archive, destination):
    """Extract after refusing absolute paths, `..` escapes and symlinks; the audit then reads only these files."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Unsafe member in the evidence ZIP: " + item.filename)
        z.extractall(destination)
    return destination


def forbidden_keys(value, found=None):
    """Keys that would mean a reference/abstract travelled with the generation evidence."""
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, inner in value.items():
            if any(part in str(key).lower() for part in FORBIDDEN_KEY_PARTS):
                found.add(str(key))
            forbidden_keys(inner, found)
    elif isinstance(value, list):
        for inner in value:
            forbidden_keys(inner, found)
    return found


def read_records(folder):
    """{record_id: payload} plus integrity counters; a duplicate id, a bad hash or an undecodable file is counted, not hidden."""
    records, corrupt, duplicates = {}, 0, 0
    for path in sorted(Path(folder).glob("*.json")) if Path(folder).exists() else []:
        try:
            envelope = _load(path)
            intact = isinstance(envelope, dict) and set(envelope) == {"payload", "sha256"} and digest(envelope["payload"]) == envelope["sha256"]
            identifier = envelope["payload"]["record_id"] if intact else None
        except UNREADABLE:
            intact, identifier = False, None
        if not intact:
            corrupt += 1
            continue
        duplicates += identifier in records
        records[identifier] = envelope["payload"]
    return records, corrupt, duplicates


def floors_for_information(success, ids, strata, rules):
    """Coverage against the admission floors; information only, no decision is taken here."""
    config, common, quotas = rules["config_coverage"], rules["common_coverage"], {s: 0 for s in STRATA}
    for i in ids:
        quotas[strata[i]] += 1
    per_profile = {}
    for profile, ok in success.items():
        by_stratum = {s: sum(strata[i] == s for i in ok) for s in STRATA}
        per_profile[profile] = {
            "scored_success_candidates": len(ok), "fraction": len(ok) / len(ids),
            "overall_floor_met": len(ok) / len(ids) >= config["overall_min"] - 1e-12,
            "stratum_floors_met": {s: by_stratum[s] / quotas[s] >= config["per_stratum_min"] - 1e-12 for s in STRATA}}
    between = set.intersection(*success.values()) if success else set()
    by_stratum = {s: sum(strata[i] == s for i in between) for s in STRATA}
    return {"per_profile": per_profile,
            "common_set": {"size": len(between), "by_stratum": by_stratum,
                           "common_n_met": len(between) >= common["common_n_min"],
                           "overall_met": len(between) / len(ids) >= common["overall_min"] - 1e-12,
                           "stratum_fraction_met": {s: by_stratum[s] / quotas[s] >= common["per_stratum_min"] - 1e-12 for s in STRATA}},
            "rule_applied": False,
            "note": "generation-stage candidates only (status based); the scoring audit measures scored success. Information, not the decision."}


def _audit(extracted, bundle_package, expected_manifest_sha, rules):
    root = Path(extracted)
    sel, shipped, pkg = root / "selection", root / "package", Path(bundle_package)
    contract = _load(pkg / "selection_contract.json")
    ids, profiles, strata = contract["selection_ids"], contract["candidate_order"], contract["source_strata"]
    sources = {r["record_id"]: r for r in map(json.loads, (pkg / "selection_sources.jsonl").read_text(encoding="utf-8").splitlines())}
    development = set(contract["excluded_pilot_ids"]) | set(contract["excluded_selection_ids"])
    profile_hash = {p["candidate_id"]: p["profile_sha256"] for p in contract["profiles"]}
    # The export zips the ledger before the last session is closed; the closed copy travels beside it when the cell completed.
    closed_copy = sel / "session_close_after_export.json"
    ledger_source = "session_close_after_export.json" if closed_copy.exists() else "resource_ledger.json"
    ledger = _load(closed_copy if closed_copy.exists() else sel / "resource_ledger.json")
    allocation = _load(pkg / "selection_allocation.json")
    n = len(ids)
    checks, per, failures, interrupted, stage_times, success = {}, {}, [], [], {}, {}
    manifest = _load(pkg / "selection_manifest.json")
    shipped_files = {p.relative_to(shipped).as_posix() for p in shipped.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    checks["contract_is_final523_and_unauthorized"] = (
        contract.get("stage") == "final523" and contract["selection_authorized"] is False and contract["final_test_authorized"] is False
        and n == 523 and list(profiles) == ["lead3", "lexrank", "bart", "led"])
    checks["package_manifest_matches_prepared_bundle"] = (
        sha(shipped / "selection_manifest.json") == expected_manifest_sha and sha(pkg / "selection_manifest.json") == expected_manifest_sha)
    checks["package_files_identical_to_built_bundle"] = all(sha(shipped / name) == h for name, h in manifest["files"].items())
    checks["shipped_file_set_equals_the_manifest"] = shipped_files == set(manifest["files"]) | {"selection_manifest.json"}
    checks["final_cohort_bound_to_the_bundle"] = (shipped / "locked/final_cohort.json").exists() and sha(
        shipped / "locked/final_cohort.json") == contract["final_cohort_sha256"]
    checks["ids_are_test_ids_disjoint_from_development"] = (
        all(i.startswith("test:") for i in ids) and not development & set(ids) and len(set(ids)) == n)
    directories = sorted(p.name for p in sel.iterdir() if p.is_dir())
    checks["no_extra_profile_directory"] = directories == sorted(profiles)
    receipts, identities = {}, {}
    for candidate in profiles:
        receipts[candidate] = _load(sel / candidate / "candidate_receipt.json")
        identities[candidate] = _load(sel / candidate / "run_identity.json")
        records, corrupt, duplicates = read_records(sel / candidate / "records")
        statuses = Counter(r["status"] for r in records.values())
        words, capped, forced, flags, cap_events = [], 0, 0, Counter(), []
        bad_binding = missing = foreign_identity = 0
        success[candidate] = set()
        for ident in ids:
            r = records.get(ident)
            if r is None:
                missing += 1
                continue
            if r["source_sha256"] != sources[ident]["source_normalized_sha256"] or r["source_stratum"] != strata[ident]:
                bad_binding += 1
            foreign_identity += r.get("binding") != identities[candidate]["payload"]
            if r["status"] == "failed":
                failures.append({"candidate": candidate, "record_id": ident, "stratum": r["source_stratum"],
                                 "error_class": str(r.get("error", "")).split(":")[0][:60], "events": [e.get("status") for e in r.get("events", [])]})
            elif r["status"] == "started":
                interrupted.append({"candidate": candidate, "record_id": ident, "stratum": r["source_stratum"]})
            elif r["status"] in FINISHED:
                success[candidate].add(ident)
                d = r["result"]["delivery"]
                words.append(d["delivered_words"])
                capped += bool(d["capped"])
                forced += bool(d["forced_word_boundary"])
                if d["capped"]:
                    cap_events.append({"record_id": ident, "stratum": r["source_stratum"], "raw_words": d["raw_words"],
                                       "delivered_words": d["delivered_words"], "forced_word_cut": bool(d["forced_word_boundary"])})
                for flag in r["validation"]["acceptance"]["warnings"]:
                    flags[flag] += 1
                for item in r.get("stage_resources", []):
                    stage_times.setdefault(candidate, {}).setdefault(item["stage"], []).append(item["wall_seconds"])
        summary = receipts[candidate].get("summary") or {}
        per[candidate] = {
            "receipt_status": receipts[candidate]["status"], "statuses": dict(statuses), "records_on_disk": len(records),
            "missing": missing, "extra_records": len(set(records) - set(ids)), "duplicate_records": duplicates,
            "corrupt_or_unreadable_files": corrupt, "binding_mismatches": bad_binding,
            "records_not_bound_to_the_run_identity": foreign_identity,
            "distinct_runtime_sha256": len({r.get("runtime_sha256") for r in records.values()}),
            "unknown_statuses": sorted(set(statuses) - KNOWN_STATUSES),
            "receipt_summary_matches_records": (
                summary.get("denominator") == n and summary.get("pending") == n - len(records)
                and summary.get("successful") == statuses["completed"] + statuses["completed_with_warning"]
                and summary.get("failed_or_interrupted") == statuses["failed"] + statuses["started"]),
            "delivered_words": describe(words), "capped": capped, "forced_word_cuts": forced, "cap_events": cap_events,
            "warning_counts": dict(flags), "quality_all_null": all(r["quality"] is None for r in records.values()),
            "origin_all_fresh": all(r["origin"] == "fresh" for r in records.values()),
            "retried": sum(bool(r.get("automatic_retry")) for r in records.values()),
            "forbidden_keys": sorted(set().union(*(forbidden_keys(r) for r in records.values())) if records else []),
            "new_generation_calls": receipts[candidate].get("new_generation_calls"),
            "new_generation_wall_seconds": receipts[candidate].get("new_generation_wall_seconds"),
            "total_wall_seconds": receipts[candidate].get("total_wall_seconds"),
            "model_load_wall_seconds": receipts[candidate].get("model_load_wall_seconds"),
            "peak_vram_reserved_bytes": max([(r.get("resources") or {}).get("cuda_peak_reserved_bytes") or 0 for r in records.values()] or [0])}
    checks["all_cells_present_in_the_denominator"] = all(
        per[c]["records_on_disk"] == n and per[c]["missing"] == 0 and per[c]["extra_records"] == 0 and per[c]["duplicate_records"] == 0 for c in profiles)
    checks["every_record_file_intact_and_readable"] = all(per[c]["corrupt_or_unreadable_files"] == 0 for c in profiles)
    checks["only_known_record_statuses"] = all(not per[c]["unknown_statuses"] for c in profiles)
    checks["receipt_summaries_match_the_records"] = all(per[c]["receipt_summary_matches_records"] for c in profiles)
    checks["receipt_status_ok"] = all(per[c]["receipt_status"] in ("PASS", "COMPLETED_WITH_FAILURES") for c in profiles)
    checks["no_binding_mismatch_and_no_retry"] = all(per[c]["binding_mismatches"] == 0 and per[c]["retried"] == 0 for c in profiles)
    checks["records_bound_to_the_run_identity_and_one_runtime"] = all(
        per[c]["records_not_bound_to_the_run_identity"] == 0 and per[c]["distinct_runtime_sha256"] <= 1 for c in profiles)
    checks["quality_null_everywhere_and_all_fresh"] = all(per[c]["quality_all_null"] and per[c]["origin_all_fresh"] for c in profiles)
    checks["every_delivered_output_within_350_words"] = all(per[c]["delivered_words"].get("max", 0) <= 350 for c in profiles)
    checks["no_reference_or_abstract_key_in_any_record"] = all(not per[c]["forbidden_keys"] for c in profiles)
    checks["cpu_profiles_complete"] = all(per[c]["statuses"] == {"completed": n} for c in ("lead3", "lexrank"))
    checks["run_identity_binds_contract_profile_and_bundle"] = all(
        identities[c]["payload"]["profile_sha256"] == profile_hash[c] and identities[c]["payload"]["candidate_id"] == c
        and identities[c]["payload"]["bundle_sha256"] == expected_manifest_sha
        and identities[c]["payload"]["allocation_sha256"] == contract["allocation_sha256"]
        and identities[c]["payload"]["acceptance_policy_sha256"] == contract["acceptance_policy_sha256"]
        and digest(identities[c]["payload"]) == identities[c]["sha256"] for c in profiles)
    preflight = _load(sel / "preflight_receipt.json")
    checks["preflight_pass_on_tesla_t4"] = preflight["device_name"] == "Tesla T4" and preflight.get("status", "PASS") == "PASS"
    authorization = _load(sel / "start_authorization.json")
    receipt_hash = str(authorization.get("readiness_receipt_v2_sha256", ""))
    checks["authorization_is_the_users_and_binds_this_bundle"] = (
        authorization["manifest_sha256"] == expected_manifest_sha and authorization["authorized_by"] == "user"
        and bool(str(authorization["statement"]).strip()) and len(receipt_hash) == 64 and set(receipt_hash) <= set("0123456789abcdef"))
    checks["metrics_not_executed"] = _load(sel / "selection_summary.json")["metrics_executed"] is False
    checks["ledger_bound_to_this_bundle_and_allocation"] = (
        ledger["bundle_sha256"] == expected_manifest_sha and ledger["allocation_sha256"] == contract["allocation_sha256"]
        and digest(allocation) == contract["allocation_sha256"])
    checks["ledger_within_approved_totals"] = (ledger["gpu_seconds"] <= allocation["total_gpu_hours"] * 3600
                                               and len(ledger["session_runs"]) <= allocation["max_sessions"])
    anomalies, runs = [], ledger["session_runs"]
    last = runs[-1]
    if last["status"] != "active" and ledger.get("session_elapsed_wall_seconds", 0) > last.get("accounted_wall_seconds", 0) * 2:
        anomalies.append({"kind": "session_closed_early_but_generation_continued", "closed_status": last["status"],
                          "accounted_wall_seconds": last["accounted_wall_seconds"],
                          "runtime_heartbeat_elapsed_seconds": ledger["session_elapsed_wall_seconds"]})
    lost = [r["status"] for r in runs if r["status"] == "interrupted"]
    if lost:
        anomalies.append({"kind": "sessions_closed_as_interrupted", "count": len(lost)})
    wall = {}   # anomalies are disclosed, not part of audit_pass
    for entry in ledger["candidate_runs"]:
        wall[entry["candidate_id"]] = wall.get(entry["candidate_id"], 0.0) + entry["wall_seconds"]
    grants = [r["granted_wall_seconds"] for r in runs]
    separation = {"bart_wall_seconds": wall.get("bart"), "led_wall_seconds": wall.get("led"), "largest_session_grant_seconds": max(grants),
                  "proved_in_different_sessions": bool(wall.get("bart") and wall.get("led") and wall["bart"] + wall["led"] > max(grants)),
                  "note": "the ledger has no per-session candidate id; this is a wall-time proof plus the notebook assertion"}
    summary_path = sel / "checkpoint_summary.json"
    checkpoint_summary = None
    if summary_path.exists():
        written = _load(summary_path)
        checkpoint_summary = {"written_utc": written.get("written_utc"), "matches_records_on_disk": all(
            written["profiles"][c]["attempted"] == per[c]["records_on_disk"] for c in profiles if c in written.get("profiles", {}))}
    result = {"checks": checks, "audit_pass": all(checks.values()), "per_profile": per, "failures": failures,
              "interrupted_records": interrupted, "interrupted_count": len(interrupted), "failed_count": len(failures),
              "stage_seconds_per_call": {c: {s: describe(v) for s, v in d.items()} for c, d in stage_times.items()},
              "ledger_source": ledger_source,
              "ledger": {k: ledger[k] for k in ("cpu_seconds", "gpu_seconds", "transfer_bytes", "checkpoint_bytes",
                                               "checkpoint_flush_seconds", "completed_session_wall_seconds", "session_elapsed_wall_seconds")},
              "ledger_sessions": [{"status": r["status"], "granted_wall_seconds": r["granted_wall_seconds"],
                                   "accounted_wall_seconds": r.get("accounted_wall_seconds")} for r in runs],
              "candidate_runs": ledger["candidate_runs"], "bart_led_separation": separation,
              "checkpoint_summary": checkpoint_summary, "anomalies": anomalies}
    if rules is not None:
        result["informational_floors"] = floors_for_information(success, ids, strata, rules)
    return result


def audit(extracted, bundle_package, expected_manifest_sha, rules=None):
    """Audit result; evidence that cannot be read or has an unexpected shape fails the named check `evidence_readable`."""
    try:
        return _audit(extracted, bundle_package, expected_manifest_sha, rules)
    except UNREADABLE as error:
        return {"checks": {"evidence_readable": False}, "audit_pass": False, "interrupted_count": 0, "failed_count": 0,
                "unreadable": f"{type(error).__name__}: {str(error)[:160]}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path, help="the last evidence ZIP; the audit extracts it itself")
    parser.add_argument("--package", required=True, type=Path, help="the built generation bundle package")
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--prior-zip", type=Path, action="append", default=[], help="earlier session ZIPs, listed by hash only")
    parser.add_argument("--rules", type=Path, help="admission_rules_v2.json, for the informational floors")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit("outcome already exists; the audit is recorded once")
    with tempfile.TemporaryDirectory() as scratch:
        extracted = extract_zip(args.zip, scratch)
        result = audit(extracted, args.package, args.manifest_sha, _load(args.rules) if args.rules else None)
    result.update(schema_version=1, protocol_id=PROTOCOL_ID, evidence_zip_sha256=sha(args.zip),
                  prior_evidence_zip_sha256=[sha(p) for p in args.prior_zip], rule_applied=False,
                  scope="text-free audit of final523 generation evidence; no scores, no ranking, no selection",
                  claim_limit="integrity and denominator evidence only; interrupted and failed cells are disclosed, not judged")
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": result["audit_pass"], "failed": [k for k, v in result["checks"].items() if not v],
                      "interrupted": result["interrupted_count"], "failed_cells": result["failed_count"]}))


if __name__ == "__main__":
    main()
