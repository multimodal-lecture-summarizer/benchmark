"""Synthetic final523 generation evidence (523 IDs x 4 profiles) for the generation audit; no real data.

IDs are `test:` shaped, as in the sealed cohort, but are fabricated and live under tmp_path only.
"""
import hashlib
import json
import os
import random
import shutil
from pathlib import Path
from types import SimpleNamespace

from experiments.scripts.tib_benchmark_checkpoint import digest

PROFILES = ("lead3", "lexrank", "bart", "led")
GRANT = 18900.0   # 5.25 h session grant
ALLOCATION = {"stage": "final523", "total_gpu_hours": 21, "max_sessions": 4, "records_per_pipeline": 523}


def sha_text(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_text(path, text):
    """Write by replacing the file, never in place: clones share inodes with the base world through hard links."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    path.write_text(text, encoding="utf-8")


def write_json(path, value):
    replace_text(path, json.dumps(value))


def make_ids():
    ids = [f"test:{i:03d}" for i in range(1, 524)]
    strata = ["short"] * 182 + ["medium"] * 172 + ["long"] * 169
    random.Random(5).shuffle(strata)
    return ids, dict(zip(ids, strata))


def record_payload(ident, stratum, status, binding=None):
    base = {"record_id": ident, "status": status, "binding": binding, "runtime_sha256": "r" * 64, "source_sha256": sha_text("source " + ident), "source_stratum": stratum,
            "origin": "fresh", "quality": None, "automatic_retry": False, "retain_in_denominator": True,
            "events": [{"status": status}], "stage_resources": [], "resources": {"cuda_peak_reserved_bytes": 1}}
    if status == "failed":
        return {**base, "error": "AdapterFailure: reduction does not reduce"}
    if status == "started":
        return base
    return {**base, "result": {"delivery": {"delivered_words": 40, "capped": False, "forced_word_boundary": False, "raw_words": 40}},
            "validation": {"acceptance": {"warnings": ["sentence_ending"] if status == "completed_with_warning" else []}},
            "stage_resources": [{"stage": "map", "wall_seconds": 1.5}]}


def clone_world(world, tmp_path):
    """A private tree of hard links to a built world: tamper by replacing files (write_json/replace_text), never in place."""
    root = Path(tmp_path) / "gen-world"
    shutil.copytree(world.root, root, copy_function=os.link)
    return SimpleNamespace(**{**vars(world), "root": root, "pkg": root / "bundle", "extracted": root / "extracted",
                              "sel": root / "extracted" / "selection"})


def make_generation_world(tmp_path, failed=(), interrupted=()):
    """Bundle package + extracted evidence (`selection/`, `package/`) as the last evidence ZIP would hold them."""
    root = Path(tmp_path) / "gen-world"
    pkg, extracted = root / "bundle", root / "extracted"
    ids, strata = make_ids()
    profile_sha = {p: sha_text("profile " + p) for p in PROFILES}
    write_json(pkg / "locked/final_cohort.json", {"selected_ids": ids})
    write_json(pkg / "selection_allocation.json", ALLOCATION)
    (pkg / "selection_sources.jsonl").write_text("".join(json.dumps(
        {"record_id": i, "source_normalized_sha256": sha_text("source " + i), "source_stratum": strata[i]}) + "\n" for i in ids), encoding="utf-8")
    contract = {"stage": "final523", "selection_ids": ids, "source_strata": strata, "candidate_order": list(PROFILES),
                "profiles": [{"candidate_id": p, "profile_sha256": profile_sha[p]} for p in PROFILES],
                "excluded_pilot_ids": [f"valid:p{i}" for i in range(40)], "excluded_selection_ids": [f"valid:s{i}" for i in range(300)],
                "selection_authorized": False, "final_test_authorized": False, "allocation_sha256": digest(ALLOCATION),
                "acceptance_policy_sha256": "a" * 64, "final_cohort_sha256": sha_file(pkg / "locked/final_cohort.json")}
    write_json(pkg / "selection_contract.json", contract)
    files = ("selection_contract.json", "selection_sources.jsonl", "selection_allocation.json", "locked/final_cohort.json")
    write_json(pkg / "selection_manifest.json", {"files": {name: sha_file(pkg / name) for name in files}})
    manifest_sha = sha_file(pkg / "selection_manifest.json")
    shutil.copytree(pkg, extracted / "package")
    sel = extracted / "selection"
    identity_of = {}
    for profile in PROFILES:
        identity_of[profile] = {"candidate_id": profile, "profile_sha256": profile_sha[profile], "bundle_sha256": manifest_sha,
                                "allocation_sha256": contract["allocation_sha256"], "acceptance_policy_sha256": "a" * 64, "profile_id": profile}
    for profile in PROFILES:
        counts = {}
        for ident in ids:
            status = ("failed" if (profile, ident) in failed else "started" if (profile, ident) in interrupted else
                      "completed_with_warning" if profile in ("bart", "led") and int(ident[5:]) % 10 == 0 else "completed")
            payload = record_payload(ident, strata[ident], status, identity_of[profile])
            counts[status] = counts.get(status, 0) + 1
            write_json(sel / profile / "records" / (sha_text(ident) + ".json"), {"payload": payload, "sha256": digest(payload)})
        bad = counts.get("failed", 0) + counts.get("started", 0)
        write_json(sel / profile / "candidate_receipt.json", {
            "status": "COMPLETED_WITH_FAILURES" if bad else "PASS", "new_generation_calls": 10, "new_generation_wall_seconds": 5.0,
            "total_wall_seconds": 6.0, "model_load_wall_seconds": 1.0,
            "summary": {"denominator": 523, "pending": 0, "successful": counts.get("completed", 0) + counts.get("completed_with_warning", 0),
                        "failed_or_interrupted": bad, "status_counts": counts}})
        identity = identity_of[profile]
        write_json(sel / profile / "run_identity.json", {"payload": identity, "sha256": digest(identity)})
    write_json(sel / "preflight_receipt.json", {"status": "PASS", "device_name": "Tesla T4"})
    write_json(sel / "start_authorization.json", {"manifest_sha256": manifest_sha, "readiness_receipt_v2_sha256": "b" * 64,
                                                  "authorized_by": "user", "authorized_on": "2026-11-01", "statement": "start final523"})
    write_json(sel / "selection_summary.json", {"metrics_executed": False, "selection_start_authorized": False})
    ledger = {"allocation": ALLOCATION, "allocation_sha256": contract["allocation_sha256"], "bundle_sha256": manifest_sha,
              "gpu_seconds": 8700 + 11200 + 600.0, "cpu_seconds": 9000.0, "transfer_bytes": 1, "checkpoint_bytes": 1,
              "checkpoint_flush_seconds": 1.0, "completed_session_wall_seconds": 19500.0, "session_elapsed_wall_seconds": 11300.0,
              "candidate_runs": [{"candidate_id": "lead3", "wall_seconds": 20.0, "cpu_seconds": 5.0},
                                 {"candidate_id": "lexrank", "wall_seconds": 30.0, "cpu_seconds": 15.0},
                                 {"candidate_id": "bart", "wall_seconds": 8700.0, "cpu_seconds": 4000.0},
                                 {"candidate_id": "led", "wall_seconds": 11200.0, "cpu_seconds": 4500.0}],
              "session_runs": [{"status": "evidence_exported", "granted_wall_seconds": GRANT, "accounted_wall_seconds": 9000.0},
                               {"status": "evidence_exported", "granted_wall_seconds": GRANT, "accounted_wall_seconds": 11300.0}]}
    write_json(sel / "resource_ledger.json", ledger)
    return SimpleNamespace(root=root, pkg=pkg, extracted=extracted, sel=sel, manifest_sha=manifest_sha, ids=ids, strata=strata,
                           contract=contract, ledger=ledger, profile_sha=profile_sha)
