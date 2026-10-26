"""Readiness receipt for selection300 scoring: what is prepared and bound, and what only a Colab session can close.

Every gate recomputes hashes from files on disk. The two in-session gates and the user authorization stay OPEN
and `scoring_start_authorized` is a constant False: this receipt never starts, and never authorizes, a run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from experiments.scripts import tib_selection300_scorer_bundle as bundle_module
from experiments.scripts import tib_selection300_scorer_notebook as notebook_module
from experiments.scripts import tib_selection300_scorer_validation as validation
from experiments.scripts.tib_pilot_bundle import sha, write

IN_SESSION_GATES = {
    "t4_runtime_in_session": "closes only in the Colab session: the first notebook cells check nvidia-smi == Tesla T4 before the ledger",
    "drive_and_ledger_in_session": "closes only in the Colab session: Drive holds the shared ledger and exactly one authorized session is left",
    "user_scoring_authorization": "closes only when the user states explicitly to start; the agent then writes start_authorization_scoring.json "
                                  "bound to the scoring manifest and this receipt's hash",
}
RECEIPT_NAME = "selection300_scoring_readiness_receipt.json"


def _gate(passed, detail):
    return {"status": "PASS" if passed else "OPEN", "detail": detail}


def archive_matches(archive, package, expected_sha):
    """The ZIP on disk hashes to the receipt and holds exactly the manifest's files with identical bytes."""
    archive, package = Path(archive), Path(package)
    if not archive.exists() or sha(archive) != expected_sha:
        return False
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist()) != set(manifest["files"]) | {"package_manifest.json"}:
            return False
        return (all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in manifest["files"].items())
                and hashlib.sha256(z.read("package_manifest.json")).hexdigest() == sha(package / "package_manifest.json"))


def build(registry=bundle_module.REGISTRY, local=bundle_module.LOCAL, generation_registry=bundle_module.GENERATION_REGISTRY,
          binding=bundle_module.BINDING, notebook_path=None, evidence_zip=bundle_module.EVIDENCE_ZIP,
          expected_evidence_sha=bundle_module.EVIDENCE_SHA256, root=bundle_module.ROOT):
    registry, local, binding = Path(registry), Path(local), Path(binding)
    generation_registry, root = Path(generation_registry), Path(root)
    notebook_path = Path(notebook_path or root / "experiments/notebooks" / notebook_module.NAME)
    prep = json.loads((registry / "preparation_receipt.json").read_text(encoding="utf-8"))
    contract = json.loads((registry / validation.CONTRACT).read_text(encoding="utf-8"))
    package = local / "bundle"
    archive = local / bundle_module.ARCHIVE_NAME

    bundle_ok, bundle_detail = False, "private bundle not present on this machine"
    if package.exists():
        try:
            _, spec, _, rows = validation.validate_selection_scoring_bundle(package)
            bundle_ok = (len(rows) == validation.EXPECTED_ROWS
                         and sha(package / "package_manifest.json") == prep["manifest_sha256"] == sha(registry / "package_manifest.json")
                         and sha(package / validation.CONTRACT) == sha(registry / validation.CONTRACT)
                         and archive_matches(archive, package, prep["archive_sha256"]))
            bundle_detail = ("validator PASS on the built bundle (1,200 / 1,197 / 3); ZIP re-hashed and equal to the manifest; "
                             "manifest and contract equal the registry copies")
        except (ValueError, KeyError) as error:
            bundle_detail = f"bundle validation failed: {error}"
    generation_ok, generation_detail = False, "generation evidence ZIP not present on this machine"
    if Path(evidence_zip).exists():
        try:
            manifest_sha, _ = bundle_module.generation_hashes(evidence_zip, generation_registry)
            generation_ok = (sha(evidence_zip) == expected_evidence_sha == contract["generation_evidence_zip_sha256"]
                             == prep["generation_evidence_zip_sha256"]
                             and manifest_sha == contract["generation_bundle_manifest_sha256"] == prep["generation_bundle_manifest_sha256"])
            generation_detail = ("evidence ZIP re-hashed equals the contract; the shared ledger's bundle hash equals the contract "
                                 "(the hash the notebook opens the session with)")
        except (ValueError, KeyError) as error:
            generation_detail = f"generation binding failed: {error}"
    freeze_ok, freeze_detail = False, "frozen scorer files not readable"
    try:
        freeze = json.loads((binding / "scorer_freeze_receipt.json").read_text(encoding="utf-8"))
        spec = json.loads(bundle_module.SPEC.read_text(encoding="utf-8"))
        freeze_ok = (sha(binding / "scorer_freeze_receipt.json") == contract["scorer_freeze_receipt_sha256"]
                     and sha(bundle_module.SPEC) == freeze["scorer_spec"]["sha256"]
                     and all(sha(root / relative) == expected for relative, expected in spec["code_sha256"].items())
                     and all(sha(package / relative) == expected for relative, expected in spec["code_sha256"].items()))
        freeze_detail = "scorer v2 spec, code and freeze receipt re-hashed from disk and equal to the bundle contract"
    except (OSError, KeyError, ValueError) as error:
        freeze_detail = f"freeze check failed: {error}"
    locked_ok = all(sha(binding / name) == contract[key] for name, key in (
        ("admission_rules_v2.json", "admission_rules_v2_sha256"), ("decisions_261023_v1.json", "decisions_sha256")))
    try:
        outcome_path = generation_registry / "selection300_generation_outcome.json"
        outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
        audit_ok = outcome.get("audit_pass") is True and sha(outcome_path) == contract["selection_generation_outcome_sha256"]
    except (OSError, ValueError):
        audit_ok = False
    note_path = registry / "notebook_preparation.json"
    note = json.loads(note_path.read_text(encoding="utf-8")) if note_path.exists() else None
    notebook_ok = bool(note) and notebook_path.exists() and note["sha256"] == sha(notebook_path) and all(
        repr(value) in notebook_path.read_text(encoding="utf-8") for value in (
            prep["archive_sha256"], prep["manifest_sha256"], prep["generation_bundle_manifest_sha256"],
            prep["generation_evidence_zip_sha256"]))
    gates = {
        "scoring_bundle_for_1200_cells": _gate(bundle_ok, bundle_detail),
        "generation_hashes_bound": _gate(generation_ok, generation_detail),
        "scorer_v2_freeze_intact": _gate(freeze_ok, freeze_detail),
        "locked_rules_unchanged": _gate(locked_ok, "admission rules and decisions re-hashed equal to the contract"),
        "generation_audit_passed": _gate(audit_ok, "the generation outcome file still reports audit_pass and equals the contract hash"),
        "colab_notebook_prepared": _gate(notebook_ok, "notebook hash recorded and it embeds the scoring ZIP, manifest and both generation hashes"),
    }
    gates.update({name: _gate(False, reason) for name, reason in IN_SESSION_GATES.items()})
    blocking = [name for name, gate in gates.items() if gate["status"] != "PASS"]
    return {"schema_version": 1, "receipt_id": "tib-selection300-scoring-readiness-261024",
            "bundle": {"archive_sha256": prep["archive_sha256"], "manifest_sha256": prep["manifest_sha256"],
                       "generation_bundle_manifest_sha256": prep["generation_bundle_manifest_sha256"]},
            "gates": gates,
            "prepared_gates_pass": all(g["status"] == "PASS" for n, g in gates.items() if n not in IN_SESSION_GATES),
            "blocking_open_gates": blocking, "scoring_start_authorized": False, "selection_rule_applied": False,
            "ready_means": "prepared and bound, not permitted to run",
            "next_step": "User states explicitly to start; the agent then writes start_authorization_scoring.json bound to the "
                         "scoring manifest hash and this receipt's hash. Last authorized session: no spare session if scoring is cut short."}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    receipt = build()
    target = bundle_module.REGISTRY / RECEIPT_NAME
    write(target, receipt)
    print(json.dumps({"prepared_gates_pass": receipt["prepared_gates_pass"],
                      "blocking_open_gates": receipt["blocking_open_gates"], "receipt_sha256": sha(target)}, indent=2))


if __name__ == "__main__":
    main()
