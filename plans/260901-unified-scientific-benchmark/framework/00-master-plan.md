# Master plan: lecture video understanding, summarization and retrieval

**Updated:** 2026-10-09. This file maps research questions, evidence gates and claim limits. The [benchmark protocol](../../../docs/BENCHMARK.md) owns task eligibility, candidate families and metrics; [Dataset EDA](../../../docs/DATASET_EDA.md) records executed versus pending inspection; task plans own run details. The adjacent [original benchmark matrix](02-benchmark-matrix.md) and [decisions log](decisions-log.md) are historical references.

## Objective

The near-term question is whether source-only predicted structure improves lecture-text summarization over fixed chunks under a shared generator and equal allocated intermediate/final output caps, with actual token use measured. The initial RQ2 comparison is text-only and depends on TIB cohort and reference qualification.

Video-grounded multimodal summarization and knowledge retrieval remain conditional extensions: their media, task-matched labels and outcomes must qualify before evaluation. Earlier architectures, model IDs and calendar milestones remain proposals unless supported by executed evidence.

## Research questions

| Question | Status and comparison | Next evidence gate | Claim limit |
|---|---|---|---|
| RQ1 — Chaptering | Historical only; multimodal versus transcript-only boundary prediction. Saved results withdrawn; no rerun planned. | No new run scheduled; retain provenance and limitations. | No current chaptering winner. Chapter boundaries do not establish scene-cut GT. |
| RQ2 — Summarization | All-split EDA has 10 executed cells and 8,769 mechanically eligible candidates. Fixed-chunk S1 versus source-only boundary-constrained chunking S3 has no new completed paired result. | Run the train-only technical pilot on Colab, then review measured budget and source dependence before freezing evaluation IDs/protocol. | Creator-abstract agreement on the declared cohort; no factuality, unseen-generalization or visual/audio-contribution claim. Abstracts need not be certified factual summaries for this outcome. |
| RQ3 — Retrieval and QA | Proposed; compare pipelines with a fixed reader after source context is recovered. | Answer agreement needs qualified context and released QA labels; retrieval/evidence-quality conclusions additionally need independent relevance/evidence GT. Video/timestamps are required only for claims that consume or locate them. | Answer improvement is not evidence of better retrieval relevance. No current result; grounded/evidence claims remain conditional. |
| RQ4 — Efficiency | Dependent; quality versus latency, VRAM and cost for fixed pipeline compositions. | Establish suitable quality outcomes, identical eligible units and measured resource runs on a shared hardware profile. | No current Pareto result; any comparison is limited to the measured cohort, configurations and compute profile. |

The completed six-candidate ASR comparison is preserved in the [diagnostic report](../../../docs/results/asr-architecture-evaluation-2026-10-05.md), including checkpoint details, scores and qualification limits. No ASR rerun is planned. Native-test results do not establish performance on an independent unseen holdout.

## Shared evidence gates

**2026-10-10 scope clarification:** qualify dataset/cohort against the exact question, inputs, annotation target and conclusion. The [claim matrix](../../reports/research-scope-261010-1621-claim-qualification-report.md) prioritizes TIB text-only creator-abstract agreement for RQ2, with RQ4 costs measured on the same run; OCR recognition and LVVO released-image detection are narrower component comparisons. Missing source-video media must not block a comparison that consumes released text/images only. Video extraction, fine-tuning splits and unseen/generalization claims retain their relevant gates. None of these scope decisions is a completed benchmark or automatic cohort freeze.

1. **Qualification and executed EDA:** verify lecture-domain source, rights, media and existing task-matched annotation provenance. Account for every selected unit, missing input, exclusion, duplicate group and leakage concern. Metadata coverage and sampled media inspection have different limits.
2. **Frozen comparison:** after EDA, fix eligible units, candidates, primary outcome, scorer, failure policy, input/token budgets and resource conditions before examining comparison scores. Compare candidates on the same units and task target.
3. **Claim supported by artifacts:** retain item-level predictions, failures, denominators, receipts and paired uncertainty. Report `not_eligible` for unsuitable inputs or labels and `no_selection` for an incomplete or inconclusive comparison. Negative results are valid outcomes.

The active [task matrix](../../../docs/BENCHMARK.md#task-matrix) covers slide transitions, board keyframes, OCR recognition/spotting, caption/grounding, separate slide/board-element and natural-object detection tracks, and tracking. These are candidates to qualify, not completed benchmarks. General-video datasets and self-created proxy labels cannot replace missing lecture-task GT.

Create notebooks for concrete EDA or evaluation runs under the benchmark protocol. Historical notebooks and registries do not establish execution or selection.

## RQ2 evidence boundary

The executed [all-split EDA notebook](../../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) shows 9,103 pinned creator-TIB records without a genre filter; 9,002 are structurally text-usable, with 98 invalid-time and three unordered-segment exclusions. Excluding eight empty and 225 reused abstracts yields 8,769 candidates. Its ten executed cells retain the inline evidence. The [source/content audit](../../../plans/reports/tib-cross-split-source-content-audit-261010-report.md) supports a limited creator-abstract agreement study with dependence sensitivity; this does not certify references as factual summaries. Creator `test` content was read, so it cannot support an unseen-holdout claim. Broader lecture-only or independent-generalization claims require their own qualification.

RQ2 uses no human scoring. Reconcile the prior ROUGE-L F1 outcome with abstract suitability before the new comparison; creator abstracts and lexical overlap do not establish factuality. Freeze S3's source-only predicted structure without oracle chapters or reference content, and do not inherit withdrawn RQ1 performance. VISTA requires separate media and reference qualification before any video-based extension. See the [RQ2 plan](../../../plans/261002-0946-rq2-controlled-summarization/plan.md) for the current protocol.

The withdrawn 20-/70-item TIB outputs cannot be treated as current RQ2 results. The next result must come from an executed EDA decision, frozen comparison and saved item-level evaluation evidence.

## Reporting standard

Every claim should identify dataset revision, label provenance, cohort and denominator, candidates, scorer, compute profile, missing units, failures, paired uncertainty and whether a split was unseen at selection time. Keep OCR recognition, text spotting, object detection, scene boundaries and chapter boundaries on their respective label and metric tracks. Preserve a `no_selection` conclusion when a defensible ranking cannot be made.
