# RQ2 automatic evaluation amendment — 2026-10-02

**Active scope, 2026-10-09:** The all-split EDA, including full-transcript reference screening, has completed. The current pool is all **8,769 candidates**; all 900 flagged candidates stay included. Automatic data preparation has no manual-review gate and no 70-item cap. The [preparation notebook](../../experiments/notebooks/rq2-tib-benchmark-preparation-colab.ipynb) creates the reusable dataset for paired creator-abstract ROUGE-L agreement. Follow the [active plan](plan.md); sealed-test and small-cohort procedures below describe the historical design.

## User decision and claim

RQ2 uses **no blinded or other human scoring**. The earlier human factual-support, key-point-coverage, calibration, power-pilot and 50-talk requirements are withdrawn. A reproducible automatic paired S1/S3 comparison can support a study with a limited claim. A small cohort is acceptable when its uncertainty is reported. This amendment supersedes conflicting human-evaluation requirements in this RQ2 plan and the older research contract for this study.

## Current evidence tier

The 20 creator-TIB validation Lecture records at revision `e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee` have executed EDA and source-linked ASR. Current S1/S3 generation is a deterministic copied-sentence diagnostic; structure is lexical TF-IDF, input is often truncated, and cumulative prompts are not token-matched. Its scores are **development diagnostics**, not the formal result. Keyframe intervals have no pixels/OCR for this cohort, so S4 is `not_run`. Audio is represented by provided ASR text; audio accuracy is unmeasured.

## Measurement rules

- Unit: one talk/DOI, paired arms on identical eligible talks. Keep failures and missing endpoints in the denominator ledger.
- Development metrics: reference ROUGE-L against provided abstracts, with a separate 12-candidate / 8-unsuitable abstract sensitivity analysis; source lexical overlap, summary length and token/latency measures. Semantic similarity may be secondary if its model revision and runtime are pinned. None of these metrics is factuality.
- Formal primary metric: ROUGE-L F1 against every nonempty creator-provided abstract on a paired eligible talk, even though these are noisy references. This is fixed before sealed-test access in [`rq2-automatic-outcome-config.json`](./rq2-automatic-outcome-config.json). Report abstract-suitability and length sensitivity separately; do not condition the primary cohort on a post-result reference judgment. The claim is abstract agreement, not factual correctness.
- Statistics: paired S3 minus S1 mean/median, percentile bootstrap confidence interval using a fixed seed, and full per-record values. Predeclare secondary family and Holm correction only when testing multiple hypotheses. Report uncertainty instead of enforcing a minimum sample size or favorable threshold.
- Generator fairness: same model, prompt template except structural input, decoding parameters and output budget. Measure with its actual tokenizer; account for every input chunk, map/reduce step and retry. Freeze a per-talk cumulative source/prompt-token budget and record actual usage. No oracle chapters or abstract may enter generation.
- Sealed test: freeze cohort/group rules, inputs, exclusions, generator, structure predictor, metric implementation, reference screening rule, random seed and analysis script on development data. Then execute once on held-out items. Do not use sealed targets for selection or tuning.

## Claim boundary

An automatic metric difference supports a claim about that metric and this cohort. ROUGE or semantic similarity to noisy creator abstracts does not establish factual correctness; lexical overlap with ASR does not establish source support. To claim factuality later, add a separately validated factuality evaluator and disclose its errors. Missing visual frames or unverified audio do not prevent a text-only RQ2 comparison; they prevent claims about visual/audio contribution.

## Open questions

1. Which available generator can execute the controlled comparison in the target environment?
2. Does the fixed abstract-screen rule leave enough talk-specific references for a useful, albeit uncertain, reference comparison?
