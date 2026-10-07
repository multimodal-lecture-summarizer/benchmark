# YTSeg `-dOX_4lI6HY`: full-file media qualification

**Result:** technical media `pass`; resource overall `hold_gt` + `hold_rights`. Not D2. [Machine receipt](./ytseg-260929-1543-dox-media-receipt.json).

The [MIT OCW lecture page](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-13-interpreting-weather-data/) links the [Archive MP4](https://archive.org/download/MIT16.687IAP19/MIT16_687IAP19_lec13_300k.mp4). Its publisher metadata names the course and instructors. Pinned YTSeg `text/train-00000-of-00004.parquet` at revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970` has one row for this ID.

Downloaded the complete publisher-linked file into ignored `experiments/datasets/ytseg_qualification/`. HTTP 200; received **123,297,321 / 123,297,321** declared bytes; SHA‑256 `6535760144bb69fbee50d8386c4f16a59e3a12634ed785d06264f68908c51a29`. `ffprobe`: H.264 640×360, AAC stereo 48 kHz, English subtitle tracks, 3,122.324 s versus YTSeg `duration=3122.0`. Full video and audio decode with `ffmpeg -xerror` exited 0. Decoded-frame PTS: 93,575 video and 146,359 audio frames, no backwards steps; endpoints at 3,122.252 and 3,122.303 s. The sole warning concerned an unmapped attached-picture stream without timescale.

Six **predefined** positions were checked against subtitle cues *inside the downloaded MP4*, YTSeg `text_ref`/`target_text_ref`, and sampled video frames:

| Position | Media evidence | YTSeg relation |
|---|---|---|
| 10%, 312 s | Turbulence AIRMET narration; weather application maps | Matching transcript; inside “Don't Despair, Use Softwair” |
| 50%, 1,561 s | Cloud cover on weather depiction chart; matching slide | Matching transcript; inside “Weather Depiction Chart” |
| 90%, 2,810 s | ADS-B weather feed narration; lecturer shown | Matching transcript; late in “HIWAS”, before next chapter |
| First internal boundary, 39 s | “Definitions” slide; VFR ceiling/visibility narration begins | Chapter and following YTSeg text align |
| Middle internal boundary, 1,508 s | “Weather Depiction Chart” slide and narration | Chapter and following YTSeg text align |
| Last internal boundary, 3,006 s | “Questions?” slide, coding magazine, then Q&A | Chapter and following YTSeg text align |

This establishes a concrete content and timeline match at those positions; matching duration alone was not used. Embedded captions and YTSeg text may share an upstream source, so the text comparison is **not independent transcription**. Six positions do not validate every boundary. No clip or subtitle text was published.

**Holds:** conversion code defining YTSeg's derived GT fields remains unavailable; raw chapter titles/milestones were not changed. The MP4 metadata claims CC BY-NC-SA 3.0, but sampled slides show third-party interface screenshots and a magazine cover. Whole-component rights and intended reuse are not established. Content-level comparison with prior pilot videos remains separate; prior exact-ID overlap of zero is insufficient. Do not count this resource toward N/G yet.

## Unresolved questions

1. Can upstream conversion code or a protocol amendment authorize the released `raw_chapters` interpretation?
2. Do this lecture's individual slide images, screenshots, and other components permit the planned study use?
3. Does content-level comparison with earlier pilot media rule out near duplicates?
