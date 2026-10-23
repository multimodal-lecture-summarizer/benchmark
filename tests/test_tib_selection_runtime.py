"""Selection runtime on the miniature bundle with injected dependencies: no model, GPU or network."""
import pytest

from selection_fixtures import authorization, dependencies, ledger, mini_bundle, real_allocation
from experiments.scripts import tib_selection_runtime as selection
from experiments.scripts.tib_benchmark_checkpoint import commit, restore


def setup(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    contract, rows = mini_bundle(bundle, monkeypatch)
    output = tmp_path / "selection"
    output.mkdir()
    allocation = real_allocation()
    ledger(output, allocation, bundle)
    return bundle, output, allocation, contract, authorization(bundle)


def run(bundle, output, candidate, allocation, auth, **kw):
    return selection.run(bundle, output / candidate, candidate, wall_hours=kw.pop("wall_hours", 4.0), allocation=allocation,
                         authorization=auth, dependencies=kw.pop("deps", dependencies(bundle)), **kw)


def test_no_historical_import_path_exists():
    assert not hasattr(selection, "import_historical") and "qwen3" not in selection.CANDIDATES


def test_cpu_profile_completes_the_whole_denominator_as_fresh_but_test_only(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    result = run(bundle, output, "lead3", a, auth)
    assert result["status"] == "HOLD" and result["test_only"]
    assert result["summary"]["denominator"] == result["summary"]["successful"] == result["summary"]["fresh"] == 6
    assert result["new_generation_calls"] == result["new_metric_calls"] == result["automatic_retries"] == 0


@pytest.mark.parametrize("mutation", ["none", "wrong_bundle", "not_user", "empty"])
def test_missing_or_wrong_authorization_holds_before_anything_is_touched(tmp_path, monkeypatch, mutation):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    bad = {"none": None, "wrong_bundle": dict(auth, manifest_sha256="0" * 64),
           "not_user": dict(auth, authorized_by="agent"), "empty": {}}[mutation]
    deps = dependencies(bundle)
    deps.environment = lambda _: pytest.fail("Environment/model must not load without authorization")
    result = run(bundle, output, "bart", a, bad, deps=deps)
    assert result["status"] == "HOLD" and "authorization" in result["error"].lower()
    assert not (output / "bart").exists()


def test_unallocated_state_fails_before_bundle_inspection(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    a["state"] = "REQUIRED_NO_START"
    deps = dependencies(bundle)
    deps.validate_bundle = lambda _: pytest.fail("Must not inspect without allocation")
    result = run(bundle, output, "lead3", a, auth, deps=deps)
    assert "REQUIRED_NO_START" in result["error"] and not (output / "lead3").exists()


@pytest.mark.parametrize("status", ["started", "failed"])
def test_resume_never_retries_attempted_records(tmp_path, monkeypatch, status):
    bundle, output, a, contract, auth = setup(tmp_path, monkeypatch)
    run(bundle, output, "lead3", a, auth)
    ident = contract["selection_ids"][0]
    path = output / "lead3" / "records" / (ident.replace(":", "-") + ".json")
    record = restore(path)
    record.update(status=status, quality=None)
    commit(path, record)
    monkeypatch.setattr(selection, "lead3", lambda *x, **k: pytest.fail("attempted record must never retry"))
    result = run(bundle, output, "lead3", a, auth, resume=True)
    assert result["summary"]["denominator"] == 6 and result["summary"]["successful"] == 5
    assert restore(path)["status"] == status


def test_cached_terminal_candidate_skips_environment_and_model(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    run(bundle, output, "lead3", a, auth)
    deps = dependencies(bundle)
    deps.environment = lambda _: pytest.fail("cached candidate must not reload")
    result = run(bundle, output, "lead3", a, auth, resume=True, deps=deps)
    assert result["execution_mode"] == "cached_candidate_resume" and result["cached_reused_records"] == 6


def test_runtime_identity_mismatch_on_resume_fails_closed(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    run(bundle, output, "lead3", a, auth)
    next((output / "lead3" / "records").glob("*.json")).unlink()
    deps = dependencies(bundle)
    deps.environment = lambda _: {"device_name": "different"}
    assert "runtime mismatch" in run(bundle, output, "lead3", a, auth, resume=True, deps=deps)["error"]


def test_technical_failure_keeps_every_id_with_null_quality(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(selection, "lead3", lambda *x, **k: (_ for _ in ()).throw(RuntimeError("technical failure")))
    result = run(bundle, output, "lead3", a, auth)
    assert result["summary"]["denominator"] == result["summary"]["failed_or_interrupted"] == 6
    assert all(r["status"] == "failed" and r["quality"] is None for r in result["records"].values())


def test_neural_backend_failure_spends_forecast_once_and_never_retries(tmp_path, monkeypatch):
    bundle, output, a, contract, auth = setup(tmp_path, monkeypatch)
    environment = {"device_name": "Tesla T4", "packages": {}, "cuda_runtime": "13", "actual_parameter_dtype": "float16",
                   "runtime_dependencies": {}, "actual_attention_backend": "eager", "actual_device_map": {},
                   "asset_sha256": {}, "tokenizer_class": "Fake", "device_memory_bytes": 1, "resolved_generation_config": {}}
    deps = dependencies(bundle)
    deps.environment = lambda _: environment
    deps.load_assets = lambda *x: (object(), object())
    deps.admit_assets = lambda *x: {"test_only": True}

    class Failing:
        last_receipt = None

        def __call__(self, *args):
            self.last_receipt = {"partial_native_telemetry": True}
            raise RuntimeError("synthetic backend failure")
    deps.backend = lambda *x: Failing()
    deps.native_bindings = lambda *x: {}

    class Pipeline:
        def __call__(self, source, *, generate, **kwargs):
            generate.set_node_context({"layer": 0, "node": 0, "source_intervals": [[0, 1]]})
            generate({"input_ids": [1]}, 4, "final")
    monkeypatch.setattr(selection.generation, "summarize_source", Pipeline())
    result = run(bundle, output, "bart", a, auth, deps=deps)
    assert result["summary"]["denominator"] == result["summary"]["failed_or_interrupted"] == 6
    assert result["new_generation_calls"] == 6 and result["node_admission_forecast"]["stage_seconds"]["final"] == 1.0
    assert all(r["quality"] is None and r["events"][0]["status"] == "failed" for r in result["records"].values())
    resumed = run(bundle, output, "bart", a, auth, deps=deps, resume=True)
    assert resumed["new_generation_calls"] == 0 and resumed["summary"]["denominator"] == 6


def test_closed_session_ledger_refuses_to_generate(tmp_path, monkeypatch):
    bundle, output, a, _, auth = setup(tmp_path, monkeypatch)
    ledger(output, a, bundle, session_status="preflight_failed_before_any_model")
    result = run(bundle, output, "lead3", a, auth)
    assert result["status"] == "HOLD" and "not active" in result["error"] and not (output / "lead3" / "records").exists()
