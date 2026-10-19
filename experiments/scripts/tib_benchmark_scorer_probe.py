"""Explicit local-only native/window equivalence probe, never automatic readiness."""

import argparse
import json
from pathlib import Path

import numpy as np

from experiments.scripts.rq2_tib_benchmark_metrics import token_alignment_f1
from experiments.scripts.tib_benchmark_scorer import LocalSemanticScorer, package_versions


def probe(scorer):
    """Requires actual pinned weights; output does not authorize selection."""
    scorer.load()
    pairs = [("The lecture explains quantum states.", "The talk discusses quantum states."),
             ("Unicode café and unknown [MASK] token.", "Unicode café with a token.")]
    errors = []
    for candidate, reference in pairs:
        native = float(scorer._bert.score([candidate], [reference], batch_size=1)[2][0])
        first, fw = scorer._bert_tokens(candidate, include_special=True)
        second, sw = scorer._bert_tokens(reference, include_special=True)
        windowed = token_alignment_f1(first, second, candidate_weights=fw, reference_weights=sw)
        errors.append(abs(native - windowed))
    texts = [p[0] for p in pairs]
    native_vectors = scorer._sentence.encode(texts, batch_size=1, normalize_embeddings=True,
                                            show_progress_bar=False)
    direct = scorer._sentence_vectors(texts)
    sentence_error = float(np.max(np.abs(native_vectors - direct)))
    tokenizer = scorer._bert._tokenizer
    long_text = "Quantum states café unknown [MASK]. " * 150
    ids = tokenizer.encode(long_text, add_special_tokens=False, truncation=False)
    vectors, weights = scorer._bert_tokens(long_text, include_special=True)
    content_count = int(sum(weights))
    encoder = scorer._sentence
    sentence_tokenizer = encoder.tokenizer
    long_sentence = "Quantum states café [MASK] " * 80
    prepared = long_sentence.strip()
    if getattr(encoder._first_module(), "do_lower_case", False):
        prepared = prepared.lower()
    expected_ids = sentence_tokenizer.encode(prepared, add_special_tokens=False, truncation=False)
    observed_ids = []

    def observe(module, arguments):
        features = arguments[0]
        for row, mask in zip(features["input_ids"], features["attention_mask"]):
            real = row[mask.bool()].tolist()
            if len(real) > encoder.max_seq_length or sentence_tokenizer.num_special_tokens_to_add(False) != 2:
                raise ValueError("Unexpected pinned sentence wrapper/capacity")
            observed_ids.extend(real[1:-1])

    hook = encoder.register_forward_pre_hook(observe)
    try:
        scorer._sentence_vectors([long_sentence])
    finally:
        hook.remove()
    passed = (max(errors) <= 1e-5 and sentence_error <= 1e-5 and content_count == len(ids)
              and observed_ids == expected_ids)
    return {"status": "pass" if passed else "fail", "actual_pinned_neural_probe": True,
            "bert_native_max_abs_error": max(errors), "sentence_native_max_abs_error": sentence_error,
            "long_bert_content_tokens": len(ids), "long_bert_preserved_content_tokens": content_count,
            "long_window_rows": len(vectors), "packages": package_versions(),
            "long_sentence_content_tokens": len(expected_ids),
            "long_sentence_exact_token_ids_preserved": observed_ids == expected_ids,
            "scorer_ready": False, "remaining_gate": "bind assets/code/runtime/profile and full fixtures in readiness receipt"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bert-assets", type=Path, required=True)
    parser.add_argument("--sentence-assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = probe(LocalSemanticScorer(bert_path=args.bert_assets, sentence_path=args.sentence_assets))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
