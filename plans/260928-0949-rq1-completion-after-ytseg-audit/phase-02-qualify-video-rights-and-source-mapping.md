---
phase: 2
title: "Qualify video rights and source mapping"
status: pending
priority: P1
dependencies: [1]
---

# Phase 2: Qualify video rights and source mapping

## Overview

Qualify a small, predeclared candidate set before media acquisition. Treat YTSeg dataset rights, underlying video rights and YouTube access terms as separate fields; record GT and course source for each candidate.

Scope decision (2026-09-28): perform file-level rights, exception, decoded alignment and GT qualification **only for IDs actually selected for the proposed cohort**. The 538-row MITFLD manifest and 468 lecture-like metadata candidates are a discovery pool, not a mandate to audit every file. Keep rejected/attrited selected IDs in the denominator.

Selection decision (2026-09-28): user chose 35 MITFLD candidates distributed across courses. Exclude the ten previously inspected pilot IDs; select one ID from each of the 21 remaining course groups and a second ID from 14 groups. Use pinned map SHA-256 and dataset revision, fixed seed, deterministic ID ranking and a same-course reserve queue. Assign proposed split groups before per-file qualification. This is a candidate selection, not D2 or a change to the master RQ1 data claim.

Selection artifact: [35-ID v2 manifest and receipt](../reports/rq1-cohort-260928-1120-mitfld-35-selection-report.md). The v1 artifact at 11:12 is superseded because its CSV omitted source `review_flag`; v2 preserves that flag for the two 18.217 shortlink exceptions. Continue the file-level ledger against v2 only.

Qualification progress: [35-ID rights, alignment and GT report](../reports/rq1-qualification-260928-1126-mitfld-selected-35-report.md). Every ID has an exact OCW MP4 pointer and valid published annotation structure/HF container bounds. Three IDs have one decoded HF↔OCW boundary spot-check each. No ID is fully rights/GT/alignment-qualified; retain all 35 as pending, with no post-score replacement or D2 freeze.

Latest [selected-35 follow-up](../reports/rq1-followup-260928-1319-mitfld-35-rights-alignment-gt-report.md): OCW duration bounds pass 35/35. Of 105 decoded first/middle/last `frags` windows, 102 pass local A/V thresholds and three in course 3.091 need review; 16 remote-read failures were retried successfully. `JuKKBf-uSDI` is on rights hold because a slide explicitly excluded from CC appears in its MP4. `9uqKU5ZDwfM` and `neBeTYziSLo` have specific unresolved component-rights questions; other selected videos have not had whole-video content clearance. User waived author email; independent GT protocol exists, actual GT does not. Current denominator: **1 hold, 34 pending, 0 fully eligible**. Phase stays pending.

## Requirements

- Use the current YTSeg revision and full-row audit as baseline. Its official split is not channel-independent; its CC BY subset is train-only and contains 14 channels.
- For every selected video record `video_id`, channel, proposed course, GT origin, rights source/date, platform access route, exceptions, decoded alignment status and exclusion reason. Unknown stays unknown. GT provenance may come from a documented independent annotation process; author correspondence is useful but not an unconditional gate if independent GT is created and licensed.
- No blanket rights conclusion from a dataset card, historical API check or one video's license; no bulk download before clearance.

## Architecture and related files

- Reuse/extend nested `experiments/scripts/rq1_candidate_ledger.py` and its existing outputs; source report: `plans/reports/research-260928-0936-ytseg-video-rights-channel-split-report.md`.
- If automated metadata checks are added, keep bounded batches, API provenance and focused tests under nested `tests/`; store decisions as a dated qualification ledger, not as a mutated frozen D2 record.

## Implementation Steps

1. Predeclare a stratified pilot across several channels from `ytseg-cc-by`; freeze candidate IDs before checking model performance. Record the selection rule and denominator. Include an alternate multi-course source only if YTSeg fails and its rights/GT can be evaluated with the same schema.
2. Check live license/status using an authorized source or official API, inspect attributable rights/third-party exceptions and permitted access method. Record stale, removed, unavailable and ambiguous cases separately.
3. Verify what the published chapter timestamps represent and whether video, transcript/audio and GT resolve to the same original unit. Check `course_id` mapping from primary source; do not equate channel with course.
4. Freeze proposed cohort IDs and a reserve/replacement rule before further eligibility checks; expand the audit only to those selected IDs. Decide `go_candidate`, `blocked_rights`, `blocked_access` or `blocked_gt`, with attrition counts. Do not replace failures after inspecting model scores.

## Success Criteria

- [ ] Every proposed unit has dated source-backed rights/access and GT provenance or an explicit unknown/exclusion; no silent default to allowed.
- [ ] Pilot and expanded denominators are reproducible; no video media is acquired on a rights assumption.
- [ ] Decision states whether any candidate can proceed to independent split design.

## Risk assessment

Licenses/status and YouTube access can change; preserve check time and source. A CC BY flag does not waive platform conditions or prove third-party content clearance. Missing API access is `blocked_access`, not a pass.
