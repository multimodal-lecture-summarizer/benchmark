"""Reconciliation tests for Group 02 and Group 07 runners against real D2 artifacts and manifests."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from benchmarks.scripts import (
    run_keyframe_selection_benchmark,
    run_ocr_benchmark,
    run_scene_boundary_benchmark,
    run_visual_caption_benchmark,
)
from benchmarks.scripts.execute_all_notebooks import (
    _runner_source_path,
    build_plan,
    load_manifest,
    select_entries,
    validate_required_artifacts,
)
from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    write_json_artifact,
    write_run_manifest,
)

HASH_A = hashlib.sha256(b"fixture-source").hexdigest()
HASH_B = hashlib.sha256(b"fixture-config").hexdigest()
HASH_C = hashlib.sha256(b"fixture-dependency").hexdigest()


def _runner_args(artifact_root: Path, notebook_id: str, run_id: str) -> list[str]:
    return [
        "--profile",
        "full",
        "--run-namespace",
        "official",
        "--evidence-status",
        "real",
        "--artifact-root",
        str(artifact_root),
        "--notebook-id",
        notebook_id,
        "--run-id",
        run_id,
        "--source-sha256",
        HASH_A,
        "--config-sha256",
        HASH_B,
        "--dependency-state-sha256",
        HASH_C,
    ]


def _seed_audio_only_dataset(artifact_root: Path) -> None:
    """Seed a receipt-validated audio-only D2 fixture in the caller's temp root."""
    seed_context = RunnerContext(
        profile="full",
        run_namespace="official",
        status="real",
        artifact_root=artifact_root,
        notebook_id="00c_dataset_eda_and_freeze",
        run_id=str(uuid.uuid4()),
        source_sha256=HASH_A,
        config_sha256=HASH_B,
        dependency_state_sha256=HASH_C,
    )
    units = [{"unit_id": "audio-unit-1", "dataset_id": "audio_only"}]
    write_json_artifact(
        seed_context,
        "dataset.frozen_manifest",
        [{
            "dataset_id": "audio_only",
            "freeze_status": "eligible",
            "scientific_selection_eligible": True,
            "unit_ids": ["audio-unit-1"],
            "unit_records": units,
        }],
    )
    write_json_artifact(
        seed_context,
        "dataset.registry",
        [{"dataset_id": "audio_only", "acquisition_level": "D2"}],
    )
    write_json_artifact(
        seed_context,
        "dataset.endpoint_matrix",
        [{
            "dataset_id": "audio_only",
            "endpoint": "asr_benchmark",
            "scientific_selection_eligible": True,
        }],
    )
    write_run_manifest(seed_context)


# ---------------------------------------------------------------------------
# Phase 3: Group 02 Reconciliation
# ---------------------------------------------------------------------------




def test_group_02_entries_fail_closed_on_audio_only_dataset(tmp_path: Path) -> None:
    """Audio-only fixture cannot enter visual runners; no developer output dependency."""
    artifact_root = tmp_path / "artifacts"
    _seed_audio_only_dataset(artifact_root)

    # 02a: fails closed because TED-LIUM endpoint is asr_benchmark, not scene_boundary_benchmark
    rc_02a = run_scene_boundary_benchmark.main(
        _runner_args(artifact_root, "02a_scene_boundary_benchmark", str(uuid.uuid4()))
    )
    assert rc_02a == 1, "02a must fail closed on audio-only dataset"

    # 02b: fails closed because scene.raw_predictions is missing and dataset is audio-only
    rc_02b = run_keyframe_selection_benchmark.main(
        _runner_args(artifact_root, "02b_keyframe_selection_benchmark", str(uuid.uuid4()))
    )
    assert rc_02b == 1, "02b must fail closed on audio-only dataset"

    # 02c: fails closed because dataset is not eligible for OCR
    rc_02c = run_ocr_benchmark.main(
        _runner_args(artifact_root, "02c_ocr_benchmark", str(uuid.uuid4()))
    )
    assert rc_02c == 1, "02c must fail closed on audio-only dataset"

    # 02d: fails closed because keyframe.raw_predictions is missing and dataset is audio-only
    rc_02d = run_visual_caption_benchmark.main(
        _runner_args(artifact_root, "02d_visual_caption_benchmark", str(uuid.uuid4()))
    )
    assert rc_02d == 1, "02d must fail closed on audio-only dataset"


def test_group_02_dependency_propagation(tmp_path: Path) -> None:
    """Missing upstream predictions must block downstream group 02 runners before execution."""
    entries = {
        "02b_keyframe_selection_benchmark": {
            "requires": ["scene.raw_predictions"], "expected_schema_version": 1
        },
        "02d_visual_caption_benchmark": {
            "requires": ["keyframe.raw_predictions"], "expected_schema_version": 1
        },
    }

    # 02b requires scene.raw_predictions
    errs_02b = validate_required_artifacts(
        entries["02b_keyframe_selection_benchmark"],
        tmp_path / "artifacts",
        "full",
        "official",
    )
    assert any("scene.raw_predictions" in e for e in errs_02b)

    # 02d requires keyframe.raw_predictions
    errs_02d = validate_required_artifacts(
        entries["02d_visual_caption_benchmark"],
        tmp_path / "artifacts",
        "full",
        "official",
    )
    assert any("keyframe.raw_predictions" in e for e in errs_02d)

