---
phase: 5
title: "Execute eligible RQ1 and report"
status: pending
priority: P1
dependencies: [4]
---

# Phase 5: Execute eligible RQ1 and report

## Overview

Execute the official RQ1 comparison only on the cohort that passed Phases 2–4. If any gate fails, publish the named blocker and preserve the completed MIT001 diagnostic as the scoped result.

## Requirements

- Same source units, split, modality availability and budget for each declared comparison; failed and missing predictions stay in the denominator.
- Validation selects configuration; a previously frozen configuration evaluates final test once. No reruns on final test to tune thresholds.
- Report descriptive and uncertainty results at appropriate independent group level; use `no_selection` when evidence cannot support a winner.

## Architecture and related files

- Reuse nested `benchmarks/scripts/run_chaptering_benchmark.py`, `benchmarks/scripts/run_chaptering_modality_ablation.py`, `experiments/notebooks/04a_chaptering_benchmark.ipynb`, `04b_chaptering_modality_ablation.ipynb`, `experiments/scripts/rq1_source_feature_extraction.py` and receipt/report helpers.
- Generate a new official artifact namespace and report from raw per-unit predictions; retain the MIT001 diagnostic namespace unchanged.

## Implementation Steps

1. Run preflight, D2 validation, 04a then 04b on eligible validation units. Inspect source/hash/GT/feature identity, output rows and failures; freeze selection.
2. Run the sealed final test once with the frozen selection and complete run manifest. If a real C5/C6 checkpoint is absent, retain `not_run` for that candidate without blocking valid baseline/heuristic comparisons.
3. Generate paired per-unit score tables, group-aware confidence intervals and corrected comparisons only when independent group count permits. Include ablation, attrition, compute, negative results and limitations.
4. Reconcile notebook outputs, raw artifacts, endpoint matrix and master-plan claim; state whether outcome is `official_result`, `diagnostic_complete` or a named `blocked_*` status.

## Success Criteria

- [ ] Every reported metric traces to raw predictions and a frozen D2/unit list; no manually copied aggregate substitutes for an artifact.
- [ ] All declared variants have a real result or explicit `not_run`/`failed` reason; no silent modality downgrade or test-set retuning.
- [ ] Final report distinguishes one-course MIT001 descriptive evidence from any newly eligible independent RQ1 result, including exact rights and split limits.

## Risk assessment

Sparse eligible groups can make CIs/tests unstable; use descriptive reporting and `no_selection`. Compute or media failure is reported with denominator rather than hidden by replacement data.
