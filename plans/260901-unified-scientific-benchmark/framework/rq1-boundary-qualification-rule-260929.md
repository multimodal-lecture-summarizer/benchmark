# RQ1 chapter-start qualification rule

**Set before further VidChapters qualification or any official candidate scores.** The endpoint is the released internal chapter-start time on the exact whole-video media. Qualification uses source annotations, publisher descriptions/transcripts, frames and audio only. Reviewers must not inspect candidate predictions or metrics when deciding a unit's status. Never move a start, rewrite a label, or drop only a disputed boundary to improve a score.

## Separate checks

1. **Source and media identity:** keep the original paired `label,time`, video ID, annotation offset/hash, publisher media URL/hash, duration and decoder receipt. Pair/description parity establishes provenance, not semantic validity.
2. **Title meaning (`title_status`):** mark `pass`, `title_error`, or `uncertain`. A wrong/overly broad title alone does **not** exclude a unit from boundary-only RQ1 if the time independently passes the next check. Titles never enter predictor inputs or boundary metrics.
3. **Boundary alignment (`boundary_status`):** at every internal start `t`, inspect the exact media before and after `t` and independent publisher transcript/slide evidence when available. Mark `pass` only when a distinguishable chapter/topic onset has an independently observed anchor within **±3 s** of `t`; the anchor is QA evidence, never replacement GT. Mark `boundary_error` when a clear corresponding onset lies beyond ±3 s or the content plainly continues the preceding chapter. Mark `uncertain` if onset is gradual or evidence conflicts. Camera cuts alone do not prove a chapter onset. Record the original `t`, observation interval, evidence type, and reviewer reason for every decision.
4. **Unit decision:** `pass_boundary` requires all internal boundaries to pass, plus identity/media/rights gates. `title_error_only` is still boundary eligible and remains flagged for error analysis. Any `boundary_error` or `uncertain` makes the whole unit `hold_boundary`; do not remove individual starts. A source with no internal starts is ineligible for this comparison. Qualification holds can be revisited using source evidence under this same rule, before cohort lock, without model output.

The ±3 s criterion matches the predeclared primary collar; ±5/10 s remain sensitivity metrics and do not retroactively qualify a boundary. A difficult source boundary may legitimately remain `uncertain`. Report counts by title and boundary status so title errors are not reported as timestamp errors.

## Initial application to existing holds

| Video | Evidence independent of predictions | Title status | Boundary status | Decision |
|---|---|---|---|---|
| `3MOahpLxj6A` | At 1493 s, sampled frames show a camera change; speech continues prior material and introduces the next concept around 1509 s. A camera change alone is insufficient. | pass/uncertain at the disputed start | uncertain at 1493; other starts appear coherent | `hold_boundary` pending wider source review |
| `U_C7xW_gCfI` | At 936 and 1094 s, speech and board continue the first two-string problem. The next problem is introduced around 1115 s, while the 1144 s title refers back to connected strings. | title_error at multiple starts | boundary_error or uncertain at 936/1094/1144 | `hold_boundary` |
| `AW3a2ECNFlE` | Ten internal starts were sampled against the publisher MP4 and local speech/slide evidence before this rule; no contradiction was recorded. | pass on sampled evidence | provisional pass; retain the original receipt and perform rule-formatted independent review before D2 | retain among three currently qualified units; no split lock |

The earlier `semantic_gt` field conflated title and timing. These are corrected **prospectively** by this rule; old receipts remain as historical evidence. No model output was consulted for the decisions above.
