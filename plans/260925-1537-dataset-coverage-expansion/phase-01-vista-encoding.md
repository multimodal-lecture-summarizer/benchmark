---
phase: 1
title: VISTA Encoding
status: completed
priority: P1
effort: ~30 minutes
dependencies: []
---

# Phase 1: VISTA Encoding

## Overview

Encode VISTA `dongqi-me/VISTA` (≈ 1.93 TB tổng, ≈ 18,606 video files) thành một registry entry rõ ràng với `access_status: unavailable` và `acquisition_level: D0`, đồng thời capture lý do feasible-not (budget overflow) và fallback chain. Mục tiêu duy nhất: đóng **criterion #2** (VISTA feasibility encoding) mà user đã nhắc trong prompt — chỉ cần một YAML record, không cần download hay chạy bất kỳ pipeline nào.

## Background & Evidence

- **Probe đã chạy:** `plans/260830-1917-scientific-benchmark/probes/output/vista_summary.json` (`gating: "gated"`, `license: "unknown"`, `loaded: false`, `all_files_count: 18606`, streaming gặp 401 Unauthorized).
- **Decision policy đã freeze:** `experiments/registry/research_decisions.yaml` mục `large_dataset_policy`:
  ```yaml
  vista_full_local_status: not_feasible_local
  allowed_alternatives:
    - labeled_subset
    - registered_fallback_dataset
    - separately_approved_external_storage_profile
  ```
  Tức là đã có decision; thiếu registry entry chính thức.
- **Lý do budget overflow:** `experiments/datasets/iiit_cvid/IIIT-CVid.zip` đã là 2.43 GB (single zip); 109.6 GB peak disk budget đã ghi trong `experiments/scripts/phase2_freeze_tedlium.py:39` artifact_root pattern. VISTA 1.93 TB vượt ~17×.

## Implementation Steps

1. **Quyết định vị trí registry entry.** Hai lựa chọn:
   - (a) Thêm field mới dưới `large_dataset_policy` trong `experiments/registry/research_decisions.yaml` — phù hợp vì decision đã đông cứng ở đây.
   - (b) Tạo file mới `experiments/registry/datasets/vista_full_d0.yaml` theo D2 schema nhưng với `access_status: unavailable` — nhất quán pattern với `tedlium3_d2.yaml`.

   **Chọn (a)** vì VISTA chưa bao giờ đạt D1; file riêng sẽ lẫn lộn với eligible datasets. Quyết định có thể đảo nếu team muốn uniform schema.

2. **⚠️ Critical dependency discovered during implementation (2026-09-25):**
   `experiments/registry/contract_validator.py` enforce **exact-match** validation cho toàn bộ `large_dataset_policy` dict (line 145-148):
   ```python
   "large_dataset_policy": {
       "vista_full_local_status": "not_feasible_local",
       "allowed_alternatives": ["labeled_subset", "registered_fallback_dataset", "separately_approved_external_storage_profile"],
   },
   ```
   `tests/test_research_contracts.py::test_default_contracts_are_valid` yêu cầu `validate_contracts() == []` (zero errors).
   `benchmarks/scripts/execute_all_notebooks.py:345` include `contract_validator.py` trong `_code_state_sha256` hash cho run manifest.
   
   **Quyết định (Path B, user-approved):** Drop key cũ `vista_full_local_status`, thay bằng nested `vista_full:` block, **đồng thời cập nhật `contract_validator.py` expected_sections** để khớp. Breaking change của contract nhưng đồng bộ; tests vẫn pass (51/51 verified sau patch).

3. **Patch `experiments/registry/research_decisions.yaml`** — thay khối `large_dataset_policy` hiện tại bằng:
   ```yaml
   large_dataset_policy:
     vista_full:
       dataset_id: vista_full
       hf_dataset: "dongqi-me/VISTA"
       access_status: unavailable
       acquisition_level: D0
       fallback_dataset: null
       reason: "1.93 TB (18,606 video files) exceeds local 109.6 GB peak disk budget by ~17×; streaming probe gated by 401 Unauthorized; license=unknown."
       evidence:
         probe_output: "plans/260830-1917-scientific-benchmark/probes/output/vista_summary.json"
         decision_date: "2026-09-25"
         adjudicated_by: "phi-hung"
       allowed_alternatives:
         - labeled_subset
         - registered_fallback_dataset
         - separately_approved_external_storage_profile
       re_adjudication_required_if:
         - storage_budget_increases_above_2tb
         - license_resolved_to_official_open
   ```

3. **Cập nhật tham chiếu downstream.** Nếu có code đọc `large_dataset_policy.vista_full_local_status` cũ (search codebase trước), thêm shim hoặc đổi tên. **Phát hiện:** `experiments/registry/contract_validator.py` line 145-148 enforce exact-match dict comparison — đã patch đồng bộ với schema mới (xem Step 2 note).

4. **Patch `experiments/registry/contract_validator.py`** — thay khối `expected_sections["large_dataset_policy"]` tương ứng với schema mới. Đã thêm comment tham chiếu plan này.

5. **Snapshot decision rationale** trong comment đầu file (≤ 5 dòng) ghi rõ lý do encoding lần này đóng criterion #2.

6. **Verify:** `pytest tests/test_research_contracts.py` → 51/51 pass; `validate_contracts() == []`.

## Related Code Files

- **Modify:**
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml`
  - `multimodal-lecture-summarizer/experiments/registry/contract_validator.py` (line 145-148)
- **Read-only references:**
  - `multimodal-lecture-summarizer/plans/260830-1917-scientific-benchmark/probes/output/vista_summary.json`
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_tedlium.py:39` (cho budget tham chiếu)
  - `multimodal-lecture-summarizer/tests/test_research_contracts.py` (đã verify pass 51/51)
  - `multimodal-lecture-summarizer/benchmarks/scripts/execute_all_notebooks.py:345` (contract_validator trong SHA-256 hash)

## Success Criteria

- [x] `research_decisions.yaml.large_dataset_policy.vista_full.access_status == "unavailable"`
- [x] `acquisition_level == "D0"`
- [x] `reason` chứa cụm "1.93 TB" và "109.6 GB"
- [x] `evidence.probe_output` path tồn tại trên disk
- [x] `re_adjudication_required_if` có ít nhất 2 điều kiện trigger
- [x] `pytest tests/test_research_contracts.py` 51/51 pass
- [x] `validate_contracts() == []` (zero errors)
- [x] YAML parse thành công (`python -c "import yaml; yaml.safe_load(open('experiments/registry/research_decisions.yaml'))"`).
- [x] Grep `vista_full_local_status` trong `experiments/` + `tests/` + `benchmarks/` trả về 0 hit (chỉ còn hit trong chính plan doc này, expected — document lịch sử schema migration).

## Risk Assessment

- **Risk:** Phase sau (audit / red-team) tìm thấy `access_status: unavailable` mâu thuẫn với `allowed_alternatives: [labeled_subset, ...]` — tức là vẫn "có lối thoát".  
  **Mitigation:** Ghi rõ trong comment rằng `unavailable` chỉ áp dụng cho **VISTA full corpus**; alternatives là các path forward riêng cần adjudicate trước khi dùng.
- **Risk:** Schema mismatch nếu sau này muốn load registry programmatically (ví dụ dataset_contracts.py).  
  **Mitigation:** Đặt tại `large_dataset_policy` (đã là policy block, không bị D2 loader quét) — không can thiệp freeze pipeline.
- **Risk:** User thay đổi `vista_full_local_status` thành key mới → silently ignore.  
  **Mitigation:** Đã đổi sang nested dict, kèm grep-back step 3.

## Effort Breakdown

| Bước | Thời gian |
|------|-----------|
| Grep codebase để chắc không có reference cũ | 5 min |
| Patch YAML + comment | 10 min |
| Verify parse + grep 0-hit | 5 min |
| Update criterion #2 trong audit sheet | 10 min |
| **Tổng** | **~30 min** |
