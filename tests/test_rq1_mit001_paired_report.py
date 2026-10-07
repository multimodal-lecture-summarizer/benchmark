"""Contract checks for the read-only paired RQ1 diagnostic report."""

from __future__ import annotations

import json
import hashlib
import uuid
from pathlib import Path

import pytest

from experiments.scripts.rq1_mit001_paired_report import build_report
from experiments.scripts.benchmark_artifacts import RunnerContext, write_json_artifact, write_run_manifest


def _write(root: Path, relative: str, value: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(root: Path) -> None:
    _write(root, "pilot_summary.json", {
        "diagnostic_only": True,
        "dataset_id": "avlectures_mit001_local_diagnostic",
        "unit_count": 35,
        "exit_codes": {"04a": 0, "04b": 0},
        "limitation": "Single course; labels were seen in an earlier pilot.",
    })
    ids = [f"lec{i:02d}" for i in range(35)]
    benchmark = [
        {"unit_id": unit, "candidate": name, "metrics": {"collar_f1_3s": score}}
        for unit in ids
        for name, score in (
            ("fixed_window_300s", 0.1),
            ("lexical_texttiling", 0.2),
            ("multimodal_scene_aligned", 0.3),
        )
    ]
    ablation = [
        {"unit_id": unit, "ablation_variant": name, "metrics": {"collar_f1_3s": score}}
        for unit in ids
        for name, score in (
            ("transcript", 0.2),
            ("transcript+ocr", 0.4),
            ("transcript+scene", 0.3),
        )
    ]
    _write(root, "diagnostic/full/payloads/chapter.per_unit_metrics.json", {"records": benchmark})
    _write(root, "diagnostic/full/payloads/chapter.ablation_metrics.json", {"records": ablation})


def test_paired_report_uses_matched_per_lecture_scores(tmp_path: Path) -> None:
    _fixture(tmp_path)
    report = build_report(tmp_path)
    assert "35 matched lectures" in report
    assert "| `transcript+ocr` | 0.4000 | +0.2000 | 35 / 0 / 0 |" in report
    assert "| `lexical_texttiling` | 0.2000 | +0.0000 | 0 / 35 / 0 |" in report
    assert "not an official or held-out result" in report


def _verified_fixture(root: Path) -> None:
    """Build receipts and run manifests for all source-feature report inputs."""
    _fixture(root)
    summary_path = root / "pilot_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.update(video_features_requested=True, code_sha256="a" * 64)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    ids = [f"lec{i:02d}" for i in range(35)]
    dataset = summary["dataset_id"]
    base = root / "diagnostic/full/payloads"

    def context(notebook: str, mode: str | None = "selection") -> RunnerContext:
        return RunnerContext(
            profile="full", run_namespace="diagnostic", status="partial", artifact_root=root,
            notebook_id=notebook, run_id=str(uuid.uuid4()), source_sha256="a" * 64,
            config_sha256="b" * 64, dependency_state_sha256="c" * 64,
            evaluation_mode=mode,
        )

    frozen = context("00c_dataset_eda_and_freeze", None)
    write_json_artifact(frozen, "dataset.frozen_manifest", [{
        "unit_ids": ids,
        "unit_records": [{"unit_id": uid, "sha256": f"{i:064x}"} for i, uid in enumerate(ids)],
    }])
    write_run_manifest(frozen)
    first = context("04a_chaptering_benchmark")
    write_json_artifact(first, "chapter.input_features", [
        {"unit_id": uid, "source_sha256": f"{i:064x}", "dataset_id": dataset,
         "split": "validation", "evaluation_mode": "selection", "cache_key": f"cache-{i}"}
        for i, uid in enumerate(ids)
    ])
    benchmark = json.loads((base / "chapter.per_unit_metrics.json").read_text(encoding="utf-8"))["records"]
    write_json_artifact(first, "chapter.per_unit_metrics", benchmark)
    write_json_artifact(first, "chapter.raw_predictions", [
        {"unit_id": row["unit_id"], "candidate": row["candidate"],
         "dataset_id": dataset, "split": "validation",
         "feature_cache_key": f"cache-{ids.index(row['unit_id'])}"}
        for row in benchmark
    ])
    write_run_manifest(first)
    second = context("04b_chaptering_modality_ablation")
    ablation = json.loads((base / "chapter.ablation_metrics.json").read_text(encoding="utf-8"))["records"]
    ablation.extend(
        {"unit_id": uid, "ablation_variant": name, "metrics": {"collar_f1_3s": score}}
        for uid in ids
        for name, score in (("transcript+visual", 0.25),
                            ("transcript+acoustic", 0.3), ("all_modalities", 0.35))
    )
    write_json_artifact(second, "chapter.ablation_metrics", ablation)
    write_json_artifact(second, "chapter.ablation_predictions", [
        {"unit_id": row["unit_id"], "ablation_variant": row["ablation_variant"],
         "dataset_id": dataset, "split": "validation",
         "feature_cache_key": f"cache-{ids.index(row['unit_id'])}"}
        for row in ablation
    ])
    write_json_artifact(second, "chapter.ablation_status", [
        {"ablation": name, "status": "run"}
        for name in ("transcript", "transcript+ocr", "transcript+scene",
                     "transcript+visual", "transcript+acoustic", "all_modalities")
    ])
    write_run_manifest(second)


def test_paired_report_requires_new_variants_for_source_feature_run(tmp_path: Path) -> None:
    _verified_fixture(tmp_path)
    report = build_report(tmp_path)
    assert "| `all_modalities` | 0.3500 | +0.1500 | 35 / 0 / 0 |" in report
    assert "fixed heuristic fusion" in report

    # A metric edit without its receipt must fail before reaching paired scores.
    path = tmp_path / "diagnostic/full/payloads/chapter.ablation_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["metrics"]["collar_f1_3s"] = 0.99
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        build_report(tmp_path)


def test_paired_report_rejects_mismatched_feature_key_even_with_valid_receipt(tmp_path: Path) -> None:
    _verified_fixture(tmp_path)
    path = tmp_path / "diagnostic/full/payloads/chapter.ablation_predictions.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["feature_cache_key"] = "another-run"
    path.write_text(json.dumps(payload), encoding="utf-8")
    receipt_path = tmp_path / "diagnostic/full/chapter.ablation_predictions.receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="prediction feature key"):
        build_report(tmp_path)


def test_paired_report_rejects_missing_new_variant(tmp_path: Path) -> None:
    _fixture(tmp_path)
    summary_path = tmp_path / "pilot_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["video_features_requested"] = True
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(ValueError, match="code_sha256"):
        build_report(tmp_path)


def test_paired_report_rejects_incomplete_cohort(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "diagnostic/full/payloads/chapter.ablation_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"] = [row for row in payload["records"] if not (row["unit_id"] == "lec00" and row["ablation_variant"] == "transcript+ocr")]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="same lecture IDs"):
        build_report(tmp_path)


def test_paired_report_rejects_non_diagnostic_or_failed_run(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "pilot_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["diagnostic_only"] = False
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Only diagnostic"):
        build_report(tmp_path)
    payload["diagnostic_only"] = True
    payload["exit_codes"]["04b"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="completed 35-lecture"):
        build_report(tmp_path)


def test_paired_report_rejects_duplicate_or_invalid_score(tmp_path: Path) -> None:
    _fixture(tmp_path)
    path = tmp_path / "diagnostic/full/payloads/chapter.per_unit_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"].append(payload["records"][0])
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate score"):
        build_report(tmp_path)
    payload["records"].pop()
    payload["records"][0]["metrics"]["collar_f1_3s"] = float("nan")
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid collar_f1_3s"):
        build_report(tmp_path)
