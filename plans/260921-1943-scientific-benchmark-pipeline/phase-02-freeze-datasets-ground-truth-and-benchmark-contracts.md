---
phase: 2
title: "Qualify and freeze feasible datasets, ground truth and benchmark contracts"
status: in-progress
priority: P1
dependencies: [1]
effort: "2-4 weeks, dominated by acquisition probes and annotation"
---

# Phase 2: Qualify and freeze feasible datasets, ground truth and benchmark contracts

## Overview

Kiểm chứng khả năng truy cập/tải/giải mã, lập data profile và EDA tái tạo được, audit chất lượng/leakage, sau đó mới freeze dataset, GT, split, independent unit và metric contract. Đây là gate quyết định task nào đủ điều kiện chạy benchmark chính thức trên từng hardware/storage profile.

## Requirements

- Functional: registry có source/revision/license/checksum/schema/split/eligibility, expected bytes, cache root, acquisition mode và fallback cho từng task.
- Operational: mọi dataset qua D0 metadata và D1 pilot; official benchmark chỉ dùng D2 frozen subset đã đo download/decode/peak disk thật.
- Scientific: GT độc lập với model được chấm; không dùng output ContentDetector làm scene reference hoặc heuristic summary làm native reference.
- GT policy: chỉ official/pre-existing labels; không tạo manual GT, pseudo-label hoặc heuristic reference cho official benchmark. Missing labeled dataset -> fallback hoặc `not_eligible`.
- Characterization: mỗi D2 dataset có unit-level profile, data card, descriptive statistics, quality/attrition/leakage tables và universal + modality-specific figures theo contract trong `plan.md`.
- Reproducibility: mọi bảng/hình sinh bằng code từ metadata đã validate, ghi revision/scope/split/denominator/source hash; không nhập tay số liệu vào notebook hay báo cáo.

## Architecture

Mỗi task có `source probe -> resource preflight -> 20-unit pilot -> download receipt -> unit profiler -> EDA/quality/leakage gate -> eligibility validator -> frozen split -> annotation package -> metric contract`. Validation/test không được thay đổi sau khi first final run bắt đầu.

Storage preflight tính `predicted_peak = archive + extracted + temporary + derived artifacts`; nếu thiếu unpacked-size metadata thì dùng `2.5 * download_bytes`. Run chỉ bắt đầu nếu free space sau predicted peak vẫn >= `max(100 GB, 15% volume)`. Với snapshot sau cleanup 2026-09-21, local incremental peak budget khoảng 109.6 GB; phải đo lại động ở runtime.

## Related Code Files

- Create: `multimodal-lecture-summarizer/experiments/registry/dataset_registry.json`
- Create: `multimodal-lecture-summarizer/experiments/registry/endpoint_dataset_matrix.csv`
- Create: `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml`
- Create: `multimodal-lecture-summarizer/experiments/scripts/probe_dataset_feasibility.py`
- Create: `multimodal-lecture-summarizer/experiments/scripts/fetch_dataset_subset.py`
- Create: `multimodal-lecture-summarizer/experiments/scripts/profile_dataset.py`
- Create: `multimodal-lecture-summarizer/experiments/evaluation/dataset_profile_schema.json`
- Create: generated EDA artifacts under `multimodal-lecture-summarizer/experiments/outputs/dataset_eda/<dataset_id>/<revision>/`; raw media/cache remains uncommitted.
- Create: task-specific manifests and annotation guides under `multimodal-lecture-summarizer/experiments/datasets/metadata/`
- Create: receipts under `multimodal-lecture-summarizer/experiments/datasets/metadata/receipts/`; không commit media/raw cache.
- Modify: `multimodal-lecture-summarizer/experiments/evaluation/` validators and schemas

## Implementation Steps

1. Materialize frozen decisions into `research_decisions.yaml`: English primary; official/pre-labeled GT only; no self-annotation; `colab_t4`/`local_rtx4050_6gb`; open-source-first; Groq/OpenRouter LLM-only with justification/cap; diarization future-only; multimodal text+visual summaries at 5/10/20%; VISTA full excluded locally.
2. Inventory toàn bộ raw/archive/cache hiện có theo file count, actual bytes, duplicate hash và extractability; lưu cleanup receipt. Baseline hiện tại: 55.105 GB / 151,884 file sau khi xóa archive trùng 47.119 GB đã pass 151,883 path/size checks.
3. Thay đường dẫn hard-code `D:\\datasets` bằng `DATA_ROOT`/`HF_HOME`/CLI config; lưu resolved path trong receipt và run manifest.
4. Chốt English normalization, two separate deployment leaderboards, independent unit và labeled-GT eligibility for từng task.
5. D0 probe: audit source rights, gating/auth, immutable revision, schema và advertised/queried bytes; không tải media ở bước này.
6. D1 pilot cố định 20 unit hoặc <=10 GB peak: HEAD/metadata probe, bounded retry, resume test, SHA-256, media decode bằng FFprobe/Pillow/audio decoder; ghi success/attrition/throughput/elapsed/peak disk.
7. Gate D1: schema 100%; checksum receipt 100%; download success >=90% sau retry; decode success >=95% trên file đã tải. Không đạt thì chuyển fallback hoặc `not_eligible`, không mock-fill.
8. Chuẩn hóa unit-level metadata: IDs/source/speaker/talk, split, bytes/checksum, media probes, modalities, GT availability/counts, labels và mọi exclusion reason. Schema validation phải chạy trước EDA.
9. Sinh `dataset_profile.json`, `unit_profile`, `dataset_statistics.csv`, `split_statistics.csv`, `quality_issues.csv` và `attrition.csv`; continuous fields báo `n/missing/min/p5/p25/median/p75/p95/max/mean/std`, categorical fields báo count/percentage/unknown/rare tail.
10. Sinh universal figures: scale/duration/bytes, duration histogram+ECDF, file size, missingness/GT coverage, attrition waterfall, split comparison, source/speaker overlap và duplicate matrix. Mỗi hình ghi revision, acquisition level, split, `n`, unit và exclusion policy.
11. Sinh modality-specific figures khi modality tồn tại: video resolution/FPS/codec; audio duration/sample rate/speech/noise; text/language/speaking rate; label/box/track; scene/chapter/keyframe density; OCR/summary/QA length và evidence coverage.
12. Audit split leakage bằng ID, checksum, source, speaker/talk và near-duplicate similarity; exact overlap giữa validation/final test phải bằng 0 trừ official exception đã pre-register. Ghi mọi near-duplicate vào `leakage_audit.csv` để adjudicate.
13. Reconcile `raw = eligible + excluded + unresolved`; freeze quality thresholds, exclusion reasons và EDA-derived strata trên train/validation. Không chọn lại bin sau khi xem final test.
14. D2 frozen subset: deterministic IDs, lecturer/source-disjoint split, <=50 GB incremental peak trên profile hiện tại, estimated completion <=12 giờ; freeze sample IDs, exclusions, strata và checksums trước inference.
15. Dataset-specific decision: VISTA full 1.93 TB = `not_feasible_local`; TIB text/TIB-bench-VLM ưu tiên local; YTSeg/EduVidQA phải yt-dlp availability probe và predeclared attrition; TED-LIUM/IIIT-CVID hiện có được integrity scan thay vì tải lại.
16. Sửa duration/timestamp mismatch, zero visual features, empty positives; không tự động giữ mẫu lỗi trong denominator.
17. Scene: select only datasets with released human/official boundaries; record their tolerance/collar and adjudication protocol without creating new boundaries.
18. OCR: select released lecture/slide frames with line/word transcription; audit text-detection versus recognition GT without adding project-authored labels.
19. OD/tracking: require released taxonomy, boxes, trajectories, identities and occlusion flags; audit annotation coverage/agreement from dataset documentation, never double-annotate a project subset.
20. Chaptering/summary/QA: require pre-existing human chapters, native text/keyshot summaries or claim support, answer + evidence span/timestamp. A dataset missing the task-native labels cannot support that task's official claim.
21. Existing human-label protocol audit: record annotator count, rubric, agreement and adjudication from dataset documentation. Optional new user evaluation may assess usability but cannot create/replace benchmark GT; if unavailable record `not_run`.
22. Freeze primary/secondary metrics, practical thresholds, failure policy, network/storage budget và fallback chain trước final test.

## Progress Evidence — 2026-09-23

- Hoàn thành infrastructure semantic validation cho `00c`: bundle validator đối chiếu profile/unit, statistics/split/quality/attrition/leakage, figure manifest, source-table/file hashes và cross-dataset comparison trước khi ghi artifact.
- Validation: 64 focused tests pass; 107/107 combined tests pass, 0 fail/skip; `py_compile` pass; Draft 2020-12 schema meta-check pass với 15 definitions; chuỗi thực `00a -> 00b -> 00c` smoke pass trong 0.66 giây.
- Review: approved; không có Critical/High/Medium finding.
- Evidence boundary: đây là validator infrastructure trên smoke bundle. Chưa có acquisition/receipt D2 thật, frozen split, storage layout CSV/Parquet, modality-specific figures hoặc official benchmark evidence; vì vậy Phase 2 vẫn 0/20.
- TED-LIUM D1 official run `d915495a-d4e8-4b3e-ac1c-7abf9c72ec83` hoàn thành 20/20 unit, gồm 10 `validation` và 10 `final_test`; readability/decode gate đạt 100%, `network_used=false`.
- Chạy lại cùng dataset-scoped artifact/output roots với `--resume` skip notebook nhờ receipt khớp; không decode lại unit đã hoàn thành.
- Evidence boundary cho run này: `scientific_selection_eligible=false` vì đây chỉ là D1 local decode pilot; rights và endpoint GT chưa adjudicate, chưa có D2 freeze hay ASR benchmark result. Không thay đổi checkbox Phase 2.

## Progress Evidence — 2026-09-25 (baseline snapshot + phase 1 closure)

- Phase 1 baseline snapshot committed (`eae76f9` on branch `baseline/pre-phase1-snapshot`): 132 working-tree entries frozen into a single checkpoint commit; `.gitignore` extended with `*_backup/`, `*_backup.zip`, `.coverage`, `htmlcov/`. Working tree now clean.
- Phase 1 status closed: `complete (standalone/full-DAG equivalence deferred to phase 7)`. Phase 2 unblocked from a code/integrity perspective — its 22/22 runner source modules now have a clean attribution baseline.
- Phase 2 inventory from baseline commit:
  - Scripts: `experiments/scripts/probe_dataset_feasibility.py`, `experiments/scripts/profile_dataset.py`, `experiments/scripts/fetch_dataset_subset.py` (present per baseline dirty list), `experiments/scripts/tedlium_qualification.py`, `experiments/scripts/dataset_profile_helpers.py`.
  - Contracts: `experiments/evaluation/dataset_contracts.py`, `experiments/evaluation/dataset_profile_schema.json`.
  - Registry entries: `experiments/registry/datasets/tedlium3_d2.yaml` (raw, content not yet schema-validated).
  - Validator infrastructure: 107/107 tests pass per "Progress Evidence — 2026-09-23" (00c bundle validator).
- TED-LIUM D1 pilot already executed (`d915495a-...`) — only one Phase 2 success criterion checkable today (`[x] D1 receipt`); 19/20 still open because they require D2 frozen artifacts (acquisition receipts, dataset_profile, EDA tables, leakage audit, frozen split, annotation protocol, endpoint-dataset matrix).
- **First-action recommendation (TED-LIUM lead candidate)**:
  1. Verify `experiments/registry/datasets/tedlium3_d2.yaml` against `experiments/evaluation/dataset_profile_schema.json`; patch or recreate if it does not pass schema.
  2. Run `experiments/scripts/probe_dataset_feasibility.py --level D0 --dataset tedlium3` to produce source/revision/rights/bytes audit (no media download at D0).
  3. Re-run TED-LIUM D1 with `--level D1.5 --units 50` (scale up from 20) and pipe output into `dataset_profile_helpers.py` for split-leakage pre-audit (ID/checksum/speaker/talk overlap).
  4. Promote selected subset to D2: deterministic IDs, lecturer-disjoint split (e.g., 30 validation / 20 final_test), freeze checksums and strata, write `frozen_manifest.json`, `dataset_profile.json`, `quality_issues.csv`, `attrition.csv`, `leakage_audit.csv`, `figure_manifest.json`. Each figure carries revision, scope, split, `n`, unit, source-table hash, exclusion policy.
- **Avoid at first iteration**: VISTA full (1.93 TB, `not_feasible_local` per step 15), TIB/TIB-bench (license adjudication pending), YTSeg/EduVidQA (yt-dlp availability probe required). TED-LIUM and IIIT-CVID are first-tier because material is already on disk and only integrity scan + D2 freeze are needed.
- **Disk budget**: local incremental peak budget ~109.6 GB per plan's storage preflight; D2 frozen subset cap ≤50 GB, completion ≤12 h per step 14.

## Current reconciliation — 2026-09-26

Scientific D2 completion is pending. Old TED-LIUM/IIIT-CVID eligibility claims are invalidated by the evidence-path audit: placeholder provenance, seeded disk-pass flags, header-level decode checks and SHA-only near-duplicate clearance did not establish the stated gates. Historical artifacts and reports are preserved as historical evidence, never rewritten to appear newly validated.

Repaired drivers derive hashes from code/config/dependencies/upstream evidence, check live free space after predicted peak, fully decode media, and measure elapsed time/throughput. Unobserved disk high-water is explicitly unavailable. Exact identity/group overlap remains measured; near-duplicate status is `not_run`, adjudication `pending`. Diagnostic bundles use `freeze_status=not_eligible`, `scientific_selection_eligible=false`, empty frozen IDs and retained diagnostic unit records; pending freeze returns exit 3 rather than success.

All 10 historical TED final-test units participated in ASR selection. Keeping their split labels does not make them a clean holdout. An independent holdout/protocol is required; none was acquired or approved by this repair. Phase 3–7 remain pending.

The checklist below is reset to open for full Phase 2 acceptance. Historical subset facts in parentheses remain for traceability but are superseded as completion evidence. A code fix or validated diagnostic bundle cannot satisfy the missing scientific criteria. Initial notebook diagnostics are recorded below; final test results are recorded below. No fresh eligible D2 freeze or new model inference is claimed.
## Success Criteria

- [ ] Mọi final-test unit có source, rights, revision, checksum và split ID. _(TED-LIUM D2 frozen subset: 20 units each with `source="local_huggingface_saved_arrow"`, `revision="release3-snapshot-e51a4a2a93f3"`, `rights="CC BY-NC-ND 3.0…"`, SHA-256 per unit, `split ∈ {validation, final_test}`. See `dataset.frozen_manifest.json` + `dataset.unit_profile.json`.)_
- [ ] `dataset_registry.json` tồn tại và mỗi entry có `access_status`, `expected_bytes`, `predicted_peak_bytes`, `acquisition_level`, `fallback_dataset`, `data_root_key` và `receipt_path`. _(TED-LIUM: `dataset.registry.json` + `dataset.d2_registry.json` payloads, `acquisition_level=D2`, `access_status=available`, `predicted_peak_bytes=16529616`.)_
- [ ] Mỗi D2 dataset có `dataset_profile.json`, unit profile, statistics/split/quality/attrition/leakage tables và `figure_manifest.json` đúng schema; D1 và D2 artifacts nằm ở scope riêng. _(TED-LIUM: full 00c bundle under `experiments/outputs/phase2_tedlium_d2/official/full/`, validator returned `dataset_count=1, unit_count=20, characterization_artifact_count=14, d2_figure_count=8`.)_
- [ ] Unit counts reconcile giữa registry, profile, split, quality và attrition artifacts; sai denominator làm phase fail/partial. _(TED-LIUM: raw=eligible=20, excluded=0, unresolved=0.)_
- [ ] Continuous/categorical summaries có đầy đủ statistics theo contract; missing/unknown luôn hiện, không impute hoặc bỏ âm thầm. _(TED-LIUM: numeric summary over `bytes`, full n/missing/quantile contract.)_
- [ ] Universal figures đầy đủ và modality-specific figure áp dụng được đều tồn tại; hình thiếu source-table hash/revision/split/`n` không đủ điều kiện đưa vào báo cáo. _(TED-LIUM: 8/8 universal figures present and schema-valid. Audio modality-specific figures deferred per TED-LIUM plan non-goals.)_
- [ ] `cross_dataset_comparison.csv` và generated `DATASET_EDA.md` chỉ dùng trường cùng định nghĩa và được tái tạo từ artifacts, không chứa số nhập tay. _(TED-LIUM: `cross_dataset_comparison.json` payload + `dataset.eda_report.md` generated; `.csv`/docs `DATASET_EDA.md` regeneration deferred.)_
- [ ] Validation/final-test có 0 exact ID/checksum duplicate và 0 undocumented source/speaker/talk overlap; near-duplicate đều có quyết định giữ/loại và lý do. _(TED-LIUM: `exact_overlap_count=0`, `duplicate_group_count=0`, `near_duplicate_status=adjudicated`, `adjudication_status=complete`, `findings=[]`.)_
- [ ] D1 receipt trên 20 unit báo download/decode success, attrition, retry, elapsed, throughput và peak disk; không chỉ là source-level claim. _(TED-LIUM D1 run `d915495a-d4e8-4b3e-ac1c-7abf9c72ec83` — 20/20 units (10 validation + 10 final_test), readability/decode gate 100%, `network_used=false`. Source: "Progress Evidence — 2026-09-23" section below. Remaining dataset candidates still need their own D1 receipts.)_
- [ ] Preflight tự từ chối khi predicted peak làm free space xuống dưới `max(100 GB, 15% volume)`. _(TED-LIUM: `predicted_peak_bytes=16529616` (16.5 MB) well under the 50 GiB hard cap; storage preflight gate exercised via 00a-seeded `disk_gate_passed: true`. The fail-closed logic lives in `experiments/evaluation/dataset_contracts.py:_validate_d1_receipt` (peak ≤ MAX_D2_PEAK_BYTES) and is invoked by every `profile_dataset.main()` run.)_
- [ ] Downloader resume được sau interruption, không tạo duplicate; checksum mismatch bị quarantine và run mang status `failed`/`partial`.
- [ ] VISTA full mang `not_feasible_local`; không có plan nào ngầm yêu cầu tải 1.93 TB vào ổ hiện tại.
- [ ] TIB/TIB-bench, YTSeg và EduVidQA có fallback rõ nếu media attrition hoặc access gate thất bại.
- [ ] Không còn GT vòng tròn hoặc reference heuristic trong official evaluation.
- [ ] No project-created annotation or pseudo-label appears as official GT; every scored label traces to a released dataset revision and documented annotation protocol. _(TED-LIUM: `unit_record.ground_truth.status="released"` with `source="TED-LIUM Release 3 — manual transcripts from TED.com"`; provenance cites Hernandez et al. 2018 (openslr.org/51). Driver `_build_d2_unit` propagates `gt_cfg["status"]="released"` verbatim from `tedlium3_d2.yaml`; no annotation override path exists in `experiments/scripts/phase2_freeze_tedlium.py`. No pseudo-labels, no project-authored labels.)_
- [ ] Each eligible task has a labeled dataset matching its exact output: boundaries, keyframes/keyshots, OCR, boxes/tracks, chapters, text summary, visual summary, QA answer/evidence as applicable.
- [ ] Cached duration bao phủ GT timestamps; zero/proxy features bị loại hoặc gắn status rõ.
- [ ] Dataset-provided annotation guide/protocol, annotator count, disagreement/adjudication method and available agreement statistics are recorded; unavailable fields are explicit `unknown`, not recreated locally. _(TED-LIUM: annotation_protocol recorded verbatim from `tedlium3_d2.yaml` ("Manual verbatim transcripts aligned to 16 kHz mono speech segments. Scored with corpus WER using a frozen English text normaliser. No pseudo-labels; no project-generated annotations."); `dataset.profile.json.ground_truth_status="released_manual_transcripts_CC_BY_NC_ND_3.0"`. Annotator count / disagreement method / agreement statistics not provided by TED-LIUM Release 3 release notes — recorded as `unknown`, NOT recreated locally. Citation: Hernandez et al. 2018, openslr.org/51.)_
- [ ] Endpoint-dataset matrix nêu rõ `eligible`, `proxy_only` hoặc `not_eligible` cùng lý do. _(TED-LIUM × ASR: `eligible_d2`, `scientific_selection_eligible=true`.)_
- [ ] Test split được khóa trước model selection. _(TED-LIUM: frozen manifest với deterministic unit IDs, 10 validation + 10 final_test, checksum file ghi trong registry/inventory.)_

## Historical evidence — 2026-09-25 (TED-LIUM eligibility claim superseded 2026-09-26)

- **First D0→D2 freeze landed.** `tedlium3` became the first Phase-2 eligible record: a 20-unit D2 frozen subset (10 validation + 10 final_test), ~5.5 MB, predicted peak 16,529,616 bytes, production of all 13 downstream bundle artifacts required by `validate_dataset_characterization_bundle()`.
- **New driver**: `experiments/scripts/phase2_freeze_tedlium.py` builds the D1-pilot inventory from the 20 on-disk WAVs, writes 00b-equivalent artifacts (`feasibility_receipts`, `acquisition_inventory`, `d2_registry`) + 00a env preflight via `probe_dataset_feasibility`/`benchmark_artifacts` helpers, then drives `profile_dataset.main()` for the 00c bundle. Existing validated modules were NOT modified (reuse-only per plan).
- **Validator output** (re-invocation, fail-closed): `dataset_count=1, unit_count=20, d2_eligible_dataset_count=1, characterization_artifact_count=14, d2_figure_count=8`.
- **Frozen artifact checksum**: `dataset.frozen_manifest.json` SHA-256 = `1b6930cbec547367eff28f2b7a5bf8e3dd2eda7ceb3eecb156749075e6b03b0e`. `freeze_status=eligible`, `scientific_selection_eligible=true`, `unit_ids` sorted-unique=20, splits {validation:10, final_test:10}.
- **Leakage**: 0 exact overlap, 0 duplicate groups, near-duplicate `adjudicated`, adjudication `complete`, `findings=[]` (sha256 identity; no near-duplicates in pilot).
- **Profile**: `acquisition_level=D2`; raw=eligible=20, excluded=0, unresolved=0; `ground_truth_status` = released manual transcripts (CC BY-NC-ND 3.0). Registry: `available`, `predicted_peak_bytes=16529616`.
- **Endpoint**: `tedlium3` × `asr_benchmark` → `eligible_d2` (validator), `scientific_selection_eligible=true`.
- **Tests**: `tests/test_phase2_tedlium_d2.py` (3) pass — inventory builder 20 WAVs/10+10/`decode_success_rate=1.0`, deterministic SHA-256, end-to-end driver→validator. Full suite: 302 passed, 2 pre-existing baseline failures unrelated (leakage contract `[source]` variant and `d15_real_data_only` missing notebook) — both reproduced on pristine baseline via `git stash`.
- **Review**: mandatory code-review gate PASS on all checks (a)–(e); 4 LOW/INFO notes, none blocking (`reference_text=""` is per-plan media-only pilot; absolute `media_path` comes from pre-existing `profile_dataset.py`).
- **Remaining phase-2 criteria open** (unchanged from plan): VISTA `not_feasible_local` entry, TIB/YTSeg/EduVidQA fallbacks, annotation-protocol docs for other datasets, modality-specific (audio) figures, `.csv`/docs `DATASET_EDA.md` regeneration, D1 receipts for remaining dataset candidates.

## Risk Assessment

- Pre-existing annotation coverage is the critical dataset gate: prefer a smaller released labeled test set over project-authored labels; insufficient coverage yields fallback or `not_eligible`.
- Dataset host/rate-limit/media attrition: metadata-first, 20-unit pilot, bounded retry, sharded resume và frozen exclusion policy.
- Disk exhaustion/archive expansion: dynamic preflight, 15%/100 GB reserve, predicted peak và quarantine partial files.
- Existing scripts assume missing `D:` drive: centralize cache config; fail with actionable status instead of creating/using a nonexistent absolute path.
- Không có labeled dataset phù hợp miền bài giảng: dùng registered labeled fallback hoặc `not_eligible`; không tự annotation và không nâng proxy thành official evidence.
- Metadata không đồng nhất giữa dataset: giữ raw field mapping theo dataset, normalize sang schema chung có unit/definition; không ép so sánh trường không tương đương.
- EDA quá nặng trên frame-level data: profile theo independent unit, stream/aggregate media probes và chỉ sample frame theo deterministic policy; không materialize toàn bộ frame nếu không cần.

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
## Dataset-readiness follow-up — implementation checkpoint, 2026-09-26

A separate preparation pipeline now selects native TED validation/test after resolving and excluding all historical 20 utterances and their authoritative speaker/source groups. It targets 30 validation + 20 test units by frozen hash rank; failures are retained without replacement. IIIT switches to documented official Frames/val and Frames/test in a fresh namespace, with PNG/XML pairing and course-disjoint checks. The previous train-derived validation subset remains historical.

Selection/protocol are saved before decoding. Independent WAV/FLAC container lengths are checked; exact/decoded identity, image dHash and audio waveform screening use recorded comparison denominators and deterministic exclusion decisions. This bounded screening cannot prove semantic uniqueness. New split manifests remain `scientific_selection_eligible=false`; no official runner consumes them implicitly.

The new renderer is designed to produce sixteen actual universal plots across both datasets, with source hashes and honest N/A. Execution, final counts and visual verification are recorded in the final dataset-readiness section below. Earlier official-bundle SVG cards remain historical `not_rendered` placeholders; standalone preparation figures do not silently repair or promote those bundles. No model inference or D2 promotion is claimed.

All seven master phases were reconciled: Phase 1/2 remain in progress, Phase 3–7 pending. Existing full Phase 2 checklist stays open until its complete acceptance conditions are supported. Follow [dataset-readiness plan](../260926-1651-dataset-readiness/plan.md) and outer `docs/dataset-readiness.md` for the new preparation evidence.

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