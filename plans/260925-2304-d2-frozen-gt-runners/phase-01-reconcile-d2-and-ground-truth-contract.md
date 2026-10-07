---
phase: 1
title: "Reconcile D2 and Ground Truth Contract"
status: completed
priority: P1
dependencies: []
---

# Phase 1: Reconcile D2 and Ground Truth Contract

## Overview

Audit live dataset sources, D2 registry/configs, receipts, frozen manifests, endpoint matrix and GT annotations. Freeze eligibility only for dataset × endpoint pairs whose rights, immutable inputs, labels, split/leakage controls and reproducibility evidence all pass. A valid D2 freeze for one task does not imply eligibility for another.

## Requirements

- Functional: D2 and GT validation is fail-closed; missing/weak/pseudo labels are represented accurately and cannot silently qualify as released GT.
- Non-functional: Preserve reproducibility, auditability and existing validated TED-LIUM artifacts unless an explicitly expected output change is documented.

## Architecture

Use existing `experiments/evaluation/dataset_contracts.py`, registry loader/contract validator, `experiments/registry/datasets/*.yaml`, `research_decisions.yaml`, Phase 2 receipts and `dataset.frozen_manifest.json` as the contract path. Ground truth is endpoint-specific; runner eligibility must derive from validated frozen IDs and endpoint matrix, not dataset presence alone.

## Related Code Files

- Read: `experiments/evaluation/dataset_contracts.py`
- Read: `experiments/scripts/phase2_freeze_tedlium.py`, `experiments/scripts/profile_dataset.py`, `experiments/scripts/benchmark_artifacts.py`
- Read: `experiments/registry/datasets/tedlium3_d2.yaml`, `experiments/registry/research_decisions.yaml`, `experiments/notebooks/notebook_manifest.yaml`
- Modify only if audit proves necessary: dataset registry/config, freeze driver, contract validators and focused tests.

## Implementation Steps

1. Capture worktree ownership and current branch; preserve existing untracked/user changes.
2. Build a dataset × endpoint matrix from tracked registry, receipts, annotation files and live source provenance. Verify rights, source/revision, checksum, decode, stable IDs, split assignment, leakage audit, attrition and reproducibility.
3. Verify GT release status, source/revision, annotation protocol, unit alignment and endpoint metric compatibility. Classify manual/released labels separately from heuristic, weak, pseudo or absent labels.
4. Compare matrix claims against D2 frozen manifest, dataset registry and endpoint matrix. Resolve schema/state drift at the shared contract layer; keep unsupported pairs ineligible.
5. Regenerate or validate receipts only for audited frozen inputs. Record hashes and any expected artifact delta; do not infer eligibility from D1 or local readability.
6. Publish a concise gate table with `eligible`, `not_eligible`, `blocked` or `not_run`, evidence paths, and remaining blockers for every candidate pair.

## Success Criteria

- [x] Every `scientific_selection_eligible=true` claim has validated source, rights, identity, checksum, decode, released GT, split/leakage and receipt evidence.
- [x] Registry, frozen manifest and endpoint matrix agree on eligible IDs and GT state.
- [x] Synthetic/fixture smoke data is explicitly excluded from official eligibility and scientific results.
- [x] Existing TED-LIUM manifest identity is unchanged unless a documented expected delta is required and approved by the accepted plan scope.
- [x] Endpoint gate table identifies any GT/provenance inputs still needed before runner execution.

## Risk Assessment

Dataset availability and annotations can differ from older plans. Mitigate by reading current files and receipts, preserve rights restrictions, and stop eligibility claims where provenance or GT cannot be demonstrated.
