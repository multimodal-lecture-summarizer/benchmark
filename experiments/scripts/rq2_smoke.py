"""Run one source-backed TIB item through S1 and a source-only S3 smoke baseline."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from datasets import load_dataset
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from benchmarks.models.llm_engine import DeterministicAbstractiveEngine
from benchmarks.models.summarization import (
    S1_FixedChunkMapReduceSummarizer,
    S3_PredictedHierarchySummarizer,
    SummarizerConfig,
)


REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
PLAN_DIR = ROOT / "plans/261002-0946-rq2-controlled-summarization"
OUTPUT_DIR = ROOT / "experiments/outputs/diagnostic/rq2_smoke"


class RecordingEngine:
    """Wrap deterministic generation to record calls without retaining prompts."""

    def __init__(self) -> None:
        self.engine = DeterministicAbstractiveEngine()
        self.calls: list[dict] = []

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> str:
        result = self.engine.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        self.calls.append(
            {
                "prompt_chars": len(prompt),
                "prompt_words": len(prompt.split()),
                "output_words": len(result.split()),
                "max_output_tokens": max_tokens,
            }
        )
        return result


def predict_lexical_boundaries(texts: list[str], starts: list[float], duration: float) -> tuple[list[float], list[dict]]:
    """Choose source-only topic-shift candidates by adjacent-window TF-IDF cohesion."""
    window = 4
    if len(texts) < window * 2 + 1 or duration <= 0:
        return [], []
    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(texts)
    shifts = []
    for index in range(window, len(texts) - window):
        left = np.asarray(matrix[index - window : index].mean(axis=0)).ravel()
        right = np.asarray(matrix[index : index + window].mean(axis=0)).ravel()
        denominator = np.linalg.norm(left) * np.linalg.norm(right)
        similarity = float(np.dot(left, right) / denominator) if denominator else 0.0
        shifts.append({"index": index, "time": starts[index], "novelty": 1.0 - similarity})

    target_count = min(5, max(1, int(duration // 600)))
    min_gap = max(90.0, duration / (target_count + 1) * 0.45)
    candidates = [
        row for i, row in enumerate(shifts)
        if row["time"] >= duration * 0.08
        and row["time"] <= duration * 0.92
        and row["novelty"] >= max(
            shifts[max(0, i - 2)]["novelty"],
            shifts[min(len(shifts) - 1, i + 2)]["novelty"],
        )
    ]
    if not candidates:
        candidates = [row for row in shifts if duration * 0.08 <= row["time"] <= duration * 0.92]
    selected = []
    for row in sorted(candidates, key=lambda item: (-item["novelty"], item["time"])):
        if all(abs(row["time"] - prior["time"]) >= min_gap for prior in selected):
            selected.append(row)
        if len(selected) == target_count:
            break
    selected.sort(key=lambda item: item["time"])
    return [row["time"] for row in selected], selected


def load_selected_record() -> tuple[dict, dict]:
    receipt_path = PLAN_DIR / "rq2-tib-valid-diagnostic-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    target = receipt["selected"][0]
    rows = load_dataset(
        receipt["dataset"],
        split="valid",
        revision=REVISION,
        streaming=True,
    )
    for record in rows:
        if str(record.get("doi") or "").strip() == target["doi"]:
            return receipt, record
    raise RuntimeError(f"Selected DOI not found in pinned validation split: {target['doi']}")


def run_smoke() -> dict:
    # Prevent a missing optional model from triggering a large network download.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    receipt, record = load_selected_record()
    segments = record["transcript_segments"]
    texts = [str(text or "").strip() for text in segments["text"]]
    starts = [float(value) for value in segments["start"]]
    ends = [float(value) for value in segments["end"]]
    if not texts or len(texts) != len(starts) or len(texts) != len(ends):
        raise ValueError("Transcript segment arrays are empty or misaligned")
    if any(right < left for left, right in zip(starts, starts[1:])):
        raise ValueError("Transcript segment starts are not ordered")

    duration = max(ends)
    boundaries, boundary_evidence = predict_lexical_boundaries(texts, starts, duration)
    transcript_hash = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
    engine = RecordingEngine()
    base_config = {
        "max_source_tokens": 8000,
        "max_output_tokens": 128,
        "chunk_tokens": 512,
    }
    s1 = S1_FixedChunkMapReduceSummarizer(
        SummarizerConfig(variant_id="S1_smoke", **base_config), llm_engine=engine
    ).summarize(texts)
    s1_calls = engine.calls[:]
    engine.calls.clear()
    s3 = S3_PredictedHierarchySummarizer(
        SummarizerConfig(variant_id="S3_lexical_cohesion_smoke", **base_config),
        llm_engine=engine,
    ).summarize(texts, boundaries, starts)
    s3_calls = engine.calls[:]

    return {
        "status": "engineering_smoke_only",
        "dataset": receipt["dataset"],
        "revision": REVISION,
        "split": "valid",
        "test_content_accessed": False,
        "doi": record.get("doi"),
        "transcript_sha256": transcript_hash,
        "input": {
            "segment_count": len(texts),
            "transcript_words": len(" ".join(texts).split()),
            "duration_seconds": duration,
        },
        "generator": "DeterministicAbstractiveEngine + cached SentenceTransformer if available",
        "structure": {
            "name": "unsupervised adjacent-window TF-IDF lexical cohesion",
            "boundaries_seconds": boundaries,
            "boundary_scores": boundary_evidence,
            "uses_transcript_content": True,
            "ground_truth_used": False,
        },
        "budgets": base_config,
        "arms": {
            "S1": {
                "summary": s1.summary_text,
                "reported_input_token_estimate": s1.token_usage.get("source_tokens"),
                "output_token_estimate": s1.token_usage.get("output_tokens"),
                "calls": s1_calls,
            },
            "S3_lexical_cohesion": {
                "summary": s3.summary_text,
                "reported_input_token_estimate": s3.token_usage.get("source_tokens"),
                "output_token_estimate": s3.token_usage.get("output_tokens"),
                "calls": s3_calls,
            },
        },
        "interpretation": (
            "Checks real-data loading, timestamp alignment, and both summarizer code paths. "
            "The generator and unsupervised lexical-cohesion structure are pilot settings, not the "
            "registered C5 predictor; metrics and summaries are not evidence of comparative quality."
        ),
    }


if __name__ == "__main__":
    result = run_smoke()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "rq2_tib_s1_s3_smoke.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "doi": result["doi"], "output": str(path)}, indent=2))
