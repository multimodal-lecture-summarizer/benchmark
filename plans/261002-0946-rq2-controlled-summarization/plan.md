# RQ2 — TIB S1/S3 benchmark evidence and protocol

**TIB P4 returned-evidence audit:** [Verified Colab receipts and outputs](../../../plans/reports/evidence-audit-261019-2013-tib-p4-returned-capacity-report.md): BART/LED/Qwen3 fresh3/3 on Tesla T4 FP16;159 files/155 JSON digests and9 neural outputs verified offline, without inference rerun. Scoped capacity PASS; LED repetition and LED/Qwen intermediate256-token exhaustion require development review. Cap350 remains maximum/pending final-lock; pilot40 incomplete, selection300/final523 not run. Mounted-store readback verified; cross-session reuse, quotas/projection and formal-runtime scorer remain open. Full523 target and diagnostics40 inside final retained. Preparation18:02 and qualification17:03 statements below are historical; they do not supersede this audit.

## Current research plan — 2026-10-19

The user's [current five-stage plan](../../../plans/261019-0035-summarization-model-benchmark/plan.md) owns one future primary TIB text-only benchmark, without separate genre benchmarks or new gold summaries. Defaults are 40 validation pilot, 300 disjoint validation selection (availability fallback 200 before selection outputs), all eligible native test records up to 911 (resource fallback full-first 600→500→400), and 40 unique final diagnostic cases. EDA covers 9,103 records and qualification every native split. The four model families remain LexRank/BART/LED/Qwen3, with fixed CPU Lead-3 as a sanity control. Primary reference scoring retains eligible A+B, excludes evidence-backed unusable C, and reports reference-quality sensitivity. These are planning defaults, not selected counts or statistical guarantees. The historical 120-record results and no_selection remain unchanged; original/rescore receipt audit remains pending. No new S1/S3 study or execution is scheduled by this documentation update.

The primary study uses normalized transcript input with raw/hash lineage and segment sidecars, no default timestamps in prompts, and a global output cap derived from development data before selection. Four model-family representatives are selected in two validation steps; fixed Lead-3 joins the common comparison and paired reporting, with separate CPU/scorer costs. Scorer changes repeat both validation steps before final seal. Genre/subject/reference-quality analyses are sensitivity views on the same frozen predictions. The [P1 evidence update](../../../plans/reports/dataset-evidence-261019-1507-tib-snapshot-rights-report.md) verifies the pinned snapshot/checksums/schema and all9,103 rows. Reference field binding supports5,592 CC0 matches;6,503 source routes remain conditional. The [subsequent qualification execution](../../../plans/reports/implementation-261019-1703-tib-qualification-cohort-report.md) completed the scoped private-use policy, all9,103-record CPU EDA and reference/group audits. Source decisions are6,171 conditional/2,932 hold; joint source/reference/content eligibility is5,270. After historical exposure filtering, train/valid/test are4,213/464/523. Development40 pilot/300 selection are sealed without fallback; final test is unsealed and no generation occurred. A0/B9,095/C8 makes A-only sensitivity unavailable. Scorer-ready, runtime profiles, W_global, actual T4 capacity and compute/storage budgets remain gates; RTX4050 observations do not qualify T4. Historical120/no_selection and its independent Drive audit status are unchanged.

## Completed notebook evidence — 2026-10-13

The [original formal notebook](../../experiments/notebooks/rq2-tib-120-evaluation-colab.ipynb) generated all 240 S1/S3 summaries and all 120 paired ROUGE-L scores. Original semantic scoring stopped after 28 pairs on the retokenized-window capacity error at `valid/208`. The executed [semantic rescore notebook](../../experiments/notebooks/rq2-tib-120-semantic-rescore-colab.ipynb) uses the repaired token-ID window implementation and reports **120/120 pairs for all three metrics, zero evaluation failures**, on Tesla T4; `valid/208` passes preflight. All sources, references and 240 predictions remain identical. The original run and frozen protocol are preserved; v2 scoring is a disclosed implementation amendment with separate receipts, not an unmodified execution of the original scorer.

| Outcome | S1 mean | S3 mean | S3-S1 | Exploratory dependence-group bootstrap 95% interval |
|---|---:|---:|---:|---|
| ROUGE-L | 0.12050 | 0.12376 | +0.00327 | [-0.00250, +0.00900] |
| BERTScore | 0.84955 | 0.85166 | +0.00211 | [-0.00075, +0.00500] |
| Source SBERTScore | 0.62227 | 0.62584 | +0.00357 | [-0.00837, +0.01582] |

All intervals cross zero: **no clear winner (`no_selection`)**. Source SBERTScore differences vary by length: short -0.01072, medium +0.01324, long +0.00820. One fixed configuration and repetition on this exposed-reference cohort support finite-cohort descriptive conclusions only, not factuality, statistical power, unseen generalization or full multimodal claims. Original segmentation/generation time and actual tokens are separate from the v2 rescore's 74.98s initialization/preflight and 205.05s scoring session. These resource observations do not establish monetary cost or a formal Pareto result.

Receipt/source/dispatch checks executed inside the notebook; independent local audit of the sealed Drive artifacts remains pending. The [dated results report](../../docs/results/rq2-tib-120-results-261013.md) owns detailed evidence and limitations.

## 2026-10-12 cohort and protocol freeze

The approved 120 evaluation IDs are now selected from creator `valid`, 40 per source-token stratum, by the predetermined SHA-256 rule. The [freeze report](../reports/tib-120-cohort-and-protocol-freeze-261012-report.md) records the sample frame, source-dependence review, limitations, missingness policy and fixed analysis. The [cohort manifest](../../experiments/registry/datasets/tib-rq2-rq4-120-cohort-261012.json) and [protocol](../../experiments/registry/datasets/tib-rq2-rq4-120-protocol-261012.json) bind IDs, hashes, model, scorers, groups and code. The standalone [formal Colab notebook](../../experiments/notebooks/rq2-tib-120-evaluation-colab.ipynb) uses the local frozen 120-bundle. **Selected 120; generation and metric coverage now complete in saved notebook evidence; independent sealed Drive audit pending.** The historical guarded full-pool notebook remains blocked. Earlier pending statements below describe the 2026-10-10 decision before this freeze.

## Historical execution decision — 2026-10-10 (status superseded above)

**Decision TIB-RQ2-RQ4-120-20261010: approve a target of 120 evaluation records, 40 short / 40 medium / 40 long, one configuration and one repetition, paired S1/S3 (240 planned summaries).** The nine-record train development pilot has executed: 18/18 arms complete, 9/9 paired scores for each of three metrics, zero failures. Do not rerun it. At this historical decision, formal evaluation was **0 records**, with **zero selected formal IDs** and **cohort/protocol NOT FROZEN**; these statuses were superseded by the freeze and completed notebook evidence above. The [canonical decision](../../experiments/registry/datasets/tib-rq2-rq4-120-decision-261010.json) supersedes full-pool execution and the historical 12-item valid protocol.

On the measured T4 / map-batch-2 profile, the 120-record planning scenario is **5.00 hours central / 8.37 hours upper scenario**, including initialization, both arms, preparation, three metrics, checkpoints and 30% margin. These are nonprobability cost scenarios, not a runtime guarantee, confidence interval or statistical-power justification. The 150-record upper scenario (10.45h) leaves less margin; 180 (12.53h) exceeds the 12-hour objective. Full 8,769 execution (central 360.35h) is superseded as the default. Retain all 8,769 candidates, including 900 flagged records, as the selection pool.

**Notebook follow-up (2026-10-10):** the integrated notebook now displays the approved decision in its first output and fails closed before installation/data/model execution. Full-pool auto-preparation was removed from its preparation cell; batch size is fixed at 2. Historical outputs remain marked as historical. This is a blocked handoff, not a runnable 120-ID benchmark: implement reviewed cohort/hash/group/scorer binding after freeze. The executed pilot notebook remains byte-for-byte unchanged.

Actual S3 predicts at most five spaced boundaries using adjacent-window lexical Jaccard novelty, forms boundary-constrained chunks, then flattens them into the same map/reduce prompts as S1. There is no separate hierarchy-aware synthesis layer to ablate. S1/S3 answers a pipeline comparison; it cannot isolate boundary placement from chunk-count/length changes. A matched-count boundary-placement control would be a separately designed extension requiring its own timing. Oracle chapters and creator abstracts never enter structure prediction/generation.

Pilot profile: existing pinned Qwen2.5-1.5B checkpoint/tokenizer, greedy seed 42, 512-token source chunks, map batch 2, common map-output allocation `96 * max(n_S1,n_S3)` distributed by exact divmod, final cap 384, shared permissive cumulative prompt cap. These are **equal allocated output caps**, not equal actual total tokens or padded compute. Structure uses zero LLM tokens; CPU/tokenization cost is included in S3 segmentation. Actual input/output tokens are logged; unknown failed usage stays null. No automatic retry. Empty output fails the arm. Two-hour generation deadline is a soft stop between dispatches, not a hard per-call timeout. CUDA failure stops further GPU dispatches. S1/S3 order alternates across selected IDs.

At the 2026-10-10 decision, freeze remained pending: source-dependence review → declared evaluation split and deterministic score-independent selection → locked 120 evaluation IDs/source/reference hashes → frozen scoring, denominators, failure/timeout rules and group-analysis protocol. Length cutpoints are 4,271 and 7,142 tokens (inclusive upper bounds); formal IDs remain unselected. The pilot two-hour soft deadline is historical pilot configuration; formal deadline policy remains to be frozen. All 8,769 candidates and 900 flagged candidates remain in the preparation pool. No hard/long/failed ID is removed by outcome. Development pilot IDs cannot become confirmatory evaluation IDs. Creator valid/test references were already inspected: future evaluation is a declared exposed-reference cohort, never an unseen test.

Primary metric: `unicode_word_lcs_rouge_l_f1_v1`, Unicode `\b\w+\b` tokens, casefold, no stemming, word LCS, `2*LCS/(reference_words+hypothesis_words)`, macro across records. Future reporting uses paired per-record S3−S1 on the successful intersection, alongside all selected IDs and per-arm success/failure coverage. Do not impute failed quality as zero. Secondary BERTScore and source SBERTScore stay separate. Pilot quality does not select IDs/configurations by S3 wins.

Before formal uncertainty, freeze a dependence-group ledger using verified source/DOI/content links and conservative components of reviewed overlap relations. Shared authors/titles alone are review cues, not automatic exclusions. The existing three-record high-overlap cluster and series cues require explicit treatment. Bootstrap paired differences at the frozen video/dependence-group unit (5,000 resamples, seed 20261009), never chunks. If trustworthy grouping remains unavailable, report finite-cohort descriptive differences without population-superiority CI. Legacy item bootstrap is not an approved substitute.

Forecast includes initialization/download/load, both arms in each length stratum, shared preparation, all three scorers and checkpoints, with an explicit 30% planning margin. Min/middle/max length probes are nonprobability cost scenarios, not unbiased throughput estimates or confidence intervals. Failures, resumed/mixed profiles, unmeasured scoring or out-of-range lengths block credible forecasts. Extra configurations/repetitions require added measured cost. Code never freezes a cohort automatically.

## Historical preparation decision — 2026-10-09 (execution instruction superseded above)

Prepare the complete **8,769-record TIB pool** across all creator splits, genres, subjects and durations. No 70-item cap and no manual-review gate. The endpoint is paired **ROUGE-L F1 against creator abstracts**.

The [executed EDA](../../experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb) has 10 successful code cells: 9,103 source records, 9,002 structurally usable transcripts, eight empty abstracts and 225 reused-abstract records excluded. All 900 flagged candidates remain included.

## Historical full-pool execution instructions — superseded

The instructions and default all-pool entry point below document the earlier implementation. **Do not Run all for formal evaluation:** first bind the runner to the reviewed 120-ID cohort, verify count/identity guards and freeze its protocol. No such execution is authorized by this decision.

### Integrated benchmark notebook

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
- [x] Execute nine-record development pilot: 18/18 arms and 9/9 paired scores for all three metrics.
- [x] Approve evaluation scale: 120 records, 40 per length stratum.
- [x] Review dependence groups, declare `valid` split, select and freeze 120 formal IDs and protocol.
- [x] Bind a standalone notebook to the frozen IDs/hash/count guards and prepare the local Colab package.
- [x] Execute generation and separate repaired semantic scoring for all 120 records; saved notebooks report 240 summaries, complete metric coverage and zero rescore failures.
- [ ] Independently audit sealed Drive generation/rescore receipts, dispatch logs, failures and original resource artifacts against notebook evidence.

Historical [20-item audit](../reports/rq2-valid-dataset-audit-261002-report.md), [70-item screen](../reports/tib-cohort-review-261009-0923-benchmark-readiness-report.md) and [broad-pool inspection](../reports/tib-diverse-pool-261009-0943-benchmark-scope-report.md) remain records of earlier work. Their manual qualification requirements do not gate the current automatic study.

## Execution optimization (2026-10-09)

Map generation supports consecutive equal-cap batches (notebook default 8), with unchanged chunk order and exact output allocation. Batched prefix token counting preserves legacy first-overflow chunk boundaries. Live notebook rendering is throttled to two seconds; failures render immediately. Arm receipts record batch size and actual model dispatches separately from logical prompt calls. Completed serial predictions resume unchanged; the notebook displays their execution profile alongside new batch predictions. FP16 batch decoding can produce numerical differences; aggregate costs include all recorded profiles and are not a uniform-throughput experiment. Reduce MAP_BATCH_SIZE to 4 or 2 for smaller GPUs. No GPU speedup has been measured locally; validation uses offline focused tests.
