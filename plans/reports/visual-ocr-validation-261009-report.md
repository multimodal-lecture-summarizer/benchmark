# Visual OCR recognition benchmark — 2026-10-09

## Decision

**Keep PaddleOCR 2.8.1 as the provisionally stronger validation candidate for word-crop recognition.** On the same 15,379 released IIIT-CVID validation crops, PaddleOCR CPU reached micro CER **0.1172**, versus **0.2444** for EasyOCR 1.7.2 CPU. The difference (Paddle minus Easy) was **−0.1272**; a paired bootstrap over 140 source videos (2,000 draws, fixed seed 20261009) gave a 95% percentile interval of **[−0.1558, −0.0998]**. The expanded EDA below identifies possible reference-label conflicts that need source-owner adjudication before a stronger ground-truth claim. This is validation evidence for this crop-recognition endpoint, not a held-out test claim or a production model change.

## Source and cohort gate

- Source: IIIT-CVID / LectureVideoDB released archive, mirror `staghado/IIIT-CVid` revision `8159222f11460bff70bec7990ade19c468755fe4`. Archive SHA-256: `b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489`. The archive README supplies the crop-to-label mappings; no labels were authored for this study.
- Executed [EDA notebook](../../experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb): 549 validation frames with XML, 15,379 word PNGs with 15,379 labels, five courses, no missing/orphan/blank crop labels, no crop decode failures. Three invalid frame boxes and three XML-size mismatches prevent treating this as a detection/spotting result. The recognition run uses supplied word crops only.
- Final summarization recomputed SHA-256 of the 2.43 GB archive and compared size and CRC of all **15,384** selected extracted files (15,379 PNGs and five label maps) with its entries. It reloaded the current labels, checked exactly matching crop IDs and references between arms, and recomputed every stored edit distance and denominator. No row failed these gates.
- Train, validation and test course IDs in the archive are disjoint. No source test images or labels entered the OCR run. Historical work previously inspected test reference aggregates, so future test analysis cannot be called a pristine unseen holdout.

## Expanded visual EDA and benchmark preparation

The executed notebook now includes course/video coverage plots, per-course label and crop-geometry tables, label-length and image-size distributions, a fixed-rule 15-crop image gallery, a cross-video dHash candidate screen, and side-by-side inspection of candidate label conflicts. These plots use the complete validation crop cohort; the galleries use stated deterministic selection rules. They are input/label analysis, separate from model scoring.

- Course 19 contributes **7,757/15,379 crops (50.44%)** from 46 videos. Across all 140 videos, crop count ranges **4–435**, median **93.5**. A crop-level uncertainty estimate would overstate independent sample size; the benchmark therefore resamples videos.
- The labels have median length **4** characters; **1,684** are one character. Course mix differs: digit-bearing labels are **40.76%** in course 11 versus **1.78%** in course 19; punctuation-bearing labels are **14.19%** in course 6. Course-specific scores are necessary to interpret the overall CER. Pixel-intensity standard deviation is plotted as a descriptive image property, not a quality label.
- There are **zero exact-byte crop groups across different videos**. A dHash screen (Hamming distance ≤5, different source video) produced **10,251 candidate pairs**, all within the same course; **1,163 pairs involving 537 unique crops** have differing released labels. This is a *candidate queue*, not 1,163 proven duplicates or 537 proven bad labels. The [local review queue](../../experiments/outputs/ocr_validation_261009/eda_dhash_different_label_review.csv) retains both source IDs and labels. Fixed-rule visual examples include near-identical displayed text carrying different labels such as `gen:`/`gen` and `the`/`key`. The source labels were not modified; these records need authoritative annotation review.
- A sensitivity calculation that temporarily omits all 537 *flagged* crops, without changing the official cohort or saved primary score, gives EasyOCR CER **0.2475** and PaddleOCR CER **0.1174** on the other 14,842 crops. This supports the direction of this validation comparison, but the screen may miss other label errors and is not an exclusion rule.
- Recognition crops remain usable with an **annotation-review flag**. Frame-level detection/spotting remains held for its three invalid boxes and three XML-size mismatches. No output from this EDA qualifies the test split.

## Frozen evaluation

The [protocol](../261009-visual-ocr-recognition/plan.md) fixes the full released validation cohort, Unicode NFKC + casefold + collapsed-whitespace normalization, retained digits/punctuation, micro CER as total Levenshtein distance over total reference characters, and empty predictions counted as deletions. Both candidates used English recognition on supplied crops without tuning or candidate-specific filtering. Inference exceptions would be recorded and scored as empty outputs. CPU was the common device for the paired quality comparison; per-row device metadata was not saved, so this assignment rests on runner configuration and runtime logs. PaddlePaddle 2.6.2 reported a CPU-only build. The overlapping CPU runs do not support a latency or throughput comparison.

| Candidate | Version | Crops | Reference characters | Total edits | Micro CER | Exact word | Empty | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EasyOCR CPU | 1.7.2 | 15,379 | 73,654 | 18,000 | 0.2444 | 54.94% | 8 | 0 |
| PaddleOCR CPU | 2.8.1 | 15,379 | 73,654 | 8,630 | 0.1172 | 71.68% | 18 | 0 |

PaddleOCR had lower CER in all five validation courses:

| Course ID | Crops | EasyOCR CER | PaddleOCR CER |
| --- | ---: | ---: | ---: |
| 11 | 2,907 | 0.3799 | 0.1664 |
| 13 | 1,452 | 0.6455 | 0.2983 |
| 19 | 7,757 | 0.0575 | 0.0431 |
| 2 | 1,875 | 0.3881 | 0.1608 |
| 6 | 1,388 | 0.4993 | 0.2197 |

The course spread is large; course 19 supplies about half the crops and is easier for both systems. The video-cluster bootstrap addresses correlation between word crops from the same source video, but only within these five validation courses.

## Reproducibility receipts

- Per-crop EasyOCR CPU predictions: `experiments/outputs/ocr_validation_261009/easyocr_cpu_full.jsonl`, SHA-256 `93dfaa733cb6068a0152df63bd1c3122aba6e6260ad213bcf16a5ce7f93b1353`.
- Per-crop PaddleOCR CPU predictions: `experiments/outputs/ocr_validation_261009/paddleocr_full.jsonl`, SHA-256 `3d4c1be2b403672aa325a3ecf685e2042e9eb8bc6f153250f6c7e176dfed901b`.
- Paired summary: `experiments/outputs/ocr_validation_261009/paired_full.summary.json`, SHA-256 `699411901daefe2bf219fda4a5c1a74c850632cef0509f594ba9743678f73237`.
- Model checkpoints: EasyOCR English G2 SHA-256 `e2272681d9d67a04e2dff396b6e95077bc19001f8f6d3593c307b9852e1c29e8`; Paddle English PP-OCRv4 `inference.pdiparams` SHA-256 `75f64a1ffb70c56b7a25655963ca16f5bf3286202e3f52ac972bee05cdee2f56`, `inference.pdmodel` SHA-256 `85b952f05f709af259cfe4254012aaf71f57a15495446f25ccd43`.
- An earlier EasyOCR GPU full run produced CER 0.2443 and remains diagnostic only, outside the paired CPU result.
- Runner: [ocr_validation_recognition.py](../../experiments/scripts/ocr_validation_recognition.py); paired audit: [summarize_ocr_validation.py](../../experiments/scripts/summarize_ocr_validation.py). `python -m pytest tests/test_ocr_validation_recognition.py -q`: **4 passed**; Python compilation passed. The test process emitted a `pyreadline3` destructor warning after exit code 0.
- The expanded EDA notebook has **10 executed code cells, eight embedded PNG figures and zero error outputs**. Its cells were executed in-process and the resulting tables/figures saved into the notebook because the local `nbclient` kernel stalled; a fresh Jupyter-kernel replay has not been verified.
- Dataset, model and result files are Git-ignored and remain local. The report and code are uncommitted; unrelated RQ2 working-tree changes were preserved.

## Limits and next gate

This assesses OCR **recognition** on provided word crops. It does not measure text localization, frame-level spotting, caption quality, slide transition detection, or the application OCR pipeline. The five validation courses are a finite source cohort. No independent test score, cross-dataset generalization, runtime ranking, or production default decision follows from this result.

## Unresolved questions

- Can the validation frame/XML anomalies be adjudicated before a separate detection and spotting benchmark?
- What independent lecture-video corpus can serve as a truly unseen generalization test?
- Can the dataset creator or an authorized annotator adjudicate the differing-label crop pairs before formal ground-truth claims?
