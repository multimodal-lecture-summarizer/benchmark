"""Pure orchestration fixtures: no model assets, downloads, inference or GPU."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts.tib_scorer_colab_checkpoint import (
    ScoreCheckpoints, atomic_write, digest, file_sha, read_checked, validate_bundle,
)
from experiments.scripts.tib_scorer_colab_runner import run
from experiments.scripts.tib_benchmark_scorer import METRICS


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


@pytest.fixture
def package(tmp_path, monkeypatch):
    root, assets = tmp_path / "bundle", tmp_path / "assets"
    root.mkdir()
    profiles = ["bart-control", "led-ngram0", "led-ngram3", "led-ngram4",
                "qwen-r256", "qwen-r384", "qwen-concise-r256"]
    rows = []
    for record in ("valid:341", "valid:644", "valid:886"):
        for profile in profiles:
            row = {"sample_id": record + "/" + profile, "record_id": record,
                   "profile_id": profile, "candidate_id": profile.split("-")[0].replace("qwen", "qwen3"),
                   "source": "Source " + record, "reference": "Reference " + record,
                   "delivered_summary": "Stored delivered output.", "source_receipt_sha256": "a" * 64,
                   "generation_status": "completed_with_warning", "warnings": ["sentence_ending"]}
            for key, target in (("source", "source_sha256"), ("reference", "reference_sha256"),
                                ("delivered_summary", "delivered_sha256")):
                row[target] = hashlib.sha256(row[key].encode()).hexdigest()
            rows.append(row)
    (root / "development_outputs.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    write(root / "cpu_ready_receipt.json", {"historical_cpu_ready": True})
    write(root / "frozen_scorer_spec.json", {"code_sha256": {}, "bertscore": {"model": "b", "model_revision": "r"},
                                           "source_similarity": {"model": "s", "model_revision": "q"}})
    pins = {"torch": "fixture-only"}
    write(root / "runtime_amendment.json", {"runtime_pins": pins, "required_record_ids": ["valid:341", "valid:644", "valid:886"],
          "expected_profile_ids": profiles, "expected_output_count": 21,
          "frozen_spec_sha256": file_sha(root / "frozen_scorer_spec.json"),
          "cpu_ready_receipt_sha256": file_sha(root / "cpu_ready_receipt.json")})
    for name in ("bert", "sentence"):
        write(assets / name / "asset_manifest.json", {"fixture_only": True})
    def seal():
        write(root / "package_manifest.json", {"schema_version": 1, "files": {
            path.relative_to(root).as_posix(): file_sha(path) for path in root.rglob("*")
            if path.is_file() and path.name != "package_manifest.json"}})
    seal()
    import sys
    monkeypatch.setitem(sys.modules, "experiments.scripts.tib_scorer_colab_backend", SimpleNamespace(
        RuntimeSemanticScorer=None, runtime_fixtures=None, runtime_pins=lambda: pins))
    calls = []
    class Sampler:
        def start(self): return self
        def finish(self): return {"fixture_only": True, **{key: 1 for key in (
            "wall_seconds", "cpu_seconds", "sampled_peak_process_rss_bytes",
            "cuda_peak_allocated_bytes", "cuda_peak_reserved_bytes", "host_memory_total_bytes")}}
    def score(*args, **kwargs):
        calls.append(args)
        return {"metrics": {key: 0.5 for key in METRICS}, "failures": {}}
    options = {"backend_factory": lambda *args: SimpleNamespace(metadata={"fixture_only": True}, _load=lambda: None),
               "fixture_runner": lambda _: {"status": "pass", "fixture_only": True},
               "runtime_probe": lambda: {"google_colab_imported": True, "cuda_available": True,
                    "T4_device_observed": True, "device_memory_bytes": 16 * 1024**3,
                    "device_name": "Tesla T4", "packages": pins, "fixture_only": True},
               "asset_validator": lambda path, **_: path,
               "sampler_factory": Sampler, "score_function": score}
    return SimpleNamespace(root=root, assets=assets, output=tmp_path / "results", rows=rows,
                           options=options, calls=calls, seal=seal)


def test_all_outputs_warning_retained_and_cached_replay_zero_new_calls(package):
    p = package
    result = run(p.root, p.output, p.assets, **p.options)
    assert result["status"] == "HOLD" and result["orchestration_checks_passed"] and len(p.calls) == 21
    assert result["T4_verified"] is False and result["actual_colab_execution"] is False
    for name, expected in result["artifact_sha256"].items():
        assert file_sha(p.output / "runs" / result["run_id"] / name) == expected
    assert result["cross_session_survival_verified"] is False
    rows = [json.loads(line) for line in (p.output / "metrics.jsonl").read_text().splitlines()]
    assert len(rows) == 21 and all(row["warnings"] == ["sentence_ending"] for row in rows)
    result = run(p.root, p.output, p.assets, resume=True, **p.options)
    assert result["orchestration_checks_passed"] and len(p.calls) == 21
    costs = json.loads((p.output / "cost_evidence.json").read_text())
    assert costs["new_metric_calls"] == costs["scoring_seconds"] == 0
    assert costs["reused_records"] == 21
    assert len(list((p.output / "runs").iterdir())) == 2
    assert all(item["record_count"] == 0 for item in costs["latency_by_profile"].values())


@pytest.mark.parametrize("failure", ["corrupt", "missing", "partial"])
def test_resume_integrity_hold_without_new_scoring(package, failure):
    p = package
    run(p.root, p.output, p.assets, **p.options)
    path = next((p.output / "checkpoints").glob("*.json"))
    if failure == "corrupt": path.write_text("{}")
    elif failure == "missing": path.unlink()
    else: path.with_suffix(".json.partial").write_text("partial")
    result = run(p.root, p.output, p.assets, resume=True, **p.options)
    assert result["status"] == "HOLD" and len(p.calls) == 21
    assert (p.output / "PASS_HOLD_report.json").is_file()


def test_nonfinite_null_failure_keeps_denominator(package):
    p = package
    p.options["score_function"] = lambda *a, **k: {"metrics": {key: float("nan") for key in METRICS}, "failures": {}}
    result = run(p.root, p.output, p.assets, **p.options)
    assert result["status"] == "HOLD" and result["selected_denominator"] == 21
    rows = [json.loads(line) for line in (p.output / "metrics.jsonl").read_text().splitlines()]
    assert all(all(value is None for value in row["metrics"].values()) for row in rows)


def test_noncolab_runtime_hold_and_reports_without_backend_call(package):
    p = package
    p.options["runtime_probe"] = lambda: {"google_colab_imported": False, "packages": {}}
    result = run(p.root, p.output, p.assets, **p.options)
    assert result["status"] == "HOLD" and not p.calls
    assert all((p.output / name).is_file() for name in ("scorer_ready_receipt.json", "metrics.jsonl", "cost_evidence.json", "PASS_HOLD_report.json"))


def test_manifest_modified_and_missing_file_rejected(package):
    p = package
    (p.root / "cpu_ready_receipt.json").write_text("{}")
    with pytest.raises(ValueError, match="hash"): validate_bundle(p.root)
    (p.root / "cpu_ready_receipt.json").unlink()
    with pytest.raises(ValueError, match="file set"): validate_bundle(p.root)


def test_input_hash_cohort_and_profile_matrix_rejected(package):
    p = package
    p.rows[0]["reference"] = "Changed reference"
    (p.root / "development_outputs.jsonl").write_text("\n".join(json.dumps(row) for row in p.rows))
    p.seal()
    with pytest.raises(ValueError, match="hash mismatch"): validate_bundle(p.root)


def test_checkpoint_binding_and_safe_nonfinite_json(tmp_path):
    row = {"sample_id": "sample"}
    store = ScoreCheckpoints(tmp_path / "nodes", {"code": "v1"})
    store.save(row, {"metrics": {"x": 0.1}}, 2.0)
    assert store.load(row)["original_scoring_wall_seconds"] == 2
    changed = ScoreCheckpoints(tmp_path / "nodes", {"code": "v2"}, resume=True)
    with pytest.raises(ValueError, match="missing"): changed.load(row)
    with pytest.raises(ValueError): atomic_write(tmp_path / "bad.json", {"x": float("nan")})


def test_no_implicit_rerun_existing_store_and_fixture_hold(package):
    p = package
    run(p.root, p.output, p.assets, **p.options)
    assert run(p.root, p.output, p.assets, **p.options)["status"] == "HOLD"
    assert len(p.calls) == 21


def test_fixture_hold_does_not_score_and_keeps_all_outputs(package):
    p = package
    p.options["fixture_runner"] = lambda _: {"status": "hold", "reason": "fixture failure"}
    result = run(p.root, p.output, p.assets, **p.options)
    assert not result["orchestration_checks_passed"] and not p.calls
    assert result["selected_denominator"] == 21
    rows = [json.loads(line) for line in (p.output / "metrics.jsonl").read_text().splitlines()]
    assert len(rows) == 21 and all(row["scoring_status"] == "not_attempted" for row in rows)


def test_missing_resource_evidence_cannot_pass_orchestration(package):
    p = package
    p.options["sampler_factory"] = lambda: SimpleNamespace(start=lambda: SimpleNamespace(finish=lambda: {}))
    result = run(p.root, p.output, p.assets, **p.options)
    assert not result["orchestration_checks_passed"]
    assert "missing_resource_evidence" in result["reasons"]


def test_support_pin_mismatch_holds_before_any_scoring(package):
    p = package
    path = p.root / "runtime_amendment.json"
    amendment = json.loads(path.read_text())
    amendment["support_package_pins"] = {"tokenizers": "missing"}
    write(path, amendment)
    p.seal()
    result = run(p.root, p.output, p.assets, **p.options)
    assert not p.calls and not result["orchestration_checks_passed"]
    assert any("support package lock" in reason for reason in result["reasons"])


def test_partial_metric_failure_preserves_independent_values(package):
    p = package
    def score(*args, **kwargs):
        return {"metrics": {"rouge1_f1": 0.5, "rouge2_f1": 0.4, "rougeL_f1": 0.5},
                "failures": {"semantic": "backend error"}}
    p.options["score_function"] = score
    result = run(p.root, p.output, p.assets, **p.options)
    assert not result["orchestration_checks_passed"]
    rows = [json.loads(line) for line in (p.output / "metrics.jsonl").read_text().splitlines()]
    assert all(row["metrics"]["rouge1_f1"] == 0.5 and row["metrics"]["bertscore_f1"] is None for row in rows)


def test_changed_profile_matrix_even_resealed_is_rejected(package):
    p = package
    p.rows[1]["profile_id"] = p.rows[2]["profile_id"]
    (p.root / "development_outputs.jsonl").write_text("\n".join(json.dumps(row) for row in p.rows))
    p.seal()
    with pytest.raises(ValueError, match="duplicate stored-output"): validate_bundle(p.root)


def test_effective_package_versions_respect_venv_precedence(monkeypatch):
    from experiments.scripts import tib_scorer_colab_resources as resources
    distributions = [SimpleNamespace(metadata={"Name": "Torch"}, version="2.11.0+cu130"),
                     SimpleNamespace(metadata={"Name": "torch"}, version="2.6.0+cu124"),
                     SimpleNamespace(metadata={"Name": "sentence_transformers"}, version="5.7.0")]
    monkeypatch.setattr(resources.importlib.metadata, "distributions", lambda: distributions)
    effective = {"torch": "2.11.0+cu130", "sentence-transformers": "5.7.0"}
    monkeypatch.setattr(resources.importlib.metadata, "version", effective.__getitem__)
    assert resources.effective_package_versions() == effective
