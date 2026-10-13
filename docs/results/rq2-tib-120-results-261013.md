# RQ2 TIB 120: completed evaluation with semantic amendment v2

Evidence reviewed on 2026-10-13 (Asia/Bangkok): [original generation notebook](../../experiments/notebooks/rq2-tib-120-evaluation-colab.ipynb) and [executed semantic rescore notebook](../../experiments/notebooks/rq2-tib-120-semantic-rescore-colab.ipynb). Scope: text-only S1 fixed chunks versus S3 source-predicted boundaries, one configuration/repetition, pinned Qwen2.5-1.5B, T4 FP16 map batch 2. Creator `valid` cohort contains 40 short, 40 medium and 40 long records selected before generation.

## Execution and evidence level

- Original generation: 120/120 records, both arms complete (240 summaries), ROUGE-L available for all 120 pairs.
- Original semantic scoring stopped at `valid/208`, leaving only 28 paired semantic scores. This partial output remains historical.
- Semantic-only v2 rescore: 120/120 completed on Tesla T4; evaluation_failed/interrupted/not_attempted/in_progress all zero. All three metrics now have 120 paired scores.
- Rescore notebook: six executed code cells, six embedded PNGs, zero error outputs. SHA-256: `ce6c3cc09255e67dd79843122193d5bc3091e7b03d5e59e9fdabcb45edb758a4`.
- All 120 displayed creator abstracts and both summaries exactly match the original notebook. Semantic means and dependence-group intervals were independently recomputed from the 120 detailed per-arm score events in the saved notebook.
- The notebook reports validation of source/reference hashes, original seal and dispatch ledger. Original Drive JSON receipts/ledger have not been retrieved and independently audited locally. Do not conflate notebook-output verification with an independent artifact/seal audit.

The v2 implementation fixes sentence-window retokenization overflow by slicing original token IDs, applying encoder wrappers/padding and forwarding the complete SentenceTransformer pipeline without truncation. It retains model revisions and the declared aggregation formula, but is an explicit implementation amendment. All 120 semantic pairs were recomputed; no v1/v2 semantic score mixing. Frozen generation protocol, source and predictions are preserved. See [rescore procedure](rq2-tib-semantic-rescore-v2.md).

## Results

All values below use the same 120 paired records. Delta is S3 minus S1; higher metric scores indicate more agreement/similarity, not factuality.

| Metric | S1 | S3 | Mean delta | Exploratory dependence-group 95% interval | S3 higher / S1 higher |
|---|---:|---:|---:|---|---:|
| ROUGE-L F1 | 0.120495 | 0.123764 | +0.003269 | [-0.002500, +0.009003] | 64 / 56 |
| BERTScore F1 | 0.849552 | 0.851660 | +0.002108 | [-0.000752, +0.005004] | 62 / 58 |
| Source SBERTScore | 0.622266 | 0.625838 | +0.003572 | [-0.008374, +0.015820] | 61 / 59 |

Frozen sensitivity method: 5,000 whole-component resamples, seed 20261009, record-weighted percentile intervals. There are 120 dependence groups; author sensitivity uses 119 groups. Author-group intervals also cross zero for every metric: ROUGE-L [-0.002374, +0.008914], BERTScore [-0.000834, +0.005021], source SBERTScore [-0.009079, +0.015838]. These are exploratory finite-cohort sensitivity intervals, not confirmatory population-superiority tests.

| Stratum (40 records each) | ROUGE-L delta | BERTScore delta | Source SBERTScore delta |
|---|---:|---:|---:|
| Short | +0.000767 | +0.003085 | -0.010716 |
| Medium | +0.004372 | +0.001375 | +0.013236 |
| Long | +0.004667 | +0.001865 | +0.008197 |

**Conclusion: no clear winner (`no_selection`).** S3 has small positive overall means, but all exploratory intervals include zero and per-record wins are nearly balanced. Source similarity decreases for short records and increases for medium/long records. Do not describe the result as consistent superiority of structured summarization. S3 changes both boundaries and chunk count/length, so the experiment does not isolate a pure boundary-placement effect.

## Measured costs relevant to RQ4

| Original generation resource | S1 | S3 |
|---|---:|---:|
| Prompt tokens | 894,704 | 899,830 |
| Output tokens | 179,524 | 177,929 |
| Generation seconds | 4,892.003137 | 4,775.379347 |
| Segmentation seconds | 455.855550 | 435.636479 |
| Incomplete-usage attempts | 0 | 0 |

S3 used approximately 0.57% more prompt tokens and 0.89% fewer output tokens; measured generation time was approximately 2.38% lower in this single run. Equal allocated output caps are not equal actual token use or equal padded compute. These observations do not establish a repeatable speed advantage or full-system Pareto frontier.

Semantic v2 rescore costs are separate: initialization/preflight 74.981829 seconds; scoring session 205.054121 seconds; sum of known item scoring times 142.760125 seconds for 120 attempts, with zero unknown-duration attempts. Session time includes overhead and is not the same measurement as summed item time. Do not count inherited generation twice or present the rescore as a new generation run. Monetary costs and end-to-end multimodal efficiency are unmeasured.

## Artifact locations and remaining audit

Drive root: `MyDrive/RQ2_TIB_120_20261012/`. Original: `formal-run-v1/frozen-receipt.json` and `dispatches.jsonl`. Amendment: `semantic-rescore-v2/rescore-receipt.json`, `aggregate-report.json`, per-item/metric/stratum/interval CSVs, six PNGs and scoring-environment JSON. These are expected paths printed in the notebook; independent local receipt retrieval/verification remains pending.

Creator abstracts were exposed in EDA and are not independently verified factual-summary labels. Source SBERTScore is transcript similarity, not a factuality percentage. This result supports a descriptive creator-abstract/transcript-agreement comparison on the selected text cohort; it does not establish unseen generalization, factual video-summary quality or benefits from audio/images.

Remaining action: audit the actual Drive receipts and dispatch ledger independently when made available. No new model run is required merely because the outcome is inconclusive.
