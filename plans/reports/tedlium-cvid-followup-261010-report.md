# TED-LIUM and IIIT-CVID qualification — 2026-10-10

This review is additive. Historical EDA, benchmark outputs and original labels are preserved. No model inference ran. Neither scientific cohort nor evaluation protocol is frozen.

## TED-LIUM

Re-hashed the retained bundle's `units.json` and all 50 WAVs against its receipt. Reused the prior 50 successful waveform decodes. Accounting, in retained utterance units: **50 selected / 50 observed / 42 label-valid / 50 media-valid / 0 evaluated / 0 failed reads**. This does not cover all 270,323 historical metadata rows or the historical 1,662 valid validation/test units.

All eight invalid references contain the exact author-source marker `ignore_time_segment_in_scoring`: four validation records and four test records whose upstream IDs identify inter-segment gaps. They are EXCLUDE for scored ASR, not missing text to impute. All 50 IDs, original Arrow coordinates and annotation/media hashes are in [the ID ledger](../../experiments/outputs/dataset_qualification_261010/tedlium3-id-ledger.csv). The 42 remaining records are bounded diagnostic candidates; they are not a representative or frozen scientific cohort. Retained validation/test source-group intersection is empty; this says nothing about missing train records or model pretraining contamination.

The old `release3-snapshot-e51a4a2a93f3` identifies a local Arrow fingerprint, not an upstream Git commit. The available [pinned author-derived builder](https://huggingface.co/datasets/distil-whisper/tedlium/blob/db6c0314dee6cc8e2770b34fda08f4a3bf1ebd59/tedlium.py) preserves ignore markers, but its repository contains a builder rather than the missing Arrow. The LIUM dataset API and the exact validation archive URL in that builder return HTTP 401 in this environment. Response-prefix hashes and URLs are persisted in [recovery probes](../../experiments/outputs/dataset_qualification_261010/tedlium-recovery-probes.json). Earlier guessed OpenSLR paths returning 404 are historical probes, not evidence that every official source is unavailable. Rebuilding Arrow from another release would require a new provenance identity and a coordinate/content comparison; it cannot silently restore the original fingerprint.

**HOLD:** original snapshot recovery, full intended-cohort media audit and an independently held-out comparison protocol. Narrow endpoint: diagnostic WER on the 42 retained released references, with a documented nonrepresentative sample and observed native test; no new benchmark was launched.

## IIIT-CVID

The full source ZIP was still present although only validation had been extracted. Verified SHA-256 `b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489`, read every frame/XML pair directly in the archive, decoded each selected PNG and regenerated the full cross-split screening queue. No extraction or original-file edit was required.

| Unit: frame/XML pair | train | validation | test | Total |
|---|---:|---:|---:|---:|
| Selected, observed and decoded | 3,171 | 549 | 1,755 | 5,475 |

Accounting: **5,475 selected / 5,475 observed / 5,455 geometry-and-nonblank-label valid / 5,475 media-valid / 0 evaluated / 0 failed reads**. Geometry validity does not establish independent transcription accuracy. Prior validation crop evidence remains a separate endpoint.

- **22 boxes on 20 frames:** four negative-coordinate cases, 15 right-edge one-pixel overflows and three other overflows. Inspected the 20-frame contact sheet against numeric XML coordinates. All remain HOLD for geometry scoring. Image edges alone do not establish coordinate conventions or the intended text extent; clipping is not an evidence-backed correction.
- **124 XML-size mismatches:** 120 have otherwise valid geometry. A hashed override map records decoded PNG dimensions for these 120, preserving original XML, box coordinates and text. The other four also have invalid geometry and remain HOLD. The derived map has not been applied to original data.
- **469 cross-split dHash candidates / 263 images:** zero byte-identical pairs; maximum token Jaccard is 0.09091. Every pair is persisted. Low text overlap does not establish source independence; retain HOLD until content/source review, without automatic exclusions. Folder-based course/lecture groups do not cross splits, but their underlying video URLs have not been independently verified.
- Structural ledger: 5,335 KEEP / 120 REPAIR / 20 HOLD. These are frame-quality decisions. Any implicated duplicate candidate or unresolved source identity can still block scientific qualification.

Evidence: [frame ledger](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-frame-ledger.csv), [geometry adjudication](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-geometry-adjudication.csv), [derived overrides](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-derived-dimension-overrides.json), [complete pair queue](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-cross-split-pairs.csv), [contact sheet](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-geometry-contact-sheet.png), [receipt](../../experiments/outputs/dataset_qualification_261010/iiit-cvid-qualification-receipt.json).

**Superseded claim:** the earlier report's statement that train/test and the full duplicate queue are absent locally. Its historical validation results remain preserved. All inspected native test references are observed, not unseen.

## Unresolved review

TED-LIUM upstream access/snapshot identity; OCR source-video identity and 469 candidate content decisions; author evidence for the 22 box geometries. No formal benchmark cohort is approved by these checks.
