---
phase: 1
title: "Reconcile evidence and claims"
status: pending
priority: P1
dependencies: []
---

# Phase 1: Reconcile evidence and claims

## Overview

Close the existing MIT001 35-video diagnostic and reconcile older readiness prose with the 2026-09-28 evidence. This phase does not rerun feature extraction or 04a/04b.

## Requirements

- Keep the single-course, all-labels-previously-exposed status explicit. Distinguish heuristic visual/acoustic/full fusion from learned C5/C6 and from caption/prosody models.
- Keep the aggregate-publication scope, nine media `review` rows and unresolved GT/SRT/per-file redistribution rights visible; no asset publication is implied.

## Architecture and related files

- Historical MIT001 paired diagnostic outputs and score reports were withdrawn on 2026-10-07. The source-qualification record `plans/reports/260928-0839-mit001-video-rights-media-audit-report.md` remains available.
- Before new evaluation, update the current benchmark protocol and recheck dataset rights, GT and split; do not reuse old score claims.

## Implementation Steps

1. Verify 35/35 source IDs, four extracted feature families, all seven 04b ablations, paired metric table and receipt hashes against the recorded run; classify any mismatch.
2. Verify the dated current-state amendment added to the older readiness plan during planning matches the run evidence, so its 2026-09-27 `not_run` paragraph cannot be mistaken for current status. Leave learned C5/C6 `not_run`.
3. Lock the diagnostic claims, sensitivity for 26 `pass` versus all 35, attribution and release scope. Report no untouched final test and no cross-course inference.

## Success Criteria

- [ ] One evidence ledger links the 35-video run, both existing reports and the exact claim/release scope; no status comes from prose alone.
- [ ] Visual, acoustic and full heuristic fusion are recorded as executed; C5/C6 and absent learned features retain honest status.
- [ ] No MP4, audio, SRT, frame, GT or per-video artifact is scheduled for redistribution under the aggregate-only decision.

## Risk assessment

Old reports may be read as current; date the amendment instead of erasing history. A mismatch in run receipts blocks an updated claim until resolved.
