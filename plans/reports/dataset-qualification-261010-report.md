# Dataset qualification: seven executed EDA notebooks

Review date: 2026-10-10. Scope: TED-LIUM → IIIT-CVID → LVVO → MLPDataset → AccessMath → LectureMath → EduVidQA. This is a qualification follow-up, not a new benchmark. No GPU or model inference ran. Original data and historical outputs were preserved.

## Current conclusion

**Research-scope clarification:** the no-freeze conclusion below concerns the previously proposed scientific endpoints. It does not mean these datasets cannot answer narrower research questions. Use the [claim-scoped qualification matrix](research-scope-261010-1621-claim-qualification-report.md): static OCR/detection comparisons need their released images and labels, text-only abstract agreement needs text, while video transition/extraction requires aligned media. Source-video and unseen-generalization gates apply only where the claim requires them. No new cohort was frozen by this clarification.

**Scientific benchmark cohorts approved by this review: none.** There is substantial usable EDA evidence, but source identity, alignment, target-label semantics or source-group review still blocks each requested scientific endpoint. No cohort or evaluation protocol was frozen. Native test references inspected during research are observed references; a later model-held-out partition must disclose that fact.

The only immediately interpretable retained ASR subset is **42/50 diagnostic candidates** with released scored references. This is a historical, nonrepresentative sample, not a newly approved full-corpus benchmark. No new scores were generated.

## Accounting

Numbers refer to each row's declared unit, not interchangeable media or model-evaluation totals.

| Dataset / unit | selected | observed | label-valid | media-valid | evaluated | failed record reads |
|---|---:|---:|---:|---:|---:|---:|
| TED-LIUM / retained utterance | 50 | 50 | 42 | 50 WAVs, prior decode reused | 0 | 0 |
| IIIT-CVID / frame + XML | 5,475 | 5,475 | 5,455 | 5,475 PNGs decoded now | 0 | 0 |
| LVVO / released frame + label | 1,000 | 1,000 | 1,000 | 1,000 JPGs, prior decode reused | 0 | 0 |
| MLPDataset / source-video row | 333 | 333 | 315 | 0 source-aligned videos | 0 | 0 |
| AccessMath / annotated video | 12 | 12 | 11 | 0 source-aligned videos | 0 | 0 |
| LectureMath / annotated video | 34 | 34 | 34 | 0 source-aligned videos | 0 | 0 |
| EduVidQA / physical QA row | 5,234 | 5,234 | 5,234 | 0 rows with qualified source context | 0 | 0 |

Label-valid means the recorded structural checks passed: geometry/nonblank labels for OCR; released box checks for LVVO; complete QA fields for EduVidQA. It is not verified task-GT accuracy. AccessMath/LectureMath historical decoded PNG totals are 130/330; they do not qualify original source videos. LVVO source-video media-valid is also zero. Zero failed record reads excludes the separately logged malformed auxiliary dental JSON, **three failed clip downloads (HTTP 403)** and **one failed sampled transcript request (ParseError)**. HOLD is not counted as a processing failure. No historical benchmark totals have been relabeled as evaluations in this review.

## Evidence and decisions by dataset

| Dataset | Newly established | Decisions / remaining HOLD |
|---|---|---|
| TED-LIUM | Rehashed all 50 retained WAVs and unit metadata. All eight invalid references are `ignore_time_segment_in_scoring`; four test IDs are inter-segment gaps. Exact builder media-host URL and LIUM API return 401. | 42 KEEP for bounded diagnostic reference use; eight EXCLUDE from scored ASR. Missing Arrow and upstream identity prevent full-corpus qualification. No new full-media audit. |
| IIIT-CVID | Full ZIP still local: verified archive hash and decoded train 3,171 / val 549 / test 1,755. Saved all 22 box issues, 124 dimension mismatches and 469 cross-split pairs. | 5,335 structural KEEP, 120 derived-dimension REPAIR, 20 frame HOLD. Four of 124 mismatches overlap invalid geometry. All 469 perceptual pairs remain unresolved; zero exact-byte matches is not proof of independence. |
| LVVO | Hash-verified historical 1,000-frame evidence; pinned author CC BY 4.0 release statement. Public HTML directly links 39/139 groups, covering 245 frames, to MP4 paths. | All scientific-endpoint records HOLD. Remaining 100 groups lack observed mappings; linked videos lack frame-alignment and underlying-rights verification. Historical 257 cross-token dHash pairs unresolved. Grouped split design saved; zero assigned roles. |
| MLPDataset | Complete 333-video and 9,021-boundary ledgers; anomalies tied to IDs and original order. Sample metadata available. | 315 structurally valid videos still HOLD for media/alignment/rights. Six empty files, 15 non-increasing marks, one absent folder and malformed dental JSON preserved. No sorting or invented transitions. |
| AccessMath | 12-video, 129-keyframe and interval ledgers. Official LectureMath metadata supplies 12 title/source-link bridge candidates. | Orphan `lecture_08/62553` PNG remains HOLD. Original videos omitted from release. Multipart camera/edit clock and required-state semantics unverified. |
| LectureMath | 34-video/330-keyframe ledgers. Pinned author code establishes `AbsTime` in milliseconds; derived seconds retain raw time and source proof. | Original-media alignment, 14 edited-video clocks, eight cross-split SourceID groups and 33 historical perceptual candidates require review. Thirty identified candidate pairs recovered; three remain unenumerated. |
| EduVidQA | All 5,234 QA IDs and 296 groups hash-verified. Six sampled three-part timestamps contradict HH:MM:SS against a 1,636-second video duration. | All 456 three-part times retain original values; no global conversion. 1,038 synthetic-test times are blank. Transcript/media alignment and independent retrieval-evidence GT absent. |

### Direct, reused and historical evidence

- **Direct in this follow-up:** immutable-file hashes; full OCR frame/XML decoding and coordinates; complete metadata/annotation ledgers; saved official repository/code/page responses; 39 LVVO public-path matches; three successful source metadata probes; three bounded clip failures and one transcript failure; author-code millisecond derivation; six sampled EduVidQA duration contradictions.
- **Reused after checking source identity:** previous 50 TED waveform decodes, 1,000 LVVO frame decodes, 130 AccessMath and 330 LectureMath PNG decodes. These were not repeated.
- **Historical only:** TED's 270,323-row aggregate and missing Arrow coordinates; old benchmark scores; LVVO 313 perceptual candidates including 257 cross-token pairs; LectureMath 33 perceptual pairs. Only the originally displayed 20 LVVO / 30 LectureMath pair IDs were recoverable without recomputing signatures. The missing candidate lists are explicitly incomplete.
- **Superseded:** the claim that IIIT-CVID train/test were absent locally; the claim that all LVVO video tokens had no observed source paths; unresolved board `AbsTime` units. Preserve the old outputs as dated evidence, not current conclusions.

### Leakage and split review

TED retained validation/test talk groups are disjoint, without any inference about missing train data or model pretraining. OCR folder-derived lecture groups are disjoint across splits; real video identity and perceptual candidates are unresolved. LVVO has no assigned split. MLP has no official task split. LectureMath's SourceID overlap is a course/creator dependence signal, not automatic evidence of repeated videos. The 12 AccessMath–LectureMath title/source bridge candidates prevent claiming those datasets independent until original cameras/edits are checked. EduVidQA video IDs are disjoint across splits; course/channel/content dependence is unverified.

No image-level random split, source-group exception, artificial GT or final-test holdout was introduced. Freeze requires reviewed identity and duplicate components, target-matching labels, source media/timebase evidence, declared metric denominators and explicit reference-exposure limits.

## Files changed and evidence locations

### Seven notebooks updated in place

Each receives one executed qualification cell and one explanatory markdown cell. **All 80 pre-existing cells are byte-content equivalent in serialized JSON**, including prior outputs; only additive review sections were written.

- [TED-LIUM](../../experiments/notebooks/diagnostics/tedlium3-full-corpus-asr-eda.ipynb)
- [IIIT-CVID](../../experiments/notebooks/diagnostics/iiit-cvid-validation-ocr-eda.ipynb)
- [LVVO](../../experiments/notebooks/diagnostics/lvvo-four-class-detection-eda.ipynb)
- [MLPDataset](../../experiments/notebooks/diagnostics/mlpdataset-slide-transition-eda.ipynb)
- [AccessMath](../../experiments/notebooks/diagnostics/accessmath-board-annotations-eda.ipynb)
- [LectureMath](../../experiments/notebooks/diagnostics/lecturemath-keyframe-annotations-eda.ipynb)
- [EduVidQA](../../experiments/notebooks/diagnostics/eduvidqa-official-annotations-eda.ipynb)

The cells verify saved receipt/artifact hashes, show accounting, decision details and ledger samples, and expose full local ledger paths. OCR includes the 20-frame geometry contact sheet. Embedded receipt snapshots keep the conclusion visible if local files are missing, explicitly marked historical rather than a fresh audit.

### Registers and reports

- [Notebook manifest](../../experiments/notebooks/notebook_manifest.yaml): seven EDA inventory entries; official benchmark execution list remains empty.
- [Qualification register](../../experiments/registry/datasets/qualification-261010.json): portable receipt snapshots and hashes, no frozen cohort.
- [TED D2 registry](../../experiments/registry/datasets/tedlium3_d2.yaml): original source currently unavailable; historical pilot estimates retained with current HOLD override.
- [EDA guide](../../docs/DATASET_EDA.md), [README](../../README.md), [dataset manifest](../../plans/260901-unified-scientific-benchmark/framework/01-dataset-manifest.md) and [decision log](../../plans/260901-unified-scientific-benchmark/framework/decisions-log.md): current evidence and superseded claims recorded.
- Detailed reports: [TED/OCR](tedlium-cvid-followup-261010-report.md), [LVVO](lvvo-followup-261010-report.md), [remaining four](remaining-datasets-followup-261010-report.md).
- [Local evidence directory](../../experiments/outputs/dataset_qualification_261010): seven receipts, per-ID decisions, anomalies, dimension overrides, source bridges/groups, duplicate excerpts/full OCR queue, HTTP/source/clip logs and verification receipt. This directory is ignored local evidence; carry it separately when moving to Colab or another machine.

### Scripts added

Under `experiments/scripts/`: `dataset_qualification_io.py`, `qualification_visual_pairs.py`, `qualify_tedlium_followup.py`, `qualify_iiit_cvid_followup.py`, `adjudicate_cvid_metadata.py`, `qualify_lvvo_followup.py`, `qualify_remaining_datasets_followup.py`, `probe_remaining_dataset_sources.py`, `finalize_remaining_dataset_review.py`, `probe_eduvidqa_sample_transcript.py`, `integrate_qualification_notebooks.py`, `verify_qualification_followup.py`. Scripts consume real source artifacts; no benchmark runner was launched.

## Verification actually run

- TED receipt and all retained media SHA-256 checks; marker classification and group intersection.
- Full OCR ZIP identity, 5,475 PNG decodes and XML parses; 22 box checks; 124 dimensions; complete cross-split dHash screening; derived overrides and 20-frame visual review.
- LVVO archive/ledger SHA-256 checks, pinned repository/rights/public-page probes, 39 exact public-path matches and uniqueness checks.
- Four ordered metadata audits; official pinned-source probes; bounded yt-dlp metadata and clip attempts; sampled transcript attempt; board author-code time units and cross-dataset bridge review.
- New qualification cells executed in-process with IPython rich outputs. The initial separate-kernel launch did not complete and was stopped; it produced no qualification evidence. Historical EDA cells were not rerun.
- `python -m experiments.scripts.verify_qualification_followup`: **PASS**, seven notebooks valid, all 80 original cells preserved, seven new review cells executed, **38 artifact hashes** plus receipt snapshots and ledger row/ID/decision accounting verified. This integrity check does not convert HOLD into a media/GT pass.
- Python syntax checks for newly added scripts. No model inference, new score generation or full-corpus video/audio decode.

## Next bounded actions and unresolved questions

1. TED: obtain the original Arrow or an authorized exact source recovery; compare identities before selecting a new representative ASR cohort. Do not relabel the 42-item diagnostic as full-corpus evidence.
2. OCR: resolve author coordinate convention and review source identity/content for all 469 candidate pairs. The 120 dimension overrides are ready as derived metadata, not a license to freeze the cohort.
3. LVVO: verify media/rights/alignment on linked groups; locate the remaining 100 sources; recover the full pair queue when required for review. Then assign source-group splits and declare observed-reference limits.
4. MLP and boards: recover media in an authorized working download environment, inspect anomaly IDs and edited/multipart clocks, and evaluate only released-label tasks that match their semantics. If media remains unavailable, report annotation diagnostics only.
5. EduVidQA: confirm timestamp syntax from source generation or aligned transcript/media; preserve the six contradictions as examples. Answer agreement requires qualified source context; retrieval quality requires independent evidence-span/relevance labels. No replacement dataset is presented as qualified without its own evidence review.

No remote messages were sent. No commit or push was performed. Unrelated existing worktree edits were preserved.
