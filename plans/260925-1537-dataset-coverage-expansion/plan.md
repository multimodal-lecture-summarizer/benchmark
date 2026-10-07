---
title: >-
  Dataset Coverage Expansion: VISTA Encode + IIIT-CVID/EduViQA D2 Freeze + Audio
  Figures
description: >-
  Đóng 3-4 open criterion cho phase 2 bằng quick-win VISTA encoding, IIIT-CVID
  D2 freeze (re-use TED-LIUM pattern), audio modality-specific figures cho
  TED-LIUM, và EduViQA D2 freeze.
status: pending
priority: P1
branch: ''
tags:
  - dataset-freeze
  - phase2
  - d2
  - iiit-cvid
  - eduviqa
  - vista
  - tedlium
  - audio-figures
  - ocr
blockedBy: []
blocks: []
created: '2026-09-25T02:39:55.315Z'
createdBy: 'ck:plan'
source: skill
---

# Dataset Coverage Expansion: VISTA Encode + IIIT-CVID/EduViQA D2 Freeze + Audio Figures

> Historical plan: the old D2 freeze drivers, generic dataset profile/contract modules and modality-figure emitters cited below were removed on 2026-10-07. Earlier receipts remain historical; these steps are no longer runnable instructions.

## Overview

Plan bốn pha nhỏ gọn nhằm **đóng các open / deferred criterion của phase 2 (freeze dataset & ground-truth contract)** trong scientific benchmark pipeline hiện hành (`plans/260904-scientific-benchmark-overhaul`).

- **Bối cảnh:** TED-LIUM đã đạt D2 frozen (eligible=1, 20 units, registry có `tedlium3_d2.yaml`). IIIT-CVID đã có 200 ảnh OCR baseline + `.extracted` + `.cache` sẵn trong `experiments/datasets/iiit_cvid/`. EduViQA có 20 videos + transcripts + chunkings + `q_and_a.json`. VISTA đã được probe (`plans/260830-1917-scientific-benchmark/probes/output/vista_summary.json`) nhưng chưa encode registry.
- **Mục tiêu cuối:** eligible_dataset_count tăng từ **1 → 2** (OCR task có D2 dataset thứ 2), criterion "each eligible task has labeled dataset" được close cho cả audio lẫn OCR, deferred audio figures được thay bằng plots thật, và VISTA được encode như một "registered unavailable fallback" để khóa criterion #2.
- **Thứ tự thực thi khuyến nghị (do user xác nhận):**
  1. Phase 1 (VISTA Encoding) — quick-win ~30 phút, đóng criterion #2 ngay.
  2. Phase 2 (IIIT-CVID D2 Freeze) — core work 1-2 ngày, mở rộng eligible coverage.
  3. Phase 3 (Audio Modality-Specific Figures) — 4-6 giờ, làm song song hoặc sau Phase 2.
  4. Phase 4 (EduViQA D2 Freeze) — defer; highest value nhưng effort cao nhất (multi-modal).

> Phase 1 có priority cao nhất về **effort/value ratio** và đóng criterion #2 (một blocker nhỏ nhưng kéo dài). Phase 2 là "core" — đây là pha đem lại value lớn nhất (1 eligible dataset mới). Phase 3 là polish cho figures. Phase 4 là defer / parallel.

## Phases

| Phase | Name | Status | Priority | Effort | Closes |
|:-----:|:-----|:-------|:--------:|:------:|:-------|
| 1 | [VISTA Encoding](./phase-01-vista-encoding.md) | Completed | P1 | ~30 min | Completed |
| 2 | [IIIT-CVID D2 Freeze](./phase-02-iiit-cvid-d2-freeze.md) | Pending | P1 | 1-2 days | Criterion #5 (OCR task has D2 labeled dataset); eligible_datasets 1 → 2 |
| 3 | [Audio Modality-Specific Figures (TED-LIUM)](./phase-03-audio-modality-specific-figures-ted-lium.md) | Pending | P2 | 4-6 hours | Deferred criterion #7 (audio modality-specific figures from real data) |
| 4 | [EduViQA D2 Freeze](./phase-04-eduviqa-d2-freeze.md) | Pending | P3 | 2-3 days | Multi-modal labeled dataset for video+QA task; defer if compute blocks |

## Cross-Plan Relationships

- **Blocks nothing downstream** — Phase 1 chỉ thêm registry entry, Phase 2-3 chỉ emit artifacts. Phase 4 nếu chạy sẽ unblock RQ3 (evidence QA) benchmark với multi-modal data thật.
- **Blocked by nothing** — toàn bộ 4 pha đều độc lập với nhau ngoại trừ Phase 2 dùng chung helper với TED-LIUM (đã có sẵn).
- **Touches the active scientific benchmark plan (`260904-scientific-benchmark-overhaul`)** nhưng không trực thuộc; sản phẩm cuối (extra eligible dataset + VISTA entry) sẽ được ghi nhận vào progress report sau khi hoàn thành.

## Acceptance Gate cho cả plan

- [ ] `experiments/registry/datasets/iiit_cvid_d2.yaml` tồn tại, hợp lệ theo `_load_d2_config` schema, license adjudicated.
- [x] `experiments/registry/research_decisions.yaml` có `large_dataset_policy.vista_full` entry đầy đủ với `access_status=unavailable` và reason citing 1.93 TB budget overflow. **(Phase 1 done, 2026-09-25, schema migration Path B; `contract_validator.py` đồng bộ; 51/51 tests pass.)**
- [ ] `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.frozen_manifest.json` chứa ≥ 1 record với `freeze_status=eligible` và `scientific_selection_eligible=true`.
- [ ] `experiments/outputs/phase2_tedlium_d2/official/full/figures/` chứa ít nhất 3 audio-specific figures mới (ECDF, sample-rate sanity, channels) thay thế stub trước đó.
- [ ] Không phá vỡ TED-LIUM artifacts hiện hữu (regression check: chạy lại `phase2_freeze_tedlium.py` vẫn pass, frozen_manifest SHA-256 trùng trước/sau hoặc chỉ thay đổi theo expected delta).
