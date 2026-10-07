---
phase: 7
title: "Validate end-to-end system and reconcile reports"
status: pending
priority: P1
dependencies: [6]
effort: "1-2 weeks including report review"
---

# Phase 7: Validate end-to-end system and reconcile reports

## Overview

Chạy pipeline shortlist trên video-level test set, đo cả quality và vận hành, sau đó đồng bộ notebook, docs và luận văn với đúng mức bằng chứng.

## Requirements

- E2E config immutable, pinned và traceable tới stage decision records.
- Đo cold/warm, duration/resolution/codec/noise strata, success/failure/timeout/OOM và API cost.
- Website/demo validation không được dùng thay cho scientific benchmark; hai loại evidence được báo riêng.

## Architecture

`Frozen pipeline configs -> end-to-end executor -> stage traces + system telemetry -> per-video result -> aggregate/Pareto -> report generator -> evidence audit`.

## Related Code Files

- Modify: `multimodal-lecture-summarizer/benchmarks/scripts/run_rq4_efficiency_benchmark.py`
- Modify notebooks `08b_end_to_end_system` and `09_cross_task_report` through generator
- Modify relevant benchmark/research docs under `multimodal-lecture-summarizer/docs/`
- Modify website statistics endpoints/UI only after measurement contract is stable and only if required by the project outline

## Implementation Steps

1. Freeze final 2–4 pipeline configs and E2E video test manifest.
2. Run repeated cold/warm trials separately on `colab_t4` and `local_rtx4050_6gb` where eligible; record wall/stage p50/p95, RTF, throughput, RAM/VRAM, cost and energy proxy only if measured.
3. Report success rate with denominator; classify validation, model, timeout, OOM, API and unknown failures.
4. Stratify by video duration, resolution, codec, noise and modality availability; report n and uncertainty per stratum.
5. Measure synchronized text + visual multimodal summaries at 5/10/20% budgets, factual/evidence support, retrieval/QA evidence correctness and key intermediate stage quality on the same videos.
6. Verify input validation and partial-failure behavior for corrupted/unsupported/oversized videos without contaminating scientific quality denominator.
7. Regenerate toàn bộ notebook từ generator; chạy `08b` trên frozen configs rồi chạy read-only `09`; tables/figures chỉ đọc eligible artifacts và gắn run IDs/commands.
8. Reconcile README, OUTLINE_MAPPING, BENCHMARK/ROADMAP/RESEARCH docs and thesis tables: remove unsupported `done`, `best`, `100%`, `93%` claims.
9. Publish limitations, external validity, dataset rights, compute footprint and all `not_run`/`not_eligible` outcomes.
10. Final independent evidence audit: sample table cells back to raw rows and reproduce at least one run from clean environment.

## Success Criteria

- [ ] E2E results exist per video for every frozen pipeline and hardware profile.
- [ ] Text and visual summaries share event/evidence IDs, obey their separate word/duration budgets and are reported as a metric vector rather than one composite score.
- [ ] Derived unified dataset exports provenance and separates official GT from model predictions at field/schema level.
- [ ] No efficiency/quality value is hard-coded or borrowed from model specs.
- [ ] Success/failure, timeout/OOM and length strata are reported with denominators.
- [ ] Every thesis/report table cell maps to eligible run ID and raw artifact.
- [ ] Clean-environment reproduction command succeeds for a representative run and full analysis.
- [ ] `08b` và `09` chạy độc lập từ artifact contract; report notebook không load model hoặc mutate raw results.
- [ ] Final conclusion labels `research_best`, `deployable_best`, tie or `no_selection` with limitations.
- [ ] Website/demo claims match measured behavior and no longer imply tracking/metric support that is absent.

## Risk Assessment

- Full E2E may exceed time/compute budget: reduce candidate count after Phase 6, never shrink test set after seeing outcomes.
- Report drift: generate tables where possible and maintain a claim-to-evidence checklist.
