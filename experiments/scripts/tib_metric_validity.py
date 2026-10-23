"""Human-free validity gate for the reference-free TIB metrics, on train sources.

Evaluates the pre-registered tests in validity_criteria.json with summaries
built mechanically from sources. No reference text, model output or candidate
algorithm is used, and the criteria file is hashed into the receipt.

    python -m experiments.scripts.tib_metric_validity --records canonical_records.jsonl.gz --out receipt.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import spearmanr

from experiments.scripts.tib_benchmark_output import select_delivered, sentence_spans
from experiments.scripts.tib_budget_views import PRIMARY_BUDGETS
from experiments.scripts.tib_fact_inventory import (
    build_document_frequency, build_inventory, key_set,
)
from experiments.scripts.tib_reference_free_metrics import (
    coverage, index_source, temporal_coverage, unsupported_rate,
)

PROTOCOL_DIR = Path(__file__).resolve().parents[1] / "registry/protocols/tib-reference-free-multilength-261022-v1"
CRITERIA_PATH = PROTOCOL_DIR / "validity_criteria.json"
PADDING = " the of and to a"


# ---- sampling ---------------------------------------------------------------

def load_train_records(path: str | Path, min_words: int):
    """Train records that pass the structure check; sources only."""
    records = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["split"] == "train" and row["structure_pass"] and row["source_words"] >= min_words:
                records.append({"id": row["record_id"], "words": row["source_words"],
                                "text": row["source_normalized"]})
    return records


def draw_sample(records, criteria):
    data = criteria["data"]
    low, high = data["tertile_cutpoints_source_words"]
    groups = {"short": [], "medium": [], "long": []}
    for rec in records:
        name = "short" if rec["words"] < low else "medium" if rec["words"] < high else "long"
        groups[name].append(rec)
    key = lambda rec: hashlib.sha256((data["salt"] + rec["id"]).encode()).hexdigest()
    sample = []
    for name in groups:
        chosen = sorted(groups[name], key=key)[: data["records_per_tertile"]]
        for rec in chosen:
            sample.append({**rec, "tertile": name})
    return sample


# ---- mechanical summary constructors ------------------------------------------

def split_sentences(text: str) -> list[str]:
    return [text[a:b] for a, b in sentence_spans(text)]


def _words(sentence: str) -> int:
    return len(sentence.split())


def lead(source: str, budget: int) -> str:
    return select_delivered(source, budget)["text"]


def uniform(sents: list[str], budget: int) -> str:
    total = sum(map(_words, sents)) or 1
    take = max(1, int(budget / (total / len(sents))))
    step = len(sents) / min(take, len(sents))
    picked = sorted({min(int(i * step), len(sents) - 1) for i in range(min(take, len(sents)))})
    while len(picked) > 1 and sum(_words(sents[i]) for i in picked) > budget:
        picked.pop()
    return " ".join(sents[i] for i in picked)


def random_pick(sents: list[str], budget: int, rng: random.Random) -> str:
    order = list(range(len(sents)))
    rng.shuffle(order)
    picked, used = [], 0
    for i in order:
        if used + _words(sents[i]) <= budget:
            picked.append(i)
            used += _words(sents[i])
    return " ".join(sents[i] for i in sorted(picked))


def oracle_pick(sents: list[str], inventory, budget: int) -> list[int]:
    """Greedy gain-per-word selection of source sentences; returns indices."""
    weights = {key: weight for key, weight, _ in inventory.facts}
    sentence_keys = [key_set(s) & weights.keys() for s in sents]
    covered, picked, used = set(), [], 0
    while True:
        best, best_gain = None, 0.0
        for i, keys in enumerate(sentence_keys):
            n = _words(sents[i])
            if i in picked or used + n > budget or n == 0:
                continue
            gain = sum(weights[k] for k in keys - covered) / n
            if gain > best_gain:
                best, best_gain = i, gain
        if best is None:
            return sorted(picked)
        picked.append(best)
        covered |= sentence_keys[best]
        used += _words(sents[best])


def join(sents: list[str], indices) -> str:
    return " ".join(sents[i] for i in indices)


def _has_item(sentence: str) -> bool:
    return unsupported_rate(index_source(""), sentence) is not None


def offtopic_items(partner_sents: list[str], count: int) -> str:
    """First sentences of another record that contain a number or a name."""
    return " ".join([s for s in partner_sents if _has_item(s)][:count])


# ---- tests ----------------------------------------------------------------------

def _share(values, predicate) -> float:
    return sum(1 for v in values if predicate(v)) / len(values)


def _strictly_decreasing(xs) -> bool:
    return all(a > b for a, b in zip(xs, xs[1:]))


def _strictly_increasing(xs) -> bool:
    return all(a < b for a, b in zip(xs, xs[1:]))


def run_validity(sample, df, criteria: dict) -> dict:
    budgets = criteria["budgets"]
    seed = criteria["constructors"]["seed"]
    n = len(sample)
    per = []
    for i, rec in enumerate(sample):
        text, partner = rec["text"], sample[(i + 1) % n]
        sents, partner_sents = split_sentences(text), split_sentences(partner["text"])
        inv_a = build_inventory(text, "A", df)
        inv_b = build_inventory(text, "B", df)
        rng = lambda tag: random.Random(f"{seed}:{rec['id']}:{tag}")
        row = {"id": rec["id"], "facts_a": len(inv_a), "facts_b": len(inv_b), "cov": {}, "tcov": {}}
        for name, budget in budgets.items():
            oracle_idx = oracle_pick(sents, inv_a, budget)
            summaries = {
                "oracle": join(sents, oracle_idx),
                "lead": lead(text, budget),
                "uniform": uniform(sents, budget),
                "random": random_pick(sents, budget, rng(name)),
                "offtopic": lead(partner["text"], budget),
            }
            row["cov"][name] = {k: coverage(inv_a, v) for k, v in summaries.items()}
            row["tcov"][name] = {k: temporal_coverage(inv_a, v) for k, v in summaries.items()}
            row["cov"][name].update({f"{k}_B": coverage(inv_b, summaries[k]) for k in ("lead", "uniform", "random")})
            if name == "M":
                row["lead_M_text"] = summaries["lead"]
                row["oracle_M_idx"] = oracle_idx
            if name == "L":
                row["oracle_L_idx"] = oracle_idx
        # T2 deletion from oracle L
        row["deletion"] = {}
        for pct in (0, 25, 50, 75):
            keep = list(row["oracle_L_idx"])
            rng(f"del{pct}").shuffle(keep)
            keep = sorted(keep[: len(keep) - round(len(keep) * pct / 100)])
            row["deletion"][pct] = coverage(inv_a, join(sents, keep))
        # T3 unsupported rate
        src_index = index_source(text)
        none_as_zero = lambda v: 0.0 if v is None else v
        row["lead_unsupported"] = none_as_zero(unsupported_rate(src_index, row["lead_M_text"]))
        base = join(sents, row["oracle_M_idx"])
        row["append"] = {}
        for m in (0, 1, 3, 5):
            extra = offtopic_items(partner_sents, m)
            row["append"][m] = none_as_zero(unsupported_rate(src_index, (base + " " + extra).strip()))
        # T4 invariance
        lead_m = row["lead_M_text"]
        c0 = coverage(inv_a, lead_m)
        row["repeat_changed"] = coverage(inv_a, lead_m + " " + lead_m) != c0
        row["padding_changed"] = coverage(inv_a, lead_m + PADDING) != c0
        per.append(row)
    return {"per_record": per, **_summarize(per, criteria)}


def _summarize(per, criteria) -> dict:
    t = criteria["tests"]
    names = list(criteria["budgets"])
    results, details = {}, {}

    results["T0_inventory_size"] = _share(per, lambda r: r["facts_a"] >= 50) >= 0.95
    details["T0_inventory_size"] = {
        "share_ge_50": _share(per, lambda r: r["facts_a"] >= 50),
        "median_facts_A": statistics.median(r["facts_a"] for r in per),
        "median_facts_B": statistics.median(r["facts_b"] for r in per)}

    t1 = {}
    for b in names:
        oracle_gt_random = _share(per, lambda r: r["cov"][b]["oracle"] > r["cov"][b]["random"])
        random_gt_off = _share(per, lambda r: r["cov"][b]["random"] > r["cov"][b]["offtopic"])
        lead_gt_uniform = _share(per, lambda r: r["cov"][b]["lead"] > r["cov"][b]["uniform"])
        t1[b] = {"oracle_gt_random": oracle_gt_random, "random_gt_offtopic": random_gt_off,
                 "lead_gt_uniform_reported_only": lead_gt_uniform,
                 "mean": {k: statistics.fmean(r["cov"][b][k] for r in per)
                          for k in ("oracle", "lead", "uniform", "random", "offtopic")}}
    results["T1_known_groups"] = all(v["oracle_gt_random"] >= 0.95 and v["random_gt_offtopic"] >= 0.95
                                     for v in t1.values())
    details["T1_known_groups"] = t1

    means = [statistics.fmean(r["deletion"][p] for r in per) for p in (0, 25, 50, 75)]
    nonincreasing = _share(per, lambda r: all(r["deletion"][a] >= r["deletion"][b]
                                              for a, b in ((0, 25), (25, 50), (50, 75))))
    results["T2_fact_deletion_dose_response"] = _strictly_decreasing(means) and nonincreasing >= 0.95
    details["T2_fact_deletion_dose_response"] = {"mean_coverage_by_pct_removed": means,
                                                 "share_nonincreasing": nonincreasing}

    lead_unsup = statistics.fmean(r["lead_unsupported"] for r in per)
    app_means = [statistics.fmean(r["append"][m] for r in per) for m in (0, 1, 3, 5)]
    app_nondecr = _share(per, lambda r: all(r["append"][a] <= r["append"][b]
                                            for a, b in ((0, 1), (1, 3), (3, 5))))
    results["T3_unsupported_rate"] = (lead_unsup <= 0.01 and _strictly_increasing(app_means)
                                      and app_nondecr >= 0.90)
    details["T3_unsupported_rate"] = {"mean_lead_unsupported": lead_unsup,
                                      "mean_by_appended_sentences": app_means,
                                      "share_nondecreasing": app_nondecr}

    def mono(kind):
        return _share(per, lambda r: r["cov"]["S"][kind] <= r["cov"]["M"][kind] <= r["cov"]["L"][kind])

    inv_rate = {"repeat_changed": _share(per, lambda r: r["repeat_changed"]),
                "padding_changed": _share(per, lambda r: r["padding_changed"])}
    mono_rates = {"lead": mono("lead"), "uniform": mono("uniform"), "oracle": mono("oracle")}
    results["T4_invariance_and_monotonicity"] = (
        inv_rate["repeat_changed"] == 0 and inv_rate["padding_changed"] == 0
        and mono_rates["lead"] == 1.0 and mono_rates["uniform"] >= 0.90 and mono_rates["oracle"] >= 0.95)
    details["T4_invariance_and_monotonicity"] = {**inv_rate, "monotone_share": mono_rates}

    rhos = {}
    for kind in ("lead", "uniform", "random"):
        rho = spearmanr([r["cov"]["M"][kind] for r in per], [r["cov"]["M"][f"{kind}_B"] for r in per])[0]
        rhos[kind] = None if math.isnan(rho) else float(rho)
    median_rho = statistics.median(v for v in rhos.values() if v is not None)
    results["T5_salience_sensitivity"] = median_rho >= 0.70
    details["T5_salience_sensitivity"] = {"spearman_A_vs_B_at_M": rhos, "median": median_rho}

    direction = _share(per, lambda r: r["tcov"]["M"]["uniform"] > r["tcov"]["M"]["lead"])
    results["T6_temporal_coverage_direction"] = direction >= 0.95
    details["T6_temporal_coverage_direction"] = {
        "share_uniform_gt_lead": direction,
        "mean_temporal_coverage_M": {k: statistics.fmean(r["tcov"]["M"][k] for r in per)
                                     for k in ("oracle", "lead", "uniform", "random", "offtopic")}}
    return {"results": results, "details": details,
            "all_pass": all(results.values())}


# ---- receipt ----------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_receipt(records_path: str | Path) -> tuple[dict, dict]:
    """Run the pre-registered gate; returns (receipt, outcome with per-record rows)."""
    criteria = json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))
    assert criteria["budgets"] == PRIMARY_BUDGETS, "criteria budgets differ from the ratified views"
    records = load_train_records(records_path, int(criteria["data"]["record_filter"].split(">=")[1]))
    sample = draw_sample(records, criteria)
    df = build_document_frequency(rec["text"] for rec in records)
    outcome = run_validity(sample, df, criteria)
    receipt = {
        "schema_version": 1,
        "criteria_id": criteria["criteria_id"],
        "criteria_sha256": sha256_file(CRITERIA_PATH),
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "train_records_after_filter": len(records),
        "sample_size": len(sample),
        "sample_ids_sha256": hashlib.sha256("\n".join(r["id"] for r in sample).encode()).hexdigest(),
        "reference_text_used": False,
        "model_outputs_used": False,
        "constructor_note": "T3 treats an undefined unsupported rate (no numbers or names) as 0; "
                            "off-topic sentences are the first sentences of the next sampled record that contain a number or a name",
        "results": outcome["results"],
        "details": outcome["details"],
        "all_pass": outcome["all_pass"],
        "not_run": criteria["not_run_in_this_stage"],
    }
    return receipt, outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    receipt, outcome = build_receipt(args.records)
    Path(args.out).write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"results": outcome["results"], "all_pass": outcome["all_pass"]}, indent=2))
    return 0 if outcome["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
