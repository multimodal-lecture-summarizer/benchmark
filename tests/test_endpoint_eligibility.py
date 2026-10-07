"""Focused regression and contract tests for fail-closed endpoint eligibility."""

from __future__ import annotations

import json
import hashlib
import uuid
from pathlib import Path
from typing import Any

import pytest

from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
)

HASH_A = hashlib.sha256(b"fixture-source").hexdigest()
HASH_B = hashlib.sha256(b"fixture-config").hexdigest()
HASH_C = hashlib.sha256(b"fixture-dependency").hexdigest()


def _create_context(
    artifact_root: Path,
    notebook_id: str,
    *,
    profile: str = "full",
    run_namespace: str = "official",
    status: str = "real",
) -> RunnerContext:
    return RunnerContext(
        profile=profile,
        run_namespace=run_namespace,
        status=status,
        artifact_root=artifact_root,
        notebook_id=notebook_id,
        run_id=str(uuid.uuid4()),
        source_sha256=HASH_A,
        config_sha256=HASH_B,
        dependency_state_sha256=HASH_C,
    )


def _seed_base_artifacts(
    context: RunnerContext,
    *,
    dataset_id: str = "test_ds",
    unit_count: int = 5,
    freeze_status: str = "eligible",
    scientific_selection_eligible: bool = True,
) -> None:
    unit_records = [
        {"unit_id": f"u{i}", "talk_id": f"t{i}", "reference_text": f"text {i}"}
        for i in range(unit_count)
    ]
    unit_ids = [u["unit_id"] for u in unit_records]
    write_json_artifact(
        context,
        "dataset.frozen_manifest",
        [
            {
                "dataset_id": dataset_id,
                "freeze_status": freeze_status,
                "scientific_selection_eligible": scientific_selection_eligible,
                "unit_ids": unit_ids,
                "unit_records": unit_records,
                "reason": "test frozen manifest",
                "profile": context.profile,
            }
        ],
    )
    write_json_artifact(
        context,
        "dataset.registry",
        [
            {
                "dataset_id": dataset_id,
                "revision": "r1",
                "acquisition_level": "D2",
                "rights": "open",
                "access_status": "local",
                "ground_truth_status": "released",
            }
        ],
    )
    write_run_manifest(context)


@pytest.mark.parametrize("allow_fixture_without_matrix", [False, True])
def test_absent_endpoint_matrix_receipt_fails_closed(
    tmp_path: Path, allow_fixture_without_matrix: bool
) -> None:
    """Missing dataset.endpoint_matrix receipt must fail closed with actionable error."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="missing.*dataset\\.endpoint_matrix receipt"):
        load_eligible_units(
            ctx_runner, allow_fixture_without_matrix=allow_fixture_without_matrix
        )


def test_malformed_endpoint_matrix_fails_closed(tmp_path: Path) -> None:
    """Malformed endpoint matrix (missing required schema fields) fails closed."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)

    # Write invalid endpoint records (missing scientific_selection_eligible)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [{"dataset_id": "test_ds", "endpoint": "asr_benchmark"}],
    )

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="boolean scientific_selection_eligible"):
        load_eligible_units(ctx_runner)


@pytest.mark.parametrize("notebook_id", ["01a_asr_model_benchmark", "01c_asr_architecture_benchmark"])
def test_tedlium_diagnostic_flags_and_self_asserted_audit_hash_cannot_open_gate(
    tmp_path: Path, notebook_id: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze", run_namespace="diagnostic")
    records = [{"unit_id": "validation:u1", "split": "validation", "reference_text": "hello"}]
    common = {
        "dataset_id": "tedlium3", "scientific_selection_eligible": False,
        "diagnostic_selection_eligible": True,
        "train_evaluation_media_audit_status": "verified",
        "train_evaluation_media_audit_sha256": "a" * 64,
    }
    write_json_artifact(seed, "dataset.frozen_manifest", [{
        **common, "freeze_status": "eligible", "unit_ids": ["validation:u1"],
        "unit_records": records,
    }])
    write_json_artifact(seed, "dataset.registry", [{**common, "revision": "old-freeze"}])
    write_json_artifact(seed, "dataset.endpoint_matrix", [{
        **common, "endpoint": "asr_benchmark",
    }])
    write_run_manifest(seed)

    runner = _create_context(artifact_root, notebook_id,
                             run_namespace="diagnostic")
    with pytest.raises(RuntimeError, match="no diagnostically or scientifically eligible"):
        load_eligible_units(runner, allowed_splits={"validation"})


@pytest.mark.parametrize("notebook_id", ["01a_asr_model_benchmark", "01c_asr_architecture_benchmark"])
def test_tedlium_bounded_metadata_screen_opens_diagnostic_gate(
    tmp_path: Path, notebook_id: str,
) -> None:
    artifact_root = tmp_path / "artifacts"
    seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze", run_namespace="diagnostic")
    metadata_hash, media_hash = hashlib.sha256(b"metadata").hexdigest(), hashlib.sha256(b"media").hexdigest()
    screen = {
        "train_evaluation_media_audit_status": "metadata_screened_audio_overlap_unverified",
        "metadata_cohort_sha256": metadata_hash,
        "media_cohort_sha256": media_hash,
    }
    common = {"dataset_id": "tedlium3", "scientific_selection_eligible": False,
              "diagnostic_selection_eligible": True, **screen}
    record = {"unit_id": "validation:u1", "split": "validation", "reference_text": "hello"}
    write_json_artifact(seed, "dataset.frozen_manifest", [{
        **common, "freeze_status": "eligible", "unit_ids": [record["unit_id"]],
        "unit_records": [record],
    }])
    write_json_artifact(seed, "dataset.registry", [{**common, "revision": "local-arrow-snapshot"}])
    write_json_artifact(seed, "dataset.endpoint_matrix", [{**common, "endpoint": "asr_benchmark"}])
    write_run_manifest(seed)

    runner = _create_context(artifact_root, notebook_id,
                             run_namespace="diagnostic")
    units = load_eligible_units(runner, allowed_splits={"validation"})
    assert [unit["unit_id"] for unit in units] == [record["unit_id"]]


@pytest.mark.parametrize("run_namespace", ["diagnostic", "official"])
@pytest.mark.parametrize("notebook_id", ["01a_asr_model_benchmark", "01c_asr_architecture_benchmark"])
def test_tedlium_metadata_screen_cannot_open_scientific_gate(
    tmp_path: Path, run_namespace: str, notebook_id: str,
) -> None:
    artifact_root = tmp_path / run_namespace
    seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze", run_namespace=run_namespace)
    metadata_hash, media_hash = hashlib.sha256(b"metadata").hexdigest(), hashlib.sha256(b"media").hexdigest()
    claims = {
        "dataset_id": "tedlium3", "scientific_selection_eligible": True,
        "diagnostic_selection_eligible": True,
        "train_evaluation_media_audit_status": "metadata_screened_audio_overlap_unverified",
        "metadata_cohort_sha256": metadata_hash, "media_cohort_sha256": media_hash,
    }
    unit = {"unit_id": "validation:u1", "split": "validation", "reference_text": "hello"}
    write_json_artifact(seed, "dataset.frozen_manifest", [{
        **claims, "freeze_status": "eligible", "unit_ids": [unit["unit_id"]],
        "unit_records": [unit],
    }])
    write_json_artifact(seed, "dataset.registry", [{**claims, "revision": "local-arrow-snapshot"}])
    write_json_artifact(seed, "dataset.endpoint_matrix", [{**claims, "endpoint": "asr_benchmark"}])
    write_run_manifest(seed)

    runner = _create_context(artifact_root, notebook_id, run_namespace=run_namespace)
    with pytest.raises(RuntimeError, match="no .* eligible frozen units"):
        load_eligible_units(runner, allowed_splits={"validation"})


@pytest.mark.parametrize("schema_version", [None, 2, True, 1.0])
def test_endpoint_matrix_requires_supported_payload_schema(
    tmp_path: Path, schema_version: Any
) -> None:
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [{
            "dataset_id": "test_ds",
            "endpoint": "asr_benchmark",
            "scientific_selection_eligible": True,
        }],
    )
    payload_path = ctx_seed.namespace_root / "payloads/dataset.endpoint_matrix.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if schema_version is None:
        payload.pop("schema_version")
    else:
        payload["schema_version"] = schema_version
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = ctx_seed.namespace_root / "dataset.endpoint_matrix.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["sha256"] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="unsupported or missing payload schema_version"):
        load_eligible_units(ctx_runner)


def test_stale_receipt_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    """Receipt hash mismatch or altered payload fails closed before model execution."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid",
            }
        ],
    )

    # Tamper with the receipt sha256
    receipt_path = ctx_seed.namespace_root / "dataset.endpoint_matrix.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="failed to read or validate dataset\\.endpoint_matrix"):
        load_eligible_units(ctx_runner)


def test_endpoint_row_false_fails_closed(tmp_path: Path) -> None:
    """scientific_selection_eligible: false blocks selection for that endpoint."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "ineligible_audit",
                "scientific_selection_eligible": False,
                "reason": "audit failed",
            }
        ],
    )

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units for endpoint"):
        load_eligible_units(ctx_runner)


def test_unknown_endpoint_fails_closed(tmp_path: Path) -> None:
    """Unknown requested endpoint blocks selection."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid",
            }
        ],
    )

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units for endpoint in \\['nonexistent_endpoint'\\]"):
        load_eligible_units(ctx_runner, endpoint="nonexistent_endpoint")


def test_eligible_asr_row_selects_units(tmp_path: Path) -> None:
    """Eligible ASR row selects all units for ASR benchmarks."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed, unit_count=5)
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid ASR",
            }
        ],
    )

    ctx_runner = _create_context(artifact_root, "01a_asr_model_benchmark")
    units = load_eligible_units(ctx_runner)
    assert len(units) == 5
    assert [u["unit_id"] for u in units] == [f"u{i}" for i in range(5)]


def test_audio_only_dataset_rejected_by_visual_runners(tmp_path: Path) -> None:
    """Audio-only fixture cannot enter visual runners, independent of local outputs."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed, dataset_id="audio_only")
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [{
            "dataset_id": "audio_only",
            "endpoint": "asr_benchmark",
            "eligibility": "eligible_d2",
            "scientific_selection_eligible": True,
        }],
    )
    for visual_notebook in (
        "02a_scene_boundary_benchmark",
        "02b_keyframe_selection_benchmark",
        "02c_ocr_benchmark",
        "02d_visual_caption_benchmark",
    ):
        ctx = _create_context(artifact_root, visual_notebook)
        with pytest.raises(RuntimeError, match="no scientifically eligible frozen units for endpoint"):
            load_eligible_units(ctx)


def test_composite_runner_selection_requires_all_modalities(tmp_path: Path) -> None:
    """Composite runners (07b, 08b) fail closed if dataset lacks any required modality."""
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed, unit_count=3)

    # 1. Dataset only eligible for ASR
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid ASR",
            }
        ],
    )
    ctx_07b = _create_context(artifact_root, "07b_error_propagation")
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units for endpoint"):
        load_eligible_units(ctx_07b)

    # 2. ASR and Scene alone are insufficient: 07b also reads OCR/detection/tracking.
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": "asr_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid ASR",
            },
            {
                "dataset_id": "test_ds",
                "endpoint": "scene_boundary_benchmark",
                "eligibility": "eligible_d2",
                "scientific_selection_eligible": True,
                "reason": "valid Scene",
            },
        ],
    )
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units"):
        load_eligible_units(ctx_07b)

    # 3. All declared 07b upstream capabilities allow selection.
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {
                "dataset_id": "test_ds",
                "endpoint": endpoint,
                "scientific_selection_eligible": True,
            }
            for endpoint in (
                "asr_benchmark",
                "scene_boundary_benchmark",
                "ocr_benchmark",
                "object_detection_benchmark",
                "multi_object_tracking_benchmark",
            )
        ],
    )
    units_07b = load_eligible_units(ctx_07b)
    assert len(units_07b) == 3

    # 4. For 08b, still fails because summary and QA are missing.
    ctx_08b = _create_context(artifact_root, "08b_end_to_end_system")
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units for endpoint"):
        load_eligible_units(ctx_08b)


def test_stage_compatibility_requires_all_compared_stage_capabilities(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    ctx_seed = _create_context(artifact_root, "00c_dataset_eda_and_freeze")
    _seed_base_artifacts(ctx_seed, unit_count=2)
    required = [
        "asr_benchmark",
        "scene_boundary_benchmark",
        "keyframe_selection_benchmark",
        "ocr_benchmark",
        "visual_caption_benchmark",
        "object_detection_benchmark",
        "multi_object_tracking_benchmark",
        "chaptering_benchmark",
        "summarization_benchmark",
        "retrieval_benchmark",
        "qa_generation_benchmark",
    ]
    ctx_08a = _create_context(artifact_root, "08a_stage_compatibility")
    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {"dataset_id": "test_ds", "endpoint": endpoint,
             "scientific_selection_eligible": True}
            for endpoint in required[:-1]
        ],
    )
    with pytest.raises(RuntimeError, match="no scientifically eligible frozen units"):
        load_eligible_units(ctx_08a)

    write_json_artifact(
        ctx_seed,
        "dataset.endpoint_matrix",
        [
            {"dataset_id": "test_ds", "endpoint": endpoint,
             "scientific_selection_eligible": True}
            for endpoint in required
        ],
    )
    assert len(load_eligible_units(ctx_08a)) == 2
