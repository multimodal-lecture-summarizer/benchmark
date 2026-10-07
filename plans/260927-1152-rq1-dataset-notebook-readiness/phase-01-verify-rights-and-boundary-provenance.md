---
phase: 1
title: "Verify rights and boundary provenance"
status: completed
priority: P1
dependencies: []
---

# Phase 1: Verify rights and boundary provenance

## Overview

Determine whether real AVLectures timed-TOC lectures can be used for a noncommercial RQ1 pilot. Keep YTSeg as the pre-registered alternative. This phase is a read-only/metadata-scale qualification, not bulk media acquisition.

## Requirements

- Record source URL, repository/archive revision, declared license, original OCW page, media URL, rights notices and GT source for every sampled lecture.
- Distinguish 5 timed-TOC courses from 10 joined-clip courses. The latter form a separate bias/sensitivity stratum, not the first primary pilot.
- Never treat repository CC0 as the license for OCW videos; never infer rights for one lecture from another.

## Architecture

Write a candidate ledger with one record per lecture: `source_id, course_id, lecture_id, boundary_origin, video_url, gt_url, rights_url, rights_status, access_status, exclusion_reason`. Use a fresh diagnostic notebook outside the official 22-node manifest to display source checks and small metadata/media probes. All network operations must be bounded, logged and resumable.

## Related Code Files

- Create: `experiments/notebooks/diagnostics/rq1_dataset_qualification.ipynb` and a small source adapter under `experiments/scripts/` only if existing dataset-probe helpers cannot express these fields.
- Reuse: `experiments/scripts/probe_dataset_feasibility.py`, dataset registry patterns, `experiments/evaluation/dataset_contracts.py`.
- Inspect: `benchmarks/scripts/fetch_ytseg_subset.py`; its current real path fabricates boundaries and must not feed qualification.

## Implementation Steps

1. Check whether an author-controlled AVLectures course archive actually exposes `videos/` and `segmentation/segments_ts.txt`. Save URL, status, date, size and checksum when present. An inaccessible archive is `blocked_access`, not a passed source.
2. Select a small predeclared cross-course sample from timed-TOC courses before looking at model outputs. Resolve each item to its OCW page; inspect CC notice, reserved third-party notice and media access. Retain explicit `unknown` when a right cannot be established.
3. Parse published boundary source, verify increasing timestamps within decoded video duration, map source-to-processed offsets and inspect a few boundaries against the video. Count missing/ambiguous alignments and attrition. Do not edit or invent timestamps.
4. Independently probe YTSeg official metadata split, bounded lecture/science filter and video rights for sampled IDs. Keep creator chapters labeled as creator/editorial GT; record whether only text/audio is lawful and available.
5. Compare candidates against the research master decision. If AVLectures would become primary, draft the decision change with scope and metric implications for review before any final-test inference.

## Success Criteria

- [ ] A dated candidate ledger has direct source and rights evidence for every sampled lecture; no blanket license claim.
- [ ] At least one source exposes actual video and independently published chapter timestamps with demonstrated alignment, or an explicit `blocked_access`/`blocked_rights`/`blocked_gt` decision.
- [ ] Timed-TOC and joined-clip AVLectures units remain distinguishable.
- [ ] YTSeg probe uses official data and records media attrition; stub IDs and generated boundaries are rejected.

## Risk Assessment

AV archive link may be missing; use source OCW timed TOC only if exact lecture mapping and existing GT can be proven. OCW pages can contain reserved content; exclude uncertain units. Source labels may be editorial rather than expert annotations; report their provenance and audit disagreement, never rename them expert GT.
