---
phase: 2
title: "Candidate adapters and resource preflight"
status: in-progress
priority: P1
dependencies: [1]
effort: "1-2 days plus model download/resource checks"
---

# Phase 2: Candidate adapters and resource preflight

## Overview

Turn all six `RQ0_A` registry entries into runnable, pinned ASR systems with one input/output adapter contract. Correct registry descriptions where they misstate the implementation; keep A4 alignment and A5 denoise as identified composites.

## Requirements

- A0=`faster_whisper.WhisperModel(base,cpu,int8)`; A1=`small,cuda,float16`; A2=`distil-whisper/distil-small.en` via Transformers; A3=`medium,cuda,float16`; A4=WhisperX `small` transcription+alignment; A5=DeepFilterNet followed by exactly A1 decoder/settings.
- Pin model weight revision/checksum and package versions; freeze language `en`, task transcription, decoding/VAD/chunk settings, 16 kHz mono input policy and seeds where relevant. No silent fallback to a different device/model/preprocessor.
- Load each model once per shard, record load and warmup separately, force lazy transcription generators to complete inside timed inference, and release GPU memory between candidates.
- Preflight CUDA/VRAM, RAM, storage/cache, model access, audio decoder and measured per-candidate throughput. Use separate CPU and GPU efficiency lanes; WER/CER share the same input cohort.
- A5 input handoff is fixed before scoring: canonical 16 kHz mono → pinned deterministic resampler to the DeepFilterNet required rate (verify installed API, typically 48 kHz) → denoise → pinned resampler back to canonical 16 kHz mono → unchanged A1 decoder. Verify duration/channel invariance. A5 end-to-end RTF includes both resamplers, denoise and ASR; report each component separately, excluding one-time model load/warmup.
- Do not add CTC/transducer candidates to this user-selected A0–A5 scope. Preserve the wider plan's later family-diversity goal.

## Architecture

Registry-bound dispatch validates exactly six IDs and maps each to an adapter with `load`, `transcribe`, `close` and identity metadata. Output includes hypothesis, optional timestamps, elapsed inference/denoise/alignment times, device, model revision and failure. A5 uses paired A1 input/settings so denoise effect is interpretable. A4 WER uses transcription text; word timestamp quality is N/A absent independent timestamp GT.

## Related Code Files

- Modify: `multimodal-lecture-summarizer/experiments/registry/candidates.yaml`, `experiments/scripts/registry_loader.py`, `benchmarks/scripts/run_asr_model_benchmark.py`.
- Create a compact adapter module under `multimodal-lecture-summarizer/experiments/evaluation/` only if dispatch in the runner would become unwieldy; use existing audio modules where correct.
- Add tests under `multimodal-lecture-summarizer/tests/` for registry coverage and adapter output without real downloads.

## Implementation Steps

1. Confirm real installed API/dependency versions and model availability; revise invalid registry kwargs/classes and pin weights/config.
2. Define a common transcription result and explicit A4/A5 compositions, including A5 resampling/time policy. Keep output IDs stable and distinguish decoder from composite lanes.
3. Add dispatch and focused adapter tests for all A0–A5, empty audio/output, device failure, lazy iterator timing and model revision mismatch.
4. On a diagnostic smoke unit, measure load, decode, GPU memory and throughput; estimate complete 6×(validation+test) runtime. If manifest's 14,400-second timeout is insufficient, schedule resumable shards and update the declared timeout only from measurement.

## Success Criteria

- [ ] Six registry IDs map to six real adapters and a fixed configuration/weight identity; A5 names its A1 decoder.
- [ ] No candidate silently changes hardware or model; resource failures are explicit `blocked_resource` rows.
- [ ] Smoke transcripts and timing are real and labeled preflight, not full benchmark evidence.

## Risk Assessment

GPU candidates may exceed local VRAM or require downloads. Move execution to a recorded GPU profile if needed; never compare CPU/GPU latency as one Pareto metric. WhisperX alignment and DeepFilterNet package APIs can change; verify installed versions before adapter coding.
