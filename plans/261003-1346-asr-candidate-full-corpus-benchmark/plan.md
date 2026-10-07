---
title: "Full TED-LIUM 3 ASR candidate benchmark A0-A5"
description: "Execute all six registered ASR candidates on full TED-LIUM Release 3 validation and test cohorts."
status: in-progress
priority: P1
branch: "baseline/pre-phase1-snapshot"
tags: [research, benchmark, asr, reproducibility]
blockedBy: []
blocks: []
created: "2026-10-03T06:51:31.855Z"
createdBy: "ck:plan"
source: skill
---

# Full TED-LIUM 3 ASR candidate benchmark A0-A5

> Historical ASR plan: the old 20-WAV D2 freeze driver and generic dataset-contract code cited in some phases were removed on 2026-10-07. The completed `01c` architecture benchmark has its own notebook and report; do not rerun the retired A0–A5 workflow from this plan.

> **Scope update (2026-10-03):** This Whisper-heavy matrix is retained as an engineering diagnostic. The user changed the main ASR benchmark to compare six architecture families; see [the new architecture benchmark plan](../261003-1958-asr-architecture-benchmark/plan.md). The successful six-candidate one-unit probe does not qualify this old matrix as the main benchmark. Do not start its full validation solely for the new architecture question.

## Overview

Implement in the nested `multimodal-lecture-summarizer/` application. User confirmed exactly registry A0–A5 and the entire TED-LIUM Release 3 snapshot. The implementation inventories the full corpus and has decoded/hashed all 507 eligible validation and 1,155 native test clips. Zero train/evaluation speaker, talk and source identity overlap is recorded. Train waveform duplicates and reference creator provenance remain unverified limitations; they do not block this diagnostic run. Candidate adapters, preflight, resume/checkpoint logic, and split-bound receipts are in place.

This run is **diagnostic**: historical selection used ten test clips, and current EDA read test reference aggregates. Lock candidate definitions and validation ranking before new test inference, but never describe the native test as an untouched independent holdout. A clean prospective final test is outside this plan.

### Execution status (2026-10-03)

- Full metadata scan: 270,323 source rows / 107 Arrow shards. Validation: 507 eligible + 84 ignored. Native test: 1,155 eligible + 314 ignored/gap rows. Train: 268,263 rows. Source, speaker, and talk identifier cross-split overlaps: zero.
- Evaluation audio: 1,662/1,662 decoded and hashed; canonical mono 16 kHz cache prepared. Train audio was not decoded, so audio-level exact/near-duplicate screening remains unverified and will be stated in the diagnostic report.
- Bounded diagnostic freeze regenerated and checked at `experiments/outputs/asr_a0_a5_benchmark_261003_metadata_screen/`; loader returns 507 validation and 1,155 native-test units only when those splits are explicitly requested. The older pinned artifact is now rejected because it predates the metadata-screen status and cohort-hash binding.
- A0–A5 inference has **not** started. The latest read-only preflight has no pinned snapshots cached for A0–A3; A4 additionally lacks `torchaudio`; A5 lacks `deepfilternet` and its registered local model directory. Package pins also mismatch. These are the current execution blockers.
- Focused implementation tests and notebook dry-plan pass. There are no ASR benchmark metrics or selected candidate yet. Phase 4 remains pending until candidate resources are ready; the unverified waveform-overlap limitation must accompany any diagnostic results.

### Candidate contract

| ID | Frozen execution | Analysis lane |
| --- | --- | --- |
| A0 | Registry Faster-Whisper `base`, CPU int8 | Decoder quality, CPU efficiency |
| A1 | Faster-Whisper `small`, CUDA float16 | Decoder quality, GPU efficiency |
| A2 | `distil-whisper/distil-small.en`, Transformers CUDA | Decoder quality, GPU efficiency |
| A3 | Faster-Whisper `medium`, CUDA float16 | Decoder quality, GPU efficiency |
| A4 | WhisperX `small` transcription plus alignment; WER from transcript | ASR+alignment composite; record alignment overhead |
| A5 | DeepFilterNet denoise followed by the **same pinned A1 decoder/settings** | Denoise+ASR composite; paired A5–A1 effect |

A4/A5 are included in the six-way execution matrix but identified as composites, not independent decoder families. WER can be compared on common audio; RTF is compared only within the same hardware profile. Every candidate/unit must have a real row or an explicit failed/blocked row; incomplete candidates cannot win.

### Evaluation contract

1. Reuse `experiments/evaluation/asr_selection_scoring.py`: versioned normalization, per-unit edit counts, corpus micro WER/CER. Preserve segment boundaries. Report per-talk WER, coverage/failures, load time, inference time, total-audio RTF and hardware profile. Talk/source is the independent unit for uncertainty.
2. Freeze complete eligible validation/test IDs, source/GT/media identities, Arrow row locators/decoded-audio hashes, exclusions, candidate revisions and decoder/preprocessing settings before inference. Map source `test` to benchmark `final_test` while retaining `original_split=test`. Exclude `ignore_time_segment_in_scoring`; audit train/validation/test metadata identities. Waveform near-duplicate screening is informative but not a gate for this diagnostic run. Full inventory includes all 268,263 train rows. Runner reads verified Arrow audio directly, not missing full-corpus WAV exports.
3. Run every A0–A5 on all validation units. Select only on validation; freeze the complete selection receipt. Then run all six on all eligible native test units with a different artifact root/run ID bound to that receipt. Completed validation/test manifests and receipts are immutable; identity-matched partial outputs may be updated when resuming. Do not adjust choices after test results.
4. Emit the existing `asr.raw_predictions`, `asr.per_unit_metrics`, `asr.aggregate`, `asr.shortlist` quartet, plus receipts, failure ledger, paired analysis and an executed `asr_a0_a5_colab_t4.ipynb` notebook. The Colab notebook is the execution record for this run; a second execution through `01a` is not required. Incomplete validation emits `no_selection` and partial status, never a ranked winner. Preserve historical roots. No synthetic/fallback metrics or partial winner.

### Acceptance

- If every currently scorable row qualifies, matrix contains 6 × 507 validation and 6 × 1,155 test evaluations. Otherwise reconcile every missing row with an ID and reason; do not claim complete coverage.
- A0–A5 dispatch from registry, pinned versions/checkpoints, deterministic run config and measured resource preflight. No silent CPU substitution for GPU candidates.
- Validation/test isolation, resume identity, WER/CER denominators, failure behavior and downstream `01b` shortlist compatibility have focused tests.
- `docs/BENCHMARK.md` contains actual commands, hardware, counts, status and results only after execution. Test remains labeled diagnostic.

The existing outer plan `plans/260921-1943-scientific-benchmark-pipeline/` covers the broader multimodal roadmap; this scoped plan supplies its ASR implementation slice. New work must preserve extensive unrelated dirty files in the nested repo.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Qualify full corpus and freeze evaluation contract](./phase-01-qualify-full-corpus-and-freeze-evaluation-contract.md) | Complete for diagnostic scope; waveform duplicates unverified |
| 2 | [Candidate adapters and resource preflight](./phase-02-candidate-adapters-and-resource-preflight.md) | In progress |
| 3 | [Resumable notebook runner and artifact integration](./phase-03-resumable-notebook-runner-and-artifact-integration.md) | In progress |
| 4 | [Execute full validation and test diagnostic report](./phase-04-execute-full-validation-and-test-diagnostic-report.md) | Pending |

## Dependencies

Phases run 1 → 2 → 3 → 4. Adapter preparation may overlap data validation, but test inference waits for a validation-only frozen selection receipt. Existing historical D2 artifacts and the 20-WAV pilot do not qualify this full cohort.

References: [TED-LIUM 3 paper](https://arxiv.org/abs/1805.04699), [TensorFlow Datasets release3 card](https://www.tensorflow.org/datasets/catalog/tedlium), [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper), [WhisperX](https://github.com/m-bain/whisperX), [Distil-Whisper checkpoint](https://huggingface.co/distil-whisper/distil-small.en).

## Unresolved questions

None for planning. GPU, storage, model weights and runtime are measured preflight gates.
