---
phase: 5
title: "Close Full DAG Readiness and Evidence Ledger"
status: completed
priority: P1
dependencies: [phase-01-enforce-fail-closed-endpoint-eligibility, phase-02-repair-focused-regression-coverage, phase-03-reconcile-group-02-entries, phase-04-reconcile-group-07-dependencies]
---

# Phase 5: Close Full DAG Readiness and Evidence Ledger

## Overview

Reconcile the complete 22-node manifest graph against actual artifacts and classify every node. The present full dry-plan proves manifest coverage and runner presence, not that a full DAG ran. Execute the official full DAG only if all required dataset × endpoint pairs, GT contracts and upstream artifacts are eligible and ready.

## Requirements

- Functional: Produce a per-node evidence ledger and either a validated full-DAG run or an explicit blocked decision with exact prerequisites.
- Non-functional: Keep `dry-plan`, `smoke`, `real`, `not_run`, `blocked` and `failed` as distinct statuses; preserve run identity, receipts, hashes and resumability rules.

## Architecture

Use `benchmarks/scripts/execute_all_notebooks.py` and `experiments/notebooks/notebook_manifest.yaml` as DAG sources. Reconcile each node's declared `requires`/`produces` against artifact receipts, endpoint GT eligibility and output namespace. The final ledger belongs in the current benchmark progress/audit record, not a duplicate status document.

## Related Code Files

- Read: `benchmarks/scripts/execute_all_notebooks.py`, `experiments/notebooks/notebook_manifest.yaml`
- Read: all `experiments/outputs/` receipts, run manifests, endpoint matrices and frozen manifests
- Update only the authoritative existing progress/audit record identified from the repo; do not overwrite journal history.

## Implementation Steps

1. Run full dry-plan and verify all 22 nodes, topological ordering, runner source hashes, budgets and artifact dependency edges.
2. Build a per-node ledger with status (`PASS`, `BLOCKED`, `NOT_RUN`, `FAILED`), profile/namespace, command, upstream artifacts, endpoint/GT gate, receipt and output hash.
3. Reconcile actual current outputs. Include `00a`–`01b` real artifacts separately from group dry-plan and smoke-test evidence.
4. Check whether each required stage has scientifically eligible datasets/GT and compatible upstream evidence. Use the existing Dataset Coverage Expansion plan and further source/annotation work where relevant; do not infer universal eligibility from TED-LIUM D2.
5. If and only if all required endpoint/data gates pass, execute full DAG in one official namespace and validate each artifact/receipt before marking nodes PASS.
6. If required coverage remains missing, record exact missing endpoint pairs and datasets/GT evidence, mark full scientific DAG blocked, and leave this phase pending until prerequisites are satisfied. Do not close the plan by counting a dry-plan as a full run.
7. Reconcile the older plan's completion claims in the evidence report and update the authoritative progress source with verified current status.

## Success Criteria

- [x] Full dry-plan and per-node ledger reconcile all manifest nodes and dependency edges.
- [x] Every node has a verified execution status; no unlisted node is implicitly counted complete.
- [x] Any official full-DAG claim is backed by matching receipts, source/config/dependency hashes, endpoint eligibility and validated output artifacts across all required nodes.
- [x] If the DAG remains blocked, exact data, released-GT, rights and upstream artifacts required to resume are named, and no full-DAG completion is claimed.
- [x] Previous plan/journal statuses are corrected or explicitly superseded by current evidence without erasing historical results.

## Risk Assessment

The full DAG may remain scientifically blocked after code/test repairs because several visual and downstream endpoint datasets lack eligible released GT. Report this as a data-coverage gate, not a runner pass or a compute failure.
