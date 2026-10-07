# Benchmark protocol for lecture video

## Current research sequence

1. **Select data and candidates.** For each task, identify a lecture-domain dataset with existing labels that match the exact target. Record source, revision, rights, media access, annotation origin, evaluation unit and split. Propose at least two meaningful model or algorithm families when feasible. Fix the metric, matching rules, normalization and common compute budget before looking at scores.
2. **Run task-specific EDA.** Create a notebook only when data are available. Reconcile selected, observed, missing and excluded units. Inspect media and labels, distribution, duplicates, leakage and failure groups. Name every sampled inspection as a sample. Record a keep, repair, restrict or reject decision. See [Dataset EDA](DATASET_EDA.md).
3. **Run task-specific evaluation.** After freezing the cohort, compare candidates on the same units, ground truth, metric and resource profile. Save item-level predictions, failures, configuration and run receipts. Report paired uncertainty when comparing systems. If labels or a complete comparison are missing, record `not_eligible` or `no_selection`; do not name a winner.

Only suitable lecture-domain data qualify. A general-video benchmark is not a fallback. Do not create placeholder or smoke notebooks. The [on-demand manifest](../experiments/notebooks/notebook_manifest.yaml) currently lists no active notebooks.

## Task matrix

The datasets and algorithms below are **candidates to qualify**, not completed selections. A source with lecture media but no task-specific ground truth remains ineligible for that task. The [candidate registry](../experiments/registry/candidates.yaml) and [metric registry](../experiments/registry/metric_registry.yaml) contain proposals, including parameters still marked pending; freeze applicable entries for each actual run.

| Task or track | Lecture-domain data to qualify | Candidate families | Common primary metric |
|---|---|---|---|
| Slide transition / scene boundary | MLPDataset has slide-transition annotations; MaViLS alignment alone does not prove general scene GT. General scene target remains unqualified. | Fixed grid, content difference, learned transition detector. | One-to-one boundary F1 at a fixed collar, only for the annotated target. |
| Board keyframes | AccessMath or LectureMath, subject to media, rights and required-state label audit. | Midpoint, embedding clustering, OCR-aware salience. | Required-state or scene F1 at a fixed frame budget. |
| OCR recognition and spotting | LectureVideoDB / IIIT-CVID frame and text annotations, after label/media audit. | Tesseract, EasyOCR, PaddleOCR. | CER for recognition; spotting Hmean for end-to-end spotting. Separate tracks. |
| Visual caption and grounding | No qualified lecture caption or visual-evidence GT yet. | BLIP-class, Florence-class, VLM if the same target can be scored. | CIDEr with multi-reference captions, or grounded-support F1 with evidence GT. |
| Detection A: slide/board elements | LVVO annotated boxes for table, chart, photo and illustration require media, rights and taxonomy verification. | YOLO, RT-DETR, Florence under one fixed four-class taxonomy. | COCO mAP@[.50:.95]. OCR text detection is a separate track. |
| Detection B: people, objects and devices | No qualified lecture-video box GT for these classes yet. | YOLO, RT-DETR, Florence after one common taxonomy is fixed. | COCO mAP@[.50:.95] within track B. Do not combine A and B ranks. |
| Multi-object tracking | No qualified lecture-video persistent-ID GT yet. | ByteTrack, BoT-SORT with a shared detector. | HOTA on the same videos and detector. |
| Summarization (RQ2) | Creator TIB: inspect all pinned `train`, `valid`, `test` records, no genre filter. VISTA needs full media/GT qualification. No evaluation cohort is frozen. | Equal-generator and equal-token fixed chunk S1 versus hierarchy S3 first; other arms only with suitable inputs. | The prior automatic protocol predeclared paired ROUGE-L F1 against nonempty creator abstracts. Reconcile it with full-split reference suitability before a new run; it measures abstract agreement, not factuality. |
| Retrieval and QA (RQ3) | EduVidQA needs source/media/label qualification. The local EduViQA snapshot is a different dataset. | BM25, dense, hybrid or reranked retrieval with a fixed reader. | Recall@k for retrieval and token F1 for QA, as separate tracks. |
| System efficiency (RQ4) | Same lecture units with suitable GT for each compared stage; currently not qualified by a shared corpus. | Fixed pipeline compositions. | Predeclared quality gate plus latency, VRAM and cost Pareto analysis on one hardware profile. |

RQ1 chaptering and ASR are not scheduled for rerun. The [ASR report](results/asr-architecture-evaluation-2026-10-05.md) preserves a completed six-candidate diagnostic comparison. Saved chaptering and summarization results were withdrawn for reanalysis. No row above becomes a completed benchmark merely because a runner or registry entry exists.

## Ground truth and reporting rules

- Match the **annotation target** exactly. Slide transitions, semantic chapter starts, generic scene cuts, keyshots, text boxes and object boxes are different labels. Do not relabel one as another without an independently documented protocol.
- Record annotation source, annotator or creator when known, method, release, rights and source-video linkage. Missing provenance is a hold, not a self-generated replacement label.
- State the denominator at every step: source records, accessible media, valid labels, evaluated units and failures. Preserve excluded IDs and reasons.
- Keep train/validation/test boundaries and grouping visible. Check exact duplicates and plausible near-duplicates; a hash match alone cannot rule out related content. If labels or references from a test split are inspected during EDA, do not describe that split later as unseen.
- If media inspection is sampled, record the sampling rule and coverage. Metadata coverage does not imply that every frame or audio sample was decoded.
- Use the same metric implementation and task inputs for all candidates within a track. Compare paired item-level outputs, show uncertainty and failure cases. Report resource conditions separately when they differ.
- Do not treat provided abstracts or lexical overlap as verified factuality. Validate reference suitability before using ROUGE or other reference metrics.

## Evidence status and locations

[Dataset EDA](DATASET_EDA.md) tracks executed versus pending inspection. [Model selection](MODEL_SELECTION_README.md) separates observed outcomes from proposals. The [master plan](../plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) states open research questions, and the [RQ2 plan](../plans/261002-0946-rq2-controlled-summarization/plan.md) describes the next summarization comparison. Older plans and repair reports may describe retired contracts or runners; they are historical records rather than executable instructions.

The TIB all-split EDA notebook exists but has not been executed across the pinned full dataset. Its planned reading of creator `test` references will make that split ineligible for an unseen-holdout claim. VISTA validation media inspection has partial evidence only. The previous 20- and 70-item TIB comparison outputs were withdrawn. Preserve the code and provenance of historical notebooks without presenting their old scores as current results.

The [RQ2 protocol amendment](../plans/261002-0946-rq2-controlled-summarization/rq2-automatic-evaluation-amendment.md) explicitly removes blinded and other human scoring. The 20-item TIB audit found no abstract qualified as a formal factual-summary reference, so the earlier automatic metric cannot be described as factuality evidence. See the [per-record audit](../plans/reports/rq2-valid-dataset-audit-261002-report.md) until its findings have been incorporated into the full-split EDA.
