---
phase: 2
title: "IIIT-CVID D2 Freeze"
status: pending
priority: P1
effort: "1-2 days"
dependencies: ["phase-01-vista-encoding"]   # soft: registry key ordering, but not blocking
---

# Phase 2: IIIT-CVID D2 Freeze

## Overview

Đưa IIIT-CVID (lecture video OCR corpus từ CVIT IIIT Hyderabad) từ trạng thái "D1 raw on disk" lên **D2 frozen subset** — với 200 ảnh OCR baseline sẵn có, license adjudicated, full 00a/00b/00c artifact chain. Đây là dataset eligible thứ hai cho **OCR track** (endpoint `ocr`), mở rộng coverage từ `eligible_datasets=1` (chỉ TED-LIUM audio) lên `eligible_datasets=2` (audio + OCR). Pattern tái sử dụng trực tiếp từ `phase2_freeze_tedlium.py` — chỉ thay phần decode (soundfile → image decoder) và inventory builder.

## Background & Evidence

- **Material đã có sẵn (verified 2026-09-25):**
  - `experiments/datasets/iiit_cvid/IIIT-CVid.zip` — 2,427,254,987 bytes (~2.43 GB), sha256 `b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489`.
  - `experiments/datasets/iiit_cvid/IIIT-CVid/` — extracted structure: `Frames/{train,val,test}/`, `Crops/`, `lexicon.txt`, `vocab.txt`, `Readme.txt`.
  - `experiments/datasets/iiit_cvid/provenance.json` — ghi rõ `license: "academic_research_only — verify with CVIT IIIT Hyderabad before redistribution"`.
  - `experiments/datasets/iiit_cvid/.extracted/` + `.cache/` — pipeline outputs sẵn.
  - `outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_baseline_comparison.csv` + summary JSON — đã có 200 ảnh baseline (PaddleOCR numbers) — không cần chạy OCR baseline mới.
- **Existing OCR baseline numbers** (từ `outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json`): dùng làm `acquisition_level` evidence cho D2 receipt.
- **Phase 2 already named in research_decisions.yaml:**
  ```yaml
  phase2_dataset_execution:
    next_target:
      dataset_id: iiit_cvid
      endpoint: ocr
  ```
  Tức là IIIT-CVID đã được pre-register làm next target.
- **Pattern to clone:** `experiments/scripts/phase2_freeze_tedlium.py` đã chạy thành công với 20 WAVs → frozen_manifest 1 eligible record.

## Implementation Steps

1. **Tạo `experiments/registry/datasets/iiit_cvid_d2.yaml`** theo schema `_load_d2_config`:
   ```yaml
   schema_version: 1
   dataset_id: iiit_cvid
   source: "local_extracted_zip"
   release: "iit_cvid_release_2018"
   revision: "extracted-e51a4a2a93f3"   # snapshot fingerprint
   local_snapshot_fingerprint: "<sha256 của IIIT-CVid.zip>"

   # Rights adjudication
   rights: "academic_research_only — verify with CVIT IIIT Hyderabad before redistribution; no public re-hosting of raw images."
   access_status: "available"
   leakage_exception: null   # image-level, no speaker_id leakage

   data_root_key: "experiments/datasets/iiit_cvid"
   receipt_path: "datasets/iiit_cvid/official/full/payloads/dataset.feasibility_receipts.json"

   # Size estimates (tính từ 200 baseline images + zip full)
   expected_bytes: <sum 200 selected image files>
   predicted_peak_bytes: <expected_bytes * 3>   # headroom cho PIL/CV2 decode
   estimated_completion_hours: 0.1              # tiny subset, instant

   # D2 gates (mirror _validate_d1_receipt)
   min_schema_success_rate: 1.0
   min_checksum_success_rate: 1.0
   min_download_success_rate: 0.90              # N/A cho local scan → set 1.0 effective
   min_decode_success_rate: 0.95

   # Ground truth (OCR task)
   ground_truth:
     status: "released"
     source: "IIIT-CVid official — manual transcriptions for slide frames"
     revision: "iit_cvid_release_2018"
     annotation_protocol: >
       Manual transcriptions aligned to slide frames; lexicon.txt + vocab.txt
       provide vocabulary for constrained decoding. Scored with corpus-level
       CER/WER using a frozen English text normaliser.

   fallback_dataset: null
   ```
   - Decision freeze date: 2026-09-25 (match Phase 1).
   - **License adjudication step:** Ghi rõ trong comment đầu file rằng license `academic_research_only` đã được verify với CVIT IIIT Hyderabad (kèm link tới email/issue); không redistribute ảnh raw.

2. **Clone driver script:**
   - `cp experiments/scripts/phase2_freeze_tedlium.py experiments/scripts/phase2_freeze_iiit_cvid.py`
   - Replace `_build_inventory_from_disk` body: thay `soundfile.info(...)` bằng `PIL.Image.open(...)` để lấy `width`, `height`, `mode`. Loop qua `experiments/datasets/iiit_cvid/IIIT-CVid/Frames/test/{<video_id>/<frame_id>.png}` chọn 200 ảnh deterministic SHA-256 rank.
   - Đổi `unit_id` scheme: `f"test:{video_id}:{frame_id}"`.
   - Đổi `extension_counts` → `.png` / `.jpg` theo thực tế.
   - Đổi `split_counts` → chỉ `test` (vì OCR baseline 200 ảnh đều từ test split; đây là official test set theo `frames-test-*-img.txt`).
   - Ghi `acquisition_level: D1_local_pilot` → upgrade lên `D2` sau khi 00c pass.

3. **Run 00c profile_dataset** để emit 13 payloads + 8 figures + frozen_manifest:
   ```bash
   cd multimodal-lecture-summarizer
   python -m experiments.scripts.phase2_freeze_iiit_cvid \
     --artifact-root experiments/outputs/phase2_iiit_cvid_d2
   ```
   - Verify output: `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.frozen_manifest.json` chứa ≥ 1 record với `freeze_status=eligible`, `scientific_selection_eligible=true`, `unit_ids.length == 200`.

4. **Re-use 200 OCR baseline numbers** từ `outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json` làm `acquisition_inventory.numeric_summary` cho dataset.statistics.json — đây là điểm leverage lớn nhất vì không cần chạy OCR model mới.

5. **Update `research_decisions.yaml`** để đánh dấu `next_target.dataset_id=iiit_cvid` đã hoàn thành, đồng thời unblock `downstream_execution.prerequisite` (chuyển từ `d2_validated: false` thành `d2_validated: true` cho IIIT-CVID endpoint).

6. **Smoke regression:** Chạy lại `phase2_freeze_tedlium.py` để bảo đảm không phá artifacts TED-LIUM hiện hữu (sha256 frozen_manifest không đổi hoặc chỉ đổi theo expected delta).

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/registry/datasets/iiit_cvid_d2.yaml`
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_iiit_cvid.py`
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_tedlium.py` (pattern to clone)
  - `multimodal-lecture-summarizer/experiments/scripts/probe_dataset_feasibility.py:38` (`_load_d2_config`)
  - `multimodal-lecture-summarizer/experiments/scripts/profile_dataset.py` (`main()` entry point)
  - `multimodal-lecture-summarizer/experiments/datasets/iiit_cvid/provenance.json`
  - `multimodal-lecture-summarizer/outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json`
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml` (mark next_target complete)

## Success Criteria

- [ ] `experiments/registry/datasets/iiit_cvid_d2.yaml` parse thành công qua `_load_d2_config("iiit_cvid")`.
- [ ] `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.frozen_manifest.json` chứa 1 record `freeze_status=eligible`, `unit_ids.length == 200`, `scientific_selection_eligible=true`.
- [ ] 8 figures trong `experiments/outputs/phase2_iiit_cvid_d2/official/full/figures/` được render (không phải stub).
- [ ] `acquisition_level: D2` xuất hiện trong cả registry record và frozen_manifest record.
- [ ] `dataset.leakage_audit.json` không có overlap với TED-LIUM (cross-dataset leakage = 0).
- [ ] Regression: TED-LIUM frozen_manifest SHA-256 không đổi sau khi chạy Phase 2.
- [ ] `research_decisions.yaml.phase2_dataset_execution.next_target.dataset_id` được đánh dấu "completed" (hoặc comment đầu file ghi rõ completion date).

## Risk Assessment

- **Risk:** 200 ảnh OCR baseline không đồng nhất với full `Frames/test/` (PaddleOCR numbers chỉ cho 200 ảnh, không phải toàn bộ test split).  
  **Mitigation:** Ghi rõ trong `iiit_cvid_d2.yaml` rằng D2 freeze là **200-image subset**, không phải full IIIT-CVid test split; full split là D3 future work.
- **Risk:** License `academic_research_only` — nếu paper yêu cầu sample ảnh minh họa, cần check redistribution policy trước khi đăng.  
  **Mitigation:** Adjudication note trong YAML + paper appendix ghi rõ "no raw image redistribution, only aggregate metrics published".
- **Risk:** `_build_inventory_from_disk` clone có thể miss một số field quan trọng (vd: `decoded`, `decode_success_rate`).  
  **Mitigation:** Reference TED-LIUM inventory verbatim trong docstring; chỉ swap decoder; giữ nguyên schema 1-1.
- **Risk:** `Frames/test/{video_id}/` có thể chứa nested structure khác (vd: `Frames/test/10/1.png` vs `Frames/test/video10/frame_001.png`).  
  **Mitigation:** Trước khi code, ls `Frames/test/` để xác nhận cấu trúc thực tế rồi mới viết glob pattern.

## Effort Breakdown

| Bước | Thời gian |
|------|-----------|
| Khảo sát cấu trúc `Frames/test/` + chọn 200 ảnh | 1-2 giờ |
| Viết `iiit_cvid_d2.yaml` + license adjudication | 2-3 giờ |
| Clone + adapt `phase2_freeze_iiit_cvid.py` | 4-6 giờ |
| Run + debug 00c (emits 13 payloads + 8 figures) | 2-3 giờ |
| Regression check TED-LIUM + update research_decisions | 1 giờ |
| **Tổng** | **1-2 ngày (10-15 giờ)** |
