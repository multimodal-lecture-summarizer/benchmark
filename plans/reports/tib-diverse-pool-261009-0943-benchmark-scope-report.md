# TIB broad-coverage RQ2 pool — 2026-10-09

## Decision

Retire the 70-validation-`Lecture` cohort as the active RQ2 selection. Use the **largest defensible TIB candidate pool across all creator splits and genres**, without a fixed sample-size cap or a `Lecture` filter. The previous [70-item text review](tib-cohort-review-261009-0923-benchmark-readiness-report.md) remains historical evidence of reference defects; it is not a sampling frame or benchmark result. No model or trial benchmark was run for this decision.

The user-provided `drive-download-20261009T023146Z-1-001.zip` has SHA-256 `c86daacd4c861b1be7d1e5b81a92d6a96c2c059296ab1b5b1f2b3af4f567dcbd`. Its pinned revision is `gigant/tib@e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`. The [all-split EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) and full JSON/CSV export agree on source and detail IDs; the usable-ID hash recomputes to `b5a64bdd012a1385083362454318a0bbd8604a75c2488c70c39ef7e9ae7adf5d`.

## Maximal text-reference candidate pool

| Step | Records remaining | Reason |
|---|---:|---|
| All pinned creator records | 9,103 | Train 7,282; valid 910; test 911. |
| Structurally text-usable | 9,002 | EDA excludes 101 invalid or unordered segment records. |
| Nonempty creator abstract | 8,994 | Eight structurally usable records have empty abstracts. |
| Unique normalized creator abstract | **8,769** | Exclude 225 records belonging to 18 repeated-abstract groups. Normalization is casefold plus whitespace collapse. Reused text cannot identify the content of one particular talk. |

This is a **metadata and text-reference screen**, not a source-verified scoring cohort. Preserve all 9,103 IDs and exclusion reasons in the audit. Short abstracts, shared authors/titles, segment overlap and transcript/segment punctuation disagreement are review flags, not automatic exclusions from this broad pool. The Python [preparation module](../../experiments/scripts/rq2_tib_benchmark_dataset.py) returns `broad_pool_ids`, `broad_pool_sha256` and diversity counts in memory after reading all three pinned splits. The export-derived SHA-256 over ordered `(split, source_index, DOI, abstract hash)` identities is `06a766f5694acb1a1be33021a08089eeba450383d03d4ac8b647dd1651c29eac`; reproduce it when the pinned raw dataset is accessible.

### Metadata coverage of the 8,769 candidates

| Dimension | Coverage |
|---|---|
| Creator split | 7,003 train; 887 valid; 879 test. `test` was inspected in EDA and is not unseen. |
| Genre | 10 exact metadata label combinations: 7,897 `Conference/Talk`, 570 `Lecture`, 135 `Webinar/Tutorial`, 91 combined `Workshop/Interactive Format` and `Lecture`, 75 across other nonempty combinations and one blank. Genre is a stratification field, not a verified content label. |
| Subject | 35 exact subject strings. `Computer Science` alone has 7,249/8,769 (82.7%); Mathematics 357, Physics 230, Information Science 147, and the remaining labels are smaller or multi-subject. A single pooled metric would be dominated by Computer Science. |
| Duration | 609 under 15 min; 3,252 from 15 to under 30; 3,967 from 30 to under 60; 785 from 60 to under 90; 156 at least 90 min. |
| Year and author | 36 release years (1976–2022); 7,152 distinct nonempty normalized author strings and seven records with blank author. These are metadata values, not verified unique speakers or source series. |
| Media | Every candidate has a source URL and keyframe metadata. The EDA did not decode pixels or audio, so actual visual/auditory diversity and media usability are unverified. |

Among the 8,769, **1,297 records share an exact author string** and **22 share an exact title** across creator splits. These matches are review queues, not proof of duplicate video content. DOI uniqueness alone does not establish source or series independence.

## Benchmark use

1. Keep every broad-pool ID eligible for **review**, regardless of genre or subject. Review source linkage, educational relevance, abstract specificity, rights and source/course/series grouping before scoring. An abstract's presence and uniqueness do not verify it as a factual summary reference. Because most records are `Conference/Talk`, describe an all-genre result as academic-video or presentation summarization; report the verified lecture subgroup separately rather than calling all 8,769 lectures.
2. If the task is limited creator-abstract agreement, predeclare the claim and reference policy, use the same qualified IDs for S1/S3, and report both overall and genre/subject/duration strata. Include uncertainty and source-group sensitivity. If the goal is factual lecture-summary quality, obtain independently supported, task-matched references; this export does not contain that evidence.
3. Run all qualified IDs when resources allow. If compute imposes a limit, freeze a deterministic group-aware selection that covers rare genre, subject and duration strata before repeating dominant strata. Record the full eligible denominator and every omitted ID; do not revert to the historical 70-item cap. Freeze model, tokenizer, source-only structure route, cumulative token budgets and failures before model execution.
4. Since all creator splits and `test` references were inspected, neither all-split scoring nor creator `test` supports an unseen-holdout claim. If a model trains or tunes on any TIB item, separate those source groups from evaluation; an independent untouched dataset is needed for an unseen final-test claim.

## Current gate

**HOLD formal RQ2 scoring.** The 8,769 records maximize metadata coverage after narrow mechanical/reference-text exclusions, but no per-record source support or independent group-safe cohort has been verified. The earlier 70-item review showed concrete template/course abstracts and reused text, so treating every remaining creator abstract as qualified ground truth would be unsound.

## Unresolved questions

- Which broad-pool records are educational talks with references that suit the chosen claim after source-content review?
- How will source/course/series groups be resolved before paired scoring and uncertainty analysis?
- What compute budget is available if the fully qualified pool is too large to score in one run?
