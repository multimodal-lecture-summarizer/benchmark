"""Probe whether MiniCheck reacts to the claim text on the ablation cells (diagnostic, prints no summary text).

For one video it prints, per arm, the number of sentences, their word counts and MiniCheck probability, against the
evidence the scorer uses. It then scores two control claims against the same evidence: an absurd claim and the
first sentence of the evidence itself. If every claim gets the same probability, MiniCheck is not reading the claim
(for example the claim is cut off), and the guard metric cannot be trusted.
"""

from __future__ import annotations

import argparse

import nltk
import statistics
from pathlib import Path

from experiments.scripts.led_ocr_ablation_extract import read_rows
from experiments.scripts.led_ocr_ablation_score import segment_evidence
from experiments.scripts.tib_pilot_faithfulness import load_minicheck_claims
from experiments.scripts.tib_summary_constructors import split_sentences

ABSURD = "The speaker states that the moon is made of green cheese and that all databases are edible."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--set", default="smoke")
    parser.add_argument("--video", required=True, help="cohort id, e.g. 10.5446/20769")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--show-text", action="store_true",
                        help="print each sentence of both arms with its probability under every evidence variant (private data)")
    args = parser.parse_args()

    for resource in ("punkt", "punkt_tab"):
        nltk.download(resource, quiet=True)
    out = Path(args.out_dir)
    private = {(r["id"], r["arm"]): r for r in read_rows(out / f"cells_private_{args.set}.jsonl")}
    claims, meta = load_minicheck_claims(args.device)
    evidence = private[(args.video, "D")]["source_text"]
    transcript = private[(args.video, "D")]["transcript_text"]
    sentences = nltk.sent_tokenize(evidence.replace("\n", " "))
    lengths = sorted(len(x.split()) for x in sentences)
    print(f"evidence words={len(evidence.split())} nltk sentences={len(sentences)} median={lengths[len(lengths) // 2]} "
          f"max={lengths[-1]} words; sentences over 250 words: {sum(n > 250 for n in lengths)}")
    first_evidence_sentence = split_sentences(transcript)[0]
    controls = {"absurd claim": ABSURD, "verbatim transcript sentence": first_evidence_sentence}
    for label, text in (("RAW evidence", evidence), ("SEGMENTED evidence (<=60-word passages)", segment_evidence(evidence))):
        print(f"=== {label}")
        for arm in ("A", "D"):
            claims_list = split_sentences(private[(args.video, arm)]["summary_text"])
            probs = claims(text, claims_list)
            print(f"arm {arm}: {len(claims_list)} sentences, words {[len(c.split()) for c in claims_list]}")
            print(f"  probs {[round(p, 3) for p in probs]} mean {statistics.fmean(probs):.4f}")
        for name, claim in controls.items():
            print(f"control {name}: prob {claims(text, [claim])[0]:.4f}")
    if args.show_text:
        variants = {"transcript": segment_evidence(transcript), "full(transcript+slides)": segment_evidence(evidence)}
        slide_lines = [ln for ln in segment_evidence(evidence).split("\n") if "Slide:" in ln]
        print(f"--- per-sentence view; slide passages in full evidence: {len(slide_lines)}")
        for arm in ("A", "D"):
            for index, sentence in enumerate(split_sentences(private[(args.video, arm)]["summary_text"]), 1):
                probs = {name: round(claims(text, [sentence])[0], 3) for name, text in variants.items()}
                print(f"[{arm}{index}] {probs} :: {sentence[:260]}")
    print("package:", meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
