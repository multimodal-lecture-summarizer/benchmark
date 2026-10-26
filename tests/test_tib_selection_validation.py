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


def final_mini_bundle(root, monkeypatch, n=6):
    """The selection miniature rewritten into the final523 shape: test IDs, final stage allocation, 300 excluded."""
    from experiments.scripts.tib_benchmark_checkpoint import digest
    contract, rows = mini_bundle(root, monkeypatch, n)
    monkeypatch.setattr(validation, "FINAL_N", n)
    monkeypatch.setattr(validation, "FINAL_QUOTAS", {"short": 2, "medium": 2, "long": 2})
    ids = [f"test:{i}" for i in range(n)]
    for row, new in zip(rows, ids):
        row["record_id"] = new
    allocation = json.loads((root / "selection_allocation.json").read_text())
    allocation.update(stage="final523", records_per_pipeline=n)
    (root / "selection_allocation.json").write_text(json.dumps(allocation))
    contract.update(selection_ids=ids, source_strata=dict(zip(ids, [r["source_stratum"] for r in rows])),
                    excluded_selection_ids=[f"valid:{3000 + i}" for i in range(300)], allocation_sha256=digest(allocation))
    (root / "selection_contract.json").write_text(json.dumps(contract))
    (root / "selection_sources.jsonl").write_text("\n".join(map(json.dumps, rows)))
    refresh(root)
    return contract, rows


def test_final523_shape_round_trips(tmp_path, monkeypatch):
    root = tmp_path / "f"
    contract, _ = final_mini_bundle(root, monkeypatch)
    assert validation.validate_bundle(root)[0] == contract


@pytest.mark.parametrize("change,text", [
    (lambda c: c.update(excluded_selection_ids=c["excluded_selection_ids"][:299]), "development selection"),
    (lambda c: c["excluded_selection_ids"].__setitem__(0, c["selection_ids"][0]), "development selection"),
    (lambda c: c.update(expected_cells=23), "self-authorize"),
    (lambda c: c.update(final_test_authorized=True), "self-authorize"),
])
def test_final523_deviations_are_refused(tmp_path, monkeypatch, change, text):
    root = tmp_path / "f"
    final_mini_bundle(root, monkeypatch)
    mutate(root, "selection_contract.json", change)
    with pytest.raises(ValueError, match=text):
        validation.validate_bundle(root)


def test_final523_allocation_must_count_523_records(tmp_path, monkeypatch):
    from experiments.scripts.tib_benchmark_checkpoint import digest
    root = tmp_path / "f"
    final_mini_bundle(root, monkeypatch)
    allocation = json.loads((root / "selection_allocation.json").read_text())
    allocation["records_per_pipeline"] = 300
    (root / "selection_allocation.json").write_text(json.dumps(allocation))
    mutate(root, "selection_contract.json", lambda c: c.update(allocation_sha256=digest(allocation)))
    with pytest.raises(ValueError, match="does not match the stage"):
        validation.validate_bundle(root)


def test_test_ids_are_refused_in_a_selection_bundle(tmp_path, monkeypatch):
    root = tmp_path / "s"
    contract, rows = mini_bundle(root, monkeypatch)
    rows[0]["record_id"] = "test:0"
    contract["selection_ids"][0] = "test:0"
    contract["source_strata"] = {r["record_id"]: r["source_stratum"] for r in rows}
    (root / "selection_contract.json").write_text(json.dumps(contract))
    (root / "selection_sources.jsonl").write_text("\n".join(map(json.dumps, rows)))
    refresh(root)
    with pytest.raises(ValueError, match="does not belong to this stage"):
        validation.validate_bundle(root)


def test_selection_ids_are_refused_in_a_final523_bundle(tmp_path, monkeypatch):
    root = tmp_path / "f"
    contract, rows = final_mini_bundle(root, monkeypatch)
    rows[0]["record_id"] = "valid:5000"
    contract["selection_ids"][0] = "valid:5000"
    contract["source_strata"] = {r["record_id"]: r["source_stratum"] for r in rows}
    (root / "selection_contract.json").write_text(json.dumps(contract))
    (root / "selection_sources.jsonl").write_text("\n".join(map(json.dumps, rows)))
    refresh(root)
    with pytest.raises(ValueError, match="does not belong to this stage"):
        validation.validate_bundle(root)


def test_unknown_stage_is_refused():
    with pytest.raises(ValueError, match="Unknown stage"):
        validation.stage_config("final500")


def test_a_pinned_stage_must_match_the_allocation(tmp_path, monkeypatch):
    root = tmp_path / "f"
    final_mini_bundle(root, monkeypatch)
    assert validation.validate_bundle(root, expected_stage="final523")
    with pytest.raises(ValueError, match="another stage"):
        validation.validate_bundle(root, expected_stage="selection300")


def test_contract_and_allocation_must_name_the_same_stage(tmp_path, monkeypatch):
    root = tmp_path / "f"
    final_mini_bundle(root, monkeypatch)
    mutate(root, "selection_contract.json", lambda c: c.update(stage="selection300"))
    with pytest.raises(ValueError, match="different stages"):
        validation.validate_bundle(root)
