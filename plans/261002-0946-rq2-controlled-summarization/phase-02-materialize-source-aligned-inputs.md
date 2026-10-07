---
phase: 2
title: "Materialize source aligned inputs"
status: pending
priority: P1
dependencies: [1]
---

# Phase 2: Materialize source aligned inputs

## Overview

Create paired, source-linked text inputs first: transcript segments and predicted temporal structure. Join visual evidence only for records eligible for S4.

## Requirements

- Reuse qualified ASR/RQ1 artifacts when available. For S3, a frozen source-only structure predictor selected on development data is sufficient; RQ1 official D2 or chapter GT is not a prerequisite. Record its algorithm, revision and source IDs.
- Keep predicted temporal structure (C5 if eligible, otherwise a frozen source-only predictor) distinct from reference/oracle chapters. TIB keyframe timestamps are not automatically semantic chapter ground truth; validate their annotation meaning before calling S2 oracle. S2 is appendix diagnostic only if the predeclared feasibility rule and semantics both hold; VISTA S2 is N/A.
- Require real aligned slide/OCR/keyframe evidence only for S4. Never create placeholder frames or silently copy transcript into missing reference fields.

## Architecture

Declared RQ2 cohort + source-bound text receipts → paired S1/S3 input package. Optional reference and visual pointers are attached only when present; availability flags govern each metric/arm.

## Related Code Files

- Reuse/modify as warranted: `experiments/scripts/artifact_enrichment.py` and `benchmarks/models/chaptering.py`. The former generic `dataset_contracts.py` module was removed on 2026-10-07; validate RQ2's source IDs, split, provenance and leakage in the task-specific input package and notebook receipt.
- Likely create: `experiments/scripts/rq2_materialize_inputs.py`; focused contract tests under `tests/`.
- Read-only precedent: RQ1 input receipt and cohort-split guards; do not assume their current dirty work is complete.

## Implementation Steps

1. Define and validate the per-talk package schema, including identity hashes, source feature revisions, predicted-vs-oracle field separation and reference pointer provenance.
2. Join eligible records to real transcript segments by stable source ID and timebase. Join slide/visual artifacts only for S4-eligible records; check attempted joins and report unmatched or misaligned records.
3. Import eligible predicted chapters from RQ1 or define a deterministic source-only temporal segmentation on development records, freeze it, and apply identically across held-out records. If neither is available, mark S3 `not_run`; do not use GT as a substitute.
4. Record ASR quality evidence separately from nonempty-transcript checks. If no gold transcript exists, report WER as unverified and perform a declared transcript quality audit.
5. Emit package manifest, per-modality availability, exclusion ledger and validation receipt.

## Success Criteria

- [ ] Every admitted S1/S3 package has source-bound transcript and predicted-structure provenance; reference linkage is required only for reference-dependent metrics.
- [ ] No GT boundary is passed to predicted variants; no placeholder visual or transcript-as-reference fallback.
- [ ] Source IDs, timestamps, hashes and split match across each modality.
- [ ] Missing or unverified upstream evidence blocks only the affected endpoint/variant with a reason.

## Risk Assessment

RQ1 cohort may not transfer to TIB. A frozen source-only predictor can unblock S3. Missing visual data blocks S4 only; do not call an oracle comparison predicted performance.
