"""Fail-closed, validation-only RQ2 S1/S3 generation contract.

The repository's legacy engines expose neither exact usage nor retry receipts.
This runner accepts only a caller-supplied backend that reports every attempt.
The command-line entry point performs a safe cohort/backend preflight only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-diagnostic-receipt.json"
DATASET = "gigant/tib"
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"


@dataclass(frozen=True)
class RunConfig:
    model_id: str
    tokenizer_id: str
    max_source_tokens: int
    cumulative_prompt_budget: int
    allowed_prompt_imbalance: int
    chunk_tokens: int = 512
    max_output_tokens: int = 128
    final_output_tokens: int | None = None
    map_batch_size: int = 1
    temperature: float = 0.0
    seed: int = 42
    device: str = "unspecified"

    def validate(self) -> None:
        if not self.model_id or not self.tokenizer_id:
            raise ValueError("A declared real model and exact tokenizer are required")
        if min(self.max_source_tokens, self.cumulative_prompt_budget,
               self.chunk_tokens, self.max_output_tokens) <= 0:
            raise ValueError("Token budgets must be positive")
        if self.final_output_tokens is not None and self.final_output_tokens <= 0:
            raise ValueError("Final summary token budget must be positive")
        if self.map_batch_size <= 0:
            raise ValueError("Map batch size must be positive")
        if self.allowed_prompt_imbalance < 0:
            raise ValueError("Prompt imbalance tolerance must be nonnegative")
        if not math.isfinite(self.temperature) or self.temperature < 0:
            raise ValueError("Invalid decoding temperature")
        if self.device not in {"unspecified", "cpu", "cuda"}:
            raise ValueError("Unknown inference device")


class UsageBackend(Protocol):
    model_id: str
    tokenizer_id: str

    def count_tokens(self, text: str) -> int: ...

    def generate(self, prompt: str, *, max_output_tokens: int,
                 temperature: float, seed: int) -> dict[str, Any]:
        """Return text and attempts, each with exact prompt/output token counts."""


def load_declared_cohort(path: Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if (receipt.get("dataset") != DATASET or receipt.get("revision") != REVISION
            or receipt.get("split_read") != "valid" or receipt.get("test_content_accessed") is not False):
        raise ValueError("Only the pinned, validation-only TIB receipt is admissible")
    selected = receipt.get("selected")
    if not isinstance(selected, list) or len(selected) != 20:
        raise ValueError("The declared 20-item cohort is missing")
    dois = [item.get("doi") for item in selected]
    if any(not isinstance(doi, str) or not doi for doi in dois) or len(set(dois)) != 20:
        raise ValueError("Missing or duplicate selected DOI")
    digest = hashlib.sha256(json.dumps(dois, ensure_ascii=False).encode()).hexdigest()
    if digest != receipt.get("selected_doi_sha256"):
        raise ValueError("Selected DOI order no longer matches its receipt digest")
    return receipt


def preflight(config: RunConfig | None = None, backend: UsageBackend | None = None,
              receipt_path: Path = RECEIPT) -> dict[str, Any]:
    receipt = load_declared_cohort(receipt_path)
    if config is None or backend is None:
        return {"status": "blocked_backend_unavailable", "cohort_count": 20,
                "selection_sha256": receipt["selected_doi_sha256"],
                "reason": "No declared usage-reporting real model/backend was supplied"}
    config.validate()
    if backend.model_id != config.model_id or backend.tokenizer_id != config.tokenizer_id:
        raise ValueError("Backend model/tokenizer differs from frozen configuration")
    if not callable(getattr(backend, "count_tokens", None)) or not callable(getattr(backend, "generate", None)):
        raise ValueError("Backend lacks exact tokenizer/generation methods")
    if config.map_batch_size > 1 and (not callable(getattr(backend, "format_prompt", None))
                                      or not callable(getattr(backend, "generate_batch", None))):
        raise ValueError("Batched map generation requires format_prompt and generate_batch")
    return {"status": "ready_for_validation_diagnostic", "cohort_count": 20,
            "selection_sha256": receipt["selected_doi_sha256"], "model_id": config.model_id,
            "tokenizer_id": config.tokenizer_id}


def _source(record: dict[str, Any], doi: str, backend: UsageBackend,
            config: RunConfig) -> tuple[list[str], list[float], str]:
    if record.get("doi") != doi:
        raise ValueError("Record DOI is not the selected DOI")
    segments = record.get("transcript_segments") or {}
    texts, starts, ends = (segments.get(key) or [] for key in ("text", "start", "end"))
    if not texts or len(texts) != len(starts) or len(texts) != len(ends):
        raise ValueError("Missing or misaligned source transcript")
    clean = [str(value).strip() for value in texts]
    if any(not value for value in clean):
        raise ValueError("Empty source segment")
    if any(not isinstance(a, (int, float)) or not isinstance(b, (int, float))
           or not math.isfinite(a) or not math.isfinite(b) or a < 0 or b < a
           for a, b in zip(starts, ends)):
        raise ValueError("Invalid source timestamps")
    if any(starts[i] < ends[i - 1] for i in range(1, len(starts))):
        raise ValueError("Overlapping or unordered source timestamps")
    joined = " ".join(" ".join(clean).split())
    count = backend.count_tokens(joined)
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("Backend did not provide an exact source token count")
    if count > config.max_source_tokens:
        raise ValueError("Declared source span exceeds frozen source cap; no silent truncation")
    return clean, [float(value) for value in starts], hashlib.sha256(joined.encode()).hexdigest()


def _fixed_chunks(text: str, backend: UsageBackend, limit: int) -> list[str]:
    batch_counter = getattr(backend, "count_tokens_batch", None)
    if callable(batch_counter):
        # Scan every prefix in source order: BPE token counts can decrease when
        # another word is appended, so binary search would change boundaries.
        # Bounded speculation moves tokenizer work into its native batch path.
        words = text.split()
        chunks: list[str] = []
        current = ""
        index = 0
        while index < len(words):
            candidates: list[str] = []
            candidate = current
            for word in words[index:index + 32]:
                candidate = f"{candidate} {word}" if candidate else word
                candidates.append(candidate)
            counts = batch_counter(candidates)
            if len(counts) != len(candidates):
                raise ValueError("Batched token counts do not match source prefixes")
            for candidate, count in zip(candidates, counts):
                word = words[index]
                index += 1
                if count > limit:
                    if not current or backend.count_tokens(word) > limit:
                        raise ValueError("A source word exceeds the per-call token cap")
                    chunks.append(current)
                    current = word
                    break
                current = candidate
        if current:
            chunks.append(current)
        return chunks
    chunks: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = " ".join((*current, word))
        if backend.count_tokens(candidate) > limit:
            if not current:
                raise ValueError("A source word exceeds the per-call token cap")
            if backend.count_tokens(word) > limit:
                raise ValueError("A source word exceeds the per-call token cap")
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _hierarchy_chunks(texts: list[str], starts: list[float],
                      boundaries: list[float], backend: UsageBackend, limit: int) -> list[str]:
    if any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in boundaries):
        raise ValueError("Invalid predicted boundary")
    if sorted(set(boundaries)) != boundaries:
        raise ValueError("Predicted boundaries must be strictly ordered")
    if any(t <= starts[0] or t >= starts[-1] for t in boundaries):
        raise ValueError("Predicted boundary outside source span")
    groups: list[list[str]] = [[] for _ in range(len(boundaries) + 1)]
    for text, start in zip(texts, starts):
        index = sum(start >= boundary for boundary in boundaries)
        groups[index].append(text)
    if any(not group for group in groups):
        raise ValueError("Predicted boundary creates an empty chapter")
    return [chunk for group in groups for chunk in _fixed_chunks(" ".join(group), backend, limit)]


def predict_source_boundaries(texts: list[str], starts: list[float]) -> list[float]:
    """Small deterministic lexical-cohesion diagnostic; never reads chapter GT."""
    if len(texts) < 3 or starts[-1] <= starts[0]:
        return []
    window = min(4, max(1, len(texts) // 8))
    candidates = []
    for index in range(1, len(texts)):
        if not starts[0] + .08 * (starts[-1] - starts[0]) < starts[index] < starts[-1] - .08 * (starts[-1] - starts[0]):
            continue
        left = set(" ".join(texts[max(0, index - window):index]).casefold().split())
        right = set(" ".join(texts[index:index + window]).casefold().split())
        novelty = 1 - len(left & right) / max(1, len(left | right))
        candidates.append((novelty, starts[index]))
    target = min(5, max(1, int((starts[-1] - starts[0]) // 600)))
    gap = max(1.0, (starts[-1] - starts[0]) / (target + 1) * .45)
    chosen: list[float] = []
    for _, timestamp in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if all(abs(timestamp - old) >= gap for old in chosen):
            chosen.append(timestamp)
        if len(chosen) >= target:
            break
    return sorted(chosen)


def _call(backend: UsageBackend, prompt: str, config: RunConfig,
          calls: list[dict[str, Any]], *, output_limit: int | None = None) -> str:
    limit = output_limit if output_limit is not None else config.max_output_tokens
    response = backend.generate(prompt, max_output_tokens=limit,
                                temperature=config.temperature, seed=config.seed)
    if not isinstance(response, dict) or not isinstance(response.get("text"), str) or not response["text"].strip():
        raise ValueError("Backend returned empty or malformed output")
    attempts = response.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("Backend omitted exact per-attempt usage")
    expected_prompt = backend.count_tokens(prompt)
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError("Malformed backend attempt")
        p, o = attempt.get("prompt_tokens"), attempt.get("output_tokens")
        if (not isinstance(p, int) or isinstance(p, bool) or p != expected_prompt
                or not isinstance(o, int) or isinstance(o, bool) or o < 0
                or o > limit):
            raise ValueError("Backend usage disagrees with exact tokenizer or is incomplete")
        if attempt.get("status") not in {"retry", "failed", "success"}:
            raise ValueError("Backend omitted an attempt status")
        calls.append({"prompt_tokens": p, "output_tokens": o,
                      "content_tokens": attempt.get("content_tokens"),
                      "status": attempt.get("status", "unknown")})
    if attempts[-1].get("status") != "success":
        raise ValueError("Last generation attempt did not succeed")
    # Decode and re-encode need not preserve token count. Check each count
    # against its own source: raw generation usage and visible text.
    visible_count = backend.count_tokens(response["text"])
    final = attempts[-1]
    if final.get("content_tokens", final["output_tokens"]) != visible_count:
        raise ValueError("Backend final text count disagrees with exact tokenizer")
    if sum(call["prompt_tokens"] for call in calls) > config.cumulative_prompt_budget:
        raise ValueError("Cumulative prompt budget exceeded, including retries")
    return response["text"].strip()


def _arm(chunks: list[str], backend: UsageBackend, config: RunConfig) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    prompts = []
    for index, chunk in enumerate(chunks, 1):
        prompt = f"Summarize lecture section {index} using only its source.\nCONTENT:\n{chunk}\nSECTION SUMMARY:"
        prompts.append(prompt)
    sections = []
    if config.map_batch_size == 1:
        sections = [_call(backend, prompt, config, calls) for prompt in prompts]
    else:
        for start in range(0, len(prompts), config.map_batch_size):
            formatted = [backend.format_prompt(prompt) for prompt in prompts[start:start + config.map_batch_size]]
            responses = backend.generate_batch(formatted, max_output_tokens=config.max_output_tokens,
                                               temperature=config.temperature, seed=config.seed)
            if not isinstance(responses, list) or len(responses) != len(formatted):
                raise ValueError("Batch backend returned the wrong number of responses")
            for formatted_prompt, response in zip(formatted, responses):
                if not isinstance(response, dict) or not isinstance(response.get("text"), str) or not response["text"].strip():
                    raise ValueError("Batch backend returned empty or malformed output")
                attempts = response.get("attempts")
                if (not isinstance(attempts, list) or not attempts
                        or not isinstance(attempts[-1], dict)
                        or attempts[-1].get("status") != "success"):
                    raise ValueError("Batch backend omitted successful per-attempt usage")
                expected_prompt = backend.count_tokens(formatted_prompt)
                for attempt in attempts:
                    if not isinstance(attempt, dict):
                        raise ValueError("Malformed batch backend attempt")
                    p, o = attempt.get("prompt_tokens"), attempt.get("output_tokens")
                    if (not isinstance(p, int) or isinstance(p, bool) or p != expected_prompt
                            or not isinstance(o, int) or isinstance(o, bool)
                            or o < 0 or o > config.max_output_tokens
                            or attempt.get("status") not in {"retry", "failed", "success"}):
                        raise ValueError("Batch backend usage disagrees with exact tokenizer")
                    calls.append({"prompt_tokens": p, "output_tokens": o,
                                  "content_tokens": attempt.get("content_tokens"),
                                  "status": attempt["status"]})
                if attempts[-1].get("content_tokens", attempts[-1]["output_tokens"]) != backend.count_tokens(response["text"]):
                    raise ValueError("Batch backend text count disagrees with tokenizer")
                if sum(call["prompt_tokens"] for call in calls) > config.cumulative_prompt_budget:
                    raise ValueError("Cumulative prompt budget exceeded, including retries")
                sections.append(response["text"].strip())
    reduce_prompt = "Synthesize these source-based section summaries.\n" + "\n".join(sections) + "\nFINAL SUMMARY:"
    summary = _call(backend, reduce_prompt, config, calls,
                    output_limit=config.final_output_tokens)
    return {"summary": summary, "calls": calls,
            "prompt_tokens": sum(call["prompt_tokens"] for call in calls),
            "output_tokens": sum(call["output_tokens"] for call in calls),
            "chunk_count": len(chunks),
            "map_gpu_batches": math.ceil(len(chunks) / config.map_batch_size)}


def _receipt_hash(result: dict[str, Any]) -> str:
    data = {key: value for key, value in result.items() if key != "receipt_sha256"}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def run_pair(record: dict[str, Any], doi: str, boundaries: list[float],
             backend: UsageBackend, config: RunConfig, output_dir: Path,
             receipt_path: Path = RECEIPT) -> dict[str, Any]:
    gate = preflight(config, backend, receipt_path)
    receipt = load_declared_cohort(receipt_path)
    if doi not in {item["doi"] for item in receipt["selected"]}:
        raise ValueError("DOI is outside declared validation cohort")
    texts, starts, source_hash = _source(record, doi, backend, config)
    predicted = predict_source_boundaries(texts, starts)
    if not predicted or boundaries != predicted:
        raise ValueError("S3 requires the runner's source-only predicted boundaries")
    configuration = vars(config)
    identity = hashlib.sha256(json.dumps({"doi": doi, "source": source_hash,
        "boundaries": boundaries, "config": configuration,
        "selection": gate["selection_sha256"]}, sort_keys=True).encode()).hexdigest()
    path = output_dir / f"{re.sub(r'[^a-zA-Z0-9]+', '-', doi).strip('-')}.json"
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(old, dict) or old.get("identity_sha256") != identity
                or old.get("status") != "paired_diagnostic"
                or old.get("receipt_sha256") != _receipt_hash(old)
                or set(old.get("arms", {})) != {"S1", "S3"}):
            raise ValueError("Existing DOI receipt differs; refusing unsafe resume")
        return old
    source_text = " ".join(" ".join(texts).split())
    s1_chunks = _fixed_chunks(source_text, backend, config.chunk_tokens)
    s3_chunks = _hierarchy_chunks(texts, starts, boundaries, backend, config.chunk_tokens)
    if " ".join(s1_chunks) != source_text or " ".join(s3_chunks) != source_text:
        raise ValueError("S1/S3 do not cover the identical source span")
    s1 = _arm(s1_chunks, backend, config)
    s3 = _arm(s3_chunks, backend, config)
    imbalance = abs(s1["prompt_tokens"] - s3["prompt_tokens"])
    if imbalance > config.allowed_prompt_imbalance:
        raise ValueError("Cumulative prompt-token imbalance exceeds frozen tolerance")
    result = {"status": "paired_diagnostic", "dataset": DATASET, "revision": REVISION,
              "split": "valid", "test_content_accessed": False, "doi": doi,
              "identity_sha256": identity, "selection_sha256": gate["selection_sha256"],
              "transcript_sha256": source_hash, "source_tokens": backend.count_tokens(source_text),
              "predicted_boundaries_seconds": boundaries,
              "boundary_predictor": "source_only_adjacent_window_lexical_cohesion_v1",
              "configuration": configuration,
              "prompt_imbalance_tokens": imbalance, "arms": {"S1": s1, "S3": s3},
              "interpretation": "Engineering diagnostic; no human factual-support judgment or formal H2 claim."}
    result["receipt_sha256"] = _receipt_hash(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    print(json.dumps(preflight(receipt_path=args.receipt), indent=2))


if __name__ == "__main__":
    main()
