# YTSeg locked resource: `MoEaRpLNo9A`

**Result: `hold`**, with technical media and sampled timeline checks passing. This resource is not D2 and was not used for model selection or official RQ1.

## Source and file

The [MIT OCW lecture page](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/resources/lecture-10-application-of-machine-learning-to-cardiac-imaging/) identifies Rahul Deo as speaker and links the MP4. The pinned YTSeg `text` train row is in `train-00001-of-00004.parquet`, row offset 3644. The pre-media CSV remains locked at SHA-256 `4DEDB0EFACECF547F1BF2EAC773A0B6CED3CEA9ED1330875CF6E9B493E9F0719`.

- Full publisher-linked MP4: **189,783,912 bytes**, matching HTTP `Content-Length`; SHA-256 `b65bdecc58df31a66705aa3e4a243db0a675bceea6aecd9ca8485193506e0eb0`.
- `ffprobe`: H.264 640×360 at 30000/1001 fps, AAC, embedded `mov_text`; duration **4882.068 s** versus YTSeg **4882.0 s**.
- `ffmpeg -xerror` full video/audio decode passed. `ffprobe -show_frames` found **146,315 video frames**, **228,847 audio frames**, zero best-effort PTS regressions, and last timestamps 4882.010467/4882.046667 s.
- MP4 is stored locally under ignored `experiments/datasets/ytseg_qualification/`; media and transcript were not published.

## Timeline checks

The pinned row has 10 `raw_chapters` starting at **0, 922, 1155, 1833, 2119, 2344, 3009, 3215, 3680, 4197 s**, ending at 4882 s. It has 10 titles and 9 timestamp entries. This is the released structure; no lists were zipped or labels changed.

At fixed **10%, 50%, 90%** positions and all nine internal chapter starts, embedded caption text in ±12 s windows matched the pinned `text_ref` by exact normalized six-token windows: **77/77, 87/87, 62/62** at the fixed positions and **79/79, 70/70, 89/89, 81/81, 84/84, 75/75, 78/78, 66/66, 52/52** at chapter starts. Locally cached `tiny.en` independently transcribed 20-second audio at the three fixed positions; speech content agreed with the captions (EKG conduction, cardiologist review of imaging, handheld ultrasound). These checks support source identity and sampled timeline. Captions may themselves be the source of YTSeg `text_ref`; chapter-title semantics were not exhaustively adjudicated. Full decoding plus near-equal duration alone would not establish timeline identity.

## Rights and decision

[MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) state CC BY-NC-SA 4.0 terms and conditions for AI training. The [official slides for this lecture](https://ocw.mit.edu/courses/6-s897-machine-learning-for-healthcare-spring-2019/4714b64e996e834409e4abab3628ebd7_MIT6_S897S19_lec10.pdf) explicitly label third-party images/logos **all rights reserved and excluded from the Creative Commons license** on many pages, including 0, 3–7, 9, and 11. Component-level permission for the video was not established. Thus `hold_rights`. Upstream GT conversion code provenance remains `hold_gt`. Overall resource status is **hold**.

Machine-readable methods, counts, and outcomes: [receipt](./ytseg-260929-1543-moea-media-receipt.json).

## Unresolved questions

1. Can the video’s excluded third-party visual components be identified and lawfully used for the proposed evaluation scope?
2. Can upstream GT conversion code, or a documented protocol decision accepting direct released `raw_chapters`, resolve `hold_gt`?
