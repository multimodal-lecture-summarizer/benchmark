---
title: Dataset EDA, duplicate screening and independent split preparation
status: completed
---

# Scope

User authorized immediate execution of the next dataset-readiness step. Python research pipeline in the nested application; preserve all existing dirty work and historical evidence. Produce executed notebook(s), real measured EDA, duplicate decisions and a versioned clean-split manifest. No model inference, downloads, commits, or whole-project D2 completion claim.

## Reviewed implementation contract

1. Read local TED validation/test Arrow metadata without decoding the entire corpus. Resolve the historical 20 utterances to authoritative speaker/source metadata; fail closed if any cannot be resolved. Exclude their entire speaker/source groups from new candidates. Predeclare deterministic SHA-256 rank, target 30 validation + 20 test from native splits, no replacement after failed decode. Enforce group disjointness. Save the protocol and selected IDs before selected-media decoding or duplicate screening. Insufficient candidates must be reported, never filled from contaminated groups.
2. IIIT uses its documented official Frames/val and Frames/test course groups, replacing the prior diagnostic train-derived validation subset only in a fresh namespace. Derive the missing val image index from sorted PNG/XML pairs; record malformed/missing/orphaned annotations. Preserve released labels; no new labels.
3. Screen every selected image/audio file after identity and full-decode verification. Exact content/decoded identity, source/speaker overlap, image dHash and audio waveform fingerprints form a versioned bounded screening protocol. Similarity is a conservative exclusion rule, not proof of semantic uniqueness. All hits retain pair scores, threshold, decision and reason. Across-split conflicts exclude validation-side units; historical TED similarity excludes new units. Never move failed/excluded samples into test or refill based on observed scores. Recheck retained splits and explicitly record method limitations.
4. Generate actual universal EDA plots from measured per-unit records: scale, duration (images explicitly N/A), file size, GT/missingness, attrition, split composition, source overlap and exact/near duplicate matrices. Each figure binds source table/file hash, code, protocol, units, scope, denominators and exclusions. Save underlying tables, manifests and PNG figures. An unavailable metric must be visibly N/A, never a zero observation.
5. Existing official freeze gates remain fail-closed unless every corresponding contract is proven. New clean-split artifacts are preparation evidence, not model-selection results or blanket D2 approval. No runner consumes them implicitly.
6. Save execution, commands, tests, tables, figures and failures in timestamped notebooks. Verify deterministic selection, historical-group exclusion, native split boundaries, duplicate detection/exclusion, corrupt media failures, honest missingness, hashes and historical preservation. Review code before final runs; inspect real outputs and update master phase progress without promoting partial evidence.

## Ownership

Plan review approved. Protocol additionally requires uniquely resolved historical identities, all-20 historical comparisons, explicit expected/completed comparison denominators, and blocked outcomes for insufficient retained sample/group counts. Pre-execution review found and repaired missing-comparison zero displays and decoder-clamped truncated audio acceptance; notebook timeouts retain partial logs.

- Dataset worker: new local selection/extraction helper for TED and official IIIT inventory, focused fixtures/tests; no shared profile edits.
- EDA worker: new measured universal EDA renderer and focused tests; optional integration only with parent coordination.
- Parent: protocol-driven duplicate screening, orchestration, source notebook and integration.
- Reviewer: plan/code review. Tester: execute notebooks and capture failures. Reuse agents for documentation and preservation audit during closeout.

## Acceptance / remaining boundaries

- [x] Protocol and selected IDs frozen before content inspection.
- [x] New TED validation/test exclude historical source/speaker groups; native IIIT course-disjoint splits recorded.
- [x] Measured screening and deterministic decision log; retained cross-split hits zero under declared methods, or explicit blocked status.
- [x] Sixteen universal plots rendered with honest N/A and auditable source tables.
- [x] Executed notebook, targeted tests, receipt/hash checks and preserved historical artifacts.
- [x] Master phases reconciled; unsupported endpoint GT/full-DAG/candidate expansion remain open.

## Implementation checkpoint — 2026-09-26

Selection/extraction, container validation, bounded duplicate screening, real universal-plot renderer and notebook orchestration are implemented. The source notebook was removed on 2026-10-08; its initial and final executed copies remain in `experiments/notebook_history_20260926.zip`. Tests, dataset run, final cohort counts, sixteen rendered plots and historical preservation are verified in the final results below.

Output is an independent preparation bundle: protocol, selected IDs, extracted metadata, screening/decision log, retained split manifests, figure source tables/PNGs and a hash-bound bundle receipt. Existing official D2 bundles stay untouched and pending; no model inference or official eligibility promotion. Master phases 1/2 stay in progress and 3–7 pending.

## Initial readiness execution — historical checkpoint

The initial notebook completed **31 tests**, no errors, and **16 actual plots** in the new cohort namespace. Its bundle contained **122 files**; **602 historical files** and the separately tracked **82 pre-existing files from the dirty worktree** remained unchanged. This is preparation evidence, not official D2 eligibility.

| Dataset | Retained validation | Retained final test | Observed attrition |
|---|---:|---:|---|
| TED-LIUM | 26 | 16 | All 50 decoded; 8 excluded for ignored GT |
| IIIT-CVID | 546 | 1755 | 3 near-duplicate validation units excluded |

At the initial checkpoint, final verification was pending. Review found that nonempty ignored TED reference markers were counted as GT coverage, and GT exclusions incorrectly prevented media-fingerprint comparisons. Both paths were corrected: GT coverage must respect GT validity; media fingerprints are independent of GT eligibility so all **2,225** planned TED comparisons can execute (initial run completed **1,701**). The fixed protocol, thresholds and selected IDs are unchanged; no replacement units are selected.

The final notebook rerun tested these corrections; verified results are recorded below. Keep the initial notebook/results as history. The sixteen new plots are actual rendered plots, while old official-bundle SVG cards remain historical placeholders. No D2 promotion, model inference or full-phase completion is claimed.

## Final dataset-readiness verification — 2026-09-26

The corrected notebook passed **33 tests in 4.65 seconds**. All commands returned 0 and all cells completed with **0 errors**. Sixteen actual PNG plots were rendered and checked; corrected TED GT coverage is **26/30 validation** and **16/20 final test**. The zero-hit TED duplicate matrix represents completed comparisons, not missing measurements.

| Dataset | Completed / expected media comparisons | Detected hit pairs | Retained validation / final test | Decisions |
|---|---:|---:|---:|---|
| TED-LIUM | 2,225 / 2,225 | 0 | 26 / 16 | All 50 decoded; 8 ignored-GT units excluded; comparison still includes their media |
| IIIT-CVID | 2,653,056 / 2,653,056 | 6,455 | 546 / 1,755 | Hits mostly within split; 3 validation units excluded; 0 retained cross-split hits |

The final bundle contains **122 files**. **602 historical artifacts** and **82 pre-existing files from the dirty worktree** remained unchanged. Initial/final protocol and selection SHA-256 identities match: no refills or threshold changes occurred after inspecting results. Initial-run coverage/comparison issues and their corrections remain recorded above.

- Executed notebook (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/dataset_readiness-20260926T101743497388Z.ipynb`.
- Fresh bundle (nested app): `experiments/outputs/dataset_readiness_260926/20260926T101747121197Z/bundle`.

The scoped preparation plan is complete. These fresh cohort plots and screening results do not overwrite the old official eight-card SVG bundles or promote them to D2. Split manifests retain `scientific_selection_eligible=false`; bounded screening is not proof of semantic uniqueness. No model inference was performed. Master Phase 1/2 remain in progress; Phases 3–7 remain pending.
