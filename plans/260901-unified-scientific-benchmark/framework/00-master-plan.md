# Master plan: lecture video understanding, summarization and retrieval

**Updated:** 2026-10-07. This file records the research questions and current decision gates. The [benchmark protocol](../../../docs/BENCHMARK.md) defines the executable sequence and [Dataset EDA](../../../docs/DATASET_EDA.md) distinguishes executed evidence from plans.

## Objective

Study whether temporal structure and grounded multimodal evidence improve lecture summarization and knowledge retrieval under controlled input and compute budgets. The central comparisons remain hypotheses; earlier proposed architectures, model IDs and calendar milestones do not establish implementation or results.

## Research questions

| Question | Comparison to investigate | Evidence needed now |
|---|---|---|
| RQ1 — Chaptering | Multimodal versus transcript-only boundary prediction. | Historical diagnostics only. Saved results were withdrawn for reanalysis; no rerun is planned. Do not use its old chapter labels as scene-cut GT. |
| RQ2 — Summarization | Fixed-chunk S1 versus hierarchical S3 with one generator and measured equal token budgets; other arms only if their inputs qualify. | Execute full-cohort TIB EDA, audit reference suitability and choose a valid evaluation cohort and automatic outcome. Qualify VISTA media/GT separately. See [RQ2 plan](../../../plans/261002-0946-rq2-controlled-summarization/plan.md). |
| RQ3 — Retrieval and QA | Flat, dense and hierarchy-aware retrieval with a fixed reader. | Verify lecture-video source, answer/evidence labels and media for EduVidQA or another suitable source; evaluate retrieval and answers on separate metrics. |
| RQ4 — Efficiency | Quality and latency/VRAM/cost of fixed pipeline compositions. | Use the same eligible lecture units, hardware profile and quality gates; report Pareto results only after measured runs. |

ASR architecture comparison is preserved in the [diagnostic report](../../../docs/results/asr-architecture-evaluation-2026-10-05.md). No ASR rerun is planned. It is not evidence that any remaining video task has been evaluated.

## Task sequence

1. Select lecture-domain datasets with existing annotations matching each target. Verify media, source revision, rights, annotation origin and source-video linkage. General-video datasets are not fallback benchmarks. Keep detection of slide/board elements and detection of natural objects as **two separate tracks** with their own taxonomy and scores.
2. Predeclare candidate families, comparison units, primary metric, scorer details and shared compute conditions for that task. An entry in a registry is a proposal until run.
3. Create and execute an EDA notebook for the actual selected cohort. Account for every unit and exclusion; inspect distributions, label/media quality, duplicates, leakage and failure groups. Record sampled inspections and decisions explicitly.
4. Freeze the cohort and evaluate the candidate families in a task-specific notebook on identical units, GT, metric and resource profile. Save item-level predictions, failures, receipts and uncertainty estimates. If inputs or labels remain unsuitable, report `not_eligible`; if the comparison is incomplete, report `no_selection`.
5. Interpret negative results and limitations without replacing the predeclared metric or inferring quality from lexical overlap alone.

Do not create placeholder or smoke notebooks. The [on-demand manifest](../../../experiments/notebooks/notebook_manifest.yaml) currently lists none. Existing historical notebooks may retain code without saved results and may require retired dependencies before reuse.

## RQ2 data decision

Inspect **all records** of the pinned creator TIB `train`, `valid` and `test` splits without filtering by genre. Track each source row by `(split, source_index)`, and report missing input, abstract quality, grouping and leakage. The [all-split EDA notebook](../../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) is prepared but its new full-cohort cells have not been executed. Reading creator `test` references removes its unseen-holdout status for future claims; a new independent source would be needed for that claim. VISTA has only partial validation-media evidence and is not yet a qualified full-cohort summarization benchmark.

The withdrawn 20-/70-item TIB outputs cannot be treated as current RQ2 results. The next result must come from an executed EDA decision, frozen comparison and saved item-level evaluation evidence.

## Reporting standard

Every claim should identify dataset revision, label provenance, cohort and denominator, candidates, scorer, compute profile, missing units, failures, paired uncertainty and whether a split was unseen at selection time. Keep OCR recognition, text spotting, object detection, scene boundaries and chapter boundaries on their respective label and metric tracks. Preserve a `no_selection` conclusion when a defensible ranking cannot be made.