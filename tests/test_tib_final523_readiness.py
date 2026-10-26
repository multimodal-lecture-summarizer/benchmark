"""Final523 readiness receipt recomputed from disk: prepared gates pass, in-session gates stay open, tampering is caught."""
import json
import shutil

import pytest

from experiments.scripts import tib_final523_notebook as notebook
from experiments.scripts import tib_final523_readiness as readiness


needs_package = pytest.mark.skipif(not (readiness.LOCAL / 'package').exists(), reason='private package not on this machine')


@needs_package
def test_prepared_gates_pass_and_only_session_gates_are_open():
    receipt = readiness.build()
    assert receipt["prepared_gates_pass"] is True
    assert receipt["blocking_open_gates"] == ["t4_preflight_first_session", "drive_store_check_first_session"]
    assert receipt["final_test_authorized"] is False and receipt["selection_start_authorized"] is False


def test_a_changed_notebook_opens_the_notebook_gate(tmp_path):
    changed = tmp_path / notebook.NAME
    changed.write_text(readiness.ROOT.joinpath("experiments/notebooks", notebook.NAME).read_text(encoding="utf-8") + " ",
                       encoding="utf-8")
    receipt = readiness.build(notebook_path=changed)
    assert receipt["gates"]["colab_notebook_prepared"]["status"] == "OPEN" and receipt["prepared_gates_pass"] is False


def test_a_drifted_seal_opens_the_cohort_gate(tmp_path):
    registry = tmp_path / "registry"
    shutil.copytree(readiness.REGISTRY, registry)
    cohort_path = registry / readiness.FINAL_COHORT
    cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
    cohort["selected_ids"] = cohort["selected_ids"][::-1]
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    receipt = readiness.build(registry=registry)
    assert receipt["gates"]["final_cohort_sealed_and_bound"]["status"] == "OPEN" and receipt["prepared_gates_pass"] is False


def test_a_missing_package_is_open_not_an_error(tmp_path):
    receipt = readiness.build(package=tmp_path / "absent")
    assert receipt["gates"]["generation_bundle_for_523_ids"]["status"] == "OPEN"


@needs_package
def test_a_shipped_module_that_differs_from_the_repository_opens_the_bundle_gate(tmp_path):
    package = tmp_path / "package"
    shutil.copytree(readiness.LOCAL / "package", package)
    target = package / "experiments/scripts/tib_selection_validation.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    receipt = readiness.build(package=package)
    gate = receipt["gates"]["generation_bundle_for_523_ids"]
    assert gate["status"] == "OPEN" and "tib_selection_validation" in gate["detail"]
