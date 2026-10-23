"""Readiness receipt v2 re-verifies hashes from disk and can never authorize a start."""
import json
import shutil

import pytest

from experiments.scripts import tib_selection300_readiness as readiness
from experiments.scripts.tib_selection300_bundle import LOCAL, REGISTRY

pytestmark = pytest.mark.skipif(not (LOCAL / "package").exists() or not (REGISTRY / "notebook_preparation.json").exists(),
                                reason="built private package and notebook preparation required")


@pytest.fixture
def registry(tmp_path):
    dest = tmp_path / "gen-registry"
    shutil.copytree(REGISTRY, dest)
    return dest


def status(receipt, gate):
    return receipt["gates"][gate]["status"]


def test_built_artifacts_close_the_prepared_gates_and_keep_session_gates_open(registry):
    receipt = readiness.build(registry)
    assert receipt["prepared_gates_pass"] is True and receipt["selection_start_authorized"] is False
    assert set(receipt["blocking_open_gates"]) == set(readiness.IN_SESSION_GATES)
    for gate in ("generation_bundle_for_300_ids", "selection_cohort_hash_bound_to_bundle", "colab_notebook_prepared", "binding_gates_v1"):
        assert status(receipt, gate) == "PASS", gate


def test_edited_contract_turns_the_bundle_and_cohort_gates_open(registry):
    contract = json.loads((registry / "selection_contract.json").read_text())
    contract["quotas"] = {"short": 99, "medium": 91, "long": 110}
    (registry / "selection_contract.json").write_text(json.dumps(contract))
    receipt = readiness.build(registry)
    assert status(receipt, "generation_bundle_for_300_ids") == "OPEN" and status(receipt, "selection_cohort_hash_bound_to_bundle") == "OPEN"
    assert receipt["prepared_gates_pass"] is False


def test_notebook_hash_drift_turns_its_gate_open(registry):
    note = json.loads((registry / "notebook_preparation.json").read_text())
    note["sha256"] = "0" * 64
    (registry / "notebook_preparation.json").write_text(json.dumps(note))
    assert status(readiness.build(registry), "colab_notebook_prepared") == "OPEN"


def test_tampered_package_file_turns_the_bundle_gate_open(registry, tmp_path):
    package = tmp_path / "package"
    shutil.copytree(LOCAL / "package", package)
    (package / "node_forecast.json").write_text('{"stage_seconds": {}}')
    assert status(readiness.build(registry, package=package), "generation_bundle_for_300_ids") == "OPEN"


def test_missing_private_package_leaves_the_bundle_gate_open(registry, tmp_path):
    assert status(readiness.build(registry, package=tmp_path / "absent"), "generation_bundle_for_300_ids") == "OPEN"


def test_written_receipt_never_authorizes_a_start():
    for path in REGISTRY.glob("*.json"):
        assert json.loads(path.read_text()).get("selection_start_authorized", False) is False, path.name


def test_stale_or_edited_zip_turns_the_bundle_gate_open(registry, tmp_path):
    archive = tmp_path / readiness.ARCHIVE_NAME
    shutil.copyfile(LOCAL / readiness.ARCHIVE_NAME, archive)
    assert status(readiness.build(registry, archive=archive), "generation_bundle_for_300_ids") == "PASS"
    with archive.open("ab") as handle:
        handle.write(b"tail")
    assert status(readiness.build(registry, archive=archive), "generation_bundle_for_300_ids") == "OPEN"
    assert status(readiness.build(registry, archive=tmp_path / "missing.zip"), "generation_bundle_for_300_ids") == "OPEN"
