---
phase: 1
title: "Enforce Fail-Closed Endpoint Eligibility"
status: completed
priority: P1
dependencies: []
---

# Phase 1: Enforce Fail-Closed Endpoint Eligibility

## Overview

Make endpoint selection a mandatory, integrity-checked part of official/full runs for every runner that consumes frozen units. Missing, unreadable, malformed or stale endpoint-matrix evidence must never disable filtering and fall back to all D2 datasets. Preserve fixture compatibility only through explicit test/smoke setup, not silent production fallback.

## Requirements

- Functional: Select only frozen datasets explicitly eligible for the runner's endpoint(s); fail before model execution when no eligible units remain.
- Non-functional: Keep artifact receipt validation, deterministic selection, existing valid TED-LIUM ASR behavior and documented schemas.

## Architecture

`RunnerContext` identifies profile, namespace and notebook. Map every notebook that calls `load_eligible_units` to explicit endpoint IDs or an explicit multi-endpoint contract. Load `dataset.endpoint_matrix` via the artifact API, validate its receipt/schema/hash, derive an allowlist, and intersect it with `dataset.frozen_manifest`. Do not convert validation exceptions into an unrestricted allowlist.

## Related Code Files

- Modify: `experiments/scripts/stage_benchmark_helpers.py`
- Read: `experiments/scripts/benchmark_artifacts.py`, `experiments/evaluation/dataset_contracts.py`, `experiments/scripts/profile_dataset.py`
- Read: all callers of `load_eligible_units` under `benchmarks/scripts/`
- Modify tests in `tests/` for helper and runner contracts.

## Implementation Steps

1. Inventory every `load_eligible_units` caller, including `07b`, `08a` and `08b`; identify whether each runner consumes one endpoint or requires a validated set of upstream modalities.
2. Reconcile endpoint names against live `dataset.endpoint_matrix` rows; remove aliases that are not part of the schema or explicitly document and test them.
3. Require a valid endpoint-matrix artifact and receipt for `official`/`full` runs. For smoke/test contexts without a matrix, require an explicit opt-in fixture policy or synthesize no eligibility; never infer `eligible` from frozen manifest alone.
4. Treat read errors, checksum/receipt mismatch, wrong schema, missing rows and empty endpoint allowlists as a closed gate with actionable errors.
5. Intersect endpoint allowlist with frozen records marked eligible and return only matching unit records; make multi-endpoint runners require the intersection/union policy they actually need, stated explicitly.
6. Add focused tests for absent receipt, malformed artifact, stale receipt/hash, endpoint row false, unknown endpoint, eligible ASR row, unsupported visual row, and composite runner selection.

## Success Criteria

- [x] No exception path sets the endpoint allowlist to unrestricted `None` for official/full execution.
- [x] Every direct caller has an explicit and tested endpoint policy.
- [x] A dataset frozen eligible only for ASR cannot be selected by group 02 or downstream visual/composite runners.
- [x] Valid TED-LIUM ASR still selects its 20 frozen units; absent/corrupt matrix blocks before inference.
- [x] No tests depend on silently omitting `dataset.endpoint_matrix` for official-like execution.

## Risk Assessment

Composite stages may legitimately require multiple upstream modalities while their own endpoint has no direct labels. Define that contract explicitly; do not solve it by dropping endpoint checks or treating a single-task dataset as universally eligible.
