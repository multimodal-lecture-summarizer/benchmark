# Endpoint Gating Fail-Closed Hardening, Group 02/07 Reconcile & Full DAG Evidence Ledger

**Date**: 2026-09-26 09:15  
**Severity**: Milestone  
**Component**: Stage Benchmark Helpers, Endpoint Matrix Gate, Group 02/07 Runners, Full DAG Ledger  
**Status**: Completed; Plan 260926-0849-endpoint-gating-dag-reconciliation verified and closed

## What Happened

Completed end-to-end execution of plan `260926-0849-endpoint-gating-dag-reconciliation`:
1. **Fixed Fail-Open Endpoint Eligibility**:
   - Replaced silent fallback (`allowed_dataset_ids = None`) in `experiments/scripts/stage_benchmark_helpers.py` with strict fail-closed enforcement.
   - For `official`/`full` executions, `load_eligible_units` requires a valid `dataset.endpoint_matrix` artifact and cryptographic receipt; absence, read error, payload corruption, schema deviation, or empty matches raises `RuntimeError` immediately before model execution or unit return.
   - Defined composite runner requirements: `07b_error_propagation` requires both `asr_benchmark` and `scene_boundary_benchmark`; `08b_end_to_end_system` requires full multimodal capabilities.
2. **Hardened Focused Regressions & SAPI Fixture**:
   - Updated `_write_speech_wav` in `tests/test_phase1_stage_smoke_runners.py` to inspect file existence, non-zero size, and readable WAV frames before `wave.open`, preventing unhandled `EOFError` when Windows SAPI fails silently.
   - Updated `_seed_upstream` in smoke runners to write explicit `dataset.endpoint_matrix` records instead of relying on missing-matrix fallback.
   - Added `test_all_20_frozen_units_match_arrow_transcripts` in `tests/test_phase2_tedlium_d2.py` verifying 100% exact equality and non-emptiness of reference text against HuggingFace Arrow tables.
3. **Reconciled Group 02 & Group 07**:
   - Verified that audio-only TED-LIUM 3 D2 artifacts fail closed on all 4 visual group 02 runners (`02a` scene, `02b` keyframe, `02c` OCR, `02d` caption) without starting inference.
   - Verified that missing upstream artifacts (`scene.raw_predictions`, `keyframe.raw_predictions`) block downstream visual runners.
   - Hardened `run_efficiency_pareto.py` (`07a`) to fail closed when no stage aggregates are found or when official/full execution lacks required stage inputs.
   - Verified that `07b` blocks on missing shortlists/predictions and rejects audio-only datasets under composite policy.
4. **Established 22-Node Full DAG Evidence Ledger**:
   - Reconciled all 22 manifest nodes in `docs/BENCHMARK.md` Section 0.4.
   - Clearly documented the boundary: 5 nodes PASS (`00a`, `00b`, `00c`, `01a`, `01b`); 17 downstream nodes remain explicitly `BLOCKED` awaiting eligible visual/multimodal datasets with released ground truth and rights.
   - Dry-plan validated for all 22 nodes without conflating topological planning with scientific benchmark execution.

## Evidence

- `tests/test_endpoint_eligibility.py`: 8/8 passed in 1.75s (absent receipt, malformed artifact, stale hash, ineligible endpoint row, unknown endpoint, ASR selection, rejection of audio-only TED-LIUM on visual runners, composite runner multi-modality requirement).
- `tests/test_group02_group07_reconciliation.py`: 7/7 passed in 3.53s (dry-plan integrity, audio-only rejection, dependency propagation, missing aggregate fail-closed, missing shortlist fail-closed).
- `tests/test_phase2_tedlium_d2.py`: 4/4 passed in 1.63s.
- `tests/test_phase1_stage_smoke_runners.py`: 6/6 passed in 15.88s.
- `tests/test_phase1_all_runners_exist.py`: 4/4 passed in 3.08s.
- `tests/test_phase1_priority_runners.py`: 18/18 passed in 25.05s.
- Combined focused regression: 25/25 passed with 0 failures, 0 regressions.
- Full dry-plan: `python benchmarks/scripts/execute_all_notebooks.py --dry-plan --profile full` completed with code 0 covering all 22 manifest nodes.

## Key Decisions

1. **No Silent Fallback to Unrestricted Allowlist**: `load_eligible_units` never falls back to `allowed_dataset_ids = None`. If endpoint matrix is absent or corrupted, execution fails closed.
2. **Distinction Between Technical Contract and Scientific Truth**: 22-node runner presence and dry-plan prove executor readiness, but official scientific benchmark completion requires real eligible data. Group 02-09 remain `BLOCKED` until dataset coverage expansion provides real released GT for visual and downstream tasks.
