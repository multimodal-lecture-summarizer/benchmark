"""Final523 readiness receipt: every prepared gate is recomputed from files on disk; the run stays unauthorized.

The two in-session gates (T4 preflight, Drive store check) close only inside the first Colab session, and
`final_test_authorized` / `selection_start_authorized` are constant False here: a start needs the user's own
start_authorization.json bound to the manifest hash.
"""
import argparse
import json
from pathlib import Path

from experiments.scripts import tib_final523_notebook as notebook
from experiments.scripts import tib_selection300_freeze as freeze
from experiments.scripts import tib_selection_validation as validation
from experiments.scripts.tib_final523_bundle import (
    ANALYSIS, ARCHIVE_NAME, FINAL_COHORT, LOCAL, LOCKED_FROM, REGISTRY, locked_choice,
)
from experiments.scripts.tib_pilot_bundle import ROOT, sha, write
from experiments.scripts.tib_selection300_bundle import SHIPPED_MODULES
from experiments.scripts.tib_selection300_readiness import IN_SESSION_GATES, _gate, archive_matches

RECEIPT_NAME = "final523_readiness_receipt.json"


def build(registry=REGISTRY, package=None, notebook_path=None, archive=None, analysis=ANALYSIS):
    registry, package = Path(registry), Path(package or LOCAL / "package")
    archive = Path(archive or LOCAL / ARCHIVE_NAME)
    notebook_path = Path(notebook_path or ROOT / "experiments/notebooks" / notebook.NAME)
    prep = json.loads((registry / "preparation_receipt.json").read_text(encoding="utf-8"))
    contract = json.loads((registry / "selection_contract.json").read_text(encoding="utf-8"))
    cohort = json.loads((registry / FINAL_COHORT).read_text(encoding="utf-8"))
    v1 = freeze.build_readiness_receipt()
    bundle_ok, detail = False, "private package not present on this machine"
    if package.exists():
        try:
            validated, rows, manifest_sha = validation.validate_bundle(package, expected_stage="final523")
            stale = [m for m in SHIPPED_MODULES
                     if sha(package / "experiments/scripts" / (m + ".py")) != sha(ROOT / "experiments/scripts" / (m + ".py"))]
            if stale:
                raise ValueError("shipped modules differ from the repository copies: " + ", ".join(stale))
            bundle_ok = (manifest_sha == prep["manifest_sha256"] == sha(registry / validation.MANIFEST)
                         and len(rows) == validation.FINAL_N and validated == contract
                         and archive_matches(archive, package, prep["archive_sha256"]))
            detail = "validate_bundle PASS on the built package; ZIP re-hashed and equal to the package; manifest hash equals the preparation receipt"
        except ValueError as error:
            detail = f"validate_bundle failed: {error}"
    locked_ok = all(sha(Path(LOCKED_FROM[name]) / name) == expected for name, expected in contract["locked_artifacts"].items())
    cohort_ok = (contract["selection_ids"] == cohort["selected_ids"] and contract["quotas"] == cohort["quotas"]
                 and contract["final_cohort_sha256"] == sha(registry / FINAL_COHORT) and contract["staged_ids"] == []
                 and cohort["final_test_sealed"] is True and cohort["final_test_authorized"] is False)
    try:
        choice_ok = contract["locked_choice"] == locked_choice(analysis) and contract["locked_choice"]["selected_profile"] in validation.CANDIDATES
    except ValueError:
        choice_ok = False
    note_path = registry / "notebook_preparation.json"
    note = json.loads(note_path.read_text(encoding="utf-8")) if note_path.exists() else None
    notebook_ok = bool(note) and notebook_path.exists() and note["sha256"] == sha(notebook_path) and all(
        repr(prep[key]) in notebook_path.read_text(encoding="utf-8") for key in ("archive_sha256", "manifest_sha256"))
    gates = {
        "binding_gates_v1": _gate(v1["binding_gates_pass"], "all receipt v1 binding gates re-verified from disk"),
        "generation_bundle_for_523_ids": _gate(bundle_ok and locked_ok, detail + "; locked artifacts match the contract"),
        "final_cohort_sealed_and_bound": _gate(cohort_ok, "contract IDs, quotas and seal hash equal the sealed final cohort; sealed, unauthorized"),
        "selection_choice_locked": _gate(choice_ok, "contract carries the selected result and its hash equals the selection300 analysis result"),
        "colab_notebook_prepared": _gate(notebook_ok, "notebook hash recorded and embeds the ZIP and manifest hashes"),
    }
    gates.update({name: _gate(False, reason) for name, reason in IN_SESSION_GATES.items()})
    blocking = [name for name, gate in gates.items() if gate["status"] != "PASS"]
    return {"schema_version": 1, "receipt_id": "tib-final523-readiness-261024",
            "bundle": {"archive_sha256": prep["archive_sha256"], "manifest_sha256": prep["manifest_sha256"]},
            "gates": gates, "prepared_gates_pass": all(g["status"] == "PASS" for n, g in gates.items() if n not in IN_SESSION_GATES),
            "blocking_open_gates": blocking, "final_test_authorized": False, "selection_start_authorized": False,
            "next_step": "User states explicitly to start; start_authorization.json is then written bound to this manifest hash."}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    receipt = build()
    write(REGISTRY / RECEIPT_NAME, receipt)
    print(json.dumps({"prepared_gates_pass": receipt["prepared_gates_pass"], "blocking_open_gates": receipt["blocking_open_gates"],
                      "receipt_sha256": sha(REGISTRY / RECEIPT_NAME)}, indent=2))


if __name__ == "__main__":
    main()
