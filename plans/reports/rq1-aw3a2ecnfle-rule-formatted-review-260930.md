# VidChapters AW3a2ECNFlE: rule-formatted source review

**Date:** 2026-09-30. **Decision:** `pass_boundary`; the previous provisional pass is confirmed before D2. This review applies the already frozen [qualification rule](../../multimodal-lecture-summarizer/plans/260901-unified-scientific-benchmark/framework/rq1-boundary-qualification-rule-260929.md) to the original uploader starts. It does not edit a label or time, use candidate predictions, or open final-test scores.

The original VidChapters record begins at byte 1898437410 in `chapters.pkl` (SHA-256 `d476b9aa628d96d015d288a9554fed2e37206670bbcd55b7bf072bf2019b166e`). Bounded `pickletools` inspection, without executing the pickle, finds the 11 original `label,time` pairs and matching uploader description. The exact [MIT OCW lecture page](https://ocw.mit.edu/courses/14-772-development-economics-macroeconomics-spring-2013/resources/lecture-5-february-21-2013/) links the video. Full MP4 SHA-256 is `b3d4dbb35935cef4c16d573d11cdd2d9eb62b16d8ed15cd9277a50093148eb20`; full decode passed, with 4923.058792 s media versus 4923.103 s annotation duration. Scoped internal research rights passed in the earlier [semantic and rights report](./vidchapters-semantic-260929-1818-selected-groups-report.md); retain source and courtesy credits.

The pre-rule audio diagnostic file SHA-256 is `44e1e38ac02421a4b8116d9ee87da6d69a1e6a12a9f139d9cbc7104ed4848266`; the ±5 s contact sheet SHA-256 is `d1334f19729f7646c6b9852eb662589031f05e2648fe8732c495cb24710690c7`. A new source-only 1 s contact sheet for the close cases at 302, 2175, 3010 and 3790 s has SHA-256 `cd9c21d3f2e11c07f9c567342a16468329970c4df1d289e6234a0da5beb302af`. ASR is a diagnostic cue; frames and audible transitions establish the reviewer observations.

| Original time (s) | Original title | Title status | Boundary status | Observation within original time ±3 s |
|---:|---|---|---|---|
| 26 | Introduction to lecture | pass | pass | OCW title slate/introduction ends; lecturer begins at about 27.6 s. |
| 302 | Overview of measurement in economics | pass | pass | Previous impact-on-welfare example ends about 301 s; lecturer starts general measurement tools about 303.7 s. |
| 802 | Household financial accounts | pass | pass | Lecturer announces financial accounts at 802 s; slide changes to household finance within the sampled interval. |
| 1111 | Example of a typical household's balance sheet | pass | pass | Lecturer starts a typical balance-sheet example about 1111.8 s; slide changes to assets/liabilities. |
| 2175 | Cash management example | pass | pass | After cash-deficit mechanisms, lecturer introduces two measured case-study households about 2172.4 s; case-study table appears by 2175 s. |
| 3010 | Example of application: productivity and net worth correlation | pass | pass | The previous accounting formula concludes; correlation slide appears about 3011 s and lecturer introduces the net-worth correlation about 3012 s. |
| 3490 | Village product accounts | pass | pass | Lecturer switches from measurement error to creating accounts about 3491 s; product/production-account slide appears. |
| 3790 | Village saving and investment accounts | pass | pass | Appropriation-account slide gives way to saving-investment slide about 3791 s; speech moves from retained earnings to the new account. |
| 4050 | Village balance of payments | pass | pass | Lecturer announces balance of payments about 4049–4050 s; matching slide appears. |
| 4522 | Village flow of funds | pass | pass | Lecturer announces flow of funds about 4523.2 s; matching table appears. |

The structural start at 0 s (`Title slates`) is retained in source provenance but excluded from internal-start scoring by the frozen endpoint. All ten internal boundaries have independent source-media anchors within ±3 s. **Title errors: 0; boundary errors/uncertain: 0.** This confirms the prior qualification and does not alter the locked cohort or 8/4/8 split.

## Unresolved questions

None for this unit's qualification. D2 and candidate/checkpoint provenance remain separate run gates.
