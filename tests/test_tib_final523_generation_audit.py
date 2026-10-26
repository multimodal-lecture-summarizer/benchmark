"""Final523 generation audit on synthetic 523 x 4 evidence: clean pass, disclosure of lost cells, and every named tamper."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from experiments.scripts import tib_final523_generation_audit as audit_module
from experiments.scripts.tib_benchmark_checkpoint import digest
from final523_generation_fixtures import PROFILES, clone_world, make_generation_world, replace_text, write_json
from experiments.scripts.tib_selection300_scorer_bundle import BINDING

RULES = json.loads((BINDING / "admission_rules_v2.json").read_text(encoding="utf-8"))


def run(world, rules=None):
    return audit_module.audit(world.extracted, world.pkg, world.manifest_sha, rules)


def failed_checks(result):
    return sorted(k for k, v in result["checks"].items() if not v)


@pytest.fixture(scope="module")
def clean_world(tmp_path_factory):
    return make_generation_world(tmp_path_factory.mktemp("gen-clean"))


@pytest.fixture(scope="module")
def lossy_world(tmp_path_factory):
    return make_generation_world(tmp_path_factory.mktemp("gen-lossy"), failed={("led", "test:005")},
                                 interrupted={("bart", "test:100"), ("bart", "test:101")})


@pytest.fixture
def world(clean_world, tmp_path):
    return clone_world(clean_world, tmp_path)


def edit(path, change):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    change(value)
    write_json(path, value)


def first_record(world, profile):
    return sorted((world.sel / profile / "records").glob("*.json"))[0]


def edit_record(world, profile, change, reseal=True):
    path = first_record(world, profile)
    envelope = json.loads(path.read_text())
    change(envelope["payload"])
    if reseal:
        envelope["sha256"] = digest(envelope["payload"])
    write_json(path, envelope)


def test_clean_evidence_passes_with_nothing_lost(world):
    result = run(world, RULES)
    assert result["audit_pass"] is True and failed_checks(result) == []
    assert result["interrupted_count"] == 0 and result["failed_count"] == 0
    assert all(v["records_on_disk"] == 523 for v in result["per_profile"].values())
    assert result["bart_led_separation"]["proved_in_different_sessions"] is True
    assert result["informational_floors"]["rule_applied"] is False
    assert result["informational_floors"]["common_set"]["size"] == 523


def test_interrupted_and_failed_cells_are_disclosed_not_failing(lossy_world):
    result = run(lossy_world, RULES)
    assert result["audit_pass"] is True
    assert result["interrupted_count"] == 2 and {r["candidate"] for r in result["interrupted_records"]} == {"bart"}
    assert result["failed_count"] == 1 and result["failures"][0]["error_class"] == "AdapterFailure"
    assert result["per_profile"]["bart"]["statuses"]["started"] == 2
    floors = result["informational_floors"]
    assert floors["common_set"]["size"] == 523 - 3 and floors["per_profile"]["bart"]["scored_success_candidates"] == 521


def test_outcome_is_text_free_and_carries_no_record_text_or_score_key(lossy_world):
    result = run(lossy_world, RULES)
    assert audit_module.forbidden_keys({k: v for k, v in result.items() if k != "checks"}) == set()
    text = json.dumps(result)
    assert "delivered_final" not in text and "raw_final" not in text and "source_normalized" not in text
    assert "rouge" not in text.lower() and "bertscore" not in text.lower()
    assert "evidence_zip_sha256" not in result   # added by the CLI from the ZIP


@pytest.mark.parametrize("name,tamper,check", [
    ("missing record", lambda w: first_record(w, "led").unlink(), "all_cells_present_in_the_denominator"),
    ("extra profile directory", lambda w: write_json(w.sel / "qwen3" / "candidate_receipt.json", {}), "no_extra_profile_directory"),
    ("wrong source hash", lambda w: edit_record(w, "bart", lambda p: p.update(source_sha256="0" * 64)), "no_binding_mismatch_and_no_retry"),
    ("wrong stratum", lambda w: edit_record(w, "bart", lambda p: p.update(source_stratum="long" if p["source_stratum"] != "long" else "short")),
     "no_binding_mismatch_and_no_retry"),
    ("automatic retry", lambda w: edit_record(w, "lexrank", lambda p: p.update(automatic_retry=True)), "no_binding_mismatch_and_no_retry"),
    ("quality present", lambda w: edit_record(w, "lead3", lambda p: p.update(quality={"x": 1})), "quality_null_everywhere_and_all_fresh"),
    ("not fresh", lambda w: edit_record(w, "lead3", lambda p: p.update(origin="historical_import")), "quality_null_everywhere_and_all_fresh"),
    ("over the word cap", lambda w: edit_record(w, "bart", lambda p: p["result"]["delivery"].update(delivered_words=351)),
     "every_delivered_output_within_350_words"),
    ("reference key in a record", lambda w: edit_record(w, "led", lambda p: p.update(reference_summary="leak")),
     "no_reference_or_abstract_key_in_any_record"),
    ("abstract key nested", lambda w: edit_record(w, "led", lambda p: p["resources"].update(abstract_text="leak")),
     "no_reference_or_abstract_key_in_any_record"),
    ("corrupt envelope hash", lambda w: edit_record(w, "bart", lambda p: p.update(status="completed"), reseal=False), "every_record_file_intact_and_readable"),
    ("truncated record file", lambda w: replace_text(first_record(w, "bart"), '{"payload": {'), "every_record_file_intact_and_readable"),
    ("record copied from another profile", lambda w: edit_record(w, "bart", lambda p: p.update(binding={**p["binding"], "candidate_id": "lead3"})),
     "records_bound_to_the_run_identity_and_one_runtime"),
    ("record bound to another bundle", lambda w: edit_record(w, "led", lambda p: p["binding"].update(bundle_sha256="0" * 64)),
     "records_bound_to_the_run_identity_and_one_runtime"),
    ("two runtimes inside one profile", lambda w: edit_record(w, "led", lambda p: p.update(runtime_sha256="9" * 64)),
     "records_bound_to_the_run_identity_and_one_runtime"),
    ("unknown record status", lambda w: edit_record(w, "bart", lambda p: p.update(status="skipped")), "only_known_record_statuses"),
    ("extra file shipped in the package", lambda w: replace_text(w.extracted / "package/notes.txt", "extra"), "shipped_file_set_equals_the_manifest"),
    ("built bundle manifest differs from the expected hash", lambda w: replace_text(w.pkg / "selection_manifest.json", '{"files": {}}'),
     "package_manifest_matches_prepared_bundle"),
    ("preflight did not pass", lambda w: write_json(w.sel / "preflight_receipt.json", {"device_name": "Tesla T4", "status": "FAIL"}), "preflight_pass_on_tesla_t4"),
    ("authorization without a readiness hash", lambda w: edit(w.sel / "start_authorization.json", lambda a: a.update(readiness_receipt_v2_sha256="short")),
     "authorization_is_the_users_and_binds_this_bundle"),
    ("receipt summary lies", lambda w: edit(w.sel / "bart" / "candidate_receipt.json", lambda r: r["summary"].update(successful=1)),
     "receipt_summaries_match_the_records"),
    ("receipt status", lambda w: edit(w.sel / "bart" / "candidate_receipt.json", lambda r: r.update(status="HOLD")), "receipt_status_ok"),
    ("cpu profile incomplete", lambda w: edit_record(w, "lead3", lambda p: p.update(status="failed", error="x")), "cpu_profiles_complete"),
    ("run identity of another profile", lambda w: write_json(w.sel / "led" / "run_identity.json", {
        "payload": {**json.loads((w.sel / "led/run_identity.json").read_text())["payload"], "profile_sha256": "0" * 64},
        "sha256": "x"}), "run_identity_binds_contract_profile_and_bundle"),
    ("run identity bundle hash", lambda w: edit(w.sel / "bart" / "run_identity.json", lambda r: r["payload"].update(bundle_sha256="0" * 64)),
     "run_identity_binds_contract_profile_and_bundle"),
    ("not a T4", lambda w: write_json(w.sel / "preflight_receipt.json", {"device_name": "Tesla K80"}), "preflight_pass_on_tesla_t4"),
    ("authorization for another manifest", lambda w: edit(w.sel / "start_authorization.json", lambda a: a.update(manifest_sha256="0" * 64)),
     "authorization_is_the_users_and_binds_this_bundle"),
    ("authorization not by the user", lambda w: edit(w.sel / "start_authorization.json", lambda a: a.update(authorized_by="agent")),
     "authorization_is_the_users_and_binds_this_bundle"),
    ("metrics executed", lambda w: write_json(w.sel / "selection_summary.json", {"metrics_executed": True}), "metrics_not_executed"),
    ("ledger bound elsewhere", lambda w: edit(w.sel / "resource_ledger.json", lambda l: l.update(bundle_sha256="0" * 64)),
     "ledger_bound_to_this_bundle_and_allocation"),
    ("ledger over the GPU total", lambda w: edit(w.sel / "resource_ledger.json", lambda l: l.update(gpu_seconds=22 * 3600)),
     "ledger_within_approved_totals"),
    ("too many sessions", lambda w: edit(w.sel / "resource_ledger.json", lambda l: l["session_runs"].extend([l["session_runs"][0]] * 3)),
     "ledger_within_approved_totals"),
    ("shipped manifest differs", lambda w: write_json(w.extracted / "package/selection_manifest.json", {"files": {}}),
     "package_manifest_matches_prepared_bundle"),
    ("shipped file differs", lambda w: replace_text(w.extracted / "package/selection_sources.jsonl", "tampered"),
     "package_files_identical_to_built_bundle"),
    ("cohort file differs", lambda w: write_json(w.extracted / "package/locked/final_cohort.json", {"selected_ids": []}),
     "final_cohort_bound_to_the_bundle"),
])
def test_each_tamper_fails_by_name(clean_world, tmp_path, name, tamper, check):
    world = clone_world(clean_world, tmp_path)
    tamper(world)
    result = run(world)
    assert result["audit_pass"] is False and check in failed_checks(result), (name, failed_checks(result))


def test_a_selection_id_in_the_final_set_or_a_non_test_id_fails(world):
    contract = dict(world.contract, excluded_selection_ids=world.contract["excluded_selection_ids"][:299] + [world.ids[0]])
    write_json(world.pkg / "selection_contract.json", contract)
    result = run(world)
    assert "ids_are_test_ids_disjoint_from_development" in failed_checks(result)


def test_an_unauthorized_or_wrong_stage_contract_fails(world):
    write_json(world.pkg / "selection_contract.json", dict(world.contract, final_test_authorized=True))
    assert "contract_is_final523_and_unauthorized" in failed_checks(run(world))


def test_sessions_closed_as_interrupted_are_disclosed_without_failing(world):
    edit(world.sel / "resource_ledger.json", lambda l: l["session_runs"].__setitem__(0, dict(l["session_runs"][0], status="interrupted")))
    result = run(world)
    assert result["audit_pass"] is True and {"kind": "sessions_closed_as_interrupted", "count": 1} in result["anomalies"]


def test_session_separation_is_not_claimed_when_the_wall_times_do_not_prove_it(world):
    edit(world.sel / "resource_ledger.json", lambda l: l["candidate_runs"].__setitem__(3, dict(l["candidate_runs"][3], wall_seconds=100.0)))
    separation = run(world)["bart_led_separation"]
    assert separation["proved_in_different_sessions"] is False and "no per-session candidate id" in separation["note"]


def test_checkpoint_summary_is_compared_with_the_records_but_never_gates(world):
    write_json(world.sel / "checkpoint_summary.json", {"written_utc": "t", "profiles": {p: {"attempted": 523} for p in PROFILES}})
    assert run(world)["checkpoint_summary"]["matches_records_on_disk"] is True
    write_json(world.sel / "checkpoint_summary.json", {"written_utc": "t", "profiles": {p: {"attempted": 400} for p in PROFILES}})
    result = run(world)
    assert result["checkpoint_summary"]["matches_records_on_disk"] is False and result["audit_pass"] is True


@pytest.mark.parametrize("name,tamper", [
    ("a profile directory without a receipt", lambda w: (w.sel / "bart" / "candidate_receipt.json").unlink()),
    ("no session in the ledger", lambda w: edit(w.sel / "resource_ledger.json", lambda l: l.update(session_runs=[]))),
    ("a missing preflight receipt", lambda w: (w.sel / "preflight_receipt.json").unlink()),
    ("a record without resources", lambda w: edit_record(w, "bart", lambda p: p.update(resources=None))),
    ("a ledger that is not JSON", lambda w: replace_text(w.sel / "resource_ledger.json", "not json")),
])
def test_unreadable_or_oddly_shaped_evidence_fails_a_named_check_and_never_raises(clean_world, tmp_path, name, tamper):
    world = clone_world(clean_world, tmp_path)
    tamper(world)
    result = run(world)
    if name == "a record without resources":
        assert result["audit_pass"] is True   # an absent optional field is tolerated, not a crash
    else:
        assert result["audit_pass"] is False and failed_checks(result) == ["evidence_readable"] and result["unreadable"]


def test_the_closed_ledger_copy_is_used_when_the_export_cell_wrote_it(world):
    ledger = json.loads((world.sel / "resource_ledger.json").read_text())
    ledger["session_runs"][-1]["status"] = "active"
    write_json(world.sel / "resource_ledger.json", ledger)   # the ledger as zipped, before the last session closed
    assert run(world)["ledger_source"] == "resource_ledger.json"
    closed = json.loads(json.dumps(ledger))
    closed["session_runs"][-1]["status"] = "evidence_exported"
    closed["gpu_seconds"] = 22 * 3600   # the closure charged the capacity floor: over the approved total
    write_json(world.sel / "session_close_after_export.json", closed)
    result = run(world)
    assert result["ledger_source"] == "session_close_after_export.json"
    assert "ledger_within_approved_totals" in failed_checks(result)


def zip_tree(world, archive):
    with zipfile.ZipFile(archive, "w") as z:
        for path in sorted(world.extracted.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(world.extracted).as_posix())


def test_extract_zip_refuses_unsafe_members(tmp_path):
    for name in ("../escape.txt", "/absolute.txt"):
        archive = tmp_path / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr(name, "x")
        with pytest.raises(ValueError, match="Unsafe member"):
            audit_module.extract_zip(archive, tmp_path / "out")


def test_cli_audits_the_extraction_of_the_zip_it_hashes_and_records_once(world, tmp_path):
    archive = tmp_path / "evidence.zip"
    zip_tree(world, archive)
    out = tmp_path / audit_module.OUTCOME_NAME
    arguments = [sys.executable, "-m", "experiments.scripts.tib_final523_generation_audit", "--zip", str(archive),
                 "--package", str(world.pkg), "--manifest-sha", world.manifest_sha, "--out", str(out)]
    cwd = Path(audit_module.__file__).parents[2]
    first = subprocess.run(arguments, capture_output=True, text=True, cwd=cwd)
    assert first.returncode == 0, first.stderr
    outcome = json.loads(out.read_text())
    assert outcome["audit_pass"] is True and outcome["evidence_zip_sha256"] == audit_module.sha(archive)
    assert outcome["protocol_id"] == audit_module.PROTOCOL_ID and outcome["rule_applied"] is False
    assert "prior_evidence_zip_sha256" in outcome   # audit_pass + evidence_zip_sha256 are the keys the scoring builder reads
    second = subprocess.run(arguments, capture_output=True, text=True, cwd=cwd)
    assert second.returncode != 0 and "recorded once" in (second.stderr + second.stdout)


def test_a_zip_that_differs_from_a_clean_tree_is_audited_as_it_is(world, tmp_path):
    edit_record(world, "bart", lambda p: p.update(status="skipped"))
    archive = tmp_path / "evidence.zip"
    zip_tree(world, archive)
    out = tmp_path / "outcome.json"
    arguments = [sys.executable, "-m", "experiments.scripts.tib_final523_generation_audit", "--zip", str(archive),
                 "--package", str(world.pkg), "--manifest-sha", world.manifest_sha, "--out", str(out)]
    subprocess.run(arguments, capture_output=True, text=True, cwd=Path(audit_module.__file__).parents[2])
    assert json.loads(out.read_text())["audit_pass"] is False
