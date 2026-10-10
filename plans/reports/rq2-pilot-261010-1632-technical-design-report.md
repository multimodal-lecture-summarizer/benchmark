# TIB RQ2/RQ4 — technical audit and Colab pilot handoff

Date: 2026-10-10. Status: **CPU preparation verified; GPU pilot NOT EXECUTED; evaluation cohort/protocol NOT FROZEN.** No local model inference, large benchmark, or unrelated dataset recovery was started.

## Scientific scope and actual mechanism

The next experiment compares creator-abstract agreement and measured text-pipeline cost on the same records. It cannot establish factual video-summary quality, usefulness to learners, audio/visual contribution or multimodal ablation. OCR crop recognition follows this route; MLP/board/EduVidQA media HOLDs do not block it.

| Condition | Actual implementation | Defensible role |
|---|---|---|
| S1 | Full ordered transcript → greedy token-limited fixed chunks → section summaries → one reduce summary | Primary comparator |
| S3 | Source-only adjacent-window lexical Jaccard novelty → at most five spaced boundaries → boundary-constrained token-limited chunks → flattened **same** section/reduce prompts | Alternative chunking pipeline |
| Separate hierarchy synthesis ablation | No separate synthesis mechanism exists in current code | Do not invent an ablation that is identical to S3 |

S1/S3 does not isolate semantic boundary placement from chunk count/length. A matched-count uniform-boundary control would need a new defined condition, measured cost and a revised protocol before inclusion. Current pilot has exactly two arms and does not claim that control exists.

Code inspected: `rq2_controlled_validation.py`, `rq2_tib_benchmark_pair.py`, `rq2_local_hf_backend.py`, bundle/data/results/metric modules. Hierarchical/multistage summarization alone is not a novelty claim; [SummN](https://aclanthology.org/2022.acl-long.112/) already studies multistage summarization of long inputs. Contribution here must rest on the specific controlled comparison and observed trade-off, including null/negative findings.

## Budget and resource contract

| Item | Pilot setting / accounting |
|---|---|
| Dataset | `gigant/tib@e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`; reuse validated 8,769-record bundle from 9,103 sources |
| Generator/tokenizer | Existing `Qwen/Qwen2.5-1.5B-Instruct@989aa7980e4cf806f80c7fef2b1adb7bc71aa306`; raw prompts, FP16, greedy, seed 42 |
| Source | Same complete source in both arms, no truncation. Abstract goes only to scorers |
| Chunk cap | 512 source tokens, unchanged legacy chunking behavior |
| Intermediate output | Common allocation `96 × max(n_S1,n_S3)`; exact divmod allocation across each arm's chunks |
| Final output | 384 tokens in each arm |
| Prompt accounting | Common permissive cumulative prompt cap, actual unpadded prompt tokens measured. This cap is not an equal-input-compute claim; the shared usage validator checks cumulative usage after returned calls |
| Structure cost | Zero LLM tokens; boundary prediction/chunking/tokenizer CPU time charged within S3 segmentation |
| GPU profile | Map batch 2, no automatic batch fallback; per-arm synchronized time, peak allocated/reserved VRAM; record hardware/package profile |
| Failed calls | Known prompt usage retained; missing output usage null, not zero. Prompt log contains counts, not references/raw prompts |

Equal allocated intermediate/final output caps do **not** imply equal actual total tokens. Padding affects compute without being counted as actual source tokens. All dispatches, logical calls and returned attempts are recorded separately. Local backend has no automatic retry. Manual resume retains attempt history; resumed profiles cannot establish a uniform throughput forecast. New code/config/hardware/selection requires a new result directory.

## Executed CPU evidence

Reused the existing full prepared bundle; did not rerun all-split EDA or source acquisition. Exact untruncated token counts computed for all **8,769 sources**, using the cached pinned tokenizer. Preparation took **102.976 seconds**, excluding tokenizer import/load. This is a CPU measurement, not a GPU throughput estimate. Source token cache is a derived ledger; original texts/labels were not modified.

Strata use train rank-third cutpoints **4,271** and **7,142** tokens, ties in the lower stratum. Within each, choose minimum/middle/maximum rank; no outcome/reference content enters this choice. Selected IDs remain development-only.

| ID | Length group | Source tokens | S1 chunks | S3 chunks | Common map cap |
|---|---|---:|---:|---:|---:|
| train/55 | long | 7,144 | 14 | 17 | 1,632 |
| train/1646 | medium | 4,274 | 9 | 10 | 960 |
| train/2014 | long | 9,376 | 19 | 21 | 2,016 |
| train/3741 | medium | 5,467 | 11 | 13 | 1,248 |
| train/4930 | long | **37,455** | 74 | 76 | 7,296 |
| train/5753 | short | 87 | 1 | 2 | 192 |
| train/5880 | short | 3,109 | 7 | 7 | 672 |
| train/6036 | short | 4,271 | 9 | 10 | 960 |
| train/6748 | medium | 7,142 | 14 | 16 | 1,536 |

Both arms reconstruct the identical complete normalized source for all nine. The longest train source is also the maximum of the full pool: 37,455 tokens. It remains selected. Full-pool numeric-stratum counts: **2,920 / 2,913 / 2,936**. Reserved creator valid counts: 296 / 289 / 302; test: 289 / 290 / 300. These are preparation counts, not frozen evaluation cohorts.

Pinned cached model config has context capacity 32,768. All nine pass a source-only planning screen `4 × common_map_cap + 384 + 2048 < context_capacity`. This is a conservative heuristic, **not** a proof about generated/re-tokenized reduce text; backend still checks actual prompt plus output cap before dispatch. No generated reduce prompt has been observed yet.

CPU receipt: `experiments/outputs/rq2_tib_pilot_261010/cpu-preparation-receipt.json`, includes source coverage, chunk counts, timings, code fingerprints and tokenizer file SHA-256. Counts for this source-only audit: **selected 9 / observed 9 / structurally label-valid 9 / media-valid 0 / model-evaluated 0 / failed 0**. Label-valid means creator abstract screening, not independently verified factual GT. Media was not decoded and is unnecessary for this text-only claim. Token lengths were observed for all 8,769 records separately.

## Failure, metric and analysis policy

- Alternate S1-first / S3-first across selected IDs. No quality-based deletion, replacement or configuration tuning.
- Empty output fails an arm; ordinary arm failure retains partial usage and attempts the other arm. CUDA/OOM stops further GPU dispatches. Deadline: two-hour soft wall stop between calls; no hard kernel timeout. Interrupted/unattempted IDs remain in the declared denominator.
- Release generator before loading semantic encoders. Semantic failure retains predictions, records the error and stops evaluation; no hidden regeneration.
- Primary: `unicode_word_lcs_rouge_l_f1_v1`, Unicode `\b\w+\b`, casefold, no stemming, word LCS, F1 `2LCS/(ref_words+hyp_words)`, per-record macro. Report paired S3−S1, not just two means.
- BERTScore: existing pinned XLM-R large layer 17, no IDF/rescaling; long inputs use declared token-window/global-alignment extension. Source SBERTScore uses pinned multilingual MPNet over all source sentences, not factuality percentages. Keep metrics separate.
- Future quality on the successful S1/S3 intersection must show its denominator and full selected/per-arm failure coverage. Do not impute failed quality as zero. Pilot scores are diagnostic only.
- Before confirmatory CI, freeze source/dependence-group membership and estimand. Existing cross-split audit identified a three-record high-overlap cluster and series cues; author/title collisions alone are not duplicate evidence. Bootstrap paired differences by video/dependence group, never chunks. Without reliable groups, retain finite-cohort descriptive differences and withhold population-superiority CI. Legacy item-level bootstrap is not the approved group analysis.
- All creator split references have been inspected in EDA. Do not call any of these references unseen. Pilot train IDs are not confirmatory evaluation IDs.

## Runtime decision after GPU receipts

Forecast includes initialization/download/load, both arms, shared preparation, ROUGE + BERTScore + source SBERTScore, checkpoint I/O and explicit 30% planning margin. Already cached preparation is reused; its CPU cost above is disclosed separately. Session-start wall timing includes pauses between notebook cells, so Run all for a comparable profile.

Length-rank probes are nonprobability technical scenarios, not unbiased population sampling. Stratum means plus observed min/max scenarios help plan; the range is not a statistical CI or guarantee. Additional configurations/repetitions are not included automatically and need their own cost evidence. Failed, resumed, heterogeneous, incomplete or out-of-length-range profiles block a credible forecast. Full-pool forecast is a planning scenario, not permission/instruction to execute 8,769 pairs. Choose final scope only after reviewing receipts; no automatic ID selection/freeze.

## Delivery and verification

- Notebook: `experiments/notebooks/rq2-tib-technical-pilot-colab.ipynb`; seven code cells, all unexecuted GPU cells explicitly blank.
- Builder: `build_rq2_tib_pilot_notebook.py`; embeds 13 current modules so uncommitted local code is reproducible on Colab without relying on remote Git state.
- New modules: `rq2_tib_pilot.py`, `rq2_tib_pilot_runtime.py`, `rq2_tib_pilot_data.py`, `rq2_tib_pilot_cohort.py`, `rq2_tib_pilot_forecast.py`.
- Shared pair module adds optional arm order/failure continuation; defaults preserve existing caller behavior.
- Tests: `test_rq2_tib_pilot_design.py`, `test_rq2_tib_pilot_runtime.py`, plus existing cost/map-batching/stage-logging suites: **52 passed in 0.94 s, exit 0**. Earlier runs emitted an ignored Windows pyreadline destructor OSError after exit 0; the final run exited cleanly. No test failed.
- Parsed all seven notebook code cells and 13 embedded modules; embedded source matches current files. ZIP CRC verified. These checks do not establish Colab dependency installation or GPU success.
- Updated owning RQ2 plan, master evidence map, decision log, benchmark README, claim register and notebook manifest. Existing EDA outputs/historical scores preserved. Formal grouped bootstrap and final cohort are pending, not falsely marked implemented/frozen.

## Run on Colab

1. Extract `experiments/outputs/rq2_tib_pilot_261010/rq2-tib-technical-pilot-colab.zip`.
2. Upload its `data` directory into **`MyDrive/RQ2_TIB_PILOT_20261010/data`**. It contains nine prepared records, design and full-pool token-length ledger, not another full-text copy of 8,769 records.
3. Open the enclosed notebook in Colab, choose GPU, Run all. Use a fresh root; never run two sessions writing the same result directory. Changed configuration/code/hardware requires a new result directory.
4. Return `pilot-run-v1/pilot-receipt.json`, `dispatches.jsonl`, `runtime-forecast.json`, and root `context-preflight.json` for review. Drive checkpoints survive browser closure, but runtime idle/disconnection can interrupt execution. Reopen metric stage using saved predictions; do not count resumed costs as a fresh uniform pilot.

## Unresolved decisions

- Actual Colab throughput, VRAM and metric cost; whether a scientifically useful cohort fits 12 hours.
- Final evaluation ID list, dependence-group ledger/estimand, formal grouped analysis and protocol freeze.
- Whether an additional boundary-placement control is scientifically necessary; it is not included in current two-arm cost estimate.
