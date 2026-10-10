# Documentation cleanup record — 2026-10-07

## Current research path

The maintained entry points are the repository [README](../README.md), [documentation index](README.md), [benchmark protocol](BENCHMARK.md), [dataset EDA guide](DATASET_EDA.md), [model-selection guide](MODEL_SELECTION_README.md), [master plan](../plans/260901-unified-scientific-benchmark/framework/00-master-plan.md), and [RQ2 plan](../plans/261002-0946-rq2-controlled-summarization/plan.md). The workflow is: select lecture datasets with matching existing labels and candidate families; run full-cohort EDA in a notebook created when needed; then compare candidates on the same units, labels, metric and resource profile.

## Removed in this cleanup

- Removed 88 superseded plan/phase Markdown files after reviewing the exact path list and receiving approval. Kept current/referenced master, source, dataset, RQ2 and historical protocol documents.
- Removed 13 obsolete supporting Markdown files: early migration/strategy and model-guide drafts, superseded journals and notebook-comparison brainstorm, stale pipeline scoring notes, `OUTLINE_MAPPING.md`, and withdrawn validation-gate summaries.
- Replaced the original 221-file candidate inventory with this record. That broad initial proposal was not used as a deletion command.

## Evidence retained

- All 96 Markdown files in `plans/reports/`, nested report directories, and their CSV/JSON companions remain available as historical source, rights, annotation and execution evidence. No RQ1 report is an official benchmark result.
- Retained the executed TIB 20-record and VISTA 40-video EDA reports, plus the all-split TIB notebook. The 20-record TIB analysis found 0/20 abstracts qualified as formal factual-summary references; the all-split EDA has not yet been executed.
- Retained Yale, MITFLD, YTSeg, VidChapters and SSLectures qualification reports that explain media access, rights, label provenance and eligibility holds. Those conclusions are candidate/source evidence, not permission to rerun RQ1.
- Retained the ASR architecture notebook and reports as a diagnostic result; no ASR rerun is planned.
- Retained four plan templates, the frozen-decision JSON and its referenced historical decisions log, the legacy-notebook index, presentation/defense drafts, workspace system-review notes, and `SPRINT_QUALITY_DEPLOYMENT.md` because they contain context outside the current benchmark protocol.

## Claim boundaries

No chaptering or summarization winner is established. The withdrawn saved chaptering and summarization outputs are not restored by keeping source-qualification reports. TIB all-split EDA and full VISTA validation inspection remain pending. The RQ2 primary metric measures agreement with creator abstracts, not factual correctness; no human scoring is planned.

## Follow-up notebook cleanup — 2026-10-08

At the user's request, removed five tracked notebooks from `experiments/notebooks/diagnostics/`: `rq2-tib-valid-eda.ipynb`, `rq2-tib-valid-sample-size-eda.ipynb`, `vista-validation-media-eda-colab.ipynb`, `dataset_readiness.ipynb`, and `full-corpus-pre-split-eda.ipynb`. Their historical Git revisions remain recoverable. The dataset-readiness initial and final executed copies also remain in `experiments/notebook_history_20260926.zip`; that archive does not contain the other four current notebook files.

Retained the TIB 20-item decision, audit, analysis script and receipts; the VISTA 40-video report; the local full-corpus JSON receipts; and the dataset-readiness archive, manifest and result summary. Removing notebooks does not make their historical diagnostics official results. The all-split TIB notebook remains the current EDA entry point; VISTA full-validation EDA is no longer planned.

Later on 2026-10-08, the all-split TIB notebook acquired saved Colab structural-scan outputs for 9,103 records (9,002 text-usable, 101 excluded). Visualization and interpretation cells were added but have not yet been executed against the saved Drive receipts. Reference and media qualification remain open.
