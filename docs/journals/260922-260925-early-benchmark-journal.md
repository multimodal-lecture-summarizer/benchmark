# Nhật ký benchmark giai đoạn đầu, 2026-09-22 đến 2026-09-25

Tập hợp nguyên văn năm nhật ký đầu kỳ. Ba nhật ký được manifest đóng băng dẫn chiếu vẫn giữ tệp riêng.

## Nguồn

- 260922-2041-phase-1-priority-execution.md — SHA-256 dd9b6cc2e462366ae88de45c09209049324254901c06f7dcfc9682da5c11dc16
- 260922-2127-phase-1-evidence-integrity-hardening.md — SHA-256 5d8151537df07d46449c638d416b68bd5b958e4e5a7072d9a6a902877d1a0e74
- 260923-1209-d2-contract-ablation-false-green.md — SHA-256 965bf6fad046a64b1c6614a61cf83b93b404beea58d7b99e0c5c34549aee4ff1
- 260923-1350-00c-characterization-contract-false-greens.md — SHA-256 42d5b4a933e45262830932305343f7a49482aea08694772333ab7a6f48e8eccc
- 260925-2057-vista-encoding-phase1-closeout.md — SHA-256 57d3aa81bba664adaac6610a302aba586f35e571fefdaf6af7c3c4b4b37a921b

---

## Nguồn: 260922-2041-phase-1-priority-execution.md

# Phase 1 Priority Path Became Executable, Not Complete

**Date**: 2026-09-22 20:41
**Severity**: High
**Component**: Scientific benchmark executor and dataset qualification
**Status**: Ongoing

## What Happened

We repaired the Phase 1 priority path: the executor now works both as `python -m benchmarks.scripts.execute_all_notebooks` and as `python benchmarks/scripts/execute_all_notebooks.py`. We added provenance-linked, atomic artifact writes and implemented real local smoke runners for `00a`, `00b`, and `00c`. Live execution of group `00` completed, while 56 focused tests passed.

## The Brutal Truth

This is relief, not victory. Before this work, our “official” pipeline depended on an invocation mode and artifact trust model that could break outside the happy path. Worse, it was tempting to promote readable local files into scientific eligibility. That would have produced clean-looking benchmark output with no defensible ground truth. The frustrating part is that 56 green tests can still hide system-level gaps if we pretend they prove the whole DAG.

## Technical Details

Direct execution previously failed because only `benchmarks/scripts` was on `sys.path`, causing `ModuleNotFoundError: experiments`. `execute_all_notebooks.py` now inserts the project root before importing registry contracts. Artifact receipts are checked against the producer run manifest for `run_id`, `status`, and SHA-256 provenance fields. The real smoke profile found local files, but `00c` deliberately emitted `freeze_status: not_eligible` with empty `unit_ids`; downstream `01a` is blocked with `dataset.frozen_manifest: no scientifically eligible frozen units`.

## What We Tried

- Kept module-only execution: rejected because documented direct-path usage remained broken.
- Treated smoke-readable data as frozen evaluation data: rejected because readability does not establish rights, task ground truth, or media decode validity.
- Reused non-atomic writes: rejected because interrupted or concurrent runs could expose partial evidence.

## Root Cause Analysis

We designed contracts before closing execution and provenance boundaries. Invocation assumptions, file existence, and scientific eligibility were conflated. The pipeline could validate shape while missing meaning.

## Lessons Learned

An artifact is trustworthy only when payload, receipt, producer manifest, hashes, namespace, and scientific eligibility agree. Smoke profiling is evidence of operability, not benchmark fitness. Green unit tests must be paired with a live DAG slice.

## Next Steps

- Benchmark owner: remove notebook-generator drift and prove generated sources match manifest contracts before Phase 1 closure.
- Executor owner: add concurrency tests for atomic publication and namespace isolation this iteration.
- Validation owner: run the repository-wide scan and full relevant suite, then update plan checkboxes only from recorded evidence.

Unresolved: no dataset is yet scientifically eligible for `01a`; full DAG remains blocked.

---

## Nguồn: 260922-2127-phase-1-evidence-integrity-hardening.md

# Phase 1 evidence integrity hardening

The difficult part of this slice was not adding another empty-list check. Generic JSON validation repeatedly accepted metadata as science: sample counts, frame indices, timestamps, and status strings could masquerade as metrics or predictions. The final approach uses declared metric names from the registry, typed finite values, explicit prediction semantics, and recursive fallback detection. This is intentionally conservative for official evidence.

Resume integrity had the same boundary problem. Hashing only the direct runner missed shared metric and worker modules. The code-state digest now includes Python sources across the three execution packages, trading broader invalidation for correct stale-result prevention.

Verification stayed evidence-scoped: 66 targeted tests, generator drift check, independent adversarial review, a real local 00a-to-00c smoke chain, then an all-skip resume. Group 02 and group 07 remain unexecuted because their runner modules do not exist; the dry plan proving their order is not benchmark readiness.

---

## Nguồn: 260923-1209-d2-contract-ablation-false-green.md

# D2 and Ablation Stopped Lying Green

**Date**: 2026-09-23 12:09
**Severity**: High
**Component**: Dataset D2 contract and ablation execution
**Status**: Ongoing

## What Happened

We first scoped and committed the completed Phase 1 slice as `6a729515` after 27 tests passed. Then we hardened the D2 dataset bundle contract and removed mock execution from the ablation runner. `RQ0_OD` now has the only real adapter; every unsupported task fails closed instead of manufacturing plausible rows. Final verification recorded 57 focused tests and 78 broader tests passing, followed by review approval.

## The Brutal Truth

The runner was capable of looking successful while proving almost nothing. Stale output could be consumed, incomplete provenance could pass as a real run, and structurally loose D2 records could hide split leakage or invented eligibility. That is maddening: green output here is worse than a crash because it can enter a thesis as fake evidence. The relief is that the code now refuses ambiguity, but we still have infrastructure evidence, not scientific results.

## Technical Details

`experiments/evaluation/dataset_contracts.py` now enforces schema-required keys, rejects extras and invalid types, checks validation/final-test separation, requires leakage identities or an explicit exception, resolves frozen unit IDs, and cross-checks eligibility. Concrete failures include `missing schema fields` and `leakage identity`.

`experiments/scripts/ablation_runner.py` deletes stale output before subprocess execution, binds results to `run_id` and `config_hash`, requires complete provenance, validates metric ranges, and rejects missing registry bases with `base candidate ... not found in registry`. Real `RQ0_OD` output must contain `map50`, `precision`, and `recall`; diagnostic evidence cannot be promoted to real.

## What We Tried

- Generic shape validation: rejected because valid-looking JSON still admitted wrong types, missing bases, and split leakage.
- Mock ablation metrics: removed because deterministic fake numbers created false confidence.
- Reusing an existing result file: rejected because it could belong to an earlier config or failed attempt.
- Enabling all RQs: rejected because no real adapters exist beyond `RQ0_OD`.

## Root Cause Analysis

We optimized for runnable orchestration before defining evidence identity. Schema shape, dataset provenance, split independence, and output freshness were treated as secondary checks. That was the fundamental mistake.

## Lessons Learned

Fail closed at every scientific boundary. A passing runner is not a benchmark result; provenance, ground truth, split integrity, and fresh execution must agree before evidence is real.

## Next Steps

- Dataset owner, next Phase 1 iteration: perform real D2 acquisition and produce eligible, traceable frozen units.
- Benchmark owner, next implementation slice: add manifest wrappers and real adapters for remaining tasks.
- Evaluation owner, before reporting metrics: replace OD diagnostic evidence with a ground-truth-backed run and rerun focused plus broader suites.

Unresolved: no real D2 acquisition, OD remains diagnostic, and manifest wrappers are still missing.

---

## Nguồn: 260923-1350-00c-characterization-contract-false-greens.md

# 00c Characterization Contract False Greens

**Date**: 2026-09-23 13:50  
**Severity**: High  
**Component**: Dataset characterization contract and `00c` runner  
**Status**: Resolved for contract infrastructure; D2 execution remains pending

## What Happened

The first `00c` characterization validator looked strict but still accepted corrupted evidence. Adversarial mutations exposed false greens in numeric summaries, source hashes, duplicate figure IDs, schema-root coverage, semantic figure bindings, leakage reporting, and non-finite values. A passing schema check was nowhere near enough.

## The Brutal Truth

This was maddening because the validator could congratulate us while the evidence contradicted itself. We had built a compliance-shaped shell: fields existed, hashes looked plausible, and tests passed, but important values were not recomputed from source records. That is exactly how fabricated benchmark evidence slips through while everyone feels safe.

## Technical Details

Concrete failures included accepting `file_size_bytes.mean = -999`, arbitrary or unreconciled `source_table_sha256`, duplicate `figure_id` values, incomplete root requirements, figures whose declared source artifact was not semantically bound, a hard-coded leakage summary, and `NaN`/`Infinity` values that JSON tooling can silently tolerate.

The fix made `validate_dataset_characterization_bundle` recompute numeric summaries and duplicate-checksum groups from units, bind statistics/comparison/figures through canonical SHA-256 hashes, reject duplicate or unknown figure identities, validate semantic figure source contracts, derive leakage counts instead of trusting literals, and reject non-finite numbers. The schema and runner now carry acquisition revision, contract scope, denominators, and artifact hashes consistently.

Latest evidence: **107/107 tests passed**. A real local `00a -> 00b -> 00c` smoke also completed successfully, with every frozen record still marked `not_eligible`.

## What We Tried

We initially relied on JSON Schema plus presence checks. Rejected: this cannot prove cross-artifact consistency. We also rejected weakening checks for smoke convenience; smoke and D2 share the semantic validator, while eligibility remains fail-closed.

## Root Cause Analysis

We validated document shape instead of evidence meaning. Tests mirrored happy-path fixtures and did not mutate derived values independently, so circularly consistent lies passed.

## Lessons Learned

Every derived metric must be recomputed from the lowest-level frozen source. Every artifact link needs a verified digest and semantic identity. Mutation tests are mandatory for scientific evidence gates.

## Next Steps

- Benchmark owner: run real D2 acquisition and characterization only after rights, provenance, and revision gates pass.
- Test owner: retain adversarial mutations for numeric, hash, figure, leakage, and non-finite fields in every future contract change.
- Do not call Phase 2 or D2 complete until real eligible datasets, full artifact layout, and measured outputs exist.

## Unresolved Questions

- Which real D2 dataset will clear rights and provenance first?
- When will CSV/Parquet layout and universal figure generation be executed against eligible data rather than smoke fixtures?

---

## Nguồn: 260925-2057-vista-encoding-phase1-closeout.md

---
title: "VISTA Encoding — Phase 1 closeout + contract_validator schema migration"
date: "2026-09-25"
session_id: "mvs_2fc401cf91724fe18bdcb70afd588e11"
plan: "plans/260925-1537-dataset-coverage-expansion"
phase: 1
status: completed
---

# Phase 1 Closeout — VISTA Encoding (2026-09-25)

## TL;DR

Closed criterion #2 (VISTA feasibility encoding) via Path B: dropped flat `large_dataset_policy.vista_full_local_status` key, replaced with nested `vista_full:` block in both `research_decisions.yaml` and `contract_validator.py`. 51/51 tests pass; `validate_contracts() == []`.

## What landed

- `experiments/registry/research_decisions.yaml` — `large_dataset_policy` rewritten with nested `vista_full:` schema: `dataset_id`, `hf_dataset`, `access_status=unavailable`, `acquisition_level=D0`, `fallback_dataset=null`, `reason` (1.93 TB / 109.6 GB budget overflow), `evidence` (probe_output path + decision_date + adjudicated_by), `allowed_alternatives` (3 entries), `re_adjudication_required_if` (2 triggers). Inline comment links to plan.
- `experiments/registry/contract_validator.py` — `expected_sections["large_dataset_policy"]` rewritten to match the new schema exactly (exact-match dict comparison enforced). Inline comment references plan + schema-migration rationale.
- `plans/260925-1537-dataset-coverage-expansion/plan.md` — Acceptance Gate updated; Phase 1 row marked Completed; VISTA entry checkbox marked `[x]` with closeout note.
- `plans/260925-1537-dataset-coverage-expansion/phase-01-vista-encoding.md` — Implementation Steps annotated with `Critical dependency discovered during implementation` block; `Related Code Files` now lists `contract_validator.py` as Modified (was Read-only); Success Criteria checkboxes all `[x]`.

## Critical dependency discovered mid-implementation

Plan v1 said "Patch `research_decisions.yaml` only; grep 0-hit cho `vista_full_local_status`". Grep found 3 callers — including `contract_validator.py` line 145-148 which enforces **exact-match** dict comparison of the entire `large_dataset_policy` block, and is itself part of `_code_state_sha256` in `execute_all_notebooks.py`. Tests in `test_research_contracts.py::test_default_contracts_are_valid` require `validate_contracts() == []`.

→ Stopped implementation per HARD-GATE-NO-SIDE-EFFECTS, surfaced two options (Path A: preserve old key, add sidecar; Path B: replace schema + update validator + tests still pass). User chose Path B. Result: 51/51 tests pass, no silent regression.

Lesson: when adding new keys to a frozen contract, grep before writing — `expected_sections` in `contract_validator.py` is a hidden exact-match gate.

## Verification (verifier subagent, 6/6 PASS)

1. YAML parse + structure — 10/10 boolean assertions on nested `vista_full` keys returned true.
2. `pytest tests/test_research_contracts.py` — 51 passed in 0.79s.
3. `validate_contracts()` — returned `[]`.
4. Grep regression — `vista_full_local_status` hit count: `experiments/`=0, `tests/`=0, `benchmarks/`=0; only remaining hits in `phase-01-vista-encoding.md` (plan doc, expected historical record).
5. Evidence file `plans/260830-1917-scientific-benchmark/probes/output/vista_summary.json` exists (3,197 bytes).
6. Git diff scope — `contract_validator.py` change is single hunk at lines 143–164; `research_decisions.yaml` change is single hunk at lines 65–90. No collateral edits.

## Why this matters for the broader plan

- **Phase 2 (IIIT-CVID D2 freeze)** can proceed now: `large_dataset_policy` schema migration didn't touch `phase2_dataset_execution` block, which Phase 2 also modifies. Two non-overlapping YAML sections — parallel-safe (if sequenced carefully on the same file).
- **Phase 4 (EduViQA D2 freeze)** will inherit the same exact-match contract enforcement pattern — any new `phase2_dataset_execution` keys must update `contract_validator.py` simultaneously. Lesson carries forward.
- **`execute_all_notebooks.py:345` SHA-256 hash** for `contract_validator.py` will change on next benchmark run because of the schema migration. This is **expected delta**, not a regression — recorded here so future runs comparing manifest SHAs don't false-alarm.

## Open questions

None for Phase 1. Phase 2 (next) has same exact-match gate risk; will grep `iiit_cvid_d2` patterns before drafting YAML.

## Files touched

```
M  experiments/registry/research_decisions.yaml        (+18 -3)
M  experiments/registry/contract_validator.py           (+20 -3)
M  plans/260925-1537-dataset-coverage-expansion/plan.md (+3 -1)
M  plans/260925-1537-dataset-coverage-expansion/phase-01-vista-encoding.md (+12 -3)
```

(Approximate line counts; git status not yet committed.)
