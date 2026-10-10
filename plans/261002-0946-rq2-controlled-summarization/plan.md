# RQ2 — TIB S1/S3 benchmark preparation

## Active execution decision — 2026-10-10

**Run the development technical pilot first; do not launch the 8,769-record benchmark yet.** Use [rq2-tib-technical-pilot-colab.ipynb](../../experiments/notebooks/rq2-tib-technical-pilot-colab.ipynb) on Colab GPU, fresh root `MyDrive/RQ2_TIB_PILOT_20261010`. Nine train IDs are selected by min/middle/max source-length ranks within three numeric strata, without comparative scores. CPU tokenization is complete; GPU generation and semantic evaluation are **not executed**. [Technical audit and handoff](../reports/rq2-pilot-261010-1632-technical-design-report.md).

Actual S3 predicts at most five spaced boundaries using adjacent-window lexical Jaccard novelty, forms boundary-constrained chunks, then flattens them into the same map/reduce prompts as S1. There is no separate hierarchy-aware synthesis layer to ablate. S1/S3 answers a pipeline comparison; it cannot isolate boundary placement from chunk-count/length changes. A matched-count boundary-placement control would be a separately designed extension requiring its own timing. Oracle chapters and creator abstracts never enter structure prediction/generation.

Pilot profile: existing pinned Qwen2.5-1.5B checkpoint/tokenizer, greedy seed 42, 512-token source chunks, map batch 2, common map-output allocation `96 * max(n_S1,n_S3)` distributed by exact divmod, final cap 384, shared permissive cumulative prompt cap. These are **equal allocated output caps**, not equal actual total tokens or padded compute. Structure uses zero LLM tokens; CPU/tokenization cost is included in S3 segmentation. Actual input/output tokens are logged; unknown failed usage stays null. No automatic retry. Empty output fails the arm. Two-hour generation deadline is a soft stop between dispatches, not a hard per-call timeout. CUDA failure stops further GPU dispatches. S1/S3 order alternates across selected IDs.

Freeze remains pending: measured receipts → size/extension decision within 12 hours → source-dependence review → locked evaluation IDs/protocol. All 8,769 candidates and 900 flagged candidates remain in the preparation pool. No hard/long/failed ID is removed by outcome. Development pilot IDs cannot become confirmatory evaluation IDs. Creator valid/test references were already inspected: future evaluation is a declared exposed-reference cohort, never an unseen test.

Primary metric: `unicode_word_lcs_rouge_l_f1_v1`, Unicode `\b\w+\b` tokens, casefold, no stemming, word LCS, `2*LCS/(reference_words+hypothesis_words)`, macro across records. Future reporting uses paired per-record S3−S1 on the successful intersection, alongside all selected IDs and per-arm success/failure coverage. Do not impute failed quality as zero. Secondary BERTScore and source SBERTScore stay separate. Pilot quality does not select IDs/configurations by S3 wins.

Before formal uncertainty, freeze a dependence-group ledger using verified source/DOI/content links and conservative components of reviewed overlap relations. Shared authors/titles alone are review cues, not automatic exclusions. The existing three-record high-overlap cluster and series cues require explicit treatment. Bootstrap paired differences at the frozen video/dependence-group unit (5,000 resamples, seed 20261009), never chunks. If trustworthy grouping remains unavailable, report finite-cohort descriptive differences without population-superiority CI. Legacy item bootstrap is not an approved substitute.

Forecast includes initialization/download/load, both arms in each length stratum, shared preparation, all three scorers and checkpoints, with an explicit 30% planning margin. Min/middle/max length probes are nonprobability cost scenarios, not unbiased throughput estimates or confidence intervals. Failures, resumed/mixed profiles, unmeasured scoring or out-of-range lengths block credible forecasts. Extra configurations/repetitions require added measured cost. Code never freezes a cohort automatically.

## Historical preparation decision — 2026-10-09 (execution instruction superseded above)

Prepare the complete **8,769-record TIB pool** across all creator splits, genres, subjects and durations. No 70-item cap and no manual-review gate. The endpoint is paired **ROUGE-L F1 against creator abstracts**.

The [executed EDA](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) has 10 successful code cells: 9,103 source records, 9,002 structurally usable transcripts, eight empty abstracts and 225 reused-abstract records excluded. All 900 flagged candidates remain included.

## Integrated benchmark notebook

Open [rq2-tib-benchmark-colab.ipynb](../../experiments/notebooks/rq2-tib-benchmark-colab.ipynb), choose GPU, and Run all. The benchmark calls `load_or_prepare_data` itself before generation: cache present means reload; cache absent means load all pinned splits, process and select the complete pool, then save it. No separate preparation notebook run is required. One workflow handles preprocessing, S1/S3 generation, ROUGE-L, BERTScore, source-based SBERTScore, saved predictions and resume.

Preparation is integrated in this notebook; a separate preparation notebook is not required.

The execution cells are separate: run/log setup → generation S1/S3 and ROUGE-L → generation coverage → release generator/load evaluator encoders → BERTScore/SBERTScore evaluation → aggregation/bootstrap → metric, strata, item and cost reports. `run_benchmark(phase="generate", summarize=False)` saves predictions without semantic scoring; `phase="evaluate"` consumes saved checkpoints using only generator/tokenizer identities and never invokes generation. `summarize_benchmark` aggregates without encoders. The default `phase="all"` API remains available.

Detailed callbacks report segmentation, per-arm map/reduce calls, model loading, per-arm metric scores, long sentence windows and source embedding batches. Each execution cell has its own live display retaining the latest 60 events; record-level generation/evaluation statuses are printed separately every 25 records. Logging does not change cache identities. Existing Drive checkpoints resume; do not run old and updated sessions concurrently against the same output directory.

- Dataset: `gigant/tib@e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`.
- Unit: `(split, source_index)`; retain DOI as metadata.
- Source: complete ordered segment text with original timestamps; trim segment edges, join with one space, no truncation.
- Reference: trimmed creator abstract; exclude empty or reused casefold/whitespace-normalized abstracts.
- Selection: all eligible IDs, automatically and deterministically.
- Tokenizer/checkpoint setting: existing `Qwen/Qwen2.5-1.5B-Instruct@989aa7980e4cf806f80c7fef2b1adb7bc71aa306` from the project runner.
- Output: `MyDrive/RQ2_TIB_BENCHMARK/tib-benchmark-data.jsonl.gz` containing records, metadata, exclusions, configuration and checksums; no separate receipt.

## Benchmark entry point

```python
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig, run_benchmark

benchmark = run_benchmark(
    backend,  # shared pinned generator and exact tokenizer
    data_path="tib-benchmark-data.jsonl.gz",
    output_dir="rq2-tib-results",
    config=BenchmarkConfig(),
)
```

This call runs preprocessing automatically when the cache is absent. The backend receives source-only adapters; scoring receives creator abstracts separately. Completed arm/item predictions are saved atomically and reused after interruption. Failed attempts and known token usage stay in the output history.

## Paired comparison settings

Use the same generator/tokenizer, source, decoding settings and per-talk cumulative prompt/output budgets for S1 and S3. S1 uses fixed chunks; S3 uses source-only predicted hierarchy. Defaults use 512-token chunks, 384 final-output tokens, greedy decoding and seed 42. The common total map-output budget is 96 times the larger chunk count and is distributed across each arm's chunks. Both arms share one cumulative prompt cap; actual usage and imbalance are measured. The execution runner must account for actual prompt/output usage across calls and retries; preparing data alone does not measure usage.

ROUGE-L F1 against creator abstracts remains primary. Secondary metrics are BERTScore F1 against abstracts and source-based SBERTScore (mean over summary sentences of maximum cosine against all transcript sentences). Report each metric separately with its scored/unscored denominator, paired S3 minus S1 and percentile bootstrap intervals (5,000 resamples, seed 20261009), plus split/genre/subject/duration strata. These are descriptive secondary analyses, not multiple independent winner tests. Do not threshold SBERTScore into factuality percentages.

Semantic encoders are immutable pinned multilingual checkpoints: XLM-R large layer 17 (BERTScore, no IDF/baseline rescaling) and multilingual MPNet sentence encoder (SBERTScore). Package versions, revisions, sentence splitter and long-input policies are stored with each score. BERTScore uses the official library within encoder capacity; overlength abstracts/summaries use an explicitly identified token-window extension with global token alignment. Long source sentences use token-weighted embeddings over all context windows; every source sentence is processed in bounded batches. This is a multilingual adaptation, not an exact replication of Ye et al.'s checkpoint setup.

Generation and evaluation identities are separate. Updating the evaluator scores existing saved summaries without regeneration; metric failures retain predictions and retry independently. The generation cache directory is unchanged. The notebook evaluates on CUDA when available after releasing the generator; the library default remains CPU. Evaluator weights stay outside generation GPU measurements.

Report per-arm segmentation seconds (S3 includes boundary prediction), synchronized generation seconds, wall seconds, generation-call count, actual prompt/output tokens, and absolute peak GPU allocated/reserved bytes when available. Summaries include failed attempts and exclude reused receipts to avoid double counting. Missing legacy timing stays unknown. Shared preprocessing and evaluation time are reported separately. Keep failed generation IDs in the comparison denominator. The current study measures creator-abstract agreement; all creator splits have been inspected in EDA.

## Delivery state

- [x] Full-source EDA executed and saved.
- [x] Reusable preparation and compressed dataset save/reload code implemented.
- [x] Integrated benchmark entry point automatically calls preprocessing, generation and scoring.
- [x] Three metrics, per-metric paired bootstrap, per-arm costs and independent evaluation resume implemented.
- [ ] Execute the full paired benchmark notebook on Colab.

Historical [20-item audit](../reports/rq2-valid-dataset-audit-261002-report.md), [70-item screen](../reports/tib-cohort-review-261009-0923-benchmark-readiness-report.md) and [broad-pool inspection](../reports/tib-diverse-pool-261009-0943-benchmark-scope-report.md) remain records of earlier work. Their manual qualification requirements do not gate the current automatic study.

## Execution optimization (2026-10-09)

Map generation supports consecutive equal-cap batches (notebook default 8), with unchanged chunk order and exact output allocation. Batched prefix token counting preserves legacy first-overflow chunk boundaries. Live notebook rendering is throttled to two seconds; failures render immediately. Arm receipts record batch size and actual model dispatches separately from logical prompt calls. Completed serial predictions resume unchanged; the notebook displays their execution profile alongside new batch predictions. FP16 batch decoding can produce numerical differences; aggregate costs include all recorded profiles and are not a uniform-throughput experiment. Reduce MAP_BATCH_SIZE to 4 or 2 for smaller GPUs. No GPU speedup has been measured locally; validation uses offline focused tests.
