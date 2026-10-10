# LVVO qualification follow-up — 2026-10-10

## Decision

**KEEP the 1,000 released frame annotations for EDA; HOLD every record for a formal source-grouped detection benchmark.** No labels, source images or old notebook outputs were changed. No detector, video decode or image decode ran in this follow-up. No split assignment or cohort was frozen.

New evidence links **39 of 139 author-defined video groups, covering 245 frames**, to MP4 paths explicitly present in public VideoPoints HTML. **100 groups remain without an observed public source match.** Public source paths are stronger evidence than inferred URLs, but do not establish that a released frame actually came from that media, that its timestamp matches, or that underlying video use is licensed.

## Checks actually executed

1. Recomputed SHA-256 for the retained author ZIP, executed EDA image ledger, prior per-image qualification ledger and prior video-group ledger; all matched their receipt. ZIP SHA-256: `f049217c51c45d532f394d7082e69da95397dee106fede1d743ff3dee80bf7cf`. This reused the prior complete 1,000-image decode and 1,580-box annotation audit without repeating it.
2. Read the official GitHub repository API, complete available commit list (four commits), recursive tree at revision `d53418d8846c5c08abf9cfa7380da8a4f16626ce`, pinned README and LICENSE. The tree is not truncated and contains examples, sample labels and LDD/LPM adaptation metadata, but no LVVO source-video mapping table. The initial `main` tree request returned 404; the API identifies `master`, and the subsequent pinned revision request succeeded. The 404 is not a repository-access blocker.
3. Retrieved the VideoPoints public home, series catalogue, research page and four course pages through links literally present in public HTML. All returned HTTP 200. Candidate course selection used equality between catalogue query hashes and MD5 of numeric course tokens **only as a search hypothesis**. A group was linked only when the fetched HTML itself contained both matching instructor and video tokens in a `<source>` MP4 path; hash equality alone never passed a group.
4. Saved per-request URL, final URL, status, response byte count, SHA-256, acquisition timestamp and raw response. Verified saved response hashes before deriving ledgers.
5. Recovered the first 20 displayed dHash candidate pairs from the executed notebook into an explicit historical queue. No full perceptual pair recomputation or visual adjudication ran. The complete 313-pair queue was not persisted by the original notebook, so those aggregate counts remain historical evidence rather than a newly reproduced all-pair result.

## Accounting and endpoint scope

| Unit | Selected | Observed | Label-valid | Media-valid | Evaluated | Failed |
|---|---:|---:|---:|---:|---:|---:|
| Released JPG/JSON pairs | 1,000 | 1,000 | 1,000 | 1,000 prior decoded JPGs | 0 | 0 prior frame/label read failures |
| Author-defined source groups | 139 | 139 tokens | Not applicable | 0 source video streams decoded | 0 | Not an attempted full-media census |

The new image ledger has **1,000 HOLD** decisions for the scientific endpoint and a separate **KEEP EDA annotation** decision. This preserves usable frame evidence without claiming benchmark qualification. There were no new annotation repair or exclusion decisions. `media-valid=1,000` refers to released JPG files only; it does not apply to 139 videos. The old labels have all been observed, so future partitions can at most be called model-held-out with references previously inspected.

### Source mapping recovered

| Author course token | Public HTML groups matched | Evidence |
|---|---:|---|
| c328 | 7 | Observed instructor/video paths in course page |
| c332 | 6 | Observed instructor/video paths in course page |
| c390 | 15 | Observed instructor/video paths in course page |
| c415 | 11 | Observed instructor/video paths in course page |
| Remaining nine courses | 0 | No matching course link found among the inspected public catalogues/pages |

For every matched group the ledger retains the public page URL, page hash and exact MP4 URL. The observed URL is not a successful HTTP/media availability probe, frame alignment check or verified creator attribution. Public catalogues may change; the raw responses preserve the evidence from this review. This bounded search cannot prove that the remaining videos are unavailable elsewhere.

## Rights, duplicate and leakage gates

The [pinned author LICENSE](https://github.com/dbiswas55/LVVO_dataset/blob/d53418d8846c5c08abf9cfa7380da8a4f16626ce/LICENSE.txt) explicitly applies CC BY 4.0 to the primary LVVO dataset made available through the author Drive link. The [pinned README](https://github.com/dbiswas55/LVVO_dataset/blob/d53418d8846c5c08abf9cfa7380da8a4f16626ce/README.md) identifies VideoPoints as the platform. These direct release statements support the stated image/annotation provenance. They do not supply per-video creator attribution or a permission trail for recovering and processing the underlying recordings. VideoPoints' “free for education use” site statement does not resolve that scope.

Historical EDA reported **zero exact-byte duplicate groups**, **313 nonidentical dHash pairs at distance ≤4**, including **257 cross-video-token pairs**. dHash is only a review signal. All 20 recovered displayed candidates remain HOLD; none was removed or merged automatically. Source-token disjointness alone cannot establish source independence while 100 source links and cross-token similarities remain unresolved.

The saved split design is **design only**, with zero assigned records. It requires verified source identities, reviewed duplicate must-link components, declared video/course/instructor generalization target, class coverage, fixed seed and metric denominators. Image-level random splitting is inappropriate. Ratios and roles remain unfrozen until these gates pass; all 139 groups stay unassigned.

## Files and reproducibility

- Script: `experiments/scripts/qualify_lvvo_followup.py`.
- Receipt: `experiments/outputs/dataset_qualification_261010/lvvo-qualification-receipt.json`.
- Per-ID ledger: `.../lvvo-id-ledger.csv` — 1,000 records.
- Source ledger: `.../lvvo-video-group-ledger.csv` — 139 records with the new 39 links and 100 unresolved groups.
- Historical candidate excerpt: `.../lvvo-historical-displayed-duplicate-pairs.csv` — 20 records, explicitly incomplete.
- Split design: `.../lvvo-provisional-split-design.json` — no assigned roles.
- Network proof register: `.../lvvo-network-probes.json`; raw `lvvo-github-*` and `lvvo-videopoints-*` responses in the same directory.

Run `python experiments/scripts/qualify_lvvo_followup.py` from the top workspace. It verifies retained evidence and saved network hashes; it does not download again or decode media. Existing qualification reports and notebook outputs remain historical source evidence. Ignored local outputs must accompany a handoff if the review is reproduced on another machine.

## Remaining blockers and narrow scope

1. Obtain or locate authoritative paths and attribution for the remaining 100 groups; check source-video availability and a declared sample of frame alignment. The new 39 links are a useful next-step subset, not 39 media-qualified videos.
2. Establish underlying recording use scope. No contact messages were sent to authors or VideoPoints.
3. Recover/recompute the full perceptual pair queue and review the 257 cross-token candidates against images and source identity before making grouping decisions. No duplicate is confirmed by this follow-up.
4. Freeze a source-group protocol only after that review. If these gates remain blocked, restrict claims to released-frame annotation EDA or a clearly qualified diagnostic endpoint. There is currently **no newly benchmark-qualified LVVO cohort**.

Unresolved questions: source and permission mapping for 100 groups; frame alignment for all linked groups; disposition of the complete duplicate queue; availability of new sealed references for an unseen-reference final test.
