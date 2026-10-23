"""Readiness receipt v2: closes the bundle and cohort-binding gates left OPEN by receipt v1.

Every gate recomputes hashes from files on disk. The receipt records bound artifacts only; the two
in-session gates (T4 preflight, Drive store check) stay OPEN and `selection_start_authorized` is a constant
False. v1 is never modified.
"""
import argparse
import json
from pathlib import Path
import zipfile

from experiments.scripts import tib_selection300_freeze as freeze
from experiments.scripts import tib_selection300_notebook as notebook
from experiments.scripts import tib_selection_validation as validation
from experiments.scripts.tib_pilot_bundle import ROOT, SEALED, sha, write
from experiments.scripts.tib_selection300_bundle import BINDING, LOCAL, REGISTRY

IN_SESSION_GATES = {
    "t4_preflight_first_session": "closes only inside the first Colab session (preflight_receipt.json)",
    "drive_store_check_first_session": "closes only inside the first Colab session (fsync/rename/readback probe)",
}


def _gate(passed, detail):
    return {"status": "PASS" if passed else "OPEN", "detail": detail}


ARCHIVE_NAME = "tib-selection300-generation-261023-v1.zip"


def archive_matches(archive, package, expected_sha):
    """The ZIP on disk hashes to the receipt and holds exactly the manifest's files with identical bytes."""
    archive, package = Path(archive), Path(package)
    if not archive.exists() or sha(archive) != expected_sha:
        return False
    manifest = json.loads((package / validation.MANIFEST).read_text(encoding="utf-8"))
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist()) != set(manifest["files"]) | {validation.MANIFEST}:
            return False
        import hashlib
        return all(hashlib.sha256(z.read(n)).hexdigest() == h for n, h in manifest["files"].items())


def build(registry=REGISTRY, binding=BINDING, package=None, notebook_path=None, sealed=SEALED, archive=None):
    registry, package = Path(registry), Path(package or LOCAL / "package")
    archive = Path(archive or LOCAL / ARCHIVE_NAME)
    notebook_path = Path(notebook_path or ROOT / "experiments/notebooks" / notebook.NAME)
    prep = json.loads((registry / "preparation_receipt.json").read_text(encoding="utf-8"))
    contract = json.loads((registry / "selection_contract.json").read_text(encoding="utf-8"))
    cohort = json.loads((Path(sealed) / "development_cohort.json").read_text(encoding="utf-8"))
    v1 = freeze.build_readiness_receipt(binding)
    bundle_ok, detail = False, "private package not present on this machine"
    if package.exists():
        try:
            validated, rows, manifest_sha = validation.validate_bundle(package)
            bundle_ok = (manifest_sha == prep["manifest_sha256"] == sha(registry / validation.MANIFEST)
                         and len(rows) == validation.SELECTION_N and validated == contract
                         and archive_matches(archive, package, prep["archive_sha256"]))
            detail = "validate_bundle PASS on the built package; ZIP re-hashed and equal to the package; manifest hash equals the preparation receipt"
        except ValueError as error:
            detail = f"validate_bundle failed: {error}"
    locked_ok = all(sha(Path(binding) / name) == expected for name, expected in contract["locked_artifacts"].items())
    cohort_ok = (contract["selection_ids"] == cohort["selected_ids"]["selection"] and contract["quotas"] == cohort["selection_quotas"]
                 and contract["sealed_cohort_sha256"] == sha(Path(sealed) / "development_cohort.json")
                 and contract["staged_ids"] == [] and contract["excluded_pilot_ids"] == cohort["selected_ids"]["pilot"])
    note = json.loads((registry / "notebook_preparation.json").read_text(encoding="utf-8")) if (registry / "notebook_preparation.json").exists() else None
    notebook_ok = bool(note) and notebook_path.exists() and note["sha256"] == sha(notebook_path) and all(
        repr(prep[key]) in notebook_path.read_text(encoding="utf-8") for key in ("archive_sha256", "manifest_sha256"))
    gates = {
        "binding_gates_v1": _gate(v1["binding_gates_pass"], "all receipt v1 binding gates re-verified from disk"),
        "generation_bundle_for_300_ids": _gate(bundle_ok and locked_ok, detail + "; locked artifacts match the contract"),
        "selection_cohort_hash_bound_to_bundle": _gate(cohort_ok, "contract IDs, quotas, staged_ids and cohort hash equal the sealed cohort"),
        "colab_notebook_prepared": _gate(notebook_ok, "notebook hash recorded and embeds the ZIP and manifest hashes"),
    }
    gates.update({name: _gate(False, reason) for name, reason in IN_SESSION_GATES.items()})
    blocking = [name for name, gate in gates.items() if gate["status"] != "PASS"]
    return {"schema_version": 1, "receipt_id": "tib-selection300-readiness-v2-261023",
            "supersedes_gates_of": "selection300_readiness_receipt.json (v1, unchanged)",
            "bundle": {"archive_sha256": prep["archive_sha256"], "manifest_sha256": prep["manifest_sha256"]},
            "gates": gates, "prepared_gates_pass": all(g["status"] == "PASS" for n, g in gates.items() if n not in IN_SESSION_GATES),
            "blocking_open_gates": blocking, "selection_start_authorized": False,
            "next_step": "User states explicitly to start; the agent then writes start_authorization.json bound to this manifest hash."}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    receipt = build()
    write(REGISTRY / "selection300_readiness_receipt_v2.json", receipt)
    print(json.dumps({"prepared_gates_pass": receipt["prepared_gates_pass"], "blocking_open_gates": receipt["blocking_open_gates"],
                      "receipt_sha256": sha(REGISTRY / "selection300_readiness_receipt_v2.json")}, indent=2))


if __name__ == "__main__":
    main()
