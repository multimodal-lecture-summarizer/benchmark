"""Tier A/B admission rule applied to scored selection300 outputs; a pure function of frozen inputs.

Interpretation sources (nothing here adds a rule or moves a threshold):
- admission_rules_v2.json, ratified 2026-10-23, restating "phase-04 development and validation selection contract, items 4-10".
- analysis_declarations_261024_v1.json, the five interpretation clauses, hash-bound and declared before any score difference was viewed.

Contract reading, items 5-7:
- Tier A: with trial cap 0, A_f = {the family's profile}. C_f = the intersection of scored-success IDs over A_f, which is that
  profile's own scored-success set. The family is a representative when the profile meets the config floors (95% overall,
  90% per stratum) and C_f meets the common floors (90% / 80%, N >= 180, >= 20 per nonempty stratum). C_f is never used to
  rank families.
- F_between = the representative families, fixed from status/coverage alone before any score is aggregated. Fewer than 2 is
  no_selection. A family that is not a representative is not admitted; it does not by itself void the others.
- Lead-3 is the fixed control: same config floors, never in tier A. A control below its floors is no_selection.
- C_between = intersection of scored-success IDs over F_between and Lead-3, with the common floors again.
- A scoring run that does not cover every (profile, ID) cell is partial and is no_selection; nothing is evaluated on a prefix.

Gate order is fixed; gates 1-4 read scoring status only. ROUGE-L values are read from gate 5 on, and only when gates 1-4 pass.
"""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from experiments.scripts.tib_selection300_scoring_audit import LEAD3_NOTE, LEAD3_NOTE_IDS, is_success

PROTOCOLS = Path(__file__).resolve().parents[2] / "experiments/registry/protocols"
BINDING = PROTOCOLS / "tib-selection300-binding-261023-v1"
SCORING = PROTOCOLS / "tib-selection300-scoring-261024-v1"
ANALYSIS = PROTOCOLS / "tib-selection300-analysis-261024-v1"

EPSILON = 1e-12
STRATA = ("short", "medium", "long")
FAMILIES = ("lexrank", "bart", "led")
CONTROL = "lead3"
PROFILES = (CONTROL,) + FAMILIES
# Score-file profile name -> profile_id used in selection300_profiles_v2.json (config_priority_for_exact_ties).
PROFILE_IDS = {"lead3": "lead3", "lexrank": "lexrank", "bart": "bart-control", "led": "led-ngram3"}
RULES_ID = "tib-selection300-admission-v2"
LABELS = ("selected", "no_selection")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def priority_order(profiles_doc):
    """Candidate names in exact-tie order, from config_priority_for_exact_ties; a naming mismatch is an error."""
    by_candidate = {p["candidate_id"]: p["profile_id"] for p in profiles_doc["profiles"]}
    if by_candidate != PROFILE_IDS:
        raise ValueError(f"profile name mapping differs from the frozen one: {by_candidate}")
    order = profiles_doc["config_priority_for_exact_ties"]
    if sorted(order) != sorted(PROFILE_IDS.values()):
        raise ValueError(f"config priority does not list exactly the four profile ids: {order}")
    to_candidate = {v: k for k, v in PROFILE_IDS.items()}
    return [to_candidate[p] for p in order]


def check_bindings(rules, declarations):
    """The rules file must be the ratified one and match the thresholds the declarations interpret."""
    if rules.get("rules_id") != RULES_ID or rules.get("ratified") is not True:
        raise ValueError("admission rules are not the ratified v2")
    d = declarations["declarations"]
    if rules["tier_b"]["leader_margin_rouge_l_min"] != d["1_margin_comparison"]["margin"]:
        raise ValueError("margin in the rules differs from the declaration")
    if rules["tier_b"]["lead3_guard_delta_min"] != 0.0:
        raise ValueError("Lead-3 guard threshold differs from the declaration")
    if tuple(rules["families"]) != FAMILIES or rules["fixed_control"] != CONTROL:
        raise ValueError("families or control differ from the engine's")


def _cells(rows, contract):
    """{(profile, id): row}; unknown profiles/IDs, duplicates and stratum disagreements are input errors."""
    ids, strata = set(contract["selection_ids"]), contract["source_strata"]
    cells = {}
    for row in rows:
        key = (row["profile_id"], row["record_id"])
        if row["profile_id"] not in PROFILES or row["record_id"] not in ids:
            raise ValueError(f"row outside the frozen profiles/IDs: {key}")
        if key in cells:
            raise ValueError(f"duplicate row: {key}")
        if row["source_stratum"] != strata[row["record_id"]]:
            raise ValueError(f"stratum differs from the contract: {key}")
        cells[key] = row
    return cells


def _stratum_counts(id_set, strata):
    return {s: sum(strata[i] == s for i in id_set) for s in STRATA}


def _meets(n, total, minimum):
    # A stratum with no quota has nothing to cover.
    return total == 0 or n / total >= minimum - EPSILON


def _config_floors(success, contract, rules):
    cfg, quotas = rules["config_coverage"], contract["quotas"]
    total, counts = len(contract["selection_ids"]), _stratum_counts(success, contract["source_strata"])
    overall = _meets(len(success), total, cfg["overall_min"])
    per = {s: _meets(counts[s], quotas[s], cfg["per_stratum_min"]) for s in STRATA}
    return {"n": len(success), "by_stratum": counts, "overall_met": overall, "per_stratum_met": per,
            "floors_met": overall and all(per.values())}


def _common_floors(common, contract, rules):
    cm, quotas = rules["common_coverage"], contract["quotas"]
    total, counts = len(contract["selection_ids"]), _stratum_counts(common, contract["source_strata"])
    overall = _meets(len(common), total, cm["overall_min"])
    n_met = len(common) >= cm["common_n_min"]
    per_fraction = {s: _meets(counts[s], quotas[s], cm["per_stratum_min"]) for s in STRATA}
    per_n = {s: counts[s] >= cm["per_nonempty_stratum_n_min"] for s in STRATA if counts[s]}
    return {"n": len(common), "by_stratum": counts, "overall_met": overall, "common_n_met": n_met,
            "per_stratum_fraction_met": per_fraction, "per_nonempty_stratum_n_met": per_n,
            "floors_met": overall and n_met and all(per_fraction.values()) and all(per_n.values())}


def _mean(values):
    return math.fsum(values) / len(values)


def _delta(a, b, ids, scores):
    """Mean of per-ID paired ROUGE-L differences a - b over ids; IDs are sorted so row order cannot matter."""
    return _mean([scores[a][i] - scores[b][i] for i in sorted(ids)])


def _gate(name, passed, reason, **measures):
    return {"gate": name, "passed": bool(passed), "reason": reason, **measures}


def apply_rule(rows, contract, rules, declarations, profiles_doc):
    """Return the text-free outcome: label, selected profile (or None), and every gate with its measures."""
    check_bindings(rules, declarations)
    priority = priority_order(profiles_doc)
    cells = _cells(rows, contract)
    ids, strata = sorted(contract["selection_ids"]), contract["source_strata"]
    gates = []

    def finish(failed_at=None):
        return {"label": "no_selection", "selected_profile": None, "gates": gates, "stopped_at": failed_at}

    missing = [(p, i) for p in PROFILES for i in ids if (p, i) not in cells]
    gates.append(_gate("1_complete_scoring_run", not missing,
                       "every (profile, ID) cell present" if not missing else "partial run; never evaluated on a prefix",
                       missing_cells=len(missing)))
    if missing:
        return finish("1_complete_scoring_run")

    success = {p: {i for i in ids if is_success(cells[(p, i)])} for p in PROFILES}

    control = _config_floors(success[CONTROL], contract, rules)
    gates.append(_gate("2_control_config_floors", control["floors_met"],
                       "Lead-3 meets the config floors" if control["floors_met"] else "Lead-3 control below config floors",
                       profile=CONTROL, **control))
    if not control["floors_met"]:
        return finish("2_control_config_floors")

    tier_a, admitted = {}, []
    for family in FAMILIES:
        config = _config_floors(success[family], contract, rules)
        c_f = _common_floors(success[family], contract, rules)
        ok = config["floors_met"] and c_f["floors_met"]
        tier_a[family] = {"config_floors": config, "c_f_common_floors": c_f, "representative": ok}
        if ok:
            admitted.append(family)
    gates.append(_gate("3_tier_a_representatives", len(admitted) >= 2,
                       f"{len(admitted)} representative famil{'y' if len(admitted) == 1 else 'ies'}; F_between needs >= "
                       f"{rules['tier_b']['min_families']}", admitted=admitted, by_family=tier_a))
    if len(admitted) < rules["tier_b"]["min_families"]:
        return finish("3_tier_a_representatives")

    c_between = set.intersection(success[CONTROL], *(success[f] for f in admitted))
    common = _common_floors(c_between, contract, rules)
    gates.append(_gate("4_c_between_common_floors", common["floors_met"],
                       "C_between meets the common floors" if common["floors_met"] else "C_between below the common floors",
                       members_sha256=sha256_bytes("\n".join(sorted(c_between)).encode("utf-8")), **common))
    if not common["floors_met"]:
        return finish("4_c_between_common_floors")

    # Scores are read from here on; F_between and C_between are already frozen.
    scores = {p: {i: cells[(p, i)]["metrics"]["rougeL_f1"] for i in c_between} for p in admitted + [CONTROL]}
    means = {p: _mean(list(scores[p].values())) for p in scores}
    leader = min(admitted, key=lambda p: (-means[p], priority.index(p)))
    rivals = [p for p in admitted if p != leader]
    margin = rules["tier_b"]["leader_margin_rouge_l_min"]

    deltas = {r: _delta(leader, r, c_between, scores) for r in rivals}
    short = [r for r in rivals if deltas[r] < margin - EPSILON]
    gates.append(_gate("5_leader_margin", not short,
                       "leader beats every rival representative by the margin" if not short
                       else f"leader below the margin against {short}",
                       leader=leader, margin=margin, means=means, deltas_vs_rivals=deltas))

    considered = [s for s in STRATA if _stratum_counts(c_between, strata)[s] >= rules["common_coverage"]["per_nonempty_stratum_n_min"]]
    in_stratum = {s: {i for i in c_between if strata[i] == s} for s in considered}
    reversals, stratum_deltas = [], {}
    for r in rivals:
        stratum_deltas[r] = {s: _delta(leader, r, in_stratum[s], scores) for s in considered}
        for s, d in stratum_deltas[r].items():
            if (deltas[r] > 0 and d < 0) or (deltas[r] < 0 and d > 0):
                reversals.append(f"{r}|{s}")
    gates.append(_gate("6_stratum_direction", not reversals,
                       "no strict sign reversal in a considered stratum" if not reversals else f"reversal at {reversals}",
                       strata_considered=considered, deltas=stratum_deltas))

    guard_min = rules["tier_b"]["lead3_guard_delta_min"]
    guard = {"c_between": _delta(leader, CONTROL, c_between, scores)}
    guard.update({s: _delta(leader, CONTROL, in_stratum[s], scores) for s in considered})
    below = [k for k, v in guard.items() if v < guard_min - EPSILON]
    gates.append(_gate("7_lead3_guard", not below,
                       "leader not below Lead-3 on C_between and every considered stratum" if not below
                       else f"leader below Lead-3 at {below}", delta_vs_lead3=guard))

    ties = [r for r in rivals if means[r] == means[leader]]
    gates.append(_gate("8_exact_ties", True,
                       "no exact tie with the leader" if not ties
                       else f"exact tie with {ties} resolved by config priority then profile id (margin gate already decides)",
                       leader=leader, tied_with=ties, priority=priority))

    if all(g["passed"] for g in gates):
        return {"label": "selected", "selected_profile": leader, "selected_profile_id": PROFILE_IDS[leader],
                "gates": gates, "stopped_at": None}
    return finish(next(g["gate"] for g in gates if not g["passed"]))


VIEW_METRICS = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1")
VIEWS = ("S", "M", "L")


def view_table(view_rows):
    """Mean of each metric per profile x stratum x view over completed view rows; descriptive, never used to select."""
    table = {}
    for profile in PROFILES:
        for stratum in STRATA:
            group = [r for r in view_rows if r["profile_id"] == profile and r["source_stratum"] == stratum]
            for view in VIEWS:
                cell = [r["views"][view] for r in group if not r["views"][view]["failures"]]
                table[f"{profile}|{stratum}|{view}"] = {
                    "n": len(cell), **{m: (math.fsum(c["metrics"][m] for c in cell) / len(cell) if cell else None)
                                       for m in VIEW_METRICS}}
    return {"label": "descriptive, not used to select", "means": table}


def lead3_notes(rows):
    return [LEAD3_NOTE] if any(r["profile_id"] == CONTROL and r["record_id"] in LEAD3_NOTE_IDS and is_success(r)
                               for r in rows) else []


def engine_sha256():
    return sha256_file(__file__)


def load_inputs(declarations_path, rules_path, profiles_path, decisions_path, contract_path, outcome_path, metrics_path):
    """Load the frozen files and refuse any whose hash differs from the one the declarations bound."""
    declarations = _load(declarations_path)
    bound = declarations["bound_hashes"]
    expected = {"admission_rules_v2_sha256": rules_path, "selection300_profiles_v2_sha256": profiles_path,
                "decisions_261023_v1_sha256": decisions_path, "scoring_outcome_sha256": outcome_path,
                "scoring_contract_sha256": contract_path}
    for key, path in expected.items():
        if sha256_file(path) != bound[key]:
            raise ValueError(f"{Path(path).name} hash differs from the one bound in the declarations")
    outcome = _load(outcome_path)
    if outcome.get("audit_pass") is not True:
        raise ValueError("scoring audit did not pass")
    rows = [json.loads(line) for line in Path(metrics_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"declarations": declarations, "rules": _load(rules_path), "profiles_doc": _load(profiles_path),
            "contract": _load(contract_path), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path, help="extracted evidence/metrics.jsonl")
    parser.add_argument("--views", required=True, type=Path, help="extracted evidence/view_metrics.jsonl")
    parser.add_argument("--engine-sha256", required=True, help="hash recorded in the receipt; must equal this module's")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.engine_sha256 != engine_sha256():
        raise SystemExit("engine hash differs from the recorded one; refusing to run")
    if args.out.exists():
        raise SystemExit("outcome already exists; the rule is applied once and never re-run")
    inputs = load_inputs(ANALYSIS / "analysis_declarations_261024_v1.json", BINDING / "admission_rules_v2.json",
                         BINDING / "selection300_profiles_v2.json", BINDING / "decisions_261023_v1.json",
                         SCORING / "scoring_contract.json", SCORING / "selection300_scoring_outcome.json", args.metrics)
    result = apply_rule(inputs["rows"], inputs["contract"], inputs["rules"], inputs["declarations"], inputs["profiles_doc"])
    result.update({"schema_version": 1, "scope": "selection300 tier A/B rule applied once; text-free",
                   "engine_sha256": engine_sha256(), "metrics_sha256": sha256_file(args.metrics),
                   "declarations_sha256": sha256_file(ANALYSIS / "analysis_declarations_261024_v1.json"),
                   "bound_hashes": inputs["declarations"]["bound_hashes"], "labels": list(LABELS),
                   "notes": lead3_notes(inputs["rows"]),
                   "views_descriptive": view_table([json.loads(x) for x in args.views.read_text(encoding="utf-8").splitlines() if x.strip()])})
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt = {"engine_sha256": engine_sha256(), "result_sha256": sha256_file(args.out), "metrics_sha256": result["metrics_sha256"],
               "view_metrics_sha256": sha256_file(args.views), "declarations_sha256": result["declarations_sha256"],
               "run_at_utc": datetime.now(timezone.utc).isoformat(), "runs": 1}
    args.out.with_name("selection300_analysis_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": result["label"], "selected_profile": result["selected_profile"],
                      "stopped_at": result["stopped_at"]}))


if __name__ == "__main__":
    main()
