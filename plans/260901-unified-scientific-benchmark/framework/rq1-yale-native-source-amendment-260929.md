# RQ1 candidate source amendment: Open Yale Courses publisher chapter data

**Prospective, recorded 2026-09-29 before any publisher-native unit enters D2, selection, or official test. Status: candidate source only.** This extends the [YTSeg/VidChapters target amendment](rq1-target-amendment-260929.md) to permit evaluation of a qualified Open Yale Courses publisher-native subset against the same endpoint: original internal chapter starts on exact whole-video media.

The [publisher course inventory](../../../../plans/reports/rq1-yale-publisher-course-inventory-260929.csv) and [locked native tranche](../../../../plans/reports/rq1-yale-native-batch-260929-locked.csv) are recruitment evidence, not GT/media/rights qualification. For a native Yale unit, source GT is the ordered pairing of the lecture page's visible “Lecture Chapters” names and numeric start times, including structural start 0. Store the page URL, retrieval date, source HTML or GT-block digest, displayed video ID, every original label/time pair, media URL/hash/duration, and any source revision. Keep the original seconds and labels; do not infer corrected starts from transcript text or another media version. Exclude start 0 and video end from scoring while preserving them in QA.

Apply the existing [title/boundary/media/rights rule](rq1-boundary-qualification-rule-260929.md) per unit. A strict source adapter must verify page identity, pair lengths/order/range, original video ID, and the exact media timeline before D2. The publisher transcript embeds chapter headings and times, so it cannot be copied into predictor inputs or feature caches as a shortcut to source-only inference. Predictor features must be derived through the same isolated media/ASR path and frozen for all candidates. Deduplicate any video that also appears in VidChapters or YTSeg; dataset labels are provenance, not independent samples.

Yale's [terms](https://oyc.yale.edu/terms) cover most course material under BY-NC-SA, while third-party components may be excluded; inspect each lecture and planned processing rights. Publisher availability and channel identity alone do not clear this gate. A future D2 manifest must label source type explicitly and use the same group split, history, and sealed test controls as the other sources.

## Unresolved questions

1. Which publisher-native IDs pass exact media and component-rights review?
2. Which adapter version and media hashes will be frozen if this source enters D2?
