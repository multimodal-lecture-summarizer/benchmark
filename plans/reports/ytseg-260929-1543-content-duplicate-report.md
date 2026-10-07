# Transcript duplicate screen: locked YTSeg × MITFLD pilot

**Result:** no text duplicate signal across **10 × 45 = 450** comparisons. This clears the *transcript screening* step only; it does not prove that no audiovisual repost exists. [Machine receipt with all pairs and transcript hashes](./ytseg-260929-1543-content-duplicate-receipt.json).

## Inputs and procedure

- YTSeg: exactly the ten **train** IDs in the [pre-media lock](./ytseg-260929-1543-pre-media-cohort-lock.csv), SHA-256 `4DEDB0EFACECF547F1BF2EAC773A0B6CED3CEA9ED1330875CF6E9B493E9F0719`; `text_ref` from four Parquet shards at revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`. Original validation/test GT was not read.
- MITFLD: 35 [selected IDs](./mitfld-rq1-35-260928-1120-selected.csv) plus ten `excluded_pilot_ids` in the [selection receipt](./mitfld-rq1-35-260928-1120-selection-receipt.json); complete published `transcripts/<id>.json` for all 45 at revision `f5a5047e040ecf0f80a3cb67d64e324407f323ec`. Each downloaded transcript's SHA-256 is in the machine receipt. All 55 required text records were available.
- Lowercase and tokenize `[a-z0-9]+`, preserving word order. Construct sets of exact contiguous five-word and ten-word shingles for each transcript. For every pair, compute 5-gram Jaccard (`intersection/union`), containment against the shorter set (`intersection/min(size)`), and count shared 10-grams. No model score, GT, or media selection entered this comparison.

## Results

| Measure | Largest observed pair | Value |
|---|---|---:|
| 5-gram shorter-set containment | YTSeg `tCKk22kaZi4` vs selected MITFLD `7J1HD9rqEB4` | **0.0057011** (0.57%; 42 shared 5-grams) |
| 5-gram Jaccard for that pair | Same pair | 0.00225928 |
| Largest prior-pilot containment | YTSeg `MoEaRpLNo9A` vs pilot `6MssatXXAzc` | **0.00569801** (0.57%; 48 shared 5-grams) |
| Shared exact 10-grams | Any of 450 pairs | **0** |

No pair reached the operational review triggers used in this screen: 5-gram shorter-set containment ≥0.10 or ≥25 shared 10-grams. These triggers were chosen for this check; they were **not** part of the earlier pre-media cohort lock. The raw scores and all 450 pair records allow a different threshold to be applied without rereading inputs.

This complements the earlier zero exact-ID overlap and different course/title evidence. Low exact transcript overlap strongly argues against the **same captioned lecture** among these 45 comparison videos. It cannot exclude a repost with substantially different captions, translated/paraphrased transcript, silent edits, partial clip reuse, or a duplicate outside the 45-video comparison set. Pairwise audio/video fingerprinting was not performed. No media or transcript excerpts were published.

## Unresolved questions

1. Is audiovisual fingerprinting needed to exclude reposts with changed captions before D2?
2. Were any other historical pilot or model-tuning videos used outside the 45 IDs checked here?
