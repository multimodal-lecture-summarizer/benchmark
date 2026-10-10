"""Shared-source S1/S3 execution, equal output allocations and partial usage."""

import hashlib
import sys
import time

from experiments.scripts.rq2_controlled_validation import (
    RunConfig, _call, _fixed_chunks, _hierarchy_chunks, predict_source_boundaries,
)


class PairGenerationError(RuntimeError):
    def __init__(self, message, partial_arm):
        super().__init__(message)
        self.partial_arm = partial_arm
        self.partial_pair = {}


def _prompts(chunks):
    return [f"Summarize lecture section {i} using only its source.\nCONTENT:\n{chunk}\nSECTION SUMMARY:"
            for i, chunk in enumerate(chunks, 1)]


def _cuda_meter(backend):
    """Measure an already initialized CUDA backend without importing torch."""
    torch = sys.modules.get("torch")
    if torch is None or not str(getattr(backend, "device", "")).startswith("cuda"):
        return None
    cuda = torch.cuda
    if not cuda.is_available() or not cuda.is_initialized():
        return None
    try:
        cuda.synchronize()
        cuda.reset_peak_memory_stats()
    except RuntimeError:
        return None
    return cuda


def _emit(on_event, **event):
    if on_event is not None:
        on_event(event)


class _BatchResponse:
    """Replay one generated response through the shared exact-usage validator."""

    def __init__(self, backend, response):
        self.count_tokens = backend.count_tokens
        self.response = response

    def generate(self, prompt, **kwargs):
        return self.response


def _map_groups(prompts, limits, size):
    # One model dispatch has a common max_new_tokens. Never round the per-chunk
    # allocation upward to combine the two caps produced by divmod.
    start = 0
    while start < len(prompts):
        end = start + 1
        while end < len(prompts) and end - start < size and limits[end] == limits[start]:
            end += 1
        yield start, prompts[start:end], limits[start]
        start = end


def _summarize(chunks, backend, call_config, map_budget, final_budget, segmentation_seconds,
               arm=None, on_event=None, reject_empty=False):
    # Both arms get exactly the same total map-output allocation, distributed
    # across their actual chunk count; final output cap is also identical.
    base, remainder = divmod(map_budget, len(chunks))
    limits = [base + (i < remainder) for i in range(len(chunks))]
    calls, sections = [], []
    summary, error, call_count = None, None, 0
    request_count = 0
    batch_size = getattr(backend, "map_batch_size", 1)
    if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
        raise ValueError("Map batch size must be a positive integer")
    if not callable(getattr(backend, "generate_batch", None)):
        batch_size = 1
    cuda = _cuda_meter(backend)
    generation_start = time.perf_counter()
    step, chunk_index = "map", None
    try:
        for start, prompts, limit in _map_groups(_prompts(chunks), limits, batch_size):
            chunk_index = start + 1
            step_start = time.perf_counter()
            details = {"batch_size": len(prompts), "chunk_end": start + len(prompts)}
            _emit(on_event, stage="generation", status="started", arm=arm, step="map",
                  chunk_index=chunk_index, chunk_total=len(chunks), **details)
            call_count += len(prompts)
            request_count += 1
            if len(prompts) == 1:
                sections.append(_call(backend, prompts[0], call_config, calls, output_limit=limit))
            else:
                responses = backend.generate_batch(prompts, max_output_tokens=limit,
                    temperature=call_config.temperature, seed=call_config.seed)
                if not isinstance(responses, list) or len(responses) != len(prompts):
                    raise ValueError("Batch backend returned the wrong number of responses")
                for offset, (prompt, response) in enumerate(zip(prompts, responses)):
                    chunk_index = start + offset + 1
                    sections.append(_call(_BatchResponse(backend, response), prompt,
                                          call_config, calls, output_limit=limit))
            _emit(on_event, stage="generation", status="completed", arm=arm, step="map",
                  chunk_index=start + 1, chunk_total=len(chunks),
                  elapsed_seconds=time.perf_counter() - step_start, **details)
            if reject_empty and any(not section.strip() for section in sections):
                raise ValueError("Empty map output; pilot policy records an arm failure")
        prompt = "Synthesize these source-based section summaries.\n" + "\n".join(sections) + "\nFINAL SUMMARY:"
        step, chunk_index = "reduce", None
        step_start = time.perf_counter()
        _emit(on_event, stage="generation", status="started", arm=arm, step=step)
        call_count += 1
        request_count += 1
        summary = _call(backend, prompt, call_config, calls, output_limit=final_budget)
        if reject_empty and not summary.strip():
            raise ValueError("Empty final output; pilot policy records an arm failure")
        _emit(on_event, stage="generation", status="completed", arm=arm, step=step,
              elapsed_seconds=time.perf_counter() - step_start)
    except (ValueError, RuntimeError, OSError) as exc:
        error = exc
        details = {"chunk_index": chunk_index, "chunk_total": len(chunks)} if step == "map" else {}
        _emit(on_event, stage="generation", status="failed", arm=arm, step=step,
              elapsed_seconds=time.perf_counter() - step_start, error_type=type(exc).__name__, **details)
    allocated, reserved = None, None
    if cuda is not None:
        try:
            cuda.synchronize()
            allocated = int(cuda.max_memory_allocated())
            reserved = int(cuda.max_memory_reserved())
        except RuntimeError:
            # Lost CUDA contexts leave memory measurements unavailable.
            allocated, reserved = None, None
    generation_seconds = time.perf_counter() - generation_start
    receipt = {"summary": summary, "calls": calls, "chunk_count": len(chunks),
            "section_summaries": sections, "status": "failed" if error else "completed",
            "reused": False, "usage_complete": error is None,
            "segmentation_seconds": segmentation_seconds,
            "generation_seconds": generation_seconds,
            "wall_seconds": segmentation_seconds + generation_seconds,
            "call_count": call_count,
            "generation_request_count": request_count,
            "map_batch_size": batch_size,
            "reported_attempt_count": len(calls),
            "peak_gpu_allocated_bytes": allocated,
            "peak_gpu_reserved_bytes": reserved,
            "map_output_caps": limits, "map_output_budget": sum(limits),
            "final_output_budget": final_budget,
            "prompt_tokens": sum(call["prompt_tokens"] for call in calls),
            "output_tokens": sum(call["output_tokens"] for call in calls)}
    if error is not None:
        receipt.update(error=str(error), error_type=type(error).__name__)
        wrapped = PairGenerationError(str(error), receipt)
        wrapped.original_error_type = type(error).__name__
        raise wrapped from error
    return receipt


def run_source_pair(source, backend, config, completed_arms=None, on_progress=None, on_event=None,
                    *, arm_order=("S1", "S3"), continue_on_arm_failure=False, reject_empty=False):
    """Consume a source-only adapter; references cannot enter either arm."""
    config.validate()
    if len(arm_order) != 2 or set(arm_order) != {"S1", "S3"}:
        raise ValueError("arm_order must contain S1 and S3 exactly once")
    preparation_start = time.perf_counter()
    segments = source["transcript_segments"]
    texts, starts = segments["text"], segments["start"]
    normalized_source = " ".join(source["transcript"].split())
    chunks_by_arm, segmentation_times = {}, {}
    for arm in ("S1", "S3"):
        segmentation_start = time.perf_counter()
        _emit(on_event, stage="segmentation", status="started", arm=arm)
        try:
            if arm == "S1":
                chunks = _fixed_chunks(normalized_source, backend, config.chunk_tokens)
            else:
                boundaries = predict_source_boundaries(texts, starts)
                chunks = _hierarchy_chunks(texts, starts, boundaries, backend, config.chunk_tokens)
        except (ValueError, RuntimeError, OSError) as exc:
            _emit(on_event, stage="segmentation", status="failed", arm=arm,
                  elapsed_seconds=time.perf_counter() - segmentation_start, error_type=type(exc).__name__)
            raise
        segmentation_times[arm] = time.perf_counter() - segmentation_start
        chunks_by_arm[arm] = chunks
        _emit(on_event, stage="segmentation", status="completed", arm=arm,
              chunk_total=len(chunks), elapsed_seconds=segmentation_times[arm])
    s1, s3 = chunks_by_arm["S1"], chunks_by_arm["S3"]
    if not s1 or not s3 or any(" ".join(chunks) != normalized_source for chunks in (s1, s3)):
        raise ValueError("The two arms must cover the identical complete source")
    map_budget = max(len(s1), len(s3)) * config.map_output_tokens
    # One common cumulative prompt cap accommodates full source plus map output;
    # record actual usage separately instead of truncating long transcripts.
    prompt_budget = max(sum(backend.count_tokens(p) for p in _prompts(chunks))
                        for chunks in (s1, s3)) + 4 * map_budget + 2048
    call_config = RunConfig(model_id=backend.model_id, tokenizer_id=backend.tokenizer_id,
        max_source_tokens=backend.count_tokens(normalized_source),
        cumulative_prompt_budget=prompt_budget, allowed_prompt_imbalance=prompt_budget,
        chunk_tokens=config.chunk_tokens, max_output_tokens=config.map_output_tokens,
        final_output_tokens=config.final_output_tokens, seed=config.seed, temperature=config.temperature)
    context = {"source_tokens": backend.count_tokens(normalized_source),
               "generation_source_sha256": hashlib.sha256(normalized_source.encode()).hexdigest(),
               "predicted_boundaries_seconds": boundaries,
               "boundary_predictor": "source_only_adjacent_window_lexical_cohesion_v1",
               "common_cumulative_prompt_budget": prompt_budget,
               "common_map_output_budget": map_budget,
               "common_final_output_budget": config.final_output_tokens,
               "structure_LLM_tokens": 0,
               "arm_order": list(arm_order)}
    # Recomputing reused arm chunks is needed for identical common budgets;
    # charge it to this attempt's overhead, not to the original reused receipt.
    fresh_segmentation = sum(seconds for name, seconds in segmentation_times.items()
        if (completed_arms or {}).get(name, {}).get("status") != "completed")
    context["shared_preparation_seconds"] = max(
        0.0, time.perf_counter() - preparation_start - fresh_segmentation)
    arms = {}
    for name in arm_order:
        chunks = chunks_by_arm[name]
        previous = (completed_arms or {}).get(name)
        if previous and previous.get("status") == "completed":
            arms[name] = {**previous, "reused": True}
            _emit(on_event, stage="generation", status="reused", arm=name)
            if on_progress:
                on_progress({**context, "arms": dict(arms)})
            continue
        try:
            arms[name] = _summarize(chunks, backend, call_config, map_budget,
                                    config.final_output_tokens, segmentation_times[name], name, on_event,
                                    reject_empty=reject_empty)
        except PairGenerationError as exc:
            arms[name] = exc.partial_arm
            exc.partial_pair = {**context, "arms": arms}
            if continue_on_arm_failure:
                if on_progress:
                    on_progress({**context, "arms": dict(arms)})
                continue
            raise
        if on_progress:
            on_progress({**context, "arms": dict(arms)})
    return {**context, "arms": arms,
            "prompt_imbalance_tokens": abs(arms["S1"]["prompt_tokens"] - arms["S3"]["prompt_tokens"])}
