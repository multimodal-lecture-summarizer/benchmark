# Phase 1 Priority Implementation Status

## Status

| Scope | Complete | Total | Progress |
|---|---:|---:|---:|
| Phase 1 acceptance criteria | 4 | 12 | 33.3% |
| Full 7-phase plan criteria | 4 | 75 | 5.3% |

Plan remains `in-progress`. Phases 2–7 remain pending.

## Delivered

- Direct executor path and module invocation both resolve the nested project package.
- Added shared fail-closed artifact writer/reader with SHA-256, provenance, atomic writes and upstream run-manifest matching.
- Added real local runners for `00a_environment_preflight`, `00b_dataset_feasibility`, `00c_dataset_eda_and_freeze`.
- Official smoke group 00 passed on 4 local datasets and 52 bounded real files (1,277,503,333 bytes); network not used.
- Smoke profiling does not promote scientific evidence: all 4 frozen-scope records are `not_eligible`, have empty `unit_ids`, and downstream `01a` is rejected before model load.
- Absolute workstation paths removed from shareable payloads.

## Validation

- `56/56` targeted tests passed.
- Python syntax compilation passed for changed modules.
- 22/22 notebook files have expected stable cell IDs, multiline code cells and manifest-aligned task/runner metadata.
- 17 artifact receipts: `official/smoke/real`, valid payload hashes and positive record counts.
- 3 runner manifests plus 3 executed-notebook manifests generated.
- Standalone `00c` and group-00 `00c` produced identical scientific payload hash.
- Required-artifact validation rejects mixed provenance/run IDs and rejects a frozen manifest with zero eligible units.

## Still Open

- Generator `--check` reports content drift for all 22 notebook files; structure is valid but source-of-truth byte stability is not closed.
- Full DAG, groups 02/07 and runners 01–09 do not run yet.
- D2 rights/revision/GT/decode qualification, split freeze and leakage adjudication not completed.
- Concurrency lock/run-scoped promotion and global streaming inventory budget remain hardening work.
- Targeted coverage remains below the preferred 80% aggregate threshold.
- A transient Windows libzmq cleanup warning appeared once; run still exited 0 with validated artifacts.

## Ownership

Changed only:

- `benchmarks/scripts/execute_all_notebooks.py`
- `experiments/scripts/benchmark_artifacts.py`
- `experiments/scripts/dataset_profile_helpers.py`
- `experiments/scripts/environment_preflight.py`
- `experiments/scripts/probe_dataset_feasibility.py`
- `experiments/scripts/profile_dataset.py`
- `tests/test_phase1_priority_runners.py`
- Phase 1 checkbox file and this report.

Existing unrelated modified, deleted and untracked files were preserved.

## Unresolved Questions

- Exact D2 dataset revisions, rights and task-specific GT eligibility remain Phase 2 decisions.
- API quota/cost caps remain required only before API-backed benchmark runs.
