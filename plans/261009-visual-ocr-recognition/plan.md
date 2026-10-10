# IIIT-CVID validation word recognition

## Scope and frozen protocol — 2026-10-09

Evaluate OCR **recognition on supplied word crops**, separately from text detection and end-to-end spotting. Source: `staghado/IIIT-CVid` revision `8159222f11460bff70bec7990ade19c468755fe4`; archive SHA-256 `b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489`. The released `Readme.txt` defines `Crops/val/<course>/Id-Label.txt` as word crop-to-label mappings.

The cohort is all **15,379** labeled PNG crops in the released validation split, across five courses. The [executed EDA notebook](../../experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb) accounted for 549 source frames and XML pairs, 15,379 crops and labels, no missing/orphaned/blank labels, and no crop decode errors. Archive path inspection found zero course-ID overlap between source train, validation and test. Three invalid frame boxes and three XML size mismatches affect detection/spotting qualification; the released crop images and labels remain the recognition input. Do not use the source test split for candidate selection. Historical test reference aggregates were already inspected, so future test results cannot be described as a pristine unseen holdout.

Expanded visual EDA shows course/video imbalance and cross-video dHash candidate pairs with differing released labels. These are annotation-review signals, not automatic exclusions or corrected ground truth. Keep the full validation cohort and report the candidate ranking as provisional until the source-label conflicts are adjudicated; see the [evaluation report](../reports/visual-ocr-validation-261009-report.md).

Compare **EasyOCR English recognition** and **PaddleOCR English recognition** on the same 15,379 crops, both on CPU. The installed PaddlePaddle 2.6.2 build reports `is_compiled_with_cuda=False`, so CPU is the shared execution device. An EasyOCR CUDA full run completed before this environment check; retain it as a separate diagnostic and exclude it from the paired CPU comparison. No model tuning, lexicon, candidate-specific filtering, reference-driven image preprocessing or retry on only one arm. Save per-crop prediction, reference, error and engine identity. Both CPU arms must finish the same cohort before a ranking. A bounded diagnostic prefix verifies execution only and cannot be called the benchmark result.

Primary outcome: **micro character error rate (CER)**, sum of Levenshtein edit distances divided by sum of reference character counts. Before scoring, both reference and prediction use Unicode NFKC, casefold and collapsed whitespace; punctuation and digits remain. An empty prediction counts as deletions. An inference exception records an error and an empty prediction; report failure counts, never drop failed units selectively. Report candidate versions, model/device, source hash, denominator, empty outputs, per-course breakdown and paired uncertainty with the final result. No test metrics or OCR detection scores are part of this comparison.

The CPU runs may overlap, so elapsed time, throughput and cost are outside this study. The common device setting controls the recognition path; only paired quality outcomes are compared.

Code: [validation recognition runner](../../experiments/scripts/ocr_validation_recognition.py). Local source/model caches and prediction outputs remain Git-ignored. The older `benchmarks/scripts/run_ocr_benchmark.py` has a fabricated OpenCV text proxy and full-frame fallback box; it is excluded from this comparison.

## Completion gate

1. Both real engines load and complete the validation cohort; all per-item outputs are saved.
2. Verify the two output files contain exactly the same 15,379 IDs, no duplicates or missing rows, and summarize paired CER and failures.
3. If either engine or cohort fails, report partial/blocked and no winner.

## Unresolved questions

- Whether frame-level detection and spotting can be qualified after the six validation frame/XML anomalies are adjudicated.
- Whether a separate untouched external test corpus is available for independent generalization claims.
- Whether the dataset creator or an authorized annotator can adjudicate the differing-label crop pairs.
