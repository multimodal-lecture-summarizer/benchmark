"""Final523 scoring builder and validator on synthetic 523-ID x 4-profile evidence; no real source, reference or output."""
import json
import zipfile

import pytest

from experiments.scripts import tib_final523_scorer_bundle as builder
from experiments.scripts import tib_final523_scorer_validation as validation
from experiments.scripts.tib_stage_session import digest
from final523_scoring_fixtures import FAILED_LED, INTERRUPTED, QUOTAS, build_final_bundle, good_outcome, make_final_world
from selection_scoring_fixtures import PROFILES, reseal


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_final_world(tmp_path_factory.mktemp("final-scoring"))


@pytest.fixture(scope="module")
def built(world, tmp_path_factory):
    first = build_final_bundle(world, tmp_path_factory.mktemp("a"))
    second = build_final_bundle(world, tmp_path_factory.mktemp("b"))
    return first, second


def test_counts_are_derived_from_the_failed_cells(built):
    (receipt, local, _), _ = built
    failed = len(FAILED_LED) + len(INTERRUPTED)
    assert (receipt["rows"], receipt["scoreable_rows"], receipt["failed_rows"]) == (2092, 2092 - failed, failed)
    assert receipt["rows_by_profile"] == dict.fromkeys(PROFILES, 523)
    contract = json.loads((local / "bundle/scoring_contract.json").read_text())
    assert contract["expected_failed"] == failed == len(contract["failed_cells"])
    assert contract["stage"] == "final523" and contract["quotas"] == QUOTAS


def test_bundle_validates_and_never_authorizes(built):
    (receipt, local, _), _ = built
    manifest, _, amendment, rows = validation.validate_final_scoring_bundle(local / "bundle")
    assert len(rows) == 2092 and amendment["expected_scoreable_count"] == receipt["scoreable_rows"]
    contract = json.loads((local / "bundle/scoring_contract.json").read_text())
    assert contract["scoring_start_authorized"] is False and contract["selection_rule_applied"] is False
    assert receipt["scoring_start_authorized"] is False and receipt["scorer_ready"] is False


def test_two_builds_are_byte_identical_and_zip_matches_manifest(built):
    (first, local_a, _), (second, local_b, _) = built
    assert first["archive_sha256"] == second["archive_sha256"] and first["manifest_sha256"] == second["manifest_sha256"]
    manifest = json.loads((local_a / "bundle/package_manifest.json").read_text())
    with zipfile.ZipFile(local_a / builder.ARCHIVE_NAME) as z:
        assert set(z.namelist()) == set(manifest["files"]) | {"package_manifest.json"}


def test_both_stage_validators_ship_and_receipt_carries_the_evidence_name(built):
    (receipt, local, _), _ = built
    shipped = {p.name for p in (local / "bundle/experiments/scripts").glob("*.py")}
    assert {"tib_final523_scorer_validation.py", "tib_selection300_scorer_validation.py"} <= shipped
    assert receipt["generation_evidence_zip_name"].startswith("tib-final523-evidence-")


def test_failed_cells_and_strata_follow_the_generation_evidence(built, world):
    (_, local, _), _ = built
    rows = [json.loads(l) for l in (local / "bundle/scoring_outputs.jsonl").read_text().splitlines()]
    failed = [r for r in rows if not r["scoreable"]]
    assert sorted(r["record_id"] for r in failed) == sorted(FAILED_LED + ("fixture:300",))
    assert {r["profile_id"] for r in failed} == {"led", "bart"}
    interrupted = next(r for r in failed if r["profile_id"] == "bart")
    assert interrupted["failure_reason"] == "interrupted_before_completion" and interrupted["views"] is None
    assert {r["record_id"]: r["source_stratum"] for r in rows} == world.strata


def test_a_generation_audit_that_did_not_pass_blocks_packaging(world, tmp_path):
    good = world.outcome.read_text()
    world.outcome.write_text(json.dumps({"audit_pass": False, "evidence_zip_sha256": world.archive_sha}))
    try:
        with pytest.raises(ValueError, match="did not pass its audit"):
            build_final_bundle(world, tmp_path)
        world.outcome.write_text(json.dumps(good_outcome("0" * 64)))
        with pytest.raises(ValueError, match="another evidence ZIP"):
            build_final_bundle(world, tmp_path)
    finally:
        world.outcome.write_text(good)


def test_changed_evidence_or_unsealed_cohort_or_other_stage_blocks_packaging(world, tmp_path):
    with pytest.raises(ValueError, match="hash changed"):
        builder.build(world.archive, "0" * 64, world.outcome, local=tmp_path / "l", registry=tmp_path / "r")
    saved = world.final_cohort.read_text()
    try:
        world.final_cohort.write_text(json.dumps({"selected_ids": world.ids, "final_test_sealed": False}))
        with pytest.raises(ValueError, match="sealed 523"):
            build_final_bundle(world, tmp_path / "x")
    finally:
        world.final_cohort.write_text(saved)


def test_evidence_generated_under_the_selection_allocation_is_refused(tmp_path):
    other = make_final_world(tmp_path, stage="selection300")
    with pytest.raises(ValueError, match="another stage"):
        build_final_bundle(other, tmp_path / "b")


def test_final_ids_overlapping_development_are_refused(world, tmp_path):
    world.development.write_text(json.dumps({"selected_ids": {"pilot": [world.ids[0]], "selection": []}}))
    try:
        with pytest.raises(ValueError, match="excluded IDs"):
            build_final_bundle(world, tmp_path)
    finally:
        world.development.write_text(json.dumps({"selected_ids": {"pilot": ["fixture:pilot-1"], "selection": ["fixture:sel-1"]}}))


def edit_bundle(local, name, change):
    path = local / "bundle" / name
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))
    reseal(local / "bundle")


@pytest.mark.parametrize("name,change,text", [
    ("scoring_contract.json", lambda c: c.update(expected_scoreable=c["expected_scoreable"] + 1), "output count"),
    ("scoring_contract.json", lambda c: c.update(failed_cells=c["failed_cells"][:-1]), "output count"),
    ("scoring_contract.json", lambda c: c.update(failed_cells=c["failed_cells"][:-1] + [c["failed_cells"][0]]), "output count"),
    ("scoring_contract.json", lambda c: c.update(scoring_start_authorized=True), "self-authorize"),
    ("scoring_contract.json", lambda c: c.update(stage="selection300"), "not the final523 stage"),
    ("scoring_contract.json", lambda c: c.update(allocation_sha256="0" * 64), "not the final523 stage"),
    ("scoring_contract.json", lambda c: c.update(profile_order=["lead3", "lexrank", "led", "bart"]), "profile universe"),
    ("scoring_contract.json", lambda c: c.update(generation_bundle_manifest_sha256="nothex"), "hash binding"),
    ("runtime_amendment.json", lambda c: c.update(expected_scoreable_count=1), "output count"),
])
def test_contract_deviations_are_refused(built, tmp_path, name, change, text):
    import shutil
    (_, local, _), _ = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    edit_bundle(copy, name, change)
    with pytest.raises(ValueError, match=text):
        validation.validate_final_scoring_bundle(copy / "bundle")


def test_failed_cell_list_must_match_the_rows(built, tmp_path):
    import shutil
    (_, local, _), _ = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    rows = [json.loads(l) for l in (copy / "bundle/scoring_outputs.jsonl").read_text().splitlines()]
    swapped = next(r for r in rows if r["profile_id"] == "lead3" and r["scoreable"])
    contract = json.loads((copy / "bundle/scoring_contract.json").read_text())
    contract["failed_cells"][0] = swapped["sample_id"]
    (copy / "bundle/scoring_contract.json").write_text(json.dumps(contract))
    reseal(copy / "bundle")
    with pytest.raises(ValueError, match="Failed cells differ"):
        validation.validate_final_scoring_bundle(copy / "bundle")


def test_runner_cli_knows_the_final_stage():
    import subprocess
    import sys
    from experiments.scripts import tib_pilot40_scorer_runner as runner
    result = subprocess.run([sys.executable, "-m", "experiments.scripts.tib_pilot40_scorer_runner", "--help"],
                            capture_output=True, text=True, cwd=str(__import__("pathlib").Path(runner.__file__).parents[2]))
    assert "final523" in result.stdout and result.returncode == 0


def carved(built):
    (_, local, _), _ = built
    return json.loads((local / "bundle/selection_allocation.json").read_text())


def test_scoring_budget_is_carved_out_of_what_generation_left(built, world):
    allocation = carved(built)
    carve = allocation["carved_from_generation"]
    assert allocation["max_sessions"] == 2 and allocation["stage"] == "final523"
    # 21 h approved, 36531.63 s used: 10.85 h left, rounded down; CPU 42 h - 47041.14 s = 28.93 h; transfer reduced by 5,759,850,502 bytes
    assert allocation["total_gpu_hours"] == allocation["total_wall_hours"] == 10.85
    assert allocation["total_cpu_hours"] == 28.93
    assert allocation["transfer_bytes"] == world.allocation["transfer_bytes"] - 5759850502
    assert carve["generation_approved"]["max_sessions"] == 4 and carve["generation_outcome_sessions_used"] == 3
    assert carve["generation_allocation_sha256"] == digest(world.allocation)
    used = carve["generation_ledger_used"]
    assert used["gpu_seconds"] + allocation["total_gpu_hours"] * 3600 <= world.allocation["total_gpu_hours"] * 3600


def test_contract_binds_both_allocations_and_the_user_decision(built, world):
    (_, local, _), _ = built
    contract = json.loads((local / "bundle/scoring_contract.json").read_text())
    assert contract["allocation_sha256"] == digest(carved(built))
    assert contract["generation_allocation_sha256"] == digest(world.allocation) != contract["allocation_sha256"]
    assert contract["scoring_budget_decision_sha256"] == builder.file_hash(local / "bundle" / validation.BUDGET_DECISION)
    assert (local / "bundle" / validation.BUDGET_DECISION).read_bytes() == builder.BUDGET_DECISION_PATH.read_bytes()


def test_carved_allocation_is_accepted_by_the_session_ledger_and_caps_scoring_at_two_sessions(built, tmp_path):
    from experiments.scripts.tib_stage_session import begin_session, finish_session
    allocation, ledger = carved(built), tmp_path / "ledger.json"
    for number in (1, 2):
        opened = begin_session(ledger, allocation, "a" * 64, local_working_root="/content/W",
                               observation={"boot_id": f"vm-{number}", "monotonic": 10.0, "epoch_ns": 1, "logical_cpu_count": 2})
        assert opened["session_limit_seconds"] == pytest.approx(10.85 * 3600 / 2)   # a lost session costs at most half of what is left
        finish_session(ledger, status="scoring_evidence_exported",
                       observation={"boot_id": f"vm-{number}", "monotonic": 20.0, "epoch_ns": 2, "logical_cpu_count": 2})
    with pytest.raises(ValueError, match="session"):
        begin_session(ledger, allocation, "a" * 64, local_working_root="/content/W",
                      observation={"boot_id": "vm-3", "monotonic": 10.0, "epoch_ns": 1, "logical_cpu_count": 2})


def test_scoring_ledger_precheck_accepts_a_missing_ledger_and_refuses_a_foreign_one(built, tmp_path):
    allocation = carved(built)
    fresh = validation.check_scoring_ledger_ready(tmp_path / "none.json", allocation, "a" * 64)
    assert fresh["sessions_used"] == 0 and fresh["max_sessions"] == 2 and fresh["new_ledger"] is True
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"bundle_sha256": "b" * 64, "allocation_sha256": digest(allocation), "session_status": "x",
                                 "session_runs": [], "gpu_seconds": 0}))
    with pytest.raises(ValueError, match="another bundle"):
        validation.check_scoring_ledger_ready(other, allocation, "a" * 64)


def test_generation_that_left_too_little_blocks_packaging(world, tmp_path):
    good = world.outcome.read_text()
    try:
        world.outcome.write_text(json.dumps(good_outcome(world.archive_sha, gpu_seconds=19 * 3600, completed_session_wall_seconds=19 * 3600)))
        with pytest.raises(ValueError, match="does not cover the scoring reserve"):
            build_final_bundle(world, tmp_path)
    finally:
        world.outcome.write_text(good)


@pytest.mark.parametrize("name,change,text", [
    ("selection_allocation.json", lambda a: a["carved_from_generation"]["generation_ledger_used"].update(gpu_seconds=1.0), "allocation hash differs"),
    ("selection_allocation.json", lambda a: a.update(total_gpu_hours=21.0), "allocation hash differs"),
])
def test_edited_scoring_allocation_is_refused(built, tmp_path, name, change, text):
    import shutil
    (_, local, _), _ = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    edit_bundle(copy, name, change)
    with pytest.raises(ValueError, match=text):
        validation.validate_final_scoring_bundle(copy / "bundle")


def test_a_carve_out_that_overshoots_the_approved_total_is_refused(built, tmp_path):
    import shutil
    (_, local, _), _ = built
    copy = tmp_path / "copy"
    shutil.copytree(local / "bundle", copy / "bundle")
    allocation = json.loads((copy / "bundle/selection_allocation.json").read_text())
    allocation.update(total_gpu_hours=20.0, total_wall_hours=20.0, max_sessions=4)
    contract = json.loads((copy / "bundle/scoring_contract.json").read_text())
    contract["allocation_sha256"] = digest(allocation)
    decision = json.loads((copy / "bundle" / validation.BUDGET_DECISION).read_text())
    decision["scoring_max_sessions"] = 4
    (copy / "bundle" / validation.BUDGET_DECISION).write_text(json.dumps(decision))
    allocation["carved_from_generation"]["decision_sha256"] = contract["scoring_budget_decision_sha256"] = builder.file_hash(
        copy / "bundle" / validation.BUDGET_DECISION)
    contract["allocation_sha256"] = digest(allocation)
    (copy / "bundle/selection_allocation.json").write_text(json.dumps(allocation))
    (copy / "bundle/scoring_contract.json").write_text(json.dumps(contract))
    reseal(copy / "bundle")
    with pytest.raises(ValueError, match="exceeds the approved total"):
        validation.validate_final_scoring_bundle(copy / "bundle")

