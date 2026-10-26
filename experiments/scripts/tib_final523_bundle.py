"""Private source-only final523 packaging; never runs inference and never authorizes a start.

Reuses the selection300 bundle logic (profiles, node forecast, frozen generation code) for the sealed 523 test
IDs and the same four profiles. The bundle binds every locked artifact by hash, including the sealed final cohort
and the selection300 analysis result that fixed the model choice. Authorization stays a separate user-made file
checked by tib_selection_validation.check_authorization. The ZIP is byte-reproducible (fixed member timestamps).
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_pilot_bundle import QUAL, ROOT, SEALED, sha
from experiments.scripts import tib_selection_validation as validation
from experiments.scripts.tib_selection300_bundle import (
    BINDING, LOCKED as SELECTION_LOCKED, NEURAL, PILOT_EVIDENCE, PILOT_EVIDENCE_SHA256, RECOVERY, SHIPPED_MODULES,
    node_forecast, pilot_profiles,
)

PROTOCOLS = ROOT / "experiments/registry/protocols"
LOCAL = ROOT / "research-data/tib-final523-generation-261024-v1"
REGISTRY = PROTOCOLS / "tib-final523-generation-261024-v1"
ANALYSIS = PROTOCOLS / "tib-selection300-analysis-261024-v1"
ARCHIVE_NAME = "tib-final523-generation-261024-v1.zip"
FIXED_ZIP_TIME = (2026, 10, 24, 0, 0, 0)
FINAL_COHORT = "final_cohort.json"
# Locked artifacts and the folder each comes from; the first group is shared with selection300.
LOCKED_FROM = {**{name: BINDING for name in SELECTION_LOCKED},
               "selection300_analysis_result.json": ANALYSIS, "analysis_declarations_261024_v1.json": ANALYSIS,
               FINAL_COHORT: REGISTRY}
ALLOCATION_FILE = "compute_budget_final523.json"


def write(path, value):
    """Bytes, not write_text: Windows newline translation would change the hashed content."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8"))


def final_sources(registry=REGISTRY, qual=QUAL, sealed=SEALED):
    """Rows, per-ID ledger and cohort for the sealed final IDs; any identity drift raises."""
    cohort = json.loads((Path(registry) / FINAL_COHORT).read_text(encoding="utf-8"))
    dev = json.loads((Path(sealed) / "development_cohort.json").read_text(encoding="utf-8"))
    if not cohort["final_test_sealed"] or cohort["final_test_authorized"] or cohort["generation_executed"]:
        raise ValueError("Final cohort must be sealed, unauthorized and ungenerated")
    ids = cohort["selected_ids"]
    if len(ids) != len(set(ids)) or len(ids) != validation.FINAL_N or set(ids) & (
            set(dev["selected_ids"]["pilot"]) | set(dev["selected_ids"]["selection"])):
        raise ValueError(f"Expected exact sealed {validation.FINAL_N} IDs, disjoint from development sets")
    if cohort["quotas"] != validation.FINAL_QUOTAS:
        raise ValueError("Sealed final quotas differ from 182/172/169")
    for key, path in (("qualification_ledger_sha256", qual / "qualified_cohort/qualification_ledger.jsonl"),
                      ("rights_ledger_sha256", qual / "source_use_ledger.jsonl"),
                      ("development_cohort_sha256", Path(sealed) / "development_cohort.json")):
        if cohort[key] != sha(path):
            raise ValueError("Qualification input changed since the seal: " + key)
    wanted = set(ids)

    def selected(path):
        return {r["record_id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())
                if r["record_id"] in wanted}
    rights = selected(qual / "source_use_ledger.jsonl")
    eligible = selected(qual / "qualified_cohort/qualification_ledger.jsonl")
    canonical_path = qual / "eda/canonical_records.jsonl.gz"
    eda = json.loads((qual / "eda/receipt.json").read_text(encoding="utf-8"))
    if sha(canonical_path) != eda["files"]["canonical_records.jsonl.gz"]:
        raise ValueError("Canonical snapshot differs")
    with gzip.open(canonical_path, "rt", encoding="utf-8") as handle:
        # Only the source text is kept: the canonical file also carries references, which must not stay in memory.
        canonical = {r["record_id"]: {"source_normalized": r["source_normalized"]}
                     for r in map(json.loads, handle) if r["record_id"] in wanted}
    if any(set(v) != wanted for v in (canonical, rights, eligible)):
        raise ValueError("Incomplete final source evidence")
    rows, ledger = [], []
    low, high = cohort["source_word_cutpoints"]
    for identifier in ids:  # sealed order is the frozen generation order
        source, right, qualified = canonical[identifier]["source_normalized"], rights[identifier], eligible[identifier]
        text_sha = hashlib.sha256(source.encode()).hexdigest()
        if not qualified["role_eligible"] or not right["allowed_for_current_local_use"]:
            raise ValueError("Final eligibility/rights failed: " + identifier)
        if text_sha != qualified["source_normalized_sha256"] or text_sha != right["source_normalized_sha256"]:
            raise ValueError("Final source identity differs: " + identifier)
        words = len(source.split())
        stratum = "short" if words <= low else "medium" if words <= high else "long"
        if stratum != cohort["source_strata"][identifier] or qualified["group_id"] != cohort["selected_groups"][identifier]:
            raise ValueError("Stratum or group differs from the seal: " + identifier)
        attribution = {key: right[key] for key in ("author", "title", "source_url", "released_license_raw",
                                                   "license_uri_canonical", "modification_notice", "conditions_recorded")}
        rows.append({"record_id": identifier, "source_normalized": source, "source_normalized_sha256": text_sha,
                     "source_stratum": stratum, "source_words": words, "attribution": attribution})
        ledger.append({"record_id": identifier, "source_normalized_sha256": text_sha, "group_id": qualified["group_id"],
                       "source_stratum": stratum, "source_use_status": right["source_use_status"],
                       "allowed_for_current_local_use": True})
    if dict(Counter(r["source_stratum"] for r in rows)) != validation.FINAL_QUOTAS:
        raise ValueError("Recomputed strata differ from the sealed final quotas")
    return cohort, dev, rows, ledger


def locked_choice(analysis=ANALYSIS):
    """The selection300 outcome the final run confirms; anything but a recorded `selected` result stops the build."""
    result = json.loads((Path(analysis) / "selection300_analysis_result.json").read_text(encoding="utf-8"))
    if result["label"] != "selected" or not result["selected_profile"]:
        raise ValueError("Selection300 produced no locked choice; final523 must not be packaged")
    return {"label": result["label"], "selected_profile": result["selected_profile"],
            "selected_profile_id": result["selected_profile_id"],
            "analysis_result_sha256": sha(Path(analysis) / "selection300_analysis_result.json")}


def deterministic_zip(path, package, names):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as output:
        for name in names:
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, (Path(package) / name).read_bytes())


def build(local=LOCAL, registry=REGISTRY):
    local, registry = Path(local), Path(registry)
    cohort, dev, rows, ledger = final_sources(registry)
    choice = locked_choice()
    package = local / "package"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    profile_list = json.loads((BINDING / "selection300_profiles_v2.json").read_text(encoding="utf-8"))
    profiles = pilot_profiles(PILOT_EVIDENCE, profile_list)
    forecast = node_forecast()
    shutil.copytree(RECOVERY, package / "original_generation")
    for path in (RECOVERY / "experiments").rglob("*.py"):
        dest = package / path.relative_to(RECOVERY)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    for name in SHIPPED_MODULES:
        shutil.copyfile(ROOT / "experiments/scripts" / (name + ".py"), package / "experiments/scripts" / (name + ".py"))
    locked = package / validation.LOCKED_DIR
    locked.mkdir()
    for name, folder in LOCKED_FROM.items():
        shutil.copyfile((registry if name == FINAL_COHORT else Path(folder)) / name, locked / name)
    with zipfile.ZipFile(PILOT_EVIDENCE) as archive:
        for member, name in (("package/acceptance_policy.json", "acceptance_policy.json"),
                             ("package/actual_recovery_receipt.json", "actual_recovery_receipt.json"),
                             ("package/actual_scorer_ready_receipt.json", "actual_scorer_ready_receipt.json"),
                             ("package/requirements-pilot.txt", "requirements-selection.txt")):
            (package / name).write_bytes(archive.read(member))
    allocation = json.loads((BINDING / ALLOCATION_FILE).read_text(encoding="utf-8"))
    if allocation["stage"] != "final523" or allocation["records_per_pipeline"] != validation.FINAL_N:
        raise ValueError("Allocation is not the final523 allocation")
    if allocation["profile_list_sha256"] != sha(BINDING / "selection300_profiles_v2.json"):
        raise ValueError("Allocation is bound to a different profile list")
    write(package / "selection_allocation.json", allocation)
    write(package / "node_forecast.json", forecast)
    (package / "selection_sources.jsonl").write_bytes(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8"))
    write(package / "source_rights_ledger.json", ledger)
    ids = cohort["selected_ids"]
    contract = {
        "schema_version": 1, "scope": "Final523 generation only; no scoring, no selection",
        "stage": "final523", "selection_ids": ids, "source_strata": {r["record_id"]: r["source_stratum"] for r in rows},
        "quotas": cohort["quotas"], "staged_ids": [], "excluded_pilot_ids": dev["selected_ids"]["pilot"],
        "excluded_selection_ids": dev["selected_ids"]["selection"],
        "candidate_order": list(validation.CANDIDATES), "word_cap": 350, "profiles": profiles,
        "source_order": "Sealed final ID order; no long-tail removal, no replacement",
        "expected_cells": len(ids) * len(validation.CANDIDATES), "expected_neural_cells": len(ids) * len(NEURAL),
        "expected_cpu_cells": len(ids) * 2, "selection_authorized": False, "final_test_authorized": False,
        "locked_choice": choice,
        "locked_artifacts": {name: sha(locked / name) for name in LOCKED_FROM},
        "allocation_sha256": digest(allocation), "profile_list_sha256": sha(locked / "selection300_profiles_v2.json"),
        "acceptance_policy_sha256": sha(package / "acceptance_policy.json"),
        "original_bundle_manifest_sha256": sha(package / "original_generation/bundle_manifest.json"),
        "final_cohort_sha256": sha(registry / FINAL_COHORT),
        "qualification_ledger_sha256": cohort["qualification_ledger_sha256"],
        "rights_ledger_sha256": cohort["rights_ledger_sha256"],
        "canonical_sha256": sha(QUAL / "eda/canonical_records.jsonl.gz"),
        "pilot40_evidence_zip_sha256": PILOT_EVIDENCE_SHA256, "metrics_executed": False}
    write(package / "selection_contract.json", contract)
    manifest = {"schema_version": 1, "files": {
        p.relative_to(package).as_posix(): sha(p) for p in sorted(package.rglob("*"))
        if p.is_file() and p.name != validation.MANIFEST and "__pycache__" not in p.parts}}
    write(package / validation.MANIFEST, manifest)
    archive_path = local / ARCHIVE_NAME
    deterministic_zip(archive_path, package, list(manifest["files"]) + [validation.MANIFEST])
    registry.mkdir(parents=True, exist_ok=True)
    for name in ("selection_contract.json", validation.MANIFEST, "node_forecast.json", "selection_allocation.json"):
        shutil.copyfile(package / name, registry / name)
    receipt = {"status": "PREPARED_AUTHORIZATION_AND_ACTUAL_EXECUTION_REQUIRED", "archive_bytes": archive_path.stat().st_size,
               "archive_sha256": sha(archive_path), "manifest_sha256": sha(package / validation.MANIFEST),
               "source_records": len(rows), "source_strata": dict(Counter(r["source_stratum"] for r in rows)),
               "expected_cells": contract["expected_cells"], "locked_choice": choice, "actual_execution": False,
               "final_test_authorized": False, "selection_start_authorized": False}
    write(registry / "preparation_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
