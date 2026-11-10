"""Phase 3b of the LED OCR ablation: score every valid cell. No comparison is computed here.

Per cell: ROUGE-L F1 at 350 and 120 words, BERTScore F1, word count, MiniCheck mean probability and flagged share
against two evidence texts (transcript + cleaned OCR; transcript only), and slide-term coverage. A metric that
cannot be computed is NULL, never zero. Scorers are injected so the logic is tested without models; the receipt is
text-free.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

from experiments.scripts.led_ocr_ablation_extract import append_ledger, log, read_rows

SUPPORT_THRESHOLD = 0.5
WORD = re.compile(r"[^\W\d_]{3,}")
SLIDE_PREFIX = re.compile(r"\bSlide:\s")
STOPWORDS = frozenset("""
the and for are but not you all any can had her was one our out has his how its may new now old see two way who did let put say she too use
that with have this will your from they know want been good much some time very when come here just like long make many over such take than
them well were what then there their these those which would about after again also because before being below between both could does doing
down during each few further have having into more most other should same than through under until while where whom why yet
""".split())


def delivered_prefix(text: str, cap: int) -> str:
    """Sentence prefix within `cap` words (the benchmark selector); imported lazily to keep tests light."""
    from experiments.scripts.tib_benchmark_output import select_delivered

    return select_delivered(text, cap)["text"]


def content_words(text: str) -> set[str]:
    return {w for w in (m.group(0).lower() for m in WORD.finditer(text)) if w not in STOPWORDS}


def slide_terms(d_source: str, transcript: str) -> set[str]:
    """T: content words in the slide blocks that never occur in the spoken text."""
    return content_words(SLIDE_PREFIX.sub(" ", d_source)) - content_words(transcript)


def term_coverage(terms: set[str], summary: str) -> float | None:
    if not terms:
        return None
    return len(terms & content_words(summary)) / len(terms)


def minicheck_stats(sentences: list[str], evidence: str, score_claims) -> dict:
    probs = list(score_claims(evidence, sentences)) if sentences else []
    if len(probs) != len(sentences) or not sentences:
        raise ValueError("scorer returned a different number of probabilities than sentences")
    if not all(isinstance(p, float) and 0.0 <= p <= 1.0 for p in probs):
        raise ValueError("scorer returned a probability outside [0, 1]")
    return {"mean_prob": statistics.fmean(probs), "flagged_share": sum(p < SUPPORT_THRESHOLD for p in probs) / len(probs),
            "sentences": len(probs)}


def score_cell(cell: dict, private: dict, reference: str, evidence_full: str, transcript: str, scorers: dict) -> dict:
    """Text-free score row for one valid cell. Each metric fails alone into NULL plus an error type."""
    summary = private["summary_text"]
    row = {"id": cell["id"], "stratum": cell["stratum"], "arm": cell["arm"], "word_count": len(summary.split()),
           "errors": {}}
    metrics = {
        "rougeL_f1_at_350": lambda: scorers["rouge"](reference, summary),
        "rougeL_f1_at_120": lambda: scorers["rouge"](reference, delivered_prefix(summary, 120)),
        "bertscore_f1": lambda: scorers["bert"](summary, reference),
        "minicheck_evidence_full": lambda: minicheck_stats(scorers["split"](summary), evidence_full, scorers["claims"]),
        "minicheck_evidence_transcript": lambda: minicheck_stats(scorers["split"](summary), transcript, scorers["claims"]),
    }
    for name, compute in metrics.items():
        try:
            row[name] = compute()
        except Exception as error:  # noqa: BLE001 - NULL plus the exception type, never a zero
            row[name] = None
            row["errors"][name] = type(error).__name__
    row["slide_term_count"] = len(slide_terms(evidence_full, transcript)) if cell["arm"] == "D" else None
    row["slide_term_coverage"] = term_coverage(slide_terms(evidence_full, transcript), summary)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--set", choices=("smoke", "cohort"), required=True)
    parser.add_argument("--references", help="private JSON {id: abstract}; default loads gigant/tib by doi")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args(argv)

    from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
    from experiments.scripts.tib_pilot_faithfulness import load_minicheck_claims
    from experiments.scripts.tib_summary_constructors import split_sentences
    from rouge_score.rouge_scorer import RougeScorer

    out_dir = Path(args.out_dir).resolve()
    receipt = read_rows(out_dir / f"cells_receipt_{args.set}.jsonl")
    private = {(r["id"], r["arm"]): r for r in read_rows(out_dir / f"cells_private_{args.set}.jsonl")}
    references = json.loads(Path(args.references).read_text(encoding="utf-8")) if args.references else load_references(
        sorted({r["id"] for r in receipt}))
    claims, minicheck_meta = load_minicheck_claims(args.device)
    semantic = SemanticScorer(device=args.device).load()
    rouge = RougeScorer(["rougeL"], use_stemmer=True)
    scorers = {"rouge": lambda ref, hyp: float(rouge.score(ref, hyp)["rougeL"].fmeasure),
               "bert": lambda hyp, ref: float(semantic._bertscore(hyp, ref)),
               "claims": claims, "split": split_sentences}
    out_path = out_dir / f"scores_receipt_{args.set}.jsonl"
    scored = {(r["id"], r["arm"]) for r in read_rows(out_path)}
    d_source = {i: r["source_text"] for (i, arm), r in private.items() if arm == "D"}
    transcripts = {i: r["transcript_text"] for (i, _), r in private.items() if "transcript_text" in r}
    log(f"scoring set={args.set}: {len(receipt)} cells, {len(scored)} already scored, {len(references)} references loaded")
    for cell in receipt:
        key = (cell["id"], cell["arm"])
        if key in scored or cell.get("status") != "ok" or key not in private or cell["id"] not in references:
            continue
        evidence = d_source.get(cell["id"], transcripts.get(cell["id"], ""))
        transcript = transcripts.get(cell["id"], "")
        row = score_cell(cell, private[key], references[cell["id"]], evidence, transcript, scorers)
        row["minicheck_package"] = minicheck_meta
        append_ledger(out_path, row)
        mc = row["minicheck_evidence_full"] or {}
        log(f"{row['id']} arm {row['arm']}: rougeL350={row['rougeL_f1_at_350']} rougeL120={row['rougeL_f1_at_120']} bert={row['bertscore_f1']} "
            f"minicheck_mean={mc.get('mean_prob')} flagged={mc.get('flagged_share')} term_cov={row['slide_term_coverage']} errors={row['errors'] or '-'}")
    return 0


def load_references(ids: list[str]) -> dict[str, str]:
    """Creator abstracts of gigant/tib at the pinned revision, joined on `doi`. Kept private."""
    from datasets import load_dataset

    wanted, found = set(ids), {}
    for split in ("train", "valid", "test"):
        for record in load_dataset("gigant/tib", split=split, revision="e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"):
            if record.get("doi") in wanted and (record.get("abstract") or "").strip():
                found[record["doi"]] = record["abstract"].strip()
    return found


if __name__ == "__main__":
    raise SystemExit(main())
