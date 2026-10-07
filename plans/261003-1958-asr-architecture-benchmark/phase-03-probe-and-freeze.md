---
phase: 3
title: "Probe and freeze"
status: pending
effort: ""
---

# Phase 3: Probe and freeze

## Overview

Exercise every candidate on the same real frozen validation unit on Colab T4 and freeze a reviewable pre-run contract.

## Implementation Steps

1. Verify ZIP/hash, immutable model cache snapshots, exact installed package versions, GPU availability, and free disk/VRAM.
2. Run one real inference for A0–A5, record nonempty transcripts and model load/inference time. Check audio duration and transcript decoding.
3. Review dependency isolation, language behavior, output normalization, WER contract, and source/config hashes; publish a new probe receipt.

## Success Criteria

- [ ] All six real probes pass on T4 with frozen source/config identity.
- [ ] No full validation starts from a failed, stale, or incomplete probe.
