# LVVO 1k provenance and split qualification — 2026-10-10

## Decision

**Keep the released four-class annotations for EDA; HOLD a formal Detection A split and benchmark.** The author-released LVVO 1k has complete image/label pairs and a stated CC BY 4.0 dataset license. The filename schema supports a consistent source-video *token* for all 1,000 frames, but the archive and author repository do not provide a verified mapping from the 139 tokens to individual VideoPoints pages or source-video files. No train, validation or final-test role is assigned in this audit. All 1,000 released labels were already inspected in EDA, so any later partition of this same release cannot be called an unseen-reference final test.

This audit reused the executed [LVVO EDA notebook](../../experiments/notebooks/diagnostics/lvvo-four-class-detection-eda.ipynb) and its [local receipt](../../experiments/outputs/lvvo_four_class_eda/eda_receipt.json). It did not redownload the 51,146,225-byte ZIP, extract it again, decode the images again, or run a detector. The archive SHA-256 is `f049217c51c45d532f394d7082e69da95397dee106fede1d743ff3dee80bf7cf`.

## Source and rights evidence

| Question | Direct evidence | Decision |
| --- | --- | --- |
| Which release? | The [author repository](https://github.com/dbiswas55/LVVO_dataset) describes `LVVO 1k withCategories.zip` as 1,000 manually annotated four-class frames; its Drive file ID and archive hash appear in the EDA receipt. The 3k release has automatic labels and is outside this cohort. | Release identity pass. |
| Who created the annotations? | The [author paper](https://arxiv.org/html/2506.13657v2) describes two independent annotators and an expert who resolved disagreements. | Creator annotation provenance documented at dataset level. No per-box annotator history is released. |
| Where did the frames originate? | The paper says 4,000 frames came from 245 VideoPoints lecture videos and states the filename format as instructor, course, video and frame tokens. The [author README](https://github.com/dbiswas55/LVVO_dataset) links to VideoPoints. The examined 1k subset has 139 distinct `v` tokens, 13 `c` tokens and 8 `i` tokens. | Platform and token schema documented. Per-video URL/media linkage HOLD. The 245 count is for all 4k frames, not the 1k subset. |
| What use is licensed? | The author README states **LVVO Dataset: CC BY 4.0**. It separately lists different licenses for adapted LDD/LPM metadata, which are not part of this cohort. [VideoPoints](https://new.videopoints.org/public/index.php) says its service is free for education use; that statement does not document the right to obtain/process each source lecture. | Released LVVO image/annotation licensing is stated. Underlying video rights and per-video attribution/scope are unverified; do not treat CC BY 4.0 as a license to redistribute source videos. |

The official example `i116_c425_v7624_i_0146.jpg` is present in the local 1k ledger. The filename schema is therefore consistent between the published documentation and archive. No source URL was inferred from `v7624` or any other numeric token. Searches of the author repository and public VideoPoints pages did not yield an authoritative per-token URL table.

## Accounting and leakage gate

| Unit | Selected | Observed | Label-valid | Media-valid | Evaluated | Failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Released 1k images | 1,000 | 1,000 | 1,000 released JSON labels with valid geometry | 1,000 decoded JPG frames in prior EDA | 0 detector predictions | 0 image/label read failures |
| Underlying videos | 139 author `v` tokens | 139 tokens parsed | — | **0 source videos verified** | 0 | — |

`media-valid=1,000` applies only to released JPG frames. It does **not** say that 139 source video streams were opened or that sampled frames were matched to them. The prior EDA found 1,580 boxes, 21 zero-object frames, no exact-byte duplicate image groups, and 313 dHash candidate pairs at Hamming distance ≤4; **257 pairs cross `v` tokens**. These are candidate visual similarities, not confirmed duplicate frames or grounds to remove records. Full pair adjudication is needed before any cross-video split. No model metric has a denominator because `evaluated=0`.

The [per-image ledger](./lvvo-provenance-split-261010-image-ledger.csv) preserves each of 1,000 released IDs, file hashes, author tokens and HOLD reasons. The [video-group ledger](./lvvo-provenance-split-261010-video-group-ledger.csv) has all 139 `i..._c..._v...` groups, their frame counts and blank source URL/split fields. The [receipt](./lvvo-provenance-split-261010-receipt.json) pins the input and ledger hashes. `hold_formal_split_no_exclusion` is a gate decision, not an automatic rejection of any image.

## Protocol boundary before a benchmark

1. Keep the endpoint to the four manually annotated classes in `LVVO 1k withCategories`. Do not merge the automatically labeled 3k or reinterpret its generic class as four-class GT.
2. Obtain an authoritative mapping from every candidate `i/c/v` group to the source VideoPoints lecture, its publisher/creator and applicable use scope. Match a declared sample of released frames back to source media. Until this exists, `v` remains an author-defined grouping token, not a independently verified video link.
3. Review the cross-video dHash candidate queue visually and against source identity; record keep/group/exclude decisions by ID. Do not auto-exclude on dHash alone. If two groups share the same source or overlapping content, bind them to one split. Review course/instructor overlap as well.
4. Only then create a deterministic, versioned video-group split. State the generalization target explicitly: held-out videos **within** known courses/instructors, or held-out courses/instructors. These answer different questions. Freeze the grouping rule, ID roles, duplicate decisions, training/validation/final-test ratios, seed, metric denominators and permitted tuning before prediction generation. Do not use image-level random splitting.
5. For this already-inspected 1k release, label a reserved subset `model-held-out, reference previously inspected` if used; never `unseen reference`. An unseen-reference final test requires new eligible lecture groups whose labels are sealed until final evaluation. No such cohort is identified here.

The paper reports an 80/20 training/validation setup for its own automatic-annotation experiment; the downloaded four-class archive has no official split field and that paper description does not establish a source-group-safe split for this benchmark. Grouping by video token gives 139 candidate groups; grouping more conservatively by instructor leaves only 8 groups (16–218 frames each), so a claimed unseen-instructor test would require a separate feasibility and class-coverage analysis.

## Unresolved questions

1. Can the LVVO authors or VideoPoints provide an authoritative `i/c/v` → lecture URL/ID and permission or attribution map for the 139 groups?
2. Which of the 257 cross-token dHash pairs are real repeats or shared source content, and what are their keep/group/exclude decisions?
3. Will a new sealed-label cohort be available for a genuinely unseen-reference final test? If not, the conclusion must be limited to model-held-out performance on previously inspected references.
