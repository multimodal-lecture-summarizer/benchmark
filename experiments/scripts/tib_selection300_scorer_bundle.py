"""Package the 1,200 selection300 generation cells and the frozen scorer v2 code for private Colab scoring.

Mirrors tib_pilot40_scorer_bundle without modifying it. The generation bundle deliberately holds no
references; this bundle is the only place that joins a delivered summary with its source and reference, so
it stays private (Drive only, never published) and the text-free registry copy carries hashes and counts.
Failed generation cells stay in the denominator as unscoreable rows; nothing is retried or dropped.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

from experiments.scripts import tib_selection300_scorer_validation as validation
from experiments.scripts.tib_budget_views import build_views
from experiments.scripts.tib_pilot40_scorer_bundle import PROFILES, VIEW_BUDGETS
from experiments.scripts.tib_scorer_colab_bundle import (
    PINS, SCRIPTS as P4B_SCRIPTS, SUPPORT, file_hash, text_hash, write_json,
)
from experiments.scripts.tib_stage_session import digest

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = ROOT / "experiments/registry/protocols"
QUALIFICATION = ROOT / "research-data/tib-qualification-261019-1703"
COHORT = ROOT / "experiments/registry/datasets/tib-text-model-benchmark-v1/qualification-261019-1703/development_cohort.json"
BINDING = PROTOCOLS / "tib-selection300-binding-261023-v1"
GENERATION_REGISTRY = PROTOCOLS / "tib-selection300-generation-261023-v1"
SPEC = PROTOCOLS / "tib-model-benchmark-p4-261019-1802/scorer_spec_v2.json"
PILOT40_AMENDMENT = PROTOCOLS / "tib-pilot40-scoring-261023-v1/runtime_amendment.json"
PILOT40_REQUIREMENTS = PROTOCOLS / "tib-pilot40-scoring-261023-v1/requirements-colab-t4.txt"
GENERATION_LOCAL = ROOT / "research-data/tib-selection300-generation-261023-v1"
EVIDENCE_ZIP = GENERATION_LOCAL / "results/tib-selection300-evidence-20261023T175142Z.zip"
EVIDENCE_SHA256 = "be9d87f1b7deb2058280eae8565c8559db6d77b0209139309ee66652a43a723a"
REGISTRY = PROTOCOLS / "tib-selection300-scoring-261024-v1"
LOCAL = ROOT / "research-data/tib-selection300-scoring-261024-v1"
AMENDMENT_ID = "tib-selection300-scoring-261024-v1"
ARCHIVE_NAME = "tib-selection300-scoring-261024-v1.zip"

EXCLUDED = {"qwen3": "protocol decision 2026-10-23 18:42: dropped from selection300/final523; primary metric not scored"}
# Ledger/session modules ship too: the notebook opens the shared-ledger session from the scoring bundle.
SCRIPTS = P4B_SCRIPTS + ["tib_pilot40_scorer_runner", "tib_selection300_scorer_validation", "tib_stage_session",
                         "tib_stage_resources", "tib_pilot_resources", "tib_selection300_binding",
                         "tib_benchmark_checkpoint"]
GENERATION_LOCKED = ("scorer_freeze_receipt.json", "admission_rules_v2.json", "decisions_261023_v1.json")
RECEIPT_STATUSES = {"PASS", "COMPLETED_WITH_FAILURES"}
MAX_ARCHIVE_BYTES = 50 * 1024 ** 2


def _jsonl(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _by_record(path, wanted):
    with Path(path).open(encoding="utf-8") as handle:
        return {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in wanted}


def selection_scoring_rows(evidence_zip=EVIDENCE_ZIP, qualification=QUALIFICATION, cohort_path=COHORT,
                           profile_list_path=BINDING / "selection300_profiles_v2.json", ids=None, excluded_ids=None,
                           interrupted_as_failed=False):
    """Rows for every (selection ID, profile) cell in sealed ID order, then profile order; drift raises.

    `ids`/`excluded_ids` let another stage (final523) pass its own sealed IDs; by default they come from the
    development cohort exactly as before. `interrupted_as_failed` keeps a record the generation runtime left
    `started` (a session that ended mid-record, never retried) in the denominator as an unscoreable failed cell.
    """
    qualification = Path(qualification)
    if ids is None:
        cohort = json.loads(Path(cohort_path).read_text(encoding="utf-8"))
        ids, excluded_ids = cohort["selected_ids"]["selection"], cohort["selected_ids"]["pilot"]
    wanted = set(ids)
    if len(ids) != len(wanted) or wanted & set(excluded_ids or ()):
        raise ValueError("Selection cohort is not a duplicate-free set disjoint from the excluded IDs")
    profile_list = json.loads(Path(profile_list_path).read_text(encoding="utf-8"))
    bound = {p["candidate_id"]: p["profile_sha256"] for p in profile_list["profiles"]}
    if tuple(bound) != PROFILES:
        raise ValueError("Profile list differs from lead3/lexrank/bart/led")

    rights = _by_record(qualification / "source_use_ledger.jsonl", wanted)
    eligible = _by_record(qualification / "qualified_cohort/qualification_ledger.jsonl", wanted)
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "rt", encoding="utf-8") as handle:
        canonical = {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in wanted}
    if any(set(group) != wanted for group in (rights, eligible, canonical)):
        raise ValueError("Incomplete selection identity/rights evidence")

    rows = {}
    with zipfile.ZipFile(evidence_zip) as archive:
        names = archive.namelist()
        directories = {n.split("/")[1] for n in names if n.startswith("selection/") and n.count("/") >= 2}
        if directories != set(PROFILES) or any("qwen" in n.lower() for n in names):
            raise ValueError("Evidence ZIP profile directories differ from the four fixed profiles")
        contract = json.loads(archive.read("package/selection_contract.json"))
        sources = {r["record_id"]: r for r in _jsonl(archive.read("package/selection_sources.jsonl").decode("utf-8"))}
        if contract["selection_ids"] != ids or set(sources) != wanted:
            raise ValueError("Evidence generation contract differs from the sealed selection cohort")
        for profile in PROFILES:
            blob = archive.read(f"selection/{profile}/candidate_receipt.json")
            receipt_sha = hashlib.sha256(blob).hexdigest()
            receipt = json.loads(blob)
            identity = json.loads(archive.read(f"selection/{profile}/run_identity.json"))["payload"]
            if (receipt["candidate_id"] != profile or receipt["status"] not in RECEIPT_STATUSES
                    or identity["profile_sha256"] != bound[profile]):
                raise ValueError(f"{profile}: receipt/run identity differs from the bound profile")
            records = receipt["records"]
            if set(records) != wanted:
                raise ValueError(f"{profile}: receipt does not cover exactly the selection IDs")
            for record_id in ids:
                record = records[record_id]
                canon, right, qual = canonical[record_id], rights[record_id], eligible[record_id]
                source, reference = canon["source_normalized"], canon["reference_normalized"]
                if not (qual["role_eligible"] and right["allowed_for_current_local_use"]
                        and right["allowed_for_reference_scoring"]):
                    raise ValueError("Rights/eligibility contract changed: " + record_id)
                if not (text_hash(source) == sources[record_id]["source_normalized_sha256"]
                        == qual["source_normalized_sha256"] == record["source_sha256"]
                        and text_hash(reference) == qual["reference_normalized_sha256"]):
                    raise ValueError("Source/reference identity mismatch: " + record_id)
                status = record["status"]
                interrupted = interrupted_as_failed and status == "started"
                if interrupted:
                    status = "failed"
                if (record["record_id"] != record_id or status not in validation.STATUSES
                        or not record.get("retain_in_denominator")
                        or record["source_stratum"] != contract["source_strata"][record_id]
                        or record["binding"]["profile_sha256"] != bound[profile]):
                    raise ValueError(f"{profile}/{record_id}: unexpected status or binding")
                row = {"sample_id": validation.sample_id(profile, record_id), "record_id": record_id,
                       "candidate_id": profile, "profile_id": profile, "source_stratum": record["source_stratum"],
                       "source": source, "reference": reference,
                       "source_sha256": text_hash(source), "reference_sha256": text_hash(reference),
                       "source_receipt_sha256": receipt_sha, "generation_status": status}
                if status == "failed":
                    row.update(scoreable=False, failure_reason="interrupted_before_completion" if interrupted else record["error"],
                               warnings=[],
                               delivered_summary=None, delivered_sha256=None, views=None)
                else:
                    result = record["result"]
                    delivered = result["delivered_final"]
                    if (text_hash(delivered) != result["delivery"]["delivered_sha256"]
                            or len(delivered.split()) > validation.WORD_CAP):
                        raise ValueError(f"{profile}/{record_id}: delivered summary hash/cap mismatch")
                    views = build_views(result["raw_final"], VIEW_BUDGETS)
                    row.update(scoreable=True, failure_reason=None,
                               warnings=record["validation"]["acceptance"]["warnings"],
                               delivered_summary=delivered, delivered_sha256=text_hash(delivered),
                               views={name: views[name]["text"] for name in VIEW_BUDGETS})
                rows[(record_id, profile)] = row
    return [rows[(record_id, profile)] for record_id in ids for profile in PROFILES]


def generation_hashes(evidence_zip, generation_registry=GENERATION_REGISTRY):
    """Manifest hash of the generation bundle, taken from the shared ledger and cross-checked three ways."""
    with zipfile.ZipFile(evidence_zip) as archive:
        ledger = json.loads(archive.read("selection/resource_ledger.json"))
        shipped_manifest = hashlib.sha256(archive.read("package/selection_manifest.json")).hexdigest()
        allocation = json.loads(archive.read("package/selection_allocation.json"))
    prepared = json.loads((Path(generation_registry) / "preparation_receipt.json").read_text(encoding="utf-8"))
    manifest = ledger["bundle_sha256"]
    if not (manifest == shipped_manifest == prepared["manifest_sha256"]):
        raise ValueError("Generation bundle manifest hash disagrees between ledger, ZIP and registry")
    if ledger["allocation_sha256"] != digest(allocation) or ledger["allocation"] != allocation:
        raise ValueError("Ledger allocation differs from the allocation shipped in the evidence ZIP")
    return manifest, allocation


def _requirements():
    return ("--extra-index-url https://download.pytorch.org/whl/cu130\n"
            + "".join(f"{k}=={v}\n" for k, v in {**PINS, **SUPPORT}.items()))


def build(local=LOCAL, registry=REGISTRY, evidence_zip=EVIDENCE_ZIP, expected_evidence_sha=EVIDENCE_SHA256,
          qualification=QUALIFICATION, cohort_path=COHORT, binding=BINDING, generation_registry=GENERATION_REGISTRY):
    local, registry, binding = Path(local), Path(registry), Path(binding)
    if file_hash(evidence_zip) != expected_evidence_sha:
        raise ValueError("Selection300 evidence ZIP hash changed")
    rows = selection_scoring_rows(evidence_zip, qualification, cohort_path, binding / "selection300_profiles_v2.json")
    scoreable = sum(r["scoreable"] for r in rows)
    if (len(rows), scoreable) != (validation.EXPECTED_ROWS, validation.EXPECTED_SCOREABLE):
        raise ValueError(f"Expected {validation.EXPECTED_ROWS}/{validation.EXPECTED_SCOREABLE} rows, got {len(rows)}/{scoreable}")
    generation_manifest, allocation = generation_hashes(evidence_zip, generation_registry)
    freeze = json.loads((binding / "scorer_freeze_receipt.json").read_text(encoding="utf-8"))
    if file_hash(PILOT40_AMENDMENT) != freeze["runtime_amendments"]["pilot40_scoring_sha256"]:
        raise ValueError("Pilot40 scoring runtime amendment differs from the freeze receipt")
    pilot_amendment = json.loads(PILOT40_AMENDMENT.read_text(encoding="utf-8"))
    if pilot_amendment["runtime_pins"] != PINS or pilot_amendment["support_package_pins"] != SUPPORT:
        raise ValueError("Runtime pins differ from the audited Pilot40 scoring amendment")
    # Ship the verified file byte for byte (it was written with Windows newlines); the pins must still match.
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

    amendment = {
        "schema_version": 1, "amendment_id": AMENDMENT_ID,
        "state": "PREPARED_HOLD_ACTUAL_COLAB_EXECUTION_REQUIRED",
        "runtime_pins": PINS, "support_package_pins": SUPPORT,
        "frozen_spec_sha256": file_hash(bundle / "frozen_scorer_spec.json"),
        "pilot40_scoring_amendment_sha256": file_hash(PILOT40_AMENDMENT),
        "evidence_zip_sha256": expected_evidence_sha,
        "expected_output_count": validation.EXPECTED_ROWS, "expected_scoreable_count": validation.EXPECTED_SCOREABLE,
        "profile_ids": list(PROFILES), "excluded_profiles": EXCLUDED,
        "views": {"budgets_words": VIEW_BUDGETS, "metrics": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
                  "source_similarity": "not computed on views"},
        "preserved": "scorer v2 metrics, windows, IDF=false, FP32 and the 350-word cap are unchanged",
        "scope": "Selection300 reference scoring; descriptive, selection rule not applied here",
        "selection_start_authorized": False, "generation_allowed": False,
    }
    write_json(bundle / "runtime_amendment.json", amendment)
    contract = {
        "schema_version": 1, "scope": "Selection300 scoring only; no generation, no selection rule, no final test",
        "selection_ids": [r["record_id"] for r in rows[::len(PROFILES)]],
        "source_strata": {r["record_id"]: r["source_stratum"] for r in rows[::len(PROFILES)]},
        "quotas": validation.QUOTAS, "profile_order": list(PROFILES),
        "expected_rows": len(rows), "expected_scoreable": scoreable, "expected_failed": len(rows) - scoreable,
        "failed_cells": [r["sample_id"] for r in rows if not r["scoreable"]],
        "generation_evidence_zip_sha256": expected_evidence_sha,
        "generation_bundle_manifest_sha256": generation_manifest,
        "allocation_sha256": digest(allocation),
        "scorer_freeze_receipt_sha256": file_hash(binding / "scorer_freeze_receipt.json"),
        "admission_rules_v2_sha256": file_hash(binding / "admission_rules_v2.json"),
        "decisions_sha256": file_hash(binding / "decisions_261023_v1.json"),
        "selection_generation_outcome_sha256": file_hash(Path(generation_registry) / "selection300_generation_outcome.json"),
        "reported_metrics": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
        "metrics_computed_not_reported": ["source_sentence_similarity_v1"],
        "scoring_start_authorized": False, "selection_rule_applied": False,
    }
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
    validation.validate_selection_scoring_bundle(bundle)

    registry.mkdir(parents=True, exist_ok=True)
    for name in ("runtime_amendment.json", validation.CONTRACT, "requirements-colab-t4.txt", "package_manifest.json"):
        shutil.copyfile(bundle / name, registry / name)
    archive = local / ARCHIVE_NAME
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative in manifest["files"]:
            output.write(bundle / relative, relative)
        output.write(bundle / "package_manifest.json", "package_manifest.json")
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError(f"Scoring ZIP is {archive.stat().st_size} bytes (> 50 MB); stop and ask")
    receipt = {"schema_version": 1, "status": "HOLD", "scorer_ready": False, "actual_colab_execution": False,
               "reason": "Prepared only; separate user scoring authorization and actual Colab execution required",
               "archive_bytes": archive.stat().st_size, "archive_sha256": file_hash(archive),
               "manifest_sha256": file_hash(bundle / "package_manifest.json"),
               "generation_evidence_zip_sha256": expected_evidence_sha,
               "generation_bundle_manifest_sha256": generation_manifest,
               "rows": len(rows), "scoreable_rows": scoreable, "failed_rows": len(rows) - scoreable,
               "rows_by_profile": {p: sum(r["profile_id"] == p for r in rows) for p in PROFILES},
               "quality_ranking_performed": False, "generation_executed": False,
               "scoring_start_authorized": False, "selection_rule_applied": False}
    write_json(registry / "preparation_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build(), indent=2))
