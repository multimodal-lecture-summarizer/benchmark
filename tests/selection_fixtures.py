"""Miniature selection bundle, ledger and dependency fixtures shared by the selection-stage tests.

Clocks here use the real monotonic domain: the node-checkpoint generator compares its deadline with
time.monotonic(), so a fixed fake clock would pass or fail depending on machine uptime.
"""
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from contextlib import nullcontext

from experiments.scripts import tib_selection_validation as validation
from experiments.scripts.tib_benchmark_acceptance import ACCEPTANCE_POLICY
from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_p4_generation_recovery import sha

SCRIPTS = Path(__file__).resolve().parents[1] / "experiments/scripts"
REGISTRY = Path(__file__).resolve().parents[1] / "experiments/registry/protocols/tib-selection300-binding-261023-v1"
MINI_QUOTAS = {"short": 2, "medium": 2, "long": 2}
TEXT = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."


def real_allocation():
    return json.loads((REGISTRY / "compute_budget_selection300.json").read_text(encoding="utf-8"))


def mini_bundle(root, monkeypatch, n=6):
    """Bundle that satisfies validate_bundle once SELECTION_N/QUOTAS are shrunk to the miniature."""
    monkeypatch.setattr(validation, "SELECTION_N", n)
    monkeypatch.setattr(validation, "QUOTAS", dict(MINI_QUOTAS))
    root = Path(root)
    root.mkdir(parents=True)
    strata = ["short", "medium", "long"] * (n // 3)
    ids = [f"valid:{2000 + i}" for i in range(n)]
    rows = [{"record_id": i, "source_normalized": TEXT, "source_normalized_sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
             "source_stratum": s, "source_words": len(TEXT.split()), "attribution": {"creator": "fixture"}}
            for i, s in zip(ids, strata)]
    original = root / "original_generation"
    original.mkdir()
    cpu = [{"candidate_id": c} for c in validation.CANDIDATES[:2]]
    trials = [{"candidate_id": c, "trial_id": p, "profile": {"candidate_id": c, "architecture": "encoder_decoder", "decode": {}}}
              for c, p in validation.PREFERRED.items()]
    (original / "candidate_profiles.json").write_text(json.dumps({"pipelines": cpu}))
    (original / "development_trials.json").write_text(json.dumps({"trials": trials}))
    (original / "bundle_manifest.json").write_text(json.dumps({"files": {p.name: sha(p) for p in original.iterdir()}}))
    profiles = []
    for c in validation.CANDIDATES:
        body = next((t["profile"] for t in trials if t["candidate_id"] == c), {"candidate_id": c})
        profiles.append({"candidate_id": c, "profile_id": validation.PREFERRED.get(c, c), "profile": body,
                         "profile_sha256": digest(body)})
    # CPU profiles must equal the frozen pipeline entries.
    for p in profiles:
        if p["candidate_id"] in ("lead3", "lexrank"):
            p["profile"] = {"candidate_id": p["candidate_id"]}
            p["profile_sha256"] = digest(p["profile"])
    policy = dict(ACCEPTANCE_POLICY)
    for prefix, name in [("classifier", "tib_benchmark_acceptance.py"), ("diagnostic_rules", "tib_benchmark_generation_telemetry.py")]:
        relative = "experiments/scripts/" + name
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((SCRIPTS / name).read_bytes())
        policy.update({prefix + "_path": relative, prefix + "_sha256": sha(target)})
    policy["technical_contracts"] = ["fixture"]
    (root / "acceptance_policy.json").write_text(json.dumps(policy))
    allocation = real_allocation()
    (root / "selection_allocation.json").write_text(json.dumps(allocation))
    locked = root / validation.LOCKED_DIR
    locked.mkdir()
    (locked / "output_policy_v2.json").write_text('{"derived_global_word_cap": 350}')
    contract = {"selection_ids": ids, "source_strata": dict(zip(ids, strata)), "quotas": dict(MINI_QUOTAS),
                "staged_ids": [], "excluded_pilot_ids": [f"valid:{i}" for i in range(40)],
                "candidate_order": validation.CANDIDATES, "word_cap": 350, "profiles": profiles,
                "selection_authorized": False, "final_test_authorized": False, "expected_cells": n * 4,
                "locked_artifacts": {"output_policy_v2.json": sha(locked / "output_policy_v2.json")},
                "allocation_sha256": digest(allocation), "acceptance_policy_sha256": sha(root / "acceptance_policy.json"),
                "original_bundle_manifest_sha256": sha(original / "bundle_manifest.json")}
    (root / "selection_contract.json").write_text(json.dumps(contract))
    (root / "selection_sources.jsonl").write_text("\n".join(map(json.dumps, rows)))
    (root / "node_forecast.json").write_text(json.dumps({
        "rule": "1.5x max observed Pilot40 node", "load_seconds": {"bart": 1.0, "led": 1.0},
        "stage_seconds": {"bart": {"map": 1.0, "reduce": 1.0, "final": 1.0}, "led": {"map": 1.0, "reduce": 1.0, "final": 1.0}}}))
    (root / "actual_recovery_receipt.json").write_text(json.dumps({
        "status": "PASS", "cross_session_recovery_verified": True, "new_generation_calls": 0, "new_metric_calls": 0}))
    (root / "actual_scorer_ready_receipt.json").write_text('{"status":"PASS","test_only":false}')
    refresh(root)
    return contract, rows


def refresh(root):
    (Path(root) / validation.MANIFEST).write_text(json.dumps({"files": {
        p.relative_to(root).as_posix(): sha(p) for p in Path(root).rglob("*")
        if p.is_file() and p.name != validation.MANIFEST}}))


def authorization(bundle):
    return {"manifest_sha256": sha(Path(bundle) / validation.MANIFEST), "readiness_receipt_v2_sha256": "a" * 64,
            "authorized_by": "user", "authorized_on": "2026-10-24", "statement": "start selection300 generation"}


def ledger(path, allocation, bundle, **updates):
    """Active session ledger whose clock is the real monotonic clock."""
    now = time.monotonic()
    value = dict(session_started_monotonic=now - 1, boot_id="boot", cpu_seconds=10, gpu_seconds=0, transfer_bytes=0,
                 checkpoint_bytes=0, checkpoint_flush_seconds=0, candidate_runs=[], allocation_sha256=digest(allocation),
                 bundle_sha256=sha(Path(bundle) / validation.MANIFEST), completed_session_wall_seconds=0,
                 session_limit_seconds=5.0 * 3600, session_runs=[{"boot_id": "boot"}], local_working_root="/content/work",
                 session_status="active")
    value.update(updates)
    (Path(path) / "resource_ledger.json").write_text(json.dumps(value))
    return value


def dependencies(bundle):
    return SimpleNamespace(
        validate_bundle=validation.validate_bundle,
        resources=SimpleNamespace(clock=time.monotonic, cpu_clock=time.process_time, boot_id="boot"),
        environment=lambda candidate: {"device_name": "cpu", "cpu_packages": {"fixture": True}},
        sample=lambda neural: nullcontext({"wall_seconds": 0, "cpu_seconds": 0, "cuda_peak_reserved_bytes": None}))
