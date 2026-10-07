# RQ1 Yale remaining-course selection lock

**Locked 2026-09-29 before opening selected lecture pages, chapter GT or media.** Continue the existing Yale publisher-native recruitment rule on the remaining 11 lecturer groups in the [40-offering course inventory](rq1-yale-publisher-course-inventory-260929.csv). Exclude lecturer groups in the earlier [nine-course QA sample](rq1-yale-260928-1952-nine-course-qa-sample.csv), [six VidChapters Yale IDs](rq1-expansion-batch-260929-2015-locked.csv), and [12 native Yale selections](rq1-yale-native-batch-260929-locked.csv). This is a recruitment priority, not a retrospective qualification decision.

The [locked 11-row manifest](rq1-yale-remaining-260929-locked.csv) sorts remaining lecturers by SHA-256 of lowercase UTF-8 name, chooses the lowest SHA-256 course URL for lecturers with more than one offering, then chooses the lowest SHA-256 published lecture URL from each course page. The [course-page receipt](rq1-yale-remaining-260929-course-snapshot.json) records source HTML hashes and every lecture URL considered. The selector reads course pages only and never reads selected lecture chapters, media, or model output.

Apply the existing [boundary/title/media/rights rule](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/rq1-boundary-qualification-rule-260929.md) to these fixed 11 IDs. Missing source GT, identity ambiguity, rights ambiguity or media mismatch stays `hold` on that row. No replacement inside this tranche and no edit to source `label,time`.

The Yale inventory contains 36 lecturer groups. The earlier QA/locked tranches touched 25 distinct lecturer groups, leaving 11 fresh. Even if all 11 were to pass, the current seven plus this tranche would reach at most 18 independent groups, below the prospective 20-group floor. Qualification yield may be lower. This capacity arithmetic does not authorize a split, D2 or official test.

## Unresolved questions

1. How many of these locked pages have a source video ID and an internal chapter start?
2. How many pass full media decode, boundary and scoped component-rights review?
