# RQ2 TIB valid Qwen Colab v2: notebook and ZIP audit

Sources inspected 2026-10-02: saved outputs in the then-present `rq2-tib-valid-qwen-colab-v2.ipynb`, the user-provided `C:\Users\hung\Downloads\valid_qwen_32e3054813bc-20261002T084426Z-1-001.zip`, and the source snapshot `C:\Users\hung\Downloads\rq2_tib_valid_20_source_reference_review.json`. The notebook was removed from the active workspace on 2026-10-07 at the user's request; this report and the local ZIP export retain the run findings. The ZIP contains the Drive manifest, 20 per-DOI JSON receipts, and `automatic_evaluation.json`.

## Run receipt from notebook output

- Pinned `gigant/tib` `valid` cohort: **20/20 paired cases completed**, including `10.5446/38319` and `10.5446/50943`, which failed in v1. The notebook and receipts report no sealed test access.
- Pinned Qwen2.5-1.5B-Instruct, greedy decoding, S1 fixed chunks versus S3 source-derived boundaries, with the same transcript for each pair. Map summaries allow 96 output tokens; final summaries allow 384.
- Transcript sizes in the displayed table range from 1,171 to 14,951 tokens. The largest observed S1/S3 prompt-token imbalance is 451, below the declared tolerance of 2,048.
- Sum of displayed per-DOI times: **3,716.81 seconds (61.95 minutes)**, excluding setup and model download. The v1 displayed sum was 51.53 minutes; these runs have different final-output limits and runtime conditions.
- Saved Drive paths: `/content/drive/MyDrive/RQ2_TIB_VALID_QWEN/valid_qwen_32e3054813bc/manifest.json` and `automatic_evaluation.json` in the same directory.

## Automatic score

ROUGE-L F1 uses the provided creator abstract as a reference proxy. Paired S3 minus S1 mean is **−0.00643**, with a 5,000-resample bootstrap 95% interval of **[−0.02125, +0.00946]**. S3 scores higher in 9 cases, S1 in 10, and they tie in 1. The interval includes zero; this run does not show a reliable S3 gain on this proxy.

Descriptive sensitivity checks from the displayed table:

| Slice | Cases | Mean S3 − S1 | 95% bootstrap interval | S3 / S1 / tie |
| --- | ---: | ---: | ---: | ---: |
| All | 20 | −0.00643 | [−0.02125, +0.00946] | 9 / 10 / 1 |
| Abstract at least 30 words | 11 | −0.01229 | [−0.03764, +0.01430] | 5 / 6 / 0 |
| Abstract under 30 words | 9 | +0.00073 | [−0.00846, +0.01121] | 4 / 4 / 1 |
| Neither final summary hits 384-token cap | 15 | +0.00112 | [−0.01459, +0.01853] | 8 / 6 / 1 |

The slices are exploratory, small, and overlapping. They are checks on score stability, not alternative official outcomes.

## Output-length and reference limits

The final summary reaches the 384-token generation cap in **3 S1 arms and 3 S3 arms**, across five distinct DOIs: `10.5446/50943`, `10.5446/46066`, `10.5446/20846`, `10.5446/43747`, and `10.5446/20848`. All six capped summaries end without a completed sentence in the saved receipts. Nine creator abstracts are under 30 words, including one of three words. The source/reference review below shows substantial variation in suitability as lecture-summary references.

## Independent ZIP integrity and output audit

- ZIP CRC check passes. Manifest has 20 unique completed DOIs and matches the declared cohort hash. All 20 receipt hashes and identity hashes recompute; DOI, model configuration, source selection hash, call counts, token-usage sums, and declared budgets agree. The saved evaluation has 20 matching rows. Recomputed score deltas and paired bootstrap match the saved values to floating-point precision. These checks show internal consistency, not independent confirmation that source transcripts or abstracts are correct.
- **Map-stage saturation is severe:** S1 reaches the 96-token cap in **327/338** section summaries (96.7%); S3 in **350/375** (93.3%). The receipts do not save the map-stage text, so individual section endings cannot be inspected. The frequent cap hits indicate likely information loss before final synthesis.
- Final visible output is shorter on average for S3 (195.3 re-encoded tokens) than S1 (228.3), although S3 is shorter in 10 cases and longer in 10. This is a descriptive feature of the generated outputs, not a controlled length-normalized comparison.
- Three S3 outputs visibly focus on closing remarks instead of the lecture topic: DOI `10.5446/16294` (thanks and next meeting, 76 visible tokens), `10.5446/38319` (generic sign-off, 45 tokens), and `10.5446/38638` (meeting logistics, 65 tokens). The first two S1 outputs cover symplectic field theory and architecture. The S1 output for `38638` instead discusses sugar addiction, obesity, and diabetes despite the lecture being about chromatography. This is a confirmed topic and factual-support failure in **both arms** for `38638`, not merely an S3 defect.
- The backend tokenizes the raw prompt directly and does not apply the instruct model's chat template. This is a plausible contributor to the prompt-like or meta-summary artifacts, but its causal effect has not been tested.

| DOI suffix | Source tokens | Chunks S1/S3 | Map cap hits S1/S3 | Final generated tokens S1/S3 | S3 − S1 ROUGE-L |
| --- | ---: | ---: | ---: | ---: | ---: |
| 45978 | 2595 | 6/6 | 6/6 | 267/221 | −0.0056 |
| 50943 | 13308 | 27/29 | 26/27 | 384/275 | +0.0023 |
| 46066 | 14951 | 30/32 | 29/30 | 182/384 | −0.0848 |
| 49509 | 3073 | 7/7 | 7/7 | 138/166 | −0.0081 |
| 16294 | 12957 | 26/29 | 25/28 | 288/78 | +0.0019 |
| 48908 | 2435 | 5/5 | 5/5 | 295/138 | +0.0061 |
| 38319 | 10233 | 20/22 | 18/22 | 142/46 | −0.0603 |
| 20846 | 11210 | 22/26 | 21/25 | 202/384 | −0.0414 |
| 38638 | 5125 | 11/12 | 11/12 | 225/67 | +0.0000 |
| 14078 | 8201 | 17/19 | 17/15 | 313/97 | +0.0864 |
| 55669 | 9892 | 20/23 | 20/20 | 109/143 | +0.0204 |
| 35254 | 8789 | 18/20 | 18/17 | 158/232 | −0.0249 |
| 19217 | 5026 | 10/12 | 10/11 | 248/160 | +0.0012 |
| 18890 | 8022 | 16/18 | 16/16 | 147/261 | −0.0469 |
| 43747 | 10253 | 21/23 | 20/23 | 384/384 | −0.0001 |
| 15101 | 13606 | 27/30 | 25/26 | 202/166 | +0.0364 |
| 49247 | 1171 | 3/3 | 2/3 | 146/196 | −0.0062 |
| 50934 | 12711 | 25/27 | 24/27 | 178/187 | +0.0150 |
| 49452 | 3494 | 7/9 | 7/9 | 202/221 | +0.0014 |
| 20848 | 10154 | 20/23 | 20/21 | 384/123 | −0.0215 |

This is a real-LLM validation diagnostic using transcript text. ROUGE-L does not measure factual support, image content, audio waveform content, or human usefulness. V1 and v2 scores should not be pooled because the final-output budget changed and v1 had two failed cases.

## Source and reference review returned by user

The returned JSON declares the same `gigant/tib` revision, `valid` split, selection hash, and no test-content access as v2. It has 20 unique DOI records. Each record contains a title, creator abstract, transcript text with timestamps, source-word count, and source hash. Rejoining the transcript segments and recomputing all 20 source hashes matches the v2 `transcript_sha256` values exactly. Segment counts, ordered timestamps, and nonempty text are internally consistent. This confirms that the review file contains the **same text input used for v2**, but does not independently validate transcription accuracy against the audio/video.

Transcript length spans **882–12,131 words**. All 20 abstracts are present, but **9/20 have fewer than 30 words**. Their role is heterogeneous: lecture-specific content, course-series descriptions, speaker/event descriptions, and near-title text. Examples:

| DOI | Abstract words | Source/reference finding |
| --- | ---: | --- |
| `38638` | 3 | `Chromatographic separation; Chapters:` gives effectively no substantive summary target. The 4,102-word transcript repeatedly mentions chromatography (16 occurrences), stationary phase (15), and mobile phase (6); it mentions sugar twice only in unrelated context and does not mention diabetes or obesity. S1's sugar-health summary is unsupported. S3 reduces the lecture to closing logistics. ROUGE cannot expose either failure against this reference. |
| `14078` | 68 | Abstract describes Walter Lewin's MIT event and book signing rather than the actual physics demonstrations. Similarity to it may reward event details over lecture substance. |
| `19217`, `18890` | 39, 69 | Abstracts describe broad course topics, some beyond the particular lecture; weak targets for lecture-specific coverage. |
| `43747` | 11 | Speaker plus talk title; too little detail to assess a full summary by lexical match. |
| `38319` | 89 | Mixes speaker/event biography with collective-housing lecture content; only part is a content reference. S3 captures a generic sign-off despite the source discussing architecture/housing. |
| `50943`, `55669` | 95, 122 | Mini-course or series descriptions; topical, but may describe more than the individual recorded lecture. |
| `46066` | 105 | Detailed Pompeii architecture reference. Both outputs emphasize eruption/excavation and underrepresent civic, commercial, and religious buildings; this is a content-coverage concern, not a verified falsehood. |
| `45978`, `20846`, `20848` | 74, 81, 165 | Relatively detailed and focused topic descriptions; useful stronger reference examples for a pilot. |
| `49509`, `48908`, `49452` | 19, 22, 14 | Brief descriptions of Gothic, Ancient Greek, and Old Church Slavonic language topics; topical, but limited coverage targets. |
| `16294` | 15 | Lists Polyfold/Symplectic Field Theory subtopics; topical, but too short to represent the full 10,415-word transcript. S3 discusses only thanks and the next meeting. |
| `35254` | 13 | Names cotangent complexes, derivations, obstruction theory, and mapping spaces; topical keywords rather than a developed summary. |
| `15101` | 23 | Names the lecture's quantum field theory and particle-operator topics; concise, reasonably lecture-specific. |
| `49247` | 22 | Notes an Old Irish text sample, but gives little content detail; the generated summaries introduce German, absent from the source text. |
| `50934` | 73 | Noncommutative-conjectures course overview; topical, with possible series-level scope. |

Two other output/source checks distinguish generation from transcript noise. In `35254`, the strings `Harki...` and `TGVF` occur in the transcript, so their appearance in S3 is partly propagation of source transcription noise; its expansion of `TGVF` as a French television organization is not supported by the abstract or transcript. In `50943`, `Hawkshield` and `k-fury` likewise occur in the transcript and appear to be source-level term errors. In `49247`, neither abstract nor transcript mentions German, yet both summaries introduce German grammar. These are descriptive spot checks, not a systematic factuality score.

The returned source file resolves the prior data-linkage question. It does **not** turn all 20 abstracts into equally valid gold summaries or establish visual/audio coverage. For this cohort, report ROUGE as an exploratory proxy; add source-grounded checks for topicality, central-idea coverage, and unsupported claims, with error examples tied to DOI and transcript spans. Keep reference limitations visible per item rather than silently removing inconvenient cases.

The dataset card itself notes that author-provided abstracts vary in style, length, quality, and content; some resemble titles or speaker introductions rather than lecture summaries: https://huggingface.co/datasets/gigant/tib/blob/main/README.md. This supports treating the abstract as a noisy reference proxy.

## Decision

V2 is a complete and internally consistent real-LLM validation diagnostic. It does not support a claim that S3 improves summarization. The severe map-stage cap saturation and weak syntheses make a clean segmentation-effect claim premature. The subsequent three-case pilot repairs prominent topic failures and greatly reduces map cap hits, while leaving some factual-support errors and one final truncation. Neither the v2 score nor the selected pilot score establishes a segmentation benefit. Choose and freeze one shared configuration, define the source-grounded error checks, and then run the paired full validation cohort; retain null or negative results transparently.

## Prepared next pilot

The historical chat-pilot notebook applied the tokenizer's chat template and 160 map / 512 final output-token caps to `38319`, `38638`, and `46066`; its notebook file was removed from the active workspace on 2026-10-07 at the user's request. The user returned `C:\Users\hung\Downloads\pilot_chat_90393cb1344f-20261002T094909Z-1-001.zip`; its seven members pass ZIP CRC, including a byte-identical copy of the 20-item source snapshot and three completed DOI receipts. Each pilot receipt recomputes its canonical receipt hash; all three source hashes, selection hashes, model IDs, and DOI identities match the corresponding v2 case. The manifest declares validation-only status and no sealed test-content access.

| DOI | v2 map cap hits S1/S3 | Pilot map cap hits S1/S3 | Pilot final cap | Direct source/output observation |
| --- | ---: | ---: | --- | --- |
| `38319` | 18/20; 22/22 | 3/20; 2/22 | Neither | Both arms now summarize urban housing/architecture instead of S3's former generic farewell. S3 gives more detail, but this is not a factuality rating. |
| `38638` | 11/11; 12/12 | 4/11; 4/12 | S1 at 512 | Both arms now discuss chromatography, correcting v2's unrelated sugar-health S1 and logistics-only S3. S1 ends mid-sentence. S3 incorrectly expands the transcript's *hydrophilic interaction chromatography* as *hydrophobic interaction chromatography (HIC)* and overgeneralizes how pH changes polarity. The three-word creator abstract remains unsuitable as a substantive lexical target. |
| `46066` | 29/30; 30/32 | 2/30; 6/32 | Neither | S3 now mentions Pompeii's forum, temples, and baths rather than only the eruption. S1 remains centered on the eruption. S3 also claims Pompeians rebuilt the city within seven years **after** the AD 79 eruption; the transcript describes **17 years of rebuilding after the AD 62 earthquake, before** the eruption. This is an unsupported chronology claim. |

Across these three fixed sources, map cap hits fell from **58/61 to 9/61** for S1 and **64/66 to 12/66** for S3. Chat formatting, instructions, and token cap changed together, so the pilot does not isolate which change caused the improvement. The saved pilot ROUGE-L S3−S1 mean is **−0.01481** over only three selected cases; it is a debugging signal, not an S1/S3 research estimate. The weak `38638` reference and the improved yet lower-ROUGE `46066` S3 illustrate why lexical overlap is insufficient for content correctness.

The manifest records `0.03–0.08 s` per DOI. The runner returns an existing validated receipt immediately when it finds one; these numbers are consistent with a resume pass and **must not be reported as model generation speed**. The ZIP proves the completed results exist, but does not contain the original GPU generation timings.

Local retrieval of `gigant/tib` failed with a network `ProxyError`; the user-supplied source snapshot now permits the text/reference review above. The Qwen model card demonstrates use of `tokenizer.apply_chat_template` for direct Transformers inference: https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct.

## Unresolved questions

- The pilot substantially reduces map truncation and repairs gross off-topic summaries, but `38638` S1 still hits the final cap and pilot S3 contains unsupported technical/chronology claims. Decide whether to make one small shared prompt/length revision before freezing, or freeze this recipe while explicitly evaluating those defects on the full validation cohort.
- Expand the source-grounded output check beyond these three cases, especially for exact claims and coverage in both arms. Decide whether the official report should use heterogeneous full-cohort ROUGE only as secondary evidence or present a clearly defined reference-quality sensitivity slice alongside it.
