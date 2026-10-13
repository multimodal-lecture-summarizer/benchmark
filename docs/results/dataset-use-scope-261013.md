# Dataset use scope — 2026-10-13

Current decision: EduViQA and SSLectures are **historical sources, not used in the current experimental plan**. This is a scope and evidence decision, not a rejection based on unavailable paper PDFs. Retain prior audits, citations and local data for traceability; do not schedule evaluation, new EDA or data acquisition for these two sources under the current plan.

| Dataset | Current role | EDA evidence retained | Reason and consequence |
|---|---|---|---|
| EduViQA (local snapshot) | Historical research only; not used for current RQ3 | Partial inventory of 20 videos and 583 generated transition markers | Separate from EduVidQA. Not task-qualified for current RQ3; generated markers are not independent scene-boundary GT. Do not merge its counts, labels or results with EduVidQA. |
| SSLectures | Historical research only; not used in current experiments | Partial package/source audit of nine records | Chapter creator/annotation provenance remains unverified. RQ1 is historical and has no rerun planned. Do not present SSLectures as an active fallback or scheduled extension. |
| EduVidQA | Retained for RQ3 preparation; no completed RQ3 evaluation | Executed annotation EDA: 5,234 released CSV rows, 296 video groups, seven code cells and four plots | Qualify source transcript/context before answer-only QA. Video/timestamps are needed for claims consuming/locating them. Retrieval relevance/evidence-quality claims remain HOLD without independent relevance/evidence GT. |

The Miro dataset overview retains the two historical rows, explicitly marked `KHÔNG SỬ DỤNG HIỆN TẠI`, rather than deleting the research trail. Both its full-reading grid and editable index must carry the same classification. Historical RQ1 detail is labeled accordingly.

## Owning evidence

- [Benchmark task scope](../../docs/BENCHMARK.md).
- [Dataset EDA evidence](../../docs/DATASET_EDA.md).
- [Research-question master plan](../../plans/260901-unified-scientific-benchmark/framework/00-master-plan.md).
- [EduVidQA preflight](../../plans/reports/rq3-eduvidqa-annotation-preflight-261009-report.md).
- [SSLectures provenance audit](../../plans/reports/rq1-sslectures-260929-1432-package-provenance-nine-row-report.md).

## Remaining work

EduVidQA context acquisition/EDA and endpoint-specific qualification remain pending. Removing two historical sources does not qualify RQ3 or authorize a new benchmark run.
