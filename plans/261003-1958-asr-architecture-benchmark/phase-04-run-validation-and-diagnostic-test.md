---
phase: 4
title: "Run validation and diagnostic test"
status: pending
effort: ""
---

# Phase 4: Run validation and diagnostic test

## Overview

Run full validation, lock selection, then run native test as a diagnostic and report paired outcomes by architecture lane.

## Implementation Steps

1. Complete six-candidate validation coverage (507 units each), or reconcile every failed attempt. Rank only complete candidates by the frozen WER/CER rule.
2. Freeze validation selection receipt. Open native test only when its identity matches the receipt, then complete 1,155 units per candidate with a separate run root.
3. Report micro WER/CER, per-talk variation, paired differences, coverage, latency/RTF by hardware lane, memory, failures, and training-data/toolchain caveats. Preserve the diagnostic status of the test split.

## Success Criteria

- [ ] Validation and native-test matrices and immutable receipts are complete or explicitly partial.
- [ ] Report distinguishes architecture comparisons from causal architecture claims and diagnostic test from untouched holdout evidence.
