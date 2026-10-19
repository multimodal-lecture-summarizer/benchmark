"""Derive the common cap exclusively from qualified, role-safe native train."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.scripts.tib_benchmark_output import derive_word_cap, select_delivered


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(values):
    return {"n": len(values), **{key: float(np.quantile(values, q, method="inverted_cdf"))
            for key, q in (("p50", .5), ("p90", .9), ("p95", .95), ("p99", .99), ("max", 1))}}


def validate_tokenizers(tokenizer_root, receipt):
    root = tokenizer_root.resolve()
    for candidate, record in receipt["tokenizers"].items():
        for asset in record["files"]:
            path = (root / candidate / asset["file"]).resolve()
            if not path.is_relative_to(root) or sha(path) != asset["sha256"]:
                raise ValueError("Pinned tokenizer file hash mismatch")


def analyze(qualification_root, tokenizer_root, output, qualification_receipt):
    from transformers import AutoTokenizer
    if output.exists():
        raise ValueError("Versioned output evidence already exists")
    ledger = qualification_root / "qualified_cohort/qualification_ledger.jsonl"
    qualified = json.loads(qualification_receipt.read_text(encoding="utf-8"))
    bindings = {Path(name).resolve(): digest for name, digest in qualified["files"].items()}
    if bindings.get(ledger.resolve()) != sha(ledger):
        raise ValueError("Qualification ledger receipt mismatch")
    canonical = qualification_root / "eda/canonical_records.jsonl.gz"
    eda_receipt = json.loads((qualification_root / "eda/receipt.json").read_text())
    if eda_receipt["files"]["canonical_records.jsonl.gz"] != sha(canonical):
        raise ValueError("Canonical audit receipt mismatch")
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    train = {r["record_id"]: r for r in rows if r["split"] == "train" and r["role_eligible"]}
    if len(train) != qualified["counts"]["train"]["after_exposure"]:
        raise ValueError("Eligible training frame count mismatch")
    cap = derive_word_cap([r["reference_words"] for r in train.values()])
    tokenizer_receipt = json.loads((tokenizer_root / "receipt.json").read_text())
    validate_tokenizers(tokenizer_root, tokenizer_receipt)
    tokenizers, native, forced, capped = {}, {}, 0, 0
    for candidate in ("bart", "led", "qwen3"):
        tokenizers[candidate] = AutoTokenizer.from_pretrained(tokenizer_root / candidate, local_files_only=True)
        tokenizers[candidate].backend_tokenizer.no_truncation()
        tokenizers[candidate].backend_tokenizer.no_padding()
        native[candidate] = []
    checked = set()
    with gzip.open(qualification_root / "eda/canonical_records.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["record_id"] not in train:
                continue
            if row["reference_raw_sha256"] != train[row["record_id"]]["reference_raw_sha256"]:
                raise ValueError("Reference lineage mismatch")
            normalized_sha = hashlib.sha256(row["reference_normalized"].encode()).hexdigest()
            if normalized_sha != train[row["record_id"]]["reference_normalized_sha256"]:
                raise ValueError("Normalized reference hash mismatch")
            assert row["split"] == "train"
            delivered = select_delivered(row["reference_normalized"], cap["word_cap"])
            capped += delivered["capped"]
            forced += delivered["forced_word_boundary"]
            for candidate, tokenizer in tokenizers.items():
                ids = tokenizer.backend_tokenizer.encode(delivered["text"], add_special_tokens=False).ids
                native[candidate].append(len(ids))
            checked.add(row["record_id"])
    if checked != set(train):
        raise ValueError("Incomplete eligible train reference frame")
    receipt = {
        "state": "cap_derived_350_pending_profile_feasibility_not_selection_ready",
        "scope": "eligible role-safe native train only; zero validation/test references used",
        "cap_derivation": cap, "global_output_word_cap": cap["word_cap"],
        "word_definition": "English whitespace words; len(text.split())",
        "quantile_method": "nearest rank/inverted_cdf; ceil(.95*N)-th ascending observation",
        "reference_words": summarize([r["reference_words"] for r in train.values()]),
        "reference_proxy_capped_n": capped, "reference_proxy_capped_rate": capped / len(train),
        "reference_proxy_forced_boundary_n": forced,
        "delivered_reference_native_token_proxy": {name: summarize(v) for name,v in native.items()},
        "candidate_final_max_new_tokens": {"bart": 768, "led": 768, "qwen3": 768},
        "proxy_exceeding_768_native_tokens": {name: sum(n > 768 for n in v) for name,v in native.items()},
        "limits": ["Reference proxy is not model-generated output or runtime feasibility",
                   "350 is a maximum, not a required generated length",
                   "Native reserves must fit actual encoder/decoder/chat/padding contexts and measured profiles",
                   "No cap reduction after selection/test outcomes; preselection development amendment only"],
        "eligible_train_ids_sha256": hashlib.sha256("\n".join(sorted(train)).encode()).hexdigest(),
        "qualification_ledger_sha256": sha(ledger),
        "qualification_execution_receipt_sha256": sha(qualification_receipt),
        "canonical_audit_sha256": sha(canonical),
        "tokenizer_file_hashes_verified": True,
        "tokenizer_receipt_sha256": sha(tokenizer_root / "receipt.json"),
        "tokenizer_receipt": tokenizer_receipt,
        "selector_code_sha256": sha(Path(__file__).with_name("tib_benchmark_output.py")),
        "analysis_code_sha256": sha(Path(__file__)),
        "final_cap_frozen": False, "generation_executed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--tokenizers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qualification-receipt", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.qualification_root, args.tokenizers, args.output, args.qualification_receipt)
    print(json.dumps({k: result[k] for k in ("cap_derivation", "delivered_reference_native_token_proxy", "proxy_exceeding_768_native_tokens")}, indent=2))
