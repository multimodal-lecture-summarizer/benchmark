---
title: "RQ1 lecture dataset qualification and benchmark notebook setup"
description: "Verify real lecture chapter GT and rights, then prepare the existing notebook DAG for an honest RQ1 pilot."
status: blocked
priority: P1
branch: ""
tags: [scientific-benchmark, rq1, dataset-qualification, notebooks]
blockedBy: []
blocks: []
created: "2026-09-27T04:55:05.701Z"
createdBy: "ck:plan"
source: skill
---

# RQ1 lecture dataset qualification and benchmark notebook setup

> Historical RQ1 plan: the generic dataset-contract and profiling code cited below was removed on 2026-10-07. RQ1 is no longer an active rerun target; preserve the historical findings without treating these steps as current instructions.

## Verified state — 2026-09-27

| Candidate | Direct evidence | Decision now |
|---|---|---|
| AVLectures CwS | [Author paper](https://arxiv.org/html/2210.16644) §3.2: 350 lectures/15 courses; 5 courses use OCW timed table-of-contents boundaries, 10 reassemble separately filmed clips. [Author repository](https://github.com/Darshansingh11/AVLectures) specifies `segments_ts.txt`, video, subtitle and OCR layout. | Conditional lead for multimodal RQ1. No course archive/video/GT download was verified from the repository; no per-video rights clearance yet. Prefer the 5 timed-TOC courses for the first pilot. Keep joined-clip courses as a separate sensitivity stratum because editing cues can reveal boundaries. |
| MIT OCW source | [OCW reuse terms](https://mitocw.zendesk.com/hc/en-us/articles/4414774353051-What-are-the-requirements-of-use-for-MIT-OpenCourseWare) permit noncommercial reuse with attribution and share-alike. [Reserved-content rule](https://mitocw.zendesk.com/hc/en-us/articles/4414756181403-How-is-all-rights-reserved-content-different-from-the-rest-of-OCW-content) excludes marked third-party content. A [Single Variable Calculus course page](https://ocw.mit.edu/courses/18-01sc-single-variable-calculus-fall-2010/pages/1.-differentiation/part-a-definition-and-basic-rules/session-1-introduction-to-derivatives/) is live and links video excerpts. | Course-level evidence exists; rights and exact media/GT alignment for candidate lectures remain unverified. GitHub CC0 covers repository material, not OCW video rights. |
| YTSeg | [Dataset card](https://huggingface.co/datasets/retkowski/ytseg): official splits, chapter timestamps, text/audio, CC BY-NC-SA 4.0; authors explicitly do not own source-video copyright. Local probe `multimodal-lecture-summarizer/plans/260830-1917-scientific-benchmark/probes/output/ytseg_summary.json` did not load; `benchmarks/manifests/frozen_manifest_v2.json` is a dry stub. | Retain as the master plan's pre-registered candidate and audio/text comparison. Video rights, media availability and lecture-only visual subset require separate proof. Creator chapters are independent of this model, not expert-annotated truth. |

**No candidate is currently qualified for an official multimodal RQ1 run.** No video archive or GT payload was downloaded in this verification. A live OCW course page does not establish AVLectures archive availability or eligibility for every video.

## Scope and research contract

The [research master plan](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) names YTSeg official split plus a frozen downloadable multimodal subset for RQ1. AVLectures is a **candidate addition**, not a silent replacement. Record any primary-dataset change and its GT/metric implications in the frozen decisions before final-test inference. The later [pipeline plan](../260921-1943-scientific-benchmark-pipeline/plan.md) requires released/pre-existing GT; project-created annotation and pseudo-labels cannot enter official selection without a separate decision change.

Set up the existing `00a`, `00b`, `00c`, `04a`, `04b` notebooks and their runner contracts. One diagnostic qualification notebook may be added outside the 22-node official manifest. Preserve the current 22-node count by making RQ1 feature extraction/receipt part of `04a`; do not run unrelated stage benchmarks on different datasets to fabricate a joint lecture record. No **final** model selection, large media acquisition, full DAG, thesis claim, or commit is part of this plan.

## Dependency decision

At planning time, `04a` required ASR, scene, OCR and caption **benchmark predictions** from datasets without shared lecture/video IDs. The current manifest instead requires one cohort's frozen manifest, registry and endpoint matrix; `04a` derives hash-bound, same-video `chapter.input_features`, and `04b` consumes those features and the `04a` shortlist. This removes the invalid cross-dataset join for the diagnostic run. Official RQ1 remains blocked until the lecture cohort meets rights, D2 and split requirements; TED-LIUM and IIIT-CVID stage predictions must not be joined by position or label.

## Phases

| Phase | Name | Status | Exit |
|---|---|---|---|
| 1 | [Verify rights and boundary provenance](./phase-01-verify-rights-and-boundary-provenance.md) | Pending | Access/rights/GT decision for a small real sample |
| 2 | [Qualify and freeze RQ1 cohort](./phase-02-qualify-and-freeze-rq1-cohort.md) | Pending | D2 receipt and independent chapter GT on disjoint splits |
| 3 | [Repair chaptering runners and notebooks](./phase-03-repair-chaptering-runners-and-notebooks.md) | Pending | Fail-closed 04a/04b and coherent same-unit feature inputs |
| 4 | [Validate pilot and benchmark readiness](./phase-04-validate-pilot-and-benchmark-readiness.md) | Pending | Executed small pilot and explicit GO/BLOCKED ledger |

## Cross-plan relationship

This is a scoped prerequisite for RQ1 in [scientific benchmark pipeline](../260921-1943-scientific-benchmark-pipeline/plan.md), especially Phase 2 dataset qualification and Phase 4 stage runners. It supersedes the unverified YTSeg `n=300`/stub-fetch assumptions in the [older Phase 5](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/phase-05-ytseg-subset-retrieval-scale.md); it does not mark either parent plan complete. The pending [OCR endpoint plan](../260926-1416-unlock-9-downstream-tasks/plan.md) can proceed independently; its IIIT-CVID labels cannot substitute for chapter GT.

## Overall acceptance

- [ ] At least one candidate has verified archive/source access, per-unit rights provenance and independently published chapter boundaries; otherwise stop with a named blocker.
- [ ] Train, validation and final-test feasibility is measured; any learned-model claim uses source/course-disjoint splits. Eligible units have decoded media, hashes, measured attrition, GT audit and D2 receipts for both 04a/04b endpoints; no dry/stub item qualifies.
- [ ] `04a`/`04b` fail when independent chapter GT or same-unit feature receipts are absent; no scene, duration or guessed boundary becomes GT.
- [ ] The frozen RQ1 scorer uses ±3-second collar F1 as primary and reports ±5/10-second, Pk and WindowDiff secondary metrics; empty predictions are accounted for without invented midpoints.
- [ ] Selection uses validation only; final test stays sealed until configuration is frozen. Diagnostic pilot cannot be reported as official RQ1 performance.
- [ ] Shared loader and receipt identity enforce split/mode; no notebook-only filter or manifest ordering can expose final test during selection.
- [ ] Manifest/notebook/runner contracts, focused tests and one executed diagnostic notebook agree; all 22 manifest nodes retain explicit status.

## Execution result — 2026-09-27: official RQ1 BLOCKED, diagnostic chain works

Evidence: `experiments/outputs/diagnostic/rq1_qualification/candidate_ledger.json` (bounded, logged, cached probes) and the executed `experiments/notebooks/diagnostics/rq1_dataset_qualification.ipynb`, which writes `experiments/outputs/diagnostic/rq1_pilot_runs/<stamp>/readiness_ledger.json`.

| Gate | Status | Evidence |
|---|---|---|
| AVLectures archive | blocked_access | india-data.org API needs an auth token. Repo LICENSE is CC0 but the README badge says CC BY-NC 4.0; neither covers the videos |
| OCW 18.01 timed TOC | diagnostic pilot only | 268 clip pages → 35 source lectures, 30 unexcluded. 6 sampled by sha256; ffprobe aligned 5; lec11 excluded (clip end past media end). Pages are CC BY-NC-SA 4.0 with no reserved marking; archive.org item is CC BY-NC-SA 3.0. Human rights review pending |
| Course-disjoint splits | blocked_data | All OCW lectures come from one course. YTSeg official val/test share 7 channels in the 40+40 sample |
| YTSeg | text/audio candidate only | rev 4ee1c1f, val 1447/test 1448. No video is distributed (blocked_rights). Chapters are creator/editorial |
| D2 receipt | blocked | `ocw_1801_timed_toc_d2.yaml` is recorded as `blocked_decision`; there is no official freeze |
| Learned C5/C6 | not_run | `checkpoints/c5_real.pt` has no train-only provenance manifest; C6 has no checkpoint |
| 04a/04b contract | done | Fallbacks to scene boundaries, duration and midpoints are removed. Validation-only `--evaluation-mode selection`, `chapter.input_features`, ±3 s primary scorer, manifest v2 edges, 26 focused tests |

Decision (2026-09-27, user): keep RQ1 multimodal. YTSeg audio/text may remain a supporting comparison, but it does not replace the multimodal primary cohort. Seek AVLectures timed-TOC courses with independent video, chapter GT and rights evidence; do not run official selection or final test until course-disjoint splits and D2 gates pass.

### New MIT001 local diagnostic evidence (2026-09-27)

Paths in this section are relative to the nested `multimodal-lecture-summarizer/` app.

`experiments/datasets/avlectures_mit001/run_local_diagnostic.py` ran 04a and 04b on 35 local MIT18.01JF07 MP4/SRT lecture pairs with AVLectures `segments_ts.txt` chapter GT. The run at `experiments/outputs/diagnostic/rq1_mit001_local_runs/20260927T103316Z` completed both notebooks and is validation-only. Its source receipt records a truncated gzip archive and rights review pending; the media audit has 26 pass and 9 review rows. All 35 units belong to one course, so this is not a course-disjoint D2 cohort or an official RQ1 result.

The earlier OCW ledger's 35 found/30 unexcluded counts use a different source of GT: published OCW clip offsets. Its `lec11` exclusion does not apply to the AVLectures GT run; the two cohorts must be reported separately.

Subsequent diagnostic run `experiments/outputs/diagnostic/rq1_mit001_local_runs/20260927T121111Z` completed 04a and 04b with exit code 0 on all 35 units. Scene and OCR input features are available for 35/35, bound to each source video; transcript+scene and transcript+OCR ablations ran. Visual caption, acoustic and all-modality ablations remain `not_run`; learned C5/C6 remain `not_run`. The frozen manifest and endpoint matrix mark `diagnostic_selection_eligible=true` and `scientific_selection_eligible=false`. This run is not an official RQ1 claim.

Paired diagnostic macro boundary F1 (±3 s): fixed-duration 0.0198, transcript 0.0294, transcript+scene 0.0486 (23 wins, 0 ties, 12 losses against transcript), transcript+OCR 0.0502 (13 wins, 2 ties, 20 losses). The OCR mean does not imply consistent per-video improvement. The OCR extractor sampled at most 12 frames per lecture. All 35 labels had appeared in the earlier pilot, so no result here is held-out. Inspect the per-lecture errors, especially the nine `review` media-audit rows, before changing extraction density or thresholds.

Earlier feasibility check: the existing production `SceneDetector` decoded `ocw-18.01-f07-lec01_300k.mp4` and returned 138 scenes with the default content threshold and frame skipping. This preceded the source-bound 35-video diagnostic run above and is retained as chronology, not counted as a separate evaluated result.

### Scope amendment: only 35 MIT001 videos available (2026-09-27)

The user has no additional course archives. Continue a **single-course multimodal study** on the 35 local MIT001 videos; do not make acquiring two more courses a prerequisite for this scoped work. The research question is whether source-backed visual/audio signals improve chapter segmentation over duration-only and transcript-only baselines **within MIT001**. This study cannot support generalization to unseen courses or the original cross-course RQ1 claim.

All 35 lecture labels and baseline metrics were included in the first diagnostic selection run. A new subset of these IDs cannot be described as an untouched final test. Predeclare feature extraction, algorithms, thresholds, exclusions and metrics before another evaluation; use paired per-lecture comparisons and, if a learned method is attempted, out-of-fold predictions with fitting and tuning confined to each training fold. Report prior exposure and any tuning on these 35 units. Keep the 04a/04b official final-test gate sealed; publish the scoped study in a separate diagnostic analysis namespace.

Next execution order after the 35-video diagnostic: (1) resolve nine media-audit `review` rows and per-video rights/provenance; (2) inspect paired per-lecture wins, losses and boundary errors; (3) predeclare any OCR sampling or chaptering change before another diagnostic run; (4) add acoustic/visual-caption features only with same-video provenance and a real predictor. C5/C6 remain `not_run` until actual train-only checkpoints and feature tensors exist.

### Current-state amendment — 2026-09-28

The 2026-09-27 `not_run` description for MIT001 visual/acoustic/full fusion is historical. The [paired 35-video diagnostic](../../multimodal-lecture-summarizer/plans/reports/rq1-mit001-multimodal-260928-0909-paired-diagnostic-report.md) and [current diagnostic write-up](../../docs/results/MIT001_CHAPTERING_DIAGNOSTIC.md) show all seven 04b heuristic variants executed on the same 35 units; visual, acoustic and `all_modalities` now have real per-video results. Learned C5/C6 remain `not_run`. The [MIT001 rights/media audit](../../multimodal-lecture-summarizer/plans/reports/260928-0839-mit001-video-rights-media-audit-report.md) fixes an aggregate-only publication scope and retains all nine media `review` rows; it does not clear redistribution of source assets.

The [full 19,299-row YTSeg audit](../../multimodal-lecture-summarizer/plans/reports/research-260928-0936-ytseg-video-rights-channel-split-report.md) supersedes the 40+40 sample overlap statement above: 276 train/test channels overlap and 1,444/1,448 test rows belong to channels in train. Video rights are not cleared, and no `course_id` is available. The scoped [completion plan](../260928-0949-rq1-completion-after-ytseg-audit/plan.md) lists the remaining rights, split, D2 and official-run gates. Phase 2 of this readiness plan remains blocked for an official independent cohort; the completed MIT001 run remains a single-course diagnostic.

## Open questions

1. Can an AVLectures CwS course archive with `segments_ts.txt` and media be retrieved from an author-controlled source, or must the pilot use original OCW media and timed TOC?
2. Which sampled OCW video pages are covered by CC BY-NC-SA without marked reserved third-party content?
3. Resolved: keep the multimodal RQ1 goal. The official claim remains blocked until eligible multimodal courses, GT, rights and course-disjoint splits exist.
