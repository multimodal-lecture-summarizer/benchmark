# YTSeg MIT 16.687 reserve B: full media audit

**Result:** technical media `pass` for all three locked TRAIN reserves; overall resource `hold_gt` + `hold_rights`. These lectures remain one course/lecturer group. [Machine receipt](./ytseg-260929-1543-reserve-b-media-receipt.json).

The MIT OCW resource pages identify and embed the exact YTSeg YouTube IDs and link to their corresponding Archive MP4s: [Lecture 16](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-16-seaplanes/), [Lecture 19](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-19-multi-engine-and-jets/), and [Lecture 21](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-21-weather-minimums-and-final-tips/). The files were downloaded in full into ignored `experiments/datasets/ytseg_qualification/`. All received byte counts equal Archive's declared size. Full mapped video/audio decoding exited 0 and frame PTS never went backward.

| YTSeg ID / lecture | Bytes | SHA-256 | MP4 / YTSeg seconds | Decoded video/audio frames |
|---|---:|---|---:|---:|
| `xsO2Ip6eiaY` / Seaplanes | 59,842,706 | `bfd2f8627a5b87590cf69322c6907556b1f0e7b6c22071fb2de01c48f43e9a75` | 1474.474 / 1475 | 44,189 / 69,116 |
| `ksyY5wa5_50` / Multi-Engine and Jets | 68,665,567 | `9a34df4cba1a1061822f517670dc1d4d1525656374428cc34800df0aca80323a` | 1702.271 / 1702 | 51,016 / 79,794 |
| `kiCNa95DnnE` / Weather Minimums and Final Tips | 52,449,855 | `d74ef9673385a27a72aebae7c8186de516cb37ac10df8fa02d9b5f21791265d3` | 1292.351 / 1292 | 38,731 / 60,579 |

Pinned YTSeg `raw_chapters` were read from TRAIN shards at revision `4ee1c1fccc5a9e118ff0918f3df1e61aadca8970` ([row excerpt](./ytseg-260929-1543-reserve-b-ytseg-rows.json)). The three rows each have one fewer `chapter_timestamps` than titles, matching the common structural pattern. That pattern is **not** treated as conversion-code proof.

At the preset 10/50/90% positions, the publisher MP4's embedded captions, video frames, and corresponding released chapter topics align:

| ID | 10% | 50% | 90% |
|---|---|---|---|
| `xsO2Ip6eiaY` | Seaplane photos / Bush Pilot Wisdom | Seaplane discussion / Bad things to do in a Seaplane | Lecturer / Light Sport flying boats |
| `ksyY5wa5_50` | Aircraft panel / Where the problems happen | Pilot Requirements slide | Lecturer / Questions? |
| `kiCNa95DnnE` | Basic VFR Weather Minimums slide | Best Glide Ratio slide | Study Guide slide |

The first, middle, and last internal raw chapter boundaries were also checked in each video, using captions immediately before/after and a frame two seconds after the boundary ([boundary receipt](./ytseg-260929-1543-reserve-b-boundary-receipt.json)). All nine sampled frames show the expected chapter slide: `Boats or Floats`, `Seaplane Pilot Skills`, `Questions?`; `Eisenhower's Air Force One`, `Pilot Requirements`, `Questions?`; `Airspace Diagram`, `Thunderstorms`, `Next Steps`. This is direct sampled timeline evidence; matching duration alone was not used.

The captions and released YTSeg text may share an upstream transcript, so their agreement is not independent ASR. Six sampled locations per video do not certify every boundary. The upstream code that defines derived GT fields remains absent, and the slides contain images/diagrams with unresolved whole-component rights. No raw label was edited, and these reserves are not additional independent groups. Content-level duplicate comparison with pilot lectures belongs to the main audit; exact video-ID non-overlap alone is insufficient.

## Unresolved questions

1. Can the upstream GT conversion be verified or an explicit release-field protocol amendment be approved?
2. Are all components in these three MIT lecture videos cleared for the intended reuse?
3. Does a content-level comparison exclude near duplicates of prior pilot lectures?
