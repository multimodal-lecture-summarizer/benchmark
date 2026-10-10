# Dataset readiness: local split preparation and measured EDA

## Scope

The dataset-readiness pipeline prepares new local TED and IIIT cohorts, records bounded duplicate screening and renders measured universal EDA. It does not run models, download data or grant official D2/model-selection eligibility. Current status: scoped preparation verified; official scientific eligibility remains pending.

## Selection and evidence contract

| Dataset | Protocol |
|---|---|
| TED-LIUM | Resolve all historical 20 IDs uniquely against native validation/test Arrow metadata. Exclude their entire authoritative speaker/source groups. Freeze deterministic hash-ranked targets of 30 validation and 20 test before decode. No replacement after observed failures. |
| IIIT-CVID | Use documented official Frames/val and Frames/test; derive val index from sorted PNG/XML pairs. Record missing/orphaned/malformed pairs, enforce course separation. Preserve old train-derived validation as historical data. |

`protocol.json` and `selection.json` precede selected-media decoding. WAV/FLAC source declarations are checked independently of decoder-reported frame counts. Empty GT, corrupt media, unresolved identities and missing comparisons remain visible failures. References come from released `text` or XML annotations; Whisper predictions are not GT.

Exact/decoded identity, image dHash and audio waveform fingerprints follow a versioned bounded screening protocol. Cross-split conflicts exclude validation-side units; historical TED matches exclude new units. Keep pair scores, thresholds, decisions, expected/completed comparisons and retained group counts. Zero detected hits only describes these methods; it does not prove semantic uniqueness. Insufficient retained cohorts remain blocked.

## Artifacts and plots

The fresh preparation root contains protocol/provenance/preflight, frozen selection, extraction, per-dataset units, screening logs, split manifests, figure tables/PNGs/manifests, summary and bundle receipt. Split manifests explicitly keep `scientific_selection_eligible=false`.

Sixteen actual universal plots were rendered in the initial run; corrected GT coverage and complete TED comparison outputs were verified in the final rerun below. Missing or inapplicable measurements appear as N/A. The earlier official-bundle universal SVG cards remain `not_rendered` historical placeholders. New standalone figures never rewrite those old receipts or establish official D2 completion.

## Execution and verification

The canonical notebook was removed on 2026-10-08. Initial and corrected final executions remain available as original bytes in [the notebook history archive](../../experiments/notebook_history_20260926.zip); its [manifest](../../experiments/notebook_history_20260926.manifest.json) records original paths and SHA-256. Counts and preservation results are recorded below.

## References and remaining gates

- [Preparation plan](../../plans/260926-1651-dataset-readiness/plan.md).
- [Master scientific plan](../../plans/260921-1943-scientific-benchmark-pipeline/plan.md).
- Phase 1 full-DAG/equivalence, complete Phase 2 qualification/endpoint coverage and Phases 3–7 remain open.

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

- The canonical notebook with the verified final output was removed on 2026-10-08. Original executed bytes remain indexed in `experiments/notebook_history_20260926.manifest.json`.
- Fresh bundle (nested app): `experiments/outputs/dataset_readiness_260926/20260926T101747121197Z/bundle`.

The scoped preparation plan is complete. These fresh cohort plots and screening results do not overwrite the old official eight-card SVG bundles or promote them to D2. Split manifests retain `scientific_selection_eligible=false`; bounded screening is not proof of semantic uniqueness. No model inference was performed. Master Phase 1/2 remain in progress; Phases 3–7 remain pending.
