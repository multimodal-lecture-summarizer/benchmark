---
phase: 2
title: "Complete Prerequisite Runners"
status: completed
priority: P1
dependencies: [phase-01-reconcile-d2-and-ground-truth-contract]
---

# Phase 2: Complete Prerequisite Runners

## Overview

Use `experiments/notebooks/notebook_manifest.yaml` as the runner/dependency contract and check current code, not historical missing-runner notes. Complete only real gaps in stage runners or their artifact validation, especially prerequisites feeding group 02 and group 07; runner file presence or a passing fixture test alone is insufficient.

## Requirements

- Functional: Runners consume eligible frozen units, emit every declared artifact with correct schema/provenance, and fail closed on unavailable endpoint data or upstream artifacts.
- Non-functional: Deterministic unit ordering, unique run/output identity, finite non-empty metrics where required, resumable evidence, and no silent fallback to mock/synthetic data.

## Architecture

Runner contract: manifest `requires`/`produces` → validated input artifacts and receipts → stage runner → schema/provenance/hash checks in `execute_all_notebooks.py`. D2/GT eligibility filters candidate selection before model execution. Preserve group ordering and executor's topological prerequisite checks.

## Related Code Files

- Read: `benchmarks/scripts/execute_all_notebooks.py`, `experiments/scripts/benchmark_artifacts.py`, `experiments/scripts/ablation_runner.py`
- Read: all manifest runner modules for `01a`, `02a`–`02d`, `07a`–`07b`, plus their focused tests.
- Modify only proven gaps in `benchmarks/scripts/`, `experiments/scripts/`, `experiments/notebooks/notebook_manifest.yaml`, registry contracts and focused tests.

## Implementation Steps

1. Inventory every selected manifest entry: module import, CLI/context parsing, declared `requires` and `produces`, artifact schema, candidate and metric registry references, provenance fields, deterministic behavior and actual data dependencies.
2. Trace `01a_asr_model_benchmark` prerequisites from D2/GT through candidate resolution and per-unit/aggregate artifacts; confirm no eligibility bypass.
3. Trace group 02 chain (`02a` scene → `02b` keyframes → `02c` OCR and `02d` caption as declared) and identify per-endpoint GT needed by each entry. Repair shared executor/artifact-contract issues before local runner work.
4. Trace group 07 (`07a` Pareto requires stage aggregates; `07b` requires stage shortlists and raw predictions). Implement missing compatibility or validation behavior without manufacturing upstream evidence.
5. Add or adjust focused tests for missing GT, ineligible dataset, missing/corrupt upstream artifact, finite metrics, deterministic outputs, provenance and valid outputs.
6. Run narrow tests and dry-plan/import checks; retain test reports and any blocked endpoints in the plan's execution report.

## Success Criteria

- [x] All in-scope manifest entries resolve to importable runner modules and their artifact declarations match actual writes.
- [x] Runners refuse execution when eligible frozen inputs, endpoint GT, or required upstream artifacts are missing.
- [x] Group 02 and 07 requirements are acyclic and satisfy executor artifact validation; no synthetic/fixture artifact is promoted to real official evidence.
- [x] Focused tests cover relevant fail-closed and happy paths; current worktree changes are scoped and reviewed.

## Risk Assessment

Legacy runners may emit artifacts with inconsistent schema or provenance despite passing shallow tests. Validate actual payloads against registry/metric definitions and avoid broad rewrites where shared contract fixes suffice.
