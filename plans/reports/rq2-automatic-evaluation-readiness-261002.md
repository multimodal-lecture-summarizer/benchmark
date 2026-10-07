# RQ2 automatic evaluation readiness — 2026-10-02

## Decision

**Proceed with text-only controlled research preparation on creator TIB; do not yet label the present 20-pair output a formal RQ2 result.** Human or blinded scoring is not required. A fixed minimum of 50 talks is not required. The [protocol amendment](../261002-0946-rq2-controlled-summarization/rq2-automatic-evaluation-amendment.md) records these changes.

The [executed EDA notebook](../../experiments/notebooks/diagnostics/rq2-tib-valid-eda.ipynb) shows the actual selected dataset; the [executed automatic evaluation notebook](../../experiments/notebooks/diagnostics/rq2-valid-automatic-evaluation.ipynb) shows every paired DOI and plots. Machine-readable item scores are in `experiments/outputs/diagnostic/rq2_valid_paired/automatic_evaluation.json` (ignored diagnostic output).

## Data actually used

| Property | Observed validation cohort |
|---|---:|
| Creator TIB `valid` Lecture records selected | 20 |
| Timed ASR transcripts | 20/20 |
| Source-prefix truncation in current run | 13/20 |
| Abstracts screened candidate but unverified | 12/20 |
| Abstracts unsuitable as talk-specific proxy | 8/20 |
| Abstracts under 30 words | 9/20 |
| Train author metadata overlap | 13/20 |
| Keyframe time metadata | 20/20, 1,012 intervals |
| Aligned frame pixels/OCR for these DOI in `tib-bench` | 0/20 |

TIB supplies an automatically transcribed audio track as text, not independently verified ASR accuracy. Keyframe times describe possible visual sampling, not actual visual content. Current study can compare **text inputs**; it cannot claim audio or slide contribution. Abstracts are dataset-provided noisy targets, not verified ground truth.

## Completed 20-pair automatic diagnostic

| Metric, S3 minus S1 | n | Mean | Paired bootstrap 95% interval |
|---|---:|---:|---:|
| ROUGE-L F1 against all creator abstracts | 20 | +0.00557 | −0.00662 to +0.01955 |
| ROUGE-L, candidate but unverified abstract subset | 12 | +0.00862 | −0.00589 to +0.02644 |
| ROUGE-L, unsuitable abstract subset | 8 | +0.00100 | −0.01646 to +0.02648 |
| Source unique-word overlap proxy | 20 | −0.04446 | −0.05380 to −0.03621 |

The ROUGE intervals span zero. The word-overlap metric counts unique summary word types present in the processed transcript prefix; it is not factuality, and its sign cannot establish that S3 is less accurate. These are descriptive intervals for a selected validation cohort, not population inference or a formal hypothesis test.

## What the current run does and does not prove

S1 and S3 used the same selected source prefix and a deterministic, mostly extractive sentence-selection engine. S3 used lexical TF-IDF cohesion rather than the planned learned chapter predictor. Thirteen pairs exceeded the approximate cumulative prompt cap in at least one arm, and actual tokenizer-matched token fairness was not verified. Thus this diagnostic verifies that the data adapter, paired outputs and evaluator work; it does not estimate the effect of controlled hierarchical LLM summarization.

Existing `run_summary_evidence_evaluation.py` overlap thresholds and `factuality_coverage` are not validated factuality measures. They are excluded from the study outcome. The S3 source-budget leak in the generic summarizer has been fixed and tested, but this does not retroactively turn the old outputs into formal evidence.

## Real-LLM validation attempt and machine crash

The user selected a real LLM. `Qwen/Qwen2.5-1.5B-Instruct` revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` was downloaded into ignored workspace output and run through [the exact-usage backend](../../experiments/scripts/rq2_local_hf_backend.py). Five S1/S3 validation pairs completed with per-call prompt/output counts and same full source span. During the next pair, `nvidia-smi` reported **GPU is lost**; the user reported that the RTX 4050 run crashed the machine. The process was stopped. No further GPU generation was attempted. The remaining 15 selected DOI are recorded as `not_run` in `experiments/outputs/diagnostic/rq2_valid_controlled_qwen/manifest_interrupted.json`.

Using only cached pinned abstracts on CPU, the five completed pairs had ROUGE-L S3−S1 mean **−0.01110**, paired bootstrap 95% interval **[−0.06412, +0.03291]**. This is a small interrupted development subset selected shortest-first, not a formal comparison or evidence of a negative effect. Source lexical overlap is N/A in this cached-abstract evaluation. The [executed interrupted-run notebook](../../experiments/notebooks/diagnostics/rq2-valid-real-llm-interrupted.ipynb) shows every retained DOI and all 15 `not_run` entries; item scores are in `experiments/outputs/diagnostic/rq2_valid_controlled_qwen/automatic_evaluation_interrupted.json`.

The local runner now defaults to CPU and requires explicit `--device cuda`; it no longer silently selects the RTX 4050. Do not resume this GPU run on the current machine until the device/driver issue is resolved. The crash cause has not been diagnosed.

**Later Colab receipt check:** a user-provided completed receipt for DOI `10.5446/50934` has 25 S1 and 27 S3 map chunks. Both final reduce calls hit the v1 96-token output cap and the visible summaries end mid-sentence. This is an output-truncation limitation of the first Colab notebook, not the reason DOI `10.5446/50943` failed. The historical Colab v2 run kept map summaries at 96 tokens and gave final summaries 384 tokens in a new config-hashed output directory; its notebook file was removed from the active workspace on 2026-10-07 at the user's request. The v1 run remains a diagnostic; do not combine v1/v2 scores as one run.

## Practical route to a formal study

1. Keep the pinned real Qwen generator and exact-usage backend selected for the abstractive claim. Run the remaining validation pairs on a stable CPU/remote environment; the current RTX 4050 is unsuitable after the device-lost crash. Do not combine CPU and GPU receipts as a single frozen run without documenting the device change.
2. On `valid`, run S1/S3 with identical source spans, model and decoding settings; record exact tokenizer/provider input and output counts for every map/reduce call and retry. Freeze a cumulative budget and a reasonable predeclared imbalance tolerance. Preserve each failed DOI.
3. Use the declared [primary outcome config](../261002-0946-rq2-controlled-summarization/rq2-automatic-outcome-config.json): paired ROUGE-L against all nonempty creator abstracts, with talk-specific suitability and abstract-length sensitivity shown. This measures similarity to creator descriptions, not truth. Source overlap, length, token use and latency are secondary/descriptive.
4. Freeze split/group policy, generator, structure predictor, reference screen, analysis code and random seed before reading sealed test content. Then run one paired held-out evaluation and report per-item outputs, interval, missingness and negative results.

A [controlled validation runner](../../experiments/scripts/rq2_controlled_validation.py) and local backend enforce paired source and exact-usage receipts. The old engines still cannot supply these receipts. Focused RQ2 tests passed before the GPU incident; CPU-only checks are rerun below in the final handoff. These are measurement and reproducibility tasks, not a request for blind scoring, a 50-item floor or a perfect reference dataset. A small sample may produce a wide interval; that limits the conclusion rather than prohibiting the study.

## Open questions

1. Which stable compute environment should finish the pinned Qwen validation run: CPU with longer runtime or a different GPU host?
2. What caused the local RTX 4050 device loss/system crash? Keep local GPU generation disabled until that is resolved.
