---
phase: 3
title: "Reconcile Group 02 Entries"
status: completed
priority: P1
dependencies: [phase-01-enforce-fail-closed-endpoint-eligibility, phase-02-repair-focused-regression-coverage]
---

# Phase 3: Reconcile Group 02 Entries

## Overview

Recheck each group 02 entry independently after the fail-closed selector and its tests are in place. TED-LIUM is audio-only; its D2 ASR eligibility must not be presented as visual eligibility. The pending IIIT-CVID coverage plan may supply OCR labels only after its own provenance, rights and GT gates pass.

## Requirements

- Functional: Reconcile `02a_scene_boundary_benchmark`, `02b_keyframe_selection_benchmark`, `02c_ocr_benchmark` and `02d_visual_caption_benchmark`.
- Non-functional: Use isolated smoke/validation roots and preserve official evidence; no synthetic fixture enters official namespace.

## Architecture

Group dry-plan verifies manifest membership/order and runner presence. Per-run validation then checks each node's own required artifacts and endpoint eligibility. `02a` and `02c` require independently eligible visual data/labels; `02b` and `02d` also require scene/keyframe upstream outputs. A blocked upstream must propagate as blocked, not as success.

## Related Code Files

- Read: `experiments/notebooks/notebook_manifest.yaml` entries `02a`–`02d`
- Read: `benchmarks/scripts/run_scene_boundary_benchmark.py`, `run_keyframe_selection_benchmark.py`, `run_ocr_benchmark.py`, `run_visual_caption_benchmark.py`
- Read: executor and group 02 tests; D2 manifest, endpoint matrix and receipts.

## Implementation Steps

1. Capture current group 02 dry-plan IDs/order/source hashes and verify dependency edges against the manifest.
2. In an isolated artifact root, exercise each runner with audio-only D2 inputs and assert it blocks before model execution or rejects missing prerequisites.
3. Validate dependency propagation: `02b` cannot run without `scene.raw_predictions`; `02d` cannot run without `keyframe.raw_predictions`.
4. If a dataset becomes D2 eligible for a visual endpoint, execute that entry with real frozen units and released GT, then validate all required outputs, receipts and metric denominators.
5. Record one row per entry: status, command, eligible dataset/endpoint, upstream artifacts, receipt/hash, denominator and failure/block reason.

## Success Criteria

- [x] All four group 02 entries have explicit, evidence-backed outcomes; dry-plan alone is not called validation pass.
- [x] Audio-only TED-LIUM cannot enter any visual endpoint runner.
- [x] Missing upstream data blocks downstream group entries before execution.
- [x] Any official visual metric traces to eligible frozen units and compatible released GT; otherwise entry remains `BLOCKED`/`NOT_RUN`.

## Risk Assessment

Visual dataset expansion may be delayed by license or annotation provenance. Keep technical runner validation separate from scientific eligibility and do not add synthetic GT to close the gap.
