# RQ2 TIB validation EDA decision — 2026-10-02

> Historical decision for the 20-item Lecture diagnostic. On 2026-10-07 the user changed the next EDA scope to **all pinned `train`, `valid`, and `test` records, without filtering `genre`**. The old receipt and findings below are preserved as historical evidence; they are not the selection rule for the next run. Structural usability and reference quality across all splits remain to be measured. Creator `test` will no longer be unseen after this EDA.

**Protocol update:** the later [automatic evaluation amendment](./rq2-automatic-evaluation-amendment.md) removes human scoring and a fixed 50-talk minimum. Human/power questions below are historical findings from this EDA decision, not active gates.

## Scope and receipt

- Source: creator `gigant/tib`, revision `e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`, `valid` split only. No final-test record or content was read in this run.
- Reproducible analysis script: [`rq2-tib-valid-eda.py`](../../experiments/scripts/rq2-tib-valid-eda.py). The executed notebook was removed on 2026-10-08; its historical revision remains in Git. Selected DOI and metadata: [`rq2-tib-valid-diagnostic-receipt.json`](./rq2-tib-valid-diagnostic-receipt.json), SHA-256 DOI-list digest `690512dcbc220b9a7da3f2ec72448abc685e9c3fd9f4c1a40f8ae4ebee085759`.
- Selection: sort validation Lecture records by SHA-256 of DOI, retain first 20 that have DOI, source URL, nonempty transcript and at least two aligned, time-ordered segments, with one record per exact normalized author string. License is not an eligibility gate. This is deterministic and declared before any summary scores.
- Cross-split metadata comparison: projected only `doi`, `title`, `author` from 7,282 `train` rows; see [`rq2-tib-valid-train-overlap.json`](./rq2-tib-valid-train-overlap.json). No `test` record or content was read.

## Observed counts

| Observation | Count |
|---|---:|
| All validation records | 910 |
| Exact `Lecture` genre | 71 |
| Other genres containing `Lecture` | 17 |
| Exact `Lecture` records passing structural text checks | 70 |
| Selected diagnostic records | 20 |
| Selected distinct DOI / exact author strings | 20 / 20 |
| Selected records with abstracts shorter than 30 words | 9 |
| Selected DOI also found in train | 0 |
| Selected exact title also found in train | 1 |
| Selected authors also found in train | 13 |

For the selected 20, median transcript length is 7,881 words, median segment count 547.5, and median duration from final segment end 62.4 minutes. The shortest has 882 words and 6.6 minutes; the longest has 12,131 words and 87.3 minutes. All selected language fields say `en`. Segment word counts equal transcript word counts at displayed precision; no selected record has empty segment text, reordered starts or adjacent-segment overlap. All 20 DOI values match the numeric TIB media URL pattern, and an [HTTP HEAD receipt](./rq2-tib-source-url-head.json) returned 200 for all 20 landing pages without fetching video. These are structural and access checks, not ASR accuracy. The abstract range is 3–165 words, so abstract-based summary metrics require separate reference qualification. The 17 mixed-genre records are a declared expansion stratum, not silently pooled into the present cohort.

Two exact-Lecture anomalies are in the [receipt](./rq2-tib-valid-diagnostic-receipt.json): `10.5446/20230` has reordered segment starts and fails structural eligibility; `10.14288/1.0398145` uses a different DOI namespace but has TIB media URL `https://av.tib.eu/media/54281`, so the numeric TIB DOI/URL comparison is inapplicable and it is not excluded for that reason. Neither entered the selected 20.

The exact title `Old Irish – Morphosyntactic Structures, Part 3` and author `Griffith, Aaron` appear in both selected validation DOI `10.5446/49247` and train DOI `10.5446/49248`. A [targeted transcript comparison](./rq2-tib-title-collision-audit.json) found different normalized hashes, 882 versus 1,841 words, and five-word-shingle Jaccard 0.0022. They are not an exact or near-text duplicate, though they may belong to the same series. Keep the validation item for the development diagnostic; group it with its train counterpart or exclude it from a formal group-safe holdout. Repeated author alone (13/20) is a group-review flag, not proof of duplicate content.

## Eligible-cohort and sample-size follow-up

The historical EDA exported [metadata for all 70 structurally eligible `valid` Lecture records](./rq2-tib-valid-eligible-metadata.json). The export matches the pinned revision and selected DOI digest; it contains 70 distinct DOI values and no test content. The sample-size notebook was removed on 2026-10-08; its score-based estimates and saved outputs were withdrawn on 2026-10-07.

| Creator subject tag | Eligible 70 | Selected 20 | One-per-exact-author candidate 52 |
| --- | ---: | ---: | ---: |
| Chemistry | 19 | 4 | 12 |
| Physics | 15 | 2 | 7 |
| Linguistics | 11 | 4 | 10 |
| Mathematics + Physics | 10 | 4 | 9 |
| Mathematics | 7 | 2 | 7 |
| Architecture | 3 | 2 | 2 |
| Engineering | 3 | 0 | 3 |
| Computer Science + Mathematics | 2 | 2 | 2 |

The selected 20 omit Engineering, under-sample Physics relative to the eligible pool, and miss the longest eligible talks (maximum 12,131 versus 20,409 transcript words). Short abstracts occur in 9/20 selected and 23/70 eligible items. There are 52 distinct normalized author strings among the 70; taking the first DOI hash per author yields a deterministic 52-item **planning candidate** that includes the original 20 and covers all eight subject tags. Exact author distinction does not prove series independence or final input-token eligibility.

The old paired-score variance and precision estimates were withdrawn with the summarization results. The 52 distinct-author count is dataset metadata only; it is not a sample-size recommendation. Recompute precision after qualifying the full selected cohort and its evaluation protocol.

## Decision

**PENDING:** Reassess the cohort across all TIB splits as currently required. The title collision is not a near-text duplicate; author/series grouping is still unresolved. Mark reference-based scores unavailable until a summary target is qualified. The previous 20-item evaluation cohort is no longer an active result.

## Early execution smoke

The prior one-item engineering output was already removed. Its measurements are withdrawn and are not part of the current evaluation workflow.

## Unresolved questions

1. Are transcript segments accurate enough, and are repeated series/courses grouped safely across train, validation and the sealed test split? Exact author/title checks do not settle broader series relationships.
2. How many sealed-test Lecture or mixed-genre records pass endpoint-specific group/quality checks? The historical 98/94 figures have not been requalified on this revision.
3. Which selected abstracts are independent, source-supported summary references? Nine are shorter than 30 words; length alone does not settle quality.
4. How many of the 52 distinct-author candidates remain after series-group review and the frozen Qwen source-token preflight? What paired S3–S1 variance does the final chat-prompt recipe produce on the expanded cohort?
