# Nhật ký sửa bằng chứng và chuẩn bị dữ liệu, 2026-09-26

Hai ghi nhận cùng ngày được lưu nguyên văn; hash cho phép đối chiếu từng tệp nguồn.

- 260926-1616-phase12-evidence-repair.md — SHA-256 0f91862fd9febb879bae0cd654df34349aeebd94f6910fff13ecbca3456bf841
- 260926-dataset-readiness.md — SHA-256 ffa9ea6c699e810c253852dece22b7e4c1cc21b49ec580b4ab357df325f88d02

---

## Nguồn: 260926-1616-phase12-evidence-repair.md

---
title: "Phase 1–2 evidence claims repaired"
date: 2026-09-26
status: scoped-repair-verified
---

# Phase 1–2 evidence claims repaired

## Context

The benchmark audit exposed a gap between infrastructure completion and scientific evidence. The master plan described Phase 1 as complete and TED-LIUM as D2 eligible while full-DAG equivalence, reliable provenance, measured resource gates and near-duplicate adjudication were not established.

## What happened

The repair replaces placeholder hashes, seeded disk-pass flags and header-level media checks with actual content identities, reserve-after-peak preflight and full decoding. SHA-only overlap checks now leave near-duplicates pending. Figure enrichment preserves source provenance and receipts. ASR model/config selection is restricted to validation with a deterministic versioned scorer.

All 10 historical TED final-test units had participated in selection. Their old results remain available, with their original provenance; a repair or renamed split cannot turn them into an independent holdout. Notebook tables and figures must distinguish historical loaded results from new execution.

## Reflection

The uncomfortable finding was that passing a structural validator had been treated as scientific completion. That inflated checklist progress and obscured missing evidence. A pending result with diagnostic artifacts is more useful than a success flag unsupported by the underlying checks.

## Decisions

- Preserve old outputs/reports; annotate superseded claims instead of rewriting history.
- Leave near-duplicate adjudication and independent holdout/protocol open.
- Treat Phase 1 infrastructure repairs separately from full-DAG/equivalence completion.
- Keep Phases 3–7 pending; no candidate expansion or new inference is authorized by these fixes.
- Capture all repair code runs, subprocess outputs, tests, tables and figures in the diagnostic notebook and a unique executed copy.

## Next

Review the final notebook rerun and repaired artifacts; preserve the initial failed attempt documented below.

## Unresolved questions

- Which independent TED holdout/protocol will support a future final-test claim?
- Which pre-registered near-duplicate procedure and adjudication evidence will clear each dataset?

## Verification update — initial notebook run, 2026-09-26

The initial repair notebook completed with **228 passed, 1 failed**. The failure was an offline-environment test fixture; it was fixed and a final notebook rerun subsequently completed (see final verification below). This is not a final all-pass result. Both dataset drivers returned **3 (pending)**, both modality figure emitters returned **0**, both receipt validations returned no errors, and **151 historical files were unchanged**.

Universal EDA visualization is still incomplete. The universal SVG entries are placeholder cards, explicitly `render_status=not_rendered` with a pending reason; the notebook renderer must not present them as measured plots, and an eligible D2 declaration is rejected. Only **six audio and four image modality figures** are actual plots. A figure-manifest entry or existing SVG file is not proof of a rendered scientific figure. Universal plots, near-duplicate adjudication, independent TED holdout and endpoint coverage remain open gates.
## Final scoped repair verification — 2026-09-26

The final executed notebook recorded **233 passed in 113.54 seconds**, with **0 cell/infrastructure errors**. It generated 22 task notebooks; compileall returned 0. Outputs contain **10 PNG displays and 15 HTML displays**; these display counts are not a count of completed universal EDA plots. Both dataset drivers returned **3 (PENDING)**, both modality figure emitters returned **0**, receipt validation returned **[]** for both datasets, and **151 historical files remained unchanged**.

- Executed notebook (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/phase12-evidence-repair-20260926T094151043461Z.ipynb`.
- Fresh artifact root (nested app): `experiments/outputs/phase12_repair_260926/20260926T094154516917Z`.
- Supplemental shared-caller suite `tests/test_tedlium_qualification.py`: **11 passed in 24.62 seconds**, first attempt, no test edits. Combined confirmed total: **244 = 233 + 11**.

The scoped repair is complete. Scientific Phase 1/2 completion is not: full-DAG/equivalence, rendered universal EDA plots, near-duplicate adjudication, independent TED holdout/protocol and endpoint coverage remain pending. Six audio and four image modality plots are real; universal SVG cards remain explicitly not rendered. Phases 3–7 remain pending. The initial 228-pass/1-fail notebook and ACL issue are retained as execution history, not concealed by the successful rerun.
### Supplemental verification closeout

The qualification supplement passed **11 tests in 24.62 seconds** on its first run; combined verified total is **244 tests (233 + 11)**. `git diff --check` returned 0; only LF/CRLF warnings. Scoped review has no outstanding P1/P2 findings. No scientific gate is promoted by this additional contract coverage.

- Source (nested app): `experiments/notebooks/diagnostics/phase12_qualification_supplement.ipynb`.
- Executed copy (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/phase12_qualification_supplement-20260926T094714806867Z.ipynb`.

---

## Nguồn: 260926-dataset-readiness.md

---
title: Dataset readiness preparation after evidence repair
date: 2026-09-26
status: preparation-verified
---

# Dataset readiness preparation after evidence repair

## Context

The earlier repair exposed contaminated TED selection and universal EDA cards that were not real plots. The next authorized step prepares a new local cohort and measurable screening without pretending those historical artifacts are repaired retroactively.

## What happened

Implemented metadata-first TED selection with whole historical speaker/source-group exclusion; official IIIT val/test pairing; immutable selection before decode; independent source-container checks; bounded duplicate screening and auditable real-plot generation. No model inference or official D2 promotion.

## Reflection

The key distinction is between a newly prepared split and an established scientific benchmark. Deterministic screening can give useful, reproducible evidence while still leaving external validity, dataset qualification and full endpoint coverage unresolved.

## Decisions

- Preserve all historical roots and the earlier failed-run record.
- Replace the IIIT train-derived validation protocol only in the fresh preparation bundle.
- Never refill failed or excluded units after content inspection.
- Keep missingness and unavailable comparisons visible; record bounded-method limitations.
- Report sixteen new plots only after execution and inspection; old SVG cards remain historical placeholders.

## Next

Notebook tests/execution, cohort counts, plots and preservation checks are verified in the final results below. Phase 1/2 scientific completion and Phases 3–7 remain open.

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
