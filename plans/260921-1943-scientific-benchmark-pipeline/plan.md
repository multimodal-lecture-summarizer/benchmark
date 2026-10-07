---
title: "Scientific benchmark pipeline and candidate diversity"
description: "Roadmap sửa benchmark, mở rộng candidate đa họ mô hình và chọn pipeline bằng bằng chứng tái lập."
status: in-progress
priority: P1
effort: "multi-phase research; evidence gates remain open"
branch: ""
tags: [research, benchmark, multimodal, reproducibility, model-selection]
blockedBy: []
blocks: []
created: "2026-09-21T12:46:17.961Z"
createdBy: "ck:plan"
source: skill
---

# Scientific benchmark pipeline and candidate diversity

> Historical plan: the generic D2 dataset-contract, profiling and evaluation-table scripts cited in this plan were removed on 2026-10-07. The implementation steps below record their original scope; use the current task-specific EDA and evaluation workflow in `benchmark/docs/BENCHMARK.md` for new runs.

**Current execution decision, 2026-10-07:** Use the simpler [three-step research workflow](../../docs/BENCHMARK.md#quy-trình-nghiên-cứu-hiện-hành): select verified lecture-domain datasets with existing task labels and diverse candidates; create/run an EDA notebook for the selected cohort and decide data handling; then create/run an evaluation notebook comparing candidates on the same task-specific scale. General-video datasets are not secondary benchmarks or fallbacks; tasks without suitable lecture-domain GT remain `not_eligible`. Only create notebooks at the time of actual use. No notebook smoke phase or placeholder notebook inventory is required. The proposed topology, 22-notebook smoke criterion and execution snapshots below document the earlier plan; they are not current work orders. ASR and RQ1 are retained as diagnostic history, with no rerun planned.

## Overview

Kế hoạch nâng bộ thực nghiệm hiện tại từ mức scaffold/pilot lên benchmark có thể bảo vệ khoa học cho đồ án. Mục tiêu không phải tìm một `best` tuyệt đối từ vài aggregate metric, mà tạo chuỗi bằng chứng tái lập:

1. Chạy thật từng candidate trên cùng frozen split, input budget và hardware profile.
2. Giữ 2–3 candidate nằm trên Pareto frontier ở mỗi task.
3. Ghép shortlist, đo tương thích và error propagation trên cùng video.
4. Chốt riêng `research_best`, `deployable_best` hoặc `no_selection` khi bằng chứng chưa đủ.

Phạm vi giữ nguyên đề cương: ASR, scene/keyframe, OCR/caption, detection/tracking, chaptering, summarization, retrieval/QA và đánh giá hệ thống. Candidate model/algorithm, ablation và preprocessing phải là ba lớp thí nghiệm khác nhau; DeepFilterNet/VAD không được trình bày như ASR decoder, còn C1–C6, S0–S4 và Q0–Q3 được giữ làm ablation/architecture variants thay vì giả là các họ mô hình độc lập.

Nguồn audit nền: [scientific evaluation audit](../reports/scientific-evaluation-audit-260921-1901-multimodal-notebook-pipeline-report.md).

## Scope decision

- Existing code: registry, ablation runner, benchmark scripts, notebook 00–07 và một số raw/aggregate artifact đã có nhưng nhiều đường chạy là no-op, dry/mock, proxy hoặc hard-coded.
- Minimum required: sửa evidence path trước; freeze data/GT; mở rộng candidate đa họ; runner thực; thống kê paired; stage shortlist; compatibility/E2E.
- Deferred: fine-tuning lớn, xây dataset công khai mới, SOTA-scale sweep và production autoscaling. Chỉ làm nếu benchmark tối thiểu đã đạt gate.
- Selected scope: HOLD — không mở rộng chức năng website; tập trung làm chặt phần nghiên cứu và tích hợp AI theo đề cương.

## Scientific rules

- Đơn vị độc lập là talk/video, không dùng frame/word/chunk/query như `n` độc lập.
- Không điền thiếu bằng `0`; dùng `not_run`, `not_eligible`, `proxy_only`, `failed`, `partial`.
- Aggregate table phải sinh từ raw per-unit artifacts; cấm nhập tay metric production.
- Final test chỉ chạy sau khi candidate, threshold, prompt, split và practical threshold đã freeze trên validation.
- So sánh paired trên cùng unit; báo delta, 95% CI, effect size, practical significance và Holm-corrected p-value khi phù hợp.
- Mọi candidate dùng cùng input, preprocessing contract, budget và hardware profile; nếu khác profile phải tách leaderboard.
- Fallback cascade có thể dùng trong production nhưng không được tính là candidate độc lập trong model bake-off.
- Khi không đủ GT hoặc số unit, kết luận bắt buộc là `no_selection`, không suy diễn winner.

## Target evidence outputs

| Layer | Required artifact |
|---|---|
| Protocol | Frozen dataset registry, split manifest, licenses/rights, checksums, annotation guide |
| Dataset characterization | Per-dataset data card, unit-level profile table, quality/attrition tables, split-leakage audit and reproducible figures |
| Run | `run_manifest.json`, config/model/code hashes, logs, hardware, timing, failure status |
| Prediction | Per-unit reference, prediction, confidence/evidence, latency, error message |
| Analysis | Per-unit metrics, paired comparison, bootstrap CI, corrected tests, Pareto table |
| Selection | Stage shortlist with `research_best`/`deployable_best`/`no_selection` and rationale |
| Integration | Compatibility matrix, oracle-vs-predicted degradation, perturbation reruns |
| Reporting | Notebook outputs and report tables regenerated only from eligible real runs |

## Dataset feasibility and storage gate

Snapshot máy phát triển sau cleanup ngày 2026-09-21:

- Ổ `C:` còn 248.91 GB trên khoảng 928.44 GB; `experiments/datasets` chiếm 55.105 GB / 151,884 file.
- Dữ liệu đã có gồm TED-LIUM3 49.326 GB, IIIT-CVID 4.495 GB, EduVidQA 1.278 GB và SlideVQA 0.006 GB.
- Archive trùng `iiit_cvid.zip` 47.119 GB đã được xóa sau khi xác minh 151,883/151,883 entry đã giải nén, 0 file thiếu và 0 size mismatch. Raw dataset directories được giữ nguyên.
- Giữ sau mọi thao tác ít nhất `max(100 GB, 15% dung lượng volume)`. Với snapshot hiện tại, peak disk tăng thêm tối đa khoảng 109.6 GB. Con số phải được preflight lại ở đầu mỗi run, không hard-code.
- Peak disk dự báo phải gồm archive + dữ liệu giải nén + cache tạm + artifact. Nếu chưa biết tỷ lệ giải nén, dùng hệ số an toàn 2.5x; vì vậy không tải archive chưa rõ kích thước lớn hơn khoảng 43 GB vào ổ hiện tại.
- VISTA full 1.93 TB là `not_feasible_local`; chỉ cho phép metadata/schema probe, subset đã duyệt, hoặc chạy trên external storage/compute profile riêng.
- [TIB text](https://huggingface.co/datasets/gigant/tib) (~502 MB) và [TIB-bench-VLM](https://huggingface.co/datasets/gigant/tib-bench-vlm/tree/main/data) (~2.33 GB theo repository hiện hành) phù hợp local pilot. [YTSeg](https://huggingface.co/datasets/retkowski/ytseg/tree/main/data)/[EduVidQA](https://github.com/sourjyadip/eduvidqa-emnlp25) phụ thuộc media bên ngoài nên phải probe availability trước, không giả định mọi YouTube URL còn sống.

Mỗi dataset đi qua bốn mức, không được nhảy gate:

| Level | Scope | Gate bắt buộc |
|---|---|---|
| D0 | Metadata/schema only, <= 1 GB | source/revision/license/schema đọc được; không tải media |
| D1 | Pilot 20 unit hoặc <= 10 GB peak | 100% checksum manifest; >= 90% tải thành công sau retry; >= 95% file tải được decode; đo bytes, thời gian và peak disk |
| D2 | Frozen subset, <= 50 GB peak tăng thêm trên máy hiện tại | deterministic IDs; resume/idempotent; estimated completion <= 12 giờ/profile; còn đủ disk reserve |
| D3 | Full/large-scale | chỉ khi D2 pass và có storage/compute profile được ghi trong manifest; không mặc định chạy local |

Download manager phải hỗ trợ cache root cấu hình được, resume theo shard/file, partial-file quarantine, SHA-256, retry có giới hạn, timeout, rate-limit và dry preflight. Tải xong phải ghi `download_receipt.json` gồm URL/revision, expected/actual bytes, checksum, elapsed time, throughput, retry/failure, decode status và tool versions. Dataset không đạt gate chuyển sang fallback đã đăng ký hoặc `not_eligible`; không thay âm thầm bằng sample/mock.

## Dataset analysis and visualization contract

The former `00c_dataset_eda_and_freeze` design required EDA from validated unit-level metadata, not hand-entered figures. That notebook has been removed from active use; a future task-specific EDA notebook should preserve the same evidence rule. Keep D1 pilot and D2 frozen results separate by `acquisition_level`, `dataset_revision`, `profile_generated_at` and denominator; do not describe pilot results as the full dataset.

Mỗi dataset phải có `dataset_profile.json` và một dòng trong `dataset_statistics.csv` với tối thiểu:

| Nhóm | Thông số bắt buộc |
|---|---|
| Identity/provenance | dataset ID, source URL, citation, revision, license/terms, access mode, retrieval date, checksum-manifest hash |
| Scale/split | raw/eligible/excluded unit count, train/validation/test count, bytes, total duration, independent-unit definition, source/speaker/talk count |
| Modalities/GT | audio/video/transcript/OCR/boxes/tracks/chapters/summary/QA availability; GT type, annotation count, annotator count, agreement và GT coverage |
| Video | duration, width, height, aspect ratio, FPS, codec, bitrate, frame count, variable-frame-rate flag |
| Audio | duration, sample rate, channels, codec, bitrate, loudness/noise/SNR proxy khi đo được, speech ratio |
| Text/speech | language/accent, speaker count, utterance count, token/word count, speaking rate, transcript coverage |
| Task labels | class/taxonomy count, positive/negative count, boxes/tracks/boundaries/QA/reference count per unit, class frequency và long-tail ratio |
| Quality | missing/corrupt/inaccessible/duplicate/near-duplicate count, timestamp overflow, zero-length/empty-label count, exclusion reason và attrition rate |

Quy tắc thống kê:

- Trường liên tục báo `n`, `missing_n`, min, p5, p25, median, p75, p95, max, mean và standard deviation; không suy diễn metric không đo được.
- Trường phân loại báo count, percentage, unknown/missing và rare-category tail. Mọi bảng split báo denominator riêng.
- Tất cả số lượng phải reconcile: `raw = eligible + excluded + unresolved`; sai lệch làm EDA `failed` hoặc `partial`.
- Exact checksum/ID/source/speaker/talk overlap giữa validation và final test phải bằng 0, trừ official split exception được pre-register. Near-duplicate phải được liệt kê và adjudicate trước freeze.
- Bin/strata cho duration, noise, resolution, codec, language/accent và label frequency được chọn trên train/validation từ EDA rồi freeze; không đổi sau khi xem final-test result.

Visualization bắt buộc, mỗi hình phải có dataset revision, acquisition level, split, `n`, unit, missing/exclusion policy và source table:

| Scope | Hình/bảng bắt buộc |
|---|---|
| Universal | unit-count + duration/bytes summary; duration histogram + ECDF; file-size distribution; missingness/GT-coverage heatmap; exclusion/attrition waterfall; split-comparison plot; source/speaker overlap matrix; exact/near-duplicate matrix |
| Video | resolution/aspect-ratio distribution; FPS/codec distribution; duration x resolution; corrupt/decode status |
| Audio/ASR | clip/talk duration; sample-rate/channel distribution; speech ratio/noise proxy; speaker/source count; word/token and speaking-rate distribution |
| Detection/tracking | class-frequency long-tail; boxes/tracks per unit; box area/aspect ratio; track length; occlusion/identity coverage |
| Scene/chapter/keyframe | boundaries/chapters/keyframes per unit; segment-length distribution; annotation-density timeline/coverage |
| OCR/caption/summary/QA | text length and language; OCR lines/tokens per frame; reference-summary length/compression; QA answer/evidence type and evidence coverage |

Artifact contract dưới `experiments/outputs/dataset_eda/<dataset_id>/<revision>/` gồm `dataset_profile.json`, `unit_profile.parquet` hoặc CSV, `dataset_statistics.csv`, `split_statistics.csv`, `quality_issues.csv`, `attrition.csv`, `leakage_audit.csv`, `figure_manifest.json` và `figures/`. `cross_dataset_comparison.csv` chỉ so sánh các trường cùng định nghĩa; `DATASET_EDA.md` được sinh tự động từ các artifact này. Mỗi figure manifest ghi source-table hash, code revision và plotting config để tái tạo hình.

## Phases

| Phase | Name | Status |
|-------|------|--------|
The original seven phase checklists were removed during the 2026-10-07 documentation cleanup. Their historical status is not a current execution queue; follow the current workflow linked above.

## Current status — 2026-09-26

Phase 1 infrastructure is repaired, but execution/equivalence evidence is incomplete. Phase 2 has diagnostic data and repaired gates; it has no newly established scientifically eligible D2 subset. SHA identity is not near-duplicate adjudication, and all 10 old TED final-test units were exposed during ASR selection. Existing results are historical diagnostics; no relabeling restores an independent holdout.

The former Phase 1 11/12 checklist and TED-only Phase 2 ticks must not be read as scientific completion. Phase 1 execution/equivalence gates remain open; scoped regression verification passed; Phase 2 full acceptance remains 0/20 while historical partial evidence is retained. All seven phase files were reviewed in this reconciliation; Phases 3–7 remain pending with no newly completed criteria.

The earlier phase-12 repair sequence and its proposed notebook are historical; see the current notebook manifest and task-specific protocol before creating any new run.
## Dependencies

- No blocking plan detected in project scope.
- Phase 2 depends on Phase 1 evidence-status contract.
- Phase 3 depends on task/language/hardware constraints frozen in Phase 2.
- Phases 4–7 are sequential evidence gates; later phases cannot claim success from dry/proxy artifacts.

## Implementation readiness gate

- Historical Phase 1 instruction (2026-09-21): work was limited to manifest/schema, notebook generation, executor dispatch and tests; it did not authorize a model winner. The current on-demand notebook workflow above supersedes notebook generation as a standalone phase.
- Phase 2 may start acquisition probes after `research_decisions.yaml` records the frozen decisions below. API runs additionally require a per-run token/cost/rate-limit cap; missing API budget blocks only that API track, not open-source/local dataset qualification.
- Phases 3–7 are blocked until Phase 2 produces an eligible dataset matrix and frozen decision file. Missing decisions must yield `blocked_decision`, never an implicit default.
- The nested Git worktree is currently dirty. Implementation must begin with a path ownership list and before-state inventory; only plan-owned notebook/generator/executor/registry/test files may be changed. Unrelated modified/untracked files must be preserved.
- Legacy notebooks and duplicate generators are deleted only after migration mapping, miniature real-data equivalence and recoverability checks pass.

## Deliverables by task

| Task | Model/algorithm bake-off | Separate ablation/preprocessing |
|---|---|---|
| ASR | Whisper family vs CTC vs transducer/attention vs lightweight offline | denoise, VAD, alignment, decoding parameters |
| Scene | uniform baseline, histogram/content, learned boundary, embedding change-point | threshold, collar, minimum scene length |
| Keyframe | midpoint, temporal dedup, clustering/diversity, OCR-aware salience | frame budget and sampling rate |
| OCR | Tesseract, EasyOCR, PaddleOCR, transformer recognizer | detector/recognizer split, deskew, enhancement |
| Caption/VLM | BLIP-class, Florence-class, Qwen/LLaVA-class feasible models | prompt, frame budget, quantization |
| Detection | YOLO, RT-DETR, open-vocabulary grounding | confidence/NMS; closed/open taxonomy reported separately |
| Tracking | ByteTrack, BoT-SORT, OC-SORT/DeepSORT under fixed detector | detector choice evaluated after tracker-only comparison |
| Chaptering | fixed-window, lexical segmentation, learned unimodal, multimodal fusion | C1–C6 modality ablations |
| Summary | extractive, encoder-decoder, flat LLM, hierarchical LLM, multimodal/VLM | S0–S4 context/evidence ablations |
| Retrieval/QA | BM25, dense, hybrid, reranked; reader/generator separated | Q0–Q3 hierarchy/modality ablations |
| System | Frozen pipeline compositions only | E1–E4 quality–latency–memory–cost trade-off |

## Frozen research decisions

| Decision | Frozen value |
|---|---|
| Primary language | English. ASR primary metric is WER with a frozen English normalizer; CER remains secondary. Non-English material is out-of-track unless declared separately. |
| Summary outputs | Both text summary and visual/keyshot summary. They form one multimodal summary package grounded in the same event/evidence timeline. |
| Summary budgets | `short=5%`, `medium=10%`, `long=20%`. Text budget is percentage of transcript word count; visual budget is percentage of original video duration. |
| Unified dataset | Pipeline may export transcript, scenes, keyframes, OCR, captions, objects, tracks, chapters, events, evidence timestamps and summaries into one derived multimodal dataset. Predictions remain predictions, never GT. |
| Ground truth | Official/pre-existing labeled data only. No project-created GT and no pseudo-label/heuristic reference in official evaluation. Missing suitable labels -> fallback dataset or `not_eligible`. |
| Speaker diarization | Future-ready module/interface only. Excluded from current official leaderboard and pipeline-selection gate; DER/JER/cpWER remain deferred. |
| Compute profiles | `colab_t4` for heavy tasks and `local_rtx4050_6gb` for light/local tasks. Efficiency results and model eligibility are reported separately by profile. |
| Model policy | Prefer open-source models/algorithms. Groq/OpenRouter allowed only for LLM stages when justified by local infeasibility or a scientific comparison; record provider, exact model/date, reason, tokens, cost, rate limits and fallback. |
| Large datasets | VISTA full remains `not_feasible_local`; use an eligible labeled subset/fallback or a separately approved external storage profile. |

**RQ1 dataset decision, 2026-09-28:** giữ nguyên quy tắc GT có sẵn ở trên. [Cohort MITFLD 35 bài](../reports/rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md) chỉ là pilot/diagnostic; split 19/8/8 chưa phải D2, `frags` chưa được xác nhận là chapter GT phù hợp/có quyền, và nhãn do nhóm tự tạo không vào official evaluation. Official RQ1 tiếp tục theo YTSeg cùng subset multimodal được đóng băng nếu vượt đủ gate quyền, GT và D2; thiếu dữ liệu phù hợp thì ghi `not_eligible`.

## Metric registry contract

`experiments/registry/metric_registry.yaml` must freeze for every rankable task/track: `primary_metric`, direction, secondary/diagnostic metrics, scorer package/version, normalization/tokenization, matching parameters (`IoU`, collar, `k`), aggregation level, failure policy, practical threshold and applicable GT type. One primary metric per rankable task/track is chosen before final-test inference. The multimodal package is explicitly non-scalar and uses `selection_mode: pareto_or_gate` over its text/visual components.

| Task/track | Primary metric | Secondary/diagnostic and mandatory constraints |
|---|---|---|
| ASR English | Corpus WER | CER, macro per-talk WER, S/D/I, empty/failure rate, timestamp error where needed, RTF; frozen text normalization |
| Scene boundary | One-to-one boundary F1 at pre-registered collar | P/R, matched-boundary MAE, FP/minute, segment-count/over-under error; collar sensitivity is diagnostic |
| Keyframe/visual evidence | Must-keep/required-scene Recall or F1 under fixed frame budget | precision, scene/temporal coverage, redundancy, downstream QA/summary delta, latency; uniform/random baselines |
| OCR detection | IoU-matched Hmean/F1 | P/R, AP when confidence ranking exists, empty prediction and condition strata |
| OCR recognition/spotting | CER for recognition-only; end-to-end spotting Hmean for full OCR | WER, word accuracy, normalized edit distance, exact match, empty-output rate, latency/frame |
| Caption with multi-reference GT | CIDEr | SPICE, BERTScore, PAC-S/CLIPScore diagnostic, hallucination/grounding and latency |
| Caption with evidence/object GT | Grounded claim/object support F1 | claim precision/recall, specificity, hallucination, human ratings only when existing labels/protocol permit |
| Object detection | COCO mAP@[.50:.95] | AP50/AP75, per-class AP, AP by size, AR, P/R; closed/open vocabulary tracks separate |
| Tracking under fixed detections | HOTA | DetA/AssA/LocA, IDF1, MOTA diagnostic, ID switches, fragmentation, mostly tracked/lost, FPS |
| Chaptering | Boundary F1/Boundary Similarity at frozen tolerance | Pk, WindowDiff, segment-count/duration error, title relevance if labeled |
| Text summary with references | ROUGE-Lsum with a factual-support eligibility gate | ROUGE-1/2, BERTScore, claim support/coverage, citation coverage, compression, redundancy; QAFactEval/SummaC diagnostic only unless calibrated |
| Visual/keyshot summary | F1 against human keyshot summary under identical 5/10/20% budget | Kendall/Spearman for dense importance labels, diversity, coverage, random/uniform and leave-one-annotator baselines |
| Multimodal summary package | Primary text + visual metrics reported jointly; no scalar merge | cross-modal event/evidence consistency and timestamp support when official labels exist; otherwise `not_eligible` for a joint metric |
| Retrieval | Recall@k, or nDCG@k for graded GT | Precision@k, MAP for multiple relevant items, MRR only for first-relevant use case, empty retrieval, latency/query |
| QA | EM/token F1 for short-answer GT | answer correctness, evidence Recall@k/timestamp overlap, claim-level citation correctness/completeness, hallucination, abstention/risk-coverage |
| End-to-end system | Video-level success subject to frozen final-quality gates | p50/p95 wall/stage latency, RTF, throughput, peak RAM/VRAM, cost/video, retry/timeout/OOM/failure attribution and quality strata |

Metric rules:

- Reference-free or model-based caption/factuality scores are diagnostic until validated against existing human labels in the lecture domain.
- OCR detection, recognition-only and end-to-end spotting stay separate; tracker-only uses fixed detections before detector+tracker integration.
- ROUGE/BERTScore do not establish factuality. A summary cannot be selected if it fails the pre-registered factual-support/evidence gate.
- Every aggregate includes denominator/failure rows and paired talk/video-level uncertainty. Missing/failed units are not zero-imputed or silently excluded.
- Primary quality gates are satisfied before quality–latency–memory–cost–failure Pareto selection; no post-hoc metric switching or undocumented scalar composite.

## Modular notebook topology

**Historical proposed topology (2026-09-21):** The table records planned task identities and does not assert that a notebook file exists or should be generated now. For current tasks, create only the EDA/evaluation notebook needed for a concrete cohort and run. Notebook outputs and shared runners still must be reproducible; no notebook depends on kernel state from another notebook.

| Group | Notebook | Responsibility |
|---|---|---|
| 00 | `00a_environment_preflight` | environment, hardware, package/model availability, data/cache paths |
| 00 | `00b_dataset_feasibility` | D0/D1 download, decode, disk and rights receipts |
| 00 | `00c_dataset_eda_and_freeze` | Generate validated data cards/statistics/figures, audit quality/leakage, then freeze IDs/splits/checksums |
| 01 | `01a_asr_model_benchmark` | compare ASR decoder families on frozen audio |
| 01 | `01b_asr_preprocessing_ablation` | denoise/VAD/alignment/decoding ablation using frozen ASR shortlist |
| 02 | `02a_scene_boundary_benchmark` | scene-boundary algorithms and collar metrics |
| 02 | `02b_keyframe_selection_benchmark` | midpoint/dedup/clustering/OCR-aware keyframes |
| 02 | `02c_ocr_benchmark` | text detection/recognition candidates |
| 02 | `02d_visual_caption_benchmark` | caption/VLM candidates and grounding support |
| 03 | `03a_object_detection_benchmark` | detector candidates on box/class GT |
| 03 | `03b_multi_object_tracking_benchmark` | tracker candidates under frozen detections |
| 04 | `04a_chaptering_benchmark` | algorithm-family comparison |
| 04 | `04b_chaptering_modality_ablation` | C1–C6 modality/fusion ablation only |
| 05 | `05a_summarization_benchmark` | synchronized text + visual multimodal summary candidates at frozen 5/10/20% budgets |
| 05 | `05b_summary_factuality_and_human_eval` | support/coverage/human-evaluation package; no generation tuning |
| 06 | `06a_retrieval_benchmark` | BM25/dense/hybrid/reranking |
| 06 | `06b_qa_generation_benchmark` | answer generation with frozen retrieval inputs |
| 07 | `07a_efficiency_pareto` | latency/RAM/VRAM/cost Pareto only |
| 07 | `07b_error_propagation` | measured upstream-error perturbation only |
| 08 | `08a_stage_compatibility` | shortlisted cross-stage compatibility matrix |
| 08 | `08b_end_to_end_system` | frozen pipeline video-level system evaluation |
| 09 | `09_cross_task_report` | read-only aggregation and report figures; never execute models |

Historical executor design: `experiments/notebooks/notebook_manifest.yaml` recorded `id`, `task_id`, `requires`, `produces`, dataset/profile, timeout and network policy. This does not require generating all listed notebook files. The smoke profile is retired for future notebook work; check the current manifest and CLI before running a task.

## Completion criteria

- [ ] Với mỗi tác vụ thực sự được chọn, notebook EDA chạy trên cohort khai báo; notebook đánh giá được tạo sau khi EDA và so sánh các họ ứng viên trên cùng metric, item và budget. Không cần tạo/chạy notebook smoke để đạt tiêu chí này.
- [ ] Mỗi notebook có đúng một `task_id`, một output namespace và không chứa model/metric implementation bị copy từ notebook khác.
- [ ] Executor chạy được từng notebook, từng group và DAG đầy đủ; `09_cross_task_report` chỉ đọc eligible artifacts.
- [ ] No official artifact contains mock, hard-coded or undocumented proxy metric.
- [ ] Every evaluated unit maps to frozen source, GT, split and checksum.
- [ ] Mỗi dataset có D0/D1 feasibility receipt; dataset được dùng chính thức có D2 receipt, peak disk và thời gian đo thật.
- [ ] Mỗi D2 dataset có profile/statistics/quality/attrition/leakage artifacts, đủ universal figures và modality-specific figures; mọi bảng/hình tái tạo được từ unit-level metadata.
- [ ] D1 pilot và D2 frozen statistics không bị trộn; mỗi số liệu/hình nêu revision, scope, split, `n`, unit và exclusion policy.
- [ ] Validation/test có 0 exact duplicate và 0 undocumented source/speaker/talk overlap; near-duplicate đã adjudicate trước freeze.
- [ ] Không có absolute `D:\\datasets` trong official runner; data/cache root đến từ config và được ghi vào run manifest.
- [ ] Full VISTA không chạy local; mọi large-scale dataset có storage profile hoặc fallback subset được pre-register.
- [ ] At least three genuinely different algorithm families are runnable for each core task where feasible; exceptions are justified as `not_eligible`.
- [ ] OD has box/class GT; tracking has trajectory/identity GT; summary has real references and factuality evidence; QA has answer and evidence GT.
- [ ] Raw predictions and failure denominator exist for every reported aggregate.
- [ ] Stage selection uses paired uncertainty and Pareto constraints, not rank by one composite score.
- [ ] `metric_registry.yaml` defines one frozen primary metric and complete scorer/matching/aggregation/failure contract per eligible task/track.
- [ ] Text and visual summaries use the same event/evidence timeline and 5/10/20% budgets; each is scored against its own official GT without merging metrics into one scalar.
- [ ] Derived unified multimodal records distinguish `ground_truth`, `prediction`, `source_metadata` and `evidence`; prediction fields are never consumed as official references.
- [ ] Shortlisted components are re-evaluated after integration under oracle and predicted inputs.
- [ ] E2E measurements cover duration/noise/resolution/codec strata and cold/warm runs.
- [ ] Report wording distinguishes implemented capability from measured scientific evidence.

## Remaining run-level decisions

1. Groq/OpenRouter token, monetary and rate-limit cap must be supplied before each API-backed LLM run; absent cap -> only that run is `blocked_decision`.
2. Exact dataset revisions and task-specific scorer thresholds are frozen during Phase 2 after source/schema probes, before final-test inference.
3. Colab session storage/time must be measured in D1; a task exceeding the observed T4 session envelope moves to a smaller labeled subset or `not_eligible`.

## Verification update — initial notebook run, 2026-09-26

The initial repair notebook completed with **228 passed, 1 failed**. The failure was an offline-environment test fixture; it was fixed and a final notebook rerun subsequently completed (see final verification below). This is not a final all-pass result. Both dataset drivers returned **3 (pending)**, both modality figure emitters returned **0**, both receipt validations returned no errors, and **151 historical files were unchanged**.

Universal EDA visualization is still incomplete. The universal SVG entries are placeholder cards, explicitly `render_status=not_rendered` with a pending reason; the notebook renderer must not present them as measured plots, and an eligible D2 declaration is rejected. Only **six audio and four image modality figures** are actual plots. A figure-manifest entry or existing SVG file is not proof of a rendered scientific figure. Universal plots, near-duplicate adjudication, independent TED holdout and endpoint coverage remain open gates.
## Final scoped repair verification — 2026-09-26

The final executed notebook recorded **233 passed in 113.54 seconds**, with **0 cell/infrastructure errors**. It generated 22 task notebooks; compileall returned 0. Outputs contain **10 PNG displays and 15 HTML displays**; these display counts are not a count of completed universal EDA plots. Both dataset drivers returned **3 (PENDING)**, both modality figure emitters returned **0**, receipt validation returned **[]** for both datasets, and **151 historical files remained unchanged**.

- Executed notebook (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/phase12-evidence-repair-20260926T094151043461Z.ipynb`.
- Fresh artifact root (nested app): `experiments/outputs/phase12_repair_260926/20260926T094154516917Z`.
- Supplemental shared-caller suite `tests/test_tedlium_qualification.py`: **11 passed in 24.62 seconds**, first attempt, no test edits. Combined confirmed total: **244 = 233 + 11**.

The scoped repair is complete. Scientific Phase 1/2 completion is not: full-DAG/equivalence, rendered universal EDA plots, near-duplicate adjudication, independent TED holdout/protocol and endpoint coverage remain pending. Six audio and four image modality plots are real; universal SVG cards remain explicitly not rendered. Phases 3–7 remain pending. The initial 228-pass/1-fail notebook and ACL issue are retained as execution history, not concealed by the successful rerun.
### Supplemental verification closeout

The qualification supplement passed **11 tests in 24.62 seconds** on its first run; combined verified total is **244 tests (233 + 11)**. `git diff --check` returned 0; only LF/CRLF warnings. Scoped review has no outstanding P1/P2 findings. No scientific gate is promoted by this additional contract coverage.

- Source (nested app): `experiments/notebooks/diagnostics/phase12_qualification_supplement.ipynb`.
- Executed copy (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/phase12_qualification_supplement-20260926T094714806867Z.ipynb`.
## Dataset-readiness follow-up — implementation checkpoint, 2026-09-26

A separate preparation pipeline now selects native TED validation/test after resolving and excluding all historical 20 utterances and their authoritative speaker/source groups. It targets 30 validation + 20 test units by frozen hash rank; failures are retained without replacement. IIIT switches to documented official Frames/val and Frames/test in a fresh namespace, with PNG/XML pairing and course-disjoint checks. The previous train-derived validation subset remains historical.

Selection/protocol are saved before decoding. Independent WAV/FLAC container lengths are checked; exact/decoded identity, image dHash and audio waveform screening use recorded comparison denominators and deterministic exclusion decisions. This bounded screening cannot prove semantic uniqueness. New split manifests remain `scientific_selection_eligible=false`; no official runner consumes them implicitly.

The new renderer is designed to produce sixteen actual universal plots across both datasets, with source hashes and honest N/A. Execution, final counts and visual verification are recorded in the final dataset-readiness section below. Earlier official-bundle SVG cards remain historical `not_rendered` placeholders; standalone preparation figures do not silently repair or promote those bundles. No model inference or D2 promotion is claimed.

The old seven-phase status snapshot is historical. Current dataset readiness and eligibility are described in `docs/DATASET_EDA.md` and the task-specific EDA evidence; no phase status in this plan opens a run.

## Initial readiness execution — historical checkpoint

The initial notebook completed **31 tests**, no errors, and **16 actual plots** in the new cohort namespace. Its bundle contained **122 files**; **602 historical files** and the separately tracked **82 pre-existing files from the dirty worktree** remained unchanged. This is preparation evidence, not official D2 eligibility.

| Dataset | Retained validation | Retained final test | Observed attrition |
|---|---:|---:|---|
| TED-LIUM | 26 | 16 | All 50 decoded; 8 excluded for ignored GT |
| IIIT-CVID | 546 | 1755 | 3 near-duplicate validation units excluded |

At the initial checkpoint, final verification was pending. Review found that nonempty ignored TED reference markers were counted as GT coverage, and GT exclusions incorrectly prevented media-fingerprint comparisons. Both paths were corrected: GT coverage must respect GT validity; media fingerprints are independent of GT eligibility so all **2,225** planned TED comparisons can execute (initial run completed **1,701**). The fixed protocol, thresholds and selected IDs are unchanged; no replacement units are selected.

The final notebook rerun tested these corrections; verified results are recorded below. Keep the initial notebook/results as history. The sixteen new plots are actual rendered plots, while old official-bundle SVG cards remain historical placeholders. No D2 promotion, model inference or full-phase completion is claimed.

## Final dataset-readiness verification — 2026-09-26

The corrected notebook passed **33 tests in 4.65 seconds**. All commands returned 0 and all cells completed with **0 errors**. Sixteen actual PNG plots were rendered and checked; corrected TED GT coverage is **26/30 validation** and **16/20 final test**. The zero-hit TED duplicate matrix represents completed comparisons, not missing measurements.

| Dataset | Completed / expected media comparisons | Detected hit pairs | Retained validation / final test | Decisions |
|---|---:|---:|---:|---|
| TED-LIUM | 2,225 / 2,225 | 0 | 26 / 16 | All 50 decoded; 8 ignored-GT units excluded; comparison still includes their media |
| IIIT-CVID | 2,653,056 / 2,653,056 | 6,455 | 546 / 1,755 | Hits mostly within split; 3 validation units excluded; 0 retained cross-split hits |

The final bundle contains **122 files**. **602 historical artifacts** and **82 pre-existing files from the dirty worktree** remained unchanged. Initial/final protocol and selection SHA-256 identities match: no refills or threshold changes occurred after inspecting results. Initial-run coverage/comparison issues and their corrections remain recorded above.

- Executed notebook (nested app): `experiments/outputs/executed_notebooks/phase12_repair_260926/dataset_readiness-20260926T101743497388Z.ipynb`.
- Fresh bundle (nested app): `experiments/outputs/dataset_readiness_260926/20260926T101747121197Z/bundle`.

The scoped preparation plan is complete. These fresh cohort plots and screening results do not overwrite the old official eight-card SVG bundles or promote them to D2. Split manifests retain `scientific_selection_eligible=false`; bounded screening is not proof of semantic uniqueness. No model inference was performed. Master Phase 1/2 remain in progress; Phases 3–7 remain pending.
