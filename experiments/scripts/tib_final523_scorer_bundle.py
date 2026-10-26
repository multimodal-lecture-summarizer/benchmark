"""Package the 2,092 final523 generation cells and the frozen scorer v2 code for private Colab scoring.

Built from the final523 generation evidence ZIP, so it can only be produced after generation has run and been
audited; until then the builder is exercised on synthetic evidence only. It reuses the selection300 scoring-bundle
helpers (row identity checks, generation hash cross-check, pins, frozen scorer code) and differs in the sealed IDs,
the derived scoreable count and a byte-reproducible ZIP. The bundle holds sources and references, so it stays
private; the text-free registry copy carries hashes and counts. Failed cells stay in the denominator as NULL rows.
"""
import argparse
import json
import math
from pathlib import Path
import shutil

from experiments.scripts import tib_final523_scorer_validation as validation
from experiments.scripts.tib_final523_bundle import FINAL_COHORT, REGISTRY as GENERATION_REGISTRY, deterministic_zip
from experiments.scripts.tib_pilot40_scorer_bundle import PROFILES, VIEW_BUDGETS
from experiments.scripts.tib_scorer_colab_bundle import PINS, SUPPORT, file_hash, write_json
from experiments.scripts.tib_selection300_scorer_bundle import (
    BINDING, COHORT as DEVELOPMENT_COHORT, EXCLUDED, MAX_ARCHIVE_BYTES, PILOT40_AMENDMENT, PILOT40_REQUIREMENTS, QUALIFICATION,
    ROOT, SCRIPTS as SELECTION_SCRIPTS, SPEC, _requirements, generation_hashes, selection_scoring_rows,
)
from experiments.scripts.tib_stage_resources import validate_stage_allocation
from experiments.scripts.tib_stage_session import digest

PROTOCOLS = ROOT / "experiments/registry/protocols"
REGISTRY = PROTOCOLS / "tib-final523-scoring-261024-v1"
LOCAL = ROOT / "research-data/tib-final523-scoring-261024-v1"
AMENDMENT_ID = "tib-final523-scoring-261024-v1"
ARCHIVE_NAME = "tib-final523-scoring-261024-v1.zip"
SCRIPTS = SELECTION_SCRIPTS + ["tib_final523_scorer_validation"]
RESUME_POLICY_PATH = REGISTRY / validation.RESUME_POLICY
BUDGET_DECISION_PATH = REGISTRY / validation.BUDGET_DECISION


def scoring_allocation(generation_allocation, generation_outcome, decision, decision_sha256):
    """The approved final523 allocation, re-cut for scoring: `scoring_max_sessions` sessions, every ceiling reduced to what the
    audited generation ledger left (rounded down), so generation use plus the scoring ceiling never exceeds the approved total.

    The generation ledger is not touched; scoring runs on its own ledger bound to the same generation bundle hash.
    """
    used = {key: generation_outcome["ledger"][key] for key in ("gpu_seconds", "cpu_seconds", "transfer_bytes",
                                                               "completed_session_wall_seconds")}
    sessions_used = len(generation_outcome["ledger_sessions"])
    if (decision.get("declared_by") != "user" or decision.get("post_hoc") is not False
            or not isinstance(decision.get("scoring_max_sessions"), int) or decision["scoring_max_sessions"] < 1):
        raise ValueError("The scoring budget decision must be the user's pre-run declaration with a session count")

    def left_hours(total_hours, used_seconds):
        return math.floor((total_hours * 3600 - used_seconds) / 36) / 100   # hours, rounded down to 0.01

    hours = min(left_hours(generation_allocation["total_gpu_hours"], used["gpu_seconds"]),
                left_hours(generation_allocation["total_wall_hours"], used["completed_session_wall_seconds"]))
    allocation = dict(generation_allocation)
    allocation.update(
        max_sessions=decision["scoring_max_sessions"], total_gpu_hours=hours, total_wall_hours=hours,
        total_cpu_hours=left_hours(generation_allocation["total_cpu_hours"], used["cpu_seconds"]),
        transfer_bytes=int(generation_allocation["transfer_bytes"] - used["transfer_bytes"]))
    if (hours < generation_allocation["scoring_gpu_hours"] or allocation["total_cpu_hours"] < generation_allocation["scoring_cpu_hours"]
            or allocation["transfer_bytes"] <= 0):
        raise ValueError("What generation left does not cover the scoring reserve; stop and ask")
    allocation["carved_from_generation"] = {
        "generation_allocation_sha256": digest(generation_allocation), "decision_sha256": decision_sha256,
        "generation_outcome_sessions_used": sessions_used, "generation_ledger_used": used,
        "generation_approved": {key: generation_allocation[key] for key in (
            "total_gpu_hours", "total_cpu_hours", "total_wall_hours", "transfer_bytes", "max_sessions")},
        "rule": "scoring ceiling = approved total minus generation use, rounded down; generation ledger untouched"}
    validate_stage_allocation(allocation)   # the same numeric contract begin_session enforces
    return allocation


def build(evidence_zip, expected_evidence_sha, generation_outcome, local=LOCAL, registry=REGISTRY,
          qualification=QUALIFICATION, final_cohort_path=GENERATION_REGISTRY / FINAL_COHORT,
          development_cohort_path=DEVELOPMENT_COHORT, binding=BINDING, generation_registry=GENERATION_REGISTRY,
          resume_policy_path=RESUME_POLICY_PATH, budget_decision_path=BUDGET_DECISION_PATH):
    """`generation_outcome` is the passing audit of the generation evidence; without it nothing is packaged."""
    local, registry, binding = Path(local), Path(registry), Path(binding)
    if file_hash(evidence_zip) != expected_evidence_sha:
        raise ValueError("Final523 evidence ZIP hash changed")
    outcome = json.loads(Path(generation_outcome).read_text(encoding="utf-8"))
    if outcome.get("audit_pass") is not True:
        raise ValueError("Generation evidence did not pass its audit; scoring is not packaged")
    if outcome.get("evidence_zip_sha256") != expected_evidence_sha:
        raise ValueError("The passing audit belongs to another evidence ZIP")
    policy = json.loads(Path(resume_policy_path).read_text(encoding="utf-8"))
    if (policy.get("partial_resume_allowed") is not True or policy.get("declared_by") != "user"
            or policy.get("post_hoc") is not False or policy.get("flag") != "--resume-partial"):
        raise ValueError("The partial-resume policy must be the user's pre-run declaration")
    from experiments.scripts import tib_pilot40_scorer_runner as runner
    if (policy["canary"]["rows"] != runner.CANARY_ROWS or policy["canary"]["tolerance_absolute_per_metric"] != runner.CANARY_TOLERANCE
            or tuple(policy["runtime_binding"]["bound"]) != runner.PORTABLE_RUNTIME_FIELDS):
        raise ValueError("The partial-resume policy numbers differ from the runner's canary and binding constants")
    cohort = json.loads(Path(final_cohort_path).read_text(encoding="utf-8"))
    development = json.loads(Path(development_cohort_path).read_text(encoding="utf-8"))["selected_ids"]
    ids = cohort["selected_ids"]
    if cohort["final_test_sealed"] is not True or len(ids) != validation.EXPECTED_IDS:
        raise ValueError("Final cohort is not the sealed 523 IDs")
    rows = selection_scoring_rows(evidence_zip, qualification, None, binding / "selection300_profiles_v2.json",
                                  ids=ids, excluded_ids=development["pilot"] + development["selection"],
                                  interrupted_as_failed=True)
    scoreable = sum(r["scoreable"] for r in rows)
    if len(rows) != validation.EXPECTED_ROWS or scoreable == 0:
        raise ValueError(f"Expected {validation.EXPECTED_ROWS} rows with scoreable cells, got {len(rows)}/{scoreable}")
    generation_manifest, generation_allocation = generation_hashes(evidence_zip, generation_registry)
    if generation_allocation["stage"] != "final523":
        raise ValueError("Evidence was generated under another stage allocation")
    decision = json.loads(Path(budget_decision_path).read_text(encoding="utf-8"))
    allocation = scoring_allocation(generation_allocation, outcome, decision, file_hash(budget_decision_path))
    freeze = json.loads((binding / "scorer_freeze_receipt.json").read_text(encoding="utf-8"))
    if file_hash(PILOT40_AMENDMENT) != freeze["runtime_amendments"]["pilot40_scoring_sha256"]:
        raise ValueError("Pilot40 scoring runtime amendment differs from the freeze receipt")
    pilot_amendment = json.loads(PILOT40_AMENDMENT.read_text(encoding="utf-8"))
    if pilot_amendment["runtime_pins"] != PINS or pilot_amendment["support_package_pins"] != SUPPORT:
        raise ValueError("Runtime pins differ from the audited Pilot40 scoring amendment")
    requirements = PILOT40_REQUIREMENTS.read_bytes()
    if (file_hash(PILOT40_REQUIREMENTS) != freeze["requirements_sha256"]
            or requirements.decode("utf-8").replace("\r\n", "\n") != _requirements()):
        raise ValueError("Requirements differ from the frozen, verified requirements")

    bundle = local / "bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    scripts = bundle / "experiments/scripts"
    scripts.mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copyfile(ROOT / "experiments/scripts" / (name + ".py"), scripts / (name + ".py"))
    for relative in ("experiments/__init__.py", "experiments/scripts/__init__.py"):
        (bundle / relative).write_text("", encoding="utf-8")
    shutil.copyfile(SPEC, bundle / "frozen_scorer_spec.json")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if file_hash(SPEC) != freeze["scorer_spec"]["sha256"]:
        raise ValueError("Scorer spec differs from the freeze receipt")
    for relative, expected in spec["code_sha256"].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError("Frozen scorer implementation changed: " + relative)
        (bundle / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, bundle / relative)

    failed = [r["sample_id"] for r in rows if not r["scoreable"]]
    amendment = {
        "schema_version": 1, "amendment_id": AMENDMENT_ID,
        "state": "PREPARED_HOLD_ACTUAL_COLAB_EXECUTION_REQUIRED",
        "runtime_pins": PINS, "support_package_pins": SUPPORT,
        "frozen_spec_sha256": file_hash(bundle / "frozen_scorer_spec.json"),
        "pilot40_scoring_amendment_sha256": file_hash(PILOT40_AMENDMENT),
        "evidence_zip_sha256": expected_evidence_sha,
        "expected_output_count": len(rows), "expected_scoreable_count": scoreable,
        "profile_ids": list(PROFILES), "excluded_profiles": EXCLUDED,
        "views": {"budgets_words": VIEW_BUDGETS, "metrics": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
                  "source_similarity": "not computed on views"},
        "preserved": "scorer v2 metrics, windows, IDF=false, FP32 and the 350-word cap are unchanged",
        "scope": "Final523 reference scoring; confirms the locked choice, selection rule not re-run here",
        "selection_start_authorized": False, "generation_allowed": False,
    }
    write_json(bundle / "runtime_amendment.json", amendment)
    contract = {
        "schema_version": 1, "scope": "Final523 scoring only; no generation, no selection rule",
        "stage": "final523", "selection_ids": ids,
        "source_strata": {r["record_id"]: r["source_stratum"] for r in rows[::len(PROFILES)]},
        "quotas": validation.FINAL_QUOTAS, "profile_order": list(PROFILES),
        "expected_rows": len(rows), "expected_scoreable": scoreable, "expected_failed": len(failed), "failed_cells": failed,
        "generation_evidence_zip_sha256": expected_evidence_sha,
        "generation_bundle_manifest_sha256": generation_manifest,
        "allocation_sha256": digest(allocation), "generation_allocation_sha256": digest(generation_allocation),
        "scorer_freeze_receipt_sha256": file_hash(binding / "scorer_freeze_receipt.json"),
        "admission_rules_v2_sha256": file_hash(binding / "admission_rules_v2.json"),
        "decisions_sha256": file_hash(binding / "decisions_261023_v1.json"),
        "final_cohort_sha256": file_hash(final_cohort_path),
        "final_generation_outcome_sha256": file_hash(generation_outcome),
        "reported_metrics": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
        "metrics_computed_not_reported": ["source_sentence_similarity_v1"],
        "scoring_start_authorized": False, "selection_rule_applied": False,
    }
    shutil.copyfile(resume_policy_path, bundle / validation.RESUME_POLICY)
    contract["resume_policy_sha256"] = file_hash(bundle / validation.RESUME_POLICY)
    shutil.copyfile(budget_decision_path, bundle / validation.BUDGET_DECISION)
    contract["scoring_budget_decision_sha256"] = file_hash(bundle / validation.BUDGET_DECISION)
    write_json(bundle / validation.CONTRACT, contract)
    write_json(bundle / "selection_allocation.json", allocation)
    # Bytes, not write_text: Windows newline translation would change the hashed content.
    (bundle / validation.OUTPUTS).write_bytes(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8"))
    (bundle / "requirements-colab-t4.txt").write_bytes(requirements)
    manifest = {"schema_version": 1, "files": {
        p.relative_to(bundle).as_posix(): file_hash(p) for p in sorted(bundle.rglob("*"))
        if p.is_file() and p.name != "package_manifest.json" and "__pycache__" not in p.parts}}
    write_json(bundle / "package_manifest.json", manifest)
    validation.validate_final_scoring_bundle(bundle)

    registry.mkdir(parents=True, exist_ok=True)
    for name in ("runtime_amendment.json", validation.CONTRACT, "requirements-colab-t4.txt", "package_manifest.json"):
        shutil.copyfile(bundle / name, registry / name)
    shutil.copyfile(bundle / "selection_allocation.json", registry / "scoring_allocation.json")
    archive = local / ARCHIVE_NAME
    deterministic_zip(archive, bundle, list(manifest["files"]) + ["package_manifest.json"])
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError(f"Scoring ZIP is {archive.stat().st_size} bytes (> 50 MB); stop and ask")
    receipt = {"schema_version": 1, "status": "HOLD", "scorer_ready": False, "actual_colab_execution": False,
               "reason": "Prepared only; separate user scoring authorization and actual Colab execution required",
               "archive_bytes": archive.stat().st_size, "archive_sha256": file_hash(archive),
               "manifest_sha256": file_hash(bundle / "package_manifest.json"),
               "generation_evidence_zip_name": Path(evidence_zip).name,
               "generation_evidence_zip_sha256": expected_evidence_sha,
               "generation_bundle_manifest_sha256": generation_manifest,
               "scoring_allocation_sha256": digest(allocation), "scoring_max_sessions": allocation["max_sessions"],
               "scoring_total_hours": allocation["total_gpu_hours"],
               "scoring_budget_decision_sha256": contract["scoring_budget_decision_sha256"],
               "rows": len(rows), "scoreable_rows": scoreable, "failed_rows": len(failed),
               "rows_by_profile": {p: sum(r["profile_id"] == p for r in rows) for p in PROFILES},
               "quality_ranking_performed": False, "generation_executed": False,
               "scoring_start_authorized": False, "selection_rule_applied": False}
    write_json(registry / "preparation_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="final523 generation evidence ZIP")
    parser.add_argument("--evidence-sha256", required=True)
    parser.add_argument("--generation-outcome", required=True, type=Path, help="passing audit of the generation evidence")
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.evidence, arguments.evidence_sha256, arguments.generation_outcome), indent=2))
