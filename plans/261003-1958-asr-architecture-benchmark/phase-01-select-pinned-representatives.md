---
phase: 1
title: "Select pinned representatives"
status: in_progress
effort: ""
---

# Phase 1: Select pinned representatives

## Overview

Freeze six exact model revisions, dependencies, inference policies, and hardware lanes before implementing adapters. Use published model cards and local compatibility checks; do not infer T4 readiness from checkpoint size alone.

## Implementation Steps

1. Record immutable Hugging Face revision SHA (and weight digest where practical) for A0–A5. Confirm English input/output and 16 kHz compatibility.
2. Pin library versions in compatible isolated Python environments. Include model/toolkit licenses and the actual Colab T4 CUDA profile in the receipt.
3. Specify sample handling, chunking limits, language setting, CTC/RNNT decode mode, Paraformer VAD/punctuation policy, Qwen generation settings, and any CPU/GPU exceptions. Use identical canonical audio and score raw transcripts with the existing WER/CER normalization.
4. Check TED-LIUM overlap/provenance limitations and preserve the existing diagnostic label. Lock a fresh candidate manifest before inference.

## Success Criteria

- [ ] Six pinned snapshots and package versions are recorded with independent model-family labels.
- [ ] T4 feasibility is measured for each lane, including load, inference, memory and disk; blocked models remain explicit failures.
- [ ] No A6 duplicates Paraformer or modern ASR.
