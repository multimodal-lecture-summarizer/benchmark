"""Offline audit of the returned selection300 generation evidence; no model, no scoring, no generation.

Checks identity (ZIP vs bundle), the 4 x 300 denominator, per-record bindings, delivery/cap behaviour,
failures and warnings, the shared ledger and measured time per profile and stage. Text-free output.
"""
import argparse
import hashlib
import json
import statistics
import zipfile
from collections import Counter
from pathlib import Path

PROFILES = ("lead3", "lexrank", "bart", "led")
NEURAL = ("bart", "led")
STRATA = ("short", "medium", "long")
FINISHED = {"completed", "completed_with_warning"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(values):
    values = sorted(values)
    if not values:
        return {"n": 0}

    def at(q):
        pos = (len(values) - 1) * q
        lo, hi = int(pos), min(int(pos) + 1, len(values) - 1)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    return {"n": len(values), "mean": statistics.fmean(values), "p50": at(0.5), "p90": at(0.9), "max": values[-1]}


def audit(extracted, bundle_package, expected_manifest_sha):
    sel, pkg = Path(extracted) / "selection", Path(bundle_package)
    contract = json.loads((pkg / "selection_contract.json").read_text(encoding="utf-8"))
    sources = {r["record_id"]: r for r in map(json.loads, (pkg / "selection_sources.jsonl").read_text(encoding="utf-8").splitlines())}
    ids = contract["selection_ids"]
    ledger = json.loads((sel / "resource_ledger.json").read_text(encoding="utf-8"))
    checks, per, failures, warnings, stage_times = {}, {}, [], {}, {}
    shipped = Path(extracted) / "package"
    checks["package_manifest_matches_prepared_bundle"] = sha(shipped / "selection_manifest.json") == expected_manifest_sha
    checks["package_files_identical_to_built_bundle"] = all(
        sha(shipped / name) == digest for name, digest in json.loads((pkg / "selection_manifest.json").read_text())["files"].items())
    receipts = {c: json.loads((sel / c / "candidate_receipt.json").read_text(encoding="utf-8")) for c in PROFILES}
    for candidate in PROFILES:
        receipt = receipts[candidate]
        records = {}
        for path in sorted((sel / candidate / "records").glob("*.json")):
            envelope = json.loads(path.read_text(encoding="utf-8"))
            records[envelope["payload"]["record_id"]] = envelope["payload"]
        statuses = Counter(r["status"] for r in records.values())
        words, capped, forced, flags, cap_events = [], 0, 0, Counter(), []
        bad_binding = missing = 0
        for ident in ids:
            r = records.get(ident)
            if r is None:
                missing += 1
                continue
            if r["source_sha256"] != sources[ident]["source_normalized_sha256"] or r["source_stratum"] != sources[ident]["source_stratum"]:
                bad_binding += 1
            if r["status"] == "failed":
                failures.append({"candidate": candidate, "record_id": ident, "stratum": r["source_stratum"], "error": r.get("error"),
                                 "events": [e.get("status") for e in r.get("events", [])]})
            elif r["status"] in FINISHED:
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
        per[candidate] = {
            "receipt_status": receipt["status"], "statuses": dict(statuses), "records_on_disk": len(records), "missing": missing,
            "binding_mismatches": bad_binding, "delivered_words": describe(words), "capped": capped, "forced_word_cuts": forced, "cap_events": cap_events,
            "warning_counts": dict(flags), "quality_all_null": all(r["quality"] is None for r in records.values()),
            "origin_all_fresh": all(r["origin"] == "fresh" for r in records.values()),
            "retried": sum(bool(r.get("automatic_retry")) for r in records.values()),
            "new_generation_calls": receipt["new_generation_calls"], "new_generation_wall_seconds": receipt["new_generation_wall_seconds"],
            "total_wall_seconds": receipt["total_wall_seconds"], "model_load_wall_seconds": receipt.get("model_load_wall_seconds"),
            "peak_vram_reserved_bytes": max([r.get("resources", {}).get("cuda_peak_reserved_bytes") or 0 for r in records.values()] or [0])}
    checks["all_1200_cells_present_in_denominator"] = all(per[c]["records_on_disk"] == 300 and per[c]["missing"] == 0 for c in PROFILES)
    checks["no_binding_mismatch_and_no_retry"] = all(per[c]["binding_mismatches"] == 0 and per[c]["retried"] == 0 for c in PROFILES)
    checks["quality_null_everywhere_and_all_fresh"] = all(per[c]["quality_all_null"] and per[c]["origin_all_fresh"] for c in PROFILES)
    # Cap events are disclosed, not failures: the cap is a delivery maximum and a mid-sentence cut is flagged by design.
    checks["every_delivered_output_within_350_words"] = all(
        per[c]["delivered_words"].get("max", 0) <= 350 for c in PROFILES)
    checks["no_qwen3_output"] = not (sel / "qwen3").exists()
    checks["cpu_profiles_complete"] = all(per[c]["statuses"] == {"completed": 300} for c in ("lead3", "lexrank"))
    checks["preflight_pass_on_tesla_t4"] = json.loads((sel / "preflight_receipt.json").read_text())["device_name"] == "Tesla T4"
    checks["authorization_binds_this_bundle"] = json.loads((sel / "start_authorization.json").read_text())["manifest_sha256"] == expected_manifest_sha
    checks["selection_not_authorized_for_metrics"] = json.loads((sel / "selection_summary.json").read_text())["metrics_executed"] is False
    checks["ledger_within_approved_totals"] = (ledger["gpu_seconds"] <= ledger["allocation"]["total_gpu_hours"] * 3600
                                               and len(ledger["session_runs"]) <= ledger["allocation"]["max_sessions"])
    anomalies = []
    last = ledger["session_runs"][-1]
    heartbeat = ledger.get("session_elapsed_wall_seconds", 0)
    if last["status"] != "active" and heartbeat > last.get("accounted_wall_seconds", 0) * 2:
        anomalies.append({"kind": "session_closed_early_but_generation_continued",
                          "closed_status": last["status"], "accounted_wall_seconds": last["accounted_wall_seconds"],
                          "runtime_heartbeat_elapsed_seconds": heartbeat,
                          "candidate_wall_seconds": {r["candidate_id"]: r["wall_seconds"] for r in ledger["candidate_runs"]}})
    return {"checks": checks, "audit_pass": all(checks.values()), "per_profile": per, "failures": failures,
            "stage_seconds_per_call": {c: {s: describe(v) for s, v in d.items()} for c, d in stage_times.items()},
            "ledger": {k: ledger[k] for k in ("cpu_seconds", "gpu_seconds", "transfer_bytes", "checkpoint_bytes",
                                             "checkpoint_flush_seconds", "completed_session_wall_seconds",
                                             "session_elapsed_wall_seconds")},
            "ledger_sessions": [{"status": r["status"], "accounted_wall_seconds": r.get("accounted_wall_seconds")} for r in ledger["session_runs"]],
            "candidate_runs": ledger["candidate_runs"], "anomalies": anomalies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--manifest-sha", required=True)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.extracted, args.package, args.manifest_sha)
    result.update(schema_version=1, protocol_id="tib-selection300-generation-261023-v1", evidence_zip_sha256=sha(args.zip),
                  scope="text-free audit of selection300 generation evidence; no ranking, no selection")
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": result["audit_pass"], "failed": [k for k, v in result["checks"].items() if not v]}))


if __name__ == "__main__":
    main()
