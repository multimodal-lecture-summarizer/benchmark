---
phase: 3
title: "Repair chaptering runners and notebooks"
status: completed
priority: P1
dependencies: [2]
---

# Phase 3: Repair chaptering runners and notebooks

## Overview

Prepare the existing `04a` and `04b` notebooks for RQ1 without producing a scientific result yet. Fix current reference leakage and ensure every input, feature and prediction belongs to the same frozen lecture unit.

## Requirements

- `04a` and `04b` reject missing independent `chapter_boundaries_sec`; no fallback to scene predictions, scene GT or duration midpoint.
- Preprocessing, OCR/visual/acoustic feature extraction and candidate inference must carry the same `dataset_id, unit_id, split, source_sha256`.
- Compare fixed-window and transcript-only baselines to actual multimodal candidates. A label such as C5 must bind a real checkpoint, architecture/version and measured inference; a heuristic toggle is not a learned C5.
- Validation-only candidate/config selection enforced at the shared loader/runner boundary; final test is evaluated once in a separate frozen-evaluation mode, with failure rows kept. Notebook-level filtering and smoke's first-record truncation are insufficient.
- Freeze primary collar F1 at ±3 seconds; report ±5/10 seconds, Pk and WindowDiff as secondary, then paired bootstrap CI, Holm-corrected comparisons and Cohen's d for the full RQ1 study. A diagnostic pilot checks scorer compatibility but does not claim statistical results.

## Architecture

The current manifest makes `04a` consume `asr.raw_predictions`, `scene.raw_predictions`, `ocr.raw_predictions`, `caption.raw_predictions`. Existing ASR/OCR benchmark datasets are disjoint and AVLectures does not have released GT for every upstream stage. Change `04a` to consume one eligible `dataset.frozen_manifest` and derive/cache a hash-bound `chapter.input_features` for those lecture IDs using existing production extraction modules. `04b` consumes that feature artifact and `chapter.shortlist`; update manifests/receipts atomically. Keep the 22 official notebooks; do not create copycat benchmark notebooks. Stage benchmark scores remain separate.

## Related Code Files

- Modify: `benchmarks/scripts/run_chaptering_benchmark.py`, `benchmarks/scripts/run_chaptering_modality_ablation.py`, `experiments/notebooks/notebook_manifest.yaml`, `experiments/notebooks/04a_chaptering_benchmark.ipynb`, `experiments/notebooks/04b_chaptering_modality_ablation.ipynb`.
- Inspect/adapt: `benchmarks/scripts/run_rq1_benchmark.py`, `benchmarks/data/dataset.py`, `benchmarks/models/chaptering.py` for existing C1–C6 train/infer and C5 checkpoint behavior. Avoid a second implementation with the same scientific name.
- Reuse/adjust: `experiments/scripts/stage_benchmark_helpers.py`, artifact/receipt validation, existing AI worker feature extraction and cached-feature conventions.
- Add focused regression tests under `tests/` for missing GT, cross-unit artifact mismatch, validation/test separation, checkpoint identity and manifest edges.

## Implementation Steps

1. Remove `scene_boundaries_sec` fallback from `run_chaptering_benchmark.py:88-94,145-153` and scene/duration fallback from `run_chaptering_modality_ablation.py:108-115`. Require source-backed chapter GT and log a clear blocked reason when absent. Remove generic prediction-to-midpoint substitution at `run_chaptering_benchmark.py:175-178` and `run_chaptering_modality_ablation.py:84`; empty predictions are retained and scored under a frozen zero-boundary policy, or reported as candidate failure, never fabricated into a hit.
2. Define `chapter.input_features` schema and cache key over unit media/transcript hashes, model revisions, extraction config and code revision. Extract each modality only from that unit; reject missing modalities for the declared comparison rather than silently downgrade.
3. Add an explicit fail-closed split allowlist to the shared eligibility loader/context and runner CLI. Selection/pilot mode admits only frozen `validation` IDs; final-test evaluation mode requires a previously frozen configuration and admits only `final_test`. Bind split/mode in run identity, receipt and cache key; reject mixed or missing split flags. The executor's current `--dataset` is not a split selector.
4. Adjust manifest `04a.requires/produces` and `04b.requires` with the executor's dependency/receipt tests. Preserve 22 nodes and prevent a local diagnostic from masquerading as an official upstream artifact.
5. Map 04a/04b to the existing `run_rq1_benchmark.py` and `benchmarks/models/chaptering.py` training/inference path, or document why a thin adapter is necessary. Verify training uses only frozen train units, records seed/checkpoint/data/code hashes, and cannot inspect validation/final-test GT during fitting. If a C5/C6 checkpoint is absent or incompatible, report `not_run` for that candidate and keep RQ1 claim blocked; do not relabel heuristic methods.
6. Replace both runners' hard-coded ±30-second collars with the frozen ±3-second primary scorer and secondary metrics. Tests cover empty prediction, one boundary, exact/collar-edge matches and multiple boundaries; statistical scripts use paired lecture-level units only when official data exists.
7. Update 04a/04b notebooks as thin launchers displaying provenance, sample counts, raw prediction paths, metrics and failures from runner artifacts. Keep their source and in-place outputs consistent with the one-notebook-location convention.

## Success Criteria

- [ ] Neither runner can score a unit without independently sourced chapter GT; adversarial fixtures for scene/duration fallback fail closed.
- [ ] Every compared modality uses the same lecture IDs and split; mismatched source/config/hash is rejected before inference.
- [ ] Validation selection and frozen final-test evaluation are separate and auditable; no test score tunes configuration.
- [ ] Adversarial ordering tests prove neither 04a nor 04b can load a final-test ID in selection/pilot mode, even when that ID is first in the frozen manifest.
- [ ] Real candidate list/checkpoints match the reported method names. Missing learned checkpoint is visible `not_run`.
- [ ] C1–C6 adapter reuses existing training/model code with train-only provenance; no second heuristic is named C5/C6. If disjoint training data is inadequate, learned comparison is `blocked_data`.
- [ ] 04a/04b no longer use ±30 seconds as primary; ±3 seconds and secondary metrics match the master RQ1 contract. Empty predictions do not become midpoint boundaries.
- [ ] Manifest edge and receipt regression suite passes; 04a/04b notebooks are generated/executed from registered runners, not copied metric logic.

## Risk Assessment

Changing manifest dependencies affects downstream 05–09 receipt hashes; version the contract and test affected consumers. Feature extraction may need more compute than a small local pilot permits; keep bounded sampling and explicit `blocked_compute` status. Do not use another dataset's stage benchmark outputs as a substitute.
