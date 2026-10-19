"""Protect evidence boundaries and strict local-use gates, independently of A/B/C."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from experiments.scripts.tib_model_benchmark_rights import (
    POLICY_VERSION, canonical_license_uri, decide_record, validate_policy,
)

POLICY = json.loads((Path(__file__).parents[1] / "experiments/registry/datasets/"
                    "tib-text-model-benchmark-v1/qualification-261019-1703/"
                    "source_use_policy.json").read_text(encoding="utf-8"))


def record(uri="http://creativecommons.org/licenses/by/3.0/", prose="CC Attribution 3.0"):
    raw = {"released_license_raw": prose}
    row = {"record_id": "train:1", "author": "Author", "title": "Title",
           "source_url": "https://av.tib.eu/media/1", "source_nonempty": True,
           "reference_nonempty": True, "opendata_record_found": True,
           "current_source_license_uris": [uri],
           "released_license_raw_sha256": hashlib.sha256(prose.encode()).hexdigest(),
           "abstract_use_status": "SUPPORTED_CC0_FIELD_MATCH",
           "reference_cc0_match": "raw_exact"}
    return row, raw


@pytest.mark.parametrize("uri", [u for u, r in POLICY["license_routes"].items()
                                if r["decision"] == "conditional"])
def test_actual_versioned_cc_routes_have_narrow_boolean_permission(uri):
    row, raw = record(uri)
    out = decide_record(row, raw, POLICY)
    assert out["source_use_status"] == "conditional"
    assert out["allowed_for_current_local_use"] is True
    assert out["allowed_for_reference_scoring"] is True
    assert out["public_text_redistribution_allowed"] is False
    assert out["conditions_recorded"]["external_api_text_transfer"] is False


@pytest.mark.parametrize("uri", [u for u, r in POLICY["license_routes"].items()
                                if r["decision"] == "hold"] + [
    "https://creativecommons.org/licenses/by/9.0/", "http://rightsstatements.org/vocab/InC/1.0/"])
def test_older_nd_unmapped_and_nonopen_never_pass(uri):
    row, raw = record(uri)
    out = decide_record(row, raw, POLICY)
    assert out["source_use_status"] == "hold"
    assert out["allowed_for_current_local_use"] is False


def test_absent_current_grant_cannot_inherit_release_label_or_representative_mapping():
    row, raw = record()
    row["current_source_license_uris"] = []
    row["opendata_record_found"] = False
    assert decide_record(row, raw, POLICY)["allowed_for_current_local_use"] is False


@pytest.mark.parametrize("key,value", [("opendata_record_found", "true"),
                                      ("source_nonempty", "true"), ("author", "")])
def test_missing_attribution_or_truthy_evidence_cannot_pass(key, value):
    row, raw = record()
    row[key] = value
    assert decide_record(row, raw, POLICY)["allowed_for_current_local_use"] is False


@pytest.mark.parametrize("key,value", [("reference_cc0_match", "no_text_match"),
                                      ("reference_nonempty", "true"),
                                      ("abstract_use_status", "HOLD")])
def test_source_grant_never_clears_missing_reference_grant(key, value):
    row, raw = record()
    row[key] = value
    out = decide_record(row, raw, POLICY)
    assert out["allowed_for_current_local_use"] is True
    assert out["reference_allowed_for_current_local_use"] is False
    assert out["allowed_for_reference_scoring"] is False


def test_nd4_private_adaptation_and_doi_difference_are_not_blanket_exclusions():
    row, raw = record("http://creativecommons.org/licenses/by-nc-nd/4.0/")
    row["doi_matches_export"] = False
    out = decide_record(row, raw, POLICY)
    assert out["allowed_for_current_local_use"] is True
    assert "doi_difference_not_automatic_wrong_record" in out["flags"]


def test_prose_conflict_preserved_and_uri_controls():
    row, raw = record("http://creativecommons.org/licenses/by-sa/3.0/",
                      "CC Attribution - ShareAlike 3.0:\nnon-commercial purpose")
    out = decide_record(row, raw, POLICY)
    assert out["released_license_raw"] == raw["released_license_raw"]
    assert out["flags"] == ["released_prose_noncommercial_conflicts_with_authoritative_uri"]
    assert out["allowed_for_current_local_use"] is True


def test_raw_license_mutation_raises():
    row, raw = record()
    raw["released_license_raw"] += " edited"
    with pytest.raises(ValueError, match="hash mismatch"):
        decide_record(row, raw, POLICY)


@pytest.mark.parametrize("field,value", [("policy_version", POLICY_VERSION + "-unknown"),
                                       ("schema_version", 2)])
def test_policy_version_mismatch_rejected(field, value):
    policy = deepcopy(POLICY)
    policy[field] = value
    with pytest.raises(ValueError, match="version"):
        validate_policy(policy)


@pytest.mark.parametrize("value", ["true", 1, False])
def test_policy_scope_requires_exact_true_boolean(value):
    policy = deepcopy(POLICY)
    policy["scope"]["local_only"] = value
    with pytest.raises(ValueError, match="boolean"):
        validate_policy(policy)


def test_uri_normalization_preserves_version_port_and_rejects_lookalike():
    assert canonical_license_uri("http://creativecommons.org/licenses/by/2.0/be/deed.en") == (
        "https://creativecommons.org/licenses/by/2.0/be/")
    assert canonical_license_uri("https://creativecommons.org.evil/licenses/by/4.0/") is None


@pytest.mark.parametrize("decision", ["DENY", "Conditional", "conditional ", "allow",
                                      None, True, 1, [], {}])
def test_unknown_or_malformed_decisions_fail_before_any_permission(decision):
    policy = deepcopy(POLICY)
    policy["license_routes"]["https://creativecommons.org/licenses/by/3.0/"]["decision"] = decision
    row, raw = record()
    with pytest.raises(ValueError, match="Invalid license route or decision"):
        decide_record(row, raw, policy)


@pytest.mark.parametrize("route", [None, [], "conditional", {}, {"unknown": "conditional"}])
def test_malformed_route_objects_fail_closed(route):
    policy = deepcopy(POLICY)
    policy["license_routes"]["https://creativecommons.org/licenses/by/3.0/"] = route
    with pytest.raises(ValueError, match="Invalid license route or decision"):
        validate_policy(policy)


@pytest.mark.parametrize("routes", [None, [], "conditional", {}])
def test_malformed_route_table_fails_closed(routes):
    policy = deepcopy(POLICY)
    policy["license_routes"] = routes
    with pytest.raises(ValueError, match="nonempty mapping"):
        validate_policy(policy)
