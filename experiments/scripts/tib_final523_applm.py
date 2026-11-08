"""Exploratory final523 run of the application's summarizer family (Qwen2.5-7B-Instruct AWQ), protocol tib-final523-applm-261031-v1.

One frozen prompt, greedy decoding, no chunking, no fallback model. Sources and references are read from the private final523
scoring bundle; the generated rows use the same fields as its `scoring_outputs.jsonl`, so the existing delivery cap (350 words),
S/M/L views, ROUGE configuration and MiniCheck sentence scoring apply unchanged. The generator is injected, so every rule here is
tested without a model. The analysis reads only text-free receipts and reuses the final523 stratified bootstrap; it labels
nothing `confirmed` or `selected`.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import zipfile
from pathlib import Path

from experiments.scripts.tib_benchmark_generation_telemetry import text_diagnostics
from experiments.scripts.tib_budget_views import build_views
from experiments.scripts.tib_final523_faithfulness import latest_by, read_jsonl, repair_jsonl

PROTOCOL_ID = "tib-final523-applm-261031-v1"
PROFILE = "applm"
CONTRACT_CAP = 350
SEED = 20261031
RESAMPLES = 10000
LEVEL = 0.95
MAX_NEW_TOKENS = 600
MAX_MODEL_LEN = 32768
MAX_FAILED_BATCHES = 2  # consecutive batches without a single generated row
DECODING = {"temperature": 0, "top_p": 1, "max_new_tokens": MAX_NEW_TOKENS, "seed": SEED, "repetition_penalty": 1}
STRATA = ("short", "medium", "long")
SYSTEM_PROMPT = "You write abstracts of conference talks."
USER_TEMPLATE = (
    "Below is the transcript of a talk. Write the abstract of this talk as one paragraph of about 110 words in English. "
    "State the topic, the main points and the conclusions. Use only information that is in the transcript. "
    "Output only the abstract.\n\nTranscript:\n{source}")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PROMPT_SHA256 = sha256(json.dumps({"system": SYSTEM_PROMPT, "user_template": USER_TEMPLATE}, sort_keys=True))


def build_messages(source: str) -> list[dict]:
    """The frozen chat messages. Only the template is parsed for fields, so braces inside the source are safe."""
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": USER_TEMPLATE.format(source=source)}]


# ---- inputs -------------------------------------------------------------------------

def collect_sources(bundle_zip: str | Path, limit: int | None = None) -> list[dict]:
    """Distinct records of a final523-style scoring bundle, in sorted record order, hash-checked.

    Takes the source, reference and stratum from the first row of each record; every profile of a record shares them.
    """
    with zipfile.ZipFile(bundle_zip) as archive:
        lines = archive.read("scoring_outputs.jsonl").decode("utf-8").splitlines()
    seen: dict[str, dict] = {}
    for line in lines:
        item = json.loads(line)
        if item["record_id"] in seen:
            continue
        if sha256(item["source"]) != item["source_sha256"] or sha256(item["reference"]) != item["reference_sha256"]:
            raise ValueError(f"text hash mismatch for {item['record_id']}")
        seen[item["record_id"]] = {"record_id": item["record_id"], "stratum": item["source_stratum"],
                                   "source": item["source"], "reference": item["reference"],
                                   "source_sha256": item["source_sha256"], "reference_sha256": item["reference_sha256"],
                                   "source_receipt_sha256": item["source_receipt_sha256"]}
    sources = [seen[k] for k in sorted(seen)]
    return sources[:limit] if limit else sources


# ---- rows ---------------------------------------------------------------------------

def make_row(src: dict, outcome: dict) -> dict:
    """A scoring_outputs-style row for one generation outcome.

    `outcome` holds either `error` (a text-free reason) or `text`, `finish_reason`, `prompt_tokens`, `completion_tokens`.
    """
    row = {"sample_id": f"{PROFILE}__{src['record_id'].replace(':', '-')}", "record_id": src["record_id"],
           "candidate_id": PROFILE, "profile_id": PROFILE, "source_stratum": src["stratum"],
           "source": src["source"], "reference": src["reference"], "source_sha256": src["source_sha256"],
           "reference_sha256": src["reference_sha256"], "source_receipt_sha256": src["source_receipt_sha256"],
           "prompt_tokens": outcome.get("prompt_tokens"), "completion_tokens": outcome.get("completion_tokens"),
           "finish_reason": outcome.get("finish_reason"), "generation_seconds": outcome.get("seconds")}
    text = outcome.get("text")
    if outcome.get("error") or not isinstance(text, str) or not text.strip():
        row.update(generation_status="failed", scoreable=False, warnings=[], delivered_summary=None, delivered_sha256=None,
                   views=None, failure_reason=outcome.get("error") or "empty_output", raw_output=None)
        return row
    delivered = build_views(text)
    warnings = []
    if outcome.get("finish_reason") == "length":
        warnings.append("no_terminal_eos_token_budget_exhausted")
    if delivered["contract"]["forced_word_boundary"]:
        warnings.append("forced_word_boundary_cut")
    diagnostics = text_diagnostics(text)
    if diagnostics["repetition_flag"]:
        warnings.append("repetition")
    row.update(generation_status="completed_with_warning" if warnings else "completed", scoreable=True,
               warnings=warnings, failure_reason=None, raw_output=text, raw_words=len(text.split()),
               delivered_summary=delivered["contract"]["text"], delivered_sha256=delivered["contract"]["delivered_sha256"],
               views={name: delivered[name]["text"] for name in ("S", "M", "L")})
    return row


def generate_rows(sources: list[dict], generate_batch, output: str | Path, batch_size: int = 4, on_batch=None) -> list[dict]:
    """Generate and append one JSONL row per source, resuming from `output` (a private file holding text).

    `generate_batch(list_of_messages) -> list of outcome dicts`. A source whose prompt may not fit is not sent: the caller's
    `generate_batch` reports it as `error: prompt_too_long`, which is final. Any other failed row is generated again on the
    next run (appended again; the last line of a record wins, see `latest_rows`). A torn last line is cut off the file. The
    run stops after MAX_FAILED_BATCHES batches in a row without a single generated row.
    """
    path = Path(output)
    repair_jsonl(path)
    done: dict[str, dict] = {}
    if path.exists():
        for item in read_jsonl(path):
            done[item["record_id"]] = item
    final = {k for k, v in done.items() if v["generation_status"] != "failed" or v["failure_reason"] == "prompt_too_long"}
    todo = [s for s in sources if s["record_id"] not in final]
    streak = 0
    for start in range(0, len(todo), batch_size):
        batch = todo[start:start + batch_size]
        outcomes = generate_batch([build_messages(s["source"]) for s in batch])
        if len(outcomes) != len(batch):
            raise ValueError("generator returned a different number of outcomes than prompts")
        rows = [make_row(s, o) for s, o in zip(batch, outcomes)]
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                done[row["record_id"]] = row
        attempted = [r for r in rows if r["failure_reason"] != "prompt_too_long"]
        streak = streak + 1 if attempted and all(r["generation_status"] == "failed" for r in attempted) else 0
        if on_batch:
            on_batch(rows)
        if streak >= MAX_FAILED_BATCHES:
            raise RuntimeError(f"{streak} consecutive failed batches; restart the runtime and run again to retry them")
    return [done[s["record_id"]] for s in sources if s["record_id"] in done]


def latest_rows(path: str | Path) -> list[dict]:
    """The generated rows of an output file, one per record (a retried row appears twice in the file; the last wins)."""
    return latest_by(read_jsonl(path), "record_id")


def generation_receipt(rows: list[dict]) -> dict:
    """Text-free counts and token/timing totals of a set of generated rows."""
    ok = [r for r in rows if r["scoreable"]]
    words = [len(r["delivered_summary"].split()) for r in ok]
    flags = lambda name: sum(1 for r in ok if name in r["warnings"])  # noqa: E731
    return {"rows": len(rows), "scoreable": len(ok), "failed": len(rows) - len(ok),
            "failures": sorted({r["failure_reason"] for r in rows if not r["scoreable"]}),
            "status_counts": {s: sum(1 for r in rows if r["generation_status"] == s)
                              for s in ("completed", "completed_with_warning", "failed")},
            "no_terminal_eos": flags("no_terminal_eos_token_budget_exhausted"), "repetition": flags("repetition"),
            "forced_word_boundary_cut": flags("forced_word_boundary_cut"),
            "delivered_words_mean": statistics.fmean(words) if words else None,
            "delivered_words_max": max(words, default=None),
            "finish_reasons": {k: sum(1 for r in rows if r["finish_reason"] == k)
                               for k in sorted({r["finish_reason"] for r in rows if r["finish_reason"]})},
            "prompt_sha256": PROMPT_SHA256, "decoding": DECODING,
            "prompt_tokens_max": max((r["prompt_tokens"] or 0 for r in rows), default=None),
            "generation_seconds_total": sum(r["generation_seconds"] or 0.0 for r in rows)}


# ---- scoring helpers (notebook) ----------------------------------------------------

def rouge_scores(summary: str, reference: str) -> dict:
    """ROUGE-1/2/L F1 with scorer v2's exact configuration (rouge-score 0.1.2, Porter stemmer)."""
    import importlib.metadata
    if importlib.metadata.version("rouge-score") != "0.1.2":
        raise ValueError("Expected rouge-score==0.1.2")
    from rouge_score.rouge_scorer import RougeScorer
    scores = RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True).score(reference, summary)
    return {name + "_f1": float(value.fmeasure) for name, value in scores.items()}


def to_faithfulness_row(row: dict) -> dict:
    """The row shape tib_final523_faithfulness.score_rows expects."""
    return {"candidate": PROFILE, "record_id": row["record_id"], "stratum": row["source_stratum"],
            "status": row["generation_status"], "source": row["source"],
            "views": {"contract": row["delivered_summary"], **row["views"]}}


# ---- analysis (text-free receipts) ----------------------------------------------------

def paired(values: dict[str, dict[str, float]], a: str, b: str, ids: dict[str, str]) -> dict:
    """Mean difference a - b over `ids` ({record_id: stratum}) with the final523 stratified bootstrap at 95%."""
    from experiments.scripts import tib_final523_analysis as engine
    by = {s: [] for s in STRATA}
    for rid in sorted(ids):
        by[ids[rid]].append(values[a][rid] - values[b][rid])
    n = sum(len(v) for v in by.values())
    if n == 0:
        return {"n": 0, "mean": None, "low": None, "high": None}
    summary = engine.bootstrap(by, resamples=RESAMPLES, seed=SEED, level=LEVEL)
    return {"n": n, "mean": engine.overall_mean(by), "low": summary["low"], "high": summary["high"]}


def analyze(applm: dict[str, dict], reference: dict[str, dict[str, dict]], strata: dict[str, str]) -> dict:
    """Descriptive contrasts of applm against led and bart on one cohort, C_applm.

    `applm[metric][record_id]` and `reference[profile][metric][record_id]` hold per-record values (None or absent when a
    cell is not scoreable); `strata` maps record_id to source stratum. C_applm is the set of records with a value for
    EVERY metric of EVERY one of the three profiles, so all contrasts and means share one denominator. A missing led or
    bart profile or metric is an error, not a smaller analysis.
    """
    metrics = sorted(applm)
    for profile in ("led", "bart"):
        missing = [m for m in metrics if m not in reference.get(profile, {})]
        if missing:
            raise ValueError(f"reference profile {profile} lacks metrics {missing}")
    table = {m: {PROFILE: applm[m], "led": reference["led"][m], "bart": reference["bart"][m]} for m in metrics}
    ids = {rid: strata[rid] for rid in applm[metrics[0]]
           if all(table[m][p].get(rid) is not None for m in metrics for p in table[m])}
    contrasts = {f"{PROFILE}-{rival}:{m}": paired(table[m], PROFILE, rival, ids) for m in metrics for rival in ("led", "bart")}
    means = {m: {p: statistics.fmean(table[m][p][rid] for rid in ids) if ids else None for p in table[m]} for m in metrics}
    return {"protocol_id": PROTOCOL_ID, "label_kind": "exploratory_post_hoc", "c_applm_n": len(ids),
            "c_applm_by_stratum": {s: sum(1 for v in ids.values() if v == s) for s in STRATA},
            "means": means, "contrasts": contrasts, "resamples": RESAMPLES, "seed": SEED, "level": LEVEL, "labels": "none"}
