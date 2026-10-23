"""MiniCheck faithfulness of Pilot40 outputs at S/M/L views, scored once per sentence.

A view is a complete-sentence prefix of the stored raw output, and MiniCheck
scores each summary sentence against the source on its own, so the score of a
view is the mean of its sentence scores. Each distinct sentence is therefore
scored once and every view is derived from those scores. The scorer is injected,
so the logic is tested without a model. Descriptive only: no selection.
"""
from __future__ import annotations

import json
import statistics
import zipfile
from pathlib import Path

from experiments.scripts import tib_summary_constructors as build
from experiments.scripts.tib_budget_views import build_views

VIEW_NAMES = ("S", "M", "L")
SUPPORT_THRESHOLD = 0.5  # MiniCheck's own decision boundary for "supported"
SCORED_STATUSES = ("completed", "completed_with_warning")


# ---- inputs -------------------------------------------------------------------------

def collect_rows(evidence_zip: str | Path) -> tuple[list[dict], list[dict]]:
    """Rows (one per record and candidate with a usable output) and skipped notes."""
    rows, skipped = [], []
    with zipfile.ZipFile(evidence_zip) as archive:
        names = set(archive.namelist())
        sources = {}
        for line in archive.read("package/pilot_sources.jsonl").decode("utf-8").splitlines():
            item = json.loads(line)
            sources[item["record_id"]] = item
        candidates = sorted({n.split("/")[1] for n in names if n.startswith("pilot/") and n.endswith("/candidate_receipt.json")})
        for candidate in candidates:
            receipt = json.loads(archive.read(f"pilot/{candidate}/candidate_receipt.json"))
            for record_id, source in sources.items():
                record = receipt.get("records", {}).get(record_id)
                result = (record or {}).get("result") or {}
                if not record or record.get("status") not in SCORED_STATUSES or not result.get("raw_final"):
                    skipped.append({"candidate": candidate, "record_id": record_id,
                                    "status": (record or {}).get("status", "missing")})
                    continue
                rows.append({"candidate": candidate, "record_id": record_id, "status": record["status"],
                             "stratum": source["source_stratum"], "source": source["source_normalized"],
                             "raw": result["raw_final"]})
    return rows, skipped


# ---- scoring (scorer injected) ----------------------------------------------------------

def view_sentences(raw: str) -> dict[str, list[str]]:
    views = build_views(raw)
    return {name: build.split_sentences(views[name]["text"]) for name in VIEW_NAMES}


def score_row_detailed(row: dict, score_claims, cache: dict | None = None) -> tuple[dict, dict]:
    """Score the distinct sentences of the row's views once and derive each view.

    Returns the text-free summary used in the receipt and, separately, the per-sentence detail
    (summary-sentence text and probability), which is derived from the private source and must
    stay out of the receipt.
    """
    cache = {} if cache is None else cache
    sentences = view_sentences(row["raw"])
    distinct = list(dict.fromkeys(s for name in VIEW_NAMES for s in sentences[name]))
    todo = [s for s in distinct if s not in cache]
    if todo:
        for sentence, prob in zip(todo, score_claims(row["source"], todo)):
            cache[sentence] = prob
    out = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
           "status": row["status"], "distinct_sentences": len(distinct), "views": {}}
    for name in VIEW_NAMES:
        probs = [cache[s] for s in sentences[name]]
        out["views"][name] = {
            "sentences": len(probs),
            "mean_prob": statistics.fmean(probs),
            "flagged_share": sum(1 for p in probs if p < SUPPORT_THRESHOLD) / len(probs),
        }
    detail = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
              "status": row["status"],
              "sentences": [{"index": i, "text": s, "prob": cache[s],
                             "in_views": [name for name in VIEW_NAMES if s in sentences[name]]}
                            for i, s in enumerate(distinct)]}
    return out, detail


def score_row(row: dict, score_claims, cache: dict | None = None) -> dict:
    """Text-free summary of one row (see score_row_detailed)."""
    return score_row_detailed(row, score_claims, cache)[0]


def max_abs_view_diff(results: list[dict], previous_scores: list[dict]) -> dict:
    """Largest per-view difference in mean_prob against an earlier run of the same rows."""
    old = {(r["candidate"], r["record_id"]): r for r in previous_scores if "views" in r}
    diffs, missing = [], []
    for r in results:
        if "views" not in r:
            continue
        before = old.get((r["candidate"], r["record_id"]))
        if before is None:
            missing.append((r["candidate"], r["record_id"]))
            continue
        diffs.extend(abs(r["views"][v]["mean_prob"] - before["views"][v]["mean_prob"]) for v in VIEW_NAMES)
    return {"compared_views": len(diffs), "max_abs_diff": max(diffs) if diffs else None, "missing_in_previous": missing}


def score_rows(rows: list[dict], score_claims, checkpoint: str | Path | None = None, on_row=None,
               detail_path: str | Path | None = None) -> list[dict]:
    """Score all rows; append each result to a JSONL checkpoint and resume from it.

    With detail_path, each newly scored row also appends its per-sentence detail (text and
    probability) to that private JSONL, written before the checkpoint line. Rows restored from an
    existing checkpoint have no detail, so use a fresh checkpoint when the detail is wanted.
    """
    done: dict[tuple, dict] = {}
    path = Path(checkpoint) if checkpoint else None
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            done[(item["candidate"], item["record_id"])] = item
    results = []
    for row in rows:
        key = (row["candidate"], row["record_id"])
        if key in done:
            results.append(done[key])
            continue
        try:
            scored, detail = score_row_detailed(row, score_claims)
            if detail_path:
                with Path(detail_path).open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(detail, ensure_ascii=False) + "\n")
        except Exception as exc:  # keep the row as a failure; never score it as zero
            scored = {"candidate": row["candidate"], "record_id": row["record_id"], "stratum": row["stratum"],
                      "status": row["status"], "error": f"{type(exc).__name__}: {exc}"}
        if path:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(scored, ensure_ascii=False) + "\n")
        results.append(scored)
        if on_row:
            on_row(scored)
    return results


# ---- summary ----------------------------------------------------------------------------

def summarize(results: list[dict], skipped: list[dict]) -> dict:
    """Per candidate and view: record-weighted means with denominators. No ranking."""
    table: dict = {}
    for candidate in sorted({r["candidate"] for r in results} | {s["candidate"] for s in skipped}):
        mine = [r for r in results if r["candidate"] == candidate]
        ok = [r for r in mine if "views" in r]
        entry = {"scored_records": len(ok), "error_records": len(mine) - len(ok),
                 "not_scored_records": sum(1 for s in skipped if s["candidate"] == candidate), "views": {}}
        for name in VIEW_NAMES:
            entry["views"][name] = {
                "mean_prob": statistics.fmean(r["views"][name]["mean_prob"] for r in ok) if ok else None,
                "flagged_share": statistics.fmean(r["views"][name]["flagged_share"] for r in ok) if ok else None,
                "mean_sentences": statistics.fmean(r["views"][name]["sentences"] for r in ok) if ok else None,
            }
        entry["by_stratum_view_M"] = {
            stratum: {"records": len(group),
                      "mean_prob": statistics.fmean(r["views"]["M"]["mean_prob"] for r in group)}
            for stratum in sorted({r["stratum"] for r in ok})
            for group in [[r for r in ok if r["stratum"] == stratum]]}
        table[candidate] = entry
    return table


# ---- scorer (installed by the notebook) ------------------------------------------------------

def load_minicheck_claims(device: str = "cuda:0"):
    from importlib import metadata
    from minicheck.minicheck import MiniCheck
    name = "roberta-large"
    try:
        scorer = MiniCheck(model_name=name, cache_dir="./ckpts")
    except TypeError:
        scorer = MiniCheck(model_name=name, device=device, cache_dir="./ckpts")

    def score_claims(source, claims):
        _, probs, _, _ = scorer.score(docs=[source] * len(claims), claims=list(claims))
        return [float(p) for p in probs]

    try:
        version = metadata.version("minicheck")
    except metadata.PackageNotFoundError:
        version = None
    return score_claims, {"package": version, "model_name": name}
