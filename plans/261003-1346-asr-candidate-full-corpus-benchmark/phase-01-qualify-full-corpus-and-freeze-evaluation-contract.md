---
phase: 1
title: "Qualify full corpus and freeze evaluation contract"
status: completed
priority: P1
dependencies: []
effort: "1-2 days plus full-corpus media scan"
---

# Phase 1: Qualify full corpus and freeze evaluation contract

## Overview

Build a new diagnostic ASR cohort from the entire local `distil-whisper/tedlium` Release 3 Arrow snapshot. Do not reuse the 20-WAV `phase2_freeze_tedlium.py` output or promote old `official/full` receipts. Inventory all 270,323 source rows and verify waveform/media for every eligible validation/test row. Check train/evaluation split identities; train waveform duplicate screening is optional follow-up, not a diagnostic gate.

## Requirements

- Reconcile source split counts 268,263/591/1,469 and expected scorable counts 268,263/507/1,155. Record all 398 ignored validation/test reference markers and any additional exclusions by ID/reason.
- Preserve the release's native split, talk/source, speaker, segment ID and timestamp; verify unique IDs, file identity, duration, decode and reference source. Train/reference labels are for qualification only.
- In benchmark records map source `test` to contract `split=final_test`, while retaining `original_split=test`; `train` and `validation` keep their names. Test the mapping against `validation_units` and `load_eligible_units` before model access.
- Stream metadata/integrity checks from the saved Arrow snapshot; avoid exporting 268k WAVs. For this diagnostic run, require zero train/evaluation speaker/talk/source identity overlap and decode/hash every retained evaluation waveform. Train audio exact/near-duplicate screening is useful follow-up, not a gate; report it as unverified.
- Every retained evaluation unit needs an immutable Arrow locator `(split, shard path/hash, row index, row ID)` plus decoded-audio hash, sample rate, duration and GT hash. A verified streaming loader must resolve this locator to canonical mono 16 kHz audio without requiring a WAV export; changing an Arrow shard invalidates the freeze.
- Keep the source snapshot bound by local Arrow shard hashes. Use the TED-LIUM Release 3 reference fields as supplied and label per-split creator provenance as unverified; no test WER or model prediction is read here.
- Produce a fresh diagnostic cohort and endpoint receipt with `scientific_selection_eligible=false`, a positive diagnostic gate, and an immutable split/GT/media hash. If the current `freeze_status`/helper contract cannot express this safely, extend it explicitly; official callers must still fail closed.

## Architecture

Input: `experiments/datasets/tedlium3/` and `experiments/outputs/full_corpus_eda_261003/tedlium3.json`. Output: a new diagnostic artifact root with unit inventory, Arrow row locators, exclusion ledger, duplicate decisions, frozen cohort, `dataset.registry`, `dataset.endpoint_matrix`, media/GT hashes and receipts. `full` must mean all retained validation/test IDs, never smoke truncation. Group comparisons by source/talk; keep the native test label visible as historically exposed. Training STM/references are checked for provenance but are not assumed to be manually transcribed evaluation GT; confirm reference origin per split.

## Related Code Files

- Modify/extend: `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_tedlium.py` only if it can be generalized without changing its 20-WAV historical contract; otherwise create a separate full-corpus freezer under `experiments/scripts/`.
- Modify if needed: `multimodal-lecture-summarizer/experiments/scripts/stage_benchmark_helpers.py`, `experiments/evaluation/dataset_contracts.py`, `experiments/registry/datasets/tedlium3_d2.yaml` (do not mislabel diagnostic as D2).
- Add focused tests under `multimodal-lecture-summarizer/tests/`; retain historical fixtures unchanged.

## Implementation Steps

1. Record snapshot revision, Arrow/file hashes, license and current free disk/RAM. Check full audio accessibility before deciding whether a download is necessary.
2. Read every source row once; validate schema, segment timings, GT provenance and ignored-reference policy. Build source/speaker/ID index for all three native splits.
3. Resolve Arrow locators to decoded arrays, then stream/checksum/decode evaluation audio exhaustively. Compare all train/evaluation split identities; waveform duplicate screening may be deferred and must remain a stated limitation. Test locator round-trip against row ID, waveform hash and GT hash.
4. Freeze sorted eligible IDs and all exclusions with deterministic hashes. Require validation and test both nonempty and source/speaker disjoint; maintain diagnostic eligibility separate from scientific eligibility.
5. Run no-model qualification tests and verify output receipts against the artifact reader before Phase 2.

## Success Criteria

- [ ] 270,323 source rows accounted for; every evaluation exclusion has an ID/reason; retained denominators match the frozen manifest.
- [ ] All retained validation/test audio decodes and matches frozen media identity; full train source inventory and metadata identity screen recorded. Train waveform overlap may remain unverified for diagnostic use.
- [ ] Each frozen evaluation ID resolves to its exact Arrow row and canonical audio; no runner depends on missing full-corpus WAV paths.
- [ ] Source `test` rows carry both `split=final_test` and `original_split=test`; selection loaders never touch them.
- [ ] Endpoint receipt is consumable by a diagnostic `full` runner and rejected by an official scientific run.
- [ ] Old 20-WAV and `official/full` artifacts remain unmodified.

## Risk Assessment

The embedded waveform is about 53 GB. Train waveform duplicate screening may be deferred; keep the limitation visible in outputs. Native test has historical exposure; this phase cannot restore an untouched holdout.
