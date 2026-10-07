# Dataset EDA: scope and evidence

## Required analysis before evaluation

Create one task-specific EDA notebook when the selected lecture-domain data and labels are available. Reconcile every selected source ID with records actually read, then report counts by source, split and relevant strata. For the intended cohort, inspect input/label completeness, distributions, quality, exact and plausible near-duplicates, source-group overlap, leakage, outliers and failed reads. Distinguish **full metadata or annotation coverage** from sampled media decoding; describe the sample rule and limit of inference.

The notebook must show tables, plots, unusual examples, missing or excluded IDs, and a decision for each dataset or cohort: keep, repair by a declared rule, restrict the target, or reject. State denominators before and after each exclusion. Freeze the comparison cohort and scoring protocol only after this review. A notebook with code but no executed outputs does not pass the EDA gate. Do not use a smoke notebook as a substitute.

For an untouched final test, inspect only data allowed by the declared protocol before model selection. If test references are examined during EDA, disclose that the split is no longer unseen. Ground truth must have traceable annotation provenance and source-video linkage; do not fill missing labels with self-created proxies.

## Current notebook evidence

| Source | Executed evidence | Remaining limit |
|---|---|---|
| [Full local-corpus pre-split EDA](../experiments/notebooks/diagnostics/full-corpus-pre-split-eda.ipynb) | Executed annotation/metadata inventory with tables and plots for locally available TED-LIUM, IIIT-CVID, EduViQA, SlideVQA and other snapshots. [Outputs](../experiments/outputs/full_corpus_eda_261003/) remain local. | Not every waveform or video frame was decoded; inventory alone does not qualify a task benchmark. Reading native test reference fields means those source splits cannot be called unseen in a later derived study. |
| [TIB validation EDA](../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) | Historical detailed inspection of 20 validation records. | This subset cannot represent all TIB or establish summary quality. |
| [TIB all-split EDA](../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) | Notebook code targets all expected 9,103 creator records: 7,282 `train`, 910 `valid`, 911 `test`, at a pinned revision, without a genre filter. | New all-split cells have no executed result. Actual counts, usable rows, source/abstract suitability and duplicate groups remain to be confirmed on Colab. It does not decode video/audio. Reading `test` content will remove unseen-holdout status. |
| [VISTA validation media EDA](../experiments/notebooks/diagnostics/vista-validation-media-eda-colab.ipynb) | Metadata for train/validation and media inspection for 40 of 1,859 validation videos. | Full-validation extension has not run; the 40-video inspection cannot qualify all media or establish suitable summary ground truth. |

## Findings that affect the next run

- IIIT-CVID's local annotation inventory found 5,475 frames and 137,745 labeled crops. The EDA recorded 22 invalid box geometries, 124 XML image-size mismatches and near-duplicate candidates across splits. These need adjudication before fixing an OCR cohort; a dHash candidate is not an automatic exclusion.
- The 20-video local EduViQA snapshot is not the proposed EduVidQA source. Its 583 generated transition markers are not independent scene-boundary ground truth.
- YTSeg creator chapter annotations are not generic scene-cut labels. RQ1 is not planned for rerun.
- TIB genre is a descriptive stratum, not an exclusion rule. Keep a row ledger keyed by `(split, source_index)` so missing or repeated DOI values do not erase records. Creator abstracts require suitability and provenance review before being treated as summary references.
- Existing TIB 20-/70-item outputs and saved RQ2 score reports were withdrawn for reanalysis. No full-TIB result or summarization winner follows from the EDA notebook code.

## Historical source and ground-truth qualification

These checks document earlier candidate screening, not current dataset approval and not benchmark results. RQ1 will not be rerun, but the rights and annotation findings remain useful provenance when explaining why a source was excluded or held.

| Candidate source | Historical finding | Current interpretation / retained detail |
|---|---|---|
| TIB creator validation | The 20-record diagnostic found author overlap with train in 13/20, same-series title relationships in nine records, and **0/20 abstracts accepted as formal summary references**. | Historical subset only; inspect all pinned splits as described above. See [per-record audit](../plans/reports/rq2-valid-dataset-audit-261002-report.md) and [decision record](../plans/261002-0946-rq2-controlled-summarization/rq2-tib-validation-eda-decision.md). |
| VISTA validation | Media inspection covered 40/1,859 validation records; record `val_0395` was only three seconds. | Partial media evidence, not full-corpus readiness or qualified summary GT. See [media EDA report](../plans/reports/vista-colab-media-eda-261003-1326-validation-cohort-report.md). |
| YTSeg / VidChapters | A historical gate marked two YTSeg and one VidChapters source records as qualified for further review; per-ID rights and GT caveats remained. Creator chapters are not generic scene-cut ground truth. | These are not approved benchmark cohorts. See the [joint qualification report](../plans/reports/qualification-260929-1637-ytseg-vidchapters-gate-report.md) and [VidChapters semantic review](../plans/reports/vidchapters-semantic-260929-1818-selected-groups-report.md). |
| Yale / MITFLD | Yale screening selected 18 records but only one passed the later new-source gate; component and third-party rights exceptions remained. The 35-item MITFLD cohort was a pilot; provenance and license for `frags` labels were unresolved, leaving **0 items officially eligible**. | Do not describe either as a completed benchmark cohort. See [Yale qualification](../plans/reports/rq1-locked-yale-260929-qualification-report.md) and [MITFLD rights/GT review](../plans/reports/rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md). |
| MIT001 | A 35-video diagnostic had nine end-time cases needing review; prior aggregate chapter scores were withdrawn. | Do not reuse old scores as evidence. See [rights and media audit](../plans/reports/260928-0839-mit001-video-rights-media-audit-report.md). |
| SSLectures | Nine records linked to source pages, but creator identity and annotation provenance were unverified for all nine. | Remains HOLD for ground-truth use. See [package provenance report](../plans/reports/rq1-sslectures-260929-1432-package-provenance-nine-row-report.md). |

Keep these linked source reports and the associated CSV/JSON receipts as historical provenance. They do not authorize an RQ1 rerun or establish an eligible cohort.

For each future task, link the executed notebook, revision, run receipt and frozen cohort from its evaluation report. Show `selected / observed / label-valid / media-valid / evaluated / failed` counts and distinguish each metric's denominator.
