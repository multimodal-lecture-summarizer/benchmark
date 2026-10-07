# Benchmark research workspace

This repository holds lecture-video research code, Colab notebooks and evidence. The application is in the sibling `multimodal-lecture-summarizer/` repository. Start with the [documentation index](docs/README.md), [benchmark protocol](docs/BENCHMARK.md) and [EDA guide](docs/DATASET_EDA.md).

## Current workflow

1. For each video task, identify a lecture-domain dataset with existing labels that match its target. Verify source, rights, media and annotation provenance. Select candidate model or algorithm families and a common metric.
2. Create an EDA notebook when the dataset is ready. Account for every selected record, inspect relevant inputs and labels, report missingness, duplication, leakage and any sampling limits, then decide whether to keep, repair, restrict or reject the cohort.
3. Create an evaluation notebook after fixing the cohort and protocol. Compare candidates on the same units, ground truth, metrics and resource profile. Save item-level predictions, failures and run receipts. Report `no_selection` when evidence is insufficient.

General-video datasets are not substitutes for missing lecture labels. Create notebooks only for a concrete EDA or evaluation run; there is no placeholder or smoke-notebook workflow. The [notebook manifest](experiments/notebooks/notebook_manifest.yaml) is currently `on_demand` and empty. [The master plan](plans/260901-unified-scientific-benchmark/framework/00-master-plan.md) states the research questions; [the RQ2 plan](plans/261002-0946-rq2-controlled-summarization/plan.md) records the summarization protocol.

## Current evidence

- [ASR architecture notebook](experiments/notebooks/asr_architecture_colab_t4.ipynb) and [report](docs/results/asr-architecture-evaluation-2026-10-05.md): a completed six-candidate diagnostic comparison. Native-test outcomes are diagnostic, and no ASR rerun is planned. This result does not change the application's model default.
- RQ1 chaptering will not be rerun. Its notebook code is retained, but saved chaptering results were withdrawn for reanalysis.
- TIB summarization: [all-split EDA notebook](experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) targets `train`, `valid` and `test` without a genre filter. It is not an executed full-cohort result. Earlier 20- and 70-record work is historical; saved comparison results were withdrawn. Reading the creator `test` references during EDA removes its unseen-holdout status for later claims.
- VISTA: [validation media EDA notebook](experiments/notebooks/diagnostics/vista-validation-media-eda-colab.ipynb) has partial executed evidence; full-validation inspection is still pending. No chaptering or summarization winner is established by these notebooks.

Downloaded datasets and most caches were removed locally. Colab runs must acquire their declared inputs from their documented source or Drive. `experiments/outputs/` contains ignored local evidence and may be incomplete; consult each report and receipt before citing a result. `benchmarks/references/` does not contain validated ground truth. The benchmark protocol lists the annotation requirements for each task.

Some retained historical notebooks depend on code or data that was removed during cleanup. They are records, not a current run sequence. Task-specific runners under `benchmarks/scripts/` are implementation helpers; their presence does not establish that an evaluation was completed.
