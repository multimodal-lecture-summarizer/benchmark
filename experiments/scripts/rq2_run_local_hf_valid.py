"""Run a declared local LLM on pinned RQ2 validation pairs only.

The default one-pair trial measures feasibility. Use --limit 20 for the full
declared validation cohort after checking the one-pair receipt and runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.scripts.rq2_controlled_validation import (
    DATASET, REVISION, RunConfig, load_declared_cohort, predict_source_boundaries,
    preflight, run_pair,
)
from experiments.scripts.rq2_local_hf_backend import LocalHfUsageBackend

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
MODEL_DIR = ROOT / "experiments/outputs/diagnostic/rq2_models/qwen2_5_1_5b_instruct"
OUTPUT_DIR = ROOT / "experiments/outputs/diagnostic/rq2_valid_controlled_qwen"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--max-source-tokens", type=int, default=8192)
    parser.add_argument("--cumulative-prompt-budget", type=int, default=32768)
    parser.add_argument("--allowed-prompt-imbalance", type=int, default=2048)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                        help="CPU by default; CUDA requires an explicitly healthy host")
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        raise ValueError("--limit must be between 1 and 20")
    output_dir = OUTPUT_DIR if args.device == "cuda" else OUTPUT_DIR.with_name(
        "rq2_valid_controlled_qwen_cpu")

    from datasets import load_dataset

    cohort = load_declared_cohort()
    backend = LocalHfUsageBackend(MODEL_DIR, model_id=MODEL_ID,
                                  revision=MODEL_REVISION, device=args.device)
    config = RunConfig(
        model_id=backend.model_id, tokenizer_id=backend.tokenizer_id,
        max_source_tokens=args.max_source_tokens,
        cumulative_prompt_budget=args.cumulative_prompt_budget,
        allowed_prompt_imbalance=args.allowed_prompt_imbalance,
        chunk_tokens=512, max_output_tokens=96, final_output_tokens=384,
        temperature=0.0, seed=42,
        device=args.device,
    )
    gate = preflight(config, backend)
    wanted = {item["doi"] for item in cohort["selected"]}
    records = {}
    for record in load_dataset(DATASET, split="valid", revision=REVISION, streaming=True):
        doi = str(record.get("doi") or "").strip()
        if doi in wanted:
            records[doi] = record
            if len(records) == len(wanted):
                break
    if set(records) != wanted:
        raise ValueError("Pinned validation cohort could not be retrieved in full")

    # Source length is known before generation; shortest-first makes the pilot quick.
    order = sorted(wanted, key=lambda doi: backend.count_tokens(
        " ".join(str(t).strip() for t in records[doi]["transcript_segments"]["text"])))
    results = []
    for doi in order[:args.limit]:
        record = records[doi]
        segments = record["transcript_segments"]
        started = time.perf_counter()
        try:
            boundaries = predict_source_boundaries(
                [str(text).strip() for text in segments["text"]],
                [float(t) for t in segments["start"]],
            )
            pair = run_pair(record, doi, boundaries, backend, config, output_dir)
            result = {"doi": doi, "status": "completed", "path": str(output_dir /
                (re.sub(r"[^a-zA-Z0-9]+", "-", doi).strip("-") + ".json")),
                "source_tokens": pair["source_tokens"],
                "prompt_imbalance_tokens": pair["prompt_imbalance_tokens"],
                "seconds": round(time.perf_counter() - started, 2)}
        except (ValueError, RuntimeError, OSError) as exc:
            result = {"doi": doi, "status": "failed", "error_type": type(exc).__name__,
                      "reason": str(exc), "seconds": round(time.perf_counter() - started, 2)}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"status": "validation_llm_diagnostic_only", "dataset": DATASET,
                "revision": REVISION, "split": "valid", "test_content_accessed": False,
                "model": backend.model_id, "selection_sha256": gate["selection_sha256"],
                "config": vars(config), "requested_limit": args.limit,
                "results": results}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
