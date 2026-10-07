---
phase: 4
title: "Reconcile Group 07 Dependencies"
status: completed
priority: P1
dependencies: [phase-01-enforce-fail-closed-endpoint-eligibility, phase-02-repair-focused-regression-coverage, phase-03-reconcile-group-02-entries]
---

# Phase 4: Reconcile Group 07 Dependencies

## Overview

Validate both group 07 runners against their complete manifest prerequisites. `07a` needs aggregates across ASR, scene, keyframe, OCR, caption, detection, tracking, chapter, summary, retrieval and QA; `07b` needs stage shortlists and raw predictions plus the `07a` selection output. With only TED-LIUM ASR results, correct behavior is blocked.

## Requirements

- Functional: Verify `07a_efficiency_pareto` and `07b_error_propagation` fail before execution when required upstream evidence is absent or incompatible.
- Non-functional: Do not construct Pareto/error metrics from smoke placeholders or mismatched unit denominators.

## Architecture

Executor DAG requirements are authoritative. Runner-specific dataset selection must also honor endpoint policy. Upstream outputs must have matching run namespace/profile, validated receipts, compatible eligible IDs and metric provenance before consumption.

## Related Code Files

- Read: `experiments/notebooks/notebook_manifest.yaml` entries `07a` and `07b`
- Read: `benchmarks/scripts/run_efficiency_pareto.py`, `run_error_propagation_benchmark.py`, `execute_all_notebooks.py`
- Read: metric registry, artifact validators and upstream receipts.

## Implementation Steps

1. Capture group 07 dry-plan and list every required artifact, producing notebook, run identity and endpoint/GT denominator.
2. Run negative-path checks for `07a` with missing aggregates and `07b` with missing shortlist/raw-prediction inputs in an isolated root; assert no runner kernel starts.
3. Inspect that present upstream artifacts still block if status, hashes, schema, profile, namespace or denominators conflict.
4. When all required stage evidence exists, run `07a` then `07b` under one official run identity; validate resource telemetry, Pareto rows, perturbation inputs and propagated metrics.
5. Otherwise record the precise missing datasets, endpoint GT, stage artifacts and upstream node statuses. Keep `BLOCKED`/`NOT_RUN` instead of manufacturing complete aggregates.

## Success Criteria

- [x] Both group 07 nodes have direct fail-closed evidence for missing/corrupt inputs.
- [x] Eligible execution consumes all declared dependencies with aligned identity and denominators.
- [x] Pareto and error-propagation claims are absent when the relevant evidence is not available.
- [x] Group report distinguishes runner contract pass from scientific benchmark completion.

## Risk Assessment

A complete group 07 run cannot be inferred from group 02 alone and likely needs eligible evidence from nearly all earlier groups. Explicitly map that dataset/GT coverage gap before compute is spent.
