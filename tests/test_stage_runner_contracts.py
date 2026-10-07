"""Stage runners reject an ineligible dataset freeze."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from benchmarks.scripts import run_asr_model_benchmark, run_scene_boundary_benchmark
from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    write_json_artifact,
    write_run_manifest,
)

HASH_A = hashlib.sha256(b"fixture-source").hexdigest()
HASH_B = hashlib.sha256(b"fixture-config").hexdigest()
HASH_C = hashlib.sha256(b"fixture-dependency").hexdigest()


def _runner_args(artifact_root: Path, notebook_id: str) -> list[str]:
    return [
        "--profile", "full", "--run-namespace", "official",
        "--evidence-status", "real", "--artifact-root", str(artifact_root),
        "--notebook-id", notebook_id, "--run-id", str(uuid.uuid4()),
        "--source-sha256", HASH_A, "--config-sha256", HASH_B,
        "--dependency-state-sha256", HASH_C,
    ]


def test_stage_runners_fail_without_eligible_freeze(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    context = RunnerContext(
        profile="full", run_namespace="official", status="real",
        artifact_root=artifact_root, notebook_id="00c_dataset_eda_and_freeze",
        run_id=str(uuid.uuid4()), source_sha256=HASH_A,
        config_sha256=HASH_B, dependency_state_sha256=HASH_C,
    )
    write_json_artifact(context, "dataset.frozen_manifest", [{
        "dataset_id": "blocked", "freeze_status": "not_eligible",
        "scientific_selection_eligible": False, "unit_ids": [],
        "reason": "blocked fixture", "profile": "full",
    }])
    write_json_artifact(context, "dataset.registry", [
        {"dataset_id": "blocked", "revision": "x", "acquisition_level": "D0"}
    ])
    write_run_manifest(context)
    assert run_scene_boundary_benchmark.main(
        _runner_args(artifact_root, "02a_scene_boundary_benchmark")
    ) == 1
    assert run_asr_model_benchmark.main(
        _runner_args(artifact_root, "01a_asr_model_benchmark")
    ) == 1
