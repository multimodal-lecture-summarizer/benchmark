---
phase: 4
title: "Implement real stage benchmark runners"
status: pending
priority: P1
dependencies: [3]
effort: "2-4 weeks"
---

# Phase 4: Implement real stage benchmark runners

## Overview

Thực thi bake-off thật cho từng task bằng cùng protocol, lưu raw prediction/per-unit metrics và sinh aggregate hoàn toàn từ artifacts đã validate.

## Requirements

- Functional: một runner contract dùng được cho local model, algorithm baseline và API candidate.
- Reproducibility: config, dataset/model/code hash, command, environment, hardware, seed, timing, peak memory và cost được ghi tự động.
- Fairness: cùng frozen split, input/preprocessing contract và task-specific budget trong một leaderboard.

## Architecture

`Registry -> Adapter -> Per-unit executor -> Raw JSONL -> Schema validator -> Metric calculator -> Aggregate/report`. Metric calculator không được gọi nếu raw output thiếu IDs/reference/prediction/status.

## Related Code Files

- Modify: `multimodal-lecture-summarizer/experiments/evaluation/runners.py`
- Modify: `multimodal-lecture-summarizer/experiments/scripts/run_eval_tables.py`
- Modify: `multimodal-lecture-summarizer/experiments/scripts/ablation_runner.py`
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_object_detection_benchmark.py`
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_rq1_benchmark.py`
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_rq2_benchmark.py`
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_rq3_benchmark.py`
- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_rq4_efficiency_benchmark.py`
- Create/modify schemas under `multimodal-lecture-summarizer/experiments/evaluation/` and tests under `multimodal-lecture-summarizer/tests/`
- Create: `multimodal-lecture-summarizer/experiments/registry/metric_registry.yaml`

## Implementation Steps

1. Định nghĩa versioned `run_manifest`, `per_unit_prediction` và `aggregate_result` schemas.
2. Implement versioned metric registry: one primary metric per task/GT track plus direction, scorer/version, normalization, IoU/collar/k, aggregation, failure policy, practical threshold and diagnostic metrics.
3. ASR English: save reference/hypothesis/alignment and S/D/I; primary corpus WER under frozen normalizer; secondary CER, macro per-talk WER, empty/failure rate, timestamp error, latency/RTF. Never cap WER at 100%.
4. Scene: save boundaries and one-to-one matches; primary boundary F1 at frozen collar; P/R, matched MAE, FP/minute, segment count and over/under-segmentation diagnostics.
5. Keyframe/visual evidence: score must-keep/required-scene Recall or F1 under a fixed frame budget; report precision, scene/temporal coverage, redundancy, downstream delta, latency and uniform/random baselines.
6. OCR: separate detection (IoU Hmean/F1), recognition-only (CER primary) and end-to-end spotting (spotting Hmean); report P/R, WER, word accuracy, normalized edit distance, exact/empty rate and latency/frame.
7. Caption/VLM: multi-reference track uses CIDEr primary with SPICE/BERTScore; evidence/object track uses grounded claim/object support F1. PAC-S/CLIPScore and model-based factuality are diagnostic; record hallucination and latency.
8. OD/tracking: OD primary COCO mAP50-95 plus AP50/AP75/per-class/by-size AP and AR. Tracker-only primary HOTA under fixed detections plus DetA/AssA/LocA, IDF1, MOTA diagnostic, IDSW/fragmentation/mostly tracked-lost/FPS.
9. Chaptering: primary boundary F1/Boundary Similarity at fixed tolerance; Pk, WindowDiff, segment-count/duration error and labeled title relevance; lecturer/source-disjoint evaluation.
10. Multimodal summary: generate synchronized text and visual/keyshot outputs from one event/evidence timeline at 5/10/20% budgets. Text reference track uses ROUGE-Lsum with factual-support gate plus ROUGE-1/2, BERTScore, claim/citation coverage, compression/redundancy. Visual track uses keyshot F1 under equal duration budget plus dense-score correlation where GT supports it. Never scalar-merge text and visual scores.
11. Retrieval/QA: retrieval primary Recall@k or nDCG@k for graded GT; report Precision@k/MAP/MRR as applicable. QA primary EM/token F1 for short answers plus answer correctness, evidence recall/timestamp overlap, citation correctness/completeness, hallucination and abstention/risk-coverage.
12. Resource telemetry: hardware/API profile, wall/stage time, p50/p95, RTF, throughput, peak RAM/VRAM, API tokens/cost, retry, timeout/OOM/failure denominator and cold/warm flags.
13. Sinh notebook tables/figures từ raw artifacts qua một deterministic analysis path; không copy số thủ công.
14. Thêm resume/checkpoint và cache keyed bằng exact config/model/data hash; cache mismatch buộc rerun.
15. Mọi runner gọi dataset preflight trước model load: validate D2 receipt, task-native GT, data root, free-space reserve, file checksums và decode sample; thiếu/khác revision thì fail closed.
16. Mỗi task runner có CLI độc lập để notebook tương ứng chỉ truyền config và render kết quả; retrieval/QA, scene/keyframe/OCR/caption, efficiency/error-propagation không dùng chung một lệnh nhập nhằng.
17. Add metric sanity fixtures for perfect, empty, shifted-boundary, duplicate, hallucinated, wrong-citation and failed predictions; add schema, dispatch, failure-path and miniature integration tests.

## Success Criteria

- [ ] Mỗi aggregate cell truy ngược được tới raw unit rows và run manifest.
- [ ] Candidate registry được dispatch đúng adapter/config; không có metric constant theo tên model.
- [ ] OCR có accuracy GT, OD có non-null mAP, tracking có identity metrics, summary có real generations, QA có ranked evidence.
- [ ] Metric registry validates every eligible task and freezes primary metric/scorer parameters before final test; unknown or incompatible GT type fails closed.
- [ ] Keyframe, caption, text summary and visual summary no longer use vague `coverage/support` fields without a defined scorer and denominator.
- [ ] Multimodal summary artifacts contain shared event/evidence IDs, synchronized text/keyshot outputs and exact 5/10/20% budget compliance.
- [ ] Speaker diarization output may exist as future-ready schema but cannot enter current official aggregate or selection decision.
- [ ] Missing/failure không bị biến thành zero score; denominator và exclusion reason được báo cáo.
- [ ] Cùng run/config hash cho kết quả analysis lặp lại; cache khác hash bị từ chối.
- [ ] Runner không tự tải full dataset hoặc model ngoài manifest; mọi network fetch có byte/time budget, resume và receipt.
- [ ] Mỗi notebook task chạy được bằng một command runner tương ứng ngoài Jupyter và tạo cùng artifact schema.
- [ ] Smoke, schema và miniature E2E tests pass trước full benchmark.

## Risk Assessment

- Model download/API/network failure: preflight artifact availability, checkpoint resume và explicit partial status.
- Khác precision/quantization làm comparison lệch: tách research-quality và deployment profile.
- Runner file hiện lớn: tách adapter, schema, metrics và telemetry theo module nếu sửa vượt ranh giới logic hiện có.
