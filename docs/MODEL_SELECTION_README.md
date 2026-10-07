# Model selection and evidence status

Select candidates only after choosing a lecture-domain dataset with the right existing labels and running its [EDA](DATASET_EDA.md). Freeze the cohort, primary metric, scoring rules and shared compute conditions before the [evaluation notebook](BENCHMARK.md) runs. A model registry entry or runner file is a proposal, not a measured result.

## Existing result: ASR diagnostic

The [ASR Colab notebook](../experiments/notebooks/asr_architecture_colab_t4.ipynb) compared six candidates on 507 TED-LIUM validation units and 1,155 native-test units. Qwen3-ASR 0.6B ranked first on validation WER (3.91%). Native-test values are diagnostic because the test split had prior exposure; the comparison does not isolate model architecture from training data, checkpoint or toolchain differences. See the [evaluation report](results/asr-architecture-evaluation-2026-10-05.md) before citing a number. No ASR rerun is planned, and the application model default has not changed.

## Remaining video tasks

The [task matrix](BENCHMARK.md#task-matrix) lists candidate datasets, model families and metrics. It is provisional: missing media, unsuitable ground truth or unexecuted full-cohort EDA leave a task `not_eligible`. If candidates have not run on the same eligible units, report `no_selection`.

The previous RQ1 chaptering and 20-/70-item RQ2 outcomes were withdrawn for reanalysis. TIB all-split EDA and VISTA full-validation inspection still require execution and review; neither establishes a summarization winner. Preserve per-item outputs, failures and receipts for any new comparison.