---
phase: 1
title: "IIIT-CVID D2 Freeze"
status: completed
priority: P1
dependencies: []
effort: "1-2 days"
completed: 2026-09-26
---

# Phase 1: IIIT-CVID D2 Freeze

## Overview

Đưa IIIT-CVID (lecture video OCR corpus từ CVIT IIIT Hyderabad) từ "D1 raw on disk" lên **D2 frozen subset** với toàn bộ **1755 annotated test frames**, license adjudicated, full 00a/00b/00c artifact chain. Kết quả là dataset eligible thứ hai của pipeline, mở khóa OCR endpoint (và đóng criterion #5 master plan Phase 2: "each eligible task has labeled dataset").

> **CORRECTION 2026-09-26 (verified against disk, supersedes original spec).**
> Plan gốc nói "200 ảnh". Đã verify: con số 200 là `max_samples` cap của prior OCR eval
> (`outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json`), **không phải** dataset size.
> Sự thật trên disk:
> - `IIIT-CVid/Frames/test/` = **1755 PNG + 1755 XML** (1:1), 7 course dirs: 3, 7, 10, 14, 18, 20, 24.
> - `frames-test-img.txt` = 1755 dòng `<relpath>.xml` → authoritative index.
> - `IIIT-CVid/Crops/test/` = **40,103 line crops** + `test.txt` (40,103 dòng path→label) + per-course `Id-Label.txt`/`type.txt`.
> - **Ground truth thật**: mỗi frame có XML Pascal-VOC, mỗi `<object>` là 1 text line với
>   `<bndbox>` + `<name>` = transcription. Đây là format chuẩn LectureVideoDB/mmocr.
>   `lexicon.txt`/`vocab.txt` chỉ là vocabulary cho constrained decoding, **không phải** GT.
> - XML thuần, **không có zero-width space**. (Plan gốc claim U+200B trong thẻ `<filename>` —
>   claim sai, do PowerShell console render artifact khi inspect file. Đã verify:
>   **0/1755 file chứa byte `E2 80 8B`**, và `ElementTree` parse ra tag `filename` sạch.
>   Không viết code strip zero-width — đó là dead code.)
>
> **Quyết định granularity (user-confirmed 2026-09-26): frame-level.**
> Mỗi unit = 1 frame; `reference_text` = text lines của frame đó ghép lại (newline-joined,
> sort theo (ymin, xmin) để deterministic). Scored bằng frame-level CER/WER.
> Lý do: khớp trực tiếp với `frames-test-img.txt` (official index), 1:1 với PNG trên disk,
> và vẫn comparable với prior 200-image baseline (line-level crops) vì cùng nguồn GT.
> Line-level (40,103 crops) bị defer vì khối lượng verify quá lớn cho phase này.
>
> **CORRECTION 2026-09-26 (runtime, supersedes "1755 units" ở Requirements/Acceptance).**
> Plan gốc giả định 1755 frames là đủ. Chạy driver thật thì **fail**:
> `dataset_contracts._validate_frozen_manifest` (line ~411) yêu cầu mọi D2 freeze phải có
> **CẢ HAI** split `validation` + `final_test` — đúng về mặt khoa học, vì cần validation để
> tune decoding params mà không đụng test set. Và
> `_reject_validation_test_leakage` (line ~179) track `unit_id`, `sha256`, `speaker_id`,
> `talk_id`, nên split boundary **không được cắt qua course (speaker) hay video (talk)**.
>
> May mà IIIT-CVID ship official train/test splits **disjoint hoàn toàn**:
> - `frames-train-img.txt` = 3171 rows, courses {1,4,5,8,9,12,15,16,17,21,22,23}
> - `frames-test-img.txt`  = 1755 rows, courses {3,7,10,14,18,20,24}
> - **course overlap = 0, video overlap = 0**
>
> Nên thiết kế cuối cùng (đã implement + verify):
> - `final_test`  = **toàn bộ 1755 frames** của official test split (7 courses, 276 videos)
> - `validation`  = **360 frames** lấy từ official train split, stratified **30 frames/course
>   × 12 courses**, chọn bằng ascending sha256 của relative path (deterministic, order-independent)
> - Tổng frozen = **2115 units**. Official test split bị consume **trọn vẹn, không cắt bớt** —
>   đây là dạng mạnh nhất của reported OCR number.
>
> Split naming: contract chỉ nhận `{train, validation, final_test}`. Source split `"test"` của
> IIIT-CVID map sang `final_test` (giống hệt cách TED-LIUM driver map source `test` → `final_test`),
> giữ `original_split` để provenance.
>
> **Cross-validation mạnh (đã assert trong test):** 40,103 text lines trích từ
> `<object><name>` của 1755 test frames **= đúng bằng** số crop trong `Crops/test/` (40,103 PNG,
> đếm bằng `rglob` vì nested theo course). Hai con số do dataset author tạo độc lập → xác nhận
> parser GT đúng. Validation frames đóng góp thêm 8,412 lines (tổng 48,515).
>
> **Endpoint name**: canonical là `ocr_benchmark` (không phải `ocr`). Xem `_NOTEBOOK_TO_ENDPOINTS`
> trong `experiments/scripts/stage_benchmark_helpers.py:02c_ocr_benchmark → {ocr_benchmark, ocr}`.

## Requirements

- **Functional**: IIIT-CVID frozen manifest + D2 bundle validator pass; `ocr_benchmark` endpoint eligible_d2 với **2115** units (`final_test`=1755 official test frames + `validation`=360 từ official train split).
- **Non-functional**: Re-use prior OCR baseline numbers (không chạy OCR model mới ở phase này); license adjudicated trước freeze; pattern clone 1-1 từ TED-LIUM driver.
- **Contract preservation**: TED-LIUM artifacts SHA-256 không đổi (25/25 payload SHA baseline đã ghi lại trước khi sửa code); `research_decisions.yaml` `next_target.iiit_cvid` được mark complete.

## Architecture

Clone pattern từ `phase2_freeze_tedlium.py`:
1. `_build_inventory_from_disk` đổi decoder từ `soundfile.info()` → `PIL.Image.open()` + `.verify()` (width/height/mode/checksum).
2. Parse GT từ XML: `xml.etree.ElementTree`, duyệt `.//object`, lấy `name` (text) + `bndbox`. XML sạch, **không cần** strip zero-width chars (đã verify 0/1755 file chứa U+200B).
3. `unit_id` scheme: `{canonical_split}:{course_id}:{video_id}:{frame_stem}` (deterministic, unique — frame stem là `hh_mm_ss_counter` nên unique trong mỗi video). `final_test:*` cho test frames, `validation:*` cho train frames.
4. `extension_counts` → `.png`.
5. `split_counts` → `final_test`=1755 (toàn bộ official test split) + `validation`=360 (30/course × 12 official train courses).
6. **Hook vào `profile_dataset.py`**: driver không tự viết endpoint matrix. `profile_dataset.py` hiện **hardcode** `endpoint: "asr_benchmark"` cho mọi D2 dataset (line ~642) → phải sửa thành config-driven, default = giá trị hiện tại để TED-LIUM không đổi byte.
7. `reference_text` cho mỗi unit = các text line trong XML ghép bằng `\n`, sort deterministic theo `(ymin, xmin)`.
8. Output namespace: `experiments/outputs/phase2_iiit_cvid_d2/official/full/`.

License adjudication:
- Source: `experiments/datasets/iiit_cvid/provenance.json` — `hf_dataset: staghado/IIIT-CVid`, `zip_sha256: b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489`, `zip_size_bytes: 2427254987`, `downloaded_at: 2026-08-29T13:31:08`.
- **Rights string trong provenance.json bị mojibake**: `"academic_research_only �?" verify with CVIT IIIT Hyderabad before redistribution"`. Phải viết lại chuẩn UTF-8 trong `iiit_cvid_d2.yaml`.
- Decision: chỉ publish aggregate metrics (CER/WER), không re-host raw images trong paper.

## Related Code Files

- **Create:**
  - `multimodal-lecture-summarizer/experiments/registry/datasets/iiit_cvid_d2.yaml`
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_iiit_cvid.py`
  - `multimodal-lecture-summarizer/experiments/scripts/emit_iiit_cvid_image_figures.py`
  - `multimodal-lecture-summarizer/tests/test_unlock_iiit_cvid_d2.py`
- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/scripts/phase2_freeze_tedlium.py` (pattern to clone verbatim)
  - `multimodal-lecture-summarizer/experiments/scripts/probe_dataset_feasibility.py:_load_d2_config`
  - `multimodal-lecture-summarizer/experiments/evaluation/dataset_contracts.py:validate_dataset_characterization_bundle` (endpoint_record chỉ được có đúng 5 keys)
  - `multimodal-lecture-summarizer/experiments/datasets/iiit_cvid/provenance.json`
  - `multimodal-lecture-summarizer/experiments/datasets/iiit_cvid/IIIT-CVid/frames-test-img.txt` (authoritative 1755-row index)
  - `multimodal-lecture-summarizer/outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json` (prior baseline: paddle_recognition_only mean_cer 0.2369 / mean_wer 0.565 @ 200 imgs)
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/scripts/profile_dataset.py` (**config-driven endpoint + reason + gt_status; default phải giữ nguyên giá trị hiện tại để TED-LIUM SHA không đổi**)
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml` (mark `next_target.iiit_cvid` complete)

## Implementation Steps

1. **Khảo sát cấu trúc IIIT-CVID thực tế** — **ĐÃ XONG 2026-09-26**:
   - `Frames/test/` = 1755 PNG + 1755 XML, 7 course dirs (3, 7, 10, 14, 18, 20, 24)
   - `frames-test-img.txt` = 1755 dòng, format `test/{course}/{video}/{hh_mm_ss_counter}.xml`
   - `Crops/test/` = 40,103 crops; `test.txt` = 40,103 dòng `Crops/test/{c}//{v}/{n}.png {label}`
   - XML `<object><name>` = transcription; `<filename>` chứa zero-width space (U+200B)
   - `metadata.txt` mỗi video dir có ffprobe output (320x240, 25 FPS, 1ch 22.05 kHz)

2. **Sửa `profile_dataset.py` thành config-driven** (nhằm giữ nguyên TED-LIUM output):
   - `endpoint_matrix` entry: `endpoint` ← `d2_cfg.get("endpoint", "asr_benchmark")`,
     `reason` ← `d2_cfg.get("eligibility_reason", <reason hiện tại>)`
   - `frozen_scope` `reason` ← `d2_cfg.get("freeze_reason", <reason hiện tại>)`
   - `gt_status` ← `d2_cfg.get("ground_truth_status_label", "released_manual_transcripts_CC_BY_NC_ND_3.0")`
   - **Không** thêm key mới vào endpoint_record (validator `_reject_extra_keys` → chỉ đúng 5 keys).
   - **Không sửa** `tedlium3_d2.yaml` → default đã bằng giá trị cũ nên SHA không đổi.

3. **Tạo `experiments/registry/datasets/iiit_cvid_d2.yaml`** theo schema `_load_d2_config`:
   ```yaml
   schema_version: 1
   dataset_id: iiit_cvid
   source: "local_extracted_zip"
   release: "iit_cvid_release_2018"
   revision: "iit-cvid-snapshot-b5b56258"
   local_snapshot_fingerprint: "b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489"

   rights: "academic_research_only - verify with CVIT IIIT Hyderabad before redistribution; aggregate metrics only, no raw image re-hosting"
   access_status: "available"
   leakage_exception: null

   data_root_key: "experiments/datasets/iiit_cvid"
   receipt_path: "datasets/iiit_cvid/official/full/payloads/dataset.feasibility_receipts.json"

   endpoint: "ocr_benchmark"
   ground_truth_status_label: "released_manual_frame_transcriptions_academic_research_only"
   freeze_reason: "D2 freeze: 2115 frame-level units - complete official test split (1755 frames, 7 courses, 276 videos) as final_test + 360-frame stratified validation sample from the disjoint official train split (30 frames x 12 courses). Manual per-line transcriptions, academic_research_only rights adjudicated 2026-09-26, 100% decode, leakage adjudicated (official train/test splits share zero courses and zero videos; sha256 identity; no exact duplicates)"
   eligibility_reason: "D2 freeze: final_test is the complete official frames-test-img.txt test split (1755 indexed frames, 1:1 with PNG and Pascal-VOC XML) and validation is drawn from the disjoint official train split, so decoding parameters can be tuned without touching the reported test set. 48,515 manual text lines extracted from XML object names; the 40,103 final_test lines match the Crops/test line-crop count exactly. academic_research_only; no exact duplicates; no validation/final_test speaker_id or talk_id overlap"

   expected_bytes: 540960433   # measured: 400,763,111 (1755 test PNG) + 140,197,322 (360 train PNG)
   predicted_peak_bytes: 1622881299   # expected_bytes * 3
   estimated_completion_hours: 0.5

   min_schema_success_rate: 1.0
   min_checksum_success_rate: 1.0
   min_download_success_rate: 1.0
   min_decode_success_rate: 0.95

   ground_truth:
     status: "released"
     source: "IIIT-CVid official - manual per-line transcriptions in Pascal-VOC XML under Frames/{test,train}"
     revision: "iit_cvid_release_2018"
     annotation_protocol: >
       Per text line bndbox, <object><name> holds the manual transcription.
       Frame-level reference_text concatenates lines sorted by (ymin, xmin).
       48,515 lines total; the 40,103 final_test lines equal the Crops/test
       line-crop count exactly, which cross-validates the extraction.
       Scored with corpus CER/WER using a frozen English text normaliser.
       lexicon.txt + vocab.txt provide constrained-decoding vocabulary only.

   fallback_dataset: null
   ```

4. **Viết `phase2_freeze_iiit_cvid.py`** (clone từ `phase2_freeze_tedlium.py`):
   - `DATASET_ROOT = .../datasets/iiit_cvid/IIIT-CVid`
   - Đọc `frames-test-img.txt` + `frames-train-img.txt` làm index (không glob toàn bộ files)
   - Với mỗi dòng `{split}/{c}/{v}/{stem}.xml` → media = `Frames/{split}/{c}/{v}/{stem}.png`, gt = XML cùng tên
   - Decode: `PIL.Image.open(p)` → `im.size`, `im.mode`, `im.verify()`; `decoded=True`, `probe_status="pil_decoded"`
   - SHA-256 của PNG
   - `unit_id = f"{canonical_split}:{c}:{v}:{stem}"`
   - `text` = newline-joined transcriptions (hook `reference_text` trong `profile_dataset.py`)
   - `speaker_id = f"course_{c}"`, `talk_id = f"{c}_{v}"` (tương đương vai trò course/video)
   - Validation selection: group train rows theo course, sort ascending `sha256(relative_path)`, lấy 30/course
   - Expected counts: raise RuntimeError nếu lệch (`test`=1755, `validation`=360, total=2115)
   - Verify cuối: 1 record eligible, `unit_ids.length == 2115`, `final_test`=1755, `validation`=360, **mọi** `reference_text` non-empty, endpoint == `ocr_benchmark`, leakage 0

5. **Run driver**:
   ```bash
   cd multimodal-lecture-summarizer
   python -m experiments.scripts.phase2_freeze_iiit_cvid \
     --artifact-root experiments/outputs/phase2_iiit_cvid_d2
   ```
   Verify:
   - `dataset.frozen_manifest.json`: 1 record `freeze_status=eligible`, `unit_ids.length == 2115`, `scientific_selection_eligible=true`
   - `dataset.profile.json`: `acquisition_level=D2`
   - `dataset.leakage_audit.json`: `exact_overlap_count=0`
   - `dataset.endpoint_matrix.json`: `iiit_cvid × ocr_benchmark → eligible_d2`

6. **Sinh image-specific figures** (`emit_iiit_cvid_image_figures.py`, ≥ 3):
   resolution distribution, aspect-ratio distribution, PIL mode histogram, + text-line density (OCR workload driver) = **4 figures**. Mỗi figure + companion `.json` sidecar (`source_table_sha256`, `image_geometry_sha256`, `code_revision`, `plotting_config`, `split_unit_counts`).

   > **Contract constraint (discovered khi implement, quan trọng):**
   > `dataset_contracts` **recompute** `source_table_sha256` từ `source_artifact` mà record khai
   > (line ~760), và chỉ cho phép 6 artifact: `dataset.statistics`, `dataset.split_statistics`,
   > `dataset.quality_issues`, `dataset.attrition`, `dataset.leakage_audit`,
   > `dataset.cross_dataset_comparison`. Ngoài ra `n` **phải bằng** `len(dataset_units)` = 2115
   > (line ~719), **không** phải 1755 như plan gốc ghi.
   > Vì geometry không nằm trong 6 artifact đó, đã thêm block `image_geometry` vào
   > `dataset.statistics` (chỉ khi inventory có raster metadata → **TED-LIUM không đổi byte**,
   > verify 25/25). Image figures khai `source_artifact="dataset.statistics"`; sidecar giữ thêm
   > `image_geometry_sha256` làm provenance thật của đúng bảng dữ liệu vẽ ra.

7. **Reuse prior OCR baseline numbers**: đọc `outputs/official_ocr_slide_text_evaluation/lecturevideodb_ocr_summary.json` làm evidence trong journal (không ghi vào statistics để tránh lẫn metric của run mới).

8. **Update `research_decisions.yaml`**: mark `next_target` iiit_cvid completed + evidence path.

9. **Smoke regression** (BẮT BUỘC): re-run `phase2_freeze_tedlium.py`, so SHA-256 cả 25 payload với baseline đã ghi → phải **identical**.

10. **Tests** `tests/test_unlock_iiit_cvid_d2.py` (≥ 5 tests):
    - `test_iiit_cvid_d2_yaml_schema_valid`: parse YAML qua `_load_d2_config("iiit_cvid")`
    - `test_iiit_cvid_inventory_builder_1755_units`: build inventory từ disk → 1755 records, `decode_success_rate == 1.0`
    - `test_iiit_cvid_xml_gt_parsed_nonempty`: mọi frame có ≥ 1 text line; `reference_text` non-empty
    - `test_iiit_cvid_zero_width_tag_handled`: XML parser chịu được thẻ `filename` có U+200B
    - `test_iiit_cvid_endpoint_matrix_ocr_eligible`: matrix có `iiit_cvid × ocr_benchmark → eligible_d2`
    - `test_tedlium_payloads_unchanged`: 25 SHA baseline khớp (regression guard)

## Success Criteria

- [x] `experiments/registry/datasets/iiit_cvid_d2.yaml` parse thành công qua `_load_d2_config("iiit_cvid")`.
- [x] `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.frozen_manifest.json` có 1 record `freeze_status=eligible`, `unit_ids.length == 2115` (`final_test`=1755 + `validation`=360), `scientific_selection_eligible=true`, mọi `unit_records[].reference_text` non-empty.
- [x] 8 universal figures (từ `write_d2_universal_figures`) + 4 image-specific figures được render → `dataset.figure_manifest.json` có **12** entries, mỗi image figure có sidecar `.json`.
- [x] `acquisition_level: D2` xuất hiện trong cả registry record và frozen_manifest record.
- [x] `dataset.leakage_audit.json` cross-dataset leakage = 0.
- [x] `dataset.endpoint_matrix.json` có entry `iiit_cvid × ocr_benchmark → eligible_d2`, `scientific_selection_eligible=true`.
- [x] Regression: **25/25** TED-LIUM payload SHA-256 không đổi sau khi sửa `profile_dataset.py` + `dataset_profile_helpers.py` + `dataset_profile_schema.json`.
- [x] Contract pass end-to-end sau khi append image figures: `validate_dataset_characterization_bundle` → `d2_figure_count=12`, `unit_count=2115`, `d2_eligible_dataset_count=1`.
- [x] `tests/test_unlock_iiit_cvid_d2.py` PASS **12/12** (≥ 5 yêu cầu).
- [ ] `research_decisions.yaml.phase2_dataset_execution.next_target.iiit_cvid.status` = `completed` (deferred sang Phase 4 aggregate, cùng endpoint matrix).

## Risk Assessment

- **Risk (đã xử lý):** 200 ảnh không phải dataset size → đã sửa thành official test split 1755 frames. Line-level 40,103 crops defer.
  **Mitigation:** Ghi rõ trong YAML + journal rằng D2 freeze là **frame-level, final_test = toàn bộ 1755 official test frames**; line-level (40,103 crops) là D3 candidate.
- **Risk (đã phát hiện khi chạy, đã xử lý):** contract bắt buộc có cả `validation` + `final_test`; 1755 test frames đơn lẻ sẽ fail validate.
  **Mitigation:** Dùng official train split (disjoint hoàn toàn: 0 course overlap, 0 video overlap) làm nguồn `validation`, stratified 30/course × 12 courses = 360 frames. Test split consume trọn vẹn, không cắt bớt.
- **Risk (đã loại trừ):** XML có zero-width space trong `<filename>` → claim sai, do console render artifact.
  **Mitigation:** Verify byte-level: 0/1755 file chứa `E2 80 8B`; `ElementTree` parse tag `filename` sạch. **Không** viết code strip zero-width (dead code).
- **Risk (đã xử lý):** `profile_dataset.py` hardcode `asr_benchmark` cho mọi D2 → sửa thành config-driven.
  **Mitigation:** Default `.get(key, <giá trị hiện tại>)`; không sửa `tedlium3_d2.yaml`; verify 25/25 SHA sau khi sửa (đã fix thành `tests/fixtures/tedlium_d2_payload_sha256.json` + test tự động).
- **Risk (đã xử lý):** figure contract recompute `source_table_sha256` từ `source_artifact`, chỉ cho 6 artifact; geometry không có trong đó → provenance sai.
  **Mitigation:** Thêm block `image_geometry` vào `dataset.statistics` (gated theo raster metadata nên TED-LIUM không đổi byte); sidecar giữ `image_geometry_sha256` làm provenance thật. Test chống regression 25/25.
- **Risk:** License `academic_research_only` + mojibake trong provenance.json.
  **Mitigation:** Viết lại rights string sạch UTF-8 trong YAML; adjudication note ghi "no raw image redistribution, only aggregate metrics".
- **Risk (đã xử lý):** Một số frame có 0 text line → `reference_text` rỗng → fail verify.
  **Mitigation:** Pre-scan 1755 XML **trước khi** viết driver: min=2, max=85, mean=22.85, **0 frame rỗng**. Driver vẫn assert non-empty và raise nếu có frame rỗng.
- **Risk (đã xử lý):** 2115 PNG verify + SHA-256 mất thời gian hơn 20 WAV.
  **Mitigation:** PIL `.verify()` chỉ đọc header; SHA-256 stream 1 MiB block. Thực tế ~25-30 s cho toàn bộ driver.

## Effort Breakdown (revised)

| Step | Time |
|------|------|
| Khảo sát cấu trúc disk (đã xong) | 0.5 giờ |
| Sửa `profile_dataset.py` config-driven + verify TED-LIUM SHA | 1-1.5 giờ |
| Viết `iiit_cvid_d2.yaml` | 0.5-1 giờ |
| Viết `phase2_freeze_iiit_cvid.py` | 2-3 giờ |
| Run + verify 13 payloads + 8 figures | 1-1.5 giờ |
| Image-specific figures | 1-1.5 giờ |
| Regression + research_decisions | 0.5-1 giờ |
| Tests + journal | 1-1.5 giờ |
| **Tổng** | **7.5-11 giờ** |