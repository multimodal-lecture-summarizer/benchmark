# Phase 1 stage smoke runners (01a + group 02) — 2026-09-24

## Status

| Scope | Done | Total | Progress | State |
|---|---:|---:|---:|---|
| Phase 1 | 8 | 12 | 66.67% | in-progress |
| This slice | runners + fixture tests | — | delivered | unblocked runner discovery |

Phase 1 checklist counts are unchanged: the four open gates still need live group/DAG evidence, audit-wide tests, and ownership reconciliation. This slice removes the missing-runner blocker for `01a` and group `02`.

## Completed this slice

- Added shared helper `experiments/scripts/stage_benchmark_helpers.py`.
- Implemented real miniature runners:
  - `benchmarks/scripts/run_asr_model_benchmark.py` (`faster-whisper-tiny.en`)
  - `benchmarks/scripts/run_scene_boundary_benchmark.py` (histogram + fixed-grid)
  - `benchmarks/scripts/run_keyframe_selection_benchmark.py` (midpoint/uniform)
  - `benchmarks/scripts/run_ocr_benchmark.py` (OpenCV threshold smoke; EasyOCR on full)
  - `benchmarks/scripts/run_visual_caption_benchmark.py` (color/histogram caption baselines)
- Added `tests/test_phase1_stage_smoke_runners.py`.
- Validation: `python -m pytest tests/test_phase1_stage_smoke_runners.py -q` → **6 passed** in 96.89s.
- Live executor: `--list` returns 22 notebooks; group `02` dry-plan reports `runner_exists=True` for all four entries.
- Live group `02` / `01a` without eligible D2 freeze fail closed on missing `dataset.frozen_manifest` / registry receipts (no longer "runner source module not found").

## Explicit non-claims

- Official group `02` / full-DAG smoke is still red without scientifically eligible frozen units.
- Group `07` and remaining 13 missing runners are untouched.
- Standalone vs full-DAG hash equivalence is not proven.
- Ownership/post-change dirty-worktree gate remains open.

## Next actions

1. Qualify first real D2 eligible freeze (or seed a controlled smoke-only eligible fixture path that still fails closed for official scientific selection if adjudication is incomplete).
2. Implement remaining missing runners needed for full-DAG smoke topology.
3. Prove standalone vs DAG artifact equivalence and finish audit test coverage.
