# IIIT-CVID frame anomaly adjudication — 2026-10-10

## Scope and decision rule

Local data contain only the released **validation** split. The [executed notebook](../../experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb) reread all 549 PNG/XML frame pairs, 15,379 XML objects, and the 15,379 released word crops. It did not rerun OCR inference. The [549-row ID ledger](ocr-iiit-cvid-validation-frame-adjudication-261010.csv) records the decision for every local frame.

Rules stated before inspection in the notebook:

1. **KEEP** a decodable frame with parsable XML, nonblank object names, boxes within decoded PNG bounds, and matching XML size.
2. **REPAIR_METADATA_DERIVED** when only XML size differs and all boxes fit the PNG. Use decoded PNG dimensions in derived evaluation metadata; preserve source XML and record both values.
3. **HOLD_BOX_OR_LABEL** if any object box is outside PNG bounds or a label is blank. Do not silently clip even a one-pixel overrun. Keep the frame out of a frame-level box or spotting cohort until an authorized annotation decision.
4. dHash similarity is a review candidate. Exclude neither image automatically. Cross-split decisions require both images, source course/video identity, and content/label review.

## Local validation findings

| Decision | Frames | Evidence |
| --- | ---: | --- |
| KEEP | 543 | PNG/XML parsed; nonblank labels; boxes in image; sizes agree. |
| REPAIR_METADATA_DERIVED | 3 | XML size is `2×1`, while decoded PNGs are `608×482`, `960×546`, and `1280×720`; all their object boxes fit PNG bounds. |
| HOLD_BOX_OR_LABEL | 3 | Each has one box with `xmax` one pixel beyond decoded image width. The three source images are displayed with the offending box in the notebook; text/object content touches the image edge. |

The three metadata-only IDs are `11/27/00_45_38_00009.png`, `19/11/00_16_20_00005.png`, and `2/11/00_04_59_00001.png`. The three held IDs are `2/23/00_20_38_00006.png` (object 4, `p5`, `xmax=1281` for width 1280), `6/1/00_43_16_00008.png` (object 7, `r-d`, `xmax=641` for width 640), and `6/4/01_16_06_00008.png` (object 6, `hand`, `xmax=641` for width 640). Indexes are zero-based. Their original coordinates and dimensions are in the CSV.

| Scope | Selected | Observed | Label-valid geometry | Media-valid PNG | Evaluated for frame-box endpoint | Failed acquisition/parse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Local validation frames | 549 | 549 | 546 after derived size repair | 549 | 0 | 0 |

`Label-valid geometry` means nonblank names and in-bounds boxes after the stated metadata correction. It does **not** certify transcription truth. The three held frames are out of the provisional frame-box denominator of 546; this is not a final benchmark cohort. The existing word-crop recognition result uses its own 15,379-crop denominator and is not recomputed here.

## Historical full-source receipt and unresolved split review

The historical [full-corpus EDA aggregate](../../experiments/outputs/full_corpus_eda_261003/iiit_cvid.json) reports 5,475 frames, 22 invalid **boxes** across 20 frames (train 18 boxes/16 frames, validation 3/3, test 1/1), and 124 XML-size mismatches (train 23, validation 3, test 98). Its mismatch ID lists are truncated to 20 examples per split. This aggregate has not been reproduced from the original train/test files in this run; neither split exists locally.

The historical [duplicate-screen aggregate](../../experiments/outputs/full_corpus_eda_261003/iiit_cvid_duplicates.json) reports zero exact cross-split byte groups and 469 cross-split dHash candidate pairs affecting 263 frames at Hamming distance at most 6. It saves only 20 example pairs, not the full queue. None had high text-token overlap under its recorded rule. This is insufficient to decide whether any pair is the same source scene or to freeze a cross-split cohort. **No automatic dHash exclusions were made.** Previously viewed test-reference aggregates also mean the native test cannot be described as unseen in this study.

Receipt SHA-256: full-source EDA `462f70792f9a9a6ff492de3e7c0118aec211037b6044b91242588822f89f6428`; duplicate screen `e348a19e580232646639ec11f2db27ce28ce3a46548f5c71bc5862c4f4d40c61`. Local ledger SHA-256: `a829c176b13d7133474a67cc0f3b3c0c7e3ec0ededc7a21b7a9f2d67c46eb682`. The notebook has 11 executed code cells, nine embedded PNG figures, and no error outputs; execution was direct in-process Python rather than a fresh Jupyter kernel.

## Next gate

Restore or reacquire author-released train/test PNG/XML with a verified archive identity; generate complete per-ID anomaly and cross-split pair ledgers; visually/source-review candidates; then lock the frame-level cohort and metric denominator. Do not call the 546 provisional validation frames or historical 5,475-frame aggregate a completed detection/spotting benchmark.

## Unresolved questions

- Which source-author or authorized annotation decision should govern the three edge-clipped validation boxes?
- Can the full train/test archive and complete 469-pair review queue be restored for per-ID adjudication?
