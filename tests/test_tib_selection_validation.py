"""Selection bundle validation on a miniature bundle, plus the start-authorization check."""
import json

import pytest

from selection_fixtures import authorization, mini_bundle, refresh
from experiments.scripts import tib_selection_validation as validation


def mutate(root, name, change):
    path = root / name
    value = json.loads(path.read_text())
    change(value)
    path.write_text(json.dumps(value))
    refresh(root)


def test_valid_mini_bundle_round_trips(tmp_path, monkeypatch):
    root = tmp_path / "b"
    contract, rows = mini_bundle(root, monkeypatch)
    actual, sources, _ = validation.validate_bundle(root)
    assert actual == contract and sources == rows


@pytest.mark.parametrize("name,change,text", [
    ("selection_contract.json", lambda c: c.update(staged_ids=["valid:1"]), "No historical import"),
    ("selection_contract.json", lambda c: c.update(excluded_pilot_ids=c["excluded_pilot_ids"][:39]), "Pilot40"),
    ("selection_contract.json", lambda c: c["excluded_pilot_ids"].__setitem__(0, c["selection_ids"][0]), "Pilot40"),
    ("selection_contract.json", lambda c: c.update(selection_authorized=True), "self-authorize"),
    ("selection_contract.json", lambda c: c.update(candidate_order=c["candidate_order"] + ["qwen3"]), "four fixed"),
    ("selection_contract.json", lambda c: c.update(quotas={"short": 3, "medium": 2, "long": 1}), "strata"),
    ("selection_contract.json", lambda c: c["locked_artifacts"].update({"output_policy_v2.json": "0" * 64}), "Locked artifact"),
    ("selection_allocation.json", lambda c: c.update(total_gpu_hours=99), "Allocation binding"),
    ("node_forecast.json", lambda c: c["stage_seconds"].pop("led"), "Node forecast"),
    ("actual_scorer_ready_receipt.json", lambda c: c.update(status="HOLD"), "scorer-ready"),
])
def test_deviations_are_refused(tmp_path, monkeypatch, name, change, text):
    root = tmp_path / "b"
    mini_bundle(root, monkeypatch)
    mutate(root, name, change)
    with pytest.raises(ValueError, match=text):
        validation.validate_bundle(root)


def test_reference_field_or_tampered_file_is_refused(tmp_path, monkeypatch):
    root = tmp_path / "b"
    mini_bundle(root, monkeypatch)
    lines = (root / "selection_sources.jsonl").read_text().splitlines()
    row = json.loads(lines[0])
    row["reference_summary"] = "leak"
    lines[0] = json.dumps(row)
    (root / "selection_sources.jsonl").write_text("\n".join(lines))
    with pytest.raises(ValueError, match="hash mismatch"):
        validation.validate_bundle(root)
    refresh(root)
    with pytest.raises(ValueError, match="Reference/abstract"):
        validation.validate_bundle(root)


def test_source_order_must_match_contract(tmp_path, monkeypatch):
    root = tmp_path / "b"
    mini_bundle(root, monkeypatch)
    lines = (root / "selection_sources.jsonl").read_text().splitlines()
    lines[0], lines[1] = lines[1], lines[0]
    (root / "selection_sources.jsonl").write_text("\n".join(lines))
    refresh(root)
    with pytest.raises(ValueError, match="ordered selection sources"):
        validation.validate_bundle(root)


def test_authorization_must_be_complete_user_made_and_bound_to_this_bundle(tmp_path, monkeypatch):
    root = tmp_path / "b"
    mini_bundle(root, monkeypatch)
    _, _, manifest_sha = validation.validate_bundle(root)
    good = authorization(root)
    assert validation.check_authorization(good, manifest_sha) is good
    missing = {k: v for k, v in good.items() if k != "statement"}
    cases = ((dict(good, manifest_sha256="0" * 64), "different bundle"), (dict(good, authorized_by="agent"), "user"),
             (dict(good, statement=" "), "user"), (missing, "missing"), (None, "missing"),
             (dict(good, readiness_receipt_v2_sha256="short"), "readiness receipt"))
    for bad, text in cases:
        with pytest.raises(ValueError, match=text):
            validation.check_authorization(bad, manifest_sha)
