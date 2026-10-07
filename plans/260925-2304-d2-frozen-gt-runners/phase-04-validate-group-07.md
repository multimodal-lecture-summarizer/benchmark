---
phase: 4
title: "Validate Group 07"
status: completed
priority: P1
dependencies: [phase-01-reconcile-d2-and-ground-truth-contract, phase-02-complete-prerequisite-runners, phase-03-validate-group-02]
---

# Phase 4: Validate Group 07

## Overview

Validate efficiency/Pareto and error-propagation runners only after their declared stage aggregates, raw predictions and shortlists are present and validated. Group 07's structural dry-plan may be checked earlier, but execution depends on upstream benchmark outputs across groups 01–06.

## Requirements

- Functional: `07a_efficiency_pareto` consumes all required stage aggregates; `07b_error_propagation` consumes stage shortlists and raw predictions plus group 07a outputs.
- Non-functional: Preserve profile-specific resource measurement, failed-run accounting, metric provenance and deterministic output identity.

## Architecture

Follow manifest dependencies: `07a` requires ASR, scene, keyframe, OCR, caption, detection, tracking, chapter, summary, retrieval and QA aggregates; `07b` requires stage shortlists and selected raw predictions. Executor dependency validation must block missing evidence before the runner starts.

## Related Code Files

- Read: `experiments/notebooks/notebook_manifest.yaml` entries `07a` and `07b`
- Read: `benchmarks/scripts/run_efficiency_pareto.py`, `run_error_propagation_benchmark.py`, executor and artifact validators
- Read: group 01–06 output receipts and metric registry.

## Implementation Steps

1. Dry-plan group 07 and verify the two entries, ordering, requirements/produces, resource bounds and no undeclared implicit dependencies.
2. Run focused runner tests with valid artifacts and deliberate missing/corrupt dependencies; confirm fail-before-execution behavior.
3. Audit input aggregates for eligible IDs, compatible denominators, finite metrics, cost/latency/memory provenance and model/config identity.
4. Run group 07 smoke/integration checks with explicit smoke labeling; run official only if all declared upstream evidence is available and compatible.
5. Validate Pareto frontiers, stage shortlists and propagated error records; record blocked/not_run if any upstream is unavailable.

## Success Criteria

- [x] `07a` and `07b` dry-plan in dependency order and reject missing/corrupt upstream artifacts.
- [x] Aggregate inputs share compatible dataset/unit denominators or are explicitly partitioned by profile/task.
- [x] Efficiency claims trace to measured resource artifacts; no assumed or fabricated cost/latency values.
- [x] Group report includes receipt/hash, profile, upstream identity, per-stage status and unresolved dependencies.

## Risk Assessment

Incompatible denominators or smoke-only upstreams can produce plausible but invalid frontiers. Require explicit identity/eligibility joins and refuse mixed scientific/test evidence.
