---
phase: 3
title: "EduViQA D2 Freeze"
status: cancelled
priority: P1
dependencies: ["phase-01-phase-01-iiit-cvid-d2-freeze"]
effort: "0 hours (cancelled 2026-09-26)"
cancelled_reason: "missing provenance - no source URL, no license, no download date. Triggers drop criterion #1 của chính phase này (vi phạm research_decisions ground_truth.policy: official_or_preexisting_labels_only). User-confirmed 2026-09-26: cancel Phase 3, chạy Phase 4/5 với 2 datasets."
---

# Phase 3: EduViQA D2 Freeze — CANCELLED

> ## CANCELLED 2026-09-26 (user-confirmed)
>
> **Lý do:** `experiments/datasets/eduviqa/` **không có `provenance.json`**. Chỉ có
> `.gitattributes`, `q_and_a.json`, `hybrid_clip_ssim_chunking_meta_data.json`.
> Không có source URL, không có license, không có ngày download → không thể adjudicate
> rights theo `research_decisions.yaml` `ground_truth.policy: official_or_preexisting_labels_only`.
> Đây chính là **drop criterion #1** do chính phase file này định nghĩa.
>
> **Hệ quả:** `eligible_d2` dataset count giữ ở **2** (TED-LIUM + IIIT-CVID),
> `eligible_d2` endpoint count giữ ở **2** (`asr_benchmark`, `ocr_benchmark`).
> Phase 4 aggregate 2 matrices; Phase 5 chại OCR first-real benchmark **only**.
> Đây vẫn đủ cho paper minimum coverage (2 D2 datasets, 2 real benchmarks).
>
> **Additional blocker phát hiện khi verify (2026-09-26)** — spec của phase này sai ở 3 chỗ
> so với disk, nên kể cả khi có provenance vẫn cần sửa trước khi chạy:
> 1. **Video extensions**: plan giả định `.mp4`; thực tế mixed `.mp4`(11) / `.mkv`(9) / `.webm`(1).
> 2. **`video_transcripts/<video_id>` là DIRECTORY**, không phải file `.json`. Chứa
>    `chunks.pkl` + `metadata.json` + `metadata_chunks.json` + `transcript.txt`.
> 3. **`video_chunkings/<video_id>` là DIRECTORY keyframe JPGs**
>    (`persian_hybrid_clip_ssim_frame_N.jpg`), không phải JSON `{chunks:[{start,end}]}`.
>    Chunk timing phải suy từ `video_transcripts/*/chunks.pkl` hoặc `metadata_chunks.json`.
> 4. Tên thư mục đã sanitize (`:` → `_`) nên **không** khớp trực tiếp tên file video.
>
> **Reopen condition:** user cung cấp source URL + license + download date → tạo
> `provenance.json`, sửa 4 spec trên, rồi chạy lại phase này.
> Candidate thay thế nếu cần multimodal QA: **SlideVQA** (14,484 released QA pairs,
> `train/val/test` annotations + `provenance.json` đã có) — nhưng **slide images chưa có
> trên disk**, cần download từ SlideShare (network). Xem `plans/` follow-up.

## Overview (original, superseded)

Đưa EduViQA (educational video + transcript + QA corpus) từ "raw material on disk" lên **D2 frozen subset** với multi-modal contract (video + transcript + chunking + QA). Đây là dataset multimodal thật đầu tiên của pipeline, mở khóa các endpoint `qa_benchmark`, `retrieval_benchmark` (và conditionally `chaptering`/`summary` tùy provenance adjudication).

## Requirements

- **Functional**: EduViQA frozen manifest + 13-bundle D2 validator pass; ≥ 2 endpoints eligible_d2 trong endpoint matrix.
- **Non-functional**: Provenance audit bắt buộc trước freeze (license, source URL, download date); yt-dlp availability probe nếu video URLs external; ≥ 80% video available.
- **Contract preservation**: TED-LIUM + IIIT-CVID artifacts SHA-256 không đổi; research_decisions.yaml `next_target.eduviqa` được mark complete.

## Architecture

Clone pattern từ `phase2_freeze_iiit_cvid.py` (sau khi Phase 1 hoàn thành):

1. `_build_inventory_from_disk` đổi decoder từ `PIL.Image.open()` → `cv2.VideoCapture()` (lấy frame_count, fps, duration, resolution, codec) + `json.load` cho transcript/chunking/QA.
2. `unit_id` scheme: `f"{video_id}"` (1 unit = 1 video với 4 modalities liên kết).
3. `extension_counts` → `.mp4` (video) + `.json` (transcript, chunking, qa).
4. `split_counts` → adjudicate từ provenance (EduViQA có train/val/test split chưa? Nếu chưa → cần split policy trong YAML).
5. Output namespace: `experiments/outputs/phase2_eduviqa_d2/official/full/`.

License adjudication:
- Source: provenance.json chưa xác nhận có → step 1 phải tìm provenance trước.
- Nếu không tìm được → escalate user, phase thành `blocked: missing provenance`.
- Decision default: chỉ publish aggregate metrics (QA accuracy, retrieval Recall@k); không re-host video.

Multi-modal figures:
- Video duration distribution (histogram)
- Transcript word count distribution (histogram)
- Chunk count per video (histogram)
- QA count per video (histogram)
- Cross-modal coverage (% chunks có transcript word count > 0)

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/registry/datasets/eduviqa_d2.yaml`
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_eduviqa.py`
  - `multimodal-lecture-summarizer/tests/test_unlock_eduviqa_d2.py`
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_iiit_cvid.py` (Phase 1 pattern, sau khi Phase 1 hoàn thành)
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/Videos/` (20 video files)
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/video_transcripts/`
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/video_chunkings/`
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/hybrid_clip_ssim_chunking_meta_data.json`
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/q_and_a.json`
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml`

## Implementation Steps

1. **Source provenance audit (BẮT BUỘC trước freeze)** (4-6 giờ):
   ```bash
   ls experiments/datasets/eduviqa/
   cat experiments/datasets/eduviqa/.gitattributes   # xem git-lfs pointers
   find experiments/datasets/eduviqa -name "provenance*" -o -name "README*" -o -name "*.md"
   ```
   - Tìm `provenance.json` hoặc docstring gốc: URL gốc, ngày download, license, sha256 zip.
   - Nếu không có → **escalate user ngay** qua AskUserQuestion: "EduViQA không có provenance rõ ràng; bạn có biết URL gốc + license của 20 video này không?". Nếu user không biết → phase thành `blocked: missing provenance` và defer.
   - Document probe `yt-dlp` cho từng video URL (nếu có URLs): ngày probe, status (available / private / deleted), bytes-on-disk, sha256.
     ```bash
     yt-dlp --skip-download --print "%(id)s %(availability)s" <URL1> <URL2> ...
     ```
   - Nếu < 80% video available → escalate user trước khi freeze (degrade D2 → D1 pilot).

2. **Tạo `experiments/registry/datasets/eduviqa_d2.yaml`** theo schema `_load_d2_config`, mở rộng contract cho multi-modal:
   ```yaml
   schema_version: 1
   dataset_id: eduviqa
   source: "local_curated_videos_with_transcripts"
   release: "{date or version}"
   revision: "{sha256_8chars}"
   local_snapshot_fingerprint: "{sha256_full}"
   
   rights: "{license_text từ provenance}"
   access_status: "available"
   leakage_exception: null
   
   data_root_key: "experiments/datasets/eduviqa"
   receipt_path: "datasets/eduviqa/official/full/payloads/dataset.feasibility_receipts.json"
   
   # Multi-modal contract
   modalities:
     - video:
         unit_pattern: "Videos/<video_id>.mp4"
         file_count: 20
     - transcript:
         unit_pattern: "video_transcripts/<video_id>.json"
         schema: {segments: [{start, end, text}], language: "en"}
     - chunking:
         unit_pattern: "video_chunkings/<video_id>.json"
         schema: {chunks: [{start, end}]}
         note: "SSIM-based heuristic chunking — NOT released chapter GT, input contract only"
     - qa:
         unit_pattern: "q_and_a.json"
         schema: {questions: [{video_id, question, answer, evidence_chunk_ids}]}
   
   expected_bytes: {sum all video files}
   predicted_peak_bytes: {expected_bytes * 4}   # 4× headroom cho video decode
   estimated_completion_hours: {depends on yt-dlp probe; default 2.0}
   
   min_schema_success_rate: 1.0
   min_checksum_success_rate: 1.0
   min_download_success_rate: 1.0   # local scan
   min_decode_success_rate: 0.95
   
   ground_truth:
     status: "released"
     sources:
       transcript: "{provenance_of_transcripts}"
       qa: "{provenance_of_qa_pairs}"
       chunking: "SSIM heuristic — NOT official GT, input contract only"
     annotation_protocol: >
       Transcripts: {protocol}. QA pairs: {protocol}. Chunks: SSIM-based hybrid.
   
   # Eligibility per endpoint
   endpoint_eligibility:
     qa_benchmark: eligible_d2
     retrieval_benchmark: eligible_d2
     chaptering_benchmark: not_eligible   # SSIM chunking không phải released GT
     summary_benchmark: not_eligible      # không có native reference summary
   
   fallback_dataset: null
   ```

3. **Clone driver script**:
   ```bash
   cp experiments/scripts/phase2_freeze_iiit_cvid.py experiments/scripts/phase2_freeze_eduviqa.py
   ```
   Replace 4 chỗ:
   - `DATASET_ID = "iiit_cvid"` → `DATASET_ID = "eduviqa"`
   - `MEDIA_EXT = {".png", ".jpg"}` → `MEDIA_EXT = {".mp4"}`
   - `_build_inventory_from_disk`: thay `PIL.Image.open()` → `cv2.VideoCapture()` + `json.load`.
   - `unit_id` scheme: `f"{video_id}"` (không có split prefix vì provenance chưa rõ có official split).
   - **Multi-modal linking**: mỗi video unit liên kết với transcript/chunking/qa files; ghi vào `unit_records[].linked_modalities`.

4. **Run yt-dlp availability probe** (nếu provenance có URLs):
   ```bash
   yt-dlp --skip-download --print "%(id)s %(availability)s" $(cat video_urls.txt) \
     > experiments/outputs/phase2_eduviqa_d2/probes/ytdlp_availability.json
   ```
   - Nếu > 20% video unavailable → escalate user trước khi freeze.

5. **Run driver**:
   ```bash
   cd multimodal-lecture-summarizer
   python -m experiments.scripts.phase2_freeze_eduviqa \
     --artifact-root experiments/outputs/phase2_eduviqa_d2
   ```
   Verify outputs:
   - `dataset.frozen_manifest.json` có `freeze_status=eligible`, multi-modal contract recorded.
   - `dataset.unit_profile.json` có ≥ 4 fields per unit (video, transcript, chunking, qa).
   - `dataset.endpoint_matrix.json` có entry `eduviqa × qa_benchmark → eligible_d2` và `eduviqa × retrieval_benchmark → eligible_d2`.
   - `dataset.leakage_audit.json` cross-dataset leakage với TED-LIUM + IIIT-CVID = 0.

6. **Multi-modal figures** (≥ 5 figures):
   ```python
   # In phase2_freeze_eduviqa.py, sau khi unit_records built:
   render_multimodal_figures(unit_records, figure_dir, manifest_metadata)
   ```
   - `multimodal_video_duration_distribution.png`
   - `multimodal_transcript_wordcount_distribution.png`
   - `multimodal_chunk_count_per_video.png`
   - `multimodal_qa_count_per_video.png`
   - `multimodal_cross_modal_coverage.png` (% chunks có transcript word count > 0)

7. **Update `research_decisions.yaml`**:
   ```yaml
   phase2_dataset_execution:
     next_target:
       dataset_id: eduviqa
       endpoint: qa_benchmark
       status: completed   # mới
       completion_date: "{date}"
       evidence: experiments/outputs/phase2_eduviqa_d2/official/full/payloads/dataset.frozen_manifest.json
   ```

8. **Regression**: Re-run Phase 1, 2 drivers để bảo đảm không phá artifacts cũ.

9. **Tests mới** `tests/test_unlock_eduviqa_d2.py` (≥ 3 tests):
   - `test_eduviqa_d2_yaml_schema_valid`: parse YAML qua `_load_d2_config("eduviqa")`.
   - `test_eduviqa_multimodal_unit_records_4_modalities`: mỗi unit có ≥ 4 linked modalities.
   - `test_eduviqa_endpoint_matrix_qa_retrieval_eligible`: validator pass + endpoint_matrix có QA + retrieval entries.

## Success Criteria

- [ ] Provenance của EduViQA được document rõ (URL gốc + license + ngày download + sha256).
- [ ] `yt-dlp` availability probe (nếu áp dụng) pass với ≥ 80% video available.
- [ ] `experiments/registry/datasets/eduviqa_d2.yaml` parse thành công qua `_load_d2_config("eduviqa")`.
- [ ] `experiments/outputs/phase2_eduviqa_d2/official/full/payloads/dataset.frozen_manifest.json` có ≥ 1 record `freeze_status=eligible`, multi-modal contract recorded.
- [ ] ≥ 5 multi-modal specific figures emitted.
- [ ] `dataset.endpoint_matrix.json` có ≥ 2 entries cho EduViQA (`qa_benchmark`, `retrieval_benchmark`).
- [ ] Regression: TED-LIUM + IIIT-CVID frozen_manifest SHA-256 không đổi.
- [ ] `research_decisions.yaml.phase2_dataset_execution.next_target.eduviqa.status` = `completed`.
- [ ] `tests/test_unlock_eduviqa_d2.py` PASS ≥ 3/3.

## Risk Assessment

- **Risk:** EduViQA không có provenance rõ ràng → không thể freeze hợp lệ.
  **Mitigation:** Step 1 là BLOCKER — escalate user trước khi viết YAML. Nếu không có provenance, đóng phase này thành `blocked: missing provenance` và defer.
- **Risk:** Video files có thể đến từ YouTube và bị takedown giữa lúc freeze và lúc benchmark.
  **Mitigation:** Snapshot SHA-256 từng video; yt-dlp probe record trong YAML để sau này có thể reproduce mirror nếu cần.
- **Risk:** Multi-modal decode (video + json) trong `_build_inventory_from_disk` có thể chậm trên local CPU.
  **Mitigation:** Dùng `cv2.VideoCapture` chỉ lấy metadata (frame count, fps) — không decode full frame; json.load là microseconds.
- **Risk:** Chaptering/summary endpoints bị user expectation mismatch (user muốn mở nhưng plan khuyến nghị `not_eligible`).
  **Mitigation:** Open question #3, #4 trong plan.md đã ghi rõ — user có thể override recommendation qua AskUserQuestion trước khi viết YAML.
- **Risk:** Phase 3 chạm `research_decisions.yaml` và Phase 1 cũng có thể (qua `next_target`).
  **Mitigation:** Phase 1 → Phase 3 strictly sequential (Phase 3 depends_on Phase 1 vì cùng pattern); git 3-way merge nếu parallel.
- **Risk:** Multi-modal contract có thể vượt quá schema hiện tại của `validate_dataset_characterization_bundle()`.
  **Mitigation:** Inspect existing validator trước khi viết YAML; nếu thiếu schema fields → extend validator (chấp nhận touch plan-owned code).

## Defer / Drop Criteria

Cân nhắc **drop Phase 3 entirely** nếu:
1. Provenance của EduViQA không tìm được → vi phạm `research_decisions.policy`.
2. yt-dlp probe < 80% available → không đủ statistical power cho D2 freeze.
3. Multi-modal decode fail > 5% unit trên `local_rtx4050_6gb`.

Trong 3 case trên, đánh dấu Phase 3 thành `cancelled` với reason rõ ràng trong progress report; eligible_dataset_count giữ ở 2 (TED-LIUM + IIIT-CVID), vẫn đủ cho paper minimum coverage.

## Effort Breakdown

| Step | Time |
|------|------|
| Provenance audit + yt-dlp probe | 4-6 giờ |
| Viết `eduviqa_d2.yaml` (multi-modal contract) | 3-4 giờ |
| Clone + adapt `phase2_freeze_eduviqa.py` | 6-8 giờ |
| Run + debug 00c | 3-4 giờ |
| Multi-modal figures (5 figures) | 2-3 giờ |
| Regression + update research_decisions | 1-2 giờ |
| Tests + journal | 2-3 giờ |
| **Tổng** | **21-30 giờ (2.5-3.5 ngày)** |