# D2 contract + ablation runner progress — 2026-09-23

## Status

| Scope | Done | Total | Progress | State |
|---|---:|---:|---:|---|
| Phase 1 | 7 | 12 | 58.33% | in-progress |
| Phase 2 | 0 | 20 | 0.00% | in-progress |
| Phases 3–7 | 0 | 43 | 0.00% | pending |
| Phase checklist roadmap | 7 | 75 | 9.33% | in-progress |
| Plan-level completion criteria | 0 | 21 | 0.00% | unchanged |

## Evidence reconciled

- Phase 1 scoped commit: `6a729515`; validation: 27 passed.
- Current slice: D2 schema/validator infrastructure + `RQ0_OD` ablation adapter; 57 focused and 78 broader tests passed; review approved.
- Backfilled 1 Phase 1 criterion: combo config reaches runner contract; value-sensitive command/output contract tests reject mismatch, empty/non-finite metrics, diagnostic evidence, incomplete provenance, stale/missing output, non-zero exit and timeout.
- Phase 2 set `in-progress`; 0 success criteria checked. No acquired real D2 bundle, frozen split, released box/class GT or official result.
- All 7 phase files + `plan.md` swept. No other checkbox met end-to-end acceptance.

## Scope changes

- None. Slice remains infrastructure only; no D2 data/result claim, no winner claim.

## Blockers and risks

| Item | Owner | Unblock path |
|---|---|---|
| Real D2 bundle absent | Benchmark/data owner | Acquire released labeled bundle; produce D2 receipt, profiles, required tables/figures, leakage audit, frozen IDs/splits/checksums; validate as one bundle. |
| OD producer remains diagnostic | OD benchmark owner | Supply released box/class GT + frozen D2 manifest; run producer with real provenance; pass ablation output validator. |
| `00c` gate incomplete | Benchmark infrastructure owner | Extend validator to require data card, statistics/split/quality/attrition/leakage artifacts and figure manifest before D2 success. |
| Group 02/07/full-DAG wrappers absent | Runner owner | Implement wrappers; run smoke topology and standalone/full-DAG equivalence checks. |

## Next actions

1. Main agent: finish implementation plan and unfinished tasks; critical before any Phase 1/2 completion claim. Done = remaining Phase 1 acceptance gates pass with direct evidence.
2. Data owner: qualify one released OD dataset. Done = real D2 bundle validates, split leakage gate passes, box/class GT provenance complete.
3. Runner owner: execute `RQ0_OD` ablation on frozen D2 data. Done = non-diagnostic raw predictions + per-combo real artifacts; no result reuse/config drift.
4. Runner owner: add group 02/07/full-DAG paths. Done = target selection, topological order, resume and equivalence tests pass.

## Unresolved questions

- Which released OD dataset revision will supply box/class GT for first D2 run?
