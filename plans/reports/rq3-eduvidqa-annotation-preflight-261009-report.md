# RQ3 EduVidQA annotation preflight — 2026-10-09

## Decision

**QA annotations acquired; RQ3 retrieval benchmark remains HOLD.** The official release has questions, reference answers, source video URLs and a `timestamp` column, but no independently bounded evidence-span labels. Video and transcript bytes are not in the release checkout or the current benchmark dataset directory. Do not run Recall@k, name a retrieval winner, or interpret timestamp agreement as evidence retrieval accuracy. A later answer-only study is possible only after source media/transcripts, cohort EDA and a frozen QA scoring protocol qualify.

This is an annotation preflight, not executed task EDA or a model evaluation. RQ2 is outside this report. Existing RQ2 worktree changes were left alone.

## Source and reproducibility

- Official release: <https://github.com/sourjyadip/eduvidqa-emnlp25>, cloned at commit `aab6cc03e43182cc916f14ed2aca495f57a1ed96` into ignored local `research-data/eduvidqa-official/`.
- Research paper: <https://aclanthology.org/2025.emnlp-main.1760/>. The repository README places annotations in `data/`; it directs users to retrieve videos and transcripts separately.
- All three CSVs were read with Python `csv.DictReader` using UTF-8 BOM handling. Counts below are physical data rows, excluding headers. URL video IDs, split overlap, question hashes and field presence were checked programmatically. Test reference text was not printed or reviewed semantically; test rows were processed for structural counts, so this report makes no untouched-test claim.
- The local `UIAIC/EduViQA` snapshot is a separate dataset and was not mixed into these counts.

| Release file | QA rows | Distinct video IDs | Timestamp present | SHA-256 |
|---|---:|---:|---:|---|
| `synthetic_train.csv` | 3,909 | 157 | 3,909 | `3c6471d5c01b92a8092a8dcff367f701fbdd80b34f8b02f5c55e0e8ba0a971f5` |
| `synthetic_test.csv` | 1,056 | 40 | 18 | `0c44b89987ea1f112e5a46843036320132cebd111b37c1203591d31110c2bbaf` |
| `real_world_test.csv` | 269 | 99 | 269 | `2b8553dd454cb7038c914809a9c4e3908161955b243de97dc490493c8c092055` |
| **Total** | **5,234** | **296** | **4,196** | — |

All 5,234 rows have nonempty video ID, URL, question and answer fields. Every URL's `v` parameter matches its 11-character video ID. The three splits have zero overlapping video IDs and zero overlapping normalized-question SHA-256 hashes. These checks establish structural consistency, not semantic independence across courses or annotation quality. In `synthetic_train`, 419 timestamps have three colon-separated components; their meaning remains unresolved until the source media/transcripts can be checked. In `synthetic_test`, **1,038/1,056 timestamp cells are empty**.

The paper reports 5,252 QA pairs: 3,908 synthetic train, 1,074 synthetic test and 270 real-world test. The pinned release contains 18 fewer total: +1 train, −18 synthetic test and −1 real-world test. The discrepancy should be disclosed in any later result; do not silently substitute paper denominators for release denominators.

## Annotation meaning and eligible claims

The paper describes real-world answers as expert-corrected/verified and synthetic pairs as generated from NPTEL transcript documents with later checks. Real-world question timestamps were selected through expert review of video/transcript matches. Synthetic timestamps were assigned from transcript PDF key frames; a 100-sample manual check found mean absolute timestamp difference of 35.4 seconds. The authors used a four-minute context window around the timestamp, which is an input selection rule, not an independent ground-truth evidence interval. Sources: [paper, §3 and Appendix C](https://aclanthology.org/2025.emnlp-main.1760.pdf), [official README](https://github.com/sourjyadip/eduvidqa-emnlp25).

The CSV columns contain no evidence start/end, relevant chunk ID or judged retrieval relevance. The 269 real-world answers have stronger author-described verification than the synthetic answers, but this preflight did not independently adjudicate them. Token F1 against long-form answers would measure lexical agreement only; it should not be called factual correctness or grounding without an appropriate scoring study.

A metadata-only `yt-dlp --skip-download --list-subs` probe for one train video (`8jqKOqwOwA4`) failed with YouTube's “Sign in to confirm you’re not a bot” response. No subtitles or media were downloaded. This one failure does not estimate availability across 296 videos; the current CLI path has not established transcript access.

## Next executable gate

1. Acquire the source transcript and, for video-grounded claims, video for a declared cohort of EduVidQA video IDs. Record per-ID URL, source, rights/access, bytes or transcript revision, failures and alignment to the CSV timestamp. Do not infer full-corpus availability from URL metadata.
2. Execute task-specific EDA on the acquired cohort: source and split accounting, transcript/media decoding coverage, timestamp parsing and range, course/video duplicate groups, missingness, and visible tables/plots/anomalies. Keep test-answer inspection within a predeclared holdout policy.
3. Decide the target before evaluation. Answer-only QA can use the released answers after qualification. Retrieval Recall@k requires independently qualified relevance/evidence labels; timestamp-centered windows can be studied only as diagnostic proxies, with that limitation explicit. Freeze candidates, reader, scoring and compute budget before running comparisons.

## Unresolved questions

- Which EduVidQA video IDs have obtainable, versioned transcripts and media on this machine, and do their timestamps align?
- Can a source with independent evidence intervals or relevance judgments support RQ3 retrieval, or must the formal endpoint narrow to answer-only QA?
- Why do the pinned CSV row counts differ from the paper's reported counts?
