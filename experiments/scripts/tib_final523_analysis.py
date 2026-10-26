"""Final523 confirmatory analysis: a pure function of frozen inputs, applied once, text-free.

Authority: analysis_declarations_final523_261024_v1.json (declared before any final523 score; nothing here adds a rule).
The choice (LED ngram3) is already locked at selection300, so this only asks whether its advantage replicates on the
sealed 523 test IDs. It never selects, swaps or re-ranks a profile.

Gate order is fixed; gates 1-3 read scoring status only. Scores are read from gate 4 on, and only when gates 1-3 pass.
  1 complete scoring run (every profile x ID cell present)   -> else not_evaluable
  2 config floors for all four profiles                      -> else not_evaluable
  3 C_final and its common floors                            -> else not_evaluable
  4 confirmatory family: led-bart and led-lexrank 97.5% bootstrap lower bounds > 0 and mean(led-lead3) >= 0
Everything after the label (strata, other pairs, BERTScore, S/M/L views, margin flags) is descriptive.
"""
import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from experiments.scripts import tib_selection300_analysis as base
from experiments.scripts.tib_selection300_scoring_audit import is_success

PROTOCOLS = base.PROTOCOLS
ANALYSIS = PROTOCOLS / "tib-final523-analysis-261024-v1"
SCORING = PROTOCOLS / "tib-final523-scoring-261024-v1"
DECLARATION = ANALYSIS / "analysis_declarations_final523_261024_v1.json"
DECLARATION_RECEIPT = ANALYSIS / "final523_analysis_declaration_receipt.json"
RESULT_NAME = "final523_analysis_result.json"

EPSILON = base.EPSILON
STRATA = base.STRATA
PROFILES = base.PROFILES
LEADER, CONTROL, RIVALS = "led", "lead3", ("bart", "lexrank")
CONTRASTS = tuple((LEADER, rival) for rival in RIVALS)
LABELS = ("confirmed", "not_confirmed", "not_evaluable")
SEED = 20261024
RESAMPLES = 10000
CONFIRM_LEVEL = 0.975  # two-sided, Bonferroni over the two contrasts
VIEWS = base.VIEWS
VIEW_METRICS = ("rougeL_f1", "bertscore_f1")
PRACTICAL_MARGIN = 0.01
DIAGNOSTIC_PER_STRATUM = 12


def sha256_file(path):
    return base.sha256_file(path)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _gate(name, passed, reason, **measures):
    return base._gate(name, passed, reason, **measures)


def check_declaration(declaration):
    """The declaration must be the pinned one: same leader, rivals, control, seed and level as the engine's."""
    if declaration.get("declaration_id") != "tib-final523-analysis-declarations-261024-v1" or declaration.get("post_hoc"):
        raise ValueError("not the pre-declared final523 analysis")
    profiles = declaration["profiles"]
    if (profiles["leader"], tuple(profiles["rivals"]), profiles["control"]) != (LEADER, RIVALS, CONTROL):
        raise ValueError("leader, rivals or control differ from the declaration")
    if profiles["candidate_to_profile_id"] != base.PROFILE_IDS:
        raise ValueError("profile name mapping differs from the frozen one")
    family = declaration["declarations"]["4_confirmatory_family"]["inference"]
    if "10000 resamples" not in family or f"seed {SEED}" not in family:
        raise ValueError("resample count or seed differ from the declaration")


# --- statistics ------------------------------------------------------------------------------------------------

def paired(scores, a, b, ids):
    """{stratum: [a-b per ID, sorted by ID]}; needs the stratum of every ID, passed through ids = {id: stratum}."""
    by = {s: [] for s in STRATA}
    for i in sorted(ids):
        by[ids[i]].append(scores[a][i] - scores[b][i])
    return by


def overall_mean(by_stratum):
    return base._mean([v for s in STRATA for v in by_stratum[s]])


def bootstrap(by_stratum, resamples=RESAMPLES, seed=SEED, level=CONFIRM_LEVEL):
    """Stratified percentile bootstrap of the overall mean difference.

    IDs are resampled with replacement inside each stratum (the quotas stay fixed), nearest-rank percentiles.
    Returns the interval and a two-sided bootstrap p-value of 'difference = 0' (add-one smoothed).
    """
    members = {s: v for s, v in by_stratum.items() if v}
    total = sum(len(v) for v in members.values())
    rng = random.Random(seed)
    sums = [0.0] * resamples
    for s in STRATA:
        if s not in members:
            continue
        values, n = members[s], len(members[s])
        for b in range(resamples):
            sums[b] += math.fsum(rng.choices(values, k=n))
    means = sorted(x / total for x in sums)
    tail = (1.0 - level) / 2.0
    low = means[max(0, math.ceil(tail * resamples) - 1)]
    high = means[min(resamples - 1, math.ceil((1.0 - tail) * resamples) - 1)]
    at_most_zero = sum(m <= 0.0 for m in means)
    at_least_zero = sum(m >= 0.0 for m in means)
    p = min(1.0, 2.0 * min(at_most_zero + 1, at_least_zero + 1) / (resamples + 1))
    return {"low": low, "high": high, "p_two_sided": p}


def holm(p_values):
    """Holm-adjusted p-values in the input order."""
    order = sorted(range(len(p_values)), key=lambda k: p_values[k])
    adjusted, running = [None] * len(p_values), 0.0
    for rank, k in enumerate(order):
        running = max(running, min(1.0, (len(p_values) - rank) * p_values[k]))
        adjusted[k] = running
    return adjusted


def _summary(by_stratum, resamples, level):
    n = sum(len(v) for v in by_stratum.values())
    if n == 0:
        return {"n": 0, "mean": None, "low": None, "high": None, "p_two_sided": None}
    return {"n": n, "mean": overall_mean(by_stratum), **bootstrap(by_stratum, resamples, level=level)}


# --- gates and result ----------------------------------------------------------------------------------------

def _score_table(rows, ids):
    """{profile: {id: rougeL}} over scored-success cells."""
    table = {p: {} for p in PROFILES}
    for row in rows:
        if row["record_id"] in ids and is_success(row):
            table[row["profile_id"]][row["record_id"]] = row["metrics"]["rougeL_f1"]
    return table


def apply_rule(rows, view_rows, contract, rules, declaration, resamples=RESAMPLES):
    check_declaration(declaration)
    _check_rules(rules)
    cells = base._cells(rows, contract)
    strata = contract["source_strata"]
    gates = []

    expected = len(PROFILES) * len(contract["selection_ids"])
    complete = len(cells) == expected
    gates.append(_gate("1_complete_run", complete, "every profile x ID cell present" if complete
                       else f"partial scoring run: {len(cells)} of {expected} cells", cells=len(cells), expected=expected))
    if not complete:
        return _stop(gates, "1_complete_run")

    success = {p: {i for i in contract["selection_ids"] if is_success(cells[(p, i)])} for p in PROFILES}
    floors = {p: base._config_floors(success[p], contract, rules) for p in PROFILES}
    ok2 = all(f["floors_met"] for f in floors.values())
    gates.append(_gate("2_config_floors", ok2, "all four profiles meet the config floors" if ok2
                       else "a profile misses a config floor", floors=floors))
    if not ok2:
        return _stop(gates, "2_config_floors")

    common = set.intersection(*success.values())
    common_floors = base._common_floors(common, contract, rules)
    gates.append(_gate("3_common_floors", common_floors["floors_met"],
                       "C_final meets the common floors" if common_floors["floors_met"] else "C_final misses a common floor",
                       common=common_floors))
    if not common_floors["floors_met"]:
        return _stop(gates, "3_common_floors")

    ids = {i: strata[i] for i in common}
    scores = _score_table(rows, set(common))
    level = CONFIRM_LEVEL
    contrasts = {}
    for a, b in CONTRASTS:
        summary = _summary(paired(scores, a, b, ids), resamples, level)
        contrasts[f"{a}-{b}"] = {**summary, "interval_level": level, "lower_bound_above_zero": summary["low"] > 0.0,
                                 "practical_margin_met": summary["mean"] >= PRACTICAL_MARGIN - EPSILON}
    guard_mean = base._delta(LEADER, CONTROL, common, scores)
    guard_ok = guard_mean >= -EPSILON
    confirmed = all(c["lower_bound_above_zero"] for c in contrasts.values()) and guard_ok
    gates.append(_gate("4_confirmatory_family", confirmed,
                       "both lower bounds > 0 and the Lead-3 guard holds" if confirmed else "criterion not met",
                       contrasts=contrasts, lead3_guard={"mean_led_minus_lead3": guard_mean, "met": guard_ok}))

    result = {"label": "confirmed" if confirmed else "not_confirmed", "stopped_at": None, "gates": gates,
              "leader": base.PROFILE_IDS[LEADER], "c_final_n": len(common),
              "descriptive": _descriptive(rows, view_rows, contract, cells, success, common, ids, scores, resamples)}
    return result


def _check_rules(rules):
    """The floors come from the ratified admission rules; refuse any other rules file."""
    if rules.get("rules_id") != base.RULES_ID or rules.get("ratified") is not True:
        raise ValueError("admission rules are not the ratified v2")
    if tuple(rules["families"]) != base.FAMILIES or rules["fixed_control"] != CONTROL:
        raise ValueError("families or control differ from the engine's")


def _stop(gates, name):
    last = gates[-1]
    return {"label": "not_evaluable", "stopped_at": name, "gates": gates, "leader": base.PROFILE_IDS[LEADER],
            "c_final_n": None, "descriptive": {"partial": True, "reason": last["reason"]}}


def _descriptive(rows, view_rows, contract, cells, success, common, ids, scores, resamples):
    """Nothing here gates the label; every contrast carries its interval."""
    strata = contract["source_strata"]
    out = {}
    # strata: the same interval method, one stratum at a time; reversals are listed only
    per_stratum = {}
    for a, b in CONTRASTS:
        key = f"{a}-{b}"
        overall_sign = _sign(overall_mean(paired(scores, a, b, ids)))
        per_stratum[key] = {}
        for s in STRATA:
            members = {i: s for i in ids if ids[i] == s}
            by = paired(scores, a, b, members)
            summary = _summary(by, resamples, CONFIRM_LEVEL)
            summary["reversal_against_overall"] = bool(summary["n"]) and overall_sign * _sign(summary["mean"]) < 0
            per_stratum[key][s] = summary
    out["strata"] = per_stratum
    # remaining pairs, exploratory, unadjusted 95% intervals
    exploratory = {}
    pairs = [(x, y) for k, x in enumerate(PROFILES) for y in PROFILES[k + 1:]]
    for a, b in pairs:
        if (a, b) in CONTRASTS or (b, a) in CONTRASTS:
            continue
        both = {i: strata[i] for i in success[a] & success[b]}
        exploratory[f"{a}-{b}"] = {"label": "exploratory, unadjusted 95% interval",
                                   **_summary(paired(_score_table(rows, set(both)), a, b, both), resamples, 0.95)}
    out["other_pairs"] = exploratory
    # sensitivity: each confirmatory contrast on the IDs where just its two profiles succeeded
    sensitivity = {}
    for a, b in CONTRASTS:
        both = {i: strata[i] for i in success[a] & success[b]}
        by = paired(_score_table(rows, set(both)), a, b, both)
        sensitivity[f"{a}-{b}"] = {"n": len(both), "mean": overall_mean(by), "missing_vs_c_final": len(both) - len(common)}
    out["pairwise_complete_sensitivity"] = sensitivity
    out["missing_cells"] = {p: {s: sum(1 for i in contract["selection_ids"] if strata[i] == s and i not in success[p])
                                for s in STRATA} for p in PROFILES}
    out["bertscore_delivered"] = _bertscore(rows, ids, resamples)
    out["views"] = _views(view_rows, common, strata, resamples)
    return out


def _sign(x):
    return (x > 0) - (x < 0)


def _bertscore(rows, ids, resamples):
    """BERTScore F1 at the delivered view for the confirmatory contrasts, on C_final IDs with a finite value for both."""
    table = {p: {} for p in PROFILES}
    for row in rows:
        if row["record_id"] in ids and is_success(row) and _finite(row["metrics"].get("bertscore_f1")):
            table[row["profile_id"]][row["record_id"]] = row["metrics"]["bertscore_f1"]
    out = {}
    for a, b in CONTRASTS:
        both = {i: ids[i] for i in set(table[a]) & set(table[b])}
        out[f"{a}-{b}"] = _summary(paired(table, a, b, both), resamples, 0.95)
    return out


def _view_scores(view_rows, common, metric, view):
    table = {p: {} for p in PROFILES}
    for row in view_rows:
        cell = row["views"][view]
        if row["record_id"] in common and not cell["failures"] and _finite(cell["metrics"].get(metric)):
            table[row["profile_id"]][row["record_id"]] = cell["metrics"][metric]
    return table


def _views(view_rows, common, strata, resamples):
    """Descriptive S/M/L: profile means, contrasts with Holm over the three views, and the share of identical views."""
    means = {}
    for p in PROFILES:
        for metric in VIEW_METRICS:
            for view in VIEWS:
                values = list(_view_scores(view_rows, common, metric, view)[p].values())
                means[f"{p}|{metric}|{view}"] = {"n": len(values), "mean": base._mean(values) if values else None}
    contrasts = {}
    for a, b in CONTRASTS:
        for metric in VIEW_METRICS:
            cells = {}
            for view in VIEWS:
                table = _view_scores(view_rows, common, metric, view)
                both = {i: strata[i] for i in set(table[a]) & set(table[b])}
                cells[view] = _summary(paired(table, a, b, both), resamples, 0.95)
            adjusted = holm([c["p_two_sided"] if c["n"] else 1.0 for c in cells.values()])
            for view, p_adj in zip(VIEWS, adjusted):
                cells[view]["p_holm_over_three_views"] = p_adj
            contrasts[f"{a}-{b}|{metric}"] = cells
    identical = {}
    for p in PROFILES:
        group = [r for r in view_rows if r["profile_id"] == p and r["record_id"] in common
                 and all(not r["views"][v]["failures"] for v in VIEWS)]
        same = sum(r["views"]["S"]["metrics"] == r["views"]["M"]["metrics"] == r["views"]["L"]["metrics"] for r in group)
        identical[p] = {"n": len(group), "share_metric_identical_S_M_L": same / len(group) if group else None}
    return {"label": "descriptive; views are prefix slices; identical metrics stand in for identical text",
            "means": means, "contrasts": contrasts, "identical_share": identical}


def diagnostic_cases(rows, common_ids, strata, per_stratum=DIAGNOSTIC_PER_STRATUM, seed=SEED):
    """36 qualitative cases: per stratum the most negative and most positive led-minus-bart deltas, plus random ones.

    Lists IDs only; reading text is allowed once the result file exists.
    """
    scores = _score_table(rows, set(common_ids))
    quarter = per_stratum // 3
    cases = {}
    for s in STRATA:
        members = sorted(i for i in common_ids if strata[i] == s)
        delta = {i: scores[LEADER][i] - scores["bart"][i] for i in members}
        ranked = sorted(members, key=lambda i: (delta[i], i))
        negative = ranked[:quarter]
        positive = [i for i in reversed(ranked) if i not in negative][:quarter]
        rest = sorted(i for i in members if i not in negative and i not in positive)
        drawn = random.Random(seed).sample(rest, min(quarter, len(rest)))
        cases[s] = {"most_negative": negative, "most_positive": positive, "random": sorted(drawn)}
    return cases


# --- inputs and CLI ------------------------------------------------------------------------------------------

def load_inputs(declaration_path, receipt_path, protocols, contract_path, outcome_path, metrics_path, views_path):
    """Load the frozen files; refuse any whose hash differs from the one the declaration bound."""
    declaration = _load(declaration_path)
    receipt = _load(receipt_path)
    if sha256_file(declaration_path) != receipt["declaration_sha256"]:
        raise ValueError("declaration differs from the hashed receipt")
    for key, relative in declaration["bound_paths_relative_to_protocols_dir"].items():
        if sha256_file(Path(protocols) / relative) != declaration["bound_hashes"][key]:
            raise ValueError(f"{relative} differs from the hash bound in the declaration")
    outcome = _load(outcome_path)
    if outcome.get("audit_pass") is not True:
        raise ValueError("final523 scoring audit did not pass")
    rules = _load(Path(protocols) / declaration["bound_paths_relative_to_protocols_dir"]["admission_rules_v2_sha256"])

    def read(path):
        return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

    return {"declaration": declaration, "rules": rules, "contract": _load(contract_path),
            "rows": read(metrics_path), "view_rows": read(views_path)}


def engine_sha256():
    return sha256_file(__file__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path, help="extracted evidence/metrics.jsonl")
    parser.add_argument("--views", required=True, type=Path, help="extracted evidence/view_metrics.jsonl")
    parser.add_argument("--contract", required=True, type=Path, help="registry final523 scoring_contract.json")
    parser.add_argument("--outcome", required=True, type=Path, help="registry final523_scoring_outcome.json (audit_pass)")
    parser.add_argument("--engine-sha256", required=True, help="hash recorded beforehand; must equal this module's")
    parser.add_argument("--out", required=True, type=Path, help="output folder")
    args = parser.parse_args()
    if args.engine_sha256 != engine_sha256():
        raise SystemExit("engine hash differs from the recorded one; refusing to run")
    result_path = args.out / RESULT_NAME
    if result_path.exists():
        raise SystemExit("result already exists; the rule is applied once and never re-run")
    args.out.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs(DECLARATION, DECLARATION_RECEIPT, PROTOCOLS, args.contract, args.outcome, args.metrics, args.views)
    result = apply_rule(inputs["rows"], inputs["view_rows"], inputs["contract"], inputs["rules"], inputs["declaration"])
    result.update({"schema_version": 1, "scope": "final523 confirmatory analysis applied once; text-free",
                   "engine_sha256": engine_sha256(), "metrics_sha256": sha256_file(args.metrics),
                   "view_metrics_sha256": sha256_file(args.views), "declaration_sha256": sha256_file(DECLARATION),
                   "bound_hashes": inputs["declaration"]["bound_hashes"], "labels": list(LABELS),
                   "resamples": RESAMPLES, "seed": SEED})
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    receipt = {"engine_sha256": engine_sha256(), "result_sha256": sha256_file(result_path),
               "run_at_utc": datetime.now(timezone.utc).isoformat(), "runs": 1}
    (args.out / "final523_analysis_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result["label"] != "not_evaluable":
        # Written only after the result file exists, as declared.
        gate3 = next(g for g in result["gates"] if g["gate"] == "3_common_floors")
        success = {r["record_id"] for r in inputs["rows"] if r["profile_id"] == PROFILES[0] and is_success(r)}
        for p in PROFILES[1:]:
            success &= {r["record_id"] for r in inputs["rows"] if r["profile_id"] == p and is_success(r)}
        assert len(success) == gate3["common"]["n"]
        cases = diagnostic_cases(inputs["rows"], success, inputs["contract"]["source_strata"])
        (args.out / "final523_diagnostic_case_ids.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": result["label"], "stopped_at": result["stopped_at"]}))


if __name__ == "__main__":
    main()
