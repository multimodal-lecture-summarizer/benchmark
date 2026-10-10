# TIB cohort review for RQ2 — 2026-10-09

**Historical selection:** The user retired the 70-validation-`Lecture` cohort later on 2026-10-09. Its item-level text screen remains evidence of reference problems; use the [broad-coverage pool decision](tib-diverse-pool-261009-0943-benchmark-scope-report.md) for current RQ2 selection.

## Decision

**HOLD the formal RQ2 benchmark.** Do not run a model comparison yet. The pinned all-split EDA establishes structural text availability, not a frozen, source-safe cohort or qualified summary references. A limited creator-abstract agreement study remains possible after an explicit cohort and protocol freeze; its result cannot measure factual summary quality or generalization to an unseen creator `test` split.

This review uses the saved [all-split notebook](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb), the user-provided `drive-download-20261009T023146Z-1-001.zip` (SHA-256 `c86daacd4c861b1be7d1e5b81a92d6a96c2c059296ab1b5b1f2b3af4f567dcbd`), the [20-item source/reference screen](../261002-0946-rq2-controlled-summarization/rq2-tib-valid-reference-screen.json), the [70-item validation Lecture metadata](../261002-0946-rq2-controlled-summarization/rq2-tib-valid-eligible-metadata.json), and the [20-item audit](rq2-valid-dataset-audit-261002-report.md). No model was run. The pinned revision is `e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`.

## What the evidence supports

| Gate | Verified evidence | Decision |
|---|---|---|
| Structural text | Saved notebook has 6/6 executed code cells and no recorded cell error. It accounts for 9,103 rows; 9,002 structurally usable and 101 excluded. Validation has 904/910 usable. | KEEP as input availability evidence. |
| Domain | The historical 70-item validation metadata selection contains 70 `Lecture` records. `genre` is metadata, not a content-level lecture qualification. | LIMIT; do not infer all 70 are task-matched. |
| Abstracts | The supplied export has full abstract text for all 70 proposed validation `Lecture` records. Text screening below rejects 24, holds 8 and retains 38 content-specific but unverified candidates. Sixteen of 70 are in ten normalized exact-abstract groups crossing splits. Twenty-three abstracts have fewer than 30 words. | HOLD formal reference eligibility: 0/70 source-content-verified. Length alone is a review flag; exact shared course text is stronger evidence against individual-talk suitability. |
| Source groups | In the 70, 55 exact author strings and one exact title cross creator splits; no DOI is shared. Earlier 20-item audit also found nine same-series train titles. Across all source rows, the notebook reports 11 shared-title and 398 shared-author groups. | HOLD split independence until source/course/series grouping is resolved. Same author/title alone does not prove duplicate content. |
| Rights and media | All 70 proposed items have license labels, but media pixels/audio were not decoded in the all-split EDA. Audio transcript accuracy was not measured. | Text-only claim only; per-record rights/access check remains. |
| Holdout | The all-split EDA read creator `test` content and abstracts. | No unseen creator-test claim. |

The [dataset card](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) describes the abstract as archive-provided metadata that varies in style and quality, and the transcript as automatic speech recognition. These fields are useful as supplied inputs and noisy targets; the card does not establish factual support of any individual abstract against its video. Its described duplicate-abstract filtering does not remove the ten normalized duplicate groups observed in this pinned export.

## Export integrity and 70-item structural screen

- `coverage.json`, `all_splits_cohort.json` and all detail files agree on the revision, 9,103 unique `(split, source_index)` source IDs and 9,002 unique detail IDs. The detail ID set exactly equals the cohort's usable ID set. CSV IDs match their JSON counterparts; all 9,002 abstract strings in the detail CSV match the JSON. The cohort's usable-list SHA-256 recomputes to `b5a64bdd012a1385083362454318a0bbd8604a75c2488c70c39ef7e9ae7adf5d`.
- All 70 historical validation `Lecture` IDs occur in the export, are EDA-usable, have nonempty abstracts, and have matching normalized transcript/segment tokens. All have archive URLs and keyframe metadata. One DOI (`valid:127`) uses `10.14288` and cannot be assessed by the notebook's `10.5446` DOI-to-URL regex; this is **unknown**, not a mismatch.
- `valid:243` has four segment overlaps. The EDA considers it structurally usable, while the newer preprocessing module excludes overlapping segments. This record is already rejected by the abstract screen, but the two definitions of text usability need reconciliation before deriving a denominator from the module.
- `valid:834` has the only exact cross-split title collision in the 70. The earlier [focused title audit](../261002-0946-rq2-controlled-summarization/rq2-tib-title-collision-audit.json) found different transcript hashes and five-word shingle Jaccard 0.0022 against the train match; it remains a same-series grouping question, not an established duplicate talk.
- The ZIP contains abstract text and a transcript example, **not the complete transcript, audio or decoded video** for per-talk factual-support review. License labels identify terms to check; they are not a blanket rights decision.

## Reviewed 20 validation items

The source-linked screen already read each selected abstract alongside its TIB landing-page abstract. Its classifications are retained without upgrading unverified candidates to ground truth:

- **Unsuitable individual-talk reference (8):** DOI suffixes `43747`, `38638`, `50943`, `38319`, `14078`, `18890`, `19217`, `55669`. Reasons include title/speaker only, chapter stub, event biography, or course-level description.
- **Content-specific but unverified (12):** `20846`, `15101`, `49452`, `35254`, `49509`, `16294`, `50934`, `46066`, `20848`, `48908`, `45978`, `49247`. Source support, abstract origin/method and source-group safety are unresolved. These are candidates for a limited abstract-agreement analysis, not accepted factual-summary labels.

The ZIP permits a **text-only screen of all 70 abstracts**. It does not permit checking whether claims are supported by each full talk. Compared with the earlier 20-item screen, `valid:523` and `valid:834` are conservatively moved from content-specific candidate to HOLD: the former states a course aim, while the latter ambiguously describes a continuation. No source-supported label is created.

## Text-only screen of all 70 proposed validation Lectures

`reject` means the abstract is visibly unsuitable as an individual-talk target by its text or is exactly reused across different talks. `hold` means talk specificity is ambiguous. `candidate_unverified` means the text names content specific to this talk, **without** establishing that the talk supports it. A short abstract is flagged, never rejected by length alone. DOI suffix `1.0398145` belongs to DOI prefix `10.14288`; other listed suffixes use `10.5446`.

| valid index | DOI suffix | Text screen | Reason / flag |
|---:|---:|---|---|
| 16 | 15130 | hold | mixed_talk_course |
| 37 | 20846 | candidate_unverified | content_specific |
| 38 | 18990 | reject | course_template |
| 55 | 49062 | candidate_unverified | content_specific; short_under_30_words |
| 82 | 49469 | candidate_unverified | content_specific; short_under_30_words |
| 90 | 21651 | reject | duplicate_abstract_across_splits |
| 107 | 21609 | reject | duplicate_abstract_across_splits |
| 127 | 1.0398145 | candidate_unverified | content_specific |
| 146 | 43747 | reject | title_speaker_only; short_under_30_words |
| 147 | 19001 | reject | duplicate_abstract_across_splits |
| 153 | 49487 | candidate_unverified | content_specific; short_under_30_words |
| 167 | 15101 | candidate_unverified | content_specific; short_under_30_words |
| 181 | 38638 | reject | duplicate_abstract_across_splits; short_under_30_words |
| 187 | 49452 | candidate_unverified | content_specific; short_under_30_words |
| 240 | 35254 | candidate_unverified | content_specific; short_under_30_words |
| 243 | 19366 | reject | duplicate_abstract_across_splits |
| 270 | 54077 | candidate_unverified | content_specific |
| 275 | 42682 | hold | restates_title; short_under_30_words |
| 283 | 49509 | candidate_unverified | content_specific; short_under_30_words |
| 309 | 50943 | reject | mini_course_description |
| 320 | 19013 | reject | duplicate_abstract_across_splits |
| 332 | 55051 | candidate_unverified | content_specific |
| 334 | 50930 | candidate_unverified | content_specific |
| 348 | 16990 | hold | sparse_series_intro; short_under_30_words |
| 350 | 49070 | candidate_unverified | content_specific; short_under_30_words |
| 356 | 38319 | reject | bio_event_dominant |
| 370 | 14078 | reject | book_event |
| 383 | 42583 | candidate_unverified | content_specific |
| 392 | 15120 | candidate_unverified | content_specific |
| 400 | 19407 | reject | duplicate_abstract_across_splits |
| 417 | 19464 | reject | duplicate_abstract_across_splits |
| 423 | 15074 | candidate_unverified | content_specific |
| 431 | 19015 | reject | duplicate_abstract_across_splits |
| 462 | 43742 | candidate_unverified | content_specific |
| 466 | 15106 | reject | course_bio_dominant |
| 498 | 43757 | candidate_unverified | content_specific |
| 507 | 16294 | candidate_unverified | content_specific; short_under_30_words |
| 523 | 50934 | hold | course_aim |
| 525 | 49089 | candidate_unverified | content_specific; short_under_30_words |
| 537 | 19460 | reject | duplicate_abstract_across_splits |
| 557 | 20231 | candidate_unverified | content_specific |
| 562 | 48906 | hold | restates_title; short_under_30_words |
| 570 | 46066 | candidate_unverified | content_specific |
| 575 | 46055 | candidate_unverified | content_specific |
| 593 | 42685 | hold | restates_title; short_under_30_words |
| 598 | 18183 | candidate_unverified | content_specific |
| 621 | 42568 | candidate_unverified | content_specific; short_under_30_words |
| 625 | 19355 | reject | duplicate_abstract_across_splits |
| 642 | 21634 | reject | duplicate_abstract_across_splits |
| 654 | 18890 | reject | duplicate_abstract_across_splits |
| 660 | 19217 | reject | duplicate_abstract_across_splits |
| 666 | 20848 | candidate_unverified | content_specific |
| 691 | 18344 | candidate_unverified | content_specific |
| 708 | 48908 | candidate_unverified | content_specific; short_under_30_words |
| 716 | 15021 | hold | vague_lecture |
| 724 | 49060 | candidate_unverified | content_specific; short_under_30_words |
| 733 | 55669 | reject | course_description |
| 762 | 18588 | candidate_unverified | content_specific; short_under_30_words |
| 798 | 42637 | candidate_unverified | content_specific; short_under_30_words |
| 800 | 37055 | reject | topic_stub; short_under_30_words |
| 818 | 14934 | candidate_unverified | content_specific |
| 825 | 19397 | reject | duplicate_abstract_across_splits |
| 829 | 45978 | candidate_unverified | content_specific |
| 834 | 49247 | hold | continuation_ambiguous; short_under_30_words |
| 841 | 15109 | candidate_unverified | content_specific |
| 853 | 16394 | candidate_unverified | content_specific |
| 870 | 19395 | reject | duplicate_abstract_across_splits |
| 886 | 17056 | candidate_unverified | content_specific |
| 900 | 16219 | candidate_unverified | content_specific |
| 907 | 55054 | candidate_unverified | content_specific |

The 38 candidates still include 28 records whose exact author string occurs in another creator split. Source/course/series isolation and actual talk support remain unchecked for each of them. No benchmark cohort is frozen.

## Before a benchmark run

1. Inspect the source content and abstract provenance for the 38 text candidates and eight HOLD items. The ZIP does not include full transcripts or media. Confirm lecture-domain relevance, per-record rights and each claim's link to the specific talk. Do not treat a word-count flag or genre as a quality label.
2. Resolve source/course/series groups for selected `(split, source_index)` IDs, then freeze IDs and the intended claim. If the target is factual lecture-summary quality, require independently supported references; current evidence does not provide them.
3. Reconcile the older automatic-evaluation amendment's all-nonempty-abstract ROUGE-L rule with the newer all-split reference review and exposed creator `test` status. Freeze the scorer, generator, source-only S3 structure route, actual tokenizer, cumulative input/output token budgets and failure policy before scoring.

## Unresolved questions

- Which of the 38 text candidates and eight ambiguous records pass source-content, reference-provenance and domain review?
- Which source/course/series groups must stay together in the chosen cohort?
- Is the intended endpoint limited agreement with creator abstracts, or factual lecture-summary quality with separately qualified references?
