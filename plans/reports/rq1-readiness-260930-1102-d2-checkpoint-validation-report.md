# RQ1 pretest D2, checkpoint and precision receipt

**2026-09-30. No official RQ1 inference or sealed final-test score opened.** This report follows the locked 20-unit cohort and 8/4/8 split. The source-only D2 binder ran on the original annotation files and exact local publisher media, not candidate outputs.

## D2 source evidence

[`rq1-d2-source-bundle-260930-twenty-units.json`](./rq1-d2-source-bundle-260930-twenty-units.json), SHA-256 `996be6ce301bc60a0012924e1a84bf04e528646ea34a1c557fbda48ac2f55d00`, contains **20/20** locked units: 2 YTSeg, 4 VidChapters, 14 publisher-native Yale. Each unit binds its original internal starts and labels; annotation source revision, row locator or record offset; media file size and freshly recomputed SHA-256; prior full-decode receipt and receipt hash; exact scoped-rights gate and its SHA-256; course, lecturer and locked split. No timestamps or labels were rewritten. The binder checks the original YTSeg `target_ts` against raw chapters, bounded VidChapters description pairs against prior qualification starts, Yale publisher pairs against source metadata, and every unit against the chapter D2 unit schema. It also reruns the course/lecturer split and project-use-history guard.

This closes the **GT/media/rights source receipt** for the 20 selected units. The [frozen D2 dataset package](./rq1-d2-frozen-dataset-260930-twenty-units.json) and [freeze receipt](./rq1-d2-freeze-receipt-260930-twenty-units.json) now pass the repository's full `validate_dataset_bundle` contract: 1 dataset, 20 units, 1 D2-eligible dataset. The [registry YAML](../../multimodal-lecture-summarizer/experiments/registry/datasets/rq1_locked_mixed_20_d2.yaml) identifies the mixed cohort; the per-unit source bundle retains each publisher revision and scoped-rights decision. This D2 **dataset** freeze does not yet bind the exact transcript/feature inputs shared by 04a/04b and does not authorize candidate selection or final test. The private media remains local/ignored; ECON 159 L2 currently resolves to a hashed MOV in `C:\Users\hung\Downloads`, which must stay accessible or be relocated with a new receipt before execution.

## Learned checkpoint provenance

[`rq1-checkpoint-provenance-audit-260930.json`](./rq1-checkpoint-provenance-audit-260930.json) records **train-only proof not established**. Existing `c5_real.pt` has SHA-256 `94d22d232ce23dcf2ce11176104db8932928c0642d1f83adea32c124b2e4c17d`, but no sibling provenance receipt linking its 20 cached-feature source videos to this cohort or the locked train groups. `c6_real.pt` is absent. Both remain `not_run`. The current generic checkpoint guard checks unit/course separation but lacks shared-lecturer and locked-split binding; future learned receipts must cover those identities, train input and code/config/seed hashes, and validation-only selection.

## Validation precision

The four locked validation groups are `tCKk22kaZi4`, `f_55cmhHq3g`, `VX4eYYmvQ78`, `Hy7ou5R_vjE`. No candidate F1@3 s receipt exists for them; hence **no empirical** `s_val` or required `G_test` can be calculated. [`rq1-validation-precision-preflight-260930.json`](./rq1-validation-precision-preflight-260930.json) records `not_estimable`, without substituting old benchmark results or synthetic scores. The predeclared formula permits eight final-test groups only when the largest sample SD among the four validation paired contrasts is at most `0.288615`. [`rq1_validation_precision_gate.py`](../../multimodal-lecture-summarizer/experiments/scripts/rq1_validation_precision_gate.py) now enforces the exact validation-only IDs and complete C1–C6 primary scores before computing that threshold; it rejects any final-test score row. The C5−C6 contrast cannot be computed while those checkpoints remain `not_run`.

## Validation performed

- Source binder: completed 20/20 whole-file SHA checks and chapter D2 unit validation; output SHA above.
- Frozen dataset: `validate_dataset_bundle` passed with 20/20 locked units and exact 8/4/8 split; candidate/feature gates remain blocked.
- Precision gate and split-guard focused tests: 15 passed.
- No candidate prediction or final-test metric was used to change cohort, GT, rights or split.

## Unresolved questions

1. Which frozen transcript and modality feature inputs will 04a and 04b share for all 20 units before candidate execution?
2. Can new C5 and C6 checkpoints be trained on exactly the eight locked train groups with course **and** lecturer provenance and validation-only selection?
3. After real validation candidate scores exist, is the largest paired-group SD ≤0.288615? If not, the available eight final-test groups do not meet the predeclared planning precision floor; keep test sealed and amend scope before opening it.
