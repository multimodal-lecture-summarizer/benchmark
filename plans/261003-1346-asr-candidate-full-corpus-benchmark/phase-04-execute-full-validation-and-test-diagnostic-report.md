---
phase: 4
title: "Execute full validation and test diagnostic report"
status: pending
priority: P1
dependencies: [1, 2, 3]
effort: "measured full-run duration; potentially multiple GPU sessions"
---

# Phase 4: Execute full validation and test diagnostic report

## Overview

Execute all six candidates on all qualified native validation and test segments, retain the executed Colab T4 notebook and publish an honest diagnostic comparison from raw receipts. Do not claim official clean-holdout evidence.

## Requirements

- Run full validation first. Check six-candidate completeness and compute validation micro WER/CER, per-talk WER, failure coverage and same-profile efficiency. Freeze ranking/selection and its hashes before any new test inference.
- Run full native test on every A0–A5 after lock, under its own artifact root/run ID bound to the validation selection receipt. Keep all six rows, including composites, in the result matrix. Do not tune candidates after inspecting test outputs or overwrite validation receipts.
- Compute paired candidate deltas only on the intersection of valid IDs; report missing pairs and both paired denominator and full cohort denominator. Use talk/source-grouped uncertainty; eight validation and eleven native-test source talks in current EDA limit inference strength.
- Compare A5 directly to A1 for denoise effect; A4 reports alignment overhead; all candidates retain corpus quality metrics. Name a **validation-ranked candidate** only after complete validation coverage. The exposed native test supplies a diagnostic comparison, never an independent final winner claim, even when complete.
- Recompute aggregates from raw predictions and spot-check reference/audio alignment. Validate receipts, notebook outputs, exact commands, environment and model hashes; rerun only failed shards after root-cause fixes.

## Architecture

New timestamped diagnostic root under `experiments/outputs/diagnostic/` contains separate validation and native-test subroots plus a parent index; each subroot keeps its own checkpoint/raw/metric/aggregate/receipt data. The notebook summarizes those measured artifacts with split counts, failure ledger, per-candidate table, per-talk paired table, plots and limitations. Historical `experiments/outputs/phase2_tedlium_d2/official/full/` remains untouched. `docs/BENCHMARK.md` points to the new run and clearly marks it diagnostic.

## Related Code Files

- Execute/save outputs in `multimodal-lecture-summarizer/experiments/notebooks/asr_a0_a5_colab_t4.ipynb` and the separate validation/native-test diagnostic roots. Do not rerun `01a` solely to satisfy this plan.
- Update `multimodal-lecture-summarizer/docs/BENCHMARK.md` after measured results; add a small machine-readable report generator under `experiments/scripts/` only if notebook analysis would duplicate runner logic.
- Tests: focused ASR, endpoint, executor, notebook and shared-caller suites; preserve unrelated dirty work.

## Implementation Steps

1. Re-run preflight on actual execution hardware. Record disk reserve, CUDA, package/weight versions, cohort hash and expected 6×N matrix.
2. Execute validation shards; reconcile every ID and candidate. Lock candidate choices and create a validation-only receipt.
3. Execute test shards once; resume only from identity-matching checkpoints. Never change the frozen protocol based on test output.
4. Generate WER/CER, same-profile RTF, per-talk paired deltas/intervals, exclusions and failure tables from raw rows. Flag A4/A5 composite lanes.
5. Validate notebook, artifact hashes and exact denominators; update BENCHMARK.md with measured evidence and known historical test exposure.

## Success Criteria

- [ ] All six A0–A5 have results for every retained validation/test unit, or incomplete status is explicit and no winner is selected.
- [ ] If no extra media exclusions occur, validation has 3,042 candidate-unit attempts and test 6,930; otherwise all denominator changes are reconciled by ID.
- [ ] Executed notebook contains visible real tables/plots, run receipts, commands and candid diagnostic label.
- [ ] Raw-to-aggregate recomputation matches; relevant tests pass; no historical artifact overwritten.

## Risk Assessment

Full run cost and VRAM are unknown until preflight. Resource shortage produces a resumable partial run and a blocker report, not inferred results. Native test exposure prevents an independent final-test claim even when all 6,930 attempts finish.
