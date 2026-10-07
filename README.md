# Benchmark research workspace

This repository contains experiment runners, Colab notebooks, frozen contracts, and evaluation evidence for the multimodal lecture summarizer. The application code is in the sibling `multimodal-lecture-summarizer/` directory.

Start with the [documentation index](docs/README.md), [benchmark protocol](docs/BENCHMARK.md), and [dataset EDA guide](docs/DATASET_EDA.md). The [on-demand notebook manifest](experiments/notebooks/notebook_manifest.yaml) is currently empty; add a notebook only for a concrete run. ASR tasks `01a` and `01b` were retired from active execution; their historical results remain available.

## Current research sequence

1. For each video-processing task, select datasets with existing labels for that task, confirm usable inputs and rights, then choose representatives from different model or algorithm families. General-video datasets are not benchmark fallbacks. For creator TIB summarization, inspect every record in the pinned `train`, `valid`, and `test` splits regardless of `genre`; treat genre as a reported stratum, not an exclusion rule. Record the same task-specific metrics and comparison conditions before evaluation.
2. Create and run an EDA notebook **when that dataset and task are ready to use**. Analyze every selected unit within the declared scope, report missing and excluded units, inspect relevant media/labels and leakage, and record any cleaning or cohort changes. A sampled inspection must be labeled as a sample.
3. Once the dataset and comparison are fixed, create and run the task's evaluation notebook on the same units, metrics and resource profile for all candidates. Preserve per-unit outputs, failures and run receipts; report `no_selection` when evidence is insufficient.

Do not create placeholder notebooks or a separate smoke-notebook workflow. Existing diagnostic results remain historical evidence, not proof that a future dataset or task passed these steps.

The new [TIB all-split EDA notebook](experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) targets all **9,103 expected records across train/valid/test without a genre filter**; actual per-split counts and usable inputs must be verified when it runs on Colab. The earlier [TIB validation notebook](experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) retains the executed 20-item diagnostic, and the completed Qwen run covers 70 structurally eligible Lecture validation records only. The new all-split EDA will inspect test content, so the creator's `test` split can no longer be described as an unseen holdout afterward. VISTA's saved media outputs cover 40/1,859 validation records; its unexecuted extension targets all 1,859. Run the new EDA and review per-item receipts before treating either gate as complete. The obsolete RQ2 20-item Qwen v2 and three-item chat-pilot notebook files and their generators were removed on 2026-10-07; historical audit reports and local ZIP exports retain those findings.

The remaining ASR notebook, [`01c`](experiments/notebooks/asr_architecture_colab_t4.ipynb), completed all six pinned architecture candidates on 507 TED-LIUM validation units and 1,155 native-test units. Qwen3-ASR 0.6B ranked first by validation WER (3.91%). Native-test results are diagnostic, and this research result does not change the application's Faster-Whisper `base.en` default. See the [ASR evaluation report](docs/results/asr-architecture-evaluation-2026-10-05.md) for results and limitations.

## Research workspace

The `benchmarks/`, `experiments/`, `tests/`, `plans/`, `reports/`, and `docs/` directories contain the research code, notebooks, protocols, and evaluation evidence moved from the application repository. Existing `audio/` and `visual/` examples remain here. Executed historical notebooks and run receipts are retained in `experiments/notebook_history_20260926.zip` with its manifest; archived smoke notebooks have been removed.

`benchmarks/references/` has no validated local ground truth. Repeated `TBD` and mock reference files were removed on 2026-10-07; current task-specific annotation requirements remain documented in `docs/BENCHMARK.md`. The generic reference schema and dataset-contract modules were retired with the old evaluation-table workflow.

`docs/visuals/benchmark-directory-tree.drawio` was regenerated from the current tree on 2026-10-07; rerun `scripts/generate_benchmark_directory_tree_drawio.py` after later layout changes.

Run outputs are present on this machine but ignored by Git. Downloaded dataset payloads and local caches were removed on 2026-10-07:

- `experiments/datasets/`: source provenance and RQ1 qualification evidence remain; TED-LIUM, IIIT-CVid, EduViQA, and SlideVQA payloads were removed.
- `experiments/outputs/`, `outputs/`, and `checkpoints/`: experiment results and model checkpoints. The local ASR architecture input ZIP was removed; its SHA-256 receipt remains.
- `cache/`: removed; model and feature caches must be rebuilt if needed.
- The completed ASR run export `external-results/runs-20261005T055449Z-1-001.zip` (SHA-256 `8f6e359f947097cb85b67b59024b2e58a7872a86fbcacb8a0a6180310270b1cf`) is documented in the evaluation report but was not present locally on 2026-10-07. A separate, incomplete 2026-10-04 ZIP was reduced to a [partial-run audit record](reports/asr-architecture-partial-validation-2026-10-04.json); its 2,656 checkpoints were not imported.

RQ1 qualification media, source archives, input bundle, and local model caches were removed on 2026-10-07. Local smoke output trees were also removed; executed RQ1 notebooks and non-smoke results remain.

Run benchmark commands from this repository root. Some experiments import `ai_workers` from the sibling application repository. In this workspace, set `PYTHONPATH` to both repositories before running those experiments:

```powershell
$env:PYTHONPATH = "$(Resolve-Path .);$(Resolve-Path ../multimodal-lecture-summarizer)"
python -m pytest tests/test_asr_architecture_colab_run.py
```

The ASR architecture notebook is `experiments/notebooks/asr_architecture_colab_t4.ipynb`. It expects `asr_architecture_colab_t4_inputs_empty_transcript_261005_clean.zip` and its SHA-256 file in the configured Drive folder; the ZIP is no longer stored locally. See `docs/results/asr-architecture-evaluation-2026-10-05.md` for the evaluation interpretation. Original run receipts in `experiments/outputs/` are kept unchanged; moving files does not make a diagnostic result an official benchmark.
