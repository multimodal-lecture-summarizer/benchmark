# RQ2/RQ4 technical pilot

Status (2026-10-10): pilot executed and reviewed; 120-record evaluation scope approved; IDs and protocol freeze pending.

- [x] Audit actual S1/S3 mechanism and budget accounting: boundary-constrained chunking under shared map-reduce, with equal allocated intermediate/final output caps and actual token use measured.
- [x] Reuse 8,769-record prepared evidence; CPU token lengths and nine-record source-only preflight.
- [x] Standalone notebook, failure/cost receipts, conservative forecast gates.
- [x] Focused preparation verification: 52 tests, seven notebook code cells, embedded-module identity and ZIP CRC.
- [x] User Colab pilot completed: 9/9 train records, 18/18 arms, ROUGE-L/BERTScore/source SBERTScore paired coverage 9/9; no reported failures.
- [x] Approve target 120 evaluation records: 40 short / 40 medium / 40 long; two arms, one configuration and no repeats (240 summaries).
- [ ] Review source/dependence groups, declare evaluation split, select IDs deterministically independently of model-quality scores, exclude nine development IDs and freeze the cohort/protocol.
- [ ] Run formal benchmark only after freeze; current formal evaluated count is 0. OCR follows.

## Recorded decision

Tesla T4 / map batch 2 / pinned Qwen2.5-1.5B-Instruct pilot costs support a 120-record forecast of 4.9954 hours using stratum means or 8.3747 hours using the observed maximum cost per stratum. Both include initialization, S1 and S3, three metrics and 30% margin. This is a technical planning scenario, not a confidence interval, a guarantee below 12 hours or evidence of statistical power. Additional configurations, repeats or changed hardware require a revised budget. Full 8,769-record execution is superseded (mean forecast 360.3528 hours). Do not rerun the pilot solely to obtain a larger-scale estimate.

Keep the 9,103 source / 8,769 eligible counts as EDA-pool evidence. Do not select evaluation IDs because S3 wins or remove difficult/long/failed IDs after outcomes. Creator references already inspected remain exposed; the claim is text-only creator-abstract agreement, with no factuality or unseen-generalization claim. No local GPU work or automatic benchmark launch.

Owning protocol: [RQ2 plan](../261002-0946-rq2-controlled-summarization/plan.md). Machine-readable decision: `experiments/registry/datasets/tib-rq2-rq4-120-decision-261010.json` (repository-relative). The [technical preparation report](../reports/rq2-pilot-261010-1632-technical-design-report.md) remains historical for execution status; preserve its evidence and unrelated dataset HOLDs.

## Pending decisions

Evaluation split, source/dependence-group handling, exact 120 IDs and protocol freeze remain pending review.
