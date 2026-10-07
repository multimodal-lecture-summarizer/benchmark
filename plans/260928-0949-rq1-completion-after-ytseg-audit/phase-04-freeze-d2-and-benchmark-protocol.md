---
phase: 4
title: "Freeze D2 and benchmark protocol"
status: pending
priority: P1
dependencies: [2, 3]
---

# Phase 4: Freeze D2 and benchmark protocol

## Overview

Only after rights, GT and split gates pass, freeze the official cohort and evaluation protocol with immutable D2 receipts and sealed final test.

## Requirements

- Bind source URL/revision, media/transcript hash, rights ledger, GT annotation origin, unit/group IDs, split, exclusions and endpoint eligibility.
- Confirm the master-plan amendment for any changed YTSeg split/subset or other cohort/GT/protocol choice is dated before D2 freeze.
- Keep creator/editorial chapter boundaries labeled as such. Never replace missing chapter GT with scenes, duration or predicted boundaries.
- Predeclare ±3-second collar F1 primary, secondary ±5/10-second, Pk/WindowDiff, failure policy, model list, feature budgets, selection criterion and group-aware uncertainty method.

## Architecture and related files

- Reuse nested `experiments/registry/datasets/`, `experiments/evaluation/dataset_contracts.py`, `experiments/scripts/dataset_freeze_evidence.py`, `experiments/notebooks/00c_dataset_eda_and_freeze.ipynb` and `experiments/notebooks/notebook_manifest.yaml`.
- Both `chaptering_benchmark` and `chaptering_modality_ablation` must resolve the same frozen unit IDs and eligible `chapter.input_features`; keep diagnostics in a separate artifact namespace.

## Implementation Steps

1. Run bounded decode/duration/hash and boundary-alignment checks on all selected media; record failed units in the denominator and do not mutate source GT.
2. Issue dataset registry, source table, D2 manifest/receipt and endpoint matrix. Verify every receipt against rights, GT, split and hash contracts, including adversarial first-row final-test ordering.
3. Freeze feature extractor versions/configuration and method identities. Learned C5/C6 require train-only training/checkpoint provenance; otherwise they remain `not_run` and are not renamed heuristic fusion.
4. Freeze validation selection and sealed final-test policy; validate dry plan and relevant focused tests before any official inference.

## Success Criteria

- [ ] D2 receipt and endpoint matrix authorize both 04a and 04b on the same eligible cohort, with no stub/dry evidence counted as real.
- [ ] D2 matches the pre-registered design or an explicit dated amendment; a custom YTSeg CC BY split cannot silently inherit the official-split claim.
- [ ] Final-test IDs/GT cannot enter training or validation selection; test proves this even when final-test IDs occur first in the manifest.
- [ ] Frozen protocol and all candidate/feature identities are versioned before Phase 5.

## Risk assessment

Dataset or rights drift after freeze invalidates the receipt and requires a versioned new cohort, not in-place mutation. Missing learned checkpoints remain visible status, not a substitute baseline.
