---
phase: 5
title: "First Real Benchmark for Downstream Tasks"
status: pending
priority: P1
dependencies: ["phase-04-phase-04-endpoint-matrix-expansion"]
effort: "2-3 days"
---

# Phase 5: First Real Benchmark for Downstream Tasks

> **SCOPE REVISION 2026-09-26 (user-confirmed, sau khi Phase 3 cancelled).**
> - Chi **1 downstream benchmark**: `02c_ocr_benchmark` tren IIIT-CVID (1755 frames).
> - **Da remove** 5.2 `06a_retrieval_benchmark` va 5.3 `06b_qa_generation_benchmark`
>   (phu thuoc EduViQA -> da cancel).
> - ASR benchmark (TED-LIUM) **khong chay lai** -- da co real benchmark tu plan
>   `260925-2304-d2-frozen-gt-runners`. Phase nay chi chung minh OCR path chay duoc
>   tren dataset D2 thu hai voi 1755 units.
> - `run_ocr_benchmark.py` da ton tai tai `benchmarks/scripts/run_ocr_benchmark.py` (verified 2026-09-26).
> - **Open question con lai (Open Question #5 cua plan.md):** compute profile.
>   Phase nay chay `--profile full` tren local. Neu 1755 frames qua thoi gian
>   (uoc tinh 15-40 phut voi 1 OCR candidate) thi escalate user ve cap nhat
>   `--profile smoke` + cap nhat expected unit count.

## Overview

Sau khi endpoint matrix co 2 eligible endpoints (`asr_benchmark`, `ocr_benchmark`), chay
**first real benchmark** cho `ocr_benchmark` (chua co official benchmark truoc do) de chung minh
pipeline khong bi stuck o "runner exists nhung khong co data". Muc tieu: raw prediction artifact
+ per-unit metric + aggregate + shortlist receipts cho 1755 IIIT-CVID frames. Phase nay **khong**
thuc hien multi-candidate bake-off (do la Phase 4 master plan -- out of scope HOLD).

## Requirements

- **Functional**: 1 first-real benchmark chay thanh cong qua
  `execute_all_notebooks.py --notebook 02c_ocr_benchmark`:
  - `02c_ocr_benchmark` (IIIT-CVID, 1755 frames, >= 1 OCR candidate, >= 1 metric)
- **Non-functional**: Real runner execution (khong phai smoke/fixture); raw predictions co per-unit
  reference; metric la CER/WER (frame-level).
- **Contract preservation**: ASR benchmark (TED-LIUM) khong bi touch -- 25/25 payload SHA phai
  giong baseline da ghi lai truoc khi sua code.

## Architecture

First-real benchmark theo pattern:

```
execute_all_notebooks.py --artifact-root experiments/outputs/phase2_iiit_cvid_d2 \
    --profile full --run-namespace official --notebook 02c_ocr_benchmark
  -> manifest.load_notebook("02c_ocr_benchmark")
  -> load_eligible_units(context)          # reads endpoint_matrix from phase2_iiit_cvid_d2
  -> run_ocr_benchmark.py --profile full --run-namespace official
  -> output:
     - ocr.raw_predictions.json   (per-unit reference + prediction)
     - ocr.per_unit_metrics.json  (per-unit CER/WER)
     - ocr.aggregate.json         (corpus_cer, corpus_wer)
     - ocr.shortlist.json         (ranked candidates)
     - ocr.frozen_configuration.json
```

**Luu y cho Phase 5:**
- Chi chay 1 candidate dau tien (khong bake-off). Day la proof-of-concept pipeline end-to-end.
- Compute profile: `local` (RTX4050 6GB / CPU fallback) -- 1 OCR candidate classical khong can GPU.
- Reference text = frame-level `reference_text` da freeze o Phase 1 (newline-joined text lines).

## Related Code Files

- **Read-only references:**
  - `multimodal-lecture-summarizer/benchmarks/scripts/run_ocr_benchmark.py`
  - `multimodal-lecture-summarizer/experiments/scripts/stage_benchmark_helpers.py:load_eligible_units`
  - `multimodal-lecture-summarizer/experiments/notebooks/notebook_manifest.yaml` (entry `02c_ocr_benchmark`)
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/registry/candidates.yaml` (ensure `ocr_benchmark` has >= 1 candidate)
- **Create:**
  - `multimodal-lecture-summarizer/tests/test_first_real_benchmark_downstream.py`
  - `plans/260926-1416-unlock-9-downstream-tasks/journal.md`

## Implementation Steps

### 5.1 OCR first-real benchmark (IIIT-CVID, 02c_ocr_benchmark)

1. **Verify OCR candidate availability** (khong assume `pytesseract` co san):
   ```bash
   python -c "import pytesseract, pytesseract as p; print(p.get_tesseract_version())"
   python -c "import easyocr; print('easyocr ok')"
   python -c "import paddleocr; print('paddleocr ok')"
   tesseract --version
   ```
   Baseline `outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json` cho biet
   `paddle_recognition_only` (mean_cer 0.2369) va `paddle_full` (mean_cer 0.8362) da chay duoc
   truoc do; `easyocr` **fail** voi `WinError 127` (shm.dll). Uu tien paddleocr > tesseract > easyocr.

2. **Inspect `run_ocr_benchmark.py` input contract**:
   - Xac nhan runner doc `media_path` + `reference_text` tu `unit_records` (khong phai `text`).
   - Xac nhan runner xuat `ocr.raw_predictions` / `ocr.per_unit_metrics` / `ocr.aggregate` /
     `ocr.shortlist` / `ocr.frozen_configuration` (5 artifacts nhu ASR pattern).
   - Xac nhan metric nao duoc dung (CER/WER) va normalizer co frozen chua.

3. **Ensure `candidates.yaml` co `ocr_benchmark` candidate** (doc schema truoc khi viet):
   ```bash
   grep -B2 -A 12 "ocr_benchmark" experiments/registry/candidates.yaml
   ```
   Neu chua co, them 1 candidate theo **schema that cua file** (do la registry-owned contract,
   khong copy-paste blind). Baseline candidate de xuat: `ocr.paddleocr_recognition_only`
   (da chay duoc trong prior eval), `compute_budget.max_latency_ms` uoc luong 150 ms/image.

4. **Run 02c OCR benchmark**:
   ```bash
   cd multimodal-lecture-summarizer
   python -m benchmarks.scripts.execute_all_notebooks \
     --artifact-root experiments/outputs/phase2_iiit_cvid_d2 \
     --profile full --run-namespace official \
     --notebook 02c_ocr_benchmark
   ```
   Verify output:
   - `ocr.raw_predictions.json` co **1755** records (1 per unit), moi record co `reference` + `prediction`.
   - `ocr.per_unit_metrics.json` co **1755** records voi CER + WER per unit.
   - `ocr.aggregate.json` co `corpus_cer`, `corpus_wer`, `unit_count=1755`.
   - `ocr.shortlist.json` co rank 1 candidate.
   - `ocr.frozen_configuration.json` co model + toggle info.

### 5.2 ~~Retrieval first-real benchmark (EduViQA)~~ -- REMOVED (Phase 3 cancelled)

### 5.3 ~~QA first-real benchmark (EduViQA)~~ -- REMOVED (Phase 3 cancelled)

### 5.4 Tests + journal

1. **Tests** `tests/test_first_real_benchmark_downstream.py` (>= 4 tests):
   - `test_ocr_raw_predictions_1755_units`: 1755 records, all co `reference` + `prediction` fields.
   - `test_ocr_aggregate_finite_metrics`: `corpus_cer`, `corpus_wer` la so finite, khong phai None/NaN.
   - `test_ocr_per_unit_metrics_cover_all_units`: 1755 per-unit metric records, `unit_id` khop 1-1
     voi raw predictions.
   - `test_asr_tedlium_payloads_unchanged`: 7 ASR payload SHA giong baseline (regression guard --
     ASR khong bi touch).

2. **Journal entry** (`plans/260926-1416-unlock-9-downstream-tasks/journal.md`):
   - Summary OCR first-real benchmark result.
   - Bang: endpoint x dataset x candidate x primary metric x unit count.
   - So sanh voi prior 200-image baseline (paddle_recognition_only mean_cer 0.2369 / mean_wer 0.565)
     -- **chi de reference**, khong phai so sanh apples-to-apples (frame-level 1755 vs line-level 200).
   - Open issues: chi 1 candidate/endpoint; EduViQA cancelled; SlideVQA/TVSum la D3 candidates.
   - Next steps: Phase 3 master plan (candidate expansion).

## Success Criteria

- [ ] `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/ocr.{raw_predictions,per_unit_metrics,aggregate,shortlist,frozen_configuration}.json` deu ton tai voi **1755** units.
- [ ] `ocr.aggregate.json` co `corpus_cer` + `corpus_wer` finite va `unit_count=1755`.
- [ ] `ocr_benchmark` co >= 1 candidate trong `candidates.yaml` voi `family`, `model_class`, `compute_budget`, `eligibility_reason`.
- [ ] `load_eligible_units` cho `02c_ocr_benchmark` tra ve 1755 units (khong con RuntimeError).
- [ ] `tests/test_first_real_benchmark_downstream.py` PASS >= 4/4.
- [ ] Journal entry viet xong voi bang summary.
- [ ] **ASR benchmark (TED-LIUM) 25/25 payload SHA-256 khong doi.**

## Risk Assessment

- **Risk:** OCR runner can thu vien Tesseract (`pytesseract` + `tesseract-ocr` system binary) chua
  co tren env.
  **Mitigation:** Verify truoc bang lenh o step 1. Neu chua co -> fallback sang candidate co san
  (paddleocr theo prior baseline). Neu ca hai deu fail -> escalate user, ghi
  `blocked: no OCR candidate available` va dung phase.
- **Risk:** 1755 frames x 1 OCR candidate uoc tinh 15-40 phut tren local CPU.
  **Mitigation:** Timeout 90 phut. Neu timeout -> escalate user chuyen sang `--profile smoke` va
  cap nhat expected unit count (khong giu 1755 claim).
- **Risk:** `network_used=false` contract -- neu OCR candidate tai model tu internet se vi pham.
  **Mitigation:** Chon candidate voi weights da local, hoac pre-download weights vao
  `experiments/datasets/hf_cache`; verify `network_used=false` trong receipts.
- **Risk:** Aggregate metric rat cao (CER > 1) neu reference_text frame-level ghep nhieu dong
  trong khi OCR doc theo tung line.
  **Mitigation:** Ghi ro trong journal "first-real benchmark la proof-of-concept, khong phai SOTA
  claim"; line-level 40,103 crops la D3 candidate cho accurate OCR scoring.
- **Risk:** Runner co the expect `media_path` cua audio/WAV thay vi PNG.
  **Mitigation:** `phase2_freeze_iiit_cvid.py` da set `media_path` = absolute PNG path trong
  `unit_records`; verify `run_ocr_benchmark.py` doc `media_path` + `reference_text` keys
  (khong phai `text`).

## Out of Scope (Reiteration)

Phase 5 KHONG lam:
- ~~Retrieval / QA first-real benchmark~~ (Phase 3 cancelled).
- Multi-candidate bake-off (Phase 4 master plan -- candidate expansion).
- Statistical analysis (paired permutation, Holm correction, Pareto -- Phase 5 master plan).
- Cross-stage compatibility matrix (Phase 6 master plan).
- End-to-end system validation (Phase 7 master plan).
- SOTA claims hoac leaderboard ranking (chi la proof-of-concept pipeline chay duoc).

## Effort Breakdown (revised)

| Step | Time |
|------|------|
| Verify + extend `candidates.yaml` (OCR endpoint) | 0.5-1 g |
| Verify OCR candidate deps (paddleocr/tesseract/easyocr) | 0.5-1 g |
| Inspect `run_ocr_benchmark.py` input/output contract | 0.5 g |
| OCR first-real benchmark run (1755 frames) | 2-4 g (chay + debug) |
| Tests + journal + regression | 1-2 g |
| **Tong** | **4.5-8.5 g** |
