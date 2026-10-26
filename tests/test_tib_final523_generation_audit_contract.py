"""The generation audit reads what the real runtime writes: checked against the real selection300 evidence ZIP (same shapes)."""
import json
import zipfile

import pytest

from experiments.scripts import tib_final523_generation_audit as audit_module
from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_selection300_scorer_bundle import EVIDENCE_ZIP

pytestmark = pytest.mark.skipif(not EVIDENCE_ZIP.exists(), reason="real selection300 evidence ZIP not on this machine")

RECEIPT_KEYS = ("status", "summary", "new_generation_calls", "new_generation_wall_seconds", "total_wall_seconds")
SUMMARY_KEYS = ("denominator", "pending", "successful", "failed_or_interrupted")
IDENTITY_KEYS = ("candidate_id", "profile_sha256", "bundle_sha256", "allocation_sha256", "acceptance_policy_sha256")
LEDGER_KEYS = ("bundle_sha256", "allocation_sha256", "gpu_seconds", "candidate_runs", "session_runs", "allocation", "session_elapsed_wall_seconds")
SESSION_KEYS = ("status", "granted_wall_seconds", "accounted_wall_seconds")
RECORD_KEYS = ("record_id", "status", "source_sha256", "source_stratum", "origin", "quality", "automatic_retry", "events", "resources")


@pytest.fixture(scope="module")
def evidence():
    return zipfile.ZipFile(EVIDENCE_ZIP)


def test_receipts_identities_ledger_and_authorization_have_the_keys_the_audit_reads(evidence):
    for profile in audit_module.NEURAL + ("lead3", "lexrank"):
        receipt = json.loads(evidence.read(f"selection/{profile}/candidate_receipt.json"))
        assert not [k for k in RECEIPT_KEYS if k not in receipt] and not [k for k in SUMMARY_KEYS if k not in receipt["summary"]]
        identity = json.loads(evidence.read(f"selection/{profile}/run_identity.json"))
        assert not [k for k in IDENTITY_KEYS if k not in identity["payload"]] and digest(identity["payload"]) == identity["sha256"]
    ledger = json.loads(evidence.read("selection/resource_ledger.json"))
    assert not [k for k in LEDGER_KEYS if k not in ledger] and all(k in ledger["session_runs"][0] for k in ("status", "granted_wall_seconds"))
    assert ledger["candidate_runs"] and all({"candidate_id", "wall_seconds"} <= set(c) for c in ledger["candidate_runs"])
    assert "device_name" in json.loads(evidence.read("selection/preflight_receipt.json"))
    assert {"manifest_sha256", "authorized_by", "statement"} <= set(json.loads(evidence.read("selection/start_authorization.json")))
    assert "metrics_executed" in json.loads(evidence.read("selection/selection_summary.json"))


def test_real_record_envelopes_verify_and_carry_the_fields_the_audit_reads(evidence, tmp_path):
    names = [n for n in evidence.namelist() if n.startswith("selection/led/records/")][:40]
    for name in names:
        target = tmp_path / name.rsplit("/", 1)[1]
        target.write_bytes(evidence.read(name))
    records, corrupt, duplicates = audit_module.read_records(tmp_path)
    assert len(records) == len(names) and corrupt == duplicates == 0
    for payload in records.values():
        assert not [k for k in RECORD_KEYS if k not in payload]
        assert payload["status"] in ("completed", "completed_with_warning", "failed", "started")
        if payload["status"] in audit_module.FINISHED:
            assert {"delivered_words", "capped", "forced_word_boundary", "raw_words"} <= set(payload["result"]["delivery"])
            assert "warnings" in payload["validation"]["acceptance"]
    assert audit_module.forbidden_keys(list(records.values())) == set()
