---
title: "RQ2 controlled lecture summarization"
description: "Qualify lecture data, inspect the full TIB source, and compare summarization methods on a common scale."
status: pending
priority: P1
created: 2026-10-02
updated: 2026-10-07
---

# RQ2 controlled lecture summarization

The current sequence is [select dataset and candidate families → execute cohort EDA → evaluate on the same scale](../../docs/BENCHMARK.md). Notebook code is created only for a concrete run. The [active manifest](../../experiments/notebooks/notebook_manifest.yaml) is empty; historical smoke and numbered notebook queues are not the execution plan.

## Data and evidence status

- **TIB:** The [all-split Colab EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) targets every record in pinned creator `train`, `valid` and `test`, without a `genre` filter. Expected source counts are 7,282 / 910 / 911; verify actual coverage and usable rows when executed. Use `(split, source_index)` as the ledger key, including rows with absent or repeated DOI. Its new full-cohort cells have no saved output, and it does not decode all media.
- **TIB references:** A creator abstract is a provided description, not automatically a reliable ground truth summary. Audit source linkage and suitability, and state the reference-eligible denominator before choosing a reference metric. Reading the creator `test` abstract during EDA will make that split inspected; it cannot support a later unseen-holdout claim.
- **Historical subsets:** The [validation EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) records a 20-item inspection. Code for a 70-item Qwen comparison remains, but saved outputs and result reports were withdrawn for reanalysis. Neither subset establishes a full-TIB conclusion.
- **VISTA:** The [media EDA notebook](../../experiments/notebooks/diagnostics/vista-validation-media-eda-colab.ipynb) inspected 40 of 1,859 validation videos. Full media access, transcript route, reference quality and GT suitability remain to be qualified before it enters a summarization comparison.

No current RQ2 model or method winner is established.

The [automatic-evaluation amendment](rq2-automatic-evaluation-amendment.md) records the user's decision to use **no human scoring** for this RQ2 study. It predeclared paired ROUGE-L F1 against each nonempty creator abstract as the primary automatic outcome, with a claim limited to **agreement with noisy abstracts**, never factual correctness. Its former sealed-test procedure was superseded by the all-split EDA decision; creator `test` cannot be called unseen after its content is inspected. The pinned [outcome configuration](rq2-automatic-outcome-config.json) is historical until cohort and reference suitability are reconciled for the new all-split scope.

## Comparison to run after EDA

The initial controlled contrast is fixed-chunk S1 versus predicted-structure hierarchical S3 on the **same qualified talks**. Hold the generator/checkpoint, prompt elements unrelated to structure, source transcript, tokenizer, cumulative input/output token budgets and hardware profile fixed. Obtain predicted structure from source-only inputs; do not feed oracle chapter or reference content to S3. Add visual or other arms only if their inputs, labels and matching comparison conditions are verified.

Reconcile the predeclared ROUGE-L F1 outcome with the full-split abstract audit **before** running a new evaluation. If references are unsuitable for the intended claim, amend the protocol explicitly; do not silently change the primary metric or treat lexical source overlap as factual support. Preserve paired item-level outputs, token ledgers, failures, source IDs and uncertainty estimates. A negative result or `no_selection` is acceptable. No blinded or other human scoring is required for this study.

## Next gates

1. Run the full TIB EDA notebook on the pinned revision; inspect its coverage ledger, duplicate groups, abnormal transcript/timestamp rows and reference review queue. Report counts by split and genre as a stratum.
2. Decide whether a text-only TIB cohort supports the proposed automatic endpoint. Document exclusions and source groups before scoring. Qualify VISTA independently if a video-based extension is required.
3. Freeze generator availability, candidates, eligible items, the reconciled automatic outcome, scorer, token budget, failure policy and analysis. Any claim requiring an unseen test must use independent untouched data after the all-split TIB inspection.
4. Create the evaluation notebook for the frozen run. Execute every eligible candidate on the same units and report denominators, failures, paired uncertainty and limitations. Preserve receipts and per-item predictions.

## Open questions

- How many records in each TIB split pass transcript, grouping and reference checks after full execution?
- Which generator/checkpoint and automatic primary outcome can be run reproducibly on the available Colab resources?
- Does VISTA provide usable media and references for the intended video-summary target?
