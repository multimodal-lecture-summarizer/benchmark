"""Join audited rights/references/groups, then seal development IDs only."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from experiments.scripts.tib_model_benchmark_sampling import select_development, stratum
from experiments.scripts.tib_model_benchmark_qualification_inputs import validate_receipts


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    result = {row["record_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate released IDs in input ledger")
    return result


def qualify_rows(metadata, rights, references, groups, old_ids):
    if not (set(metadata) == set(rights) == set(references) == set(groups)):
        raise ValueError("Input record ID frames differ")
    rows = []
    for record_id, record in metadata.items():
        permission, reference, group = rights[record_id], references[record_id], groups[record_id]
        for field in ("source_raw_sha256", "reference_raw_sha256"):
            if record[field] != permission[field] or record[field] != reference[field]:
                raise ValueError(f"Input text hash mismatch: {record_id}/{field}")
        if record["source_raw_sha256"] != group["source_raw_sha256"]:
            raise ValueError(f"Group source hash mismatch: {record_id}")
        if type(permission["allowed_for_reference_scoring"]) is not bool:
            raise ValueError("Rights gate requires a boolean")
        if type(record["structure_pass"]) is not bool or reference["reference_label"] not in {"A", "B", "C"}:
            raise ValueError("Invalid structure or reference decision")
        reasons = []
        if not record["structure_pass"]:
            reasons.append("empty_or_invalid_canonical_source")
        if reference["reference_label"] == "C":
            reasons.append("reference_C")
        if not permission["allowed_for_reference_scoring"]:
            reasons.append("source_or_reference_use_hold")
        if (record.get("language") or "").strip().casefold() not in {"en", "eng", "english"}:
            reasons.append("non_english_or_unknown_metadata")
        row = {k: v for k, v in record.items() if k not in {"quality_flags"}}
        row.update(group_id=group["group_id"], reference_label=reference["reference_label"],
                   source_use_status=permission["source_use_status"],
                   data_eligible=not reasons, qualification_reasons=reasons,
                   eda_exposed=True, role_eligible=False, exposure_reasons=[])
        rows.append(row)
    if old_ids - set(metadata):
        raise ValueError("Historical exposure IDs absent from pinned snapshot")
    tuned_groups = {groups[name]["group_id"] for name in old_ids}
    protected_test = {r["group_id"] for r in rows if r["data_eligible"] and r["split"] == "test" and r["group_id"] not in tuned_groups}
    protected_valid = {r["group_id"] for r in rows if r["data_eligible"] and r["split"] == "valid" and r["group_id"] not in tuned_groups | protected_test}
    for row in rows:
        if row["record_id"] in old_ids:
            row["exposure_reasons"].append("historical_120_or_9_pilot")
        elif row["group_id"] in tuned_groups:
            row["exposure_reasons"].append("linked_known_tuning_group")
        elif row["split"] != "test" and row["group_id"] in protected_test:
            row["exposure_reasons"].append("protected_native_test_group")
        elif row["split"] == "train" and row["group_id"] in protected_valid:
            row["exposure_reasons"].append("protected_native_validation_group")
        row["role_eligible"] = row["data_eligible"] and not row["exposure_reasons"]
        row["eligibility_status"] = ("eligible_flagged_B" if row["reference_label"] == "B" else "eligible") if row["role_eligible"] else "excluded_or_hold"
    return rows


def run(root: Path, registry: Path, old_manifest: Path):
    output = root / "qualified_cohort"
    if output.exists():
        raise ValueError("Qualified cohort output already exists; amendment must use a new version")
    for name in ("qualification_policy.json", "development_cohort.json"):
        if (registry / name).exists():
            raise ValueError(f"Existing qualification artifact must not be overwritten: {name}")
    required = [root / "eda/receipt.json", root / "source_group_summary.json",
                registry / "reference_review_validation_v2.json", root / "rights_validation_review_fix_receipt.json",
                root / "group_validation_review_fix_receipt.json"]
    for path in required:
        if not path.is_file():
            raise ValueError(f"Missing prerequisite receipt: {path}")
    validate_receipts(root, registry)
    group_summary = json.loads((root / "source_group_summary.json").read_text())
    if group_summary.get("status") != "completed":
        raise ValueError("Source grouping audit incomplete")
    if json.loads((registry / "reference_review_validation_v2.json").read_text())["status"] != "pass":
        raise ValueError("Targeted reference review evidence has not passed")
    paths = {"metadata": root / "eda/record_metadata.jsonl", "rights": root / "source_use_ledger.jsonl",
             "references": root / "reference_usability_ledger.jsonl", "groups": root / "source_group_ledger.jsonl"}
    inputs = {key: read_rows(path) for key, path in paths.items()}
    if len(inputs["metadata"]) != 9103:
        raise ValueError("Expected complete pinned frame")
    old = json.loads(old_manifest.read_text())
    old_ids = {row["id"].replace("/", ":") for row in old["selected"]} | {value.replace("/", ":") for value in old["pilot_excluded_ids"]}
    rows = qualify_rows(**inputs, old_ids=old_ids)
    train = sorted(r["source_words"] for r in rows if r["split"] == "train" and r["role_eligible"])
    if len(train) < 3:
        raise ValueError("No qualified development train frame for source cutpoints")
    cuts = [train[len(train) * k // 3 - 1] for k in (1, 2)]
    policy = {"schema_version": 1, "status": "frozen_before_selection", "seed": "tib-development-261019-v1",
              "source_word_cutpoints_train_tertiles": cuts,
              "sampling": "constrained_largest_remainder_source_length; hash order; pilot includes each-bin min/max",
              "pilot_n": 40, "selection_n": 300, "availability_fallback": 200,
              "group_role_policy": "pilot-group reservation excludes all linked remaining IDs from selection; never split group across roles",
              "primary_reference_labels": ["A", "B"], "eda_exposure_alone_excludes": False,
              "known_tuning_ids": sorted(old_ids), "input_sha256": {key: sha(path) for key, path in paths.items()},
              "prerequisite_sha256": {str(p): sha(p) for p in required}, "old_exposure_manifest_sha256": sha(old_manifest),
              "final_test_sealed": False}
    registry.mkdir(parents=True, exist_ok=True)
    policy_path = registry / "qualification_policy.json"
    with policy_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(policy, indent=2) + "\n")
    counts = {split: {"source": sum(r["split"] == split for r in rows),
                      "data_eligible": sum(r["split"] == split and r["data_eligible"] for r in rows),
                      "after_exposure": sum(r["split"] == split and r["role_eligible"] for r in rows),
                      "exposure_reasons": dict(Counter(reason for r in rows if r["split"] == split and r["data_eligible"] for reason in r["exposure_reasons"]))}
              for split in ("train", "valid", "test")}
    output.mkdir()
    with (output / "qualification_ledger.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "counts.json").write_text(json.dumps(counts, indent=2) + "\n")
    selected = select_development([r for r in rows if r["split"] == "valid" and r["role_eligible"]], cuts)
    selected_ids = {role: [r["record_id"] for r in selected[role]] for role in ("pilot", "selection")}
    selected_groups = {role: sorted({r["group_id"] for r in selected[role]}) for role in ("pilot", "selection")}
    cohort = {"schema_version": 1, "state": "development_ids_sealed_no_generation_authorized",
              "policy_sha256": sha(policy_path), "counts": counts, "selected_ids": selected_ids,
              "selected_groups": selected_groups, "pilot_n": 40, "selection_n": len(selected["selection"]),
              "pilot_quotas": selected["pilot_quotas"], "selection_quotas": selected["selection_quotas"],
              "selection_fallback": selected["selection_fallback"], "fallback_reason": selected["fallback_reason"],
              "staged_pilot_ids": selected["staged_pilot_ids"], "source_word_cutpoints": cuts,
              "final_test_sealed": False, "generation_executed": False,
              "blocked_runtime_gates": ["scorer_ready", "candidate_profiles", "T4_measured_capacity", "compute_storage_retry_budgets"]}
    with (registry / "development_cohort.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(cohort, indent=2) + "\n")
    (output / "development_records.json").write_text(json.dumps(selected, indent=2) + "\n")
    return cohort


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--old-manifest", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root, args.registry, args.old_manifest)
    print(json.dumps({"counts": result["counts"], "pilot_n": result["pilot_n"], "selection_n": result["selection_n"]}, indent=2))
