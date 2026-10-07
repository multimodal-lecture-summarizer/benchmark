---
title: "RQ2 controlled hierarchical lecture summarization"
description: "Qualify a real lecture cohort, compare controlled summary structures, and report measured factual coverage."
status: pending
priority: P1
branch: "baseline/pre-phase1-snapshot"
tags: [benchmark, rq2, summarization, experimental]
blockedBy: []
blocks: []
created: 2026-10-02
createdBy: "ck:plan"
source: skill
---

# RQ2 controlled hierarchical lecture summarization

**Execution update, 2026-10-07:** Follow the [current three-step workflow](../../docs/BENCHMARK.md#quy-trình-nghiên-cứu-hiện-hành). The active notebook manifest is empty and `on_demand`; run EDA for the selected dataset/cohort, then create an evaluation notebook after the comparison is fixed. The historical smoke and 05a/05b flow below is not an active run sequence.

**TIB scope update, 2026-10-07:** At the user's direction, the new [all-split Colab EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) covers every record in pinned `train`, `valid`, and `test` regardless of `genre`. Report genre descriptively and retain invalid/missing-input rows in a `(split, source_index)` ledger. Previous 20-item and 70-Lecture evaluation outputs and score reports were withdrawn for reanalysis; notebook code remains. The EDA will inspect `test` content, so later claims cannot treat that creator split as an unseen holdout.

## Overview

Answer RQ2 with a text-only paired S1–S3 comparison on real talks, then test whether predicted structure improves predeclared automatic summary-quality outcomes. The [2026-10-02 amendment](./rq2-automatic-evaluation-amendment.md) removes all required human scoring and fixed sample-size floors. Freeze the cohort, automatic outcome and measured equal-token protocol before evaluation. A negative or inconclusive result is valid. An unseen-holdout claim requires a new independent source after all-split TIB EDA. No numerical target or existing report value is a result until reproduced from admissible source records.

## Current evidence and scope

- The older [research contract](../260901-unified-scientific-benchmark/framework/00-master-plan.md) names VISTA primary and `gigant/tib-bench` external. The [registry](../../experiments/registry/research_decisions.yaml) marks VISTA full D0/unavailable. [Creator TIB](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) is the first text-cohort candidate: it provides official train/validation/test splits, transcript segments, abstract and source DOI. A historical probe found 98 Lecture test IDs and 94 preliminary usable records; these are not yet RQ2-qualified. [TIB-bench-text](https://huggingface.co/datasets/gigant/tib-bench-text) was a train-only historical diagnostic fallback, and [TIB-bench](https://huggingface.co/datasets/gigant/tib-bench) is an optional slide source. See the [feasibility research report](../reports/rq2-dataset-human-feasibility-261002-1001-research-report.md). Other published cohorts may enter if they pass endpoint-specific checks and the official protocol is amended before final scoring.
- A [validation-only RQ2 EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) has executed on creator TIB revision `e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`; see its [decision](./rq2-tib-validation-eda-decision.md). The earlier 20-record S1/S3 evaluation outputs were removed; [automatic evaluation notebook code](../../experiments/notebooks/diagnostics/rq2-valid-automatic-evaluation.ipynb) remains without saved outputs. The earlier 05a/05b notebook flow is no longer registered in the [active manifest](../../experiments/notebooks/notebook_manifest.yaml).
- The legacy synthetic-reference RQ2 result JSON was removed. No old score is eligible as current RQ2 evidence.
- Existing broad [benchmark overhaul](../260904-scientific-benchmark-overhaul/plan.md) overlaps RQ2 but contains preset outcome numbers. This plan is the executable RQ2 protocol. Its data and metric gates govern RQ2 work; no cross-plan hard dependency is declared because the overlapping phase is marked completed while the current evidence is blocked.

## Decision tree

1. **Historical engineering check:** the former plan used 1–5 real source-linked records to verify the pipeline. This is not a current notebook phase or evidence of summary quality.
2. **Research diagnostic:** select a small, declared development cohort, run executed EDA on those actual records, and compare S1 against S3 using real transcript segments and source-only predicted structure. No video download, slide or oracle chapter is needed for the text comparison. Report source overlap as lexical overlap and abstract metrics as agreement with noisy descriptions, never factual support.
3. **Formal automatic study:** choose a stable source/transcript cohort and group-safe evaluation partition. Freeze the generator, tokenizer, cumulative token budget, structure predictor, automatic primary outcome, reference eligibility rule, exclusions and analysis before scoring. Use provided creator abstracts as noisy reference proxies with stratified sensitivity; do not call ROUGE, semantic similarity or lexical source overlap factuality. After all-split TIB EDA, creator `test` is an inspected split, so a truly unseen test requires independent data. The [amendment](./rq2-automatic-evaluation-amendment.md) records the earlier human-protocol change.
4. **Optional extensions:** S0 as lower bound, S4 only where aligned real slides/OCR exist, S2 only where genuine chapter semantics exist, VISTA only if media/ASR is feasible. Missing extension evidence yields `not_run` for that arm, without invalidating the S1–S3 text comparison.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Freeze cohort and execute EDA](./phase-01-freeze-cohort-and-execute-eda.md) | Pending |
| 2 | [Materialize source aligned inputs](./phase-02-materialize-source-aligned-inputs.md) | Pending |
| 3 | [Build controlled S0 S4 comparison](./phase-03-build-controlled-s0-s4-comparison.md) | Pending |
| 4 | [Validate automatic outcomes and freeze protocol](./phase-04-pilot-factuality-and-power.md) | In progress |
| 5 | [Run sealed automatic evaluation and report](./phase-05-run-sealed-evaluation-and-report.md) | Pending |

## Dependencies and gates

`P1 candidate/EDA → P2 text inputs → P3 S1–S3 diagnostic → P4 automatic pilot/freeze → P5 sealed test` describes the earlier detailed phase plan. The current sequence is dataset and candidate selection, executed EDA, then same-scale evaluation. Creator `test` will be inspected in the all-split EDA, so P5 cannot use it as a sealed test. EDA is required before calling the selected cohort research-ready. Missing visual or oracle data blocks only S4/S2. The formal gate requires source provenance, group-safe pairing, a real declared generator, measured token fairness and a frozen automatic outcome protocol. A historical dry plan, smoke run, synthetic fixture or old JSON is not official RQ2 evidence.

## Success criteria

- A versioned diagnostic-cohort manifest and executed RQ2 EDA notebook for the actual selected records, with counts, plots, anomalies, exclusions, source-link receipts and keep/limit/reject decision. A formal-test manifest is frozen later, only if that tier is attempted.
- For each analyzed talk: source ID/hash, transcript and predicted-structure provenance, summary outputs, token ledger and endpoint-specific evaluation record. Identify any creator abstract as an unverified provided target. Missing inputs produce arm-specific `not_run` or exclusion with reason.
- Pre-registered S3–S1 paired effect and uncertainty for one automatic primary outcome; multiplicity control only for additional tested hypotheses. Preserve item-level scores and report abstract-quality sensitivity. No human scores are required.
- Report states measured outcomes, denominators, missingness, limitations and the applicable dataset-specific claim. No fixed 2.39%, 27.87% or ≤2.5% value is copied forward as observation.

## Open questions

1. How many creator-TIB records in each of train/valid/test remain text-usable after full-split source, grouping and transcript checks, without a genre filter? Determine from executed EDA; do not call creator test unseen afterward.
2. Which real generator/model weights or API endpoint will be available for the controlled run? The current environment has a cached tokenizer but no verified model weights or configured API key.
3. Which fixed talk-specific abstract rule yields a useful reference subset, and how sensitive are results to the 8 unsuitable validation abstracts?
