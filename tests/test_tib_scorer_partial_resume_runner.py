"""Runner scenarios for scorer partial resume on the small Pilot40 fake harness (8 rows, 7 scoreable)."""
import json
from pathlib import Path

import pytest

from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts.tib_scorer_colab_checkpoint import digest
from test_tib_pilot40_scorer_runner import package, read_lines  # noqa: F401  (fixture + helper)

STAGE = {**runner.PILOT40_STAGE, "partial_resume_allowed": True, "portable_binding": True}


def interrupting(p, after):
    """Make the fake scorer push the clock past the session deadline once `after` rows were scored."""
    original, state = p.options["score_function"], {"n": 0}

    def wrapped(*args, **kwargs):
        result = original(*args, **kwargs)
        state["n"] += 1
        if state["n"] == after:
            p.clock.offset += 10_000
        return result
    p.options["score_function"] = wrapped
    return original


def metrics_by_sample(output):
    return {r["sample_id"]: (r["scoring_status"], r["metrics"], r["failures"]) for r in read_lines(Path(output) / "metrics.jsonl")}


def views_by_sample(output):
    return {r["sample_id"]: r["views"] for r in read_lines(Path(output) / "view_metrics.jsonl")}


def baseline(p):
    clean = Path(str(p.output) + "-baseline")
    runner.run(p.root, clean, p.assets, stage=STAGE, **p.options)
    return clean


def interrupted_run(p, after=3):
    original = interrupting(p, after)
    first = runner.run(p.root, p.output, p.assets, stage=STAGE, **p.options)
    p.options["score_function"] = original
    return first


def hold_reasons(result):
    return " | ".join(result["reasons"])


def test_interrupt_in_pass_one_then_resume_partial_equals_an_uninterrupted_run(package):
    p = package
    first = interrupted_run(p)
    assert "session_deadline" in first["reasons"] and len(list((p.output / "checkpoints").glob("*.json"))) == 3
    calls_before = len(p.calls)
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert second["orchestration_checks_passed"] and second["partial_resume_used"] is True
    assert second["reused_rows"] == 3 and second["fresh_rows"] == 4
    assert len(p.calls) - calls_before == 4 + 3   # 4 missing rows + 3 canary re-scores
    assert second["canary"]["passed"] is True and len(second["canary"]["sample_ids"]) == 3
    assert first["run_id"] in second["run_ids"] and second["run_id"] in second["run_ids"] and second["quarantined"] == []
    clean = baseline(p)
    assert metrics_by_sample(p.output) == metrics_by_sample(clean)
    assert views_by_sample(p.output) == views_by_sample(clean)
    assert second["views_status"] == "COMPLETE" and len(read_lines(p.output / "view_metrics.jsonl")) == 7


def test_interrupt_in_the_views_pass_then_resume_partial_finishes_the_views(package):
    p = package
    p.clock.jump = 10_000.0
    first = runner.run(p.root, p.output, p.assets, stage=STAGE, **p.options)
    assert first["views_status"] == "PARTIAL_DEADLINE"
    p.clock.jump = 0.0
    done_views = len(list((p.output / "view_checkpoints").glob("*.json")))
    calls_before, view_calls_before = len(p.calls), len(p.view_calls)
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert second["orchestration_checks_passed"] and second["views_status"] == "COMPLETE"
    assert second["fresh_rows"] == 0 and second["reused_rows"] == 7
    assert len(p.calls) - calls_before == 6   # only the canary scored again
    assert len(p.view_calls) - view_calls_before == 7 - done_views
    clean = baseline(p)
    assert metrics_by_sample(p.output) == metrics_by_sample(clean) and views_by_sample(p.output) == views_by_sample(clean)


def test_a_torn_write_is_quarantined_and_its_row_scored_fresh(package):
    p = package
    interrupted_run(p)
    victim = sorted((p.output / "checkpoints").glob("*.json"))[0]
    victim.rename(victim.with_name(victim.name + ".partial"))   # as if the atomic rename never happened
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert second["orchestration_checks_passed"] and second["reused_rows"] == 2 and second["fresh_rows"] == 5
    assert len(second["quarantined"]) == 1 and ".partial.quarantined-" in second["quarantined"][0]
    assert not list((p.output / "checkpoints").glob("*.partial")) and list((p.output / "checkpoints").glob("*.quarantined-*"))


def test_a_corrupt_checkpoint_is_a_hold_not_a_hole(package):
    p = package
    interrupted_run(p)
    victim = sorted((p.output / "checkpoints").glob("*.json"))[0]
    envelope = json.loads(victim.read_text())
    envelope["payload"]["result"]["metrics"] = {k: 0.0 for k in envelope["payload"]["result"]["metrics"]}
    victim.write_text(json.dumps(envelope))
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not result["orchestration_checks_passed"] and "integrity mismatch" in hold_reasons(result)


def test_a_foreign_checkpoint_file_is_a_hold(package):
    p = package
    interrupted_run(p)
    source = sorted((p.output / "checkpoints").glob("*.json"))[0]
    (p.output / "checkpoints" / ("f" * 64 + ".json")).write_bytes(source.read_bytes())
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not result["orchestration_checks_passed"] and "do not belong to this binding" in hold_reasons(result)


def test_a_changed_asset_binding_holds_instead_of_silently_rescoring(package):
    p = package
    interrupted_run(p)
    (p.assets / "bert" / "asset_manifest.json").write_text(json.dumps({"fixture_only": "changed"}))
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not result["orchestration_checks_passed"] and "do not belong to this binding" in hold_reasons(result)


def test_cross_session_drift_is_caught_by_the_canary(package):
    p = package
    interrupted_run(p)
    p.options["score_function"] = lambda summary, reference, source, semantic: {
        "metrics": {k: 0.6 for k in runner.METRICS}, "failures": {}}   # a runtime that now scores differently
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not result["orchestration_checks_passed"] and "Cross-session drift" in hold_reasons(result)


def test_partial_resume_is_refused_for_stages_without_the_policy_and_together_with_resume(package):
    p = package
    with pytest.raises(ValueError, match="stage policy opt-in"):
        runner.run(p.root, p.output, p.assets, resume_partial=True, **p.options)
    with pytest.raises(ValueError, match="stage policy opt-in"):
        runner.run(p.root, p.output, p.assets, stage=STAGE, resume=True, resume_partial=True, **p.options)


def test_plain_resume_still_refuses_a_partial_cache(package):
    p = package
    interrupted_run(p)
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume=True, **p.options)
    assert not result["orchestration_checks_passed"] and "Required resume checkpoint missing" in hold_reasons(result)


def other_vm(p, **changes):
    probe = p.options["runtime_probe"]
    return {**p.options, "runtime_probe": lambda: {**probe(), **changes}}


def test_portable_binding_ignores_the_vm_but_not_the_compute_runtime(package):
    p = package
    interrupted_run(p)
    vm_changes = {"platform": "Linux-other-kernel", "logical_cpu_count": 99, "torch_cpu_threads": 7, "google_colab_module": "/x"}
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **other_vm(p, **vm_changes))
    assert second["orchestration_checks_passed"] and second["reused_rows"] == 3
    # A different CUDA runtime changes what a score means: the earlier checkpoints no longer belong.
    third = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **other_vm(p, cuda_runtime="99.9"))
    assert not third["orchestration_checks_passed"] and "do not belong to this binding" in hold_reasons(third)


def test_strict_stages_still_bind_the_whole_runtime(package):
    p = package
    runner.run(p.root, p.output, p.assets, **p.options)
    result = runner.run(p.root, p.output, p.assets, resume=True, **other_vm(p, platform="Linux-other-kernel"))
    assert not result["orchestration_checks_passed"] and "Required resume checkpoint missing" in hold_reasons(result)


def test_strict_stage_receipts_gain_no_partial_resume_fields(package):
    p = package
    result = runner.run(p.root, p.output, p.assets, **p.options)
    assert not {"partial_resume_used", "reused_rows", "fresh_rows", "run_ids", "quarantined", "canary"} & set(result)
    payload = json.loads(next((p.output / "checkpoints").glob("*.json")).read_text())["payload"]
    assert set(payload) == {"key", "result", "original_scoring_wall_seconds"}


def test_portable_stage_checkpoints_carry_provenance(package):
    p = package
    first = runner.run(p.root, p.output, p.assets, stage=STAGE, **p.options)
    payload = json.loads(next((p.output / "checkpoints").glob("*.json")).read_text())["payload"]
    assert payload["provenance"]["run_id"] == first["run_id"] and len(payload["provenance"]["runtime_full_sha256"]) == 64


def test_the_runtime_digest_helper_is_unchanged_for_strict_stages():
    runtime = {"platform": "x", "packages": {"a": "1"}, "cuda_runtime": "12"}
    assert runner.runtime_binding_digest(runtime, runner.PILOT40_STAGE) == digest(runtime)
    assert runner.runtime_binding_digest(runtime, STAGE) == digest(
        {"cuda_runtime": "12", "device_name": None, "device_memory_bytes": None, "python": None, "packages": {"a": "1"}})


PROFILE_ORDER = ["lead3", "lexrank", "bart", "led"]


def canary_pool(count, strata=("long", "medium", "short")):
    """Rows as interleaved_order yields them: strata first, the four profiles of one source side by side."""
    rows = []
    for stratum in strata:
        for source in range(count // len(strata) // 4):
            for profile in PROFILE_ORDER:
                rows.append({"sample_id": f"{profile}__{stratum}-{source}", "profile_id": profile, "source_stratum": stratum})
    return rows


def test_canary_rows_cover_every_profile_and_stratum_and_are_deterministic():
    rows = canary_pool(2004)
    picked = runner.canary_rows(rows)
    assert len(picked) == runner.CANARY_ROWS == len({r["sample_id"] for r in picked})
    assert {r["profile_id"] for r in picked} == set(PROFILE_ORDER)
    assert {r["source_stratum"] for r in picked} == {"long", "medium", "short"}
    assert picked == runner.canary_rows(rows)


def test_an_early_interruption_still_samples_every_profile():
    only_long = canary_pool(2004, strata=("long",))[:800]
    picked = runner.canary_rows(only_long)
    assert {r["profile_id"] for r in picked} == set(PROFILE_ORDER) and {r["source_stratum"] for r in picked} == {"long"}


def test_few_or_no_reused_rows():
    rows = canary_pool(24)
    assert runner.canary_rows(rows[:2]) == rows[:2] and runner.canary_rows([]) == []
    assert len(runner.canary_rows(rows[:5])) == 5


def test_a_stored_scoring_failure_is_reused_as_failed_and_is_not_a_drift_witness(package):
    p = package
    original, state = p.options["score_function"], {"n": 0}

    def flaky(*args, **kwargs):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("transient out of memory")   # caught by the runner and stored as a failed result
        result = original(*args, **kwargs)
        if state["n"] == 3:
            p.clock.offset += 10_000
        return result
    p.options["score_function"] = flaky
    runner.run(p.root, p.output, p.assets, stage=STAGE, **p.options)
    p.options["score_function"] = original
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert second["canary"]["passed"] is True and "Cross-session drift" not in hold_reasons(second)
    assert second["reused_failed_rows"] == 1 and "metric_failures_or_unscored_records" in hold_reasons(second)
    assert second["delivered_status"] == "HOLD" and second["failed_or_unscored_scoreable_records"] == 1


def test_a_partial_resume_over_an_empty_folder_is_not_reported_as_used(package):
    p = package
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert result["partial_resume_requested"] is True and result["partial_resume_used"] is False
    assert result["reused_rows"] == 0 and result["canary"] is None and result["orchestration_checks_passed"]


def test_the_receipt_flags_sessions_that_ran_on_different_runtimes(package):
    p = package
    interrupted_run(p)
    same = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert same["mixed_runtime"] is False and len(same["runtime_full_sha256_by_run"]) == 2
    # A second, separate attempt: interrupt it, then resume on a VM with different thread settings.
    p2_output = Path(str(p.output) + "-b")
    original = interrupting(p, 3)
    runner.run(p.root, p2_output, p.assets, stage=STAGE, **p.options)
    p.options["score_function"] = original
    mixed = runner.run(p.root, p2_output, p.assets, stage=STAGE, resume_partial=True, **other_vm(p, torch_cpu_threads=7))
    assert mixed["orchestration_checks_passed"] and mixed["mixed_runtime"] is True
    assert len(set(mixed["runtime_full_sha256_by_run"].values())) == 2


def test_only_pinned_packages_enter_the_binding(package):
    p = package
    interrupted_run(p)
    packages = {**p.options["runtime_probe"]()["packages"], "an-unrelated-base-image-library": "9.9"}
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **other_vm(p, packages=packages))
    assert second["orchestration_checks_passed"] and second["reused_rows"] == 3


def test_reused_cost_is_reported_separately_and_the_canary_stays_out_of_component_totals(package):
    p = package
    interrupted_run(p)
    second = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    costs = json.loads((p.output / "cost_evidence.json").read_text())
    assert second["reused_original_scoring_seconds"] >= 0 and "reused_original_scoring_seconds" in costs
    assert costs["component_all_passes_calls"]["sentence_vectors"] == second["fresh_rows"] == 4
    assert costs["canary_seconds"] >= 0


def test_a_run_that_holds_leaves_torn_files_where_they_were(package):
    p = package
    interrupted_run(p)
    victim = sorted((p.output / "checkpoints").glob("*.json"))[0]
    torn = victim.with_name(victim.name + ".partial")
    victim.rename(torn)
    (p.output / "checkpoints" / ("f" * 64 + ".json")).write_text("{}")   # a foreign file makes the run hold
    result = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not result["orchestration_checks_passed"] and "do not belong to this binding" in hold_reasons(result)
    assert torn.exists() and not list((p.output / "checkpoints").glob("*.quarantined-*"))


def test_any_stray_file_in_the_checkpoint_folder_is_foreign_but_earlier_quarantines_are_not(package):
    p = package
    interrupted_run(p)
    victim = sorted((p.output / "checkpoints").glob("*.json"))[0]
    victim.rename(victim.with_name(victim.name + ".partial"))
    runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)   # leaves a quarantined file behind
    again = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert again["orchestration_checks_passed"] and again["fresh_rows"] == 0
    (p.output / "checkpoints" / "notes.txt").write_text("stray")
    stray = runner.run(p.root, p.output, p.assets, stage=STAGE, resume_partial=True, **p.options)
    assert not stray["orchestration_checks_passed"] and "do not belong to this binding" in hold_reasons(stray)
