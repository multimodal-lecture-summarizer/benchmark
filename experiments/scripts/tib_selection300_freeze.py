"""Record the D1-D4 decisions, freeze the scorer identity and emit the selection300 readiness receipt.

Pure bookkeeping over existing artifacts: no model, no generation, no scoring. The receipt can never
authorize a start; `selection_start_authorized` is a constant False in every artifact written here.
"""
import argparse
import json
import zipfile
from pathlib import Path

from experiments.scripts import tib_selection300_admission as admission
from experiments.scripts import tib_selection300_binding as binding
from experiments.scripts.tib_selection300_binding import REGISTRY, ROOT, sha256_file, write_json

PROTOCOLS = ROOT / "experiments/registry/protocols"
SCORER_SPEC = PROTOCOLS / "tib-model-benchmark-p4-261019-1802/scorer_spec_v2.json"
P4B = PROTOCOLS / "tib-scorer-colab-runtime-261020-v1"
P4C_AUDIT = PROTOCOLS / "tib-p4-fresh-recovery-261020-v2/actual-colab-20261020T023840Z/audit.json"
P40_SCORING = PROTOCOLS / "tib-pilot40-scoring-261023-v1"
DECIDED_ON = "2026-10-23"
ALLOWED = {"D1": {"ratify_verbatim", "change_post_hoc"}, "D2": {"report_changing_views_only", "report_all_three_views"},
           "D3": {"exclude_minicheck", "include_minicheck"}, "D4": {"freeze_v2", "not_frozen"}}
# Only these answers leave the protocol buildable without reopening a budget or threshold decision.
BUILDABLE = {"D1": "ratify_verbatim", "D2": "report_all_three_views", "D3": "exclude_minicheck", "D4": "freeze_v2"}
OPEN_GATES = {
    "generation_bundle_for_300_ids": "no hash-bound bundle or notebook for the 300 selection IDs exists yet (tib_pilot_bundle.py is fixed to 40)",
    "t4_preflight_first_session": "actual T4, pins and quota probes pass only inside the first session",
    "selection_cohort_hash_bound_to_bundle": "development_cohort.json selection IDs must be hashed into the bundle once it exists",
    "drive_store_check_first_session": "persistent store write/readback is verified per session before long work",
}


def check_answers(answers):
    if set(answers) != set(ALLOWED) or any(answers[k] not in ALLOWED[k] for k in ALLOWED):
        raise ValueError("Answers must cover D1-D4 with allowed values")
    mismatched = [k for k, want in BUILDABLE.items() if answers[k] != want]
    if mismatched:
        raise ValueError("Answers differ from the encoded protocol; re-plan before binding: " + ",".join(mismatched))


def decision_record(answers):
    check_answers(answers)
    return {"schema_version": 1, "decided_by": "user", "decided_on": DECIDED_ON, "answers": answers,
            "post_hoc": {"D1": False, "reason": "thresholds ratified verbatim; declared before Pilot40 scores were seen"},
            "note_D2": "user chose to report all three views for every profile instead of the recommended changing-views-only policy",
            "selection_start_authorized": False}


def record_decisions(answers, out=REGISTRY):
    record = decision_record(answers)
    write_json(Path(out) / "decisions_261023_v1.json", record)
    return record


def build_view_policy(answers):
    """D2: report S/M/L for every profile; identical texts reuse the same scores and are still listed."""
    if answers["D2"] != "report_all_three_views":
        raise ValueError("Only the all-three-views policy is encoded; re-plan for other policies")
    return {"schema_version": 1, "policy_id": "tib-view-policy-v1", "budgets_words": {"S": 60, "M": 120, "L": 240},
            "primary_metric": "ROUGE-L F1 at the 350-word delivered view, unchanged",
            "secondary_views": "ROUGE-L and BERTScore at S, M and L for every profile, Holm over the three views",
            "identical_view_text": "scored once and reused; still listed per view so every profile has three rows",
            "reporting_caveat": "Lead-3 and BART produce S=L for most records (35/40 and 35/37 in Pilot40), so their view rows are nearly duplicates and the Holm family counts a view that cannot differ",
            "views_are_prefix_slices": "they measure the first N words, not the ability to write an N-word summary",
            "faithfulness_metric": "none in selection300/final523 (MiniCheck excluded by D3)",
            "selection_start_authorized": False}


def build_admission_v2(out=REGISTRY):
    v1 = Path(out) / "admission_rules_v1.json"
    rules = json.loads(v1.read_text(encoding="utf-8"))
    rules.update(rules_id="tib-selection300-admission-v2", ratified=True, ratified_on=DECIDED_ON,
                 supersedes={"file": v1.name, "sha256": sha256_file(v1)},
                 ratification_pending=None, decision_file="decisions_261023_v1.json")
    return rules


def _spec_and_code_drift():
    spec = json.loads(SCORER_SPEC.read_text(encoding="utf-8"))
    return spec, [name for name, expected in spec["code_sha256"].items() if sha256_file(ROOT / name) != expected]


def build_scorer_freeze(out=REGISTRY):
    spec, drift = _spec_and_code_drift()
    if drift:
        raise ValueError("Frozen scorer code changed: " + ", ".join(drift))
    outcome_path = P40_SCORING / "pilot40_scoring_outcome.json"
    outcome = json.loads(outcome_path.read_text(encoding="utf-8"))
    if not outcome["audit_pass"]:
        raise ValueError("Pilot40 scoring audit did not pass")
    evidence = ROOT / "research-data/tib-pilot40-scoring-261023-v1/results/tib-pilot40-scoring-evidence-20261023T123512Z.zip"
    if sha256_file(evidence) != outcome["evidence_zip_sha256"]:
        raise ValueError("Pilot40 scoring evidence ZIP changed")
    with zipfile.ZipFile(evidence) as archive:
        receipt = json.loads(archive.read("evidence/scorer_pilot40_receipt.json"))
    bound = receipt["binding"]
    # The Pilot40 receipt must have run exactly the frozen spec and this registry's amendment.
    if bound["frozen_spec_sha256"] != sha256_file(SCORER_SPEC):
        raise ValueError("Pilot40 scoring ran a different scorer spec than the frozen one")
    if bound["runtime_amendment_sha256"] != sha256_file(P40_SCORING / "runtime_amendment.json"):
        raise ValueError("Pilot40 scoring ran a different runtime amendment than the registered one")
    current = json.loads((P4B / "current_scorer_evidence.json").read_text(encoding="utf-8"))
    if not (current["scorer_ready"] and sha256_file(P4B / current["actual_receipt"]) == current["actual_receipt_sha256"]):
        raise ValueError("P4b actual receipt missing or changed")
    if json.loads(P4C_AUDIT.read_text(encoding="utf-8")).get("status") != "PASS":
        raise ValueError("P4c recovery audit is not PASS")
    return {
        "schema_version": 1, "freeze_id": "tib-scorer-v2-freeze-261023", "frozen_on": DECIDED_ON,
        "scope": "selection300 and final523", "scorer_spec": {"file": SCORER_SPEC.name, "sha256": sha256_file(SCORER_SPEC)},
        "code_sha256": spec["code_sha256"],
        "runtime_amendments": {"p4b_sha256": sha256_file(P4B / "runtime_amendment.json"),
                               "pilot40_scoring_sha256": bound["runtime_amendment_sha256"],
                               "note": "the Pilot40 scoring amendment is a separate file that carries the same pins as P4b"},
        "requirements_sha256": sha256_file(P40_SCORING / "requirements-colab-t4.txt"),
        "receipts": {"p4b_actual_scorer_ready_sha256": current["actual_receipt_sha256"],
                     "p4c_recovery_audit_sha256": sha256_file(P4C_AUDIT),
                     "pilot40_scoring_outcome_sha256": sha256_file(outcome_path),
                     "pilot40_scoring_evidence_zip_sha256": outcome["evidence_zip_sha256"]},
        "asset_manifests_sha256": bound["asset_manifests_sha256"],
        "pilot40_measured_scoring_seconds_by_stratum": outcome["timing_by_stratum_seconds"],
        "metrics_reported": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
        "metrics_computed_not_reported": ["source_sentence_similarity_v1"],
        "sbert_note": "computed because scorer v2 is kept unchanged; never reported or used to choose (decisions 22/10 and 23/10)",
        "idf": False, "dtype": "float32", "word_cap": admission.WORD_CAP, "selection_start_authorized": False}


def _gate(passed, detail):
    return {"status": "PASS" if passed else "OPEN", "detail": detail}


def build_readiness_receipt(out=REGISTRY):
    """Gates re-verify hashes and consistency; presence of a file alone never passes a gate."""
    out = Path(out)

    def load(name):
        path = out / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def sha(name):
        return sha256_file(out / name) if (out / name).exists() else None

    profiles, cap, policy = load("selection300_profiles_v2.json"), load("cap350_feasibility_receipt.json"), load("output_policy_v2.json")
    rules, decisions = load("admission_rules_v2.json"), load("decisions_261023_v1.json")
    views, freeze = load("view_policy_v1.json"), load("scorer_freeze_receipt.json")
    outcome = json.loads(binding.SCORING_OUTCOME.read_text(encoding="utf-8"))
    answers = (decisions or {}).get("answers", {})
    profile_sha = sha("selection300_profiles_v2.json")
    alloc_ok = profiles is not None
    for stage in binding.STAGES:
        data = load(f"compute_budget_{stage}.json")
        try:
            binding.validate_allocation(data, outcome)
            alloc_ok &= data["profile_list_sha256"] == profile_sha
        except (ValueError, KeyError, TypeError, AttributeError):
            alloc_ok = False
    scorer_ok = False
    if freeze and answers.get("D4") == "freeze_v2":
        spec, drift = _spec_and_code_drift()
        scorer_ok = (not drift and freeze["code_sha256"] == spec["code_sha256"]
                     and freeze["scorer_spec"]["sha256"] == sha256_file(SCORER_SPEC)
                     and freeze["runtime_amendments"]["p4b_sha256"] == sha256_file(P4B / "runtime_amendment.json")
                     and freeze["runtime_amendments"]["pilot40_scoring_sha256"] == sha256_file(P40_SCORING / "runtime_amendment.json")
                     and freeze["receipts"]["pilot40_scoring_outcome_sha256"] == sha256_file(P40_SCORING / "pilot40_scoring_outcome.json")
                     and freeze["selection_start_authorized"] is False)
    gates = {
        "profile_list_v2": _gate(bool(profiles) and [p["candidate_id"] for p in profiles["profiles"]] == list(binding.PROFILE_ORDER)
                                 and "qwen3" in profiles["excluded"] and all(p.get("profile_content_rehashed") for p in profiles["profiles"]),
                                 "four profiles bound to Pilot40 run identities, profile content re-hashed"),
        "allocations_selection300_final523": _gate(alloc_ok, "approved ceilings validated against the measured projection and the profile list hash"),
        "cap350_locked": _gate(bool(cap and policy) and cap["cap_lock_allowed"] and policy["state"] == "locked_before_selection"
                               and policy["cap_feasibility_receipt_sha256"] == sha("cap350_feasibility_receipt.json")
                               and policy["supersedes_state_of"]["sha256"] == sha256_file(admission.OLD_POLICY),
                               "no forced cuts and no non-design capping in Pilot40"),
        "admission_rules_ratified": _gate(bool(rules) and rules["ratified"] is True and answers.get("D1") == "ratify_verbatim"
                                          and rules["supersedes"]["sha256"] == sha("admission_rules_v1.json"),
                                          "D1, v2 matches current v1"),
        "view_policy": _gate(bool(views) and answers.get("D2") == "report_all_three_views"
                             and views["policy_id"] == "tib-view-policy-v1", "D2"),
        "minicheck_scope": _gate(answers.get("D3") == "exclude_minicheck", "D3 excluded from budget"),
        "scorer_frozen": _gate(scorer_ok, "D4 scorer v2 identity re-verified against files on disk"),
    }
    gates.update({name: _gate(False, reason) for name, reason in OPEN_GATES.items()})
    blocking = [name for name, gate in gates.items() if gate["status"] != "PASS"]
    return {"schema_version": 1, "receipt_id": "tib-selection300-readiness-261023", "gates": gates,
            "binding_gates_pass": all(g["status"] == "PASS" for n, g in gates.items() if n not in OPEN_GATES),
            "blocking_open_gates": blocking, "selection_start_authorized": False,
            "note": "This receipt records bound protocol artifacts only. Starting selection300 needs the generation bundle plan and an explicit user go-ahead."}


def build_all(answers, out=REGISTRY):
    """Build every artifact in memory first; a failure leaves no partial decision and no stale receipt."""
    out = Path(out)
    decisions = decision_record(answers)
    view_policy = build_view_policy(answers)
    freeze = build_scorer_freeze(out)
    stale = out / "selection300_readiness_receipt.json"
    if stale.exists():
        stale.unlink()
    write_json(out / "decisions_261023_v1.json", decisions)
    write_json(out / "view_policy_v1.json", view_policy)
    write_json(out / "admission_rules_v2.json", build_admission_v2(out))
    write_json(out / "scorer_freeze_receipt.json", freeze)
    receipt = build_readiness_receipt(out)
    write_json(stale, receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ALLOWED:
        parser.add_argument("--" + key.lower(), required=True, choices=sorted(ALLOWED[key]))
    args = parser.parse_args()
    result = build_all({key: getattr(args, key.lower()) for key in ALLOWED})
    print(json.dumps({"binding_gates_pass": result["binding_gates_pass"],
                      "blocking_open_gates": result["blocking_open_gates"]}, indent=2))
