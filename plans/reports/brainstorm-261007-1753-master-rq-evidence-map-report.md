# Brainstorm: master as an RQ and evidence map

**Date:** 2026-10-07  
**Mode:** markdown  
**Decision:** Keep `00-master-plan.md` strategic. Keep task protocols and execution detail in their owning documents.

## Problem and agreed scope

The master was updated on 2026-10-07, but its RQ table still lets readers infer that all four questions are active and that a multimodal summarization result is near. The current near-term route is a conditional, text-only RQ2 structure comparison. Qualified video media, references and ground truth are not yet available for a broader multimodal claim.

This brainstorm defines proposed changes to the master only. It does not approve a new benchmark run, revise a frozen outcome or change historical evidence. Success means a reader can identify each RQ's status, next evidence gate and maximum defensible claim without treating old plans as an execution queue.

## Problem-first check

| Question | Finding |
|---|---|
| Why change the master? | The scientific scope and execution readiness are easy to conflate. |
| Underlying problem | Readers may interpret proposed datasets, models and RQs as qualified, run or selected. |
| Risky assumption | A single detailed master could stay synchronized with task-specific protocols. It would duplicate changing candidate and cohort details. |
| Alternative framings | Clarify RQ status; clarify claim ceilings; clarify which document owns task execution. All three are needed. |
| Evidence strength | Strong for documentation mismatch: current master, benchmark protocol, RQ2 plan and historical matrix can be compared directly. Experimental evidence remains pending for most RQs. |
| Validation | Review each proposed sentence against current protocol, EDA ledger, RQ2 amendment and retained results; check links and historical warnings. |
| Stop rule | Do not claim an RQ has a winner or an unseen test without executed, source-linked item-level evidence. |

## Approaches considered

| Approach | Benefit | Cost | Decision |
|---|---|---|---|
| Patch a few sentences | Fastest | RQ status and ownership stay ambiguous | Reject |
| Add status, gate and claim ceiling; link task protocol | Compact, auditable, less duplication | Requires careful wording around RQ2 and historical material | **Choose** |
| Copy full task matrix and implementation schedule into master | One document to scan | Duplicates `docs/BENCHMARK.md`; likely to drift | Reject |

## Proposed master structure

1. **Purpose and document ownership.** Master owns research questions, status, evidence gates and claim ceilings. `docs/BENCHMARK.md` owns task eligibility, candidate families and metrics; `docs/DATASET_EDA.md` owns observed cohort status; task plans own run details. Mark adjacent `02-benchmark-matrix.md` and `decisions-log.md` as historical where linked.
2. **Near-term and conditional objectives.** Near-term: test fixed-chunk S1 against predicted-structure S3 on a qualified lecture-text cohort with the same generator and measured equal cumulative token budgets. Video-grounded multimodal summarization and retrieval remain conditional on task-matched media, labels and outcome qualification.
3. **RQ status table.** Each row has question, status, next gate and claim ceiling. RQ1: historical diagnostic, withdrawn saved results, no rerun planned. RQ2: pending full-cohort TIB EDA and reference/outcome reconciliation; no winner. RQ3: proposed, source/media/answer/evidence GT unqualified. RQ4: dependent, shared eligible units and measured quality/resource runs absent.
4. **Task portfolio pointer.** Link the active task matrix in `docs/BENCHMARK.md` for slide transitions, board keyframes, OCR recognition/spotting, caption/grounding, separate detection tracks and tracking. Do not call these completed RQ0 results or copy provisional candidate IDs into the master.
5. **Shared evidence ladder.** Candidate proposal → source/rights/media/GT qualification → executed EDA with denominators and leakage audit → frozen same-unit comparison → item-level predictions, failures, compute receipts and paired uncertainty → claim limited to measured target. Use `not_eligible` or `no_selection` when a gate fails.
6. **RQ2-specific claim boundary.** S3 needs a frozen source-only predicted-structure route and cannot inherit withdrawn RQ1 performance. No human scoring for this study. Prior ROUGE-L F1 against creator abstracts is an outcome to reconcile after all-split EDA and, if retained, measures abstract agreement only. Record whether creator `test` references were actually read; once inspected, that split cannot support an unseen-holdout claim. TIB is text-only for this comparison; VISTA needs separate media/reference qualification.
7. **Evidence status and links.** Preserve the ASR six-candidate diagnostic as diagnostic, with no ASR rerun planned. Preserve RQ1 and withdrawn 20/70-item TIB results as historical. Keep current status concise and link dated evidence instead of reproducing scores.

## Acceptance criteria

- A reader can identify the current state, next gate and permitted claim for RQ1–RQ4 from one table.
- No text implies TIB EDA, VISTA full media review, RQ2 evaluation, RQ3 evaluation or RQ4 Pareto analysis has completed.
- No text describes abstract overlap as factuality or inspected creator `test` as unseen.
- Task candidates and metrics have one active owner in `docs/BENCHMARK.md`; older matrix and decisions are visibly historical.
- Existing dataset, notebook and result links resolve; current status is checked against live receipts before any future master edit.

## Risks and next step

The biggest risk is turning a strategic map back into a detailed run plan. Limit edits to a short status table, evidence ladder and links. Before changing the master, verify the live EDA and result status again; it can change after this report.

Next step, if requested: edit `00-master-plan.md` to this design, then review its claims and links against `docs/BENCHMARK.md`, `docs/DATASET_EDA.md` and the RQ2 plan. No experiments or code changes are implied.

## Unresolved questions

None for the master’s role. The cohort, generator and reconciled automatic outcome for RQ2 remain research gates, not documentation decisions.
