---
title: "Harden Endpoint Eligibility and Complete Group and DAG Verification"
description: "Khắc phục endpoint gating fail-open, làm sạch focused test, đối soát từng entry group 02/07 và xác lập bằng chứng/full-DAG gate trung thực."
status: completed
priority: P1
branch: "baseline/pre-phase1-snapshot"
tags:
  - scientific-benchmark
  - endpoint-eligibility
  - fail-closed
  - group-02
  - group-07
  - full-dag
blockedBy: []
blocks: []
created: "2026-09-26"
createdBy: "ck:plan"
source: skill
---

# Harden Endpoint Eligibility and Complete Group and DAG Verification

## Overview

Plan follow-up sau audit plan `260925-2304-d2-frozen-gt-runners`. Bằng chứng hiện có xác nhận TED-LIUM D2 với manual GT 20/20, chạy thật `01a`/`01b`, và dry-plan đủ 22 node. Còn lỗi endpoint selector fail-open khi endpoint matrix receipt bị thiếu/lỗi, focused SAPI fixture có thể tạo WAV rỗng, kết quả group 02/07 mới là một phần, và chưa có full-DAG run hoặc per-node ledger.

Mục tiêu là hoàn thiện các vấn đề đó mà không biến dry-plan, smoke, dữ liệu audio-only hay node `blocked/not_run` thành kết quả khoa học. Full DAG chỉ được chạy chính thức khi tất cả dependency đầu vào và endpoint GT tương ứng thực sự đủ điều kiện.

## Phases

| Phase | Name | Status | Depends |
|---|---|---|---|
| 1 | [Enforce Fail-Closed Endpoint Eligibility](./phase-01-enforce-fail-closed-endpoint-eligibility.md) | Completed | — |
| 2 | [Repair Focused Regression Coverage](./phase-02-repair-focused-regression-coverage.md) | Completed | 1 |
| 3 | [Reconcile Group 02 Entries](./phase-03-reconcile-group-02-entries.md) | Completed | 1, 2 |
| 4 | [Reconcile Group 07 Dependencies](./phase-04-reconcile-group-07-dependencies.md) | Completed | 1–3 |
| 5 | [Close Full DAG Readiness and Evidence Ledger](./phase-05-close-full-dag-readiness-and-evidence-ledger.md) | Completed | 1–4 |

## Execution Sequence

`endpoint gate → regression coverage → all group 02 entries → all group 07 entries → full-DAG readiness/ledger → official full DAG only if eligibility gates pass`.

## Existing Plan and Dataset Work

- Follow-up to [D2 Frozen Ground Truth and Dependent Runners](../260925-2304-d2-frozen-gt-runners/plan.md). The prior plan's completion flags are historical; this plan closes the newly found gaps.
- Coordinate visual/QA dataset eligibility with the pending [Dataset Coverage Expansion](../260925-1537-dataset-coverage-expansion/plan.md). That plan's draft dataset/license/GT claims must be independently verified before use.
- Current TED-LIUM eligibility is ASR-specific. It cannot satisfy scene, keyframe, OCR, caption, detection, tracking, chaptering, summary, retrieval or QA eligibility by itself.

## Acceptance Gate

- [x] Full/official stage execution requires a valid, integrity-checked endpoint matrix and eligible dataset IDs for the requested endpoint; absence, corruption or schema mismatch fails closed.
- [x] Tests cover missing, malformed, stale and negative endpoint matrices, eligible endpoint selection, composite runners, and the SAPI empty/invalid-WAV case.
- [x] Every group 02 entry has an explicit `PASS`, `BLOCKED`, `NOT_RUN` or `FAILED` outcome with its own prerequisites and evidence; no group-level pass inferred from dry-plan alone.
- [x] Both group 07 entries are checked against all declared upstream artifacts and tested to block before execution when dependencies are missing.
- [x] Full-DAG dry-plan covers all 22 manifest nodes and exact dependency edges; a per-node ledger identifies what actually ran and its status.
- [x] Claim a completed official full DAG only when every required endpoint is scientifically eligible and all node artifacts/receipts validate. Otherwise preserve the DAG as blocked and list exact dataset, released-GT and artifact prerequisites; do not mark this phase complete as if the run succeeded.

## Open Questions

- Which additional dataset × endpoint pairs can be qualified with released GT and rights for visual and downstream stages? Resolve through the existing dataset coverage work and current source evidence, not assumptions in old plan drafts.
