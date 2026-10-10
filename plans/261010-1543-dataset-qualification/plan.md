# Dataset qualification follow-up

Scope: TED-LIUM → IIIT-CVID → LVVO → MLPDataset → AccessMath → LectureMath → EduVidQA. No GPU inference or large benchmark. Preserve original files and prior outputs. Reuse hash-verified EDA; new review outputs are additive.

- [x] TED-LIUM review executed: eight markers traced; source restoration blocked by missing Arrow/HTTP 401; 50-ID ledger retained.
- [x] IIIT-CVID review executed: all 5,475 frames decoded; 120 metadata overrides; geometry/source-content decisions remain HOLD.
- [x] LVVO review executed: 39/139 source-path matches; remaining mapping/rights/alignment and split HOLD.
- [x] MLPDataset review executed: complete ledgers and anomalies; sampled clip HTTP 403, alignment HOLD.
- [x] AccessMath review executed: orphan and 12 cross-dataset bridges; original camera/timebase/target semantics HOLD.
- [x] LectureMath review executed: milliseconds verified; source media/edited clocks and duplicate review HOLD.
- [x] EduVidQA review executed: six sampled timebase contradictions, transcript ParseError; alignment/retrieval GT HOLD.
- [x] Added executed qualification cells to seven notebooks, manifest, decision log and consolidated report; integrity verification PASS.

Review completion does not mean scientific qualification completion. No cohort or protocol was frozen. See [consolidated report](../reports/dataset-qualification-261010-report.md) and its unresolved questions.

Every decision ledger uses KEEP / REPAIR / EXCLUDE / HOLD with an explicit endpoint. A structurally valid record can remain HOLD for a scientific endpoint. Native test references already inspected cannot be unseen. Source-group candidates are not automatically excluded. Freeze only reviewed cohorts and protocols; otherwise report no qualified scientific cohort.
