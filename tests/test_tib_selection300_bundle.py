"""Selection source identity checks on a miniature sealed cohort, plus the Pilot40-derived node forecast."""
import gzip
import hashlib
import json
import zipfile

import pytest

from experiments.scripts import tib_selection300_bundle as bundle
from experiments.scripts.tib_pilot_bundle import sha

QUOTAS = {"short": 2, "medium": 2, "long": 2}
IDS = [f"valid:{i}" for i in range(6)]
PILOT = [f"valid:{100 + i}" for i in range(3)]


def text_for(i):
    return " ".join(["word"] * (10 if i < 2 else 60 if i < 4 else 200)) + f" id{i}."


def jsonl(rows):
    return "".join(json.dumps(r) + "\n" for r in rows)


def sealed_world(tmp_path):
    sealed, qual = tmp_path / "sealed", tmp_path / "qual"
    (qual / "qualified_cohort").mkdir(parents=True)
    (qual / "eda").mkdir()
    sealed.mkdir()
    (sealed / "qualification_policy.json").write_text("{}")
    cohort = {"policy_sha256": sha(sealed / "qualification_policy.json"), "selection_quotas": QUOTAS,
              "selected_ids": {"selection": IDS, "pilot": PILOT}, "source_word_cutpoints": [30, 100]}
    (sealed / "development_cohort.json").write_text(json.dumps(cohort))
    sources = {i: text_for(n) for n, i in enumerate(IDS)}
    rights = [{"record_id": i, "allowed_for_current_local_use": True, "source_use_status": "ok",
               "source_normalized_sha256": hashlib.sha256(t.encode()).hexdigest(), "author": "a", "title": "t",
               "source_url": "u", "released_license_raw": "r", "license_uri_canonical": "l",
               "modification_notice": "m", "conditions_recorded": "c"} for i, t in sources.items()]
    eligible = [{"record_id": i, "role_eligible": True, "group_id": "g" + i,
                 "source_normalized_sha256": hashlib.sha256(t.encode()).hexdigest()} for i, t in sources.items()]
    (qual / "source_use_ledger.jsonl").write_text(jsonl(rights))
    (qual / "qualified_cohort/qualification_ledger.jsonl").write_text(jsonl(eligible))
    (qual / "qualified_cohort/development_records.json").write_text(json.dumps({
        "pilot": [{"group_id": "p" + i} for i in PILOT], "selection": [{"group_id": "g" + i} for i in IDS]}))
    with gzip.open(qual / "eda/canonical_records.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(jsonl([{"record_id": i, "source_normalized": t} for i, t in sources.items()]))
    (qual / "eda/receipt.json").write_text(json.dumps({"files": {
        "canonical_records.jsonl.gz": sha(qual / "eda/canonical_records.jsonl.gz")}}))
    return sealed, qual


def load(tmp_path, **kw):
    sealed, qual = sealed_world(tmp_path)
    return bundle.selection_sources(sealed, qual, expected_n=6, quotas=QUOTAS, **kw), (sealed, qual)


def test_sources_follow_sealed_order_with_recomputed_quotas_and_no_reference(tmp_path):
    (cohort, rows, ledger), _ = load(tmp_path)
    assert [r["record_id"] for r in rows] == IDS and [r["source_stratum"] for r in rows] == ["short"] * 2 + ["medium"] * 2 + ["long"] * 2
    assert all(set(r) == {"record_id", "source_normalized", "source_normalized_sha256", "source_stratum",
                          "source_words", "attribution"} for r in rows)
    assert len(ledger) == 6


def test_overlap_with_pilot_or_wrong_count_or_quota_is_refused(tmp_path):
    sealed, qual = sealed_world(tmp_path)
    cohort = json.loads((sealed / "development_cohort.json").read_text())
    cohort["selected_ids"]["pilot"] = [IDS[0]]
    (sealed / "development_cohort.json").write_text(json.dumps(cohort))
    with pytest.raises(ValueError, match="disjoint"):
        bundle.selection_sources(sealed, qual, expected_n=6, quotas=QUOTAS)
    sealed, qual = sealed_world(tmp_path / "two")
    with pytest.raises(ValueError, match="selection IDs"):
        bundle.selection_sources(sealed, qual, expected_n=7, quotas=QUOTAS)
    with pytest.raises(ValueError, match="quotas"):
        bundle.selection_sources(sealed, qual, expected_n=6, quotas={"short": 3, "medium": 2, "long": 1})


@pytest.mark.parametrize("break_what", ["rights", "hash", "group", "canonical"])
def test_identity_and_rights_drift_is_refused(tmp_path, break_what):
    sealed, qual = sealed_world(tmp_path)
    if break_what == "rights":
        rows = [json.loads(line) for line in (qual / "source_use_ledger.jsonl").read_text().splitlines()]
        rows[0]["allowed_for_current_local_use"] = False
        (qual / "source_use_ledger.jsonl").write_text(jsonl(rows))
    elif break_what == "hash":
        path = qual / "qualified_cohort/qualification_ledger.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["source_normalized_sha256"] = "0" * 64
        path.write_text(jsonl(rows))
    elif break_what == "group":
        path = qual / "qualified_cohort/development_records.json"
        value = json.loads(path.read_text())
        value["pilot"][0]["group_id"] = value["selection"][0]["group_id"]
        path.write_text(json.dumps(value))
    else:
        (qual / "eda/receipt.json").write_text(json.dumps({"files": {"canonical_records.jsonl.gz": "0" * 64}}))
    with pytest.raises(ValueError):
        bundle.selection_sources(sealed, qual, expected_n=6, quotas=QUOTAS)


def forecast_zip(path, *, drop_stage=None):
    with zipfile.ZipFile(path, "w") as z:
        for candidate, base in (("bart", 2.0), ("led", 10.0)):
            records = {}
            for i, stage in enumerate(("map", "reduce", "final")):
                if stage == drop_stage:
                    continue
                records[f"valid:{i}"] = {"status": "completed", "stage_resources": [
                    {"stage": stage, "wall_seconds": base + i}, {"stage": stage, "wall_seconds": base}]}
            records["valid:9"] = {"status": "failed", "stage_resources": [{"stage": "map", "wall_seconds": 999}]}
            z.writestr(f"pilot/{candidate}/candidate_receipt.json", json.dumps(
                {"records": records, "model_load_wall_seconds": 30.0}))


def test_forecast_is_one_and_a_half_times_the_worst_measured_call_and_ignores_failed(tmp_path):
    path = tmp_path / "e.zip"
    forecast_zip(path)
    f = bundle.node_forecast(path, sha(path))
    assert f["stage_seconds"]["bart"] == {"final": 6.0, "map": 3.0, "reduce": 4.5}
    assert f["stage_seconds"]["led"]["final"] == 18.0 and f["load_seconds"] == {"bart": 45.0, "led": 45.0}


def test_forecast_requires_every_stage_and_a_pinned_zip(tmp_path):
    path = tmp_path / "e.zip"
    forecast_zip(path, drop_stage="reduce")
    with pytest.raises(ValueError, match="every generation stage"):
        bundle.node_forecast(path, sha(path))
    with pytest.raises(ValueError, match="hash changed"):
        bundle.node_forecast(path, "0" * 64)
