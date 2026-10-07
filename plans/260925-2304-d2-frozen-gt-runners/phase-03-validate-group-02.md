---
phase: 3
title: "Validate Group 02"
status: completed
priority: P1
dependencies: [phase-01-reconcile-d2-and-ground-truth-contract, phase-02-complete-prerequisite-runners]
---

# Phase 3: Validate Group 02

## Overview

After D2/GT gates and runner contracts pass, validate group 02 in increasing cost: dry plan and dependency order, focused smoke/integration checks, then an official run only for eligible visual endpoints with released GT. Keep each entry's status distinct; a missing visual GT can leave an entry blocked while other eligible entries run.

## Requirements

- Functional: Validate `02a_scene_boundary_benchmark`, `02b_keyframe_selection_benchmark`, `02c_ocr_benchmark`, and `02d_visual_caption_benchmark` with their declared upstreams.
- Non-functional: Record exact command/profile/namespace, eligible dataset IDs, runner version hashes, artifact receipts and errors.

## Architecture

Executor selects group `02` from the manifest and orders by artifact dependencies. The validation chain must preserve the runner's declared semantics; inspect the live plan before execution. Tests using generated media validate plumbing only and stay `smoke`/non-scientific.

## Related Code Files

- Read: `experiments/notebooks/notebook_manifest.yaml` entries `02a`–`02d`
- Read: runner modules `benchmarks/scripts/run_scene_boundary_benchmark.py`, `run_keyframe_selection_benchmark.py`, `run_ocr_benchmark.py`, `run_visual_caption_benchmark.py`
- Read: group 02 artifact receipts, dataset registry/endpoint matrix and focused tests.

## Implementation Steps

1. Run manifest/group dry-plan and verify exact entries, topological order, runner existence, resource/network budgets and declared inputs/outputs.
2. Run the focused group 02 tests for contract failures, artifact schemas, chaining and deterministic behavior.
3. Run smoke/integration checks under a distinct smoke namespace; label fixture-backed artifacts as test-only.
4. If Phase 1 identifies eligible dataset × endpoint pairs, run only corresponding real benchmark entries with validated frozen IDs/GT and official evidence status. Do not claim group completion where entries are blocked/not_run.
5. Validate produced artifacts and receipts, then report each entry's status and metric denominator.

## Success Criteria

- [x] Dry-plan covers the expected group 02 entries in valid dependency order with all runner sources found.
- [x] Focused checks pass for declared requires/produces, artifact provenance and fail-closed behavior.
- [x] Every official result uses an eligible endpoint and released GT; smoke artifacts remain separate.
- [x] Group report lists per-entry status, eligible IDs, denominator, receipt/hash and blockers; absent GT is reported plainly.

## Risk Assessment

Scene, keyframe, OCR and caption tasks have different labels and data needs. Avoid treating one dataset's D2 status as global eligibility or using heuristic caption scores as human GT.
