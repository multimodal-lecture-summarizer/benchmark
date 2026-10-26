"""Readiness gates on the synthetic bundle: each prepared gate flips to OPEN when its evidence changes."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_selection300_scorer_bundle as bundle_module
from experiments.scripts import tib_selection300_scorer_notebook as notebook_module
from experiments.scripts import tib_selection300_scoring_readiness as readiness
from selection_scoring_fixtures import build_bundle, make_world, reseal


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("readiness")
    world = make_world(tmp)
    receipt, local, registry = build_bundle(world, tmp)
    root = tmp / "root"
    (root / "experiments/notebooks").mkdir(parents=True)
    notebook_module.create(registry=registry, root=root, expected_evidence_sha=world.archive_sha)
    return SimpleNamespace(world=world, local=local, registry=registry, root=root, receipt=receipt)


@pytest.fixture
def paths(prepared, tmp_path):
    """A private copy of every artifact the receipt reads, so a test can damage one without leaking."""
    copy = SimpleNamespace(local=tmp_path / "local", registry=tmp_path / "registry", binding=tmp_path / "binding",
                           generation=tmp_path / "generation", evidence=tmp_path / "evidence.zip", root=tmp_path / "root")
    shutil.copytree(prepared.local, copy.local)
    shutil.copytree(prepared.registry, copy.registry)
    shutil.copytree(prepared.world.binding, copy.binding)
    shutil.copytree(prepared.world.registry, copy.generation)
    shutil.copytree(prepared.root, copy.root)
    shutil.copyfile(prepared.world.archive, copy.evidence)
    return copy


def build(prepared, paths):
    return readiness.build(registry=paths.registry, local=paths.local, generation_registry=paths.generation,
                           binding=paths.binding, notebook_path=paths.root / "experiments/notebooks" / notebook_module.NAME,
                           evidence_zip=paths.evidence, expected_evidence_sha=prepared.world.archive_sha)


def test_prepared_gates_pass_and_session_gates_stay_open(prepared, paths):
    receipt = build(prepared, paths)
    assert receipt["prepared_gates_pass"] is True
    assert set(receipt["blocking_open_gates"]) == set(readiness.IN_SESSION_GATES)
    assert all(receipt["gates"][name]["status"] == "OPEN" for name in readiness.IN_SESSION_GATES)
    assert receipt["scoring_start_authorized"] is False and receipt["selection_rule_applied"] is False
    assert "not permitted to run" in receipt["ready_means"]
    assert receipt["bundle"]["generation_bundle_manifest_sha256"] == prepared.world.manifest_sha


def test_a_damaged_zip_opens_the_bundle_gate(prepared, paths):
    archive = paths.local / bundle_module.ARCHIVE_NAME
    archive.write_bytes(archive.read_bytes() + b"x")
    receipt = build(prepared, paths)
    assert receipt["gates"]["scoring_bundle_for_1200_cells"]["status"] == "OPEN" and receipt["prepared_gates_pass"] is False


def test_a_zip_with_different_bytes_but_same_manifest_opens_the_bundle_gate(prepared, paths):
    import zipfile
    archive = paths.local / bundle_module.ARCHIVE_NAME
    swapped = paths.local / "swapped.zip"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(swapped, "w") as dst:
        for name in src.namelist():
            dst.writestr(name, b"changed" if name == "scoring_outputs.jsonl" else src.read(name))
    prep = json.loads((paths.registry / "preparation_receipt.json").read_text())
    prep["archive_sha256"] = bundle_module.file_hash(swapped)
    (paths.registry / "preparation_receipt.json").write_text(json.dumps(prep))
    assert build(prepared, paths)["gates"]["scoring_bundle_for_1200_cells"]["status"] == "OPEN"


def test_an_edited_bundle_file_opens_the_bundle_gate(prepared, paths):
    path = paths.local / "bundle/scoring_contract.json"
    path.write_text(path.read_text().replace('"scoring_start_authorized": false', '"scoring_start_authorized": true'))
    reseal(paths.local / "bundle")
    assert build(prepared, paths)["gates"]["scoring_bundle_for_1200_cells"]["status"] == "OPEN"


def test_missing_private_bundle_opens_the_gate_instead_of_crashing(prepared, paths):
    shutil.rmtree(paths.local / "bundle")
    gate = build(prepared, paths)["gates"]["scoring_bundle_for_1200_cells"]
    assert gate["status"] == "OPEN" and "not present" in gate["detail"]


def test_a_changed_generation_zip_opens_the_generation_gate(prepared, paths):
    paths.evidence.write_bytes(paths.evidence.read_bytes() + b"x")
    assert build(prepared, paths)["gates"]["generation_hashes_bound"]["status"] == "OPEN"


def test_a_registry_manifest_that_disagrees_with_the_ledger_opens_the_generation_gate(prepared, paths):
    (paths.generation / "preparation_receipt.json").write_text(json.dumps({"manifest_sha256": "0" * 64}))
    assert build(prepared, paths)["gates"]["generation_hashes_bound"]["status"] == "OPEN"


def test_changed_locked_rules_or_freeze_open_their_gates(prepared, paths):
    (paths.binding / "admission_rules_v2.json").write_text("{}")
    receipt = build(prepared, paths)
    assert receipt["gates"]["locked_rules_unchanged"]["status"] == "OPEN"
    (paths.binding / "scorer_freeze_receipt.json").write_text("{}")
    assert build(prepared, paths)["gates"]["scorer_v2_freeze_intact"]["status"] == "OPEN"


def test_a_failed_generation_audit_opens_its_gate(prepared, paths):
    (paths.generation / "selection300_generation_outcome.json").write_text(json.dumps({"audit_pass": False}))
    assert build(prepared, paths)["gates"]["generation_audit_passed"]["status"] == "OPEN"


def test_an_edited_notebook_opens_the_notebook_gate(prepared, paths):
    notebook = paths.root / "experiments/notebooks" / notebook_module.NAME
    notebook.write_text(notebook.read_text().replace("RESUME = False", "RESUME = True"))
    assert build(prepared, paths)["gates"]["colab_notebook_prepared"]["status"] == "OPEN"


def test_a_notebook_built_for_other_hashes_opens_the_notebook_gate(prepared, paths):
    prep = json.loads((paths.registry / "preparation_receipt.json").read_text())
    prep["manifest_sha256"] = "9" * 64
    (paths.registry / "preparation_receipt.json").write_text(json.dumps(prep))
    assert build(prepared, paths)["gates"]["colab_notebook_prepared"]["status"] == "OPEN"
