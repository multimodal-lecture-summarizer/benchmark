---
phase: 3
title: "Design independent cohort and split"
status: pending
priority: P1
dependencies: [2]
---

# Phase 3: Design independent cohort and split

## Overview

Determine whether the rights-cleared candidate set supports an independent official RQ1 study. Make the split at verified course/source group level; keep MIT001 as a separate one-course diagnostic.

Scope decision (2026-09-28): Phase 2 predeclares and freezes a 35-ID MITFLD candidate list and proposed course-group split before per-file rights/media/GT checks. Phase 3 verifies the same locked list after qualification, reports selected-set attrition and decides whether the surviving groups support the claim. The 468 lecture-like metadata rows are an upper-bound discovery pool; do not audit all 468 as a prerequisite.

Qualification checkpoint: [35-ID follow-up](../reports/rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md) leaves 1 selected video on rights hold and 34 pending; none has independently licensed chapter GT. The proposed 19/8/8 video and 11/5/5 course allocation is still candidate-only. Do not call 34 videos surviving/eligible or freeze this split before rights, 3.091 alignment review and GT creation.

## Requirements

- Remove duplicate `video_id` across splits and near-duplicate lectures across sources. YTSeg official train/test share 276 channels; never claim those official splits are channel/course-disjoint.
- `course_id` requires source evidence. If unavailable, channel-disjoint may be reported as a narrower sensitivity design, not course-disjoint.
- Predeclare minimum usable groups/units through a feasibility or precision analysis before viewing final-test model scores; no arbitrary `n=300` target.

## Architecture and related files

- Reuse nested `experiments/evaluation/dataset_contracts.py`, `experiments/scripts/dataset_freeze_evidence.py` and dataset registry patterns. Produce a proposed split manifest with group provenance and audit; do not yet issue D2.
- Add focused split-leakage tests under nested `tests/` if code is changed.

## Implementation Steps

1. Join eligible video IDs to verified course/source IDs and GT; quantify rights/media attrition and distribution by course, channel, topic and chapter count.
2. Construct candidate train/validation/final-test allocations at course group level. Reject shared video IDs, shared course/source groups and missing GT; keep grouping and seed reproducible.
3. Assess whether remaining independent groups support the intended candidate selection and uncertainty analysis. If only channel groups are known, label the weaker design honestly; if too small, decide `blocked_data`/`no_selection`.
4. Document the proposed cohort and all exclusions before inspecting held-out results. Require an explicit master-plan amendment for any departure from the pre-registered YTSeg official split plus frozen multimodal subset, including a custom YTSeg CC BY split, changed GT origin, cohort or primary source. Do not issue D2 before this decision is recorded.

## Success Criteria

- [ ] Split audit reports zero video and verified source/course overlap across all three partitions, or explicitly blocks course-independent claims.
- [ ] Candidate count, independent group count, exclusions and GT coverage are published before D2 freeze.
- [ ] Feasibility decision states the exact claim supported: diagnostic, video-disjoint, channel-disjoint, course-disjoint or blocked.
- [ ] Any changed split/cohort/GT design has a dated master-plan amendment before Phase 4.

## Risk assessment

Only 14 channels exist in the historical CC BY subset, with highly uneven sizes; a valid split may still be statistically weak. Channel labels alone cannot prove course independence.
