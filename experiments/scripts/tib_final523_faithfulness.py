"""MiniCheck faithfulness of the final523 LED and BART outputs, a post-hoc secondary (protocol tib-final523-faithfulness-261031-v1).

Reads the private final523 scoring bundle, so no output is generated again. Each distinct sentence of the contract view
(the delivered 350-word summary) and of the stored S/M/L views is scored once against the whole source; every view score
is derived from those sentence scores, as in the Pilot40 run (tib_pilot_faithfulness). The scorer is injected, so the
logic is tested without a model. The analysis reads only the text-free receipt and reuses the final523 stratified
bootstrap; it never changes the final523 confirmatory label.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import zipfile
from pathlib import Path

from experiments.scripts import tib_summary_constructors as build
from experiments.scripts.tib_pilot_faithfulness import SUPPORT_THRESHOLD, load_minicheck_claims  # noqa: F401 (notebook uses it)

PROTOCOL_ID = "tib-final523-faithfulness-261031-v1"
PROFILES = ("led", "bart")
VIEW_NAMES = ("contract", "S", "M", "L")
STRATA = ("short", "medium", "long")
LEADER, RIVAL = "led", "bart"
SEED = 20261031
RESAMPLES = 10000
LEVEL = 0.95
PRACTICAL_MARGIN = 0.05
EXPECTED_C_FINAL = 519
REVIEW_FLAGGED, REVIEW_UNFLAGGED = 4, 2


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---- inputs -------------------------------------------------------------------------

def collect_rows(bundle_zip: str | Path, profiles=PROFILES) -> tuple[list[dict], list[dict]]:
    """Rows to score and the not-scoreable cells, from scoring_outputs.jsonl of the final523 scoring bundle.

    Stops on any hash mismatch between the stored text and its recorded digest.
    """
    with zipfile.ZipFile(bundle_zip) as archive:
        lines = archive.read("scoring_outputs.jsonl").decode("utf-8").splitlines()
    rows, skipped = [], []
    for line in lines:
        item = json.loads(line)
        if item["profile_id"] not in profiles:
            continue
        if not item["scoreable"]:
            skipped.append({"candidate": item["profile_id"], "record_id": item["record_id"],
                            "stratum": item["source_stratum"], "status": item["generation_status"],
                            "failure_reason": item.get("failure_reason")})
            continue
        if _sha256(item["source"]) != item["source_sha256"] or _sha256(item["delivered_summary"]) != item["delivered_sha256"]:
            raise ValueError(f"text hash mismatch for {item['sample_id']}")
        rows.append({"candidate": item["profile_id"], "record_id": item["record_id"], "stratum": item["source_stratum"],
                     "status": item["generation_status"], "source": item["source"],
                     "views": {"contract": item["delivered_summary"], **{n: item["views"][n] for n in ("S", "M", "L")}}})
    return rows, skipped


# ---- scoring (scorer injected) ----------------------------------------------------------

def score_row_detailed(row: dict, score_claims) -> tuple[dict, dict]:
    """Text-free record scores and, separately, the private per-sentence detail (text and probability)."""
    sentences = {name: build.split_sentences(row["views"][name]) for name in VIEW_NAMES}
    distinct = list(dict.fromkeys(s for name in VIEW_NAMES for s in sentences[name]))
    values = list(score_claims(row["source"], distinct)) if distinct else []
    if len(values) != len(distinct):
        raise ValueError(f"scorer returned {len(values)} probabilities for {len(distinct)} sentences")
    if not all(isinstance(p, float) and 0.0 <= p <= 1.0 for p in values):
        raise ValueError("scorer returned a probability outside [0, 1] or not a number")
    probs = dict(zip(distinct, values))
    out = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
           "status": row["status"], "distinct_sentences": len(distinct), "views": {}}
    for name in VIEW_NAMES:
        values = [probs[s] for s in sentences[name]]
        if not values:
            raise ValueError(f"view {name} has no sentence")
        out["views"][name] = {"sentences": len(values), "mean_prob": statistics.fmean(values),
                              "flagged_share": sum(1 for p in values if p < SUPPORT_THRESHOLD) / len(values)}
    detail = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
              "sentences": [{"index": i, "text": s, "prob": probs[s],
                             "in_views": [n for n in VIEW_NAMES if s in sentences[n]]} for i, s in enumerate(distinct)]}
    return out, detail


def read_jsonl(path: str | Path) -> list[dict]:
    """JSONL lines; a half-written last line (a session that died mid-write) is dropped, any other bad line raises."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    items = []
    for i, line in enumerate(lines):
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            if i != len(lines) - 1:
                raise
    return items


def repair_jsonl(path: str | Path) -> None:
    """Cut a torn last line off the file itself, so the next append starts on a clean line.

    `read_jsonl` ignores such a line in memory only; without this, the first appended row would be glued to it and lost.
    """
    path = Path(path)
    if not path.exists():
        return
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    cut = data.rfind(b"\n") + 1
    path.write_bytes(data[:cut])


def latest_by(items: list[dict], key: str) -> list[dict]:
    """One item per `key` value, the last occurrence winning, in first-seen order (a retried row is appended again)."""
    latest: dict = {}
    for item in items:
        latest[item[key]] = item
    return list(latest.values())


def score_rows(rows: list[dict], score_claims, checkpoint: str | Path, detail_path: str | Path, on_row=None,
               max_consecutive_errors: int = 5) -> list[dict]:
    """Score every row, appending to a JSONL checkpoint and resuming from it.

    The private detail line is written before the checkpoint line, so a resumed run never lacks detail for a scored
    record (a crash between the two writes leaves a duplicate detail line; readers keep the last one). A row that
    raises is kept as an error row, never scored as zero, and is scored again on the next run. Error rows hold only
    the exception type, because an exception message can quote private sentence text. After
    `max_consecutive_errors` errors in a row the run stops (a broken GPU context fails every later record).
    """
    path, done = Path(checkpoint), {}
    repair_jsonl(path)
    repair_jsonl(detail_path)
    if path.exists():
        for item in read_jsonl(path):
            done[(item["candidate"], item["record_id"])] = item  # the last line of a key wins
    results, streak = [], 0
    for row in rows:
        key = (row["candidate"], row["record_id"])
        if key in done and "views" in done[key]:
            results.append(done[key])
            continue
        try:
            scored, detail = score_row_detailed(row, score_claims)
            with Path(detail_path).open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(detail, ensure_ascii=False) + "\n")
            streak = 0
        except Exception as exc:
            scored = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
                      "status": row["status"], "error": type(exc).__name__}
            streak += 1
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(scored, ensure_ascii=False) + "\n")
        results.append(scored)
        if on_row:
            on_row(scored)
        if streak >= max_consecutive_errors:
            raise RuntimeError(f"{streak} consecutive scoring errors; restart the runtime and run again to retry them")
    return results


# ---- analysis (text-free receipt only) --------------------------------------------------

def common_ids(scores: list[dict]) -> dict[str, str]:
    """C_final for this analysis: {record_id: stratum} for records with a scored LED and a scored BART row."""
    by = {}
    for r in scores:
        if "views" in r:
            by.setdefault(r["record_id"], {})[r["candidate"]] = r["stratum"]
    return {rid: s[LEADER] for rid, s in by.items() if LEADER in s and RIVAL in s}


def contrast(scores: list[dict], ids: dict[str, str], view: str, statistic: str,
             resamples: int = RESAMPLES) -> dict:
    """LED - BART on `ids`, with the final523 stratified percentile bootstrap at 95%."""
    from experiments.scripts import tib_final523_analysis as engine
    table = {p: {r["record_id"]: r["views"][view][statistic] for r in scores
                 if r["candidate"] == p and "views" in r and r["record_id"] in ids} for p in PROFILES}
    by_stratum = {s: [] for s in STRATA}
    for rid in sorted(ids):
        by_stratum[ids[rid]].append(table[LEADER][rid] - table[RIVAL][rid])
    n = sum(len(v) for v in by_stratum.values())
    if n == 0:
        return {"n": 0, "mean": None, "low": None, "high": None, "p_two_sided": None}
    return {"n": n, "mean": engine.overall_mean(by_stratum),
            **engine.bootstrap(by_stratum, resamples=resamples, seed=SEED, level=LEVEL)}


def describe(scores: list[dict], skipped: list[dict]) -> dict:
    """Per profile, view and stratum: record-weighted means with denominators. No ranking."""
    out = {}
    for p in PROFILES:
        mine = [r for r in scores if r["candidate"] == p]
        ok = [r for r in mine if "views" in r]
        entry = {"scored": len(ok), "errors": len(mine) - len(ok),
                 "not_scoreable": sum(1 for s in skipped if s["candidate"] == p), "views": {}}
        for view in VIEW_NAMES:
            cell = {}
            for stratum in ("all",) + STRATA:
                group = [r for r in ok if stratum == "all" or r["stratum"] == stratum]
                cell[stratum] = {"n": len(group), **({
                    "mean_prob": statistics.fmean(r["views"][view]["mean_prob"] for r in group),
                    "flagged_share": statistics.fmean(r["views"][view]["flagged_share"] for r in group),
                    "mean_sentences": statistics.fmean(r["views"][view]["sentences"] for r in group)} if group else {})}
            entry["views"][view] = cell
        out[p] = entry
    return out


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> dict:
    """Wilson score interval for a proportion."""
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "low": None, "high": None}
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"k": successes, "n": n, "rate": p, "low": max(0.0, centre - half), "high": min(1.0, centre + half)}


def false_flag_rates(labels: list[dict]) -> dict:
    """Per profile: share of flagged reviewed sentences labelled S (fully supported); N labels are excluded."""
    out = {}
    for p in PROFILES:
        flagged = [x for x in labels if x["candidate"] == p and x["flagged"] and x["label"] != "N"]
        out[p] = wilson(sum(1 for x in flagged if x["label"] == "S"), len(flagged))
    return out


def interpret(primary: dict, rates: dict | None, margin: float = PRACTICAL_MARGIN, complete: bool = True) -> dict:
    """Apply the protocol's frozen interpretation rule to the primary contrast and the review's false-flag rates."""
    if primary.get("mean") is None:
        return {"label": "not_evaluable", "reason": "no common scored record"}
    if not complete:
        return {"label": "not_evaluable",
                "reason": f"C_final must be {EXPECTED_C_FINAL} with no error row; rerun the notebook to retry errors"}
    if not rates or any(rates[p]["n"] == 0 for p in PROFILES):
        return {"label": "pending_hand_review", "reason": "false-flag rates are needed before any directional label"}
    overlap = rates[LEADER]["low"] <= rates[RIVAL]["high"] and rates[RIVAL]["low"] <= rates[LEADER]["high"]
    if primary["high"] < 0 and primary["mean"] <= -margin and overlap:
        return {"label": "led_less_faithful", "reason": "interval below 0, difference beyond the margin, comparable false-flag rates"}
    if primary["low"] > 0 and primary["mean"] >= margin and overlap:
        return {"label": "led_more_faithful", "reason": "interval above 0, difference beyond the margin, comparable false-flag rates"}
    return {"label": "no_difference_established",
            "reason": "interval, margin or false-flag comparability condition not met",
            "conditions": {"interval_excludes_0": primary["high"] < 0 or primary["low"] > 0,
                           "beyond_margin": abs(primary["mean"]) >= margin, "false_flag_overlap": overlap}}


def analyze(receipt: dict, labels: list[dict] | None = None, resamples: int = RESAMPLES,
            expected_c_final: int = EXPECTED_C_FINAL) -> dict:
    """The analysis the protocol declares, from the text-free receipt (and the hand-review labels when available)."""
    if receipt.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("receipt belongs to another protocol")
    scores, skipped = receipt["scores"], receipt["skipped"]
    ids = common_ids(scores)
    contrasts = {view: {stat: contrast(scores, ids, view, stat, resamples) for stat in ("mean_prob", "flagged_share")}
                 for view in ("contract", "S")}
    rates = false_flag_rates(labels) if labels else None
    errors = sum(1 for r in scores if "views" not in r)
    complete = len(ids) == expected_c_final and errors == 0
    return {"protocol_id": PROTOCOL_ID, "label_kind": "post_hoc_secondary", "c_final_n": len(ids),
            "c_final_by_stratum": {s: sum(1 for v in ids.values() if v == s) for s in STRATA},
            "error_rows": errors, "complete": complete,
            "contrasts": contrasts, "descriptive": describe(scores, skipped),
            "false_flag_rates": rates,
            "interpretation": interpret(contrasts["contract"]["mean_prob"], rates, complete=complete),
            "resamples": resamples, "seed": SEED, "level": LEVEL, "practical_margin": PRACTICAL_MARGIN}


# ---- hand-review sample (private detail file) -------------------------------------------

def load_detail(path: str | Path) -> dict[tuple, dict]:
    """The private detail file keyed by (candidate, record_id); a duplicated record keeps its last line."""
    return {(item["candidate"], item["record_id"]): item for item in read_jsonl(path)}


def draw_review_sample(detail: dict[tuple, dict], seed: int = SEED) -> list[dict]:
    """Contract-view sentences for review: per profile x stratum, REVIEW_FLAGGED flagged and REVIEW_UNFLAGGED unflagged.

    Deterministic for a given detail file; a cell with too few sentences contributes what it has.
    """
    rng = random.Random(seed)
    sample = []
    for p in PROFILES:
        for stratum in STRATA:
            pool = [(rid, s) for (cand, rid), rec in sorted(detail.items()) if cand == p and rec["stratum"] == stratum
                    for s in rec["sentences"] if "contract" in s["in_views"]]
            for flagged, k in ((True, REVIEW_FLAGGED), (False, REVIEW_UNFLAGGED)):
                group = [x for x in pool if (x[1]["prob"] < SUPPORT_THRESHOLD) == flagged]
                for rid, s in rng.sample(group, min(k, len(group))):
                    sample.append({"candidate": p, "record_id": rid, "stratum": stratum, "sentence_index": s["index"],
                                   "prob": s["prob"], "flagged": flagged})
    return sample
