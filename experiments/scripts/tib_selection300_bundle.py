"""Private source-only selection300 packaging; never runs inference and never touches cohorts.

Generalises tib_pilot_bundle (kept untouched) to the 300 sealed selection IDs and the four approved
profiles. The bundle binds every locked artifact by hash and never authorizes a start: authorization is
a separate user-made file checked by tib_selection_validation.check_authorization.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_pilot_bundle import ROOT, QUAL, SEALED, sha, write
from experiments.scripts import tib_selection_validation as validation

LOCAL = ROOT / "research-data/tib-selection300-generation-261023-v1"
REGISTRY = ROOT / "experiments/registry/protocols/tib-selection300-generation-261023-v1"
BINDING = ROOT / "experiments/registry/protocols/tib-selection300-binding-261023-v1"
RECOVERY = ROOT / "research-data/tib-p4-fresh-recovery-261020-v2/package/generation_bundle"
PILOT_EVIDENCE = ROOT / "research-data/tib-pilot40-261020-v1/results/tib-pilot40-evidence-20261023T074252Z.zip"
PILOT_EVIDENCE_SHA256 = "39cc411bd3304041a478c1fb55b55b2417764538a62df69aa15472ab0980dbce"
LOCKED = ("selection300_profiles_v2.json", "compute_budget_selection300.json", "compute_budget_final523.json",
          "cap350_feasibility_receipt.json", "output_policy_v2.json", "admission_rules_v2.json",
          "decisions_261023_v1.json", "view_policy_v1.json", "scorer_freeze_receipt.json",
          "selection300_readiness_receipt.json")
SHIPPED_MODULES = ("tib_benchmark_acceptance", "tib_p4_generation_recovery", "tib_pilot_resources", "tib_pilot_validation",
                   "tib_stage_resources", "tib_stage_session", "tib_selection_validation", "tib_selection_runtime",
                   "tib_selection300_binding")
FORECAST_SAFETY = 1.5
NEURAL = ("bart", "led")


def selection_sources(sealed=SEALED, qual=QUAL, expected_n=validation.SELECTION_N, quotas=None):
    """Rows, per-ID ledger and the cohort for the sealed selection IDs; any identity drift raises."""
    quotas = validation.QUOTAS if quotas is None else quotas
    cohort = json.loads((sealed / "development_cohort.json").read_text(encoding="utf-8"))
    if sha(sealed / "qualification_policy.json") != cohort["policy_sha256"]:
        raise ValueError("Sealed qualification policy differs")
    ids, pilot = cohort["selected_ids"]["selection"], cohort["selected_ids"]["pilot"]
    if len(ids) != len(set(ids)) or len(ids) != expected_n or set(ids) & set(pilot):
        raise ValueError(f"Expected exact sealed {expected_n} selection IDs, disjoint from the pilot")
    if cohort["selection_quotas"] != quotas:
        raise ValueError("Sealed selection quotas differ from the approved 100/90/110")
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
        canonical = {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in wanted}
    if any(set(v) != wanted for v in (canonical, rights, eligible)):
        raise ValueError("Incomplete selection source evidence")
    rows, ledger = [], []
    low, high = cohort["source_word_cutpoints"]
    for identifier in ids:  # sealed order is the frozen generation order
        source, right, qualified = canonical[identifier]["source_normalized"], rights[identifier], eligible[identifier]
        text_sha = hashlib.sha256(source.encode()).hexdigest()
        if not qualified["role_eligible"] or not right["allowed_for_current_local_use"]:
            raise ValueError("Selection eligibility/rights failed: " + identifier)
        if text_sha != qualified["source_normalized_sha256"] or text_sha != right["source_normalized_sha256"]:
            raise ValueError("Selection source identity differs: " + identifier)
        words = len(source.split())
        stratum = "short" if words <= low else "medium" if words <= high else "long"
        attribution = {key: right[key] for key in ("author", "title", "source_url", "released_license_raw",
                                                   "license_uri_canonical", "modification_notice", "conditions_recorded")}
        rows.append({"record_id": identifier, "source_normalized": source, "source_normalized_sha256": text_sha,
                     "source_stratum": stratum, "source_words": words, "attribution": attribution})
        ledger.append({"record_id": identifier, "source_normalized_sha256": text_sha, "group_id": qualified["group_id"],
                       "source_stratum": stratum, "source_use_status": right["source_use_status"],
                       "allowed_for_current_local_use": True})
    if dict(Counter(r["source_stratum"] for r in rows)) != quotas:
        raise ValueError("Recomputed strata differ from the sealed selection quotas")
    development = json.loads((qual / "qualified_cohort/development_records.json").read_text(encoding="utf-8"))
    if {r["group_id"] for r in development["pilot"]} & {r["group_id"] for r in development["selection"]}:
        raise ValueError("Pilot/selection groups overlap")
    return cohort, rows, ledger


def node_forecast(evidence_zip=PILOT_EVIDENCE, expected_sha=PILOT_EVIDENCE_SHA256, safety=FORECAST_SAFETY):
    """1.5 x the slowest measured Pilot40 call per neural profile and stage, plus model load time."""
    if sha(evidence_zip) != expected_sha:
        raise ValueError("Pilot40 evidence ZIP hash changed")
    stage_seconds, load_seconds, support = {}, {}, {}
    with zipfile.ZipFile(evidence_zip) as archive:
        for candidate in NEURAL:
            receipt = json.loads(archive.read(f"pilot/{candidate}/candidate_receipt.json"))
            observed = {}
            for record in receipt["records"].values():
                if record["status"] == "failed":
                    continue
                for item in record.get("stage_resources", []):
                    observed.setdefault(item["stage"], []).append(item["wall_seconds"])
            if {"map", "reduce", "final"} - set(observed):
                raise ValueError(f"{candidate}: Pilot40 did not measure every generation stage")
            stage_seconds[candidate] = {s: max(v) * safety for s, v in sorted(observed.items())}
            support[candidate] = {s: len(v) for s, v in sorted(observed.items())}
            load_seconds[candidate] = receipt["model_load_wall_seconds"] * safety
    return {"schema_version": 1, "rule": f"{safety}x maximum observed Pilot40 call per profile and stage; operational guard, not a statistical bound",
            "source_zip_sha256": expected_sha, "stage_seconds": stage_seconds, "load_seconds": load_seconds,
            "calls_observed": support}


def pilot_profiles(evidence_zip, profile_list):
    """The four profile bodies that actually ran in Pilot40, matched to the bound profile list."""
    with zipfile.ZipFile(evidence_zip) as archive:
        contract = json.loads(archive.read("package/pilot_contract.json"))
    by_candidate = {p["candidate_id"]: p for p in contract["profiles"]}
    bound = {p["candidate_id"]: p["profile_sha256"] for p in profile_list["profiles"]}
    profiles = []
    for candidate in validation.CANDIDATES:
        entry = by_candidate[candidate]
        if digest(entry["profile"]) != entry["profile_sha256"] or entry["profile_sha256"] != bound[candidate]:
            raise ValueError(f"{candidate}: profile differs from the bound profile list")
        profiles.append({k: entry[k] for k in ("candidate_id", "profile_id", "profile", "profile_sha256")})
    return profiles


def build(local=LOCAL, registry=REGISTRY):
    local, registry = Path(local), Path(registry)
    package = local / "package"
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    cohort, rows, ledger = selection_sources()
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
    for name in LOCKED:
        shutil.copyfile(BINDING / name, locked / name)
    with zipfile.ZipFile(PILOT_EVIDENCE) as archive:
        for member, name in (("package/acceptance_policy.json", "acceptance_policy.json"),
                             ("package/actual_recovery_receipt.json", "actual_recovery_receipt.json"),
                             ("package/actual_scorer_ready_receipt.json", "actual_scorer_ready_receipt.json"),
                             ("package/requirements-pilot.txt", "requirements-selection.txt")):
            (package / name).write_bytes(archive.read(member))
    allocation = json.loads((BINDING / "compute_budget_selection300.json").read_text(encoding="utf-8"))
    if allocation["profile_list_sha256"] != sha(BINDING / "selection300_profiles_v2.json"):
        raise ValueError("Allocation is bound to a different profile list")
    write(package / "selection_allocation.json", allocation)
    write(package / "node_forecast.json", forecast)
    (package / "selection_sources.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    write(package / "source_rights_ledger.json", ledger)
    ids = cohort["selected_ids"]["selection"]
    contract = {
        "schema_version": 1, "scope": "Selection300 generation only; no scoring, no final test",
        "selection_ids": ids, "source_strata": {r["record_id"]: r["source_stratum"] for r in rows},
        "quotas": cohort["selection_quotas"], "staged_ids": [], "excluded_pilot_ids": cohort["selected_ids"]["pilot"],
        "candidate_order": list(validation.CANDIDATES), "word_cap": 350, "profiles": profiles,
        "source_order": "Sealed selection ID order; no long-tail removal, no replacement",
        "expected_cells": len(ids) * len(validation.CANDIDATES), "expected_neural_cells": len(ids) * len(NEURAL),
        "expected_cpu_cells": len(ids) * 2, "selection_authorized": False, "final_test_authorized": False,
        "locked_artifacts": {name: sha(locked / name) for name in LOCKED},
        "allocation_sha256": digest(allocation), "profile_list_sha256": sha(locked / "selection300_profiles_v2.json"),
        "acceptance_policy_sha256": sha(package / "acceptance_policy.json"),
        "original_bundle_manifest_sha256": sha(package / "original_generation/bundle_manifest.json"),
        "sealed_cohort_sha256": sha(SEALED / "development_cohort.json"),
        "qualification_ledger_sha256": sha(QUAL / "qualified_cohort/qualification_ledger.jsonl"),
        "rights_ledger_sha256": sha(QUAL / "source_use_ledger.jsonl"),
        "canonical_sha256": sha(QUAL / "eda/canonical_records.jsonl.gz"),
        "pilot40_evidence_zip_sha256": PILOT_EVIDENCE_SHA256,
        "metrics_executed": False}
    write(package / "selection_contract.json", contract)
    manifest = {"schema_version": 1, "files": {
        p.relative_to(package).as_posix(): sha(p) for p in sorted(package.rglob("*"))
        if p.is_file() and p.name != validation.MANIFEST and "__pycache__" not in p.parts}}
    write(package / validation.MANIFEST, manifest)
    archive_path = local / "tib-selection300-generation-261023-v1.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as output:
        for name in manifest["files"]:
            output.write(package / name, name)
        output.write(package / validation.MANIFEST, validation.MANIFEST)
    registry.mkdir(parents=True, exist_ok=True)
    for name in ("selection_contract.json", validation.MANIFEST, "node_forecast.json", "selection_allocation.json"):
        shutil.copyfile(package / name, registry / name)
    receipt = {"status": "PREPARED_AUTHORIZATION_AND_ACTUAL_EXECUTION_REQUIRED", "archive_bytes": archive_path.stat().st_size,
               "archive_sha256": sha(archive_path), "manifest_sha256": sha(package / validation.MANIFEST),
               "source_records": len(rows), "source_strata": dict(Counter(r["source_stratum"] for r in rows)),
               "expected_cells": contract["expected_cells"], "actual_execution": False,
               "selection_start_authorized": False}
    write(registry / "preparation_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
