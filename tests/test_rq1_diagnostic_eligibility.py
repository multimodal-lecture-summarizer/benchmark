"""Diagnostic RQ1 cohorts must remain separate from official selection."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from experiments.scripts.benchmark_artifacts import RunnerContext, write_json_artifact, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import load_eligible_units


def _context(root: Path, namespace: str, notebook_id: str) -> RunnerContext:
    return RunnerContext(
        profile="full",
        run_namespace=namespace,
        status="real",
        artifact_root=root,
        notebook_id=notebook_id,
        run_id="diagnostic-eligibility-fixture",
        source_sha256=hashlib.sha256(b"source").hexdigest(),
        config_sha256=hashlib.sha256(b"config").hexdigest(),
        dependency_state_sha256=hashlib.sha256(b"dependencies").hexdigest(),
    )


def _seed(
    context: RunnerContext,
    *,
    frozen_scientific: bool,
    endpoint_scientific: bool,
    frozen_diagnostic: object = None,
    endpoint_diagnostic: object = None,
    freeze_status: str = "eligible",
) -> None:
    frozen = {
        "dataset_id": "local_course",
        "freeze_status": freeze_status,
        "scientific_selection_eligible": frozen_scientific,
        "unit_ids": ["lecture_01"],
        "unit_records": [{"unit_id": "lecture_01", "split": "validation"}],
    }
    endpoint = {
        "dataset_id": "local_course",
        "endpoint": "chaptering_benchmark",
        "scientific_selection_eligible": endpoint_scientific,
    }
    if frozen_diagnostic is not None:
        frozen["diagnostic_selection_eligible"] = frozen_diagnostic
    if endpoint_diagnostic is not None:
        endpoint["diagnostic_selection_eligible"] = endpoint_diagnostic
    write_json_artifact(context, "dataset.frozen_manifest", [frozen])
    write_json_artifact(context, "dataset.registry", [{"dataset_id": "local_course"}])
    write_json_artifact(context, "dataset.endpoint_matrix", [endpoint])
    write_run_manifest(context)


def test_explicit_diagnostic_flags_allow_only_diagnostic_namespace(tmp_path: Path) -> None:
    seed = _context(tmp_path, "diagnostic", "00c_dataset_eda_and_freeze")
    _seed(seed, frozen_scientific=False, endpoint_scientific=False,
          frozen_diagnostic=True, endpoint_diagnostic=True)
    diagnostic = _context(tmp_path, "diagnostic", "04a_chaptering_benchmark")
    assert [unit["unit_id"] for unit in load_eligible_units(diagnostic)] == ["lecture_01"]

    official_seed = _context(tmp_path, "official", "00c_dataset_eda_and_freeze")
    _seed(official_seed, frozen_scientific=False, endpoint_scientific=False,
          frozen_diagnostic=True, endpoint_diagnostic=True)
    official = _context(tmp_path, "official", "04a_chaptering_benchmark")
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units"):
        load_eligible_units(official)


@pytest.mark.parametrize("frozen_diagnostic,endpoint_diagnostic", [(None, True), (True, None), (False, True), (True, False)])
def test_diagnostic_requires_both_explicit_flags(
    tmp_path: Path, frozen_diagnostic: object, endpoint_diagnostic: object
) -> None:
    seed = _context(tmp_path, "diagnostic", "00c_dataset_eda_and_freeze")
    _seed(seed, frozen_scientific=False, endpoint_scientific=False,
          frozen_diagnostic=frozen_diagnostic, endpoint_diagnostic=endpoint_diagnostic)
    runner = _context(tmp_path, "diagnostic", "04a_chaptering_benchmark")
    with pytest.raises(RuntimeError, match="no diagnostically or scientifically eligible frozen units"):
        load_eligible_units(runner)


def test_scientifically_eligible_units_remain_available_in_diagnostic(tmp_path: Path) -> None:
    seed = _context(tmp_path, "diagnostic", "00c_dataset_eda_and_freeze")
    _seed(seed, frozen_scientific=True, endpoint_scientific=True)
    runner = _context(tmp_path, "diagnostic", "04a_chaptering_benchmark")
    assert len(load_eligible_units(runner)) == 1


def test_diagnostic_flag_cannot_override_ineligible_freeze(tmp_path: Path) -> None:
    seed = _context(tmp_path, "diagnostic", "00c_dataset_eda_and_freeze")
    _seed(seed, frozen_scientific=False, endpoint_scientific=False,
          frozen_diagnostic=True, endpoint_diagnostic=True, freeze_status="ineligible")
    runner = _context(tmp_path, "diagnostic", "04a_chaptering_benchmark")
    with pytest.raises(RuntimeError, match="no diagnostically or scientifically eligible frozen units"):
        load_eligible_units(runner)


def test_diagnostic_endpoint_flag_must_be_boolean(tmp_path: Path) -> None:
    seed = _context(tmp_path, "diagnostic", "00c_dataset_eda_and_freeze")
    _seed(seed, frozen_scientific=False, endpoint_scientific=False,
          frozen_diagnostic=True, endpoint_diagnostic="yes")
    runner = _context(tmp_path, "diagnostic", "04a_chaptering_benchmark")
    with pytest.raises(RuntimeError, match="boolean diagnostic_selection_eligible"):
        load_eligible_units(runner)
