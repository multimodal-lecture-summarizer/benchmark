"""Bundle validator, scoring order and the Pilot40 regression guard for the generalised runner."""
import json
import shutil

import pytest

from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts import tib_selection300_scorer_validation as validation
from selection_scoring_fixtures import PROFILES, build_bundle, make_world, reseal, sha


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("validation-built")
    world = make_world(tmp)
    receipt, local, registry = build_bundle(world, tmp)
    return local / "bundle"


@pytest.fixture
def bundle(built, tmp_path):
    copy = tmp_path / "bundle"
    shutil.copytree(built, copy)
    return copy


def rewrite_rows(root, change):
    path = root / validation.OUTPUTS
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    change(rows)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    reseal(root)


def edit_json(root, name, change):
    path = root / name
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    path.write_text(json.dumps(value), encoding="utf-8")
    reseal(root)


def test_built_bundle_validates(bundle):
    manifest, spec, amendment, rows = validation.validate_selection_scoring_bundle(bundle)
    assert len(rows) == 1200 and sum(r["scoreable"] for r in rows) == 1197
    assert tuple(amendment["profile_ids"]) == PROFILES


def test_modified_file_or_unlisted_file_is_rejected(bundle):
    (bundle / "scoring_outputs.jsonl").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        validation.validate_selection_scoring_bundle(bundle)


def test_extra_file_is_rejected(bundle):
    (bundle / "extra.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="file set"):
        validation.validate_selection_scoring_bundle(bundle)


@pytest.mark.parametrize("name,change,match", [
    ("qwen3_in_amendment", lambda a: a.update(profile_ids=list(PROFILES) + ["qwen3"]), "profile universe"),
    ("wrong_count_amendment", lambda a: a.update(expected_output_count=1196), "output count"),
    ("self_authorizing", lambda a: a.update(selection_start_authorized=True), "self-authorize"),
])
def test_amendment_violations(bundle, name, change, match):
    edit_json(bundle, "runtime_amendment.json", change)
    with pytest.raises(ValueError, match=match):
        validation.validate_selection_scoring_bundle(bundle)


@pytest.mark.parametrize("change,match", [
    (lambda c: c.update(scoring_start_authorized=True), "self-authorize"),
    (lambda c: c.update(generation_bundle_manifest_sha256="short"), "hash binding"),
    (lambda c: c.update(selection_ids=c["selection_ids"][:-1]), "ID universe"),
    (lambda c: c.update(profile_order=["lexrank", "lead3", "bart", "led"]), "profile universe"),
])
def test_contract_violations(bundle, change, match):
    edit_json(bundle, "scoring_contract.json", change)
    with pytest.raises(ValueError, match=match):
        validation.validate_selection_scoring_bundle(bundle)


@pytest.mark.parametrize("name,change,match", [
    ("qwen3_profile", lambda rows: rows[0].update(profile_id="qwen3", candidate_id="qwen3"), "reordered|profile"),
    ("row_dropped", lambda rows: rows.pop(), "output count"),
    ("rows_reordered", lambda rows: rows.reverse(), "reordered"),
    ("missing_view", lambda rows: next(r for r in rows if r["scoreable"]).update(views={"S": "a", "M": "b"}), "views"),
    ("empty_view", lambda rows: next(r for r in rows if r["scoreable"]).update(views={"S": " ", "M": "b", "L": "c"}), "views"),
    ("failed_without_reason", lambda rows: next(r for r in rows if not r["scoreable"]).update(failure_reason=""), "reason"),
    ("failed_with_output", lambda rows: next(r for r in rows if not r["scoreable"]).update(delivered_summary="x"), "reason"),
    ("scoreable_flag", lambda rows: rows[0].update(scoreable=False), "Scoreable flag"),
    ("source_hash", lambda rows: rows[0].update(source="altered"), "text/hash"),
    ("reference_hash", lambda rows: rows[0].update(reference_sha256="0" * 64), "text/hash"),
    ("delivered_hash", lambda rows: rows[0].update(delivered_summary="altered words"), "Delivered"),
    ("oversize", lambda rows: rows[0].update(delivered_summary="w " * 351, delivered_sha256=sha("w " * 351)), "Delivered"),
    ("stratum", lambda rows: rows[0].update(source_stratum="short" if rows[0]["source_stratum"] != "short" else "long"), "status or stratum"),
    ("bad_status", lambda rows: rows[0].update(generation_status="stopped"), "status or stratum"),
    ("sample_id", lambda rows: rows[0].update(sample_id="x"), "binding"),
])
def test_row_violations(bundle, name, change, match):
    rewrite_rows(bundle, change)
    with pytest.raises(ValueError, match=match):
        validation.validate_selection_scoring_bundle(bundle)


def test_interleaved_order_keeps_four_profiles_together_and_long_first(bundle):
    _, _, _, rows = validation.validate_selection_scoring_bundle(bundle)
    ordered = validation.interleaved_order(rows)
    assert len(ordered) == 1197 and all(r["scoreable"] for r in ordered)
    strata = [validation.STRATUM_ORDER[r["source_stratum"]] for r in ordered]
    assert strata == sorted(strata)
    # Any prefix covers the four profiles within one row of each other, plus the failed cells of touched sources.
    failed_records = {r["record_id"] for r in rows if not r["scoreable"]}
    for cut in (4, 41, 400, 1000):
        prefix = ordered[:cut]
        counts = [sum(r["profile_id"] == p for r in prefix) for p in PROFILES]
        assert max(counts) - min(counts) <= 1 + len(failed_records & {r["record_id"] for r in prefix})
    first_source = ordered[0]["record_id"]
    assert [r["profile_id"] for r in ordered[:4]] == list(PROFILES) and {r["record_id"] for r in ordered[:4]} == {first_source}


def test_default_runner_stage_and_order_are_the_pilot40_ones():
    assert runner.PILOT40_STAGE["receipt"] == "scorer_pilot40_receipt.json"
    assert runner.PILOT40_STAGE["ready_key"] == "scorer_pilot40_ready"
    rows = [{"scoreable": True, "source_stratum": "short", "sample_id": "b"},
            {"scoreable": True, "source_stratum": "long", "sample_id": "z"},
            {"scoreable": False, "source_stratum": "long", "sample_id": "a"}]
    assert [r["sample_id"] for r in runner.run_order(rows)] == ["z", "b"]
