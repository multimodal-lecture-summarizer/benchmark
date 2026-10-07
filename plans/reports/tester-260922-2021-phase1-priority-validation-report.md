# Test Report — 2026-09-22 — Phase 1 Priority

---
scope: executor, contracts, generator, runners 00a-00c
mode: diff-aware targeted
status: partial-pass
---

## Summary

- Targeted implementation and real group-00 smoke pass.
- Blocking consistency gap: checked-in 22 notebooks drift from generator output.
- Coverage below project 80% expectation.

## Diff-aware Selection

- Mapped: `benchmarks/scripts/execute_all_notebooks.py` -> `tests/test_notebook_executor.py`, `tests/test_phase1_priority_runners.py`.
- Mapped: manifest/contracts/registry -> `tests/test_research_contracts.py`, `tests/test_registry_loader.py`.
- Mapped: notebook generator -> `tests/test_notebook_generator.py`.
- Mapped: runners `environment_preflight`, `probe_dataset_feasibility`, `profile_dataset` -> `tests/test_phase1_priority_runners.py`.
- Full repo suite not run; requested targeted validation only.

## Test Results Overview

- Syntax: PASS, six Phase 1 Python modules compiled.
- Targeted pytest: 55 passed, 0 failed, 0 skipped; 6.77s.
- Slowest test: direct/module entrypoint equivalence, 3.27s.
- No flaky rerun performed.

## Coverage Metrics

| Metric | Value | Threshold | Status |
|---|---:|---:|---|
| Statements | 76.55% | 80% | FAIL |
| Branches | 70.00% | 70% | PASS |
| Combined branch-aware | 74.77% | 80% | FAIL |
| Functions | N/A | 80% | NOT MEASURED |

Lowest scoped files: registry loader 62%, executor 71%, generator 75% combined branch-aware coverage.

## CLI Equivalence

- Direct and module `--dry-plan --group 00 --profile smoke`: exit 0 both.
- Stdout byte-identical; SHA-256 `abe2b16fa79461e5ac0299c79b5d783c294e1c1fb0c7ec6712a3654f2816169e`.
- Existing pytest also validates `--list` equivalence and 22 selected notebooks.

## Official Smoke Group 00

- First sandbox attempt: environment-only failure, `SetFileSecurity: Access is denied` during Jupyter kernel startup.
- Approved outside-sandbox rerun: PASS, exit 0.
- `00a`: 4.0s; `00b`: 48.6s; `00c`: 7.1s.
- Real local evidence: 4 datasets, 64 files.
- Outputs: 3 executed notebooks, 3 output run manifests.
- Artifacts: 17 payload receipts, 3 artifact run manifests.
- All receipts: `official`, `smoke`, `real`; valid 64-char SHA-256; positive record count and denominator.
- Feasibility payload reports `network_used=false` for all 4 datasets.
- Limitation: no packet/socket interception used; no-network claim validated from code search and emitted receipts, not external network tracing.

## Critical Issues

1. Generator check FAIL: `python -m experiments.scripts.generate_refactored_notebook --check` reports all 22 notebooks would change. Sample diff is Markdown hard-break normalization (`two spaces` to `<br>`), but byte-stability/source provenance gate remains failed.
2. Targeted statement/combined coverage below 80%; executor error/resume/execution branches and registry loader CLI/load failures remain under-tested.

## Recommendations

1. High: regenerate all 22 notebooks from current generator, or revert generator formatting change; rerun `--check` until exit 0.
2. Medium: add executor tests for timeout/kernel failure, dependency blocking, resume success/hash mismatch, artifact validation error branches.
3. Medium: add registry loader malformed/missing-file and CLI tests; generator CLI/check success tests.
4. Low: optionally enforce no-network with socket blocking/telemetry during smoke, not only runner-reported `network_used=false`.

## Unresolved Questions

- Is the `<br>` normalization intentional? If yes, generated notebooks must be refreshed before Phase 1 gate can close.
- Does project require 80% per-file, total statement coverage, or combined branch-aware coverage?
