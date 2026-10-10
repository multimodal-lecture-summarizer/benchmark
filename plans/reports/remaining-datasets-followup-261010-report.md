# MLPDataset, AccessMath, LectureMath and EduVidQA qualification follow-up

Date: 2026-10-10. Requested order followed after LVVO source-mapping HOLD: MLPDataset → AccessMath → LectureMath → EduVidQA. No model inference, GPU processing, benchmark, cohort freeze or original-label change.

## Counts and decisions

| Dataset | Unit | Selected | Observed | Label-valid, structural only | Media-valid for target endpoint | Evaluated | Failed record reads | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---|
| MLPDataset | Released source-video row | 333 | 333 | 315 | 0 | 0 | 0 | HOLD, all 333 |
| AccessMath | Annotated video | 12 | 12 | 11 | 0 | 0 | 0 | HOLD, all 12 |
| LectureMath | Annotated video | 34 | 34 | 34 | 0 | 0 | 0 | HOLD, all 34 |
| EduVidQA | Physical QA CSV row | 5,234 | 5,234 | 5,234 | 0 | 0 | 0 | HOLD, all 5,234 |

Observed means metadata/annotation was read, not original media observed. Label-valid here means the declared structural checks passed; it is not a claim of verified task GT. Failed counts are record-parser failures, not HOLD records or media-acquisition failures. Auxiliary dental JSON has one parse failure, separately recorded. Three bounded clip downloads failed HTTP 403; the sampled transcript retrieval failed with XML ParseError. Those attempts are reported separately from dataset-record counts.

Per-ID ledgers and receipts are in `experiments/outputs/dataset_qualification_261010/`. Every scientific-endpoint row includes HOLD and an explicit reason. Original labels and prior EDA outputs remain intact. All native test references inspected during EDA are observed research material, not unseen holdouts.

## New direct evidence and reused historical evidence

Rehashed the official cached archives against pinned SHA-256 and reparsed metadata only. Reused the executed notebook's previous PNG-decoding and perceptual-hash evidence; no full image-decoding rerun. Explicitly exported the historical decision JSON from each board notebook with its original counts. Current follow-up does not claim that an original video was decoded.

| Archive | SHA-256 |
|---|---|
| MLP `mlp_anon.zip` | `dbd07ef37de603a22abb7be7d81245034b3c487f4878227cbef36ae3d451cfa7` |
| AccessMath author release | `7bffabf04ecf5ee5c03fb36089dba81bbef8c6a0f310002207df6ed51bfd9fee` |
| LectureMath author release | `cf0129f4d71a21d7be9b43f71d184e6b711d76375855d873e75636472ca72f45` |

The current LectureMath author revision `245d58a20393166addacb9ece75326ef3455b16f` returned HTTP 200. Its database metadata SHA-256 equals the cached EDA pin `e67d3e90b8d06658af09cacf1c022560d8bb0d83550a534c02f22bfda7cad834`. Pinned README, database, edited-video flags, complete repository tree, annotation code and TimeHelper code were saved with URL/status/response SHA-256. This pins previously branch-addressed metadata without replacing the historical source files.

### MLPDataset

- Persisted 333 source-video decisions and all 9,021 boundary rows, including original order, annotation-member path/hash and source URL.
- Confirmed 332 annotation folders, one missing source ID `aXxRSrIcGjU`, six empty boundary files and 15 nonincreasing boundary records. Combined per-video structural qualification is 315/333. No sorting, deduplication or boundary repair was applied.
- Persisted malformed `data/dental/dental.json`: line 5,120,653, column 15. This affects the conversation JSON endpoint; independently parsed `segments.txt` boundaries remain separately accounted for. The malformed JSON is not silently used as transition GT.
- Deterministic first sorted released source `-8QB3Rbeqoc`: normal yt-dlp metadata acquisition succeeded, duration 819 s, title “Oral Medicine | ASA Classification | INBDE”. Media license field absent. A bounded 0–20 s low-resolution MP4 acquisition failed HTTP 403 at the media server. No frame inspection or boundary alignment occurred.
- No official split exists in the inspected package. Source-video IDs are retained as groups, but course/speaker dependence and a split require review before assignment. No leakage-safe split is claimed.

Permitted scope now: annotation inventory, anomaly statistics and source-access diagnostics. Transition boundary F1 remains HOLD. Future review should acquire the 11 videos containing the 15 nonincreasing records and the six empty annotation sources; compare author order against source frames before any derived rule. No general-domain replacement was selected because it would change the lecture-slide endpoint.

### AccessMath

- Persisted 12 video rows, 129 XML keyframe records and all segment intervals. There are 130 released PNGs. `lecture_08` has orphan PNG frame `62553`; retained HOLD rather than invented XML label or deletion.
- The archive's `data/lectures/info.txt` explicitly says original videos were omitted due size. Segment XML contains multipart local camera paths, not downloadable URLs.
- Historical EDA decoded 130/130 PNGs, found zero read failures, zero cross-split exact duplicate groups and zero dHash candidates at the historical threshold. These historical facts are retained; missing source URLs do not establish independent source groups.
- Official LectureMath metadata provides a title-linked candidate media URL for every one of the 12 AccessMath IDs. This is stronger than inferring from an ID prefix, but exact camera, concatenation and clock equivalence remain unverified.
- The sampled `nm_lecture_01` bridge points to `6arlCAT3Hb4`, metadata duration 1,508 s, title “AccessMath - NM Lecture 01”, with platform metadata declaring Creative Commons Attribution. This declaration applies to that sampled video; it does not establish rights for all videos or annotation redistribution. A 0–20 s media attempt failed HTTP 403.

Permitted scope now: released keyframe/segment and board-image annotation diagnostics. Original-video keyframe extraction and required-board-state evaluation remain HOLD until camera/timebase alignment and required-state semantics are verified. A guessed legacy project-page URL returned 404; this does not prove the official dataset resource is unavailable.

### LectureMath

- Persisted 34 video rows, 330 keyframe rows and all segment intervals. All 34 pass inspected structural checks; 14 carry the author's edited-video flag.
- Verified `AbsTime` units from pinned author code: `KeyFrameAnnotation.LoadExportedKeyframes` reads `AbsTime` into `frame_time`; `self.time` is passed to `TimeHelper.stampToStr`, which explicitly takes milliseconds. Added `derived_time_s = AbsTime / 1000`, preserving raw values/frame indices. This resolves the unit ambiguity, not alignment to a remotely recovered video or edited timeline.
- Historical EDA decoded 330/330 PNGs without failures, found no exact duplicate groups, and flagged 33 cross-split dHash candidate pairs over nine video IDs. Saved all 30 historically displayed identified pairs. Three pairs were not persisted in the original notebook display; they remain explicitly unenumerated. No duplicate verdict or automatic exclusion is claimed, and no image rerun was launched merely to recreate the display.
- Eight released SourceID groups occur across train/test: `00000`, `00005`, `00008`, `00009`, `00010`, `00011`, `00012`, `00013`. Exact source-video URLs are disjoint in the historical audit, but creator/course dependence remains a leakage review signal. SourceID is not misrepresented as exact video identity.
- Author documentation and code support extractive summaries, segments, handwritten-content annotations and keyframes. They do not by themselves establish the application's independently specified required-board-state GT.

Permitted scope now: released keyframe/handwriting annotation diagnostics, or a task explicitly matched to the author's summary evaluation after media/timebase qualification. Required-state benchmark remains HOLD.

### AccessMath ↔ LectureMath dependence

`accessmath-lecturemath-source-bridge-ledger.csv` links 12 AccessMath IDs to exact released LectureMath titles/URLs. Every bridge retains both original split names and HOLD status. Treat these as potential shared source material; do not pool the datasets as independent train/test sources. The matching titles do not prove source-camera pixels or multipart concatenation clocks coincide. No cross-dataset leakage was “fixed” by relabeling a split.

### EduVidQA

- Reverified three pinned CSV hashes and persisted all 5,234 physical QA-row IDs plus 296 source-video groups. No answer text was exported into the follow-up ledger; normalized question hashes allow exact leakage inspection.
- Confirmed 456 unresolved three-component timestamps and 1,038 blank synthetic-test timestamps. All QA content-field checks pass, which does not make all timestamps valid.
- Deterministic sampled source `-Lw8isQCi4g` returned metadata duration 1,636 s and title “Lecture 4 : Recurrence of Merge Sort”. Six source rows (`synthetic_train:507`–`512`) have three-component timestamps.
- HH:MM:SS is contradicted for all six sampled rows: e.g. `25:27:00` would mean 91,620 s, exceeding observed duration. A minutes:seconds:fraction hypothesis gives 1,527 s and is within duration, but range consistency is not proof of interpretation. No global conversion was applied.
- The pinned author repository exposes evaluation scripts, not a timestamp generation/parser implementation. It recommends yt-dlp and youtube-transcript-api. A bounded 0–20 s download failed HTTP 403; the recommended transcript API returned `ParseError: no element found`. No frame/transcript alignment occurred.
- Video-ID groups have no exact cross-split intersection. Course/channel/content independence remains unverified. The release lacks independent retrieval relevance/evidence-span labels. No synthetic transition markers or QA timestamps were promoted into retrieval GT.

Permitted scope now: released annotation/answer-agreement diagnostics once source context is qualified, not retrieval evidence-quality conclusions. Retrieval benchmark remains HOLD. A replacement would require independently annotated lecture evidence spans; none was asserted qualified in this run.

## Scripts, evidence and checks actually run

New scripts under `experiments/scripts/`:

- `qualify_remaining_datasets_followup.py`: four ordered archive/CSV metadata audits, per-ID/segment/boundary/keyframe/source-group ledgers and receipts.
- `probe_remaining_dataset_sources.py`: pinned author resource probes, three deterministic metadata probes and three bounded 0–20 s acquisition attempts.
- `finalize_remaining_dataset_review.py`: author-code time-unit derivation, cross-dataset source bridges, historical duplicate queue export and sampled timestamp hypothesis review.
- `probe_eduvidqa_sample_transcript.py`: one bounded author-recommended transcript attempt and receipt.

Executed all four scripts. `python -m py_compile` passed for all four. Finalizer checked every referenced artifact SHA-256 for all four dataset receipts. Read-only archive hashing and metadata parsing; no original data edits. No benchmark or cohort freeze. No scientific cohort among these four is eligible yet.

Reports/receipts are additive; prior notebook evidence remains historical. Root integration owns notebook appendices, manifest and decision-log updates.

## Unresolved questions

1. Can an authorized normal media download environment recover the sampled videos beyond metadata, then validate cameras, edits and multipart timebase?
2. Does the author confirm the three-part EduVidQA timestamp serialization? Six samples reject HH:MM:SS, but do not establish a corpus-wide conversion.
3. Can the missing three historical LectureMath dHash pair IDs be recovered from an external signature receipt? If not, a narrowly scoped 330-PNG signature recreation is needed before complete pair adjudication.
4. Which released board-label semantics, if any, match the required-state endpoint? Until verified, retain the narrower released-summary/handwriting endpoint and HOLD the broader claim.
