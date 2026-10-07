# YTSeg MIT 16.687 reserve A: full-media qualification

**Scope:** Three locked TRAIN reserve IDs, all in course `mit-16.687-iap-2019` and the same lecturer group. They add no independent group. Source is pinned `retkowski/ytseg` revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970`; locked cohort CSV SHA-256 `4DEDB0EFACECF547F1BF2EAC773A0B6CED3CEA9ED1330875CF6E9B493E9F0719`.

| ID / publisher page | Official MP4 | Bytes received / declared | SHA-256 | Full decode / PTS | Six alignment points |
|---|---|---:|---|---|---|
| [`3sB64Au76h0`](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-12-aircraft-performance/) | `MIT16_687IAP19_lec12_300k.mp4` | 155,177,690 / 155,177,690 | `4e0c3d2e86366585acf497e83e5ba618403fa95dad232e4640ef06565d2647f2` | pass; 117,838 video / 184,307 audio frames, no PTS regressions | pass ([receipt](./ytseg-260929-1543-reserve-a-3sB64Au76h0-receipt.json)) |
| [`Th2N_rDfkDw`](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-7-navigation/) | `MIT16_687IAP19_lec07_300k.mp4` | 99,442,554 / 99,442,554 | `46a203a37f6e364871a5c51e692cdd71279f2d69b79c69bda250b74636027415` | pass; 75,371 video / 117,886 audio frames, no PTS regressions | pass ([receipt](./ytseg-260929-1543-reserve-a-Th2N_rDfkDw-receipt.json)) |
| [`alLh1Jdqwvg`](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-10-communication-and-flight-information/) | `MIT16_687IAP19_lec10_300k.mp4` | 86,983,502 / 86,983,502 | `ec070d8d4abc1f41e6db71f562390136ac9f1fceec9c26cf1eb1909aba639f55` | pass; 65,119 video / 101,852 audio frames, no PTS regressions | pass ([receipt](./ytseg-260929-1543-reserve-a-alLh1Jdqwvg-receipt.json)) |

Each publisher page contains the exact YouTube ID and links the Archive MP4 shown. Files were downloaded in full to ignored `experiments/datasets/ytseg_qualification/`. `ffmpeg -xerror` decoded the entire main video and audio streams with exit 0; `ffprobe -show_frames` found no backward video or audio timestamp steps. Container durations were 3,931.882 / 2,514.900 / 2,172.842 s, against pinned YTSeg 3,932 / 2,515 / 2,173 s. Near-equal durations were treated only as a preliminary check.

At 10%, 50%, and 90%, and eight seconds after the first, middle, and last internal `raw_chapters` starts, embedded subtitle cues matched pinned `text_ref` with six-word sequence coverage **100% at all 18 points**. Their positions in the full pinned transcript tracked playback position; the first/middle/last boundary topics were respectively performance importance / service ceiling / questions, navigation outline / ADF / navigation mistakes, and transponder / phonetic alphabet / advisory circular. This is concrete sampled content and timeline alignment. Captions may be the source of YTSeg `text_ref`; the comparison is not an independent audio transcription. Six points per video do not prove every boundary. Full transcript text was removed from the report workspace after computing the hashes and coverage; receipts include no extended excerpts.

**Decision:** All three pass the *technical media* gate. Overall each remains `hold_gt` because upstream GT conversion code is unavailable, and `hold_rights` because [MIT OCW terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/) do not alone establish whole-component reuse rights for every image, interface, and other third-party material appearing in the recordings. Content-level near-duplicate comparison against pilot media is pending at the cohort level. No model selection, derived split, D2 freeze, or official RQ1 run occurred.

## Unresolved questions

1. Can the released `raw_chapters` fields be formally accepted in a protocol amendment without upstream conversion code?
2. Are all components in these three recordings cleared for the intended study use?
3. Does cohort-level content fingerprinting rule out near duplicates with prior pilot lectures?
