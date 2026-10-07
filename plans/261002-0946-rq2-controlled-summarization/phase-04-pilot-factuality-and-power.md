---
phase: 4
title: "Validate automatic outcomes and freeze protocol"
status: in_progress
priority: P1
dependencies: [3]
---

# Phase 4: Validate automatic outcomes and freeze protocol

The [2026-10-02 amendment](./rq2-automatic-evaluation-amendment.md) removes all human scoring and any fixed 50-talk minimum. A small cohort is allowed; report its uncertainty and limit the claim.

## Work

1. On creator TIB validation only, retain paired S1/S3 outputs and compute per-record metrics. Current deterministic copied-sentence generation and lexical boundaries are an engineering diagnostic, not the formal S3 treatment.
2. Report summary length, source lexical overlap, reference ROUGE-L and optional pinned semantic similarity. Call source overlap a **lexical proxy**, never factuality or evidence support. Creator abstracts are noisy provided targets; stratify by the existing 12 candidate / 8 unsuitable screen and show sensitivity to omitting unsuitable targets.
3. Use the predeclared [outcome config](./rq2-automatic-outcome-config.json): primary S3–S1 ROUGE-L F1 against all nonempty creator abstracts, with candidate/unsuitable and short-abstract sensitivity. This measures agreement with noisy descriptions. A factual accuracy claim needs a separately validated factuality measure.
4. Save per-DOI source/reference linkage, outputs, evaluator version, paired differences, bootstrap confidence interval, denominator, exclusions and source truncation. Use the generation model's tokenizer and account for every chunk prompt, output and retry. Use the same generator and decoding settings for both arms, with a measured cumulative input-token budget per talk.
5. Freeze selection, group policy, generator, structure predictor, token rule, primary/secondary outcomes, missing-data policy and statistical analysis before scoring. After all-split TIB EDA, only new independent data can support an unseen-test claim. Select sample size by available eligible items and precision, without an arbitrary floor.

## Completion evidence

- [x] Executed automated evaluation on all 20 validation diagnostic pairs, with item-level records and descriptive paired uncertainty in `experiments/outputs/diagnostic/rq2_valid_paired/automatic_evaluation.json` and the executed notebook.
- [ ] Controlled generation and measured equal cumulative token budgets on a development/validation cohort.
- [x] One automatic primary endpoint and analysis config is declared before sealed-test access, with its claim boundary. Generation/backend settings remain to be frozen separately.
- [ ] No result is described as factual accuracy without a defensible validation measure.

## Open questions

1. Can the chosen generator and tokenizer run in the target environment for every selected item?
2. Which validation items provide usable talk-specific abstract proxies under a documented rule?
