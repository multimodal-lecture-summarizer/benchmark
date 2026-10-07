---
title: "RQ2 dataset and blinded evaluation feasibility"
type: research
date: 2026-10-02
status: completed
scope: "Dataset selection and human H2 feasibility; no benchmark execution"
---

# RQ2 dataset and blinded evaluation feasibility

**Research time:** 2026-10-02, Asia/Bangkok.  
**Decision:** Use `gigant/tib` as the first RQ2 text-cohort candidate. Treat human H2 feasibility as unverified until a timed, paired 10-talk pilot and cohort qualification are complete.

## Executive summary

The creator's [TIB dataset card](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) describes 9,103 records with train 7,282 / validation 910 / test 911, DOI, source/video URLs, per-record license, abstract, transcript and timed segments. This is a better initial S1–S3 route than the reduced `tib-bench-text` packaging: it already has official split labels and does not require downloading raw video to test a text-only hierarchy. The old local probe found 98 test records tagged Lecture; 94 passed its simple nonempty/length filter. Those 94 are candidates, not an eligible or executed RQ2 cohort.

The registered H2 requires blinded human factual-support and key-point-coverage outcomes. [D-T10](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/decisions-log.md) requires a 10-talk variance pilot and at least 50 final talks, with n expanded if power requires it. Its `pilot_results` and `final_n` fields remain empty, as does the [frozen decision record](../../multimodal-lecture-summarizer/benchmarks/docs/frozen_decisions.json). No measured audit time or RQ2 human score receipt was found. The available candidate count makes 50 numerically plausible, but neither eligible n nor one-person capacity is established.

## Research method and evidence boundary

- Official creator dataset cards and primary evaluation papers reviewed on 2026-10-02; local historical probes and live repo contracts inspected.
- No fresh dataset download, real-cohort EDA notebook, human annotation, power pilot or final-test access occurred in this research.
- Old probe counts are a lead; do not transfer their status to a new manifest without rerunning metadata and endpoint checks.
- Local source pointers: [TIB probe totals](../../multimodal-lecture-summarizer/plans/260830-1917-scientific-benchmark/probes/output/tib_summary.json), [98 lecture IDs](../../multimodal-lecture-summarizer/plans/260830-1917-scientific-benchmark/probes/output/tib_lecture_test_ids.json), [94 preliminary records](../../multimodal-lecture-summarizer/plans/260830-1917-scientific-benchmark/probes/output/tib_lecture_usable.json), [EDA status](../../multimodal-lecture-summarizer/docs/DATASET_EDA.md).

## Dataset decision

| Candidate | Verified public structure | Local evidence | Decision |
|---|---|---|---|
| [`gigant/tib`](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) | 9,103 records; official train/validation/test; transcript, timed segments, abstract, DOI and license field | Old probe: 98 Lecture test DOI; 94 with nonempty/length-filtered transcript and abstract ≥30 characters; median transcript 39,162 characters | **First to qualify** for S1–S3. Reserve validation for development and test for sealed final; check series/group leakage before use. |
| [`gigant/tib-bench-text`](https://huggingface.co/datasets/gigant/tib-bench-text) | Viewer shows ~1,034 records under a single `train` split; transcript/abstract fields | No executed RQ2 cohort | Useful lightweight smoke source only if base TIB access fails. A derived split must be declared and audited. |
| [`gigant/tib-bench`](https://huggingface.co/datasets/gigant/tib-bench) | Reduced visual packaging; viewer displays a single `train` split | Old DOI mapping report claims 80 overlap with base TIB test, not a native `test` split | Optional S4 visual extension after DOI join is rechecked; do not require for S1–S3. |
| [VISTA official project](https://github.com/dongqi-me/VISTA) | Video/paper-abstract task, no transcript shipped in current repo contract | Local [registry](../../multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml) says VISTA full D0/unavailable | Defer until explicit bounded media/ASR access profile; not needed to start RQ2 text comparison. |

The [TIB creator card](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) reports filtering very short, non-English and duplicate conference-wide abstracts. That is useful provenance, not proof that every retained abstract is a good lecture summary. Perform a reference support/style audit only for reference-dependent endpoints. Use the per-record license field and [TIB portal rights information](https://av.tib.eu/faq) to decide allowed access and release; do not assume the dataset has one uniform license.

### Minimum qualification to run, versus formal H2

- **Engineering smoke (1–5 real items):** stable DOI/source ID, usable timed transcript, use-rights check, no quality claim.
- **Research diagnostic (predeclared 10–20 validation/development items):** execute EDA on those real items, document groups/missingness, pair S1 and source-only S3, report actual token use and source-grounded factuality. No video, slide, chapter GT or abstract requirement for this endpoint.
- **Formal H2:** group-safe held-out set, source-linked input, blinded factual-support/coverage rubric, pilot-derived sample size, fixed generation and fairness protocol. A published abstract is optional for the human H2 outcome; ROUGE and reference-based QA become N/A without one. Any dataset or outcome change from the registered VISTA/TIB protocol must be amended before opening test.

The old 94-count gives headroom above the registered 50-talk floor, but exclusion for missing data, quality, rights or group overlap can reduce it. If the Lecture subset falls below the required n, a predeclared broader TIB scientific-presentation cohort is a possible narrower-scope route; do not expand after viewing final scores.

## Blinded evaluation decision

The [registered H2](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/04-rq-mapping.md) names human factual support and key-point coverage for S3 versus S1. [D-S03](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/decisions-log.md) removes a second annotator and allows a single-author 20–50-talk quality audit with automated judge support. It does not fill D-T10's 10-talk variance pilot or final n. [PROGRESS.md](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/PROGRESS.md) checks the pilot item while also saying the results remain to be filled; the checked box is not a receipt.

[LongEval](https://aclanthology.org/2023.eacl-main.121/) supports smaller clause-level faithfulness judgments with source snippets to reduce annotation variance/workload. [RoSE](https://aclanthology.org/2023.acl-long.228/) supports explicit salient-content units and highlights evaluation reliability limits. [How to Evaluate a Summarizer](https://aclanthology.org/2021.eacl-main.160/) shows study design and annotator structure affect power. These papers support a careful rubric; they do not establish this project's rating time or effect size.

### Conditional paired-power calculation

Using SciPy's noncentral t distribution for a two-sided paired t test at 80% power, with `d` defined as the mean **within-talk S3−S1 difference divided by its SD**, yields the following planning numbers:

| Assumed paired effect | α = 0.05 | α = 0.0125 (conservative first Holm threshold for four S-pairs) |
|---|---:|---:|
| d = 0.5 | 34 paired talks; registered floor makes 50 | 48 paired talks; registered floor makes 50 |
| d = 0.3 | 90 paired talks | 128 paired talks |

These are **assumption-based calculations, not pilot results or a promised sample size**. The old 94 Lecture candidates barely cover the d=0.3, α=.05 case before any exclusions, and cannot cover 128 if the conservative four-pair threshold applies. Clustering by course/author could further reduce effective n. The H2 multiplicity rule and unit must be fixed before power planning; a broader predeclared TIB cohort may be needed. Computation used `t.ppf(1-α/2,n-1)` and noncentrality `sqrt(n)·d`, selecting the smallest integer n with two-tail power ≥0.8; no project data entered the calculation.

### Pilot acceptance rule

1. On 10 **development/validation** talks, generate both S1 and S3 under the same declared budget. Randomize/blind arm identity for the single author. Score source-linked factual support and key-point coverage at a predefined granularity. Record per-talk paired differences, unscorable units and start/end time for each pair.
2. Compute paired-effect variance and required n from the **within-talk difference**, not the two independent-arm variances. Use a paired-power implementation such as [statsmodels `tt_solve_power`](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.tt_solve_power.html) with the declared alpha/power and any multiplicity adjustment. Do not copy the old phase-06 formula without checking whether it double-counts variance after standardization.
3. Freeze final n as `max(50, n_required)` if H2 remains the registered human outcome. Compare measured time per pair × final n (plus declared QA/contingency time) with the actual committed researcher capacity. **No capacity decision is possible without both measured time and available hours.**
4. If feasible, run blinded final human H2 on the frozen test cohort. If not, amend H2 **before** final-test access: automated source-grounded metrics as primary, blinded 20–50-talk author audit as calibration/supporting evidence, no claim of a confirmed human improvement. If neither route is validated, retain a paired diagnostic only.

A missing human label must remain missing. Current [summary evidence runner](../../multimodal-lecture-summarizer/benchmarks/scripts/run_summary_evidence_evaluation.py) returns 1.0 for missing human labels and therefore cannot certify H2.

## Recommendation and next actions

1. Make `gigant/tib` the first candidate in the [RQ2 plan](../../multimodal-lecture-summarizer/plans/261002-0946-rq2-controlled-summarization/plan.md); keep `tib-bench-text` as smoke fallback and `tib-bench` as optional S4 source.
2. On current TIB revision, produce a metadata-only receipt for train/valid/test and the Lecture test IDs. Check DOI/author/series groups across splits, per-record license, transcript segment timing, and missingness. Keep final-test content/abstract sealed.
3. Select a validation diagnostic, execute and save RQ2 EDA notebook with tables, plots, anomalies, denominators and keep/limit/reject decision. Audit reference quality on development material only.
4. Implement/fix the real paired S1/S3 path, then run the timed 10-talk blinded pilot. Record the observed workload and paired variance in D-T10; determine final n and whether H2 remains feasible before final-test opening.

## Unresolved questions

- How many of the 94 historical Lecture candidates remain after **current** source/split, rights, grouping and transcript-quality checks?
- What are the measured paired-score variance and minutes per blinded S1/S3 talk in the 10-talk pilot?
- How many researcher hours are actually committed for the final author audit, and is required institutional review/approval applicable and complete?
