"""Synthetic full-size (523 IDs x 4 profiles) final523 evidence for scoring tests; no real data.

Fixture IDs start with `fixture:` so they can never collide with the sealed final cohort.
"""
import gzip
import hashlib
import json
import random
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

from experiments.scripts import tib_final523_scorer_bundle as bundle
from experiments.scripts.tib_stage_session import digest
from selection_scoring_fixtures import BINDING_COPIED, PROFILES, jsonl, make_record, sha

FAILED_LED = ("fixture:005", "fixture:100", "fixture:250", "fixture:400")
# A record the generation runtime left `started` (session ended mid-record, never retried).
INTERRUPTED = (("bart", "fixture:300"),)
QUOTAS = {"short": 182, "medium": 172, "long": 169}


def good_outcome(archive_sha, **ledger):
    """A passing generation audit with the closed-ledger figures the scoring budget is carved from (3 sessions used)."""
    used = {"cpu_seconds": 47041.14, "gpu_seconds": 36531.63, "transfer_bytes": 5759850502,
            "completed_session_wall_seconds": 36531.63, **ledger}
    return {"audit_pass": True, "evidence_zip_sha256": archive_sha, "ledger": used,
            "ledger_sessions": [{"status": "evidence_exported"}, {"status": "interrupted"}, {"status": "evidence_exported"}]}


def make_final_ids():
    ids = [f"fixture:{i:03d}" for i in range(1, 524)]
    strata = ["short"] * 182 + ["medium"] * 172 + ["long"] * 169
    random.Random(11).shuffle(strata)
    return ids, dict(zip(ids, strata))


def make_final_world(tmp_path, stage="final523"):
    """Evidence ZIP, qualification folder, final cohort, binding and generation registry under tmp_path."""
    root = Path(tmp_path) / "final-world"
    ids, strata = make_final_ids()
    qualification, binding, registry = root / "qual", root / "binding", root / "generation-registry"
    (qualification / "qualified_cohort").mkdir(parents=True)
    (qualification / "eda").mkdir()
    binding.mkdir()
    registry.mkdir()
    (qualification / "source_use_ledger.jsonl").write_text(jsonl(
        [{"record_id": i, "allowed_for_current_local_use": True, "allowed_for_reference_scoring": True} for i in ids]))
    (qualification / "qualified_cohort/qualification_ledger.jsonl").write_text(jsonl(
        [{"record_id": i, "role_eligible": True, "source_normalized_sha256": sha("source " + i),
          "reference_normalized_sha256": sha("reference " + i)} for i in ids]))
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(jsonl([{"record_id": i, "source_normalized": "source " + i,
                             "reference_normalized": "reference " + i} for i in ids]))
    final_cohort = root / "final_cohort.json"
    final_cohort.write_text(json.dumps({"selected_ids": ids, "final_test_sealed": True}))
    development = root / "development_cohort.json"
    development.write_text(json.dumps({"selected_ids": {"pilot": ["fixture:pilot-1"], "selection": ["fixture:sel-1"]}}))
    profile_shas = {p: sha("profile " + p) for p in PROFILES}
    profile_list = binding / "selection300_profiles_v2.json"
    profile_list.write_text(json.dumps({"profiles": [{"candidate_id": p, "profile_sha256": profile_shas[p]} for p in PROFILES]}))
    for name in BINDING_COPIED:
        shutil.copyfile(bundle.BINDING / name, binding / name)
    allocation = json.loads((bundle.BINDING / ("compute_budget_final523.json" if stage == "final523"
                                              else "compute_budget_selection300.json")).read_text(encoding="utf-8"))
    manifest_bytes = b'{"schema_version": 1, "files": {}}'
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    ledger = {"bundle_sha256": manifest_sha, "allocation_sha256": digest(allocation), "allocation": allocation}
    (registry / "preparation_receipt.json").write_text(json.dumps({"manifest_sha256": manifest_sha}))
    archive = root / "tib-final523-evidence-20261101T000000Z.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("package/selection_contract.json", json.dumps({"selection_ids": ids, "source_strata": strata}))
        z.writestr("package/selection_sources.jsonl", jsonl(
            [{"record_id": i, "source_normalized_sha256": sha("source " + i), "source_stratum": strata[i]} for i in ids]))
        z.writestr("package/selection_manifest.json", manifest_bytes)
        z.writestr("package/selection_allocation.json", json.dumps(allocation))
        z.writestr("selection/resource_ledger.json", json.dumps(ledger))
        for profile in PROFILES:
            records = {}
            for i in ids:
                status = "failed" if (profile == "led" and i in FAILED_LED) else (
                    "completed_with_warning" if profile in ("bart", "led") else "completed")
                records[i] = make_record(i, strata[i], profile, profile_shas[profile], status)
                if (profile, i) in INTERRUPTED:
                    records[i] = make_record(i, strata[i], profile, profile_shas[profile], "failed")
                    records[i].pop("error")
                    records[i]["status"] = "started"
            z.writestr(f"selection/{profile}/candidate_receipt.json", json.dumps({
                "candidate_id": profile, "status": "COMPLETED_WITH_FAILURES" if profile in ("led", "bart") else "PASS",
                "records": records}))
            z.writestr(f"selection/{profile}/run_identity.json", json.dumps({"payload": {"profile_sha256": profile_shas[profile]}}))
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    outcome = root / "final523_generation_outcome.json"
    outcome.write_text(json.dumps(good_outcome(archive_sha)))
    return SimpleNamespace(root=root, ids=ids, strata=strata, qualification=qualification, binding=binding,
                           registry=registry, final_cohort=final_cohort, development=development, outcome=outcome,
                           archive=archive, profile_list=profile_list, manifest_sha=manifest_sha, allocation=allocation,
                           archive_sha=archive_sha)


def build_final_bundle(world, tmp_path, **overrides):
    local, registry = Path(tmp_path) / "local", Path(tmp_path) / "registry"
    options = dict(local=local, registry=registry, qualification=world.qualification, final_cohort_path=world.final_cohort,
                   development_cohort_path=world.development, binding=world.binding, generation_registry=world.registry)
    options.update(overrides)
    receipt = bundle.build(world.archive, world.archive_sha, world.outcome, **options)
    return receipt, local, registry
