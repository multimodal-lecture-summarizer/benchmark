---
title: "ASR architecture benchmark on TED-LIUM 3"
description: "Compare six distinct ASR architecture lanes on the frozen TED-LIUM 3 evaluation cohort using one Colab T4 notebook."
status: in_progress
priority: P1
branch: ""
tags: [research, benchmark, asr, model-families, t4]
blockedBy: []
blocks: []
created: "2026-10-03T13:00:47.273Z"
createdBy: "ck:plan"
source: skill
---

# ASR architecture benchmark on TED-LIUM 3

## Overview

This is the main ASR **architecture** comparison requested on 2026-10-03. It replaces the A0–A5 Whisper-heavy matrix as the main scientific question. The old six-pipeline probe remains a separate engineering diagnostic; its receipts, candidate IDs, and results must not be relabeled or merged into this run.

| Lane | Representative checkpoint | Architecture | Comparison role |
| --- | --- | --- | --- |
| A0 | `Systran/faster-whisper-base` | Whisper encoder-decoder via CTranslate2 | Common baseline; run GPU float16 on the same T4 as the other lanes |
| A1 | `facebook/wav2vec2-large-960h-lv60-self` | Self-supervised Wav2Vec2 encoder + CTC | Non-Whisper encoder/CTC baseline |
| A2 | `nvidia/stt_en_fastconformer_ctc_large` | FastConformer + CTC | Convolution/attention encoder with CTC |
| A3 | `nvidia/stt_en_fastconformer_transducer_large` | FastConformer + RNNT | Compare transducer decoding with A2's CTC family |
| A4 | `funasr/paraformer-en` | Paraformer, non-autoregressive | Parallel decoding alternative |
| A5 | `Qwen/Qwen3-ASR-0.6B` | Modern multilingual generative ASR | Contemporary model on English TED-LIUM; force English when supported |

These are model *representatives*, not architecture-only causal ablations: training data, parameter counts and toolchains differ. Record them and avoid attributing a WER gap solely to architecture. A2/A3 are the nearest controlled pair, but their training/checkpoints must still be checked. A4 is already Paraformer and A5 already modern ASR, so the proposed A6 repeats an occupied lane; add A6 only after a distinct research question and a T4 probe justify it.

Reuse the existing frozen 507 validation / 1,155 native-test unit IDs and metric definitions, but create a **new registry namespace, source/config digests, artifact root, selection receipt, and notebook**. Keep native test diagnostic because earlier work accessed test aggregates. Run all six on validation and freeze selection before native-test inference. One notebook runs this task; no second 01a notebook.

The checkpoint revisions, Python dependency pins, local cache paths, preprocessing/decoding settings, and per-model T4 resource limits are Phase 1 deliverables. No full validation starts until every adapter passes one real waveform and the run identity is frozen. Separate environments may be needed for NeMo, FunASR, and Qwen; one notebook may orchestrate them. Do not silently replace a failed lane with another architecture.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Select pinned representatives](./phase-01-select-pinned-representatives.md) | In progress: revisions and package locks recorded; T4 runtime feasibility awaits Colab probe |
| 2 | [Implement adapters and T4 notebook](./phase-02-implement-adapters-and-t4-notebook.md) | In progress: registry, workers, orchestration, notebook and bundle prepared; real probe remains |
| 3 | [Probe and freeze](./phase-03-probe-and-freeze.md) | Pending |
| 4 | [Run validation and diagnostic test](./phase-04-run-validation-and-diagnostic-test.md) | Pending |

## Dependencies

The earlier [Whisper-heavy A0–A5 plan](../261003-1346-asr-candidate-full-corpus-benchmark/plan.md) provides a qualified cohort and diagnostic infrastructure. Its A0–A5 labels refer to different systems and are not reusable as result identities here.
