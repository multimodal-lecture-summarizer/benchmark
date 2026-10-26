"""Synthetic final523 scoring evidence (12 IDs x 4 profiles, one failed LED cell) for the scoring audit; no real data.

The tree mirrors the returned evidence: evidence/ (receipt, metrics, views, checkpoints, archived runs), bundle/
(contract, resume policy) and the ledger after scoring. A resumed variant has two runs: the first cut short after five
rows, the second reusing them. All values are fabricated.
"""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

from experiments.scripts import tib_final523_scoring_audit as audit_module
from experiments.scripts.tib_final523_scorer_validation import FINAL_STAGE, RESUME_POLICY
from experiments.scripts.tib_scorer_colab_checkpoint import digest, file_sha
from experiments.scripts.tib_selection300_scorer_bundle import BINDING

PROFILES = ("lead3", "lexrank", "bart", "led")
IDS = [f"fixture:{i:02d}" for i in range(12)]
STRATUM = {i: ("short", "medium", "long")[n % 3] for n, i in enumerate(IDS)}
FAILED = "led__fixture-05"
METRIC_NAMES = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1", "source_sentence_similarity_v1")
VIEW_NAMES = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1")
BUNDLE_SHA, GEN_ZIP_SHA, GEN_MANIFEST = "b" * 64, "e" * 64, "c" * 64
RUN_KILLED, RUN_FIRST, RUN_FINAL = "1000", "2000", "3000"
POLICY_PATH = Path(audit_module.__file__).parents[1] / "registry/protocols/tib-final523-scoring-261024-v1" / RESUME_POLICY
RUNTIME = {"google_colab_imported": True, "google_colab_module": "/colab", "cuda_available": True, "device_name": "Tesla T4",
           "T4_device_observed": True, "device_memory_bytes": 15 * 1024**3, "cuda_runtime": "12.4", "python": "3.11.9",
           "platform": "Linux-6.1", "packages": {"torch": "2.5"}, "logical_cpu_count": 2, "torch_cpu_threads": 2, "torch_interop_threads": 2}


def sample_id(profile, record):
    return f"{profile}__{record.replace(':', '-')}"


def write(path, value, lines=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if lines:
        path.write_text("".join(json.dumps(v) + "\n" for v in value), encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def metric_row(profile, record, reused=False):
    sid = sample_id(profile, record)
    base = {"sample_id": sid, "record_id": record, "profile_id": profile, "source_stratum": STRATUM[record], "reused": reused}
    if sid == FAILED:
        return {**base, "scoring_status": "not_scoreable_generation_failed", "metrics": dict.fromkeys(METRIC_NAMES),
                "failures": {"record": "AdapterFailure: x"}, "new_scoring_wall_seconds": 0.0}
    return {**base, "scoring_status": "completed", "failures": {}, "metrics": dict.fromkeys(METRIC_NAMES, 0.3),
            "new_scoring_wall_seconds": 0.0 if reused else 4.0, "bertscore_seconds": 3.0, "source_similarity_seconds": 0.5,
            "rouge_and_other_seconds": 0.5}


def view_row(profile, record, reused=False):
    return {"sample_id": sample_id(profile, record), "record_id": record, "profile_id": profile, "source_stratum": STRATUM[record],
            "views": {v: {"metrics": dict.fromkeys(VIEW_NAMES, 0.2), "failures": {}} for v in "SML"}, "reused_view": {}}


def checkpoint(folder, binding, sid, run_id, runtime_digest):
    key = {"binding": binding, "sample_id": sid, "input_sha256": "d" * 64}
    payload = {"key": key, "result": {"metrics": {}, "failures": {}}, "original_scoring_wall_seconds": 1.0,
               "provenance": {"run_id": run_id, "runtime_full_sha256": runtime_digest}}
    write(Path(folder) / (digest(key) + ".json"), {"payload": payload, "sha256": digest(payload)})


def make_scoring_world(tmp_path, resumed=False):
    root = Path(tmp_path) / ("resumed" if resumed else "fresh")
    extracted = root / "extracted"
    evidence, bundle = extracted / "evidence", extracted / "bundle"
    pairs = [(p, i) for i in IDS for p in PROFILES]
    rows_all = [(p, i) for p, i in pairs]
    scoreable = [(p, i) for p, i in rows_all if sample_id(p, i) != FAILED]
    first_run = scoreable[:5] if resumed else []
    reused = {sample_id(p, i) for p, i in first_run}
    rows = [metric_row(p, i, reused=sample_id(p, i) in reused) for p, i in rows_all]
    views = [view_row(p, i) for p, i in scoreable]
    binding = {"package_manifest_sha256": BUNDLE_SHA, "evidence_zip_sha256": GEN_ZIP_SHA, "runtime_sha256": digest({"portable": 1})}
    run_id = RUN_FINAL
    write(evidence / "metrics.jsonl", rows, lines=True)
    write(evidence / "view_metrics.jsonl", views, lines=True)
    costs = {"resources": {"wall_seconds": 3900.0, "cpu_seconds": 3800.0, "cuda_peak_reserved_bytes": 1000},
             "total_wall_seconds": 4000.0, "reused_original_scoring_seconds": 5.0 if resumed else 0.0}
    write(evidence / "cost_evidence.json", costs)
    write(evidence / "PASS_HOLD_report.json", {"delivered_status": "PASS"})
    full = digest(RUNTIME)
    receipt = {"delivered_status": "PASS", "views_status": "COMPLETE", "reasons": [], FINAL_STAGE["ready_key"]: True, "T4_verified": True,
               "testing_dependency_injection": False, "fixtures": {"status": "pass"}, "runtime": RUNTIME, "binding": binding, "run_id": run_id,
               "qwen3_scored": False, "generation_executed": False, "selection_start_authorized": False,
               "successful_metric_records": len(scoreable), "failed_generation_cells": 1,
               "artifact_sha256": {n: file_sha(evidence / n) for n in ("cost_evidence.json", "PASS_HOLD_report.json", "metrics.jsonl", "view_metrics.jsonl")}}
    if resumed:
        canary_ids = sorted(reused)[:3]
        receipt.update(partial_resume_requested=True, partial_resume_used=True, reused_rows=len(reused), fresh_rows=len(scoreable) - len(reused),
                       reused_failed_rows=0, run_ids=[RUN_FIRST, RUN_FINAL], mixed_runtime=False, quarantined=[],
                       canary={"tolerance": 1e-6, "sample_ids": canary_ids, "max_abs_diff": 0.0, "passed": True},
                       reused_original_scoring_seconds=5.0, runtime_full_sha256_by_run={RUN_FIRST: full, RUN_FINAL: full})
    write(evidence / "scorer_final523_receipt.json", receipt)
    for index, (p, i) in enumerate(scoreable):
        owner = RUN_FIRST if index < len(first_run) else RUN_FINAL
        checkpoint(evidence / "checkpoints", binding, sample_id(p, i), owner, full)
        checkpoint(evidence / "view_checkpoints", binding, sample_id(p, i) + "__views", owner, full)
    (evidence / "runs" / RUN_KILLED).mkdir(parents=True)
    runs = {RUN_FINAL: (rows, "PASS", "COMPLETE")}
    if resumed:
        first_rows = [metric_row(p, i) for p, i in first_run] + [dict(metric_row(p, i), scoring_status="not_attempted", metrics=dict.fromkeys(METRIC_NAMES))
                                                               for p, i in scoreable[5:6]]
        runs[RUN_FIRST] = (first_rows, "HOLD", "NOT_STARTED")
    for rid, (run_rows, status, view_status) in runs.items():
        write(evidence / "runs" / rid / "metrics.jsonl", run_rows, lines=True)
        write(evidence / "runs" / rid / "cost_evidence.json", {"total_wall_seconds": 1000.0})
        write(evidence / "runs" / rid / "scorer_final523_receipt.json",
              {"delivered_status": status, "views_status": view_status, "reasons": [] if status == "PASS" else ["session_deadline"], "runtime": dict(RUNTIME), "quarantined": []})
    policy = POLICY_PATH.read_bytes()
    bundle.mkdir(parents=True)
    (bundle / RESUME_POLICY).write_bytes(policy)
    write(bundle / "runtime_amendment.json", {"runtime_pins": {"torch": "2.5"}, "support_package_pins": {}})
    contract = {"stage": "final523", "scoring_start_authorized": False, "selection_rule_applied": False, "expected_rows": len(rows_all),
                "expected_scoreable": len(scoreable), "expected_failed": 1, "failed_cells": [FAILED], "selection_ids": IDS,
                "source_strata": STRATUM, "quotas": {"short": 4, "medium": 4, "long": 4}, "profile_order": list(PROFILES),
                "generation_evidence_zip_sha256": GEN_ZIP_SHA, "generation_bundle_manifest_sha256": GEN_MANIFEST,
                "resume_policy_sha256": file_sha(bundle / RESUME_POLICY)}
    write(bundle / "scoring_contract.json", contract)
    ledger = {"bundle_sha256": GEN_MANIFEST, "gpu_seconds": 20000.0,
              "session_runs": [{"status": "evidence_exported", "granted_wall_seconds": 18900.0, "accounted_wall_seconds": 9000.0},
                               {"status": "scoring_evidence_exported", "granted_wall_seconds": 18900.0, "accounted_wall_seconds": 4100.0,
                                "measured_wall_seconds": 4100.0}]}
    allocation = {"max_sessions": 4, "total_gpu_hours": 21}
    rules = json.loads((BINDING / "admission_rules_v2.json").read_text(encoding="utf-8"))
    return SimpleNamespace(root=root, extracted=extracted, evidence=evidence, bundle=bundle, contract=contract, ledger=ledger,
                           allocation=allocation, rules=rules, policy_path=POLICY_PATH, reused=reused, run_id=run_id, binding=binding)


def clone(world, tmp_path):
    destination = Path(tmp_path) / world.root.name
    shutil.copytree(world.root, destination)
    return SimpleNamespace(**{**vars(world), "root": destination, "extracted": destination / "extracted",
                              "evidence": destination / "extracted" / "evidence", "bundle": destination / "extracted" / "bundle",
                              "contract": json.loads(json.dumps(world.contract)), "ledger": json.loads(json.dumps(world.ledger)),
                              "allocation": dict(world.allocation)})
