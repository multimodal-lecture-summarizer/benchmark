"""Offline runner contracts for partial A0-A5 coverage and split isolation."""
import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from benchmarks.scripts import run_asr_model_benchmark as runner
from experiments.evaluation.asr_selection_scoring import selection_metadata
from experiments.scripts.benchmark_artifacts import (
    RunnerContext, write_json_artifact, write_run_manifest,
)
from experiments.evaluation.asr_candidate_adapters import registered_asr_candidates


def _context(root: Path, *, mode=None, profile="full"):
    h = lambda value: hashlib.sha256(value.encode()).hexdigest()
    return RunnerContext(
        profile=profile, run_namespace="diagnostic", status="real", artifact_root=root,
        notebook_id="01a_asr_model_benchmark", run_id=str(uuid.uuid4()),
        source_sha256=h("source"), config_sha256=h("config"),
        dependency_state_sha256=h("dependencies"), evaluation_mode=mode,
    )


def _blocked_preflight(monkeypatch):
    from experiments.scripts import asr_benchmark_preflight
    candidates = registered_asr_candidates(
        Path(runner.__file__).resolve().parents[2] / "experiments/registry/candidates.yaml")
    monkeypatch.setattr(asr_benchmark_preflight, "inspect_environment", lambda: {
        "all_candidates_ready": False,
        "candidates": [{"candidate": item["id"], "ready": False,
                         "missing_dependencies": [], "model": {"cached": False}}
                       for item in candidates],
    })
    monkeypatch.setattr(runner.CandidateAdapter, "load", lambda self: (_ for _ in ()).throw(
        AssertionError("blocked preflight must not load or download a model")))


def _manifest_context(context, val_units, test_units):
    context = replace(context, notebook_id="00c_dataset_eda_and_freeze")
    records = [*val_units, *test_units]
    manifest = {"dataset_id": "tedlium3", "unit_records": records,
                "unit_ids": [row["unit_id"] for row in records],
                "eligible_split_counts": {"validation": len(val_units), "final_test": len(test_units)}}
    write_json_artifact(context, "dataset.frozen_manifest", [manifest])
    write_run_manifest(context)


def test_complete_validation_shortlist_selects_rank_one() -> None:
    scores = {f"candidate-{i}": {"wer": float(i)} for i in range(6)}
    shortlist = runner._rank_validation_candidates(scores, {"cohort": "validation"})

    assert len(shortlist) == 6
    assert [row["rank"] for row in shortlist] == [1, 2, 3, 4, 5, 6]
    assert [row["candidate"] for row in shortlist if row["selected"]] == ["candidate-0"]
    assert all(row["cohort"] == "validation" for row in shortlist)


def test_completed_runner_validation_publishes_one_selected_candidate(tmp_path, monkeypatch):
    context = _context(tmp_path, mode="selection")
    unit = {"unit_id": "validation:one", "dataset_id": "fixture", "split": "validation",
            "reference_text": "hello world", "talk_id": "talk"}
    frozen_context = replace(context, notebook_id="00c_dataset_eda_and_freeze",
                             evaluation_mode=None)
    write_json_artifact(frozen_context, "dataset.frozen_manifest", [{
        "dataset_id": "fixture", "unit_records": [unit], "unit_ids": [unit["unit_id"]],
        "eligible_split_counts": {"validation": 1, "final_test": 0}}])
    write_run_manifest(frozen_context)

    class FakeAdapter:
        def __init__(self, candidate):
            self.model_size = candidate["id"]
            self.device = "cpu"
            self.load_seconds = 0.0
            self.model_revision = "fixture"
            self.dependency_versions = {}

        def load(self):
            pass

        def transcribe(self, audio):
            return SimpleNamespace(text="hello world", inference_seconds=0.1,
                                   preprocessing_seconds=0.0, alignment_seconds=0.0)

        def close(self):
            pass

    monkeypatch.setattr(runner, "parse_context", lambda *args: context)
    monkeypatch.setattr(runner, "load_eligible_units", lambda *args, **kwargs: [unit])
    monkeypatch.setattr(runner, "ADAPTER_FACTORY", FakeAdapter)
    monkeypatch.setattr(runner, "_audio", lambda *args, **kwargs: (
        np.zeros(16000, dtype=np.float32), 1.0, "fixture-audio-hash"))
    monkeypatch.setattr(runner, "_hardware_identity", lambda: {})

    assert runner.main([]) == 0
    shortlist = json.loads((context.namespace_root / "payloads/asr.shortlist.json").read_text())["records"]
    receipt = json.loads((context.namespace_root / "selection_receipt.json").read_text())
    assert len(shortlist) == 6
    assert sum(row["selected"] is True for row in shortlist) == 1
    assert next(row for row in shortlist if row["selected"])["rank"] == 1
    assert receipt["status"] == "complete"


def test_incomplete_validation_emits_all_six_blocked_rows_and_no_selection(tmp_path, monkeypatch):
    context = _context(tmp_path)
    units = [{"unit_id": f"validation:{i}", "dataset_id": "tedlium3",
              "split": "validation", "reference_text": f"spoken words {i}", "talk_id": "talk"}
             for i in range(507)]
    test_units = [{"unit_id": f"final_test:{i}", "dataset_id": "tedlium3",
                   "split": "final_test", "reference_text": f"held words {i}"}
                  for i in range(1155)]
    _manifest_context(context, units, test_units)
    monkeypatch.setattr(runner, "parse_context", lambda *args: context)
    monkeypatch.setattr(runner, "load_eligible_units", lambda *args, **kwargs: units)
    _blocked_preflight(monkeypatch)

    assert runner.main([]) == 2
    payload_root = context.namespace_root / "payloads"
    predictions = json.loads((payload_root / "asr.raw_predictions.json").read_text())["records"]
    shortlist = json.loads((payload_root / "asr.shortlist.json").read_text())["records"]
    assert len(predictions) == 6 * 507
    assert all(row["status"] == "blocked" for row in predictions)
    assert shortlist == [{"candidate": "no_selection", "selected": False,
                          "status": "partial", "reason": "incomplete_validation_matrix",
                          **selection_metadata(units)}]
    assert json.loads((context.namespace_root / "runs/01a_asr_model_benchmark.run.json").read_text())["status"] == "partial"


def test_final_test_uses_receipt_and_separate_root_without_mutating_validation(tmp_path, monkeypatch):
    validation_root = tmp_path / "validation"
    test_root = tmp_path / "native_test"
    validation_context = _context(validation_root, mode="selection")
    candidates = registered_asr_candidates(
        Path(runner.__file__).resolve().parents[2] / "experiments/registry/candidates.yaml")
    val_units = [{"unit_id": f"validation:{i}", "dataset_id": "tedlium3",
                  "split": "validation", "reference_text": f"words {i}"}
                 for i in range(507)]
    test_units = [{"unit_id": f"final_test:{i}", "dataset_id": "tedlium3",
                   "split": "final_test", "reference_text": f"held words {i}"}
                  for i in range(1155)]
    _manifest_context(validation_context, val_units, test_units)
    selection = selection_metadata(val_units)
    shortlist = [{"candidate": candidate["id"], "selected": i == 0, "rank": i + 1,
                  **selection} for i, candidate in enumerate(candidates)]
    write_json_artifact(validation_context, "asr.shortlist", shortlist)
    write_run_manifest(validation_context)
    shortlist_path = validation_context.namespace_root / "payloads/asr.shortlist.json"
    receipt = {"status": "complete", "candidate_count": 6, "unit_count": 507,
               "candidate_ids": [candidate["id"] for candidate in candidates],
               "selection_unit_ids_sha256": selection["selection_unit_ids_sha256"],
               "checkpoint_identity": "fixture", "source_sha256": validation_context.source_sha256,
               "config_sha256": validation_context.config_sha256,
               "dependency_state_sha256": validation_context.dependency_state_sha256,
               "dataset_manifest_sha256": hashlib.sha256(
                   (validation_context.namespace_root / "payloads/dataset.frozen_manifest.json").read_bytes()
               ).hexdigest(),
               "test_unit_ids_sha256": runner._unit_ids_sha256(test_units),
               "run_id": validation_context.run_id,
               "shortlist_sha256": hashlib.sha256(shortlist_path.read_bytes()).hexdigest()}
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    selection_receipt = validation_context.namespace_root / "selection_receipt.json"
    selection_receipt.write_text(json.dumps(receipt), encoding="utf-8")
    prior_shortlist = shortlist_path.read_bytes()

    test_context = _context(test_root, mode="final_test")
    _manifest_context(test_context, val_units, test_units)
    monkeypatch.setattr(runner, "parse_context", lambda *args: test_context)
    monkeypatch.setattr(runner, "load_eligible_units", lambda *args, **kwargs: test_units)
    monkeypatch.setenv("MLS_ASR_SELECTION_RECEIPT", str(selection_receipt))
    _blocked_preflight(monkeypatch)

    assert runner.main([]) == 2
    test_shortlist = json.loads((test_context.namespace_root / "payloads/asr.shortlist.json").read_text())["records"]
    assert test_shortlist[0]["status"] == "final_test_cannot_select"
    assert test_shortlist[0]["selected"] is False
    assert prior_shortlist == shortlist_path.read_bytes()
    assert (test_context.namespace_root / "runs/01a_asr_model_benchmark.run.json").is_file()
    parent_index = json.loads((test_context.namespace_root / "parent_index.json").read_text())
    assert parent_index["validation"]["artifact_root"] == str(validation_root.resolve())
    assert parent_index["native_test"]["artifact_root"] == str(test_root.resolve())
    assert parent_index["validation"]["selection_receipt_sha256"] == receipt["receipt_sha256"]


def test_smoke_is_a_one_unit_preflight_and_never_creates_selection(tmp_path, monkeypatch):
    context = _context(tmp_path, profile="smoke")
    units = [{"unit_id": f"validation:{i}", "dataset_id": "tedlium3",
              "split": "validation", "reference_text": f"spoken words {i}"}
             for i in range(507)]
    test_units = [{"unit_id": f"final_test:{i}", "dataset_id": "tedlium3",
                   "split": "final_test", "reference_text": f"held words {i}"}
                  for i in range(1155)]
    _manifest_context(context, units, test_units)
    monkeypatch.setattr(runner, "parse_context", lambda *args: context)
    monkeypatch.setattr(runner, "load_eligible_units", lambda *args, **kwargs: units)
    _blocked_preflight(monkeypatch)

    assert runner.main([]) == 2
    payload_root = context.namespace_root / "payloads"
    predictions = json.loads((payload_root / "asr.raw_predictions.json").read_text())["records"]
    shortlist = json.loads((payload_root / "asr.shortlist.json").read_text())["records"]
    assert len(predictions) == 6
    assert shortlist[0]["status"] == "smoke_cannot_select"
    assert not (context.namespace_root / "selection_receipt.json").exists()


def test_completed_validation_receipt_is_never_deleted_or_replaced(tmp_path, monkeypatch):
    context = _context(tmp_path)
    units = [{"unit_id": f"validation:{i}", "dataset_id": "tedlium3",
              "split": "validation", "reference_text": f"spoken words {i}"}
             for i in range(507)]
    test_units = [{"unit_id": f"final_test:{i}", "dataset_id": "tedlium3",
                   "split": "final_test", "reference_text": f"held words {i}"}
                  for i in range(1155)]
    _manifest_context(context, units, test_units)
    receipt_path = context.artifact_root / "diagnostic/full/selection_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    original = b'{"status":"complete","receipt_sha256":"frozen"}\n'
    receipt_path.write_bytes(original)
    monkeypatch.setattr(runner, "parse_context", lambda *args: context)
    monkeypatch.setattr(runner, "load_eligible_units", lambda *args, **kwargs: units)

    assert runner.main([]) == 1
    assert receipt_path.read_bytes() == original
