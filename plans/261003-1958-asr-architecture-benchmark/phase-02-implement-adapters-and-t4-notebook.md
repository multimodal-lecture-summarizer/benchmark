---
phase: 2
title: "Implement adapters and T4 notebook"
status: in_progress
effort: ""
---

# Phase 2: Implement adapters and T4 notebook

## Overview

Build one Colab T4 notebook and six adapters for the new architecture matrix. Keep the old Whisper-heavy diagnostic runnable and its artifacts isolated.

## Implementation Steps

1. Add a separate registry/adapter dispatch for the new A0–A5 identities; do not mutate existing diagnostic candidate definitions or receipts.
2. Share canonical audio loading, metric normalization, resume, failure ledger, and split-safe selection logic where contracts match. Add model-specific adapters for Transformers CTC, NeMo CTC/RNNT, FunASR Paraformer, and Qwen3-ASR.
3. Build one new notebook that installs isolated pinned environments as needed, downloads immutable snapshots, runs resource preflight and six real inferences, then launches validation and native test sequentially.
4. Freeze source/config/dependency identities and atomically checkpoint each attempt. Ensure every missing candidate-unit has an explicit reason.

## Success Criteria

- [ ] Notebook has one top-to-bottom path and refuses full work if a probe fails.
- [ ] Runner emits 6 × 507 validation attempts and, after selection receipt, 6 × 1,155 diagnostic test attempts or explicit failures.
- [ ] Existing A0–A5 diagnostic artifacts remain readable with their original identities.
