"""Offline contracts for reference qualification and immutable calibration."""
import inspect
import json

import pytest

from experiments.scripts import tib_model_benchmark_references as reference


@pytest.mark.parametrize("value", ["brief", "Course description", "REUSED abstract", "safety"])
def test_nonempty_short_generic_or_reused_never_automatically_c(value):
    assert reference.classify_reference(value) == "B"


def test_empty_and_technical_normalization_are_separate_from_casefold_history():
    assert reference.classify_reference(" \n\t") == "C"
    assert reference.normalize("  e\u0301 \n Topic ") == "é Topic"
    assert reference.normalize("Topic") != reference.normalize("topic")
    assert reference.historical_normalize("Topic") == reference.historical_normalize("topic")


def test_classification_accepts_no_scores_or_predictions():
    assert list(inspect.signature(reference.classify_reference).parameters) == ["reference"]
    assert "rouge" not in inspect.getsource(reference.classify_reference).lower()


def test_calibration_precedes_freeze_and_cannot_overwrite(tmp_path, monkeypatch):
    rows = [("train", index, {"transcript": "source", "abstract": "abstract"}) for index in range(8)]
    monkeypatch.setattr(reference, "iter_records", lambda _: iter(rows))
    path = tmp_path / "policy.json"
    reference.freeze_policy(tmp_path, path)
    policy = json.loads(path.read_text(encoding="utf-8"))
    assert len(policy["calibration"]) == 6
    assert all(row["record_id"].startswith("train:") for row in policy["calibration"])
    assert policy["calibration_version"] and policy["policy_version"]
    assert policy["default_nonempty"] == "B"
    assert policy["status"] == "frozen_before_full_ledger"
    with pytest.raises(ValueError, match="already frozen"):
        reference.freeze_policy(tmp_path, path)


def test_review_hash_mismatch_cannot_attach_evidence(tmp_path):
    output = tmp_path / "out"
    output.mkdir()
    row = {"record_id": "train:0", "source_raw_sha256": "actual"}
    (output / "reference_usability_ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    review = {"groups": [{"decision": "B", "rationale": "uncertain", "members": [
        {"record_id": "train:0", "source_spans": [[0, 2]], "source_raw_sha256": "different"}]}]}
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    with pytest.raises(ValueError, match="hashes differ"):
        reference.apply_reviews(output, tmp_path, path, tmp_path)


@pytest.mark.parametrize("existing", ["reference_usability_ledger.jsonl", "reference_summary.json", "historical_reuse_review.jsonl"])
def test_base_qualification_refuses_overwrite_before_reading_inputs(tmp_path, monkeypatch, existing):
    path = tmp_path / existing
    path.write_text("preserve reviewed evidence", encoding="utf-8")
    monkeypatch.setattr(reference, "iter_records", lambda _: pytest.fail("must not process input"))
    with pytest.raises(ValueError, match="cannot be overwritten"):
        reference.qualify(tmp_path, tmp_path / "absent-policy.json", tmp_path, tmp_path)
    assert path.read_text(encoding="utf-8") == "preserve reviewed evidence"


@pytest.mark.parametrize("start,end,digest", [(-1, 3, "correct"), (0, 7, "correct"), (3, 2, "correct"),
                                             (True, 3, "correct"), (0, 3, "wrong")])
def test_review_span_must_match_actual_source(tmp_path, monkeypatch, start, end, digest):
    raw = {"transcript": "source", "abstract": "reference"}
    monkeypatch.setattr(reference, "iter_records", lambda _: iter([("train", 0, raw)]))
    row = {"record_id": "train:0", "reference_label": "B", "source_raw_sha256": reference.sha("source"),
           "reference_raw_sha256": reference.sha("reference"), "reference_normalized_sha256": reference.sha("reference")}
    member = {**row, "source_spans": [{"start": start, "end": end,
              "coordinate": "raw Unicode character offsets; end exclusive",
              "sha256": reference.sha("sou") if digest == "correct" else "wrong"}]}
    with pytest.raises(ValueError, match="span|excerpt"):
        reference.verify_review_members(tmp_path, {"train:0": ({}, member)}, [row])


def test_valid_span_is_verified_from_actual_text_not_only_ledger(tmp_path, monkeypatch):
    raw = {"transcript": "source", "abstract": "reference"}
    monkeypatch.setattr(reference, "iter_records", lambda _: iter([("train", 0, raw)]))
    row = {"record_id": "train:0", "reference_label": "B", "source_raw_sha256": reference.sha("source"),
           "reference_raw_sha256": reference.sha("reference"), "reference_normalized_sha256": reference.sha("reference")}
    member = {**row, "source_spans": [{"start": 0, "end": 3,
              "coordinate": "raw Unicode character offsets; end exclusive", "sha256": reference.sha("sou")}]}
    assert reference.verify_review_members(tmp_path, {"train:0": ({}, member)}, [row]) == 1
    member["source_raw_sha256"] = row["source_raw_sha256"] = "forged matching ledger/member"
    with pytest.raises(ValueError, match="actual pinned text"):
        reference.verify_review_members(tmp_path, {"train:0": ({}, member)}, [row])
