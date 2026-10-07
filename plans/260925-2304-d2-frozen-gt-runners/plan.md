---
title: "Complete D2 Frozen Ground Truth and Dependent Runners Before Group Validation"
description: "Khóa D2 frozen/ground-truth eligibility theo endpoint, hoàn thiện runner prerequisites, rồi xác minh group 02, group 07 và toàn DAG bằng evidence fail-closed."
status: completed
priority: P1
branch: "baseline/pre-phase1-snapshot"
tags:
  - scientific-benchmark
  - d2-freeze
  - ground-truth
  - runners
  - group-02
  - group-07
blockedBy: []
blocks: []
created: "2026-09-25"
createdBy: "ck:plan"
source: skill
---

# Complete D2 Frozen Ground Truth and Dependent Runners Before Group Validation

> Historical completed plan: the generic D2 contract, profiling and old evaluation runner code cited below was removed on 2026-10-07. Completion refers to the original implementation and receipts, not a currently runnable path.

## Overview

Hoàn tất D2 frozen manifest và ground-truth contract theo dataset × endpoint trước khi dùng artifacts đó để chạy benchmark. Sau đó đối chiếu dependency contract trong notebook manifest, sửa các runner/prerequisite còn thiếu hoặc sai, xác minh group 02 và 07, rồi mới chạy/đánh giá full DAG. Đây là kế hoạch thực thi; smoke/dry-plan không được nâng thành kết quả khoa học.

Repo hiện có TED-LIUM D2 registry/driver cùng manifest entries cho `01a`, group 02 và group 07. Sự tồn tại của source file hoặc fixture-based test chưa chứng minh runner có thể tạo evidence thật. Bắt đầu bằng audit trạng thái live; chỉ sửa các blocker còn tồn tại.

## Phases

| Phase | Name | Status | Dependency |
|---|---|---|---|
| 1 | [Reconcile D2 and Ground Truth Contract](./phase-01-reconcile-d2-and-ground-truth-contract.md) | Completed | — |
| 2 | [Complete Prerequisite Runners](./phase-02-complete-prerequisite-runners.md) | Completed | 1 |
| 3 | [Validate Group 02](./phase-03-validate-group-02.md) | Completed | 1, 2 |
| 4 | [Validate Group 07](./phase-04-validate-group-07.md) | Completed | 1, 2, 3 |
| 5 | [Run and Reconcile Full DAG](./phase-05-run-and-reconcile-full-dag.md) | Completed | 1–4 |

## Execution Order

`D2/GT audit and freeze → prerequisite runner audit/fix → group 02 → group 07 → full DAG`. Group 07 consumes aggregates and shortlists produced by multiple prior groups, so do not run it ahead of its declared inputs. If an endpoint has no eligible released GT, record that group/entry as blocked or `not_run`; do not substitute synthetic labels or claim a full scientific run.

## Plan Interactions

The pending [Dataset Coverage Expansion](../260925-1537-dataset-coverage-expansion/plan.md) proposes IIIT-CVID and EduViQA freezes plus TED-LIUM figures. Coordinate dataset selection and registry edits with that plan before implementation; do not assume its draft provenance, license, or ground-truth claims are already adjudicated. Existing plan statuses and historical notes are not runtime evidence.

## Acceptance Gate

- [x] Each frozen dataset has verified source/revision, rights/access, checksums, stable unit IDs/splits, decode and leakage evidence, plus a released GT contract appropriate to each endpoint claimed eligible.
- [x] `dataset.frozen_manifest`, registry and endpoint matrix agree; every eligible claim traces to a validated receipt and reproducible inputs.
- [x] Required runner sources, imports, manifest declarations, artifact schemas, dependency checks and provenance are reconciled; unsupported endpoints fail closed.
- [x] Group 02 validation records per-entry outcome and artifact receipts; no fixture-only or `not_run` result is reported as benchmark evidence.
- [x] Group 07 runs only after all declared aggregate/shortlist/raw-prediction dependencies exist and pass validation.
- [x] Full DAG is run only after prerequisites pass; DAG order, receipts, statuses, hashes and missing evidence are reconciled in a final report.

## Open Questions

- Which dataset/endpoint combinations beyond TED-LIUM ASR should become D2 eligible in this execution? Resolve from current provenance, rights and annotations during Phase 1; do not assume IIIT-CVID/EduViQA eligibility from the older expansion draft.
