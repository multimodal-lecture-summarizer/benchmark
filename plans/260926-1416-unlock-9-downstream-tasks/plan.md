---
title: "Unlock 9 downstream tasks via D2 dataset freeze"
description: "Freeze IIIT-CVID + EduViQA D2 subsets, sinh audio modality figures, mở rộng endpoint matrix và chạy first real benchmark cho mỗi downstream task có dataset eligible. Scope HOLD: không động vào Phase 3-7 (candidate expansion, statistical, compatibility, E2E)."
status: pending
priority: P1
branch: "baseline/pre-phase1-snapshot"
tags:
  - d2-freeze
  - iiit-cvid
  - audio-figures
  - endpoint-matrix
  - ocr-benchmark
  - downstream-benchmark
blockedBy: []
blocks: []
note: "Plan này supersede 3 phase pending của plan `multimodal-lecture-summarizer/plans/260925-1537-dataset-coverage-expansion` (IIIT-CVID / audio figures / EduViQA). Plan cũ ở sub-directory nên không thể track bằng same-scope blocks; recommend cancel plan cũ sau khi plan này approved."
revision_note: >-
  REVISED 2026-09-26 sau verification pass trên disk thật (trước khi implement).
  Phase 3 (EduViQA) CANCELLED — thiếu provenance.json → kích hoạt drop criterion #1.
  IIIT-CVID = 1755 frames (không phải 200). Endpoint count = 2 (không phải 4).
  Endpoint names chuẩn hoá theo _NOTEBOOK_TO_ENDPOINTS. Chi tiết: xem từng phase file.
created: "2026-09-26T07:16:40.585Z"
createdBy: "ck:plan"
source: skill
---

# Unlock 9 downstream tasks via D2 dataset freeze

> Historical plan: the D2 freeze drivers, generic dataset profile/contract modules and modality-figure emitters cited below were removed on 2026-10-07. The completed checkboxes record work at that time and are not current rerun instructions.

## Overview

Kế hoạch HOLD-scope để **mở khóa downstream tasks** bằng cách:

1. Freeze **IIIT-CVID** (1755 official test frames với per-line OCR ground truth) — mở `ocr_benchmark`.
2. Sinh **audio modality-specific figures** cho TED-LIUM (đóng deferred criterion #7 của Phase 2 master plan).
3. Aggregate **endpoint matrix** từ 2 D2 datasets.
4. Chạy **first real OCR benchmark** trên 1755 frames, để chứng minh pipeline không bị stuck ở "runner exists nhưng không có data".

**Revised scope (2026-09-26, sau verification pass + user decision):**

| Thay đổi | Gốc | Mới | Lý do |
|---------|-----|-----|--------|
| Số D2 datasets | 3 | **2** | EduViQA **cancelled** — không có `provenance.json` (không có source URL / license / download date). Vi phạm `research_decisions.yaml` `ground_truth.policy: official_or_preexisting_labels_only`. Kích hoạt drop criterion #1 của chính Phase 3. |
| IIIT-CVID units | 200 | **1755** | 200 là `max_samples` cap của prior OCR eval, **không phải** dataset size. Thật: `Frames/test/` = 1755 PNG + 1755 XML (1:1), index bởi `frames-test-img.txt`. |
| IIIT-CVID GT | lexicon/vocab | **Pascal-VOC XML** | `<object><name>` = transcription mỗi text line. `lexicon.txt`/`vocab.txt` chỉ là constrained-decoding vocabulary. |
| Granularity | (không rõ) | **frame-level** | User-confirmed. Line-level (40,103 crops) defer sang D3. |
| `eligible_d2` endpoints | 4 | **2** | `asr_benchmark` + `ocr_benchmark` (EduViQA mất `qa`/`retrieval`). |
| Phase 5 benchmarks | 3 (OCR+retrieval+QA) | **1** (OCR) | Phụ thuộc EduViQA. |
| Endpoint names | `qa_benchmark`, `summary_benchmark`, `multimodal_summary_benchmark` | **`qa_generation_benchmark`**, **`summarization_benchmark`**, (không có) | 3 tên trên **không tồn tại** trong registry. Canonical lấy từ `_NOTEBOOK_TO_ENDPOINTS` (`experiments/scripts/stage_benchmark_helpers.py`). |
| `load_eligible_units` | cần sửa để dispatch | **không cần sửa** | Nó đã đúng: đọc `dataset.endpoint_matrix` từ `context.namespace_root` (per-artifact-root). Aggregator Phase 4 là **report artifact**, không phải dispatch. |
| `profile_dataset.py` | không sửa | **sửa (config-driven)** | Line ~642 **hardcode** `endpoint: "asr_benchmark"` cho mọi D2 dataset → sẽ emit `iiit_cvid × asr_benchmark` sai. Sửa thành config-driven với default = giá trị hiện tại để TED-LIUM SHA không đổi. |

**Không thuộc scope**: Phase 3 candidate expansion (Whisper/CTC/NeMo cho ASR; YOLO/RT-DETR cho OD), Phase 4-7 của master plan (statistical analysis, compatibility matrix, E2E system validation). Các scope đó sẽ thành plan follow-up sau khi plan này close.

## Bối cảnh evidence (2026-09-26)

- **TED-LIUM D2 đã freeze thành công** (plan `260925-2304-d2-frozen-gt-runners`, completed 2026-09-25): 20 unit WAV (10 validation + 10 final_test), ASR GT manual transcripts, ASR benchmark thật đã chạy (`faster-whisper-tiny.en` WER 16.28%, CER 4.38%, frozen config `beam=5`). **25 payload SHA-256 baseline đã ghi lại trước khi sửa code** (regression guard).
- **Endpoint matrix hiện tại**: chỉ có `tedlium3 × asr_benchmark → eligible_d2`.
- **22 runner modules** đã có (theo plan `260921-1943` Phase 1 complete) — không cần tạo runner mới. Đã verify `run_ocr_benchmark.py` tồn tại.
- **Group 02/07 fail-closed** đã pass test (35/35 PASS 2026-09-26).
- **IIIT-CVID trên disk** (`experiments/datasets/iiit_cvid/IIIT-CVid/`): `Frames/{train,val,test}`, `Crops/{train,val,test}`, `frames-test-img.txt` (1755 rows), `frames-test-slides-img.txt` (368 rows, course 20), `lexicon.txt`, `vocab.txt`, `test.txt` (40,103 rows). `provenance.json` có `zip_sha256`, license **bị mojibake** → phải viết lại.
- **EduViQA trên disk**: `Videos/` (11 mp4 + 9 mkv + 1 webm), `video_transcripts/<id>/` (**directory**: `chunks.pkl`, `metadata.json`, `metadata_chunks.json`, `transcript.txt`), `video_chunkings/<id>/` (**directory** keyframe JPGs), `q_and_a.json`, `hybrid_clip_ssim_chunking_meta_data.json`. **Không có `provenance.json`.**
- **Datasets khác trên disk không có trong plan gốc**: `slidevqa` (14,484 released QA pairs + `provenance.json`, nhưng **không có slide images** → cần download SlideShare), `tvsum_extracted` (`tvsum_videos/video` **rỗng**).

## Phases

| Phase | Name | Status | Depends | Closes |
|-------|------|--------|---------|--------|
| 1 | [IIIT-CVID D2 Freeze](./phase-01-phase-01-iiit-cvid-d2-freeze.md) | **Completed** | — | `ocr_benchmark` eligible_d2 (2115 units: final_test=1755 + validation=360); criterion #5 master plan Phase 2 |
| 2 | [Audio Modality Figures for TED-LIUM](./phase-02-phase-02-audio-modality-figures.md) | **Completed** | — | Deferred criterion #7 master plan Phase 2; 6 audio figures, manifest 8→14 |
| 3 | [EduViQA D2 Freeze](./phase-03-phase-03-eduviqa-d2-freeze.md) | **Cancelled** | — | ❌ cancelled: missing provenance |
| 4 | [Endpoint Matrix Expansion](./phase-04-phase-04-endpoint-matrix-expansion.md) | Pending | 1 | 2 endpoints eligible_d2; group 02/07 sẵn sàng chạy thật |
| 5 | [First Real Benchmark (OCR)](./phase-05-phase-05-first-real-benchmark-downstream.md) | Pending | 4 | OCR raw prediction artifact từ real run trên 1755 final_test frames |

## Deliverables

| Item | Path | Purpose |
|------|------|---------|
| IIIT-CVID D2 driver | `experiments/scripts/phase2_freeze_iiit_cvid.py` | Cloned từ `phase2_freeze_tedlium.py`, swap decoder WAV → PNG + XML GT parser |
| IIIT-CVID registry | `experiments/registry/datasets/iiit_cvid_d2.yaml` | D2 config: `ocr_benchmark` endpoint, 2115 units, rights adjudicated |
| Config-driven endpoint | `experiments/scripts/profile_dataset.py` | **MODIFIED**: `endpoint`/`reason`/`gt_status` đọc từ D2 config thay vì hardcode `asr_benchmark`; default giữ nguyên giá trị cũ |
| Raster geometry | `experiments/scripts/dataset_profile_helpers.py` | **NEW** `image_geometry_summary()` + `image_geometry` block trong `dataset.statistics` (gated theo raster metadata → TED-LIUM không đổi byte) |
| TED-LIUM SHA fixture | `tests/fixtures/tedlium_d2_payload_sha256.json` | 25 payload SHA-256 baseline, chống regression khi thêm dataset thứ hai |
| Image figures | `experiments/scripts/emit_iiit_cvid_image_figures.py` | Sinh 4 image-specific figures (resolution, aspect ratio, mode, text-line density) + sidecar `.json` |
| Audio figures | `experiments/scripts/emit_audio_modality_figures.py` | Sinh 6 audio-specific figures từ TED-LIUM WAV |
| Endpoint matrix v2 | `experiments/outputs/endpoint_matrix_v2/official/full/payloads/endpoint_matrix_aggregate.json` | Aggregate 2 per-dataset matrices, 2 endpoints eligible_d2 |
| OCR benchmark receipts | `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/ocr.*.json` | Real run artifact: 5 files, 1755 units |
| Tests (P1) | `tests/test_unlock_iiit_cvid_d2.py` | ≥ 5 tests incl. TED-LIUM SHA regression guard |
| Tests (P2) | `tests/test_audio_modality_figures.py` | ≥ 3 tests |
| Tests (P4) | `tests/test_endpoint_matrix_expansion.py` | ≥ 5 tests |
| Tests (P5) | `tests/test_first_real_benchmark_downstream.py` | ≥ 4 tests incl. ASR SHA regression guard |
| Updated research decisions | `experiments/registry/research_decisions.yaml` | Mark `next_target` iiit_cvid complete + `endpoint_matrix_summary` |
| ~~EduViQA D2 driver~~ | ~~`experiments/scripts/phase2_freeze_eduviqa.py`~~ | ❌ **CANCELLED** — missing provenance |
| ~~EduViQA registry~~ | ~~`experiments/registry/datasets/eduviqa_d2.yaml`~~ | ❌ **CANCELLED** — missing provenance |

## Acceptance Gate

- [x] **Phase 1**: `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.frozen_manifest.json` chứa 1 record `freeze_status=eligible`, `scientific_selection_eligible=true`, `unit_ids.length == 2115` (`final_test`=1755 + `validation`=360), `acquisition_level=D2`, mọi `unit_records[].reference_text` non-empty.
- [x] **Phase 1**: `dataset.endpoint_matrix.json` có entry `iiit_cvid × ocr_benchmark → eligible_d2` (canonical name, **không phải** `ocr`).
- [x] **Phase 1**: 8 universal + 4 image-specific figures render trong `experiments/outputs/phase2_iiit_cvid_d2/official/full/figures/`; `dataset.figure_manifest.json` có 12 entries.
- [x] **Phase 1**: contract pass end-to-end (`validate_dataset_characterization_bundle` → `d2_figure_count=12`, `unit_count=2115`, `d2_eligible_dataset_count=1`).
- [x] **Phase 2**: 6 audio modality-specific figures emitted dưới `experiments/outputs/phase2_tedlium_d2/official/full/figures/audio/`, mỗi cái có companion `.json` với `source_table_sha256` + `code_revision`.
- [x] **Phase 2**: `dataset.figure_manifest.json` có 14 entries (8 universal + 6 audio), 8 cũ **không bị mất**.
- [x] **Phase 2**: contract revalidate PASS sau append (`d2_figure_count=14`, `unit_count=20`, `d2_eligible_dataset_count=1`).
- [x] **Regression (quan trọng)**: **25/25** TED-LIUM payload SHA-256 giống baseline đã ghi (đặc biệt `dataset.frozen_manifest.json` và 7 `asr.*.json`). Sửa `profile_dataset.py` + `dataset_profile_helpers.py` + `dataset_profile_schema.json` **không** làm đổi byte nào của TED-LIUM. Baseline lưu tại `tests/fixtures/tedlium_d2_payload_sha256.json`, có test tự động chống hồi quy.
- [x] **Regression (Phase 2)**: `dataset.figure_manifest.json` là append target có chủ đích nên được phép đổi; **24/25** payload còn lại (mọi thứ trừ manifest) vẫn byte-identical sau khi thêm 6 audio figures. Fixture ghi rõ `appendable_payloads` + `immutable_payload_count`, và test chống hồi quy chỉ kiểm 24 payload bất biến.
- [x] **Phase 3**: ❌ **CANCELLED** — không có acceptance gate. `eligible_d2` dataset count giữ ở 2.
- [ ] **Phase 4**: `endpoint_matrix_aggregate.json` có **2** entries `scientific_selection_eligible=true` (`asr_benchmark`, `ocr_benchmark`) + 12 `not_eligible` với `reason` rõ ràng.
- [ ] **Phase 4**: `load_eligible_units` trả 20 TED-LIUM units cho `asr_benchmark`, **1755** IIIT-CVID `final_test` units cho `ocr_benchmark`, và `RuntimeError` fail-closed cho `scene_boundary_benchmark` trên cả 2 roots.
- [ ] **Phase 5**: ≥ 1 downstream endpoint có raw prediction artifact từ **real** run: `ocr.raw_predictions.json` + `ocr.per_unit_metrics.json` + `ocr.aggregate.json` + `ocr.shortlist.json` + `ocr.frozen_configuration.json`, tất cả **1755** `final_test` units.
- [ ] **Phase 5**: `ocr.aggregate.json` có `corpus_cer` + `corpus_wer` finite, `unit_count=1755`.
- [x] **Regression (quan trọng)**: **25/25** TED-LIUM payload SHA-256 giống baseline đã ghi (đặc biệt `dataset.frozen_manifest.json` và 7 `asr.*.json`). Sửa `profile_dataset.py` + `dataset_profile_helpers.py` + `dataset_profile_schema.json` **không** làm đổi byte nào của TED-LIUM. Baseline lưu tại `tests/fixtures/tedlium_d2_payload_sha256.json`, có test tự động chống hồi quy.
- [ ] **Tests mới**: 4 test files PASS (≥ 5 + 3 + 5 + 4 = 17 tests). Phase 1 đã xong: `tests/test_unlock_iiit_cvid_d2.py` PASS 12/12.
- [x] **Tests cũ**: 337/338 PASS. 1 failure **pre-existing, không liên quan** (`tests/test_validation_gate.py::test_d15_real_data_only_no_mocks_across_all_notebooks` kỳ vọng tên notebook kiểu cũ `00_dataset_eda_and_quality_audit.ipynb`, nhưng repo dùng scheme `00a_environment_preflight` / `02c_ocr_benchmark` khớp `_NOTEBOOK_TO_ENDPOINTS`).
- [ ] **Documentation**: `research_decisions.yaml` đánh dấu `next_target: iiit_cvid` complete + có `endpoint_matrix_summary` với 2 eligible / 12 not_eligible (canonical names).

## Dependencies

- **Cross-plan:**
  - `blocks: [260925-1537-dataset-coverage-expansion]` — 3 phase đầu của plan này supersede 3 phase pending của plan cũ.
  - Được dùng bởi: master plan `260921-1943-scientific-benchmark-pipeline` (Phase 2 success criteria #5, #7, deferred).
- **Code dependencies:**
  - Phase 1 reuse `phase2_freeze_tedlium.py` pattern + `validate_dataset_characterization_bundle`.
  - Phase 1 **modify** `profile_dataset.py` (config-driven endpoint/reason/gt_status) — regression-sensitive.
  - Phase 2 driver độc lập, chỉ append vào `dataset.figure_manifest.json`.
  - Phase 4 read-only với per-dataset matrices; chỉ tạo aggregate report.
  - Phase 5 dispatch qua `execute_all_notebooks.py` + `load_eligible_units` trong `stage_benchmark_helpers.py`.
- **Data dependencies:**
  - `experiments/datasets/iiit_cvid/IIIT-CVid/Frames/test/` — **1755 PNG + 1755 XML** (verified 2026-09-26), index `frames-test-img.txt`.
  - `experiments/datasets/tedlium3/{test,validation}/` — 20 WAV đã freeze (existing).
  - ~~`experiments/datasets/eduviqa/`~~ — **CANCELLED** (no provenance).

## Out of Scope (Explicit)

Những thứ **không** thuộc plan này:

1. **Candidate family expansion** (Phase 3 master plan): chỉ 1 candidate/endpoint. Cho ASR có `faster-whisper-tiny.en` + `faster-whisper-base.en`; chưa có CTC, NeMo Parakeet, Zipformer. Cho OD chưa có YOLO/RT-DETR/GroundingDINO.
2. **Statistical analysis & selection gates** (Phase 5 master plan): hierarchical bootstrap, Holm correction, Pareto frontier, `research_best`/`deployable_best`.
3. **Compatibility matrix & error propagation** (Phase 6 master plan).
4. **End-to-end system validation** (Phase 7 master plan).
5. **Human evaluation** (Phase 5 master plan criterion #11).
6. **Production deployment / website changes**: vẫn HOLD.
7. **Line-level OCR scoring** (40,103 crops) — D3 candidate, quá lớn cho phase này.
8. **EduViQA / SlideVQA / TVSum** — EduViQA cancelled (provenance); SlideVQA cần download slide images; TVSum videos rỗng trên disk.

## Open Questions — RESOLVED 2026-09-26

1. **EduViQA provenance** → ✅ **RESOLVED: CANCEL Phase 3.** Không có `provenance.json`; user-confirmed cancel. `eligible_d2` giữ ở 2.
2. **Caption endpoint trên IIIT-CVID** → ✅ **RESOLVED: `not_eligible`.** Không có multi-reference caption GT. Chờ dataset có CIDEr/SPICE reference (TIB-bench-VLM hoặc tương tự).
3. **Chaptering endpoint trên EduViQA** → ✅ **N/A** (Phase 3 cancelled). Ghi nhận: SSIM chunking là heuristic, không phải released GT → `not_eligible` nếu mở lại.
4. **Summary endpoint trên EduViQA** → ✅ **N/A** (Phase 3 cancelled). Ghi nhận: không có native reference summary.
5. **Compute profile cho downstream benchmark** → ⏳ **OPEN, deferred tới Phase 5 runtime.** Sẽ chạy `--profile full` trên local (1 classical OCR candidate, ước tính 15-40 phút cho 1755 frames). Timeout 90 phút → escalate user chuyển `--profile smoke`. **Không cần Colab T4** vì không có heavy model.

## New Open Questions (phát sinh từ verification pass)

6. **`profile_dataset.py` hardcode endpoint** — sửa thành config-driven. Cần xác nhận không có consumer nào khác phụ thuộc vào việc **mọi** D2 dataset đều là `asr_benchmark`. Đã verify: `validate_dataset_characterization_bundle` không enforce endpoint value; `_NOTEBOOK_TO_ENDPOINTS` map theo notebook chứ không theo dataset. → An toàn.
7. **Frame-level vs line-level OCR scoring** — frame-level (1755) đã chọn. Line-level (40,103 crops trong `Crops/test` + `test.txt`) sẽ cho CER thấp hơn nhiều và comparable trực tiếp với prior baseline. Để D3.
8. **OCR candidate availability** — `easyocr` đã fail với `WinError 127` (shm.dll) trong prior eval. Cần verify `paddleocr` / `tesseract` còn dùng được ở Phase 5.

## Status Tracking

Plan status sẽ update bằng `ck plan check <phase> --start` / `ck plan check <phase>` theo workflow chuẩn. Cuối mỗi phase, journal entry sẽ được viết để track evidence và lessons learned.

### Lưu ý về `ck plan status` và Phase 3 cancelled

`ck plan status` **không có bucket "cancelled"**: nó chỉ phân biệt completed / in-progress / pending,
nên phase có `status: cancelled` trong frontmatter vẫn bị đếm vào *Pending*. Phase 3 đã có
`status: cancelled` + `cancelled_reason` đúng chuẩn (user-confirmed 2026-09-26), và `ck plan check`
cũng không có cờ cancel — vậy nên **40% (2/5) là trần trước khi làm Phase 4/5**, không phải
tracker bị stale. Sau khi Phase 4 + 5 complete, kỳ vọng `4/5 (80%)`, 1 phase cancelled,
3 pending → 0. Đừng "fix" lại frontmatter Phase 3 dựa trên con số phần trăm.
