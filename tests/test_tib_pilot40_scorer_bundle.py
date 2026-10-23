"""Bundle identity checks on a miniature evidence ZIP and qualification folder."""
import gzip
import hashlib
import json
import zipfile

import pytest

from experiments.scripts import tib_pilot40_scorer_bundle as bundle
from experiments.scripts.tib_budget_views import build_views

IDS = ["valid:1", "valid:2"]
RAW = ("Alpha beta gamma delta. " * 20 + "Second sentence here. " * 20).strip()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def jsonl(rows):
    return "".join(json.dumps(r) + "\n" for r in rows)


def make_record(record_id, stratum, status="completed"):
    base = {"origin": "fresh", "source_stratum": stratum, "retain_in_denominator": True,
            "source_sha256": sha("source " + record_id), "status": status}
    if status == "failed":
        return {**base, "origin": "historical_import", "error": "ValueError: Historical persisted config mismatch"}
    delivered = RAW
    return {**base, "result": {"raw_final": RAW, "delivered_final": delivered,
                               "delivery": {"delivered_sha256": sha(delivered)}},
            "validation": {"acceptance": {"warnings": ["sentence_ending"] if status == "completed_with_warning" else []}}}


@pytest.fixture
def world(tmp_path):
    qualification = tmp_path / "qual"
    (qualification / "qualified_cohort").mkdir(parents=True)
    (qualification / "eda").mkdir()
    rights = [{"record_id": i, "allowed_for_current_local_use": True, "allowed_for_reference_scoring": True} for i in IDS]
    qual = [{"record_id": i, "role_eligible": True, "reference_label": "A",
             "source_normalized_sha256": sha("source " + i), "reference_normalized_sha256": sha("reference " + i)}
            for i in IDS]
    (qualification / "source_use_ledger.jsonl").write_text(jsonl(rights), encoding="utf-8")
    (qualification / "qualified_cohort/qualification_ledger.jsonl").write_text(jsonl(qual), encoding="utf-8")
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(jsonl([{"record_id": i, "source_normalized": "source " + i,
                             "reference_normalized": "reference " + i} for i in IDS]))
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"selected_ids": {"pilot": IDS, "selection": ["valid:9"]}}))
    archive = tmp_path / "evidence.zip"
    sources = [{"record_id": i, "source_normalized": "source " + i, "source_normalized_sha256": sha("source " + i),
                "attribution": "attr"} for i in IDS]
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("package/pilot_sources.jsonl", jsonl(sources))
        for profile in (*bundle.PROFILES, "qwen3"):
            records = {i: make_record(i, "long" if i == IDS[0] else "short",
                                      "completed_with_warning" if profile == "led" else "completed") for i in IDS}
            if profile == "bart":
                records["valid:2"] = make_record("valid:2", "short", "failed")
            z.writestr(f"pilot/{profile}/candidate_receipt.json", json.dumps({"records": records}))
    return archive, qualification, cohort


def rows_for(world):
    archive, qualification, cohort = world
    return bundle.pilot40_rows(archive, qualification, cohort)


def test_four_profiles_no_qwen3_failed_cell_retained(world):
    rows = rows_for(world)
    assert len(rows) == 8 and {r["profile_id"] for r in rows} == set(bundle.PROFILES)
    failed = [r for r in rows if not r["scoreable"]]
    assert len(failed) == 1 and failed[0]["profile_id"] == "bart" and failed[0]["views"] is None
    assert "Historical persisted config mismatch" in failed[0]["failure_reason"]
    led = next(r for r in rows if r["profile_id"] == "led")
    assert led["warnings"] == ["sentence_ending"] and led["generation_status"] == "completed_with_warning"


def test_views_match_budget_view_builder(world):
    row = next(r for r in rows_for(world) if r["scoreable"])
    expected = build_views(RAW, bundle.VIEW_BUDGETS)
    assert row["views"] == {name: expected[name]["text"] for name in "SML"}


@pytest.mark.parametrize("tamper", ["source", "delivered", "selection_overlap", "rights", "missing_profile_record"])
def test_identity_drift_is_rejected(world, tamper, tmp_path):
    archive, qualification, cohort = world
    if tamper == "source":
        path = qualification / "qualified_cohort/qualification_ledger.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        rows[0]["source_normalized_sha256"] = "0" * 64
        path.write_text(jsonl(rows))
    elif tamper == "delivered":
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(bad, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == "pilot/lead3/candidate_receipt.json":
                    value = json.loads(data)
                    value["records"][IDS[0]]["result"]["delivered_final"] = "altered"
                    data = json.dumps(value).encode()
                dst.writestr(name, data)
        archive = bad
    elif tamper == "selection_overlap":
        cohort.write_text(json.dumps({"selected_ids": {"pilot": IDS, "selection": [IDS[0]]}}))
    elif tamper == "rights":
        path = qualification / "source_use_ledger.jsonl"
        rows = [json.loads(l) for l in path.read_text().splitlines()]
        rows[1]["allowed_for_reference_scoring"] = False
        path.write_text(jsonl(rows))
    else:
        bad = tmp_path / "bad.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(bad, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == "pilot/led/candidate_receipt.json":
                    value = json.loads(data)
                    value["records"].pop(IDS[1])
                    data = json.dumps(value).encode()
                dst.writestr(name, data)
        archive = bad
    with pytest.raises(ValueError):
        bundle.pilot40_rows(archive, qualification, cohort)
