# Benchmark protocol for lecture video

## Current research sequence

**Claim-scoped qualification:** use the [research question matrix](../../plans/reports/research-scope-261010-1621-claim-qualification-report.md). Input/GT gates apply to the precise comparison: released-image OCR/detection does not require original video recovery; text-only QA needs source context but not necessarily video timestamps; retrieval evidence quality needs independent relevance/evidence labels. Fixed-cohort descriptive scores, fine-tuned held-out performance and unseen generalization have different leakage requirements. Do not impose the strongest claim's gates on every narrower endpoint. Every actual run still needs its cohort, scorer, failure policy and claim fixed before outcomes are inspected.

1. **Select data and candidates.** For each task, identify a lecture-domain dataset with existing labels that match the exact target. Record source, revision, rights, media access, annotation origin, evaluation unit and split. Propose at least two meaningful model or algorithm families when feasible. Fix the metric, matching rules, normalization and common compute budget before looking at scores.
2. **Run task-specific EDA.** Create a notebook only when data are available. Reconcile selected, observed, missing and excluded units. Inspect media and labels, distribution, duplicates, leakage and failure groups. Name every sampled inspection as a sample. Record a keep, repair, restrict or reject decision. See [Dataset EDA](DATASET_EDA.md).
3. **Run task-specific evaluation.** After freezing the cohort, compare candidates on the same units, ground truth, metric and resource profile. Save item-level predictions, failures, configuration and run receipts. Report paired uncertainty when comparing systems. If labels or a complete comparison are missing, record `not_eligible` or `no_selection`; do not name a winner.

Only suitable lecture-domain data qualify. A general-video benchmark is not a fallback. Do not create placeholder or smoke notebooks. The [on-demand manifest](../experiments/notebooks/notebook_manifest.yaml) currently lists no active notebooks.

## Active TIB RQ2 route

The integrated evaluation includes primary ROUGE-L F1, secondary BERTScore F1 (abstract reference) and source-based SBERTScore (full transcript). Each metric reports paired S3−S1 bootstrap CI95 and scoring coverage. Per-arm segmentation/generation time, call counts, actual tokens and optional absolute GPU peaks are reported separately from shared preparation and metric evaluation. Saved generation is reused when evaluation configuration changes. Semantic scoring runs on CPU by default; model revisions and long-input extensions are recorded.

Run the [integrated benchmark notebook](../experiments/notebooks/rq2-tib-benchmark-colab.ipynb) on GPU. Its `run_benchmark` entry point automatically calls `load_or_prepare_data`, then executes paired S1/S3 generation and scoring. No prior preparation run is required; the same entry point creates `tib-benchmark-data.jsonl.gz` if absent and reuses it when present. This includes full ordered segment text, timestamps, creator abstracts, ID/content hashes, exclusion IDs and the S1/S3 preparation configuration. Reference flags and manual review do not gate this study. The endpoint is creator-abstract agreement. The older 20-/70-item runners are not used by this preparation route.

## Task matrix

The datasets and algorithms below are **candidates to qualify**, not completed selections. A source with lecture media but no task-specific ground truth remains ineligible for that task. The [candidate registry](../experiments/registry/candidates.yaml) and [metric registry](../experiments/registry/metric_registry.yaml) contain proposals, including parameters still marked pending; freeze applicable entries for each actual run.

| Task or track | Lecture-domain data to qualify | Candidate families | Common primary metric |
|---|---|---|---|
| Audio ASR (Diagnostic completed) | TED-LIUM Release 3 (507 validation units, 1,155 native-test units). Diagnostic run completed; no rerun scheduled. | 6 architecture families: Whisper encoder-decoder (A0 Whisper Base), Wav2Vec2 CTC (A1), FastConformer CTC (A2), FastConformer RNNT (A3), Paraformer English (A4), Qwen3-ASR 0.6B (A5). | Micro WER and CER under NFKC US normalization (`english-asr-nfkc-apostrophe-us-v1`). |
| Slide transition / scene boundary | MLPDataset has slide-transition annotations; MaViLS alignment alone does not prove general scene GT. General scene target remains unqualified. | Fixed grid, content difference, learned transition detector. | One-to-one boundary F1 at a fixed collar, only for the annotated target. |
| Board keyframes | AccessMath or LectureMath, subject to media, rights and required-state label audit. | Midpoint, embedding clustering, OCR-aware salience. | Required-state or scene F1 at a fixed frame budget. |
| OCR recognition and spotting | LectureVideoDB / IIIT-CVID frame and text annotations, after label/media audit. | Tesseract, EasyOCR, PaddleOCR. | CER for recognition; spotting Hmean for end-to-end spotting. Separate tracks. |
| Visual caption and grounding | No qualified lecture caption or visual-evidence GT yet. | BLIP-class, Florence-class, VLM if the same target can be scored. | CIDEr with multi-reference captions, or grounded-support F1 with evidence GT. |
| Detection A: slide/board elements | LVVO annotated boxes for table, chart, photo and illustration require media, rights and taxonomy verification. | YOLO, RT-DETR, Florence under one fixed four-class taxonomy. | COCO mAP@[.50:.95]. OCR text detection is a separate track. |
| Detection B: people, objects and devices | No qualified lecture-video box GT for these classes yet. | YOLO, RT-DETR, Florence after one common taxonomy is fixed. | COCO mAP@[.50:.95] within track B. Do not combine A and B ranks. |
| Multi-object tracking | No qualified lecture-video persistent-ID GT yet. | ByteTrack, BoT-SORT with a shared detector. | HOTA on the same videos and detector. |
| Summarization (RQ2) | TIB all-split EDA completed; 8,769 candidates, no genre or sample-size cap. [Integrated benchmark](../experiments/notebooks/rq2-tib-benchmark-colab.ipynb) automatically prepares and uses the full pool. | Same-generator fixed chunk S1 versus source-only predicted hierarchy S3. | Paired ROUGE-L F1 against creator abstracts; report overall and genre/subject/duration groups. |
| Retrieval and QA (RQ3) | EduVidQA needs source/media/label qualification. The local EduViQA snapshot is a different dataset. | BM25, dense, hybrid or reranked retrieval with a fixed reader. | Recall@k for retrieval and token F1 for QA, as separate tracks. |
| System efficiency (RQ4) | Same lecture units with suitable GT for each compared stage; currently not qualified by a shared corpus. | Fixed pipeline compositions. | Predeclared quality gate plus latency, VRAM and cost Pareto analysis on one hardware profile. |

RQ1 chaptering and ASR are not scheduled for rerun. The [ASR report](results/asr-architecture-evaluation-2026-10-05.md) preserves the completed six-candidate diagnostic comparison (Qwen3-ASR 0.6B ranked first on validation WER at 3.91%). Saved chaptering and summarization results were withdrawn for reanalysis. No row above becomes a completed benchmark merely because a runner or registry entry exists.

## Ground truth and reporting rules

- Match the **annotation target** exactly. Slide transitions, semantic chapter starts, generic scene cuts, keyshots, text boxes and object boxes are different labels. Do not relabel one as another without an independently documented protocol.
- Record annotation source, annotator or creator when known, method, release, rights and source-video linkage. Missing provenance is a hold, not a self-generated replacement label.
- State the denominator at every step: source records, accessible media, valid labels, evaluated units and failures. Preserve excluded IDs and reasons.
- Keep train/validation/test boundaries and grouping visible. Check exact duplicates and plausible near-duplicates; a hash match alone cannot rule out related content. If labels or references from a test split are inspected during EDA, do not describe that split later as unseen.
- If media inspection is sampled, record the sampling rule and coverage. Metadata coverage does not imply that every frame or audio sample was decoded.
- Use the same metric implementation and task inputs for all candidates within a track. Compare paired item-level outputs, show uncertainty and failure cases. Report resource conditions separately when they differ.
- For the current TIB creator-abstract agreement track, the completed EDA is the data screen and no additional manual review is required. Other tasks keep their task-specific label requirements.

## Evidence status and locations

[Dataset EDA](DATASET_EDA.md) tracks executed versus pending inspection. [Model selection](MODEL_SELECTION_README.md) separates observed outcomes from proposals. The [master plan](../plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) states open research questions, and the [RQ2 plan](../plans/261002-0946-rq2-controlled-summarization/plan.md) describes the next summarization comparison. Older plans and repair reports may describe retired contracts or runners; they are historical records rather than executable instructions.

The TIB all-split EDA completed all 10 code cells for 9,103 records and retained **8,769 candidates**, including all 900 candidates with screening flags. Use the [integrated benchmark notebook](../experiments/notebooks/rq2-tib-benchmark-colab.ipynb); preprocessing is called inside the benchmark itself. It selects every candidate automatically, measures full-source token counts and saves one reusable gzip JSONL file. Report paired creator-abstract ROUGE-L agreement overall and by genre/subject/duration. The [active RQ2 plan](../plans/261002-0946-rq2-controlled-summarization/plan.md) replaces the older manual qualification gates. VISTA remains outside this run; historical 20-/70-item comparisons are retired.

The [RQ2 protocol amendment](../plans/261002-0946-rq2-controlled-summarization/rq2-automatic-evaluation-amendment.md) explicitly removes blinded and other human scoring. The 20-item TIB audit found no abstract qualified as a formal factual-summary reference, so the earlier automatic metric cannot be described as factuality evidence. See the [per-record audit](../plans/reports/rq2-valid-dataset-audit-261002-report.md) until its findings have been incorporated into the full-split EDA.
