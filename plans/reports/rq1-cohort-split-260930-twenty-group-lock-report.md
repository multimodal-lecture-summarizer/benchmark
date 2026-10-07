# RQ1 20-group cohort and 8/4/8 split lock

**2026-09-30, before any candidate result on this cohort.** [Ten-group qualification](rq1-recruitment-260930-ten-group-qualification-report.md) supplied exactly seven new passes to the existing 13; all 20 exact IDs and source-gate hashes are frozen in the [cohort manifest](rq1-cohort-260930-twenty-qualified-locked.json) (SHA-256 `8596d3aad4421ff2e38a86c4e890090ad52f42f33b87e0a7d0babd080135fb4d`). [Project-controlled history](rq1-project-use-history-260930-twenty-group-report.md) was screened before assigning any final-test role; its [20-row machine record](rq1-project-use-history-260930-twenty-groups.json) has SHA-256 `aaa04ffd5097638e2b5dc8ce786c7cddcbbdb132d7a67e1689619aefc4265326`.

The [predeclared source-stratified hash rule](rq1-split-260930-rule-locked.md) produced the [locked assignment](rq1-split-260930-8-4-8-locked.json) (SHA-256 `1bb28edc0c48849d72b827bcf98b7ea35eecbcce7c8da4160693e0041956cbe8`) and [receipt](rq1-split-260930-8-4-8-receipt.json). The split guard validates **20 connected components with no shared course or lecturer crossing splits**, with **8 train, 4 validation, 8 sealed final-test** groups. Legacy YTSeg/VidChapters groups contribute 3/1/2 and publisher-native Yale contributes 5/3/6.

The eight sealed final-test IDs are `AW3a2ECNFlE`, `09vU-wVwW3U`, `e3uBi2TZdUY`, `Y3S1uqgGfB4`, `qQ3kFydI_xQ`, `9FrHGAd_yto`, `WMkD8HKJQCM`, and `4YY4CTSQ8nY`. ECON 159 L2 appears here after source-only QA history review; its previous GT/media QA is recorded, and no inspectable project candidate training or selection use was found. These IDs and GT must not enter train/validation feature fitting, tuning or checkpoint selection. The split is an allocation decision, not an instruction to execute final inference now.

The prospective 8/4/8 scale is now achieved. The desired grouped-bootstrap 95% CI half-width ≤0.20 F1 remains **unverified**: four validation groups must supply a pretest variance estimate, and the planning formula may demand more than eight sealed groups. If that happens, do not extend this sealed test after looking at scores; record `blocked_precision` or amend the pretest claim before opening final results. D2 exact-source/media/transcript/feature receipts and candidate/checkpoint provenance are still outstanding.

## Unresolved questions

1. Can all 20 frozen units pass D2 source/media/transcript/feature receipt validation without cohort edits?
2. Can train-only learned candidate checkpoints and validation-only selection be produced under this eight-group training allocation?
3. Does validation-only variance support the fixed eight-group sealed test for the stated precision target?
