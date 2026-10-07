---
phase: 3
title: "Audio Modality-Specific Figures (TED-LIUM)"
status: pending
priority: P2
effort: "4-6 hours"
dependencies: []
---

# Phase 3: Audio Modality-Specific Figures (TED-LIUM)

## Overview

Thay thế 8 SVG figures hiện đang ở dạng **stub / generic** trong `experiments/outputs/phase2_tedlium_d2/official/full/figures/` bằng các plot **audio-modality-specific** — vẽ trực tiếp từ `dataset.unit_profile.json` và `dataset.statistics.json.numeric_summary` của TED-LIUM D2. Mục tiêu đóng **deferred criterion #7** (audio modality-specific figures) bằng dữ liệu thật, không phải placeholder.

## Background & Evidence

- **Hiện trạng:** 9 file SVG đã có (đếm từ `Get-ChildItem` ngày 2026-09-25):
  - `selected-bytes-by-dataset.svg`, `tedlium3-attrition_waterfall.svg`, `tedlium3-duplicate_matrix.svg`, `tedlium3-duration_distribution.svg`, `tedlium3-file_size_distribution.svg`, `tedlium3-missingness_gt_coverage.svg`, `tedlium3-scale_bytes.svg`, `tedlium3-source_overlap.svg`, `tedlium3-split_comparison.svg`.
  - User nhắc "8 SVG stubs" — số 8 hoặc 9 không quan trọng; vấn đề là figures hiện tại **chưa audio-specific** (vd: chỉ có file_size + duration cơ bản, chưa có sample-rate / channels / bit-depth / SNR).
- **Source data thật có sẵn:**
  - `experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.unit_profile.json` — per-unit audio metadata (`duration_sec`, `sample_rate_hz`, `frames`, `channels`, `audio_sha256`, `speaker_id`, `talk_id`).
  - `experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.statistics.json` — aggregate stats (đã đọc: 20 units, file_size_bytes summary).
  - `experiments/scripts/phase2_freeze_tedlium.py:79-83` — confirm per-unit fields capture được: `duration_sec`, `sample_rate_hz`, `frames`, `channels`.
- **Pattern re-use:** `experiments/scripts/profile_dataset.py` đã có sẵn matplotlib/SVG plotting path (8 figures đã được generate qua nó). Phase 3 chỉ cần thêm 4-6 figure generator mới, không cần infra mới.

## Implementation Steps

1. **Viết `experiments/scripts/figures/audio_modality_plots.py`** — module generator 4-6 figures audio-specific. Mỗi function nhận vào `dataset.unit_profile.json` (list of dicts) + output dir, return None. Pattern theo profile_dataset hiện hữu (matplotlib backend `svg`, savefig với metadata).
   ```python
   def plot_duration_histogram_ecdf(units, out_dir) -> Path
   def plot_sample_rate_sanity(units, out_dir) -> Path      # constant 16kHz check
   def plot_channels_sanity(units, out_dir) -> Path          # constant mono
   def plot_frames_vs_duration_scatter(units, out_dir) -> Path
   def plot_speaker_distribution(units, out_dir) -> Path
   def plot_audio_bytes_per_speaker_stacked(units, out_dir) -> Path
   ```

2. **Mỗi figure phải thỏa 3 nguyên tắc:**
   - **Real data only** — không dùng synthetic placeholder; đọc từ `dataset.unit_profile.json` thật.
   - **Reproducibility** — set `matplotlib.use("Agg")`, `np.random.seed(0)`, không gọi external API.
   - **No-PII** — chỉ plot speaker-level aggregate (`n_speakers`, total_duration_per_speaker); không plot waveform của từng speaker cá nhân.

3. **Tích hợp vào `phase2_freeze_tedlium.py` driver:** thêm 1 dòng sau step 4 (`profile_dataset.main()`):
   ```python
   from experiments.scripts.figures.audio_modality_plots import (
       plot_duration_histogram_ecdf, plot_sample_rate_sanity, ...
   )
   figs_dir = artifact_root / "official" / "full" / "figures"
   for fn in [plot_duration_histogram_ecdf, plot_sample_rate_sanity,
              plot_channels_sanity, plot_frames_vs_duration_scatter,
              plot_speaker_distribution, plot_audio_bytes_per_speaker_stacked]:
       fn(units, figs_dir)
   ```
   Hoặc nếu muốn module độc lập, tạo CLI `python -m experiments.scripts.figures.audio_modality_plots --unit-profile ... --out ...`.

4. **Update `dataset.figure_manifest.json`** — thêm entries cho 4-6 figures mới với `kind: audio_modality_specific`, `source_payload: dataset.unit_profile.json`, `generator: figures.audio_modality_plots.<fn>`.

5. **Smoke verify:** Render từng figure, mở bằng Pillow hoặc trình duyệt để chắc không có lỗi layout (label overlap, axis range sai, etc.).

6. **Document trong `dataset.eda_report.md`** (do profile_dataset emit) — bổ sung 1 đoạn "Audio Modality Sanity Checks" liệt kê các figures mới + 1 dòng kết luận (vd: "All 20 units: 16kHz mono consistent; duration distribution matches TED-talk length profile; speaker count balanced across val/test.").

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/scripts/figures/__init__.py` (package init)
  - `multimodal-lecture-summarizer/experiments/scripts/figures/audio_modality_plots.py`
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_tedlium.py` (call figures module sau step 4)
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.unit_profile.json`
  - `multimodal-lecture-summarizer/experiments/scripts/profile_dataset.py` (matplotlib pattern)

## Success Criteria

- [ ] ≥ 4 SVG figures mới trong `experiments/outputs/phase2_tedlium_d2/official/full/figures/` với prefix `tedlium3-audio-`.
- [ ] Mỗi figure có metadata trong `dataset.figure_manifest.json` với `kind: audio_modality_specific`.
- [ ] `plot_sample_rate_sanity` xác nhận tất cả 20 units = 16 kHz (TED-LIUM spec).
- [ ] `plot_channels_sanity` xác nhận tất cả 20 units = mono.
- [ ] `plot_duration_histogram_ecdf` có cả histogram + ECDF trong cùng 1 SVG (2 subplot).
- [ ] `dataset.eda_report.md` có section "Audio Modality Sanity Checks" mới.
- [ ] Re-running `phase2_freeze_tedlium.py` vẫn pass + output SHA-256 của các figures audio-specific ổn định (deterministic).

## Risk Assessment

- **Risk:** Plot matplotlib với sample size 20 units → histogram trống / ít bin.  
  **Mitigation:** Dùng ECDF thay vì histogram cho sample nhỏ; hoặc chọn bin width thông minh (Freedman-Diaconis hoặc Scott's rule).
- **Risk:** Speaker-level plot có thể vô tình tiết lộ PII nếu plot per-speaker waveform.  
  **Mitigation:** Đã giới hạn ở aggregate (count, total duration); plot kiểu bar chart, không plot audio signal.
- **Risk:** `matplotlib.use("Agg")` backend có thể không produce SVG đúng nếu môi trường headless chưa set font cache.  
  **Mitigation:** Pin matplotlib version; dùng `matplotlib.rcParams["svg.fonttype"] = "none"` để tránh embed font.
- **Risk:** Phase 3 chạm `phase2_freeze_tedlium.py` (đã freeze xong) — có thể vô tình re-emit artifacts và đổi SHA-256.  
  **Mitigation:** Document SHA-256 delta trước/sau; coi là expected delta (figures mới được thêm).

## Effort Breakdown

| Bước | Thời gian |
|------|-----------|
| Khảo sát `dataset.unit_profile.json` schema | 30 min |
| Viết `audio_modality_plots.py` (6 functions) | 2-3 giờ |
| Tích hợp vào driver + test render | 1 giờ |
| Update figure_manifest + eda_report | 30 min |
| Manual review figures (label, axis, layout) | 1 giờ |
| **Tổng** | **4-6 giờ** |

## Parallelization Note

Có thể chạy song song với **Phase 2** (IIIT-CVID D2 freeze) vì:
- Độc lập dataset (TED-LIUM vs IIIT-CVID).
- Độc lập code path (`figures/` package mới vs `iiit_cvid_d2.yaml` + clone driver).
- Cùng chạy trên local_rtx4050_6gb profile (light).
- Lý do duy nhất cần serialize là nếu cả hai cùng touch `research_decisions.yaml` — Phase 2 step 5 làm điều đó. Workaround: Phase 3 chỉ đụng `figure_manifest.json`, không đụng `research_decisions.yaml`, nên hoàn toàn parallel-safe.
