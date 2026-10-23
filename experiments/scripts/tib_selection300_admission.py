"""Cap350 feasibility receipt, locked output policy v2 and the admission rules for the four-profile selection300.

Reads the pinned Pilot40 evidence only. Nothing is generated or scored, and no existing registry file changes.
Thresholds restate the pre-declared P4 selection contract; they are not new decisions.
"""
import argparse
import json
import statistics
import zipfile
from pathlib import Path

from experiments.scripts.tib_selection300_binding import (
    EVIDENCE_SHA256, EVIDENCE_ZIP, PROFILE_ORDER, REGISTRY, ROOT, sha256_file, write_json,
)

OLD_POLICY = ROOT / "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/output_policy.json"
ACCEPTANCE = ROOT / "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/development-decision-261019-2341/intermediate_acceptance_policy_v1.json"
COHORT = ROOT / "experiments/registry/datasets/tib-text-model-benchmark-v1/qualification-261019-1703/development_cohort.json"
WORD_CAP = 350
STRATA = ("short", "medium", "long")
# LexRank selects sentences up to the cap by design, so reaching it is behaviour, not truncation.
FILLS_TO_CAP_BY_DESIGN = {"lexrank"}


def _spread(values):
    values = sorted(values)
    p95 = values[min(len(values) - 1, max(0, -(-95 * len(values) // 100) - 1))]
    return {"n": len(values), "median": statistics.median(values), "p95_nearest_rank": p95, "max": values[-1]}


def build_cap_receipt(evidence_zip=EVIDENCE_ZIP, expected_sha=EVIDENCE_SHA256):
    if sha256_file(evidence_zip) != expected_sha:
        raise ValueError("Pilot40 evidence ZIP hash changed")
    cells, totals = {}, {}
    with zipfile.ZipFile(evidence_zip) as archive:
        for candidate in PROFILE_ORDER:
            records = json.loads(archive.read(f"pilot/{candidate}/candidate_receipt.json"))["records"]
            usable = [r for r in records.values() if r["status"] != "failed"]
            if not usable:
                raise ValueError(f"{candidate}: no usable outputs")
            warnings = {}
            for record in usable:
                for flag in record["validation"]["acceptance"]["warnings"]:
                    warnings[flag] = warnings.get(flag, 0) + 1
            totals[candidate] = {
                "usable": len(usable), "capped": sum(r["result"]["delivery"]["capped"] for r in usable),
                "forced_word_boundary": sum(r["result"]["delivery"]["forced_word_boundary"] for r in usable),
                "records_with_warnings": sum(bool(r["validation"]["acceptance"]["warnings"]) for r in usable),
                "warning_counts": warnings}
            for stratum in STRATA:
                group = [r["result"]["delivery"] for r in usable if r["source_stratum"] == stratum]
                if group:
                    cells[f"{candidate}|{stratum}"] = {
                        "raw_words": _spread([d["raw_words"] for d in group]),
                        "delivered_words": _spread([d["delivered_words"] for d in group]),
                        "capped": sum(d["capped"] for d in group),
                        "forced_word_boundary": sum(d["forced_word_boundary"] for d in group)}
    forced = sum(t["forced_word_boundary"] for t in totals.values())
    capped_other = sum(t["capped"] for c, t in totals.items() if c not in FILLS_TO_CAP_BY_DESIGN)
    return {"schema_version": 1, "scope": "cap350 feasibility from Pilot40 outputs; text-free",
            "pilot40_evidence_zip_sha256": expected_sha, "word_cap": WORD_CAP,
            "usable_outputs": sum(t["usable"] for t in totals.values()),
            "by_profile": totals, "by_profile_stratum": cells,
            "forced_word_boundary_total": forced, "capped_outside_by_design_total": capped_other,
            "fills_to_cap_by_design": sorted(FILLS_TO_CAP_BY_DESIGN),
            "cap_lock_allowed": forced == 0 and capped_other == 0,
            "claim_limit": "feasibility evidence on 11-15 outputs per profile and stratum, not a guarantee for selection300",
            "cap_is_maximum_not_generation_target": True, "references_used_for_cap": False,
            "derivation_source": "output_policy.json: eligible train p95 = 333 words, rounded up to a multiple of 25"}


def build_output_policy_v2(cap_receipt_sha256):
    old = json.loads(OLD_POLICY.read_text(encoding="utf-8"))
    return {"schema_version": 2, "policy_id": "tib-output-train-p95-350-v2",
            "state": "locked_before_selection", "derived_global_word_cap": WORD_CAP,
            "supersedes_state_of": {"file": OLD_POLICY.name, "sha256": sha256_file(OLD_POLICY),
                                    "previous_state": old["state"]},
            "cap_feasibility_receipt_sha256": cap_receipt_sha256,
            "selector": old["selector"], "sentence_splitter": old["sentence_splitter"],
            "eligible_train_n": old["eligible_train_n"], "p95_words": old["p95_words"],
            "validation_or_test_references_used_for_cap": False,
            "applies_to": list(PROFILE_ORDER), "scoring_text": old["scoring_text"],
            "cap_is_maximum_not_generation_target": True}


def build_admission_rules():
    """The pre-declared P4 contract specialised to K_models = 3 plus the fixed Lead-3 control."""
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    return {
        "schema_version": 1, "rules_id": "tib-selection300-admission-v1", "ratified": False,
        "ratification_pending": "decision D1 in plans/261023-1942-selection300-binding",
        "source_contract": "phase-04 development and validation selection contract, items 4-10",
        "validation_set": {"selection_n": len(cohort["selected_ids"]["selection"]),
                           "strata": list(STRATA), "quotas": cohort["selection_quotas"],
                           "cutpoints_words": cohort["source_word_cutpoints"]},
        "families": ["lexrank", "bart", "led"], "fixed_control": "lead3",
        "K_models": 3, "K_total": 4, "max_paired_contrasts": 6,
        "acceptance_policy": {"file": ACCEPTANCE.name, "sha256": sha256_file(ACCEPTANCE),
                              "successful_statuses": ["completed", "completed_with_warning"],
                              "failures_are_null_not_zero": True},
        "scored_success": "generation complete and ROUGE-L F1 finite; BERTScore secondary; SBERT diagnostic only, never reported or used to choose",
        "config_coverage": {"overall_min": 0.95, "per_stratum_min": 0.90,
                            "applies_to": ["lexrank", "bart", "led", "lead3 (fixed control, same floors)"]},
        "common_coverage": {"overall_min": 0.90, "per_stratum_min": 0.80, "common_n_min": 180,
                            "per_nonempty_stratum_n_min": 20},
        "tier_a": "one profile per family and trial cap 0, so A_f = {profile} and the representative is that profile",
        "tier_a_failure": "an empty A_f, or a C_f below the common floors, makes the family not representative; the profile is not swapped after seeing the family comparison",
        "f_between_frozen": "F_between is fixed from status, coverage and resource rules before any quality aggregation",
        "stratum_direction": "the sign of each delta must hold in every stratum above the floor; a reversal there is no_selection",
        "tier_b": {"min_families": 2, "common_set": "C_between = intersection of scored-success IDs of the admitted representatives and Lead-3",
                   "leader_margin_rouge_l_min": 0.01, "margin_scale": "absolute, 0-1",
                   "lead3_guard_delta_min": 0.0, "guard_scope": "C_between and strata above the floor",
                   "otherwise": "no_selection; no relabelling, no dropping rivals or hard IDs"},
        "ties": "exact tie by config priority, then stable profile ID; practical-small difference is no_selection",
        "config_priority": "selection300_profiles_v2.json config_priority_for_exact_ties",
        "resource_rule": {"partial_on_exhaustion": "report on the whole sealed V, never a completed prefix",
                          "automatic_retries": False, "source_order": "frozen"},
        "forbidden_after_scores": ["change representatives", "lower floors", "change membership", "open trials",
                                   "reselect on the test set"],
        "selection_start_authorized": False}


def build_all(out=REGISTRY):
    out = Path(out)
    receipt = build_cap_receipt()
    write_json(out / "cap350_feasibility_receipt.json", receipt)
    if not receipt["cap_lock_allowed"]:
        raise ValueError("Cap350 cannot be locked: forced cuts or non-design capping observed; user decision needed")
    write_json(out / "output_policy_v2.json", build_output_policy_v2(sha256_file(out / "cap350_feasibility_receipt.json")))
    write_json(out / "admission_rules_v1.json", build_admission_rules())
    return {n: sha256_file(out / n) for n in ("cap350_feasibility_receipt.json", "output_policy_v2.json", "admission_rules_v1.json")}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build_all(), indent=2))
