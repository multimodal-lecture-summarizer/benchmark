"""Final523 scoring audit on synthetic evidence: fresh and resumed passes, every named tamper, and no score values anywhere."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from experiments.scripts import tib_final523_scoring_audit as audit_module
from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts.tib_scorer_colab_checkpoint import digest, file_sha
from final523_scoring_audit_fixtures import (
    BUNDLE_SHA, FAILED, RUN_FINAL, RUN_FIRST, RUN_KILLED, clone, make_scoring_world, sample_id, write,
)


def keys_of(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from keys_of(inner)


def values_of(value):
    if isinstance(value, dict):
        for inner in value.values():
            yield from values_of(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from values_of(inner)
    else:
        yield value


def run(world):
    return audit_module.audit(world.extracted, BUNDLE_SHA, world.contract, world.rules, world.ledger, world.allocation, world.policy_path)


def failed_checks(result):
    return sorted(k for k, v in result["checks"].items() if not v)


@pytest.fixture(scope="module")
def fresh_base(tmp_path_factory):
    return make_scoring_world(tmp_path_factory.mktemp("score-fresh"))


@pytest.fixture(scope="module")
def resumed_base(tmp_path_factory):
    return make_scoring_world(tmp_path_factory.mktemp("score-resumed"), resumed=True)


@pytest.fixture
def fresh(fresh_base, tmp_path):
    return clone(fresh_base, tmp_path)


@pytest.fixture
def resumed(resumed_base, tmp_path):
    return clone(resumed_base, tmp_path)


def edit(path, change):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    change(value)
    write(path, value)


def reseal_artifacts(world):
    edit(world.evidence / "scorer_final523_receipt.json", lambda r: r.update(
        artifact_sha256={n: file_sha(world.evidence / n) for n in r["artifact_sha256"]}))


def edit_receipt(world, change):
    edit(world.evidence / "scorer_final523_receipt.json", change)


def edit_rows(world, change):
    path = world.evidence / "metrics.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    change(rows)
    write(path, rows, lines=True)
    reseal_artifacts(world)


def first_checkpoint(world, folder="checkpoints"):
    return sorted((world.evidence / folder).glob("*.json"))[0]


def edit_checkpoint(world, change, folder="checkpoints", index=0, reseal=True):
    path = sorted((world.evidence / folder).glob("*.json"))[index]
    envelope = json.loads(path.read_text())
    change(envelope["payload"])
    if reseal:
        envelope["sha256"] = digest(envelope["payload"])
    write(path, envelope)


def test_fresh_run_passes_and_reports_no_reuse(fresh):
    result = run(fresh)
    assert result["audit_pass"] is True and failed_checks(result) == [] and result["anomalies"] == []
    assert result["resume"]["mode"] == "fresh" and result["resume"]["reused_rows"] == 0
    assert result["resume"]["fresh_rows"] == 47 and result["counts"]["failed_generation_cells"] == 1
    assert result["runs_without_receipt"] == 1 and result["resume"]["checkpoint_counts"]["mixed_runtime"] is False


def test_resumed_run_passes_with_all_resume_checks(resumed):
    result = run(resumed)
    assert result["audit_pass"] is True and failed_checks(result) == []
    assert {"drift_canary_ran_and_passed", "reuse_accounting_adds_up_and_matches_the_checkpoints",
            "checkpoint_runs_are_the_contributing_runs", "every_contributing_run_has_an_archived_directory"} <= set(result["checks"])
    assert result["resume"]["mode"] == "partial" and result["resume"]["reused_rows"] == 5 and result["resume"]["fresh_rows"] == 42
    assert [r["run_id"] for r in result["run_timeline"]] == [RUN_KILLED, RUN_FIRST, RUN_FINAL]
    assert result["resume"]["checkpoint_counts"]["score_checkpoints_by_run"] == {RUN_FIRST: 5, RUN_FINAL: 42}
    first = next(r for r in result["run_timeline"] if r["run_id"] == RUN_FIRST)
    assert first["delivered_status"] == "HOLD" and first["rows_scored_fresh"] == 5
    assert result["resume"]["reused_original_scoring_seconds"] == 5.0


def test_the_outcome_carries_no_score_value_or_score_key(resumed):
    result = run(resumed)
    text = json.dumps(result)
    assert result["scores_included"] is False and result["rule_applied"] is False
    assert "scores_descriptive" not in result and "means" not in text and "descriptive_means" not in text
    assert not [k for k in keys_of(result) if k.endswith("_f1") or k in ("metrics", "means", "views")]   # no metric-bearing keys
    assert not [v for v in values_of(result) if isinstance(v, float) and v in (0.3, 0.2, 0.4)]   # the fabricated score values
    assert audit_module.PROTOCOL_ID.startswith("tib-final523")
    assert "0.3" not in text   # the fabricated metric value of every scored cell


def test_coverage_is_informational_and_costs_are_split(resumed):
    result = run(resumed)
    assert result["coverage"]["rule_applied"] is False and result["coverage"]["c_between"]["size"] == 11
    assert "total" in result["timing_seconds_fresh_rows_only"] and result["resume"]["fresh_scoring_seconds"] > 0


@pytest.mark.parametrize("name,tamper,check", [
    ("receipt on HOLD", lambda w: edit_receipt(w, lambda r: r.update(delivered_status="HOLD")), "receipt_delivered_pass"),
    ("views incomplete", lambda w: edit_receipt(w, lambda r: r.update(views_status="PARTIAL_DEADLINE")), "views_complete"),
    ("injected dependencies", lambda w: edit_receipt(w, lambda r: r.update(testing_dependency_injection=True)), "not_injected"),
    ("not a T4", lambda w: edit_receipt(w, lambda r: r["runtime"].update(device_name="Tesla K80")), "actual_colab_t4"),
    ("bundle manifest differs", lambda w: edit_receipt(w, lambda r: r["binding"].update(package_manifest_sha256="0" * 64)), "bundle_manifest_bound"),
    ("generation evidence differs", lambda w: edit_receipt(w, lambda r: r["binding"].update(evidence_zip_sha256="0" * 64)), "generation_evidence_bound"),
    ("artifact changed", lambda w: (w.evidence / "cost_evidence.json").write_text("{}"), "artifact_hashes_match"),
    ("a row missing", lambda w: edit_rows(w, lambda rows: rows.pop()), "row_counts"),
    ("failed cell not NULL", lambda w: edit_rows(w, lambda rows: next(r for r in rows if r["sample_id"] == FAILED)["metrics"].update(rougeL_f1=0.1)),
     "failed_cells_null"),
    ("undeclared failed cell", lambda w: edit_rows(w, lambda rows: rows[0].update(scoring_status="not_scoreable_generation_failed")), "failed_cells_are_the_declared_ones"),
    ("a metric missing", lambda w: edit_rows(w, lambda rows: next(r for r in rows if r["scoring_status"] == "completed")["metrics"].update(bertscore_f1=None)),
     "five_metrics_finite"),
    ("qwen profile", lambda w: edit_rows(w, lambda rows: rows[0].update(profile_id="qwen3")), "profiles_fixed_no_qwen3"),
    ("contract authorizes scoring", lambda w: (w.contract.update(scoring_start_authorized=True)), "contract_is_final523_and_unauthorized"),
    ("shipped contract differs", lambda w: edit(w.bundle / "scoring_contract.json", lambda c: c.update(expected_failed=9)), "shipped_contract_is_the_registry_contract"),
])
def test_base_tampers_fail_by_name(fresh, name, tamper, check):
    tamper(fresh)
    result = run(fresh)
    assert result["audit_pass"] is False and check in failed_checks(result), (name, failed_checks(result))


def test_a_missing_view_row_fails(fresh):
    path = fresh.evidence / "view_metrics.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    del rows[0]["views"]["S"]
    write(path, rows, lines=True)
    reseal_artifacts(fresh)
    assert "view_rows_finite_and_complete" in failed_checks(run(fresh))


@pytest.mark.parametrize("name,tamper,check", [
    ("a foreign checkpoint binding", lambda w: edit_checkpoint(w, lambda p: p["key"].update(binding={"x": 1})), "checkpoints_intact_unique_and_bound_to_the_receipt"),
    ("a corrupt checkpoint envelope", lambda w: edit_checkpoint(w, lambda p: p.update(original_scoring_wall_seconds=99.0), reseal=False),
     "checkpoints_intact_unique_and_bound_to_the_receipt"),
    ("a checkpoint missing", lambda w: first_checkpoint(w).unlink(), "checkpoints_cover_exactly_the_scored_cells"),
    ("a view checkpoint missing", lambda w: first_checkpoint(w, "view_checkpoints").unlink(), "checkpoints_cover_exactly_the_scored_cells"),
    ("provenance from an unknown run", lambda w: edit_checkpoint(w, lambda p: p["provenance"].update(run_id="9999")), "checkpoint_runs_are_the_contributing_runs"),
    ("no provenance at all", lambda w: edit_checkpoint(w, lambda p: p.pop("provenance")), "checkpoint_runs_are_the_contributing_runs"),
    ("a run outside the receipt", lambda w: edit_receipt(w, lambda r: r.update(run_ids=[RUN_FINAL])), "checkpoint_runs_are_the_contributing_runs"),
    ("reuse accounting broken", lambda w: edit_receipt(w, lambda r: r.update(reused_rows=r["reused_rows"] + 1)),
     "reuse_accounting_adds_up_and_matches_the_checkpoints"),
    ("checkpoints disagree with the claimed fresh count", lambda w: edit_checkpoint(w, lambda p: p["provenance"].update(run_id=RUN_FIRST), index=-1),
     "reuse_accounting_adds_up_and_matches_the_checkpoints"),
    ("a contributing run directory deleted", lambda w: shutil.rmtree(w.evidence / "runs" / RUN_FIRST), "every_contributing_run_has_an_archived_directory"),
    ("canary missing", lambda w: edit_receipt(w, lambda r: r.update(canary=None)), "drift_canary_ran_and_passed"),
    ("canary failed", lambda w: edit_receipt(w, lambda r: r["canary"].update(passed=False)), "drift_canary_ran_and_passed"),
    ("canary drift above tolerance", lambda w: edit_receipt(w, lambda r: r["canary"].update(max_abs_diff=1e-3)), "drift_canary_ran_and_passed"),
    ("canary on a row that was not reused", lambda w: edit_receipt(w, lambda r: r["canary"].update(sample_ids=[sample_id("lead3", "fixture:11")])),
     "drift_canary_ran_and_passed"),
    ("canary tolerance loosened", lambda w: edit_receipt(w, lambda r: r["canary"].update(tolerance=1e-3)), "drift_canary_ran_and_passed"),
    ("a reused failed row", lambda w: edit_receipt(w, lambda r: r.update(reused_failed_rows=1)), "no_reused_failed_rows"),
    ("policy file changed", lambda w: edit(w.bundle / "scorer_resume_policy_final523_v1.json", lambda p: p.update(post_hoc=True)),
     "resume_policy_is_the_users_pre_run_declaration"),
    ("policy hash not in the contract", lambda w: w.contract.update(resume_policy_sha256="0" * 64), "resume_policy_is_the_users_pre_run_declaration"),
    ("CUDA runtime differs between runs", lambda w: edit(w.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json", lambda r: r["runtime"].update(cuda_runtime="11.8")),
     "contributing_runs_agree_on_the_compute_runtime"),
    ("a pinned package differs between runs", lambda w: edit(w.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json",
                                                              lambda r: r["runtime"]["packages"].update(torch="9.9")),
     "contributing_runs_agree_on_the_compute_runtime"),
    ("an orphan quarantined file", lambda w: (w.evidence / "checkpoints" / "ghost.json.partial.quarantined-1").write_text("{}"),
     "quarantined_files_are_listed_and_their_rows_scored"),
    ("a quarantined file whose row exists but no run listed it", lambda w: (first_checkpoint(w).parent / (first_checkpoint(w).name + ".partial.quarantined-7")).write_text("{}"),
     "quarantined_files_are_listed_and_their_rows_scored"),
    ("a receipt-listed quarantine that is not on disk", lambda w: edit_receipt(w, lambda r: r.update(quarantined=["nowhere.json.partial.quarantined-9"])),
     "quarantined_files_are_listed_and_their_rows_scored"),
])
def test_resume_tampers_fail_by_name(resumed, name, tamper, check):
    tamper(resumed)
    result = run(resumed)
    assert result["audit_pass"] is False and check in failed_checks(result), (name, failed_checks(result))


def test_a_fresh_run_that_claims_reuse_fails(fresh):
    edit_rows(fresh, lambda rows: rows[0].update(reused=True))
    assert "fresh_run_reused_nothing" in failed_checks(run(fresh))


def test_a_fresh_run_with_a_checkpoint_from_another_run_fails(fresh):
    edit_checkpoint(fresh, lambda p: p["provenance"].update(run_id=RUN_KILLED))   # another run directory exists, but it is not this run
    assert "fresh_run_checkpoints_all_belong_to_this_run" in failed_checks(run(fresh))


def test_a_complete_replay_passes_without_partial_fields(fresh):
    edit_rows(fresh, lambda rows: [r.update(reused=True) for r in rows if r["scoring_status"] == "completed"])
    edit_receipt(fresh, lambda r: r.update(cached_replay_verified=True))
    result = run(fresh)
    assert result["resume"]["mode"] == "replay" and result["audit_pass"] is True, failed_checks(result)
    edit_rows(fresh, lambda rows: rows[0].update(reused=False))
    assert "replay_reused_every_scored_row" in failed_checks(run(fresh))


def test_a_wrong_row_id_fails_a_named_check_and_never_crashes_the_coverage(fresh):
    edit_rows(fresh, lambda rows: rows[0].update(record_id="evil:1"))
    result = run(fresh)
    assert "rows_are_the_contract_matrix_with_unique_sample_ids" in failed_checks(result) and result["coverage"] is None


def test_a_duplicate_sample_id_fails(fresh):
    edit_rows(fresh, lambda rows: rows[1].update(sample_id=rows[0]["sample_id"]))
    assert "rows_are_the_contract_matrix_with_unique_sample_ids" in failed_checks(run(fresh))


def test_a_run_that_held_before_the_runtime_probe_does_not_count_against_agreement(resumed):
    edit(resumed.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json", lambda r: r.update(runtime={}))
    result = run(resumed)
    assert result["audit_pass"] is True, failed_checks(result)


def test_unrelated_installed_packages_do_not_fail_agreement_but_are_disclosed(resumed):
    edit(resumed.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json",
         lambda r: r["runtime"]["packages"].update({"an-unrelated-library": "9.9"}))
    result = run(resumed)
    assert result["audit_pass"] is True and result["resume"]["checkpoint_counts"]["mixed_runtime"] is True
    assert "packages" in result["resume"]["checkpoint_counts"]["runtime_fields_that_differ_between_runs"]
    assert result["resume"]["checkpoint_counts"]["compute_fields_that_differ_between_runs"] == ["packages"]


def test_free_text_in_a_run_reason_never_reaches_the_outcome(resumed):
    edit(resumed.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json",
         lambda r: r.update(reasons=["ValueError: the summary said something private"]))
    result = run(resumed)
    assert "something private" not in json.dumps(result)
    assert next(r for r in result["run_timeline"] if r["run_id"] == RUN_FIRST)["reasons"] == ["ValueError"]


@pytest.mark.parametrize("name,tamper", [
    ("a missing receipt", lambda w: (w.evidence / "scorer_final523_receipt.json").unlink()),
    ("a ledger without sessions", lambda w: w.ledger.update(session_runs=[])),
    ("a truncated metrics file", lambda w: (w.evidence / "metrics.jsonl").write_text('{"sample_id": ')),
    ("a receipt without a binding", lambda w: edit_receipt(w, lambda r: r.pop("binding"))),
])
def test_unreadable_or_oddly_shaped_evidence_fails_a_named_check_and_never_raises(resumed, name, tamper):
    tamper(resumed)
    result = run(resumed)
    assert result["audit_pass"] is False and list(result["checks"]) == ["evidence_readable"] and result["unreadable"]


def test_a_malformed_checkpoint_is_counted_corrupt_not_a_crash(resumed):
    first_checkpoint(resumed).write_text("not json")
    result = run(resumed)
    assert "checkpoints_intact_unique_and_bound_to_the_receipt" in failed_checks(result)


def test_a_checkpoint_under_the_wrong_file_name_is_corrupt(resumed):
    path = first_checkpoint(resumed)
    path.rename(path.with_name("0" * 64 + ".json"))
    assert "checkpoints_intact_unique_and_bound_to_the_receipt" in failed_checks(run(resumed))


def test_a_quarantined_file_with_its_row_rescored_passes(resumed):
    victim = first_checkpoint(resumed)
    (victim.parent / (victim.name + ".partial.quarantined-" + RUN_FINAL)).write_text("{}")
    edit_receipt(resumed, lambda r: r.update(quarantined=[victim.name + ".partial.quarantined-" + RUN_FINAL]))
    result = run(resumed)
    assert result["audit_pass"] is True and result["resume"]["checkpoint_counts"]["quarantined_files"] == 1
    assert result["resume"]["quarantined"] == [victim.name + ".partial.quarantined-" + RUN_FINAL]


def test_non_compute_runtime_differences_are_disclosed_as_mixed_runtime_without_failing(resumed):
    edit(resumed.evidence / "runs" / RUN_FIRST / "scorer_final523_receipt.json", lambda r: r["runtime"].update(platform="Linux-other", logical_cpu_count=99))
    result = run(resumed)
    assert result["audit_pass"] is True and result["resume"]["mixed_runtime"] is True
    assert set(result["resume"]["runtime_fields_that_differ_between_runs"]) == {"platform", "logical_cpu_count"}
    assert result["resume"]["compute_fields_that_differ_between_runs"] == []


@pytest.mark.parametrize("name,tamper,anomaly", [
    ("session still active", lambda w: w.ledger["session_runs"][-1].update(status="active"), "scoring_session_still_active"),
    ("session closed as interrupted", lambda w: w.ledger["session_runs"][-1].update(status="interrupted"), "scoring_session_closed_as_interrupted"),
    ("ledger for another bundle", lambda w: w.ledger.update(bundle_sha256="0" * 64), "ledger_bound_to_another_bundle"),
    ("too many sessions", lambda w: w.ledger["session_runs"].extend([w.ledger["session_runs"][0]] * 3), "session_count_above_allocation"),
    ("GPU over the total", lambda w: w.ledger.update(gpu_seconds=22 * 3600), "cumulative_gpu_above_allocation"),
    ("wall shorter than the runner's", lambda w: w.ledger["session_runs"][-1].update(measured_wall_seconds=10.0), "session_wall_shorter_than_runner_wall"),
])
def test_ledger_anomalies_fail_the_audit(fresh, name, tamper, anomaly):
    tamper(fresh)
    result = run(fresh)
    assert result["audit_pass"] is False and anomaly in result["anomalies"], (name, result["anomalies"])


def test_the_audit_uses_the_runner_constants_not_its_own(resumed, monkeypatch):
    monkeypatch.setattr(runner, "CANARY_ROWS", 7)
    assert "resume_policy_is_the_users_pre_run_declaration" in failed_checks(run(resumed))


def zip_extracted(world, archive):
    with zipfile.ZipFile(archive, "w") as z:
        for path in sorted(world.extracted.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(world.extracted).as_posix())


def test_cli_audits_the_extraction_of_the_zip_it_hashes_and_refuses_to_overwrite(resumed, tmp_path):
    archive = tmp_path / "scoring-evidence.zip"
    zip_extracted(resumed, archive)
    paths = {"contract": tmp_path / "contract.json", "ledger": tmp_path / "ledger.json", "allocation": tmp_path / "allocation.json",
             "rules": tmp_path / "rules.json"}
    for name, value in (("contract", resumed.contract), ("ledger", resumed.ledger), ("allocation", resumed.allocation), ("rules", resumed.rules)):
        write(paths[name], value)
    out = tmp_path / audit_module.OUTCOME_NAME
    arguments = [sys.executable, "-m", "experiments.scripts.tib_final523_scoring_audit", "--zip", str(archive),
                 "--manifest-sha", BUNDLE_SHA, "--contract", str(paths["contract"]), "--rules", str(paths["rules"]),
                 "--policy", str(resumed.policy_path), "--ledger", str(paths["ledger"]), "--allocation", str(paths["allocation"]), "--out", str(out)]
    cwd = Path(audit_module.__file__).parents[2]
    first = subprocess.run(arguments, capture_output=True, text=True, cwd=cwd)
    assert first.returncode == 0, first.stderr
    outcome = json.loads(out.read_text())
    assert outcome["audit_pass"] is True and outcome["evidence_zip_sha256"] == audit_module.sha(archive)
    assert outcome["protocol_id"] == audit_module.PROTOCOL_ID and outcome["scores_included"] is False
    second = subprocess.run(arguments, capture_output=True, text=True, cwd=cwd)
    assert second.returncode != 0 and "recorded once" in (second.stderr + second.stdout)


def test_row_order_is_the_runners_scoring_order_and_does_not_matter(fresh):
    edit_rows(fresh, lambda rows: rows.reverse())
    result = run(fresh)
    assert result["audit_pass"] is True, failed_checks(result)


def test_a_missing_or_repeated_cell_fails_the_matrix_check(fresh):
    edit_rows(fresh, lambda rows: rows.__setitem__(1, dict(rows[0], sample_id="other:1")))
    assert "rows_are_the_contract_matrix_with_unique_sample_ids" in failed_checks(run(fresh))
