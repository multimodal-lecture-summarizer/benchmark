"""Run the declared TIB validation cohort through paired S1/S3 engineering diagnostics.

This runner does not score summary quality or access the sealed test split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset

from benchmarks.models.summarization import (
    S1_FixedChunkMapReduceSummarizer,
    S3_PredictedHierarchySummarizer,
    SummarizerConfig,
)
from experiments.scripts.rq2_smoke import RecordingEngine, predict_lexical_boundaries

PLAN_DIR = ROOT / "plans/261002-0946-rq2-controlled-summarization"
OUTPUT_DIR = ROOT / "experiments/outputs/diagnostic/rq2_valid_paired"
RECEIPT_PATH = PLAN_DIR / "rq2-tib-valid-diagnostic-receipt.json"
DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
SOURCE_CAP = 8000
OUTPUT_CAP = 128
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _aligned_prefix(record: dict) -> tuple[list[str], list[float], float, bool]:
    segments = record["transcript_segments"]
    texts, starts, ends = segments["text"], segments["start"], segments["end"]
    if not texts or len(texts) != len(starts) or len(texts) != len(ends):
        raise ValueError("Missing or misaligned transcript segments")
    if any(not str(text or "").strip() for text in texts):
        raise ValueError("Empty transcript segment")
    times = [(float(start), float(end)) for start, end in zip(starts, ends)]
    # A source ASR segment can have zero duration; retain its text and time.
    if any(not (0 <= start <= end and end < float("inf")) for start, end in times):
        raise ValueError("Invalid transcript segment time")
    if any(right[0] < left[1] for left, right in zip(times, times[1:])):
        raise ValueError("Overlapping or unordered transcript segments")
    remaining = int(SOURCE_CAP / 1.3)
    selected_texts, selected_starts = [], []
    selected_end = 0.0
    for text, start, end in zip(texts, starts, ends):
        words = str(text or "").strip().split()
        if remaining <= 0:
            break
        take = min(remaining, len(words))
        selected_texts.append(" ".join(words[:take]))
        selected_starts.append(float(start))
        selected_end = float(start) + (float(end) - float(start)) * take / len(words)
        remaining -= take
        if take < len(words):
            break
    if not selected_texts:
        raise ValueError("Empty budgeted transcript")
    full_words = sum(len(str(text or "").split()) for text in texts)
    return selected_texts, selected_starts, selected_end, full_words > sum(
        len(text.split()) for text in selected_texts
    )


def _arm_result(result, calls: list[dict], elapsed: float) -> dict:
    prompt_estimate = int(1.3 * sum(call["prompt_words"] for call in calls))
    return {
        "summary": result.summary_text,
        "reported_source_token_estimate": result.token_usage.get("source_tokens"),
        "reported_output_token_estimate": result.token_usage.get("output_tokens"),
        "cumulative_prompt_word_estimate": sum(call["prompt_words"] for call in calls),
        "cumulative_prompt_token_estimate": prompt_estimate,
        "estimated_prompt_cap_exceeded": prompt_estimate > SOURCE_CAP,
        "call_count": len(calls),
        "elapsed_seconds": round(elapsed, 2),
        "calls": calls,
    }


def _run_pair(record: dict, selected: dict, engine: RecordingEngine) -> dict:
    if str(record.get("doi") or "").strip() != selected["doi"]:
        raise ValueError("DOI mismatch")
    texts, starts, duration, truncated = _aligned_prefix(record)
    boundaries, scores = predict_lexical_boundaries(texts, starts, duration)
    config = {"max_source_tokens": SOURCE_CAP, "max_output_tokens": OUTPUT_CAP, "chunk_tokens": 512}
    engine.calls.clear()
    started = time.monotonic()
    s1 = S1_FixedChunkMapReduceSummarizer(
        SummarizerConfig(variant_id="S1_diagnostic", **config), llm_engine=engine
    ).summarize(texts)
    s1_elapsed = time.monotonic() - started
    s1_calls = engine.calls[:]
    engine.calls.clear()
    started = time.monotonic()
    s3 = S3_PredictedHierarchySummarizer(
        SummarizerConfig(variant_id="S3_lexical_diagnostic", **config), llm_engine=engine
    ).summarize(texts, boundaries, starts)
    s3_elapsed = time.monotonic() - started
    s1_arm = _arm_result(s1, s1_calls, s1_elapsed)
    s3_arm = _arm_result(s3, engine.calls[:], s3_elapsed)
    return {
        "status": "development_diagnostic_only",
        "doi": selected["doi"],
        "runner_sha256": RUNNER_SHA256,
        "dataset": DATASET,
        "revision": REVISION,
        "split": "valid",
        "test_content_accessed": False,
        "transcript_sha256": hashlib.sha256("\n".join(texts).encode()).hexdigest(),
        "input": {
            "segment_count": len(texts),
            "words": sum(len(text.split()) for text in texts),
            "full_transcript_words": selected["transcript_words"],
            "prefix_truncated": truncated,
            "duration_seconds": duration,
        },
        "structure": {
            "name": "source-only TF-IDF adjacent-window lexical cohesion",
            "boundaries_seconds": boundaries,
            "boundary_scores": scores,
            "ground_truth_used": False,
        },
        "generator": "DeterministicAbstractiveEngine; approximate word-based token ledger",
        "sbert_model_available": engine.engine._get_sbert_model() is not None,
        "transcript_prefix_and_output_caps": config,
        "arms": {
            "S1": s1_arm,
            "S3_lexical_cohesion": s3_arm,
        },
        "quality_evaluation": "not_run",
        "formal_h2_eligible": False,
        "full_transcript_processed": not truncated,
        "cumulative_prompt_budget_status": "estimate_exceeded" if (
            s1_arm["estimated_prompt_cap_exceeded"] or s3_arm["estimated_prompt_cap_exceeded"]
        ) else "estimate_within_cap_unverified",
        "fairness_note": "Prompt tokens are approximate, include every call, and are not equalized between arms.",
    }


def _write_json_atomic(path: Path, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def _valid_resume(path: Path, record: dict, receipt: dict, sbert_available: bool) -> bool:
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
        texts, _, _, _ = _aligned_prefix(record)
        current_hash = hashlib.sha256("\n".join(texts).encode()).hexdigest()
        arms = prior["arms"]
        return all((
            prior.get("doi") == str(record.get("doi") or "").strip(),
            prior.get("dataset") == DATASET,
            prior.get("revision") == REVISION,
            prior.get("runner_sha256") == RUNNER_SHA256,
            prior.get("selection_sha256") == receipt["selected_doi_sha256"],
            prior.get("transcript_sha256") == current_hash,
            prior.get("sbert_model_available") is sbert_available,
            prior.get("formal_h2_eligible") is False,
            all(arms[name]["summary"].strip() and arms[name]["calls"]
                for name in ("S1", "S3_lexical_cohesion")),
        ))
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError, OSError):
        return False


def run(limit: int) -> dict:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    if receipt.get("dataset") != DATASET or receipt.get("revision") != REVISION or receipt.get("split_read") != "valid":
        raise ValueError("Receipt dataset, revision or split differs from the declared validation cohort")
    selected = receipt["selected"][:limit]
    wanted = {row["doi"]: row for row in selected}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(OUTPUT_DIR / "manifest.json", {
        "status": "in_progress", "runner_sha256": RUNNER_SHA256,
        "selection_sha256": receipt["selected_doi_sha256"], "requested": len(selected),
        "split": "valid", "test_content_accessed": False,
    })
    done, failed = [], []
    engine = RecordingEngine()
    sbert_available = engine.engine._get_sbert_model() is not None
    rows = load_dataset(
        DATASET, split="valid", revision=REVISION, streaming=True
    )
    for record in rows:
        doi = str(record.get("doi") or "").strip()
        if doi not in wanted:
            continue
        path = OUTPUT_DIR / f"{hashlib.sha256(doi.encode()).hexdigest()[:16]}.json"
        if path.exists() and _valid_resume(path, record, receipt, sbert_available):
            done.append({"doi": doi, "path": str(path), "resumed": True})
            continue
        try:
            result = _run_pair(record, wanted[doi], engine)
            result["selection_sha256"] = receipt["selected_doi_sha256"]
            _write_json_atomic(path, result)
            done.append({"doi": doi, "path": str(path), "resumed": False})
        except Exception as exc:
            failed.append({"doi": doi, "error": f"{type(exc).__name__}: {exc}"})
        print(f"RQ2 valid diagnostic: {len(done) + len(failed)}/{len(selected)}", flush=True)
        if len(done) + len(failed) == len(selected):
            break
    missing = sorted(set(wanted) - {item["doi"] for item in done + failed})
    manifest = {
        "status": "development_diagnostic_only",
        "selection_sha256": receipt["selected_doi_sha256"],
        "runner_sha256": RUNNER_SHA256,
        "split": "valid",
        "test_content_accessed": False,
        "requested": len(selected),
        "completed": done,
        "failed": failed,
        "missing": missing,
        "formal_h2_eligible": False,
    }
    _write_json_atomic(OUTPUT_DIR / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    report = run(args.limit)
    print(json.dumps({"completed": len(report["completed"]), "failed": report["failed"], "missing": report["missing"]}))
