---
phase: 1
title: "Freeze cohort and execute EDA"
status: pending
priority: P1
dependencies: []
---

# Phase 1: Freeze cohort and execute EDA

## Overview

Inspect every record in pinned creator-TIB `train`, `valid`, and `test`, regardless of `genre`, before deciding which records have usable inputs and reference evidence. Produce executed EDA with a `(split, source_index)` ledger. The previous 20-item and 70-Lecture cohorts are historical diagnostics; VISTA full remains pending access and execution. Reading `test` content retires its unseen-holdout status.

## Requirements

- Minimum for text diagnostic: stable source ID, usable transcript/segments or source-bound ASR, duration/timebase where temporal structure needs it, and a declared development selection. Independent abstracts, raw video and slides are endpoint-specific additions. License is not a dataset eligibility gate for this study.
- Record source/version, available split, transcript provenance, reference author/method if present, duplicate groups and exclusions. Do not assume the text dataset's displayed train split is an official test split.
- Freeze a group-safe evaluation cohort after the EDA and comparison protocol are feasible. The creator-TIB `test` split will have been inspected and cannot support an unseen-holdout claim; define a new independent holdout if that claim is required. If using an alternative to registered VISTA/TIB, amend the official protocol before final scoring.

## Architecture

Dataset adapter → all-split source-row ledger → structural eligibility and reference review → executed notebook → frozen evaluation cohort/hash → keep/limit/reject decision. Creator abstracts can support an abstract-agreement endpoint with stated noise; transcript overlap supports only lexical analysis.

## Related Code Files

- Review/modify: `experiments/scripts/rq2-tib-valid-eda.py`, `experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb`, `docs/DATASET_EDA.md`. Keep `rq2-tib-valid-eda.ipynb` as historical executed evidence.
- Create an evaluation notebook only after the full-validation EDA and cohort decision are complete.
- Evidence: `plans/260901-unified-scientific-benchmark/framework/01-dataset-manifest.md`; legacy probes are leads, not current qualification.

## Implementation Steps

1. Recheck the creator `gigant/tib` revision and official splits. Scan every `train`, `valid`, and `test` source row (9,103 expected); do not filter by genre, author or a fixed sample size.
2. For every source row, record split and source index, DOI, genre, transcript/segment status, abstract, source/media availability and explicit reasons for any unusable input. Count duplicate/missing DOI without collapsing rows.
3. Execute EDA across all three splits: duration, transcript/segment length, genre/topic/group balance, duplicate/missing counts, cross-split overlap and reference length/style/support. Report slide/media availability separately from text eligibility.
4. After EDA, freeze the set that can be scored under one protocol. Keep failed/unscorable rows in the ledger and explain their treatment. A provided talk-specific summary is required for reference metrics; otherwise narrow the outcome. Do not present the historical 20/70 diagnostics as all-validation results.

## Success Criteria

- [ ] Per-source-row ledger covers all pinned train/valid/test records, with observed split counts, a deterministic candidate hash and no invented label or target.
- [ ] Executed notebook includes actual counts, distributions, anomalies and keep/limit/reject decision for the full dataset scope.
- [ ] If a final cohort is frozen, report that creator `test` content was inspected and do not claim it is an unseen holdout.
- [ ] Report states which endpoints the selected data can support; absent slide, chapter GT or abstract does not automatically reject text diagnostic.

## Risk Assessment

Poor or absent references block reference-based metrics. Source-linked text can still support lexical/efficiency outcomes with a narrower claim; overlap alone does not prove factuality. Exact title and author overlap need group review before any formal holdout claim. A pilot subset does not establish corpus-wide feasibility.
