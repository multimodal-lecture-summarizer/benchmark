---
phase: 4
title: "Validate pilot and benchmark readiness"
status: completed
priority: P1
dependencies: [1, 2, 3]
---

# Phase 4: Validate pilot and benchmark readiness

## Overview

Execute a small, bounded validation-only pilot to prove that the prepared notebooks, data contract and artifact receipts work together. Decide GO or BLOCKED for a later official RQ1 benchmark.

## Requirements

- Pilot uses only a predeclared validation subset; final-test labels and predictions remain sealed.
- Separate `dry-plan`, diagnostic real execution and official full evidence. A successful notebook cell is not a scientific RQ1 claim.
- Record commands, exit codes, run IDs, source/config hashes, per-unit predictions/failures and resource use.

## Architecture

Use a dedicated diagnostic artifact namespace and executed-copy notebook. Verify `00a`–`00c` D2/source receipts first, then run `04a` and `04b` on the same validation units with a bounded model/feature budget. The manifest executor validates prerequisites and declared outputs. Report each node's status and reason, preserving historical outputs unchanged.

## Related Code Files

- Execute: `experiments/notebooks/run_experiments.ipynb` or `benchmarks/scripts/execute_all_notebooks.py` with explicit notebook/profile/artifact root.
- Review: `experiments/notebooks/diagnostics/rq1_dataset_qualification.ipynb`, `experiments/notebooks/00a_*.ipynb`, `00b_*.ipynb`, `00c_*.ipynb`, `04a_*.ipynb`, `04b_*.ipynb`.
- Tests: `tests/test_notebook_executor.py`, `tests/test_dataset_contracts.py`, `tests/test_endpoint_eligibility.py` and new chapter-specific tests.

## Implementation Steps

1. Run focused source/rights, GT, split, endpoint and runner contract tests. Prove the shared loader excludes all final-test IDs in pilot mode regardless of manifest ordering; preserve failures in the executed diagnostic notebook.
2. Validate a dry-plan for exact `00a`–`00c` and `04a`–`04b` dependencies, then execute validation-only diagnostic cells. Check output artifacts/receipts with existing validator; verify complete denominators.
3. Inspect at least a few source-video/chapter boundary pairs and predictions. Test same-course leakage, missing modality, unavailable video, corrupted GT, incorrect duration, empty predictions, ±3-second collar edges and stale cache rejection.
4. Review resource use and initial error modes. Pilot results may determine a sample-size calculation but cannot change the frozen final-test set or be published as final performance.
5. Write a GO/BLOCKED ledger tied to evidence. GO requires rights, GT, D2, same-unit features, real candidate availability and reproducible notebook runs. If any item fails, name the blocker and stop before full benchmark.

## Success Criteria

- [ ] Focused tests pass or failures are explicitly listed; no falsified success from skipped cells.
- [ ] One executed diagnostic notebook and receipts prove the small validation-only chain; final-test unit IDs are absent from inputs, cache, predictions and selection metrics.
- [ ] Raw predictions, failure denominator, hashes and run lineage are inspectable and consistent.
- [ ] Pilot confirms primary ±3-second collar F1 and secondary metric outputs without promoting pilot uncertainty estimates to official findings.
- [ ] GO/BLOCKED decision states dataset, rights, GT, compute and model readiness separately. No full-DAG or RQ1 hypothesis claim is made.

## Risk Assessment

An apparent pass on historical/stub artifacts is possible unless run identity and source hashes are checked. Resource or access failures must stay visible as blocked evidence, not trigger synthetic data or fallback GT. Broaden tests only where a shared manifest/receipt contract changed.
