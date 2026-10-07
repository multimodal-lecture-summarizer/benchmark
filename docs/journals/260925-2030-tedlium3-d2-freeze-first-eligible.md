# TED-LIUM D2 Freeze — First Phase-2 Eligible Dataset

**Date**: 2026-09-25 20:30  
**Severity**: Info (milestone)  
**Component**: Phase 2 — dataset freeze pipeline (00a/00b/00c)  
**Status**: Landed; remaining phase-2 criteria still open

## What Happened

`tedlium3` became the first D0→D2 eligible record in the Phase-2 pipeline. A new driver (`experiments/scripts/phase2_freeze_tedlium.py`) froze a 20-unit subset (10 validation + 10 final_test) from the 20 on-disk WAVs (TED-LIUM Release 3, CC BY-NC-ND 3.0) and produced the full 00c characterization bundle, all schema-valid and fail-closed.

## Evidence

- Validator: `dataset_count=1, unit_count=20, d2_eligible_dataset_count=1, characterization_artifact_count=14, d2_figure_count=8`.
- `dataset.frozen_manifest.json` SHA-256 `1b6930cb…b03b0e`; `freeze_status=eligible`, `scientific_selection_eligible=1`, unit_ids sorted-unique=20.
- Leakage: 0 exact overlap, 0 duplicate groups, near-duplicate adjudicated/complete, `findings=[]`.
- Registry: `available`, `acquisition_level=D2`, `predicted_peak_bytes=16529616`.
- Endpoint matrix: `tedlium3 × asr_benchmark` → `eligible_d2` (matches existing validated `asr_benchmark` key, not plan's loose `asr` wording).
- Tests: 3/3 new (`tests/test_phase2_tedlium_d2.py`) pass; full suite 302 passed, 2 pre-existing baseline failures unrelated (confirmed via `git stash`).

## Decisions

- Reuse-only design: driver constructs `RunnerContext` directly (same pattern as `test_d2_freeze_pipeline.py`) and calls `profile_dataset.main()`; no changes to validated modules.
- `relative_path` stored relative to `experiments/datasets/` because `profile_dataset.py` resolves `media_path` as `PROJECT_ROOT/experiments/datasets + relative_path`.
- Read JSON with `encoding='utf-8'` (Windows locale decoder mangles the em-dash in `rights`).
- `reference_text=""` — media-only pilot; manual-transcript `ground_truth_status` recorded at dataset level.

## Review

Mandatory code-review gate PASS (checks a–e). Flags LOW/INFO; the two flagged behaviors (absolute `media_path`, empty `reference_text`) trace to pre-existing `profile_dataset.py` semantics, not the driver.

## Next Steps

- Commit driver + tests if user approves (branch `baseline/pre-phase1-snapshot`).
- Open phase-2 items: modality-specific (audio) figures, `.csv`/docs `DATASET_EDA.md` regeneration, D1 receipts for remaining dataset candidates, VISTA/TIB/YTSeg/EduVidQA fallbacks.