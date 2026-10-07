---
phase: 5
title: "Run sealed automatic evaluation and report"
status: pending
priority: P1
dependencies: [4]
---

# Phase 5: Run sealed automatic evaluation and report

**Scope amendment, 2026-10-07:** The requested TIB EDA reads train, valid and test content. The creator `test` split therefore cannot be treated as the sealed test described in the historical steps below. Run a transparent all-split/internal evaluation if appropriate, or obtain independent unseen data before claiming sealed generalization.

1. Freeze the protocol in the [automatic evaluation amendment](./rq2-automatic-evaluation-amendment.md) on development/validation data. Check source hashes, group policy, generator/tokenizer revision, cumulative token accounting, structure predictor, evaluator and outcomes. Keep sealed test content unopened until freeze.
2. Run paired S1/S3 on the same eligible held-out items and preserve every item-level receipt, failure and exclusion. Do not tune from final results.
3. Calculate the predeclared primary paired contrast and bootstrap confidence interval; report secondary metrics with denominators and the predeclared multiplicity policy. Show sensitivity to abstract suitability, source truncation and group overlap. Report S2/S4 as `not_run` when their inputs are absent.
4. Produce an executed notebook and versioned research report with tables, plots, item-level references, costs, uncertainty, limitations and exact claim scope. Negative or imprecise results remain results. Human scoring is not part of this protocol.

## Success criteria

- [ ] Frozen config and complete item-level receipts reproduce all numbers.
- [ ] Equal generation settings and measured cumulative token budgets are documented.
- [ ] ROUGE/semantic similarity are described as similarity to noisy abstracts; lexical source overlap as lexical overlap. Neither proves factual correctness.
- [ ] Report separates validation diagnostic from sealed evaluation and states `not_run` for unavailable visual, audio or chapter arms.

## Open questions

1. How many group-safe held-out creator TIB records are eligible after the frozen rules are applied?
