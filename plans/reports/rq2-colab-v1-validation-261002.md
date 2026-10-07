# RQ2 TIB valid Qwen Colab v1: executed-output review

Source: executed outputs of `experiments/notebooks/diagnostics/rq2-tib-valid-qwen-colab.ipynb`, inspected 2026-10-02. The Drive manifest, per-DOI receipts, and `automatic_evaluation.json` have not been independently opened for this review.

Retention update 2026-10-06: the v1 notebook was deleted at the user's request during cleanup of old versions. This report preserves the prior review summary, but its notebook outputs are no longer available in the repository for independent rechecking.

## Run and result

- Cohort: 20 pinned `gigant/tib` valid DOIs; source is timed transcript text. The run did not access the sealed test split.
- Model and comparison: pinned Qwen2.5-1.5B-Instruct, greedy decoding; S1 fixed 512-token chunks versus S3 source-derived boundaries, followed by section summaries and a final summary.
- Completed: 18/20 paired cases. DOI `10.5446/38319` and `10.5446/50943` failed. Notebook table shows both reasons truncated as `Backend generated-token usage is below visible...`; the matching guard in the embedded runner raises `Backend generated-token usage is below visible text count`.
- Mean paired S3 − S1 ROUGE-L F1 against the provided creator abstract: **−0.00965** (5000-sample paired bootstrap 95% interval **[−0.03152, +0.00957]**). S3 is higher for 10 cases, lower for 7, tied for 1. This validation run does not establish a reliable S3 advantage.
- Nine of the 18 completed cases have abstracts shorter than 30 words, including one with only 3 words. As a descriptive sensitivity check, the mean paired difference is **+0.00070** for the 9 abstracts with at least 30 words and **−0.02000** for the 9 shorter abstracts. These strata are small and the abstract is an unverified reference proxy.
- Notebook output says the run saved `/content/drive/MyDrive/RQ2_TIB_VALID_QWEN/valid_qwen_34d3c6a28823/manifest.json` and `automatic_evaluation.json`. Summed reported per-item time is about 51.5 minutes; this excludes setup and model download.

## Interpretation and repair

The two failures come from a false token-accounting assumption: decoded text can re-encode into more tokens than the raw generation emitted. Raw generated-token usage and the visible text's re-encoded token count are independently valid counts. The runner and v2 Colab notebook now validate each count against its own source without comparing their ordering. A focused test covers this case; 8 RQ2 runner/budget tests pass.

The v1 run limited both section and final summaries to 96 generated tokens. An inspected per-DOI receipt from this run had final summaries ending mid-sentence at that cap. The prepared v2 notebook keeps section summaries at 96 tokens and allows 384 tokens for final summaries. Because v2 changes the final-summary budget, it writes to a separate config-hashed Drive directory and requires a new run of all 20 cases for a comparable paired result. It has been checked statically and locally with unit tests; v2 has not been run in Colab.

The ROUGE-L score measures wording overlap with creator abstracts. This run does not assess factual accuracy, image content, audio waveform content, or a sealed final-test result. The 18-case score remains a validation diagnostic, not an official RQ2 conclusion.

## Unresolved questions

- Open the Drive manifest and per-DOI receipts to confirm full failure reasons, receipt integrity, summary completion, and output lengths.
- Run the corrected v2 notebook on Colab and inspect its full 20-case outputs before selecting the official RQ2 configuration.
