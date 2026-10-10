# TIB cross-split source and transcript audit — 2026-10-10

## Scope and source

This audit addresses the 11 normalized-title and 398 normalized-author groups flagged by the earlier all-split EDA. It is **not** a rerun of reference EDA, a quality judgment on creator abstracts, or a model benchmark. The script [`rq2_tib_split_audit.py`](../../experiments/scripts/rq2_tib_split_audit.py) streamed the pinned public `gigant/tib@e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee` rows: train 7,282, valid 910, test 911. Queue membership came from the user-supplied EDA ZIP with verified SHA-256 `c86daacd4c861b1be7d1e5b81a92d6a96c2c059296ab1b5b1f2b3af4f567dcbd`. The script does not inspect the abstract field; the dataset loader necessarily deserializes rows that contain it. Earlier EDA had already exposed test references, so test is **not unseen**.

For queued records, the audit compared exact DOI, normalized source/video URLs, normalized transcript SHA-256, and sets of contiguous five-word transcript shingles. It also derives a conservative title stem by removing numbered lecture/part markers. That stem is a lexical series clue, not verified course metadata. Source host equality is uninformative here because `av.tib.eu` is the archive domain. No media pixels or audio were decoded, and no external course page was verified.

## Results

| Check | Observed |
|---|---:|
| Creator records scanned | 9,103 |
| Cross-split title / author groups | 11 / 398 |
| Unique queued records / unique cross-split pairs | 1,562 / 2,658 |
| Exact DOI / source URL / video URL / transcript-hash matches | 0 / 0 / 0 / 0 |
| Pairs with high transcript overlap (five-word Jaccard ≥0.30 or shorter-set containment ≥0.80) | 3 |
| Pairs with same lexical series stem but below high-overlap threshold | 95 |
| Shared metadata only | 2,560 |
| Automatic exclusions | 0 |

All 11 exact normalized-title cross-split pairs have distinct DOI and source URLs; their five-word Jaccard ranges from 0.000676 to 0.009770. A shared title alone therefore does not identify a repeated transcript in this queue. The 398 author groups expand to 2,655 unique pairs: eight also share a title, and three additional pairs share a title without an exact author match, for 2,658 unique pairs overall.

The three high-overlap pairs are one `Cool Tools In the Developers Toolbox` author/series cluster: train:2341 (`10.5446/35935`), valid:433 (`10.5446/35934`), test:782 (`10.5446/36010`). Pairwise Jaccard is 0.311–0.402; shorter-set containment is 0.591–0.595. These are separate DOI/media records with substantial shared transcript wording. Treat them as a linked source group in any split sensitivity analysis; do not infer that one record is a full duplicate or automatically discard it. The other 95 lexical-series pairs also need group-aware interpretation, not automatic removal.

## Decision for a limited benchmark

Keep all 8,769 mechanically eligible records as **candidates**. This audit changes zero eligibility IDs. It supports a limited **agreement with creator-provided abstracts** study with source/author/series sensitivity analysis; it does not validate those abstracts as factual video-summary ground truth or establish an independent final test. When reporting a benchmark, separate `selected / observed / label-valid / media-valid / evaluated / failed`, include the denominator for each metric, and identify whether linked source groups were kept together in uncertainty calculations. Same-author and same-title groups remain review flags. The three high-overlap pairs warrant an explicit source-group sensitivity check.

## Reproducible evidence

Ignored local outputs under `experiments/outputs/rq2_tib_split_audit/`:

- `cross_split_group_evidence.csv`: 409 group rows; member IDs and pair-class counts; SHA-256 `6d0fc43dac666d181c1dce66c1cf001e88d534852605de4f6149dffaf27a19f6`.
- `cross_split_pair_evidence.csv`: 2,658 pair rows; IDs, DOI, source URL, titles/series stems, transcript hashes, overlap statistics, and decision; SHA-256 `c3576fb2b34ac90312914ecd1c904e2c3dd74c7e5af256f6f610330d01df6fb0`.
- `audit_summary.json`: source revision, split/group counts, method, and decisions; SHA-256 `68d8e9c002fc94970068b24d21dd9040df832827ac5f9085e92eb58abe9c871c`.

Run from `benchmark/`: `python -m experiments.scripts.rq2_tib_split_audit`. The script verifies source counts and the queue ZIP hash before writing results. It does not create a new benchmark preprocessing path.

## Unresolved questions

- Course/series membership cannot be proven from title and archive URL alone. The 98 lexical/high-overlap pairs should be treated as dependent in sensitivity analysis; authoritative course metadata would be needed to fully classify the remaining author pairs.
- Media identity was not checked at waveform or frame level. Exact transcript/content comparisons therefore establish text relation only.
