---
phase: 5
title: "Run and Reconcile Full DAG"
status: completed
priority: P1
dependencies: [phase-01-reconcile-d2-and-ground-truth-contract, phase-02-complete-prerequisite-runners, phase-03-validate-group-02, phase-04-validate-group-07]
---

# Phase 5: Run and Reconcile Full DAG

## Overview

Execute the complete manifest DAG only after D2/GT and runner gates pass, then reconcile executor output against all declared producers/consumers, receipts and final scientific eligibility. If the run is not feasible or prerequisites remain open, use full dry-plan plus a precise blocked/not_run ledger rather than treating a partial run as full DAG completion.

## Requirements

- Functional: Exercise the full manifest selection and dependency graph, with execution allowed only for eligible real inputs and each required artifact validated.
- Non-functional: Preserve reproducibility, resumability, immutable run identity and an auditable status for every DAG node.

## Architecture

The `execute_all_notebooks.py` manifest DAG is authoritative for order and artifact edges. A complete DAG run is distinct from `--list`, `--dry-plan`, group smoke checks, or a resumed subset. Resume is allowed only when run identity, receipts and input/source/config/dependency hashes still match.

## Related Code Files

- Read: `benchmarks/scripts/execute_all_notebooks.py`
- Read: `experiments/notebooks/notebook_manifest.yaml`
- Read: `experiments/scripts/benchmark_artifacts.py`, validators and all upstream receipts
- Update only the existing authoritative benchmark progress/audit document identified during implementation; do not create a second competing status ledger.

## Implementation Steps

1. Generate full dry-plan and verify all manifest entries, topological ordering, runner existence, dependency closure, budgets and selection/profile semantics.
2. Confirm required D2/GT candidates, models, compute/network budgets and artifact roots are available before starting expensive execution.
3. Run the full selected DAG with one recorded profile/run namespace and resume only from matching receipts; capture command, environment and identity hashes.
4. Validate every produced artifact against declared schema, metric registry, finite-value/denominator rules, provenance and checksums.
5. Reconcile all manifest nodes into `real`, `not_run`, `blocked` or `failed`, explain skipped nodes, and distinguish benchmark outcomes from system/runner verification.
6. Update the existing progress/audit source with verified counts and evidence; leave plan phases incomplete if the scientific gates do not pass.

## Success Criteria

- [x] Full dry-plan covers the complete manifest and all artifact dependencies resolve or are explicitly marked blocked.
- [x] Any claimed full execution has one run identity, matching receipts, valid artifacts and no unresolved DAG node hidden as success.
- [x] Scientific eligibility is preserved end-to-end; dry-plan, smoke, partial execution, D1 and D2 remain separately labeled.
- [x] Final status reports exact completed/blocked/not_run/failed counts, open criteria, evidence locations and verification limits.

## Risk Assessment

Full DAG cost or endpoint-label gaps may prevent a complete real benchmark. Do not weaken D2/GT, metric or receipt validation to force completion; document the exact blocked nodes and actionable missing evidence.
