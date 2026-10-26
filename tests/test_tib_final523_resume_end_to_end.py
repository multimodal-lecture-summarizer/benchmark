"""Full-size synthetic final523 scoring: interrupt, resume with --resume-partial semantics, compare with an uninterrupted run.

No GPU, no model, no real source/reference/output: every ID is `fixture:*` and lives under tmp_path.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_final523_scorer_validation as final
from experiments.scripts import tib_pilot40_scorer_runner as runner
from final523_scoring_fixtures import build_final_bundle, make_final_world
from selection_scoring_fixtures import install_fakes, make_assets, make_ledger


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_final_world(tmp_path_factory.mktemp("e2e-world"))


@pytest.fixture(scope="module")
def built(world, tmp_path_factory):
    receipt, local, _ = build_final_bundle(world, tmp_path_factory.mktemp("e2e-built"))
    return SimpleNamespace(receipt=receipt, bundle=local / "bundle")


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def run(env, output, **kwargs):
    arguments = dict(validator=final.validate_final_scoring_bundle, order=final.interleaved_order, stage=final.FINAL_STAGE,
                     ledger=env.ledger, wall_hours=10.0, **env.fakes.options)
    arguments.update(kwargs)
    return runner.run(env.bundle, output, env.assets, **arguments)


def make_env(world, built, tmp_path, monkeypatch):
    fakes = install_fakes(monkeypatch, runner, world)
    ledger = make_ledger(world, tmp_path / "ledger.json", third_open=True)
    return SimpleNamespace(bundle=built.bundle, assets=make_assets(tmp_path / "assets"), ledger=ledger, fakes=fakes)


def comparable(output):
    rows = {r["sample_id"]: (r["scoring_status"], r["metrics"], r["failures"]) for r in lines(Path(output) / "metrics.jsonl")}
    views = {r["sample_id"]: r["views"] for r in lines(Path(output) / "view_metrics.jsonl")}
    return rows, views


def test_interrupted_final523_scoring_resumes_to_the_same_complete_result(world, built, tmp_path, monkeypatch):
    env = make_env(world, built, tmp_path, monkeypatch)
    expected = built.receipt["scoreable_rows"]
    original, state = env.fakes.options["score_function"], {"n": 0}

    def interrupting(*args, **kwargs):
        result = original(*args, **kwargs)
        state["n"] += 1
        if state["n"] == 700:
            env.fakes.clock.offset += 400_000.0   # the session ends mid-run
        return result
    env.fakes.options["score_function"] = interrupting
    first = run(env, tmp_path / "scoring")
    env.fakes.options["score_function"] = original
    assert "session_deadline" in first["reasons"] and first["views_status"] == "NOT_STARTED"
    assert len(list((tmp_path / "scoring/checkpoints").glob("*.json"))) == 700

    calls_before = len(env.fakes.calls)
    second = run(env, tmp_path / "scoring", resume_partial=True)
    assert second["orchestration_checks_passed"] and second["partial_resume_used"] is True
    assert (second["reused_rows"], second["fresh_rows"]) == (700, expected - 700)
    assert len(env.fakes.calls) - calls_before == (expected - 700) + runner.CANARY_ROWS
    assert second["canary"]["passed"] and len(second["canary"]["sample_ids"]) == runner.CANARY_ROWS
    assert second["views_status"] == "COMPLETE" and first["run_id"] in second["run_ids"]

    baseline = run(env, tmp_path / "baseline")
    assert comparable(tmp_path / "scoring") == comparable(tmp_path / "baseline")
    assert baseline["successful_metric_records"] == second["successful_metric_records"] == expected
    rows = lines(tmp_path / "scoring/metrics.jsonl")
    assert len(rows) == 2092 and sum(r["scoring_status"] == "not_scoreable_generation_failed" for r in rows) == built.receipt["failed_rows"]
