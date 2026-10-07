# Benchmark documentation

## Current guidance

| Document | Purpose |
|---|---|
| [Benchmark protocol](BENCHMARK.md) | Task eligibility, candidate comparison, metrics and reporting. |
| [Dataset EDA](DATASET_EDA.md) | What to inspect before using a cohort, and what has actually been inspected. |
| [Model selection](MODEL_SELECTION_README.md) | Separate completed evidence from proposed candidates. |
| [Master plan](../plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) | Research questions and open hypotheses. |
| [RQ2 plan](../plans/261002-0946-rq2-controlled-summarization/plan.md) | Summarization-specific cohort and comparison decisions. |

The sequence is dataset and candidate selection → executed EDA notebook → evaluation notebook on the same task units and metric. Only lecture-domain datasets with suitable existing labels enter the benchmark. Notebooks are created when needed; the [active manifest](../experiments/notebooks/notebook_manifest.yaml) is currently empty.

## Retained results

[The ASR architecture report](results/asr-architecture-evaluation-2026-10-05.md) documents the completed six-candidate diagnostic run and its limitations; [transcript recovery notes](results/asr-architecture-empty-transcript-recovery-2026-10-05.md) record a run-specific repair. RQ1 and ASR are not planned for rerun. Saved chaptering and summarization outcomes were withdrawn pending new analysis; their notebook code may remain as historical material.

Other files under `docs/` are supporting or historical references, not an execution queue. Do not infer a completed benchmark from a plan, runner, registry entry or unexecuted notebook.

The older `docs/frozen_decisions.json` and `plans/260901-unified-scientific-benchmark/framework/decisions-log.md` record the original design, including RQ2 assumptions superseded by the no-human-scoring amendment and all-split TIB EDA scope. They are not the current RQ2 protocol. The [cleanup record](cleanup-record-2026-10-07.md) summarizes the reviewed deletions and the evidence retained.
