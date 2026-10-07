# D2 Frozen Ground Truth Reconciliation & Dependent Runners Milestone

**Date**: 2026-09-25 23:55  
**Severity**: Milestone  
**Component**: D2 Ground Truth Contract, Stage Benchmark Helpers, 01a/01b ASR, Group 02 & Group 07 Validation  
**Status**: Completed; Plan 260925-2304-d2-frozen-gt-runners verified and closed

## What Happened

Completed execution of plan `260925-2304-d2-frozen-gt-runners`. Key milestones achieved:
1. Reconciled TED-LIUM 3 D2 frozen manifest by populating real verbatim manual transcripts from HuggingFace Arrow tables (`validation/data-00000-of-00001.arrow` and `test/data-00000-of-00001.arrow`) across all 20 frozen units. Eliminated empty `reference_text` placeholders and enforced strict non-empty assertions in `phase2_freeze_tedlium.py`.
2. Hardened `load_eligible_units` in `experiments/scripts/stage_benchmark_helpers.py` to enforce endpoint-specific scientific selection gating against `dataset.endpoint_matrix`. Notebooks targeting visual or QA endpoints fail closed with descriptive `RuntimeError` rather than crashing on unsupported modalities.
3. Executed real benchmark runs through the clean Jupyter notebook kernel executor:
   - `01a_asr_model_benchmark`: 20 units evaluated on `faster-whisper-tiny.en` (WER 0.1628) and `faster-whisper-base.en` (WER 0.1919). Real predictions, metrics, aggregates, and shortlist receipts generated.
   - `01b_asr_preprocessing_ablation`: Evaluated 3 decoding presets (`default_greedy`, `beam5`, `beam5_temp0.2`), selecting `beam5` (WER 0.1628) and generating frozen configuration and receipts.
4. Validated fail-closed boundaries for downstream stages:
   - Group 02 visual benchmarks (`02a` scene boundary, `02c` OCR) refuse audio-only datasets cleanly.
   - Group 07 Pareto and error-propagation runners (`07a`, `07b`) refuse execution when upstream stage aggregates or shortlists are missing.
5. Ran full test suite: 302 tests pass, exactly 2 pre-existing baseline failures preserved, 0 regressions.

## Evidence

- `phase2_freeze_tedlium.py`: Re-generated 00c characterization bundle with SHA-256 `6ffcc78cf6218dc1914a2ccdcacde6d978671d2db34d4738c207ca3056b0ec10`. All 20 units contain non-empty manual transcripts.
- `tests/test_phase2_tedlium_d2.py`: 3/3 passed.
- `tests/test_phase1_stage_smoke_runners.py`: 6/6 passed.
- `01a_asr_model_benchmark`: Generated `asr.raw_predictions.json`, `asr.per_unit_metrics.json`, `asr.aggregate.json`, `asr.shortlist.json` + receipts in `experiments/outputs/phase2_tedlium_d2/official/full/payloads/` and executed notebook in `experiments/outputs/executed_notebooks/official/full/01a_asr_model_benchmark.ipynb`.
- `01b_asr_preprocessing_ablation`: Generated `asr.ablation_predictions.json`, `asr.ablation_metrics.json`, `asr.frozen_configuration.json` + receipts and executed notebook in `experiments/outputs/executed_notebooks/official/full/01b_asr_preprocessing_ablation.ipynb`.
- Group 02 validation: `run_scene_boundary_benchmark` fails closed with `"no scientifically eligible frozen units for endpoint in ..."`.
- Group 07 validation: `07a_efficiency_pareto` blocked before execution by `execute_all_notebooks.py` due to missing required upstream aggregates.
- Pytest suite: 302 passed, 2 pre-existing baseline failures (`test_d2_rejects_validation_final_test_leakage[source]` and `test_d15_real_data_only_no_mocks_across_all_notebooks`).

## Key Decisions

1. **Extraction of Real GT from Arrow Tables**: Extracted verbatim manual transcripts directly from the existing Arrow partitions on disk, normalizing `<>` stems to match WAV file names. No synthetic transcripts or mocks introduced.
2. **Endpoint Matrix Gating in Stage Helpers**: Evaluated dataset eligibility strictly against `dataset.endpoint_matrix`. Preserves backward compatibility when `dataset.endpoint_matrix` is absent in legacy test fixtures.
3. **No Promotion of Test/Smoke Fixtures**: Smoke test runners and fixtures remain strictly segregated from official evidence namespaces. Ineligible visual endpoints are marked as blocked rather than falsely marked as passing.

## Verification & Status

All success criteria for Plan `260925-2304-d2-frozen-gt-runners` across all 5 phases are met. Harness reports written:
- `plans/260925-2304-d2-frozen-gt-runners/reports/harness/context-snippets.json`
- `plans/260925-2304-d2-frozen-gt-runners/reports/harness/risk-gate.json`
- `plans/260925-2304-d2-frozen-gt-runners/reports/harness/verification.json`
- `plans/260925-2304-d2-frozen-gt-runners/reports/harness/review-decision.json` (PASS, score 9.5/10)
