---
phase: 2
title: "Qualify and freeze RQ1 cohort"
status: blocked
priority: P1
dependencies: [1]
---

# Phase 2: Qualify and freeze RQ1 cohort

## Overview

Use only a candidate that passed Phase 1. Freeze an independently labeled lecture cohort with D2 receipts for the chaptering endpoints used by `04a` and `04b`; keep audio-only/text-only tracks distinct. Do not target an arbitrary `n=300` before media attrition and a pilot power calculation are measured.

## Requirements

- Released chapter GT must include source, revision, timestamp convention and annotation origin. Scene cuts, clip joins, predicted boundaries and duration midpoints cannot serve as chapter GT.
- Course/source-disjoint train, validation and final test for a learned C5/C6 study; require `course_id` and original `lecture_id` in every AV unit, then select IDs and exclusions before extracting features or examining performance. A validation/test-only cohort can support baseline diagnostics but cannot authorize learned-model claims.
- Record rights, decoded media, duration, SHA-256, transcript/OCR availability, missingness, near-duplicate decisions and measured storage/ETA.

## Architecture

Reuse `00a_environment_preflight`, `00b_dataset_feasibility`, `00c_dataset_eda_and_freeze` and their registered runners. A dataset registry entry binds source and rights; D2 `unit_records` carry `chapter_boundaries_sec` and provenance. The endpoint matrix must explicitly authorize both `chaptering_benchmark` and `chaptering_modality_ablation` for the same eligible units, or both runners must intentionally use a tested shared `chapter` endpoint. Publish a source-table-backed characterization bundle and matching run receipt in a fresh namespace.

## Related Code Files

- Modify: `experiments/registry/datasets/` (new candidate config), `experiments/evaluation/dataset_contracts.py` and profile/feasibility adapter only where video chapter fields need contract support.
- Reuse/adjust: `experiments/notebooks/00a_environment_preflight.ipynb`, `00b_dataset_feasibility.ipynb`, `00c_dataset_eda_and_freeze.ipynb`, `experiments/notebooks/notebook_manifest.yaml`.
- Add focused fixtures/tests under `tests/` for chapter GT provenance, split leakage and rights fail-closed behavior.

## Implementation Steps

1. Freeze candidate source/revision and the selection rule; map course, lecture and original video IDs before decoding. Count independent courses and test whether a course-disjoint train/validation/final-test design is feasible before promising C5/C6. Exclude every item with unknown rights or missing released GT.
2. Decode selected media and compare actual duration with chapter timestamps. Check exact and bounded near-duplicate/source overlap. Record every exclusion and the denominator without replacing failed test units after seeing results.
3. Extend D2 schema only where necessary for boundary arrays and source-backed annotation metadata. Make `course_id` mandatory for AV units; extend the leakage validator to check course/source IDs across splits, since current generic checks only cover unit, hash, speaker and talk IDs. Reject missing/out-of-range/unsorted or prediction-derived chapter labels; prevent output fields from entering GT.
4. Run 00a–00c in a fresh diagnostic namespace first. Render real universal and video-specific EDA from per-unit tables, then issue an official D2 receipt only when all existing gates pass.
5. Freeze split manifest and dataset × endpoint matrix for both 04a/04b endpoint selectors. Preserve final-test IDs sealed; validation can be used for feature/runner pilot.

## Success Criteria

- [ ] Every frozen unit has media checksum, decoded duration, source rights and independently published timestamped chapter GT.
- [ ] Train/validation/final-test feasibility is explicitly measured. Any claimed learned-model run uses nonempty source/course-disjoint splits under validator checks; baseline-only diagnostics are labeled as such. Attrition denominators are reported.
- [ ] D2 characterization figures are rendered from measured tables with source hashes; no placeholder cards count.
- [ ] Validator and endpoint gate authorize both 04a and 04b on the same eligible lecture units. If a gate fails, receipt is `not_eligible` and the affected runner stays blocked.

## Risk Assessment

AVLectures' 10 joined-clip courses can leak edit cues; exclude from primary or report as a separate stratum. YTSeg video may not be rights-cleared even though its metadata is licensed; freeze an audio/text track separately if only those modalities qualify.
