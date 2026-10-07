---
title: "Metric coverage audit for scientific benchmark pipeline"
description: "Audit current model and algorithm metrics against the thesis outline and a stronger research-grade protocol."
status: completed
created: "2026-09-21T21:03:20+07:00"
scope: "plans/260921-1943-scientific-benchmark-pipeline"
---

# Metric Coverage Audit for Scientific Benchmark Pipeline

## Navigation

- [Summary](#summary)
- [Coverage Matrix](#coverage-matrix)
- [Metric Contract Rules](#metric-contract-rules)
- [Human Evaluation Contract](#human-evaluation-contract)
- [Statistical Selection Gate](#statistical-selection-gate)
- [Sources](#sources)
- [Recommendations](#recommendations)
- [Unresolved Questions](#unresolved-questions)

## Research Methodology

- Audited current plan phases 2, 4, 5, 6 and 7 against the thesis outline.
- Source types: NIST evaluation material, COCO evaluation specification, peer-reviewed ACL/CVPR papers and official open-access proceedings.
- Audit date: 2026-09-21.
- Scope: metric validity and coverage; no benchmark was executed and no current score was reclassified.

## Summary

Current plan satisfies the outline's named minimums: ASR WER; detection Precision/Recall/mAP; summary ROUGE/BERTScore; system timing/success/length strata. It is not yet complete enough for defensible component selection. ASR, detection/tracking, chaptering and system telemetry are structurally strong. Keyframe, caption/VLM, summary factuality, evidence-grounded QA, diarization and human agreement need explicit metric contracts.

No single scalar should select a winner. Pre-register one primary quality metric per task/profile, keep secondary diagnostic metrics, and combine quality with latency/memory/cost/failure only through Pareto selection.

## Coverage Matrix

| Task | Current plan | Assessment | Required primary metric | Required secondary/diagnostic metrics |
|---|---|---|---|---|
| ASR | WER, CER, latency, RTF, failure | Correct; normalization and aggregation unspecified | English: corpus WER; Vietnamese/bilingual track: language-appropriate WER plus CER | S/D/I counts, macro per-talk WER, utterance failure/empty rate, timestamp error when alignment matters, RTF, peak memory |
| VAD/diarization | Not explicit as independent metric contract | Missing if speaker/VAD remains in claimed pipeline | VAD: duration-weighted miss + false alarm or segment F1; diarization: DER | JER, speaker confusion/miss/false alarm decomposition; cpWER/SA-WER for speaker-attributed ASR |
| Scene boundary | Collar P/R/F1, over/under-segmentation | Mostly correct | One-to-one matched boundary F1 at pre-registered collar | P/R, matched-boundary absolute time error, false positives per minute, segment-count error, multiple collar sensitivity |
| Keyframe | Diversity, coverage, FPS | Too vague | Must-keep/required-scene Recall or F1 under a fixed frame budget | Precision, scene coverage, temporal coverage, redundancy, downstream QA/summary delta, latency; always include uniform/random baselines |
| OCR text detection | Detection F1 | Incomplete | IoU-matched detection Hmean/F1 at fixed threshold | P/R, AP where multiple confidence thresholds exist, empty-prediction rate, small-text/condition strata |
| OCR recognition/spotting | CER, WER, exact, word accuracy | Correct but mixed with detection | CER for recognition; end-to-end spotting Hmean for full OCR | WER, word accuracy, normalized edit distance, exact match, empty-output rate, latency/frame |
| Caption/VLM | Semantic/factual support, latency | Insufficient and undefined | Claim/object support precision against image/video evidence or human-grounded adequacy | CIDEr/SPICE when multi-reference captions exist; BERTScore; PAC-S/CLIPScore as diagnostic; object hallucination rate; human relevance, specificity and fluency |
| Object detection | mAP50-95, AP50, per-class AP, P/R | Strong | COCO-style AP@[.50:.95] within a fixed label-space track | AP50/AP75, per-class AP, AP by object size, AR, P/R, calibration if confidence is consumed downstream |
| Multi-object tracking | HOTA, IDF1, MOTA, IDSW, fragmentation | Strong; HOTA decomposition missing | HOTA under fixed detector input | DetA, AssA, LocA, IDF1, MOTA as diagnostic, ID switches, fragmentation, mostly-tracked/lost, FPS |
| Chaptering/topic segmentation | Pk, WindowDiff, boundary F1, duration bias | Good; add interpretable boundary alignment | Boundary F1 or Boundary Similarity at a fixed tolerance | Pk and WindowDiff with declared unit/window, segment-count error, duration error; title relevance if chapter titles generated |
| Text/video summary | ROUGE-L, BERTScore, factuality/support, coverage, human rubric | Correct minimum; underspecified for multimodal factuality | Human-supported claim F1 or pre-registered relevance/coverage score; ROUGE-Lsum only when reference summaries exist | ROUGE-1/2/Lsum, BERTScore, claim precision/recall, QAFactEval or SummaC as calibrated diagnostic, citation support/coverage, compression ratio, redundancy, blinded human factuality/relevance/coverage/coherence/fluency |
| Video-summary/keyshot output | Not clearly separated from text summary/keyframe | Missing if system outputs a visual summary | F1 against human keyshot summaries under identical length budget | Kendall/Spearman importance agreement where dense scores exist, diversity, coverage, random/uniform and leave-one-annotator baselines; report aggregation rule over references |
| Retrieval | Recall@k, MRR, nDCG | Good | Recall@k for evidence completeness or nDCG@k for graded relevance | Precision@k, MRR only for first-relevant use case, MAP for multiple relevant items, latency/query, empty-retrieval rate |
| QA/generation | EM/F1, citation P/R | Good base; grounding/abstention missing | Answer EM/token F1 for short answers; human correctness for free-form answers | Faithfulness/groundedness, claim-level citation correctness and completeness, evidence Recall@k/timestamp overlap, hallucination rate, unanswerable abstention F1 and risk-coverage |
| End-to-end system | Wall/stage time, RTF, RAM/VRAM, cost, success/failure, cold/warm | Strong | Video-level task success plus final summary/QA quality on fixed pipeline | p50/p95 latency, throughput, peak memory, cost/video, retry/timeout/OOM rate, stage failure attribution, duration/resolution/codec/noise strata |

## Metric Contract Rules

1. Pre-register one primary metric and direction per task and deployment profile. Do not select a different primary after final results.
2. Specify scorer implementation/version, tokenization/normalization, matching algorithm, IoU/collar/k, aggregation level and missing/failure policy.
3. Compute raw metrics per independent talk/video, plus corpus aggregate where mathematically appropriate. Frame/word/query rows are not independent `n`.
4. Keep closed-vocabulary and open-vocabulary detection in separate tracks unless a fixed taxonomy mapping exists.
5. Keep OCR detection, recognition-only and end-to-end spotting results separate.
6. Evaluate trackers under frozen detections first; detector+tracker composition is an integration experiment.
7. Reference-free caption/factuality scores are diagnostic until calibrated against human judgments in the lecture domain.
8. For summaries, separate relevance/coverage from factual support. ROUGE or BERTScore alone cannot establish factual correctness.
9. For RAG, separate retrieval quality, answer correctness, evidence/citation correctness and abstention. A correct answer without supporting evidence does not pass grounding.
10. Every aggregate reports denominator, failure count, paired uncertainty and practical threshold. Missing/failed rows are not zero-imputed.

## Human Evaluation Contract

- Blind candidate identity and randomize/counterbalance presentation order.
- Use at least two independent annotators per item; prefer three for the final subset when budget permits.
- Summary dimensions: factuality, importance/relevance, coverage, coherence, fluency, non-redundancy and evidence traceability.
- Caption dimensions: visual support, specificity, hallucination, usefulness and fluency.
- Report Krippendorff's alpha for nominal/ordinal multi-rater labels or weighted Cohen's kappa for exactly two ordinal raters; include bootstrap CI and adjudication rate.
- Pairwise preference must report win/tie/loss with paired CI; Elo/Bradley-Terry can be secondary, not a replacement for raw judgments.
- Automatic judge output cannot be the sole final-test evidence; validate correlation/agreement against a human-labeled subset.

## Statistical Selection Gate

- Primary comparisons use paired talk/video-level bootstrap or permutation; hierarchical bootstrap when units cluster by speaker/source.
- Report candidate delta, 95% CI, effect size and practical threshold.
- Apply Holm correction within pre-registered task/metric comparison families.
- Require minimum quality constraints before Pareto analysis. Pareto dimensions: primary quality, latency/RTF, peak memory/cost and failure rate.
- Return `tie/indistinguishable` or `no_selection` when CI or evidence does not support a winner.

## Sources

- NIST lists WER as the primary OpenASR metric: https://www.nist.gov/itl/tted/mltg/openasr20-challenge-results
- NIST Rich Transcription covers STT, diarization and speaker-attributed STT: https://www.nist.gov/publications/rich-transcription-2007-meeting-recognition-evaluation
- COCO detection evaluation uses AP over IoU 0.50:0.05:0.95 and AR: https://presentations.cocodataset.org/ECCV18/COCO18-Detect-Overview.pdf
- HOTA balances detection, association and localization and exposes decomposed errors: https://arxiv.org/abs/2009.07736
- Segmentation metrics have different behaviors; boundary, WindowDiff and alignment measures are complementary: https://aclanthology.org/L14-1709/ and https://aclanthology.org/2022.conll-1.26/
- Standard video-summary F1 can be misleading without fixed budgets and baselines: https://openaccess.thecvf.com/content_CVPR_2019/papers/Otani_Rethinking_the_Evaluation_of_Video_Summaries_CVPR_2019_paper.pdf
- PAC-S reports stronger human correlation than several caption metrics across image/video settings: https://openaccess.thecvf.com/content/CVPR2023/html/Sarto_Positive-Augmented_Contrastive_Learning_for_Image_and_Video_Captioning_Evaluation_CVPR_2023_paper.html
- ROUGE relevance does not establish factuality in long summaries: https://aclanthology.org/2022.emnlp-main.172/
- QAFactEval and SummaC provide complementary QA/NLI factuality diagnostics: https://aclanthology.org/2022.naacl-main.187/ and https://aclanthology.org/2022.tacl-1.10/
- Citation/evidence evaluation must distinguish full, partial and unsupported claims: https://aclanthology.org/2024.inlg-main.35/

## Recommendations

1. Add a task-level metric registry with primary, secondary, diagnostic, direction, scorer version and parameters.
2. Expand Phase 4 into separate contracts for ASR/VAD/diarization, scene, keyframe, OCR, caption, detection, tracking, chaptering, text summary, visual summary, retrieval and QA.
3. Add human-evaluation agreement and automatic-metric calibration gates to Phase 2/4/5.
4. Add metric sanity fixtures: perfect, empty, shifted-boundary, duplicate, hallucinated, wrong-citation and failed-run cases.
5. Do not claim completeness until every eligible task has GT, scorer, raw prediction schema and executable test.

## Unresolved Questions

1. Speaker diarization có nằm trong phạm vi benchmark chính thức hay chỉ là future work?
2. Hệ thống sinh text summary, visual/keyshot summary, hay cả hai? Hai đầu ra cần metric khác nhau.
3. Ngôn ngữ chính là English, Vietnamese hay bilingual? Điều này quyết định ASR normalization và metric primary.
4. Caption và summary có multi-reference human GT hay chỉ evidence annotations? Điều này quyết định dùng reference-based hay grounded claim metrics làm primary.
