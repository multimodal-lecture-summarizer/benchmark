---
phase: 5
title: "Add statistical analysis and selection gates"
status: pending
priority: P1
dependencies: [4]
effort: "4-7 days plus full-run time"
---

# Phase 5: Add statistical analysis and selection gates

## Overview

Thay rank/composite và CI trên seed giả bằng phân tích paired ở talk/video level, practical thresholds và Pareto selection có khả năng trả về `no_selection`.

## Requirements

- Primary unit, metric, comparison family và threshold được pre-register trước final test.
- Each task/GT track has exactly one primary metric; factual-support/evidence and budget compliance may be hard eligibility gates rather than scalar components.
- Seed dùng cho stochastic repeat, không được xem là independent sample thay cho video/talk.
- Quality, latency, memory, cost và failure giữ dạng vector; composite chỉ là visualization phụ nếu được giải thích.

## Architecture

`Eligible raw runs -> paired unit table -> omnibus gate -> paired post-hoc -> hierarchical bootstrap -> Holm correction -> Pareto shortlist -> decision record`.

## Related Code Files

- Modify/create statistical utilities under `multimodal-lecture-summarizer/experiments/evaluation/`
- Modify: `multimodal-lecture-summarizer/experiments/scripts/ablation_runner.py`
- Modify notebooks 01–07 analysis cells through their generator
- Create decision artifacts under experiment output directories, not hand-written report tables

## Implementation Steps

1. Xây paired unit table, giữ candidate rows trên cùng talk/video; nêu rõ missing-pair policy.
2. Tính corpus-level và macro per-unit metrics khi phù hợp; không average ratio sai denominator.
3. Chạy hierarchical bootstrap tối thiểu 10,000 resamples ở talk/video level; cluster speaker/source khi metadata cho phép.
4. Dùng omnibus test trước post-hoc; paired permutation/bootstrap delta cho candidate comparisons.
5. Áp dụng Holm correction theo task/metric family; lưu raw và adjusted p-values.
6. Báo effect size, 95% CI delta và threshold có ý nghĩa thực tiễn; `p < .05` không tự động đồng nghĩa tốt hơn.
7. Xây Pareto frontier trên quality, latency/RTF, peak memory/cost và failure rate.
8. Tạo decision rule: `research_best`, `deployable_best`, `tie/indistinguishable`, `no_selection`.
9. Đọc strata đã được tạo và freeze từ Phase 2 EDA: duration, noise, resolution/codec, language/accent và label frequency khi cỡ mẫu đủ; không tái bin hoặc data dredging sau khi xem final test.
10. Human metrics: agreement CI và adjudicated score; tách automatic vs human evidence.
11. Refuse selection when primary metric improves but factual-support, evidence-grounding, failure-rate or summary-budget gate fails; do not compensate with a weighted composite.

## Success Criteria

- [ ] CI/p-value dùng independent units, không dùng một aggregate row hay 3 seed như n=3 thay cho video.
- [ ] Pairwise tables có raw/adjusted p, delta CI, effect size và practical threshold.
- [ ] Missing candidate units được hiển thị; không impute zero.
- [ ] Pareto frontier là đa chiều thật; không thay bằng sorted scalar composite.
- [ ] Selection record nêu data scope, uncertainty, constraints và có thể trả `no_selection`.
- [ ] No task changes primary metric, scorer parameters, collar/IoU/k, normalization or comparison family after final-test outputs are visible.
- [ ] Mọi stratified result dùng frozen EDA bins, báo `n` độc lập và CI per stratum; stratum quá nhỏ được ghi `insufficient_n`, không gộp tùy ý.
- [ ] Rerun analysis từ cùng raw artifacts tạo byte-equivalent hoặc numerically equivalent tables.

## Risk Assessment

- Test set nhỏ làm CI rộng: chấp nhận `no_selection`; không tăng n giả bằng frame/chunk.
- Nhiều metrics tạo multiplicity: chốt primary metric và correction families trước khi xem final results.
