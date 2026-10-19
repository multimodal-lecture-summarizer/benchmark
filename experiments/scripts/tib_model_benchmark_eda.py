"""Execute local P2 data diagnostics without summaries or model weights."""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

from experiments.scripts.tib_model_benchmark_canonical import canonical_record, iter_released


def quantiles(values):
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not len(array):
        return {"n": 0, "p50": None, "p90": None, "p95": None, "max": None}
    return {"n": len(array), **dict(zip(("p50", "p90", "p95", "max"),
            (float(value) for value in np.quantile(array, [.5, .9, .95, 1]))))}


def analyze(snapshot: Path, tokenizer_root: Path, output: Path) -> dict:
    if output.resolve() == snapshot.resolve() or snapshot.resolve() in output.resolve().parents:
        raise ValueError("EDA output must be outside the immutable snapshot")
    if output.exists():
        raise ValueError("Choose a new EDA directory; do not overwrite evidence")
    identity = json.loads((tokenizer_root / "receipt.json").read_text())
    tokenizers = {}
    for name in ("bart", "led", "qwen3"):
        for item in identity["tokenizers"][name]["files"]:
            actual = hashlib.sha256((tokenizer_root / name / item["file"]).read_bytes()).hexdigest()
            if actual != item["sha256"]:
                raise ValueError(f"Tokenizer file hash mismatch: {name}/{item['file']}")
        # Some official releases supply vocab/merges rather than tokenizer.json.
        loaded = AutoTokenizer.from_pretrained(str(tokenizer_root / name), local_files_only=True, use_fast=True)
        if not loaded.is_fast:
            raise ValueError("An offline fast tokenizer is required for audited counts")
        tokenizers[name] = loaded.backend_tokenizer
        tokenizers[name].no_truncation()
        tokenizers[name].no_padding()
        identity["tokenizers"][name]["effective_backend_sha256"] = hashlib.sha256(tokenizers[name].to_str().encode()).hexdigest()
    output.mkdir(parents=True)
    rows = []
    with gzip.open(output / "canonical_records.jsonl.gz", "wt", encoding="utf-8", compresslevel=1) as handle:
        for split, index, filename, raw in iter_released(snapshot):
            record = canonical_record(split, index, filename, raw)
            native = {name: len(tokenizer.encode(record["source_normalized"], add_special_tokens=False).ids)
                      for name, tokenizer in tokenizers.items()}
            record["source_length"] = {"words": record["source_words"], "native_tokens": native}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            metadata = {key: value for key, value in record.items() if key not in {
                "source_raw", "source_normalized", "reference_raw", "reference_normalized",
                "source_offset_runs", "reference_offset_runs", "source_trim", "reference_trim"}}
            metadata["compression_ratio"] = record["source_words"] / record["reference_words"] if record["reference_words"] else None
            rows.append(metadata)
            if len(rows) % 1000 == 0:
                print(f"Canonical/native-token audit {len(rows)}/9103", flush=True)
    summary = {"snapshot_revision": snapshot.name, "records": len(rows), "counts": {},
               "tokenizers": identity, "global_output_word_cap": None,
               "generation_executed": False, "normalization": "NFC/whitespace; raw text, hashes and offset runs retained",
               "window_counts_scope": "illustrative lower bounds; no wrappers/overlap/reduction; not measured T4 calls"}
    caps = {"bart": 1022, "led": 4094, "qwen3": 3840}
    for split in ("train", "valid", "test"):
        subset = [row for row in rows if row["split"] == split]
        summary["counts"][split] = {
            "n": len(subset), "source_words": quantiles([r["source_words"] for r in subset]),
            "reference_words": quantiles([r["reference_words"] for r in subset]),
            "compression_ratio": quantiles([r["compression_ratio"] if r["compression_ratio"] is not None else np.nan for r in subset]),
            "source_native_tokens": {name: quantiles([r["source_length"]["native_tokens"][name] for r in subset]) for name in tokenizers},
            "illustrative_window_lower_bounds": {name: quantiles([np.ceil(r["source_length"]["native_tokens"][name] / caps[name]) for r in subset]) for name in tokenizers},
            "genre": dict(Counter(r["genre"] or "UNKNOWN" for r in subset)),
            "subject": dict(Counter(r["subject"] or "UNKNOWN" for r in subset)),
            "language": dict(Counter(r["language"] or "UNKNOWN" for r in subset)),
            "anomalies": dict(Counter(flag for r in subset for flag in r["quality_flags"])),
        }
    summary["illustrative_source_token_capacity_upper_bounds"] = caps
    train = [row for row in rows if row["split"] == "train"]
    summary["source_word_cutpoints_train_tertiles"] = [int(np.quantile([r["source_words"] for r in train], q, method="lower")) for q in (1/3, 2/3)]
    summary["output_cap_train_reference_evidence"] = summary["counts"]["train"]["reference_words"]
    with (output / "record_metadata.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    make_figures(rows, output)
    receipt = {"state": "executed_eda_not_cohort_seal", "files": {}}
    for path in sorted(output.rglob("*")):
        if path.is_file():
            receipt["files"][str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return summary


def make_figures(rows, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = output / "figures"
    figures.mkdir()
    for field, label in (("source_words", "Source whitespace words"), ("reference_words", "Reference whitespace words"), ("compression_ratio", "Source/reference word ratio")):
        fig, ax = plt.subplots(figsize=(9, 4))
        for split in ("train", "valid", "test"):
            values = [r[field] for r in rows if r["split"] == split and r[field] is not None and r[field] > 0]
            ax.hist(np.log10(values), bins=40, histtype="step", label=f"{split} N={len(values)}")
        ax.set(xlabel=f"log10({label})", ylabel="Released records", title="TIB fixed snapshot — split distributions")
        ax.legend(); fig.tight_layout(); fig.savefig(figures / f"{field}.png", dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, name in zip(axes, ("bart", "led", "qwen3")):
        values = [r["source_length"]["native_tokens"][name] for r in rows]
        ax.hist(np.log10(np.maximum(values, 1)), bins=40)
        ax.set(title=f"{name} N={len(values)}", xlabel="log10(full-source native tokens)", ylabel="Records")
    fig.tight_layout(); fig.savefig(figures / "native_token_tails.png", dpi=140); plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--tokenizers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.snapshot, args.tokenizers, args.output)
    print(json.dumps({"records": result["records"], "counts": {k: v["n"] for k, v in result["counts"].items()}}, indent=2))
