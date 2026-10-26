"""Builder checks on a synthetic 300-ID x 4-profile evidence ZIP; no real source, reference or output."""
import json
import zipfile
from pathlib import Path

import pytest

from experiments.scripts import tib_selection300_scorer_bundle as builder
from experiments.scripts import tib_selection300_scorer_validation as validation
from experiments.scripts.tib_budget_views import build_views
from selection_scoring_fixtures import FAILED_LED, PROFILES, RAW, jsonl, make_world, build_bundle, sha


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("scoring-world"))


def rows_for(world, archive=None):
    return builder.selection_scoring_rows(archive or world.archive, world.qualification, world.cohort, world.profile_list)


def rewrite_zip(world, tmp_path, edit):
    """Copy the evidence ZIP, letting `edit(name, data) -> data|None` change or drop members."""
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(world.archive) as src, zipfile.ZipFile(bad, "w") as dst:
        for name in src.namelist():
            data = edit(name, src.read(name))
            if data is not None:
                dst.writestr(name, data)
    return bad


def edit_receipt(profile, change):
    def edit(name, data):
        if name != f"selection/{profile}/candidate_receipt.json":
            return data
        value = json.loads(data)
        change(value)
        return json.dumps(value).encode()
    return edit


def test_rows_cover_the_matrix_in_cohort_then_profile_order(world):
    rows = rows_for(world)
    assert len(rows) == 1200 and sum(r["scoreable"] for r in rows) == 1197
    assert [(r["record_id"], r["profile_id"]) for r in rows] == [(i, p) for i in world.ids for p in PROFILES]
    failed = [r for r in rows if not r["scoreable"]]
    assert sorted(r["record_id"] for r in failed) == sorted(FAILED_LED) and {r["profile_id"] for r in failed} == {"led"}
    assert all(r["views"] is None and r["delivered_summary"] is None and "AdapterFailure" in r["failure_reason"] for r in failed)


def test_views_and_delivered_match_the_view_builder(world):
    row = next(r for r in rows_for(world) if r["scoreable"] and r["profile_id"] == "bart")
    expected = build_views(RAW, builder.VIEW_BUDGETS)
    assert row["views"] == {name: expected[name]["text"] for name in "SML"}
    assert row["warnings"] == ["sentence_ending"] and row["delivered_sha256"] == sha(RAW)


def test_strata_match_the_quota_and_the_generation_contract(world):
    rows = rows_for(world)
    per_record = {r["record_id"]: r["source_stratum"] for r in rows}
    assert per_record == world.strata
    assert sorted(set(per_record.values())) == ["long", "medium", "short"]


@pytest.mark.parametrize("tamper", [
    "qualification_source", "qualification_reference", "delivered", "id_outside_cohort", "rights", "wrong_profile_sha",
    "oversized_delivered", "bad_status", "missing_record", "extra_qwen_directory", "bad_receipt_status", "stratum_drift"])
def test_identity_drift_is_rejected(world, tmp_path, tamper):
    qual, cohort, archive = world.qualification, world.cohort, world.archive
    rows_path = qual / "qualified_cohort/qualification_ledger.jsonl"
    rights_path = qual / "source_use_ledger.jsonl"
    saved = {p: p.read_text() for p in (rows_path, rights_path, cohort)}
    try:
        if tamper == "qualification_source":
            data = [json.loads(l) for l in rows_path.read_text().splitlines()]
            data[0]["source_normalized_sha256"] = "0" * 64
            rows_path.write_text(jsonl(data))
        elif tamper == "qualification_reference":
            data = [json.loads(l) for l in rows_path.read_text().splitlines()]
            data[1]["reference_normalized_sha256"] = "0" * 64
            rows_path.write_text(jsonl(data))
        elif tamper == "rights":
            data = [json.loads(l) for l in rights_path.read_text().splitlines()]
            data[2]["allowed_for_reference_scoring"] = False
            rights_path.write_text(jsonl(data))
        elif tamper == "id_outside_cohort":
            cohort.write_text(json.dumps({"selected_ids": {"pilot": [], "selection": world.ids[:-1] + ["fixture:999"]}}))
        elif tamper == "delivered":
            archive = rewrite_zip(world, tmp_path, edit_receipt("lead3", lambda v: v["records"][world.ids[0]]["result"].update(delivered_final="altered")))
        elif tamper == "oversized_delivered":
            long_text = "word " * 351
            def oversize(v):
                record = v["records"][world.ids[0]]
                record["result"].update(delivered_final=long_text)
                record["result"]["delivery"]["delivered_sha256"] = sha(long_text)
            archive = rewrite_zip(world, tmp_path, edit_receipt("lexrank", oversize))
        elif tamper == "wrong_profile_sha":
            archive = rewrite_zip(world, tmp_path, lambda n, d: json.dumps({"payload": {"profile_sha256": "f" * 64}}).encode()
                                  if n == "selection/bart/run_identity.json" else d)
        elif tamper == "bad_status":
            archive = rewrite_zip(world, tmp_path, edit_receipt("bart", lambda v: v["records"][world.ids[3]].update(status="stopped")))
        elif tamper == "missing_record":
            archive = rewrite_zip(world, tmp_path, edit_receipt("led", lambda v: v["records"].pop(world.ids[4])))
        elif tamper == "extra_qwen_directory":
            archive = rewrite_zip(world, tmp_path, lambda n, d: d)
            with zipfile.ZipFile(archive, "a") as z:
                z.writestr("selection/qwen3/candidate_receipt.json", "{}")
        elif tamper == "bad_receipt_status":
            archive = rewrite_zip(world, tmp_path, edit_receipt("lead3", lambda v: v.update(status="HOLD")))
        else:
            archive = rewrite_zip(world, tmp_path, edit_receipt("lead3", lambda v: v["records"][world.ids[0]].update(source_stratum="short" if world.strata[world.ids[0]] != "short" else "long")))
        with pytest.raises(ValueError):
            rows_for(world, archive)
    finally:
        for path, text in saved.items():
            path.write_text(text)


def test_build_packages_a_manifest_bound_private_bundle(world, tmp_path):
    receipt, local, registry = build_bundle(world, tmp_path)
    bundle_dir = local / "bundle"
    manifest = json.loads((bundle_dir / "package_manifest.json").read_text())
    on_disk = {p.relative_to(bundle_dir).as_posix() for p in bundle_dir.rglob("*") if p.is_file()} - {"package_manifest.json"}
    assert set(manifest["files"]) == on_disk and not any("__pycache__" in n for n in on_disk)
    assert (receipt["rows"], receipt["scoreable_rows"], receipt["failed_rows"]) == (1200, 1197, 3)
    assert receipt["rows_by_profile"] == dict.fromkeys(PROFILES, 300)
    assert receipt["scoring_start_authorized"] is False and receipt["scorer_ready"] is False
    with zipfile.ZipFile(local / builder.ARCHIVE_NAME) as z:
        assert set(z.namelist()) == set(manifest["files"]) | {"package_manifest.json"}
    validation.validate_selection_scoring_bundle(bundle_dir)


def test_contract_binds_generation_hashes_and_never_authorizes(world, tmp_path):
    receipt, local, registry = build_bundle(world, tmp_path)
    contract = json.loads((local / "bundle/scoring_contract.json").read_text())
    assert contract["generation_bundle_manifest_sha256"] == world.manifest_sha
    assert contract["generation_evidence_zip_sha256"] == world.archive_sha
    assert contract["scoring_start_authorized"] is False and contract["selection_rule_applied"] is False
    assert (contract["expected_rows"], contract["expected_scoreable"], contract["expected_failed"]) == (1200, 1197, 3)
    assert sorted(contract["failed_cells"]) == sorted(f"led__{i.replace(':', '-')}" for i in FAILED_LED)
    assert contract["metrics_computed_not_reported"] == ["source_sentence_similarity_v1"]


def test_bundle_is_free_of_qwen_data_and_registry_is_text_free(world, tmp_path):
    receipt, local, registry = build_bundle(world, tmp_path)
    for path in (local / "bundle").rglob("*"):
        # Only the amendment may name Qwen3, and only as an excluded profile.
        if path.is_file() and path.suffix in (".json", ".jsonl", ".txt") and path.name != "runtime_amendment.json":
            assert "qwen" not in path.read_text(encoding="utf-8").lower(), path.name
    amendment = json.loads((local / "bundle/runtime_amendment.json").read_text())
    assert "qwen3" not in amendment["profile_ids"] and set(amendment["excluded_profiles"]) == {"qwen3"}
    published = "".join(p.read_text(encoding="utf-8") for p in Path(registry).rglob("*") if p.is_file())
    assert "reference fixture" not in published and "source fixture" not in published and "Alpha beta" not in published


def test_generation_manifest_disagreement_stops_the_build(world, tmp_path):
    (world.registry / "preparation_receipt.json").write_text(json.dumps({"manifest_sha256": "0" * 64}))
    try:
        with pytest.raises(ValueError, match="manifest hash disagrees"):
            build_bundle(world, tmp_path)
    finally:
        (world.registry / "preparation_receipt.json").write_text(json.dumps({"manifest_sha256": world.manifest_sha}))


def test_changed_evidence_zip_or_count_stops_the_build(world, tmp_path):
    with pytest.raises(ValueError, match="hash changed"):
        builder.build(local=tmp_path / "l", registry=tmp_path / "r", evidence_zip=world.archive,
                      expected_evidence_sha="0" * 64, qualification=world.qualification, cohort_path=world.cohort,
                      binding=world.binding, generation_registry=world.registry)
    short = rewrite_zip(world, tmp_path, edit_receipt("led", lambda v: v["records"][world.ids[0]].update(
        status="failed", error="x")))
    with pytest.raises(ValueError, match="Expected 1200/1197"):
        builder.build(local=tmp_path / "l", registry=tmp_path / "r", evidence_zip=short, expected_evidence_sha=builder.file_hash(short),
                      qualification=world.qualification, cohort_path=world.cohort, binding=world.binding,
                      generation_registry=world.registry)
