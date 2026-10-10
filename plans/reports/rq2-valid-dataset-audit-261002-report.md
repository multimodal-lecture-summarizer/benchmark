# RQ2 TIB validation cohort audit — 2026-10-02

## Decision

The pinned 20-record `gigant/tib` `valid` cohort is usable for a **text-only development diagnostic**, with limits below. It is **not** a qualified formal H2 cohort, a verified ASR benchmark, a reference-based summary benchmark, or an S4 visual cohort. No `test` or `mm-test` content was read.

Source revision: `e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee`. Cohort DOI-list SHA-256: `690512dcbc220b9a7da3f2ec72448abc685e9c3fd9f4c1a40f8ae4ebee085759`. Selection and original EDA: [receipt](../261002-0946-rq2-controlled-summarization/rq2-tib-valid-diagnostic-receipt.json), [decision](../261002-0946-rq2-controlled-summarization/rq2-tib-validation-eda-decision.md).

The historical RQ2 EDA notebook was removed on 2026-10-08; its Git revision recorded 11/11 executed code cells, 3 displayed tables and 2 figures (7 plots), with no cell errors. It showed the selection flow, per-record modalities and license labels, abstract and ASR examples, distributions, reference screening and diagnostic-only outcome. Its [compact detailed receipt](../../experiments/outputs/diagnostic/rq2_eda/selected_valid_details.json) records all 20 validation items and the same DOI-list hash. Published archive abstracts are data examples, not qualified ground truth.

## Direct checks

- **Transcript:** 20/20 have ordered timed segments, no segment gap over 30 seconds and no Unicode replacement characters. DOI `10.5446/15101` has one zero-duration ASR segment at 2090.56 seconds; its text is retained. Normalized token sequences agree in 20/20. Whitespace word counts agree in 19/20; DOI `10.5446/43747` has a punctuation-spacing difference (`understand....of` versus `understand. of`). The [creator dataset card](https://huggingface.co/datasets/gigant/tib/blob/main/README.md) says transcripts come from automatic speech recognition. These consistency checks do **not** measure WER or verify speech content against audio.
- **Group separation:** 13/20 exact author strings occur in 7,282 projected `train` metadata rows. Nine selected titles have concrete same-series train titles. Seven DOI suffixes have neither exact train-author overlap nor a close title-family match in that scan: `14078`, `20846`, `20848`, `38319`, `43747`, `50943`, `55669`. This is a conservative development subgroup, not a proven formal holdout; coauthors, aliases and the sealed test remain unchecked.
- **Abstracts:** 20/20 source landing pages returned an abstract. Compared with the pinned dataset abstract, 16 match after case/whitespace normalization, three are cleaned substrings and one has editorial punctuation plus chapter-list changes. Eight are plainly unsuitable as summaries of the individual talk; 12 remain candidates pending source-claim support and authorship/provenance checks. **Qualified formal reference denominator: 0/20.** ROUGE/BERTScore should remain `N/A` for formal H2 until each reference passes.
- **Visual evidence:** 20/20 creator rows have keyframe *metadata*, 1,012 timed entries in total (9–120 per talk); they do not contain image pixels or OCR. All 20 have nonempty license metadata: 10 CC BY 3.0, 2 CC BY-SA, 2 CC BY-NC-SA, 6 CC BY-NC-ND. End keyframe versus transcript time differs by −20.7 to +17.4 seconds; 8/20 differ by more than five seconds. A DOI-only scan of all 822 `gigant/tib-bench` train rows (51 Parquet shards; no image bytes downloaded) found **0/20 matches**. That slide collection cannot directly supply S4 images for this cohort. Source-video extraction remains possible only after per-DOI media, license and alignment checks. S4 = `not_run`.

## Per-record screening

DOI values below are `10.5446/<suffix>`. “Author” counts exact-string matches in train metadata. “Series” means a concrete same-family title in train. “Abstract” is a screen, **not** a verified reference label. “KF” is keyframe metadata count, not downloaded images.

| DOI suffix | Author | Series | Abstract screen | KF |
|---|---:|---|---|---:|
| 14078 | 0 | no match | unsuitable: book-signing description | 40 |
| 15101 | 53 | yes | candidate: short lecture description; one zero-duration ASR segment | 52 |
| 16294 | 1 | yes | candidate: short topic outline | 75 |
| 18890 | 17 | yes | unsuitable: course-level description | 39 |
| 19217 | 31 | unconfirmed | unsuitable: course-level description | 35 |
| 20846 | 0 | no match | candidate: talk-specific abstract | 68 |
| 20848 | 0 | no match | candidate: talk-specific abstract | 44 |
| 35254 | 1 | unconfirmed | candidate: short topic outline | 65 |
| 38319 | 0 | no match | unsuitable: speaker/event biography | 68 |
| 38638 | 1 | yes | unsuitable: three-word chapter stub | 41 |
| 43747 | 0 | no match | unsuitable: title/speaker only; punctuation-spacing difference | 60 |
| 45978 | 6 | unconfirmed | candidate: talk-specific abstract | 9 |
| 46066 | 11 | unconfirmed | candidate: source abstract has additional chapter list | 75 |
| 48908 | 4 | yes | candidate: phonology topics | 14 |
| 49247 | 3 | yes | candidate: text-sample lecture | 12 |
| 49452 | 2 | yes | candidate: short morphology topic | 25 |
| 49509 | 2 | yes | candidate: Gothic morphology outline | 18 |
| 50934 | 1 | yes | candidate: course aim, part 1/3 | 64 |
| 50943 | 0 | no match | unsuitable: mini-course abstract for part 3/3 | 120 |
| 55669 | 0 | no match | unsuitable: course-level abstract for part 2/3 | 88 |

Concrete `valid`→`train` series examples include `49247` Old Irish Part 3 against `49246` Part 2, `49248` Part 3 and `49249` Part 4; `16294` Polyfolds 1/4 against `16296` 3/4; and `50934` Noncommutative 1/3 against `50927` 3/3. Matching series is a group-leakage risk, not proof that the transcript text is duplicated.

## S1–S3 execution and scientific limit

The historical [validation diagnostic runner](../../experiments/scripts/rq2_valid_paired_diagnostic.py) ran 20/20 selected DOI pairs with zero failed or missing records. Its manifest and per-talk artifacts, later withdrawn and removed, contained source identity, transcript-prefix hash, predicted lexical-cohesion boundaries, S1/S3 summaries, per-call prompt-size estimates and errors. No raw transcript or reference was persisted. Thirteen transcripts were limited to an 8,000-token-estimate prefix; all 40 summary outputs were nonempty and under the 128-token-estimate output cap.

The generator was the deterministic local engine and S3 used a source-only lexical-cohesion detector, **not** registered learned C5. Across all map/reduce calls, estimated cumulative prompt tokens exceeded 8,000 in 13/20 S1 and 13/20 S3 runs; S1 and S3 estimates differed in all 20 pairs. Median estimates were 9,351 (S1) and 8,538.5 (S3). These are word-derived estimates, not tokenizer/provider measurements. No quality or human metric was scored. The run establishes pipeline execution and exposes a token-fairness failure; it is not evidence that S3 improves S1.

Focused validation: `python -m pytest tests/test_rq2_valid_paired_diagnostic.py -q` passed 8/8. A second run resumed all 20 fingerprint-matched outputs with zero failures. The code review found no remaining high-priority blocker for this **diagnostic** scope.

## Remaining gates

1. For formal H2, acquire audio/transcript accuracy evidence on sampled items; finish author/course/series grouping and qualified final split without opening sealed content prematurely.
2. If reference metrics are wanted, verify each candidate abstract against the corresponding talk and document who supplied it where evidence exists. Do not infer authorship from the dataset card's “likely” statement.
3. For S4, acquire real video/slide pixels under each item's terms, join DOI and timestamps, verify image/OCR content and drift. `tib-bench` has no DOI overlap with this 20-item cohort.
4. Choose a tokenizer-accounted generator and freeze equal measured cumulative source-token allocation, output cap, prompts, retries and blinded human rubric. Time a development pilot before sizing the formal H2 study.

## Reproduction notes

From the nested app directory, run `python experiments/scripts/rq2_valid_paired_diagnostic.py --limit 20`. In this sandbox the default proxy pointed to `127.0.0.1` and Hugging Face's default cache was not writable; the successful read used process-local removal of `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` and `HF_HOME` under the ignored workspace output directory. No global network or cache setting was changed.
