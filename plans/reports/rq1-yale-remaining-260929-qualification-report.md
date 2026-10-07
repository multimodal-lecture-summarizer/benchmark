# RQ1: remaining fresh Yale lecturer groups

**2026-09-29; source-only qualification before any candidate chaptering score.** The [11-row Yale selection](rq1-yale-remaining-260929-locked.csv) and its [course-page snapshot](rq1-yale-remaining-260929-course-snapshot.json) were locked before opening selected lecture pages or media. The selection took one hash-ordered lecture from each previously uninspected lecturer group in the 40-offering Yale inventory. No original `label,time` was edited; no candidate output entered eligibility review.

## GT, media and boundary results

- [Publisher GT/source metadata](rq1-yale-remaining-260929-source-metadata.csv): 10/11 pages have a paired structural zero and internal starts, embedded video ID, and publisher video HEAD. [HIST 276 lecture 3](https://oyc.yale.edu/history/hist-276/lecture-3) publishes **five labels but six numeric times**; it remains `hold_source` without invented pairing. The 10 source-valid units contain [56 preserved pairs](rq1-yale-remaining-260929-source-pairs.csv), including 46 internal starts.
- [Exact-media acquisition manifest](rq1-yale-remaining-260929-media-acquisition.csv) preceded downloads. [Full decode receipt](rq1-yale-remaining-260929-full-media-decode-receipt.json) records **10/10** source-valid Yale publisher videos, **2,732,685,878 bytes** total, per-file SHA-256 and full FFmpeg audio/video decode. The source-invalid HIST 276 media was not downloaded for qualification.
- The [per-start review](rq1-yale-remaining-260929-boundary-review.csv) records 46 decisions: **39 pass, four uncertain, three boundary errors** under the fixed ±3 s rule. Title meaning is separate: 38 pass, eight uncertain, zero clear title errors. Ambiguous coarse ASR spans were checked with wider source audio or word times; no timestamp was moved. The [decision file](rq1-yale-remaining-260929-review-decisions.json) records source-only reasons. Contact sheets, source-audio diagnostics and 120 s full-lecture storyboards remain in ignored local storage.

## Unit gates and yield

The [unit gate table](rq1-yale-remaining-260929-final-gates.csv) gives all 11 decisions. Five newly selected course/lecturer groups pass all source, exact-media, boundary and scoped rights gates: [HIST 116 L4](https://oyc.yale.edu/history/hist-116/lecture-4) / Joanne Freeman; [PHIL 176 L20](https://oyc.yale.edu/philosophy/phil-176/lecture-20) / Shelly Kagan; [HIST 251 L1](https://oyc.yale.edu/history/hist-251/lecture-1) / Keith E. Wrightson; [SPAN 300 L2](https://oyc.yale.edu/spanish-and-portuguese/span-300/lecture-2) / Roberto González Echevarría; and [PLSC 114 L12](https://oyc.yale.edu/political-science/plsc-114/lecture-12) / Steven B. Smith. The scoped decision covers internal noncommercial research on these exact Yale videos, with no redistribution of media or transcripts. Full-lecture visual samples show lecturer/board only; selected-page transcripts did not identify an extended contemporary third-party audiovisual component. Yale's [general terms](https://oyc.yale.edu/terms) do not automatically cover excluded third-party material.

Five units stay `hold_component`, four of those also `hold_boundary`. HSAR 252 has boundary-aligned starts but remains held because its [publisher Lecture 19 credits](https://oyc.yale.edu/sites/default/files/lecturecredits19.pdf) identify third-party images present in the video. HIST 276 is the source-pair hold. These holds are unresolved use-basis or GT/alignment decisions, not findings of infringement. A correct title alone does not repair an off-collar boundary; an uncertain title alone did not remove any boundary-aligned unit.

**Observed yield:** five pass among 11 fixed selections. Together with the prior seven independent passes, the undivided recruitment pool is now **N=12/G=12**. The prospective narrower floor of **8/4/8 = 20 groups** still needs **at least eight additional eligible, independent groups**, and development-only precision may demand more test groups. All 36 listed Yale lecturer groups have now had at least one lecture touched in recruitment/QA; the 36-group metadata ceiling was never a pass count. Follow-up can test preselected alternative lectures in held groups or another predeclared source, but no held GT is repaired and no current pass is assigned a split.

**Execution state:** cohort not locked; project-use history for final-test role assignment not verified; no course/lecturer split; D2 open; candidate/checkpoint/config unlocked; official RQ1 not run.

## Unresolved questions

1. Can a separately locked alternative Yale tranche supply eight additional independent pass groups, given observed rights and boundary attrition?
2. Will development-only variability support the revised grouped-bootstrap precision at the 20-group floor?
