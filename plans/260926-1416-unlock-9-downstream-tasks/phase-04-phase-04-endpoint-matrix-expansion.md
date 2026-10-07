---
phase: 4
title: "Endpoint Matrix Expansion"
status: pending
priority: P1
dependencies: ["phase-01-phase-01-iiit-cvid-d2-freeze"]
effort: "3-5 hours"
---

# Phase 4: Endpoint Matrix Expansion

> **SCOPE REVISION 2026-09-26 (user-confirmed, sau khi Phase 3 cancelled).**
>
> - Chi **2 dataset**: `tedlium3` + `iiit_cvid` (khong co `eduviqa`).
> - Tong `eligible_d2` endpoint = **2** (`asr_benchmark`, `ocr_benchmark`) — khong phai 4.
> - Dependency Phase 3 **bo**; chi con Phase 1.
> - **`load_eligible_units` KHONG can sua.** No da dung: doc
>   `dataset.endpoint_matrix` tu `context.namespace_root` (per-artifact-root), nen
>   `02c_ocr_benchmark` voi `--artifact-root .../phase2_iiit_cvid_d2` tu resolve
>   `iiit_cvid x ocr_benchmark`. Aggregator o day la **report/reconciliation artifact**,
>   khong phai dispatch mechanism. Spec goc noi nguoc lai → da sua.
> - **Endpoint names phai dung canonical** tu `_NOTEBOOK_TO_ENDPOINTS`
>   (`experiments/scripts/stage_benchmark_helpers.py`). Spec goc dung `qa_benchmark`,
>   `summary_benchmark`, `multimodal_summary_benchmark` — **khong ton tai** trong registry.
>   Canonical: `qa_generation_benchmark`, `summarization_benchmark`; va
>   `multimodal_summary_benchmark` khong co (gan nhat: metric track
>   `multimodal_summary_package` trong `metric_registry.yaml`).

## Overview

Aggregate và reconcile `dataset.endpoint_matrix.json` từ 3 D2 datasets (TED-LIUM, IIIT-CVID, EduViQA), verify eligibility flags từng endpoint xuyên suốt, đảm bảo `load_eligible_units` trong `stage_benchmark_helpers.py` chọn đúng dataset cho đúng endpoint. Đây là gate để Phase 5 có thể dispatch downstream runners thật (không còn fail-closed "no eligible units").

## Requirements

- **Functional**: Endpoint matrix có ≥ 3 entries `eligible_d2`; mỗi entry có `scientific_selection_eligible=true` khi dataset D2 frozen + GT contract match.
- **Non-functional**: Endpoint selector fail-closed (giữ behavior từ plan `260926-0849`); không cho phép 1 dataset mở eligibility cho nhiều endpoint không liên quan.
- **Contract preservation**: Existing TED-LIUM endpoint matrix entry (`tedlium3 × asr_benchmark → eligible_d2`) không đổi; IIIT-CVID/EduViQA entries là additive.

## Architecture

Workflow:

1. **Aggregate 3 endpoint matrix payloads** từ 3 dataset outputs:
   - `experiments/outputs/phase2_tedlium_d2/official/full/payloads/dataset.endpoint_matrix.json` (existing, 1 entry)
   - `experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.endpoint_matrix.json` (Phase 1 mới)
   - `experiments/outputs/phase2_eduviqa_d2/official/full/payloads/dataset.endpoint_matrix.json` (Phase 3 mới)

2. **Reconcile eligibility** theo matrix dưới (master plan `260921-1943` + dataset-specific contracts):

| Endpoint (canonical) | TED-LIUM | IIIT-CVID | Total |
|---|---|---|---|
| `asr_benchmark` | eligible_d2 | not_eligible (no audio) | 1 |
| `scene_boundary_benchmark` | not_eligible (audio-only) | not_eligible (frames only, no scene GT) | 0 |
| `keyframe_selection_benchmark` | not_eligible | not_eligible | 0 |
| `ocr_benchmark` | not_eligible (audio-only) | **eligible_d2** | 1 |
| `visual_caption_benchmark` | not_eligible | not_eligible (no multi-ref caption GT) | 0 |
| `object_detection_benchmark` | not_eligible | not_eligible (XML bndbox is TEXT-line bbox, not object class GT) | 0 |
| `multi_object_tracking_benchmark` | not_eligible | not_eligible | 0 |
| `chaptering_benchmark` | not_eligible | not_eligible | 0 |
| `chaptering_modality_ablation` | not_eligible | not_eligible | 0 |
| `summarization_benchmark` | not_eligible | not_eligible (no native reference summary) | 0 |
| `summary_evidence_evaluation` | not_eligible | not_eligible | 0 |
| `retrieval_benchmark` | not_eligible | not_eligible | 0 |
| `qa_generation_benchmark` | not_eligible | not_eligible | 0 |
| `end_to_end_system` | not_eligible | not_eligible | 0 |

**Total eligible_d2 endpoints = 2** (`asr_benchmark`, `ocr_benchmark`). 12 canonical endpoints
remain `not_eligible`, awaiting D3 datasets with released GT.

> **Luu y quan trong ve IIIT-CVID `object_detection_benchmark`:** XML co `<bndbox>` nhung
> `<object><name>` la **text transcription**, khong phai class label nen KHONG duoc coi la
> object-detection GT. Day la ly do plan goc du doan sai (compliance: fail-closed).

3. **Update `dataset.endpoint_matrix.json` cho mỗi dataset** (không sửa entry TED-LIUM ASR):
   - IIIT-CVID: thêm `iiit_cvid × ocr_benchmark → eligible_d2`, các endpoint khác → `not_eligible`.
   - EduViQA: thêm `eduviqa × qa_benchmark → eligible_d2`, `eduviqa × retrieval_benchmark → eligible_d2`, các endpoint khác → `not_eligible`.

4. **Verify `load_eligible_units` select đúng dataset**:
   ```python
   from experiments.scripts.stage_benchmark_helpers import load_eligible_units
   asr_units = load_eligible_units("asr_benchmark")        # → 20 TED-LIUM units
   ocr_units = load_eligible_units("ocr_benchmark")        # → 200 IIIT-CVID units
   qa_units = load_eligible_units("qa_benchmark")          # → 20 EduViQA units
   retrieval_units = load_eligible_units("retrieval_benchmark")  # → 20 EduViQA units
   scene_units = load_eligible_units("scene_boundary_benchmark")  # → RuntimeError "no eligible units"
   ```

5. **Create aggregate endpoint matrix**:
   - File mới: `experiments/outputs/endpoint_matrix_v2/official/full/payloads/endpoint_matrix_aggregate.json`
   - Schema:
     ```json
     {
       "schema_version": 1,
       "records": [
         {"endpoint": "asr_benchmark", "eligible_datasets": ["tedlium3"], "scientific_selection_eligible": true},
         {"endpoint": "ocr_benchmark", "eligible_datasets": ["iiit_cvid"], "scientific_selection_eligible": true},
         {"endpoint": "retrieval_benchmark", "eligible_datasets": ["eduviqa"], "scientific_selection_eligible": true},
         {"endpoint": "qa_benchmark", "eligible_datasets": ["eduviqa"], "scientific_selection_eligible": true},
         {"endpoint": "scene_boundary_benchmark", "eligible_datasets": [], "scientific_selection_eligible": false, "reason": "no D2 frozen dataset with released scene boundary GT"},
         // ... 7 endpoints not_eligible khác
       ]
     }
     ```
   - Update `validate_dataset_characterization_bundle` (hoặc tạo validator mới) để verify aggregate matrix reconcile với per-dataset matrices.

## Related Code Files

- **Read-only references:**
  - `multimodal-lecture-summarizer/experiments/scripts/stage_benchmark_helpers.py:load_eligible_units`
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml:large_dataset_policy`
  - `multimodal-lecture-summarizer/multimodal-lecture-summarizer/plans/260921-1943-scientific-benchmark-pipeline/plan.md` (metric registry contract)
- **Modify:**
  - `multimodal-lecture-summarizer/experiments/scripts/aggregate_endpoint_matrix.py` (NEW)
  - `multimodal-lecture-summarizer/experiments/registry/research_decisions.yaml` (add `endpoint_matrix` summary)
- **Create:**
  - `multimodal-lecture-summarizer/tests/test_endpoint_matrix_expansion.py`

## Implementation Steps

1. **Verify Phase 1 + 3 endpoints đã được driver write** (3-5 phút):
   ```bash
   cat experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads/dataset.endpoint_matrix.json
   cat experiments/outputs/phase2_eduviqa_d2/official/full/payloads/dataset.endpoint_matrix.json
   ```
   Expect mỗi file có ≥ 1 entry eligible_d2.

2. **Implement `aggregate_endpoint_matrix.py`** (~200 dòng):
   ```python
   #!/usr/bin/env python3
   """Aggregate endpoint matrices from all D2 datasets and validate cross-dataset eligibility."""
   import argparse
   import json
   import pathlib
   from collections import defaultdict
   
    ENDPOINT_DATASET_COMPATIBILITY = {
        "asr_benchmark": ["tedlium3"],
        "ocr_benchmark": ["iiit_cvid"],
        # canonical names below; the rest stay not_eligible (no released GT)
        "scene_boundary_benchmark": [],
        "keyframe_selection_benchmark": [],
        "visual_caption_benchmark": [],
        "object_detection_benchmark": [],
        "multi_object_tracking_benchmark": [],
        "chaptering_benchmark": [],
        "chaptering_modality_ablation": [],
        "summarization_benchmark": [],
        "summary_evidence_evaluation": [],
        "retrieval_benchmark": [],
        "qa_generation_benchmark": [],
        "end_to_end_system": [],
    }
   
   def main():
       parser = argparse.ArgumentParser()
       parser.add_argument("--artifact-roots", nargs="+", required=True,
                           help="paths to phase2_*_d2/official/full/payloads directories")
       args = parser.parse_args()
       
       aggregate_records = []
       for endpoint, expected_datasets in ENDPOINT_DATASET_COMPATIBILITY.items():
           # Load per-dataset endpoint_matrix.json files
           found_datasets = []
           for root in args.artifact_roots:
               matrix_file = pathlib.Path(root) / "dataset.endpoint_matrix.json"
               if not matrix_file.exists():
                   continue
               matrix = json.loads(matrix_file.read_text())
               for record in matrix["records"]:
                   if (record.get("endpoint") == endpoint
                       and record.get("eligibility") == "eligible_d2"
                       and record.get("scientific_selection_eligible") is True):
                       found_datasets.append(record["dataset_id"])
           
           aggregate_records.append({
               "endpoint": endpoint,
               "eligible_datasets": found_datasets,
               "scientific_selection_eligible": len(found_datasets) > 0,
               "expected_datasets_per_master_plan": expected_datasets,
               "compatibility_match": sorted(found_datasets) == sorted(expected_datasets),
               "reason": "" if found_datasets else "no D2 frozen dataset with released GT for this endpoint",
           })
       
       aggregate = {
           "schema_version": 1,
           "records": aggregate_records,
           "metadata": {
               "total_endpoints": len(ENDPOINT_DATASET_COMPATIBILITY),
               "total_eligible_endpoints": sum(1 for r in aggregate_records if r["scientific_selection_eligible"]),
               "total_eligible_datasets": 2,   # tedlium3 + iiit_cvid
           },
       }
       
       output = pathlib.Path("experiments/outputs/endpoint_matrix_v2/official/full/payloads/endpoint_matrix_aggregate.json")
       output.parent.mkdir(parents=True, exist_ok=True)
       output.write_text(json.dumps(aggregate, indent=2))
       print(f"Aggregate endpoint matrix written to {output}")
       print(f"Eligible endpoints: {aggregate['metadata']['total_eligible_endpoints']}/{aggregate['metadata']['total_endpoints']}")
   
   if __name__ == "__main__":
       main()
   ```

3. **Run aggregator**:
   ```bash
   cd multimodal-lecture-summarizer
   python -m experiments.scripts.aggregate_endpoint_matrix \
     --artifact-roots \
       experiments/outputs/phase2_tedlium_d2/official/full/payloads \
       experiments/outputs/phase2_iiit_cvid_d2/official/full/payloads \
       experiments/outputs/phase2_eduviqa_d2/official/full/payloads
   ```
   Verify output có:
   - 4 entries `scientific_selection_eligible=true` (asr, ocr, retrieval, qa).
   - 7 entries `scientific_selection_eligible=false` với `reason` rõ ràng.

4. **Verify `load_eligible_units`** dispatch đúng:
   ```python
   # In Python REPL or test:
   from experiments.scripts.stage_benchmark_helpers import load_eligible_units
   for endpoint in ["asr_benchmark", "ocr_benchmark", "retrieval_benchmark", "qa_benchmark", "scene_boundary_benchmark"]:
       try:
           units = load_eligible_units(endpoint)
           print(f"{endpoint}: {len(units)} units")
       except RuntimeError as e:
           print(f"{endpoint}: RuntimeError: {e}")
   ```
   Expect:
   - `asr_benchmark`: 20 units (TED-LIUM)
   - `ocr_benchmark`: 200 units (IIIT-CVID)
   - `retrieval_benchmark`: 20 units (EduViQA)
   - `qa_benchmark`: 20 units (EduViQA)
   - `scene_boundary_benchmark`: RuntimeError "no eligible units"

5. **Update `research_decisions.yaml`**:
   ```yaml
   # Add new section after phase2_dataset_execution:
   endpoint_matrix_summary:
     last_updated: "{date}"
     total_d2_eligible_datasets: 3
     eligible_endpoints:
       - asr_benchmark: [tedlium3]
       - ocr_benchmark: [iiit_cvid]
       - retrieval_benchmark: [eduviqa]
       - qa_benchmark: [eduviqa]
     not_eligible_endpoints:
       - scene_boundary_benchmark: "no D2 frozen dataset with released scene boundary GT"
       - keyframe_selection_benchmark: "no D2 frozen dataset with released keyframe GT"
       - visual_caption_benchmark: "no D2 frozen dataset with multi-reference caption GT"
       - object_detection_benchmark: "no D2 frozen dataset with box/class GT"
       - multi_object_tracking_benchmark: "no D2 frozen dataset with trajectory/identity GT"
       - chaptering_benchmark: "SSIM chunking is heuristic, not released GT"
       - summary_benchmark: "no D2 frozen dataset with native reference summary"
       - multimodal_summary_benchmark: "depends on summary_benchmark"
   ```

6. **Tests mới** `tests/test_endpoint_matrix_expansion.py` (≥ 5 tests):
   - `test_aggregate_endpoint_matrix_4_eligible`: aggregate có đúng 4 entries `scientific_selection_eligible=true`.
   - `test_per_dataset_endpoint_matrices_unchanged`: 3 per-dataset files không bị sửa content (chỉ verify aggregate output).
   - `test_load_eligible_units_asr_returns_tedlium`: 20 units, all từ tedlium3.
   - `test_load_eligible_units_ocr_returns_iiit_cvid`: 200 units, all từ iiit_cvid.
   - `test_load_eligible_units_qa_returns_eduviqa`: 20 units, all từ eduviqa.
   - `test_load_eligible_units_scene_fails_closed`: RuntimeError "no eligible units".

## Success Criteria

- [ ] `experiments/outputs/endpoint_matrix_v2/official/full/payloads/endpoint_matrix_aggregate.json` co **2** entries `scientific_selection_eligible=true` + 12 `not_eligible` voi `reason` ro rang.
- [ ] `load_eligible_units("asr_benchmark")` returns 20 TED-LIUM units (verified voi `RunnerContext` tren `phase2_tedlium_d2`).
- [ ] `load_eligible_units("ocr_benchmark")` returns **1755** IIIT-CVID units (verified voi `RunnerContext` tren `phase2_iiit_cvid_d2`).
- [ ] `load_eligible_units("scene_boundary_benchmark")` raises RuntimeError "no eligible units" (fail-closed) tren **ca** 2 roots.
- [ ] `research_decisions.yaml` co `endpoint_matrix_summary` section voi 2 eligible + 12 not_eligible endpoints, ten endpoint canonical.
- [ ] 2 per-dataset endpoint matrices **khong bi modify** content (SHA-256 verify) — aggregator chi doc.
- [ ] `tests/test_endpoint_matrix_expansion.py` PASS >= 5/5.

## Risk Assessment

- **Risk:** `ENDPOINT_DATASET_COMPATIBILITY` constant có thể stale so với master plan mới nhất.
  **Mitigation:** Cross-check với `plans/260921-1943-scientific-benchmark-pipeline/plan.md:152-163` trước khi commit; chấp nhận update nếu master plan đã thay đổi.
- **Risk:** `load_eligible_units` raise RuntimeError generic không nói rõ endpoint nào failed.
  **Mitigation:** Verify error message bao gồm endpoint name + list of eligible datasets đang có.
- **Risk:** Aggregate matrix reconcile fail với per-dataset matrices (vd: dataset ghi eligible_d2 nhưng aggregate nói không).
  **Mitigation:** Step 3 compatibility_check field expose mismatch; fail-closed nếu mismatch.
- **Risk:** User thêm dataset mới (vd: TIB-bench-VLM) sau khi phase này complete → aggregate matrix stale.
  **Mitigation:** Plan ghi rõ "re-run aggregator khi thêm D2 dataset mới"; document trong research_decisions comment.

## Effort Breakdown

| Step | Time |
|------|------|
| Verify 3 per-dataset endpoint matrices | 0.5 giờ |
| Implement aggregate_endpoint_matrix.py | 2-3 giờ |
| Run aggregator + manual verify load_eligible_units | 1-2 giờ |
| Update research_decisions.yaml | 0.5 giờ |
| Tests mới + regression check | 2-3 giờ |
| **Tổng** | **6-9 giờ** |