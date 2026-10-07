# RQ1 source expansion: selection locked before media inspection

**Lock date:** 2026-09-29 19:51 Asia/Bangkok. **Purpose:** find additional independent course/lecturer groups; do not use model predictions, scores, or held-out outcomes. This is a recruitment rule, not a new qualification gate. The four already passed units and the previously locked four-unit batch keep their existing status and are outside this selection.

## Metadata-only selection rule for the next batch

1. Search the published **VidChapters-7M original `chapters.pkl`** and **YTSeg released text metadata** for lecture videos from institutional publishers. Search publisher/course metadata first in this fixed order: MIT OpenCourseWare outside the existing 87-ID channel list; Open Yale Courses; Stanford Online/Stanford Engineering Everywhere; Harvard CS50. Record source snapshot, query, source ID and byte offset/row locator. Publisher names are discovery hints, never rights clearance.
2. Include a candidate only when source metadata has an original video ID, video duration, at least **one internal chapter start** (not structural time zero), and enough publisher metadata to propose a course key and all named lecturers. Keep any ambiguous mapping as `hold_identity`; do not infer a new independent group from a title alone.
3. Deduplicate the current 89-ID catalogue and any cross-dataset IDs first. Form tentative transitive groups by shared course or lecturer. Prioritize **new groups**, one video per tentative group before taking a second from any group. Within a course, order by SHA-256 of the exact video ID (ascending), independent of chapter labels, media quality, or model output. Traverse publisher buckets in the fixed order above. Stop the first expansion tranche at **12 distinct tentative new groups** or when all four buckets are exhausted; publish yield and attrition, then decide whether another tranche is justified.
4. Freeze the selected ID/order/course/lecturer/source locator and source snapshot hash in a batch CSV **before opening or downloading any selected media**. Then apply the existing [GT/title/boundary/media/rights rule](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/rq1-boundary-qualification-rule-260929.md) independently per unit. Do not move GT, rewrite titles, or use candidate results to keep/drop units. Mark unavailable or ambiguous items `hold` with reason; do not silently replace them inside a locked tranche.

These are metadata-based recruitment choices. GT/media/rights pass is determined only later by the existing rule. The 20/10/20 design stays deferred while source capacity and observed pass yield remain unknown. The four already passed groups remain an undivided recruitment pool.

## Unresolved questions

1. Do the four institutional buckets contain 12 source-identifiable *new* groups with original GT?
2. How many selected groups pass exact media and component-level rights checks?
