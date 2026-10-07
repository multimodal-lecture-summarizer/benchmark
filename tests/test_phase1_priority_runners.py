from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

import nbformat
import pytest

from benchmarks.scripts.execute_all_notebooks import (
    _entry_config_sha256,
    _fallback_only_errors,
    _sha256,
    _scientifically_empty_errors,
    _validate_payload,
    build_plan,
    can_resume,
    load_manifest,
    main as executor_main,
    notebook_source_sha256,
    select_entries,
    validate_produced_artifacts,
    validate_required_artifacts,
)
from experiments.scripts import environment_preflight, probe_dataset_feasibility
from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    write_json_artifact,
    write_run_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HASH_A = hashlib.sha256(b"fixture-source").hexdigest()
HASH_B = hashlib.sha256(b"fixture-config").hexdigest()
HASH_C = hashlib.sha256(b"fixture-dependency").hexdigest()


def _runner_args(artifact_root: Path, notebook_id: str, run_id: str) -> list[str]:
    return [
        "--profile",
        "smoke",
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


def _context(run_id: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "status": "real",
        "source_sha256": HASH_A,
        "config_sha256": HASH_B,
        "dependency_state_sha256": HASH_C,
    }




def test_direct_and_module_executor_entrypoints_match() -> None:
    direct = subprocess.run(
        [sys.executable, "benchmarks/scripts/execute_all_notebooks.py", "--list", "--profile", "full"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    module = subprocess.run(
        [sys.executable, "-m", "benchmarks.scripts.execute_all_notebooks", "--list", "--profile", "full"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert direct.returncode == module.returncode == 0
    assert direct.stdout == module.stdout
    assert len(direct.stdout.strip().splitlines()) == 0


def test_fallback_only_scientific_artifact_cannot_be_official_success(tmp_path: Path) -> None:
    context = RunnerContext(
        profile="smoke",
        run_namespace="official",
        status="real",
        artifact_root=tmp_path,
        notebook_id="fixture_notebook",
        run_id=str(uuid.uuid4()),
        source_sha256=HASH_A,
        config_sha256=HASH_B,
        dependency_state_sha256=HASH_C,
    )
    write_json_artifact(
        context,
        "asr.aggregate",
        [{"candidate": "fallback", "execution_mode": "fallback", "metric": 0.1}],
    )
    write_run_manifest(context)
    errors = validate_produced_artifacts(
        {"id": context.notebook_id, "produces": ["asr.aggregate"], "expected_schema_version": 1},
        tmp_path,
        "smoke",
        "official",
        {
            "run_id": context.run_id,
            "status": context.status,
            "source_sha256": context.source_sha256,
            "config_sha256": context.config_sha256,
            "dependency_state_sha256": context.dependency_state_sha256,
        },
    )
    assert any("fallback-only evidence" in error for error in errors)


def test_empty_metric_mapping_is_rejected(tmp_path: Path) -> None:
    payload = tmp_path / "empty-metrics.json"
    payload.write_text('{"metrics": {}}\n', encoding="utf-8")
    errors, record_count = _validate_payload(payload, "asr.aggregate")
    assert record_count == 0
    assert any("field 'metrics' is empty" in error for error in errors)


def test_nested_empty_or_null_metrics_are_scientifically_empty(tmp_path: Path) -> None:
    payloads = (
        {"records": [{"unit_id": "u1", "metrics": {}}]},
        {"metrics": {"wer": None}},
        {"metrics": {"wer": float("nan")}},
    )
    for index, value in enumerate(payloads):
        payload = tmp_path / f"empty-scientific-{index}.json"
        payload.write_text(json.dumps(value), encoding="utf-8")
        errors = _scientifically_empty_errors(payload, "asr.aggregate")
        assert any("no finite metric" in error for error in errors)


def test_payload_level_and_nested_fallback_markers_are_rejected(tmp_path: Path) -> None:
    payloads = (
        {"metrics": {"wer": 0.1}, "execution_mode": "fallback_cpu"},
        {"metrics": {"wer": 0.1}, "execution_mode": "fallback-cpu"},
        {"metrics": {"wer": 0.1}, "provenance": {"fallback_used": True}},
        {"records": [{"metrics": {"wer": 0.1}, "model_loaded": False}]},
    )
    for index, value in enumerate(payloads):
        payload = tmp_path / f"fallback-{index}.json"
        payload.write_text(json.dumps(value), encoding="utf-8")
        errors = _fallback_only_errors(payload, "asr.aggregate")
        assert any("fallback-only evidence" in error for error in errors)


def test_status_sentinels_cannot_be_official_scientific_evidence(tmp_path: Path) -> None:
    invalid_artifacts = (
        ("asr.aggregate", {"metrics": {"wer": "not_run"}}),
        ("asr.aggregate", {"metrics": {"wer": "NaN"}}),
        ("asr.aggregate", {"metrics": {"wer": None, "sample_count": 10}}),
        (
            "asr.aggregate",
            {
                "metrics": {
                    "status": "not eligible",
                    "frame_index": 12,
                    "timestamp_ms": 1000,
                    "rank": 1,
                    "offset": 2,
                    "wer_sample_count": 12,
                    "wer_seed": 42,
                }
            },
        ),
        ("asr.raw_predictions", {"predictions": "not_run"}),
        ("asr.raw_predictions", {"predictions": {"unit_id": "u1", "status": "real"}}),
        (
            "asr.raw_predictions",
            {"predictions": {"status": "not eligible", "unit_count": 5}},
        ),
        ("retrieval.rankings", {"rankings": ["blocked"]}),
    )
    for index, (artifact_id, payload) in enumerate(invalid_artifacts):
        artifact_root = tmp_path / str(index)
        context = RunnerContext(
            profile="smoke",
            run_namespace="official",
            status="real",
            artifact_root=artifact_root,
            notebook_id="fixture_notebook",
            run_id=str(uuid.uuid4()),
            source_sha256=HASH_A,
            config_sha256=HASH_B,
            dependency_state_sha256=HASH_C,
        )
        write_json_artifact(context, artifact_id, payload)
        write_run_manifest(context)
        errors = validate_produced_artifacts(
            {
                "id": context.notebook_id,
                "produces": [artifact_id],
                "expected_schema_version": 1,
            },
            artifact_root,
            "smoke",
            "official",
            {
                "run_id": context.run_id,
                "status": context.status,
                "source_sha256": context.source_sha256,
                "config_sha256": context.config_sha256,
                "dependency_state_sha256": context.dependency_state_sha256,
            },
        )
        assert any("no finite metric" in error for error in errors)


def test_finite_allowlisted_metric_is_scientifically_meaningful(tmp_path: Path) -> None:
    payload = tmp_path / "real-metric.json"
    payload.write_text(json.dumps({"metrics": {"wer": 0.125}}), encoding="utf-8")
    assert _scientifically_empty_errors(payload, "asr.aggregate") == []
    payload.write_text(
        json.dumps({"metrics": {"model_a": {"window_diff": {"mean": 0.2}}}}),
        encoding="utf-8",
    )
    assert _scientifically_empty_errors(payload, "chapter.aggregate") == []
    payload.write_text(
        json.dumps({"metrics": {"model_a": {"corpus_wer": 0.15}}}),
        encoding="utf-8",
    )
    assert _scientifically_empty_errors(payload, "asr.aggregate") == []


def test_runner_rejects_non_real_official_status(tmp_path: Path) -> None:
    args = _runner_args(tmp_path, "00a_environment_preflight", str(uuid.uuid4()))
    args[args.index("real")] = "dry"
    assert environment_preflight.main(args) == 1


def test_dataset_filter_inventories_only_exact_child(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "datasets"
    selected = data_root / "tedlium3"
    other = data_root / "other"
    selected.mkdir(parents=True)
    other.mkdir()
    (selected / "sample.json").write_text("{}", encoding="utf-8")
    (other / "sample.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(probe_dataset_feasibility, "DATA_ROOT", data_root)
    monkeypatch.setenv("MLS_DATASET_FILTER", "tedlium3")
    assert probe_dataset_feasibility._selected_dataset_roots("full") == [selected.resolve()]


def test_dataset_filter_fails_for_missing_empty_and_unselected_full(
    tmp_path: Path, monkeypatch
) -> None:
    data_root = tmp_path / "datasets"
    (data_root / "empty").mkdir(parents=True)
    monkeypatch.setattr(probe_dataset_feasibility, "DATA_ROOT", data_root)
    monkeypatch.setenv("MLS_DATASET_FILTER", "missing")
    with pytest.raises(RuntimeError, match="does not exist"):
        probe_dataset_feasibility._selected_dataset_roots("full")
    monkeypatch.setenv("MLS_DATASET_FILTER", "empty")
    with pytest.raises(RuntimeError, match="is empty"):
        probe_dataset_feasibility._selected_dataset_roots("full")
    monkeypatch.delenv("MLS_DATASET_FILTER")
    with pytest.raises(RuntimeError, match="requires MLS_DATASET_FILTER"):
        probe_dataset_feasibility._selected_dataset_roots("full")


def test_dataset_filter_rejects_symlink_alias(tmp_path: Path, monkeypatch) -> None:
    data_root = tmp_path / "datasets"
    target = data_root / "target"
    alias = data_root / "alias"
    target.mkdir(parents=True)
    (target / "sample.json").write_text("{}", encoding="utf-8")
    try:
        alias.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this Windows host")
    monkeypatch.setattr(probe_dataset_feasibility, "DATA_ROOT", data_root)
    monkeypatch.setenv("MLS_DATASET_FILTER", "alias")
    with pytest.raises(RuntimeError, match="symlink, junction, or alias"):
        probe_dataset_feasibility._selected_dataset_roots("full")
