# RQ1 20-group split rule

**Set before computing assignments or opening candidate results, 2026-09-30.** Input is the exact [20-group qualified cohort](rq1-cohort-260930-twenty-qualified-locked.json) after the [bounded project-use history audit](rq1-project-use-history-260930-twenty-group-report.md). No unit is added, removed or relabeled for the split.

Each distinct course/lecturer connected component is one allocation unit. Use two source strata: `legacy` = YTSeg or VidChapters (6 groups); `yale` = publisher-native Open Yale (14 groups). Sort each stratum by the lowercase SHA-256 hex of the UTF-8 string `rq1-8-4-8-260930|<course_id>|<semicolon-joined sorted lecturer_ids>`. Assign the first 3 legacy and 5 Yale groups to train, the next 1 legacy and 3 Yale to validation, and the final 2 legacy and 6 Yale to sealed final test. Thus the fixed totals are `8/4/8`, with source types represented in each split. No score, title status, boundary uncertainty or video quality enters assignment.

All videos sharing a course or any lecturer must remain together, including future additions to those components; a cross-split link invalidates this lock. Final-test IDs must stay out of candidate fitting, tuning, feature-based selection and checkpoint choice. The split guard validates the exact assignment and history statuses after generation. This rule does not open the final test; D2 inputs, validation-only precision and candidate/checkpoint receipts must still be frozen before prediction generation.

## Unresolved questions

1. Does D2 contain exact media, annotation and transcript provenance for every split unit?
2. Does the validation-only variance check support an eight-group final test under the predeclared ±0.20 F1 target?
