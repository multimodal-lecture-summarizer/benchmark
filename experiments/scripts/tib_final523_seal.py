"""Seal the 523 eligible test IDs as the final cohort; source identity only, never a reference, never a generation.

The qualification ledgers carry record IDs, groups, word counts and hashes; no reference text is read here.
The seal is write-once: an existing sealed file is never replaced, and sealing does not authorize a run.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from experiments.scripts.tib_pilot_bundle import QUAL, ROOT, SEALED, sha, write

REGISTRY = ROOT / "experiments/registry/protocols/tib-final523-generation-261024-v1"
SEALED_FILE = "final_cohort.json"
EXPECTED_N = 523
QUOTAS = {"short": 182, "medium": 172, "long": 169}
STRATA = tuple(QUOTAS)


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def stratum(words, cutpoints):
    low, high = cutpoints
    return "short" if words <= low else "medium" if words <= high else "long"


def build_cohort(ledger, rights, development, dev_cohort, expected_n=EXPECTED_N, quotas=None):
    """Return the sealed cohort body from already-loaded ledgers; any identity or overlap problem raises."""
    quotas = QUOTAS if quotas is None else quotas
    test = [r for r in ledger if r["split"] == "test" and r["role_eligible"]]
    if len(test) != expected_n or len({r["record_id"] for r in test}) != expected_n:
        raise ValueError(f"Expected exactly {expected_n} distinct role-eligible test IDs, found {len(test)}")
    rights_by_id = {r["record_id"]: r for r in rights}
    for r in test:
        right = rights_by_id.get(r["record_id"])
        if right is None or not right["allowed_for_current_local_use"]:
            raise ValueError("Rights do not allow local use: " + r["record_id"])
        if right["source_normalized_sha256"] != r["source_normalized_sha256"]:
            raise ValueError("Source identity differs between ledgers: " + r["record_id"])
    groups = [r["group_id"] for r in test]
    dev_groups = {r["group_id"] for r in development["pilot"]} | {r["group_id"] for r in development["selection"]}
    other_groups = {r["group_id"] for r in ledger if r["split"] != "test"}
    if len(set(groups)) != len(groups):
        raise ValueError("Test groups are not one-to-one with test IDs")
    if set(groups) & (dev_groups | other_groups):
        raise ValueError("Test groups overlap development, train or valid groups")
    cutpoints = dev_cohort["source_word_cutpoints"]
    strata = {r["record_id"]: stratum(r["source_words"], cutpoints) for r in test}
    if dict(Counter(strata.values())) != quotas:
        raise ValueError(f"Recomputed strata {dict(Counter(strata.values()))} differ from {quotas}")
    return {"ids": [r["record_id"] for r in test], "groups": {r["record_id"]: r["group_id"] for r in test},
            "source_strata": strata, "quotas": quotas, "source_word_cutpoints": cutpoints}


def seal(registry=REGISTRY, qual=QUAL, sealed=SEALED):
    registry = Path(registry)
    target = registry / SEALED_FILE
    if target.exists():
        raise FileExistsError("Final cohort is already sealed; the seal is never rewritten")
    dev_cohort_path = sealed / "development_cohort.json"
    dev_cohort = json.loads(dev_cohort_path.read_text(encoding="utf-8"))
    ledger_path = qual / "qualified_cohort/qualification_ledger.jsonl"
    rights_path = qual / "source_use_ledger.jsonl"
    development_path = qual / "qualified_cohort/development_records.json"
    body = build_cohort(_jsonl(ledger_path), _jsonl(rights_path),
                        json.loads(development_path.read_text(encoding="utf-8")), dev_cohort)
    cohort = {"schema_version": 1, "state": "final_test_sealed_no_generation_authorized",
              "scope": "final523 test cohort; source identity only, no reference field read",
              "selected_ids": body["ids"], "selected_groups": body["groups"], "source_strata": body["source_strata"],
              "quotas": body["quotas"], "source_word_cutpoints": body["source_word_cutpoints"],
              "n": len(body["ids"]), "order": "qualification ledger order; frozen generation order, no replacement",
              "policy_sha256": dev_cohort["policy_sha256"], "development_cohort_sha256": sha(dev_cohort_path),
              "qualification_ledger_sha256": sha(ledger_path), "rights_ledger_sha256": sha(rights_path),
              "development_records_sha256": sha(development_path),
              "final_test_sealed": True, "generation_executed": False, "final_test_authorized": False,
              "selection_start_authorized": False}
    write(target, cohort)
    return {"path": str(target), "sha256": sha(target), "n": cohort["n"], "quotas": cohort["quotas"]}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(seal(), indent=2))


if __name__ == "__main__":
    main()
