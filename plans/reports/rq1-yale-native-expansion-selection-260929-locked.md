# RQ1 Yale publisher-native source: second recruitment tranche

**Locked 2026-09-29, before inspecting any newly selected lecture media.** This extends the source search after the first institutional VidChapters/YTSeg tranche yielded six new Yale course groups. It is a selection rule, not an added qualification gate. The original four passes, the two later passes, all holds, and the locked six-ID Yale VidChapters tranche keep their existing status.

## Source and deterministic selection

1. Use the [Open Yale Courses course list](https://oyc.yale.edu/courses), snapshotted as [40 offerings](rq1-yale-publisher-course-inventory-260929.csv) (SHA-256 `992c4a83bb052af9bbd88f2cc79fe96afcb8841de3ca3aedfe1cd92cdebccb4e`). Treat course URL and every listed professor as tentative identity; merge offerings that share a professor. The 40 offerings form at most 36 independent Yale lecturer groups before any GT/media/rights checks.
2. Prioritize wholly new lecturers: exclude from this *tranche's selection* the six Yale VidChapters lecturer groups already locked and the earlier nine-course Yale MOV QA sample's lecturers. This avoids selecting media already inspected in that prior QA and maximizes new course coverage. Exclusion here is a recruitment priority, not a judgement that those courses are invalid for train or validation.
3. Sort remaining lecturer groups by SHA-256 of the lowercased UTF-8 professor name, then take the first 12. If one professor has multiple courses, choose the course with the smallest SHA-256 of its canonical course URL. On that course page, collect canonical `/lecture-N` links, sort by SHA-256 of the full lecture URL, and lock the first URL. Do not use chapter quality, media, rights, or model output to choose a replacement. If a selected page lacks an internal start or a source video ID, mark that row `hold_source`; do not silently replace it within this tranche.
4. After writing and hashing the locked course/lecture manifest, inspect each selected page's original publisher chapter labels/times, source video ID and transcript, then apply the existing [title/boundary/media/rights rule](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/rq1-boundary-qualification-rule-260929.md). Preserve publisher starts. No official cohort or split follows from this batch alone.

The publisher-native chapter source is a **candidate third source** for the same internal-chapter-start endpoint. Before any such unit enters D2, record a prospective source amendment and implement a strict publisher adapter. Publisher transcripts with embedded chapter headings/times cannot be used directly as predictor input. No model scores are consulted in recruitment.

## Unresolved questions

1. Which of the 12 selected course pages provide usable original chapter starts and an exact media identity?
2. How many pass media timeline and component-level rights under the existing rule?
