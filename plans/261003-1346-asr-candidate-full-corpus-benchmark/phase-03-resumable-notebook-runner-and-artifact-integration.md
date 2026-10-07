---
phase: 3
title: "Resumable notebook runner and artifact integration"
status: in-progress
priority: P1
dependencies: [1, 2]
effort: "1-2 days"
---

# Phase 3: Resumable notebook runner and artifact integration

## Overview

Run the complete A0–A5 cohort from the Colab T4 notebook through a resumable runner and produce the existing four artifact types with verifiable per-unit coverage. The Colab notebook is the sole active ASR benchmark notebook; `01a_asr_model_benchmark` remains the manifest and artifact producer ID.

## Requirements

- `full` consumes every retained validation unit and, after a frozen validation receipt, every retained native test unit; `smoke` is a separate preflight. Selection can access validation only. Test execution cannot write a new selection.
- Read canonical audio through Phase 1's verified Arrow locator/streaming adapter. Replace the runner's `require_media` file-path assumption for this cohort; pass the same decoded float32 mono 16 kHz samples to all six candidates.
- Keep separate validation and native-test subruns: distinct `RunnerContext` artifact roots and run IDs, each with its own receipts/run manifest. Completed receipts/manifests are immutable; partial outputs may be updated only when resuming identity-matched checkpoints. Retain the canonical quartet in the validation root for existing consumers. The test root binds to a read-only hash of the complete validation selection receipt and never overwrites its manifest or shortlist. A parent index names both roots and identities.
- Checkpoint each candidate/segment transaction atomically. Resume only when source, cohort, GT, media, model, config, normalizer, code and hardware profile identities match. Refuse partial/stale artifacts and do not redo completed predictions unnecessarily.
- Keep `asr.raw_predictions`, `asr.per_unit_metrics`, `asr.aggregate`, `asr.shortlist` schemas usable by existing readers. Add status/coverage receipts or separate artifacts as needed. `asr.shortlist` is validation-derived only.
- Corpus micro WER/CER is reconstructed from per-unit edit counts; RTF = total timed inference seconds / total audio seconds. Report load/warmup, preprocessing and alignment separately, with source/talk grouping and missing-pair policy.
- A failed candidate/unit is recorded; a partial candidate cannot be ranked or made `selected`. Do not fill missing text or metrics with zero.
- If any expected candidate/unit is missing or failed, use a nonempty diagnostic status row for each candidate in aggregate and a single `asr.shortlist` sentinel `{candidate: "no_selection", selected: false, status: "partial", reason: ...}`. Keep raw/per-unit artifacts nonempty with explicit failed attempt rows and N/A metrics; use `evidence-status=partial`. Since `rank_shortlist` always selects rank 1 and the writer rejects empty lists, bypass ranking for this path and test its schema/consumer behavior. A complete validation matrix is required before any `selected: true` row.

## Architecture

The Colab notebook prepares the pinned environment and model cache, then calls the Python runner after a six-candidate probe. The runner loads the frozen diagnostic manifest, iterates deterministic candidate and unit shards, writes checkpoints, derives full artifacts and a validation-only ranking. The validation root keeps the original quartet and run manifest. A separately identified test subrun/root holds test raw/metrics/aggregate artifacts and a read-only reference to the validation shortlist, with receipt hash verification. `parent_index.json` binds both subruns. `write_run_manifest` and receipt validation must remain correct after both runs; never reuse the same `namespace_root/runs/01a...json` filename for different split outputs. Migrate any consumer that needs test metrics explicitly.

## Related Code Files

- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_asr_model_benchmark.py`; add `experiments/notebooks/asr_a0_a5_colab_t4.ipynb`, `experiments/scripts/asr_colab_bundle.py`, and `experiments/scripts/asr_colab_run.py`. Retire the old `01a` notebook file while retaining its logical manifest ID.
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_asr_preprocessing_ablation.py` for the new registry shortlist or a typed, explicit unsupported-composite handoff.
- Audit callers: `benchmarks/scripts/run_error_propagation_benchmark.py`, `run_end_to_end_system.py`, `run_efficiency_pareto.py`, `experiments/scripts/generate_cross_task_report.py`.
- Add focused tests under `multimodal-lecture-summarizer/tests/`.

## Implementation Steps

1. Freeze CLI/manifest settings and status schema; keep executor provenance keys intact.
2. Implement deterministic resume/checkpoint and candidate/unit completeness accounting. Quarantine stale/mismatched checkpoints.
3. Assemble per-unit and aggregate metrics, with six-row candidate status ledger and validation-only selection. For incomplete coverage, emit the explicit `no_selection` contract rather than calling `rank_shortlist`; test split output must not alter shortlist.
4. Verify `01b` and other quartet readers against the resulting schema. Route a selected supported decoder to `01b` with an exact registry ID/adapter contract; for A2/A4/A5 or any unsupported winner, emit an explicit typed `01b blocked_unsupported_candidate` status until that ablation adapter exists. Do not silently reinterpret a composite as Faster-Whisper.
5. Run adapter probe and interrupted-resume tests; validate the Colab notebook and bundle. No full benchmark claim before measured T4 execution.

## Success Criteria

- [ ] For every candidate, `expected = completed + failed + blocked` for each split; no silent omissions.
- [ ] Resume with matching identity is idempotent; changed GT/model/config/media rejects reuse.
- [ ] Validation artifacts still validate after the test subrun; independent run IDs/manifests and the selection-receipt hash prevent cross-split overwrite or promotion.
- [ ] Final-test reference cannot enter candidate selection; old quartet readers remain valid or are deliberately updated.
- [ ] `01b` either consumes the exact supported selected candidate or stops with a tested explicit status, including when A2/A4/A5 wins.
- [ ] All-candidates-failed and one-candidate-partial cases still produce valid nonempty diagnostic receipts and no selected candidate.
- [ ] Focused tests, bundle integrity and Colab notebook contract pass; six real adapter probes pass on T4 before the full matrix.

## Risk Assessment

The executor-controlled `01a` has a 14,400-second cell timeout, so the Colab notebook invokes the runner directly and stores checkpoints on Drive. Dependency installation and model loading on T4 still require a real probe; existing dirty runner/manifest edits must be diff-reviewed before changes.
