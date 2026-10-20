"""Cache-only recovery contracts; all synthetic runtime evidence remains HOLD."""
import json
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_p4_scorer_replay as replay_tool
from experiments.scripts.tib_scorer_colab_checkpoint import (
    ScoreCheckpoints, atomic_write, digest, file_sha, read_checked, validate_bundle,
)
from test_tib_scorer_colab_runtime import package  # Shared valid21-row package fixture.


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


@pytest.fixture
def recovery(package, tmp_path):
    p = package
    runtime = p.options["runtime_probe"]()
    manifest, _, amendment, rows = validate_bundle(p.root)
    binding = replay_tool._origin_binding(p.root, p.assets, manifest, amendment, runtime)
    store = tmp_path / "original-checkpoints"
    cache = ScoreCheckpoints(store, binding)
    for row in rows:
        cache.save(row, {"metrics": {name: 0.12345678901234567 for name in replay_tool.METRICS},
                         "failures": {}}, 1.25)
    origin = tmp_path / "original-ready.json"
    write(origin, {"status": "PASS", "scorer_ready": True, "testing_dependency_injection": False,
                   "actual_colab_execution": True, "T4_verified": True, "successful_metric_records": 21,
                   "selected_denominator": 21, "failed_or_unscored_records": 0,
                   "fixtures": {"status": "pass"}, "runtime": runtime, "binding": binding})
    expected = tmp_path / "expected.json"
    def reseal():
        write(expected, {"files": replay_tool._store_hashes(store),
                         "origin_ready_sha256": file_sha(origin),
                         "asset_manifest_sha256": binding["asset_manifests_sha256"]})
    reseal()
    options = dict(bundle=p.root, store=store, origin_ready=origin, asset_manifests=p.assets,
                   expected=expected, output=tmp_path / "new-replay", runtime_probe=lambda: runtime)
    return SimpleNamespace(p=p, runtime=runtime, binding=binding, store=store,
                           origin=origin, expected=expected, reseal=reseal, options=options)


def test_exact21_reuse_zero_new_metric_calls_and_read_only(recovery):
    r = recovery
    before = replay_tool._store_hashes(r.store)
    receipt = replay_tool.replay(**r.options)
    assert receipt["status"] == "HOLD"
    assert receipt["orchestration_checks_passed"] is True
    assert receipt["testing_dependency_injection"] is True
    assert receipt["reused_records"] == 21
    assert receipt["new_metric_calls"] == receipt["new_scoring_seconds"] == 0
    assert receipt["original_scoring_seconds"] == 26.25
    assert all(receipt["stage_checks"].values())
    assert receipt["cross_session_survival_verified"] is False
    assert receipt["stage_session_context"] is None
    assert receipt["model_reload_executed"] == receipt["fixtures_executed"] == receipt["scoring_executed"] is False
    assert replay_tool._store_hashes(r.store) == before
    assert not r.p.calls
    out = r.options["output"]
    copied = [json.loads(line) for line in (out / "metrics_replay.jsonl").read_text().splitlines()]
    assert len(copied) == 21 and copied[0]["warnings"] == ["sentence_ending"]
    assert copied[0]["metrics"]["bertscore_f1"] == 0.12345678901234567
    assert copied[0]["result_sha256"] == digest({"metrics": copied[0]["metrics"], "failures": {}})
    assert receipt["artifact_sha256"]["metrics_replay.jsonl"] == file_sha(out / "metrics_replay.jsonl")
    assert receipt["rss_before_bytes"] > 0 and receipt["rss_after_bytes"] > 0
    assert receipt["hash_seconds"] >= 0 and receipt["restore_seconds"] >= 0
    assert json.loads((out / "scorer_replay_receipt.json").read_text()) == receipt


@pytest.mark.parametrize("failure", ["missing", "corrupt", "partial", "extra", "absent-store"])
def test_bad_store_holds_without_fill_or_retry(recovery, failure):
    r = recovery
    path = next(r.store.glob("*.json"))
    if failure == "missing":
        path.unlink()
    elif failure == "corrupt":
        path.write_text("{}")
    elif failure == "partial":
        path.with_suffix(".json.partial").write_text("partial")
    elif failure == "extra":
        (r.store / "extra.json").write_text("{}")
    else:
        r.options["store"] = r.store / "missing-directory"
    before = replay_tool._store_hashes(r.store)
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and result["reused_records"] == 0
    assert result["new_metric_calls"] == 0 and not r.p.calls
    assert replay_tool._store_hashes(r.store) == before
    assert not (r.store / "missing-directory").exists()


@pytest.mark.parametrize("failure", ["runtime-full-hash", "pin", "cpu", "manifest", "origin-hold", "origin-sha"])
def test_binding_changes_hold(recovery, failure):
    r = recovery
    if failure == "runtime-full-hash":
        r.runtime["platform"] = "different-new-host"
    elif failure == "pin":
        r.runtime["packages"]["torch"] = "different"
    elif failure == "cpu":
        r.runtime["cuda_available"] = False
    elif failure == "manifest":
        (r.p.assets / "bert" / "asset_manifest.json").write_text("{}")
    else:
        data = json.loads(r.origin.read_text())
        if failure == "origin-hold":
            data["status"] = "HOLD"
        else:
            data["extra"] = "changed bytes"
        write(r.origin, data)
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and not result["orchestration_checks_passed"]
    assert result["reused_records"] == result["new_metric_calls"] == 0


@pytest.mark.parametrize("failure", ["null", "bool", "missing-metric", "failure", "wrong-input", "cost"])
def test_semantically_invalid_even_with_resealed_file_hash_hold(recovery, failure):
    r = recovery
    path = next(r.store.glob("*.json"))
    payload = read_checked(path)
    if failure == "null":
        payload["result"]["metrics"]["bertscore_f1"] = None
    elif failure == "bool":
        payload["result"]["metrics"]["bertscore_f1"] = True
    elif failure == "missing-metric":
        payload["result"]["metrics"].pop("bertscore_f1")
    elif failure == "failure":
        payload["result"]["failures"] = {"semantic": "failed"}
    elif failure == "wrong-input":
        payload["key"]["input_sha256"] = "0" * 64
    else:
        payload["original_scoring_wall_seconds"] = -1
    atomic_write(path, payload)
    r.reseal()
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and not result["orchestration_checks_passed"]
    assert result["new_metric_calls"] == 0


def test_mocked_observe_runtime_cannot_claim_actual_pass_without_session_context(recovery, monkeypatch):
    r = recovery
    monkeypatch.setattr(replay_tool.resources, "observe_runtime", lambda: r.runtime)
    r.options.pop("runtime_probe")
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and result["reused_records"] == 0
    assert any("session context required" in reason for reason in result["reasons"])
    assert not r.options["output"].exists()


def test_actual_path_without_current_session_context_holds_before_cache_read(recovery, monkeypatch):
    r = recovery
    original_validate = replay_tool.checkpoints.validate_bundle
    def bound_helpers_fixture(bundle):
        manifest, spec, amendment, rows = original_validate(bundle)
        for module in (replay_tool.checkpoints, replay_tool.resources):
            from pathlib import Path
            manifest["files"]["experiments/scripts/" + Path(module.__file__).name] = file_sha(module.__file__)
        return manifest, spec, amendment, rows
    monkeypatch.setattr(replay_tool.checkpoints, "validate_bundle", bound_helpers_fixture)
    monkeypatch.setattr(replay_tool, "_origin_binding", lambda *args: r.binding)
    monkeypatch.setattr(replay_tool.resources, "observe_runtime", lambda: r.runtime)
    r.options.pop("runtime_probe")
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and result["reused_records"] == 0
    assert result["stage_session_context"] is None
    assert any("session context required" in reason for reason in result["reasons"])
    assert not r.options["output"].exists()


def test_invalid_context_cannot_create_output_in_unrelated_store(recovery, tmp_path):
    r = recovery
    other_store = tmp_path / "original-generation-store"
    other_store.mkdir()
    r.options.pop("runtime_probe")
    r.options["session_context"] = tmp_path / "nonexistent-context.json"
    r.options["output"] = other_store / "forbidden-output"
    result = replay_tool.replay(**r.options)
    assert result["status"] == "HOLD" and result["reused_records"] == 0
    assert list(other_store.iterdir()) == []
    assert not r.options["output"].exists()


def test_refuse_output_overwrite_and_input_overlap(recovery):
    r = recovery
    r.options["output"] = r.store / "new-output"
    with pytest.raises(ValueError, match="overlaps"):
        replay_tool.replay(**r.options)
    r.options["output"] = r.p.root
    with pytest.raises(ValueError, match="overlaps"):
        replay_tool.replay(**r.options)
