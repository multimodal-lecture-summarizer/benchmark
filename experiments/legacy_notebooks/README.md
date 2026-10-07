# Legacy Notebooks — Archive

These notebooks were **superseded on 2026-09-21** by the new
comparison framework in `experiments/notebooks/`.

As of 2026-09-26, all six files listed below were found on disk and moved into
`experiments/notebook_history_20260926.zip` with SHA-256 entries in
`experiments/notebook_history_20260926.manifest.json`. The table below records
the earlier refactor audit and does not describe the current file locations.

## Historical refactor audit (2026-09-21)

| File | Status | Source |
|:-----|:-------|:-------|
| `01_audio_asr_benchmark_old.ipynb` | ⚠️ **LOST** during refactor — only refactored version available | was overwritten before archive; legacy_notebooks_backup did not contain Phase 1 ASR file |
| `02_visual_scene_ocr_benchmark_old.ipynb` | ⚠️ **LOST** during refactor | same reason as 01 |
| `03_multimodal_chaptering_benchmark_old.ipynb` | ✅ preserved (39KB) | `legacy_notebooks_backup/03_phase3_representation_and_chaptering.ipynb` |
| `04_hierarchical_summarization_benchmark_old.ipynb` | ✅ preserved (46KB) | `legacy_notebooks_backup/04_phase4_hierarchical_summarization.ipynb` |
| `05_evidence_retrieval_qa_benchmark_old.ipynb` | ✅ preserved (45KB) | `legacy_notebooks_backup/05_phase5_evidence_retrieval_and_qa.ipynb` |
| `06_efficiency_pareto_error_cascading_old.ipynb` | ✅ preserved (924KB) | `legacy_notebooks_backup/06_phase6_rq4_efficiency_and_pareto.ipynb` |

## Why Archived

| Old Notebook | Reason for Replacement |
|:-------------|:----------------------|
| 01_audio_asr_benchmark.ipynb | Hard-coded candidates, no ablation, no leaderboard |
| 02_visual_scene_ocr_benchmark.ipynb | Only 1 video (CA01.mp4), no statistical comparison |
| 03_multimodal_chaptering_benchmark.ipynb | C1-C6 hard-coded, no ablation grid |
| 04_hierarchical_summarization_benchmark.ipynb | S0-S4 hard-coded, no leaderboard |
| 05_evidence_retrieval_qa_benchmark.ipynb | Q0-Q3 hard-coded, no ablation |
| 06_efficiency_pareto_error_cascading.ipynb | E1-E4 hard-coded, no cross-task |

## Migration Path

New notebooks use:
- `experiments/registry/candidates.yaml` — centralized model catalog
- `experiments/scripts/ablation_runner.py` — 2^k grid with cap 8
- `experiments/scripts/leaderboard_builder.py` — multi-metric scoring
- `experiments/scripts/dashboard_renderer.py` — Plotly HTML

See plan: `plans/260921-notebook-comparison-redesign/plan.md`

## Recovery

For notebooks 03-06: git-blame the original timestamps (9/4/2026 - 9/5/2026)
to find the original code commit.

For notebooks 01-02: original was overwritten. To recover:
1. Check git history (if any pre-2026-09-21 commit)
2. Re-run the old `experiments/scripts/legacy_sprint1_compare.py` to regenerate output JSON
3. Or reconstruct from `reports/rq0a_audio_results.json` + `reports/rq0v_visual_results.json`
