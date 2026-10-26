"""Final cohort seal on synthetic ledgers: counts, strata, group disjointness, rights, write-once."""
import copy
import json

import pytest

from experiments.scripts import tib_final523_seal as seal

CUTS = [100, 200]
QUOTAS = {"short": 3, "medium": 2, "long": 1}
WORDS = {"short": 50, "medium": 150, "long": 300}


def fixture():
    ledger, rights = [], []
    n = 0
    for stratum, count in QUOTAS.items():
        for _ in range(count):
            rid = f"test:{n}"
            sha = f"{n:064x}"
            ledger.append({"record_id": rid, "split": "test", "role_eligible": True, "group_id": f"g-test-{n}",
                           "source_words": WORDS[stratum], "source_normalized_sha256": sha})
            rights.append({"record_id": rid, "allowed_for_current_local_use": True, "source_normalized_sha256": sha})
            n += 1
    ledger += [{"record_id": "test:x", "split": "test", "role_eligible": False, "group_id": "g-x", "source_words": 10,
                "source_normalized_sha256": "0" * 64},
               {"record_id": "train:1", "split": "train", "role_eligible": True, "group_id": "g-train", "source_words": 10,
                "source_normalized_sha256": "1" * 64}]
    development = {"pilot": [{"group_id": "g-pilot"}], "selection": [{"group_id": "g-sel"}]}
    return ledger, rights, development, {"source_word_cutpoints": CUTS}


def build(ledger, rights, development, dev_cohort, **kw):
    return seal.build_cohort(ledger, rights, development, dev_cohort, expected_n=6, quotas=QUOTAS, **kw)


def test_builds_ordered_cohort_without_ineligible_ids():
    body = build(*fixture())
    assert body["ids"] == [f"test:{i}" for i in range(6)] and "test:x" not in body["ids"]
    assert body["source_strata"]["test:0"] == "short" and body["source_strata"]["test:5"] == "long"


def test_wrong_count_is_refused():
    ledger, rights, development, dev = fixture()
    with pytest.raises(ValueError, match="Expected exactly"):
        seal.build_cohort(ledger, rights, development, dev, expected_n=7, quotas=QUOTAS)


def test_quota_mismatch_is_refused():
    ledger, rights, development, dev = fixture()
    ledger[0]["source_words"] = 150
    with pytest.raises(ValueError, match="differ"):
        build(ledger, rights, development, dev)


def test_group_overlap_with_development_train_or_valid_is_refused():
    for group in ("g-pilot", "g-sel", "g-train"):
        ledger, rights, development, dev = fixture()
        ledger[0]["group_id"] = group
        with pytest.raises(ValueError, match="overlap"):
            build(ledger, rights, development, dev)


def test_shared_group_inside_the_test_split_is_refused():
    ledger, rights, development, dev = fixture()
    ledger[1]["group_id"] = ledger[0]["group_id"]
    with pytest.raises(ValueError, match="one-to-one"):
        build(ledger, rights, development, dev)


def test_rights_failure_or_identity_drift_is_refused():
    ledger, rights, development, dev = fixture()
    bad = copy.deepcopy(rights)
    bad[2]["allowed_for_current_local_use"] = False
    with pytest.raises(ValueError, match="Rights"):
        build(ledger, bad, development, dev)
    bad = copy.deepcopy(rights)
    bad[2]["source_normalized_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="identity"):
        build(ledger, bad, development, dev)
    with pytest.raises(ValueError, match="Rights"):
        build(ledger, rights[:-1], development, dev)


def test_real_cohort_seals_523_once_and_never_rewrites(tmp_path):
    first = seal.seal(registry=tmp_path)
    assert first["n"] == 523 and first["quotas"] == {"short": 182, "medium": 172, "long": 169}
    cohort = json.loads((tmp_path / seal.SEALED_FILE).read_text(encoding="utf-8"))
    assert cohort["final_test_sealed"] is True and cohort["final_test_authorized"] is False
    assert cohort["generation_executed"] is False and len(set(cohort["selected_ids"])) == 523
    dev = json.loads((seal.SEALED / "development_cohort.json").read_text(encoding="utf-8"))
    assert not set(cohort["selected_ids"]) & (set(dev["selected_ids"]["pilot"]) | set(dev["selected_ids"]["selection"]))
    with pytest.raises(FileExistsError):
        seal.seal(registry=tmp_path)
    text = (tmp_path / seal.SEALED_FILE).read_text(encoding="utf-8")
    assert "reference" not in text.replace("no reference field read", "")
