"""Selection300 source-only bundle validation and the start-authorization check; no metric inputs.

Mirrors tib_pilot_validation for the 300-source, four-profile stage. The neural/CPU output validators are
reused unchanged. The bundle contract (not this module) names the sources, strata and locked artifacts, and
this module refuses anything that deviates from the approved shape.
"""
import hashlib
import json
from pathlib import Path

from .tib_benchmark_acceptance import ACCEPTANCE_POLICY
from . import tib_benchmark_acceptance as classifier_module
from . import tib_benchmark_generation_telemetry as diagnostic_module
from .tib_benchmark_checkpoint import digest
from .tib_p4_generation_recovery import safe_file, sha
from .tib_pilot_resources import require
from .tib_pilot_validation import source_only, validate_cpu, validate_neural  # noqa: F401  re-exported

SELECTION_N = 300
QUOTAS = {"short": 100, "medium": 90, "long": 110}
CANDIDATES = ["lead3", "lexrank", "bart", "led"]
PREFERRED = {"bart": "bart-control", "led": "led-ngram3"}
MANIFEST = "selection_manifest.json"
LOCKED_DIR = "locked"
MANDATORY = {"selection_contract.json", "selection_sources.jsonl", "acceptance_policy.json", "node_forecast.json",
             "selection_allocation.json", "actual_recovery_receipt.json", "actual_scorer_ready_receipt.json"}
AUTHORIZATION_FIELDS = {"manifest_sha256", "readiness_receipt_v2_sha256", "authorized_by", "authorized_on", "statement"}


def validate_bundle(bundle):
    bundle = Path(bundle)
    manifest = json.loads((bundle / MANIFEST).read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        require(sha(safe_file(bundle, name)) == expected, "Selection bundle hash mismatch: " + name)
    require(MANDATORY <= set(manifest["files"]), "Missing bound selection dependency")
    contract = json.loads((bundle / "selection_contract.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (bundle / "selection_sources.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = contract["selection_ids"]
    require(len(ids) == len(set(ids)) == len(rows) == SELECTION_N and [r["record_id"] for r in rows] == ids,
            f"Exactly {SELECTION_N} sealed ordered selection sources required")
    require(contract["quotas"] == QUOTAS and {s: sum(v == s for v in contract["source_strata"].values())
                                              for s in QUOTAS} == QUOTAS, "Sealed 100/90/110 strata required")
    require(contract["candidate_order"] == CANDIDATES and contract["word_cap"] == 350
            and [p["candidate_id"] for p in contract["profiles"]] == CANDIDATES, "Exactly four fixed profiles/cap350")
    require(contract["staged_ids"] == [] and "qwen3" not in json.dumps(contract["profiles"]).lower(),
            "No historical import and no Qwen3 in the selection bundle")
    require(not set(ids) & set(contract["excluded_pilot_ids"]) and len(contract["excluded_pilot_ids"]) == 40,
            "Selection must be disjoint from Pilot40")
    require(contract["selection_authorized"] is False and contract["final_test_authorized"] is False
            and contract["expected_cells"] == SELECTION_N * len(CANDIDATES), "Bundle must not self-authorize")
    for row in rows:
        source_only(row)
        required = {"record_id", "source_normalized", "source_normalized_sha256", "source_stratum", "attribution"}
        require(required <= set(row) <= required | {"source_words"}, "Unexpected source schema")
        if "source_words" in row:
            require(type(row["source_words"]) is int and row["source_words"] == len(row["source_normalized"].split()),
                    "Source word count mismatch")
        require(row["source_normalized"] and hashlib.sha256(row["source_normalized"].encode()).hexdigest()
                == row["source_normalized_sha256"] and contract["source_strata"][row["record_id"]] == row["source_stratum"],
                "Source/stratum binding mismatch")
        require(not row["record_id"].startswith("test:") and row["record_id"] not in contract["excluded_pilot_ids"],
                "Final-test or Pilot40 ID forbidden")
    for name, expected in contract["locked_artifacts"].items():
        require(sha(safe_file(bundle, f"{LOCKED_DIR}/{name}")) == expected, "Locked artifact mismatch: " + name)
    allocation = json.loads((bundle / "selection_allocation.json").read_text(encoding="utf-8"))
    require(digest(allocation) == contract["allocation_sha256"] and allocation["stage"] == "selection300"
            and allocation["selection_start_authorized"] is False, "Allocation binding mismatch")
    policy = json.loads((bundle / "acceptance_policy.json").read_text(encoding="utf-8"))
    require(all(policy.get(k) == v for k, v in ACCEPTANCE_POLICY.items())
            and sha(bundle / "acceptance_policy.json") == contract["acceptance_policy_sha256"],
            "Frozen acceptance policy mismatch")
    for prefix in ("classifier", "diagnostic_rules"):
        name, expected = policy[prefix + "_path"], policy[prefix + "_sha256"]
        require(name in manifest["files"] and sha(safe_file(bundle, name)) == expected,
                "Frozen acceptance classifier/diagnostic hash mismatch")
        loaded = classifier_module if prefix == "classifier" else diagnostic_module
        require(sha(loaded.__file__) == expected, "Loaded acceptance classifier/diagnostic differs")
    original = bundle / "original_generation"
    require(sha(original / "bundle_manifest.json") == contract["original_bundle_manifest_sha256"], "Frozen bundle identity")
    for name, expected in json.loads((original / "bundle_manifest.json").read_text(encoding="utf-8"))["files"].items():
        require(sha(safe_file(original, name)) == expected, "Frozen generation bytes mismatch")
    registry = json.loads((original / "development_trials.json").read_text(encoding="utf-8"))
    cpu_profiles = {p["candidate_id"]: p for p in json.loads(
        (original / "candidate_profiles.json").read_text(encoding="utf-8"))["pipelines"]}
    for profile in contract["profiles"]:
        require(digest(profile["profile"]) == profile["profile_sha256"], "Selection profile digest mismatch")
        if profile["candidate_id"] in PREFERRED:
            trial = next(t for t in registry["trials"] if t["trial_id"] == PREFERRED[profile["candidate_id"]])
            require(profile["profile_id"] == trial["trial_id"] and profile["profile"] == trial["profile"],
                    "Frozen neural profile changed")
        else:
            require(profile["profile"] == cpu_profiles[profile["candidate_id"]], "Frozen CPU profile changed")
    forecast = json.loads((bundle / "node_forecast.json").read_text(encoding="utf-8"))
    require(set(forecast["stage_seconds"]) == set(PREFERRED) and set(forecast["load_seconds"]) == set(PREFERRED)
            and all(v > 0 for s in forecast["stage_seconds"].values() for v in s.values()),
            "Node forecast must cover every neural profile and stage")
    recovered = json.loads((bundle / "actual_recovery_receipt.json").read_text(encoding="utf-8"))
    scorer = json.loads((bundle / "actual_scorer_ready_receipt.json").read_text(encoding="utf-8"))
    require(recovered.get("status") == "PASS" and recovered.get("cross_session_recovery_verified") is True
            and recovered.get("new_generation_calls") == recovered.get("new_metric_calls") == 0,
            "Actual recovery gate missing")
    require(scorer.get("status") == "PASS" and not scorer.get("test_only", False), "Actual scorer-ready gate missing")
    return contract, rows, sha(bundle / MANIFEST)


def check_authorization(authorization, manifest_sha256):
    """The only way to start: a user authorization bound to this exact bundle. Never created here."""
    require(isinstance(authorization, dict) and AUTHORIZATION_FIELDS <= set(authorization),
            "REQUIRED_NO_START: start authorization missing or incomplete")
    require(authorization["authorized_by"] == "user" and str(authorization["statement"]).strip(),
            "Authorization must record the user's own statement")
    require(authorization["manifest_sha256"] == manifest_sha256, "Authorization is bound to a different bundle")
    require(isinstance(authorization["readiness_receipt_v2_sha256"], str)
            and len(authorization["readiness_receipt_v2_sha256"]) == 64, "Authorization lacks the readiness receipt hash")
    return authorization
