---
phase: 4
title: "EduViQA D2 Freeze"
status: pending
priority: P3
effort: "2-3 days"
dependencies: ["phase-02-iiit-cvid-d2-freeze"]   # pattern reuse từ Phase 2
---

# Phase 4: EduViQA D2 Freeze

## Overview

Đưa EduViQA (educational video + transcript + QA corpus) từ trạng thái "raw material on disk" lên **D2 frozen subset** với multi-modal contract (video + transcript + chunking + QA). Đây là dataset multi-modal thật đầu tiên của plan, có giá trị cao nhất cho **RQ3 (Evidence QA)** benchmark — nhưng cũng phức tạp nhất vì 4 modalities cùng lúc.

> **Defer / parallel:** Phase này chỉ chạy sau khi Phase 2 (IIIT-CVID) pass, vì cùng pattern driver. Nếu compute profile `colab_t4` đang bận cho downstream benchmark, có thể defer đến khi free.

## Background & Evidence

- **Material đã có sẵn:**
  - `experiments/datasets/eduviqa/Videos/` — 20 video files (theo `eduviqa_d2.yaml` chưa tồn tại, cần ls để xác nhận count chính xác).
  - `experiments/datasets/eduviqa/video_transcripts/` — auto-generated transcripts (Whisper hoặc tương đương).
  - `experiments/datasets/eduviqa/video_chunkings/` — chunk boundaries (25s default theo RRF config).
  - `experiments/datasets/eduviqa/hybrid_clip_ssim_chunking_meta_data.json` — SSIM-based chunking metadata.
  - `experiments/datasets/eduviqa/q_and_a.json` — QA pairs (input cho RQ3).
  - `experiments/datasets/eduviqa/.cache/` — HuggingFace download cache.
- **Source unclear:** Provenance của EduViQA chưa thấy trong `experiments/datasets/eduviqa/provenance.json` (cần ls). Có thể là user-curated subset hoặc public dataset subset. **Cần adjudicate trước khi freeze.**
- **Source acquisition probe:** Cần `yt-dlp` availability probe documented — EduViQA video URLs có thể đến từ YouTube playlist gốc, cần check video còn available hay không.

## Implementation Steps

1. **Source provenance audit (BẮT BUỘC trước freeze):**
   - Tìm `provenance.json` hoặc docstring gốc: URL gốc, ngày download, license, sha256 zip.
   - Nếu không có → yêu cầu user cung cấp provenance trước khi viết YAML; KHÔNG freeze dataset không rõ nguồn gốc (vi phạm `ground_truth.policy: official_or_preexisting_labels_only`).
   - Document probe `yt-dlp` cho từng video URL: ngày probe, status (available / private / deleted), bytes-on-disk, sha256.

2. **Tạo `experiments/registry/datasets/eduviqa_d2.yaml`** theo schema `_load_d2_config`, mở rộng contract cho multi-modal:
   ```yaml
   schema_version: 1
   dataset_id: eduviqa
   source: "local_curated_videos_with_transcripts"
   release: "<date>"
   revision: "<sha256>"
   local_snapshot_fingerprint: "<fingerprint>"

   # Rights — adjudicate dựa trên provenance
   rights: "<license text từ provenance>"
   access_status: "available"
   leakage_exception: null

   data_root_key: "experiments/datasets/eduviqa"
   receipt_path: "datasets/eduviqa/official/full/payloads/dataset.feasibility_receipts.json"

   # Multi-modal contract
   modalities:
     - video:    # .mp4 files
       unit_pattern: "Videos/<video_id>.mp4"
     - transcript:  # .json or .txt
       unit_pattern: "video_transcripts/<video_id>.json"
     - chunking:    # chunk boundaries
       unit_pattern: "video_chunkings/<video_id>.json"
     - qa:          # QA pairs (ground truth for RQ3)
       unit_pattern: "q_and_a.json"
       fields: [question, answer, evidence_chunk_ids]

   expected_bytes: <sum all video files>
   predicted_peak_bytes: <expected_bytes * 4>   # 4× headroom cho video decode
   estimated_completion_hours: <depends on yt-dlp probe>

   # D2 gates (same as IIIT-CVID)
   min_schema_success_rate: 1.0
   min_checksum_success_rate: 1.0
   min_download_success_rate: 0.90
   min_decode_success_rate: 0.95

   # Ground truth — multi-task
   ground_truth:
     status: "released"
     sources:
       transcript: "<provenance>"
       qa: "<provenance>"
     annotation_protocol: >
       Transcripts: <protocol>. QA pairs: <protocol>. Chunks: SSIM-based hybrid.

   fallback_dataset: null
   ```

3. **Clone driver script:**
   - `cp experiments/scripts/phase2_freeze_iiit_cvid.py experiments/scripts/phase2_freeze_eduviqa.py`
   - Replace `_build_inventory_from_disk` body: thay image decoder bằng:
     ```python
     import cv2   # for video decode (frame count, fps, duration, resolution)
     # + json.load cho transcript / chunking / qa
     ```
   - `unit_id` scheme: `f"{video_id}"` (1 unit = 1 video với 4 modalities liên kết).
   - `extension_counts`: `.mp4` (video) + `.json` (transcript, chunking, qa).
   - `split_counts`: cần adjudicate từ provenance (EduViQA có train/val/test split chưa? Nếu chưa → cần split policy trong YAML).

4. **Run yt-dlp availability probe trước freeze:**
   ```bash
   yt-dlp --skip-download --print "%(id)s %(availability)s" <URL1> <URL2> ...
   ```
   - Output ghi vào `experiments/outputs/phase2_eduviqa_d2/probes/ytdlp_availability.json`.
   - Nếu > 20% video unavailable → escalate với user trước khi freeze (degrade D2 → D1 pilot).

5. **Run 00c profile_dataset** để emit 13 payloads + 8 figures + frozen_manifest. Lưu ý: figures cho EduViQA phải là **multi-modal specific** (không chỉ video duration):
   - Video duration distribution
   - Transcript word count distribution
   - Chunk count per video distribution
   - QA count per video distribution
   - Cross-modal coverage (vd: bao nhiêu % chunks có transcript word count > 0?)

6. **Update `research_decisions.yaml`** tương tự Phase 2.

7. **Regression:** Re-run Phase 1, 2, 3 drivers để bảo đảm không phá artifacts cũ.

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/registry/datasets/eduviqa_d2.yaml`
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_eduviqa.py`
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_iiit_cvid.py` (Phase 2 — pattern to clone, sau khi Phase 2 hoàn thành)
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/q_and_a.json`
  - `multimodal-lecture-summarizer/experiments/datasets/eduviqa/hybrid_clip_ssim_chunking_meta_data.json`
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml`

## Success Criteria

- [ ] Provenance của EduViQA được document rõ (URL gốc + license + ngày download + sha256).
- [ ] `yt-dlp` availability probe pass với ≥ 80% video available.
- [ ] `experiments/registry/datasets/eduviqa_d2.yaml` parse thành công qua `_load_d2_config("eduviqa")`.
- [ ] `experiments/outputs/phase2_eduviqa_d2/official/full/payloads/dataset.frozen_manifest.json` chứa ≥ 1 record `freeze_status=eligible`, multi-modal contract recorded.
- [ ] ≥ 4 multi-modal specific figures emitted.
- [ ] Regression: TED-LIUM + IIIT-CVID frozen_manifest SHA-256 không đổi.

## Risk Assessment

- **Risk:** EduViQA không có provenance rõ ràng → không thể freeze hợp lệ.  
  **Mitigation:** Step 1 là BLOCKER — escalate user trước khi viết YAML. Nếu không có provenance, đóng phase này thành "blocked: missing provenance" và defer.
- **Risk:** Video files có thể đến từ YouTube và bị takedown giữa lúc freeze và lúc benchmark.  
  **Mitigation:** Snapshot SHA-256 từng video; yt-dlp probe record trong YAML để sau này có thể reproduce mirror nếu cần.
- **Risk:** Multi-modal decode (video + json) trong `_build_inventory_from_disk` có thể chậm trên local CPU.  
  **Mitigation:** Dùng `cv2.VideoCapture` chỉ lấy metadata (frame count, fps) — không decode full frame; json.load là microseconds.
- **Risk:** Phase 4 chạm `research_decisions.yaml` và Phase 3 cũng có thể (qua figure_manifest, nhưng research_decisions thì không) → xung đột với Phase 2.  
  **Mitigation:** Sequence Phase 2 → Phase 4 strictly (Phase 4 depends on Phase 2). Nếu parallel, dùng git stash hoặc 3-way merge cho YAML.

## Effort Breakdown

| Bước | Thời gian |
|------|-----------|
| Provenance audit + yt-dlp probe | 4-6 giờ |
| Viết `eduviqa_d2.yaml` (multi-modal contract) | 3-4 giờ |
| Clone + adapt `phase2_freeze_eduviqa.py` | 6-8 giờ |
| Run + debug 00c | 3-4 giờ |
| Multi-modal figures | 2-3 giờ |
| Regression + update research_decisions | 1-2 giờ |
| **Tổng** | **2-3 ngày (20-27 giờ)** |

## Defer / Drop Criteria

Cân nhắc **drop Phase 4 entirely** nếu bất kỳ điều nào xảy ra:
1. Provenance của EduViQA không tìm được → vi phạm research_decisions policy.
2. yt-dlp probe < 80% available → không đủ statistical power cho D2 freeze.
3. Compute profile `local_rtx4050_6gb` không đủ cho multi-modal decode (RAM overflow).

Trong 3 case trên, đánh dấu Phase 4 thành `cancelled` với reason rõ ràng trong progress report; eligible_dataset_count giữ ở 2 (TED-LIUM + IIIT-CVID), vẫn đủ cho paper minimum coverage.
