"""Probe whether MiniCheck reacts to the claim text on the ablation cells (diagnostic, prints no summary text).

For one video it prints, per arm, the number of sentences, their word counts and MiniCheck probability, against the
evidence the scorer uses. It then scores two control claims against the same evidence: an absurd claim and the
first sentence of the evidence itself. If every claim gets the same probability, MiniCheck is not reading the claim
(for example the claim is cut off), and the guard metric cannot be trusted.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from experiments.scripts.led_ocr_ablation_extract import read_rows
from experiments.scripts.tib_pilot_faithfulness import load_minicheck_claims
from experiments.scripts.tib_summary_constructors import split_sentences

ABSURD = "The speaker states that the moon is made of green cheese and that all databases are edible."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--set", default="smoke")
    parser.add_argument("--video", required=True, help="cohort id, e.g. 10.5446/20769")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    import nltk

    for resource in ("punkt", "punkt_tab"):
        nltk.download(resource, quiet=True)
    out = Path(args.out_dir)
    private = {(r["id"], r["arm"]): r for r in read_rows(out / f"cells_private_{args.set}.jsonl")}
    claims, meta = load_minicheck_claims(args.device)
    evidence = private[(args.video, "D")]["source_text"]
    transcript = private[(args.video, "D")]["transcript_text"]
    print(f"evidence words: full={len(evidence.split())} transcript={len(transcript.split())}")
    for arm in ("A", "D"):
        sentences = split_sentences(private[(args.video, arm)]["summary_text"])
        probs = claims(evidence, sentences)
        print(f"arm {arm}: {len(sentences)} sentences, words per sentence {[len(s.split()) for s in sentences]}")
        print(f"  probs {[round(p, 3) for p in probs]} mean {statistics.fmean(probs):.4f}")
    first_evidence_sentence = split_sentences(transcript)[0]
    controls = {"absurd claim": ABSURD, "verbatim transcript sentence": first_evidence_sentence}
    for name, claim in controls.items():
        print(f"control {name}: prob {claims(evidence, [claim])[0]:.4f}")
    print("package:", meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
