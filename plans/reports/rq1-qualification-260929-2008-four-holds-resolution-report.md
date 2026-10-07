# RQ1: resolution of the four locked candidates

**Pre-score source QA only.** [Batch selection](rq1-batch-260929-1945-locked.csv) preceded these media checks. The [per-unit receipt](rq1-batch-260929-2008-media-boundary-receipt.json) records original annotation offsets, publisher URLs, exact media hashes, duration, full decode and decisive boundary evidence. [Gate table](rq1-batch-260929-2008-final-gates.csv). No GT time/label was edited and no model prediction was inspected. Downloaded media, contact sheets and diagnostic audio remain in an ignored local dataset directory.

| ID | Decision | Decisive evidence |
|---|---|---|
| `EuNXVy5-KgA` | **pass** | Exact [MIT 16.687 resource](https://ocw.mit.edu/courses/16-687-private-pilot-ground-school-january-iap-2019/resources/lecture-20-flying-at-night/) and 14/14 source pairs. MP4 SHA-256 and full decode pass. Each of 13 internal starts opens its named slide within ±3 s. End credits identify external figures as public domain. |
| `js34ZxECiCA` | **hold boundary + rights** | MIT channel ID/title/duration reconcile with [MIT 22.033 lecture 8](https://ocw.mit.edu/courses/22-033-nuclear-systems-design-project-fall-2011/resources/lecture-8-metals-and-cheeses-uncoventional-pairings/); 21/21 source pairs and exact publisher MP4 decode pass. At 1984 s the IGSCC slide is already present, and speech continues Alloy 600TT. Video end credits explicitly exclude named third-party images from its CC license. |
| `qdbkvD4N-us` | **hold boundary** | Exact [MIT 18.S096 resource](https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/resources/lecture-21-stochastic-differential-equations/), 3/3 source pairs and full MP4 decode pass. The task labeled 1275 s is introduced around 1259–1267 s; the heat-equation topic at 2547 s is named around 2543 s. Board wiping at either timestamp alone cannot rescue the original boundary under the fixed ±3 s rule. |
| `09vU-wVwW3U` | **pass** | Exact [MIT 6.046J resource](https://ocw.mit.edu/courses/6-046j-design-and-analysis-of-algorithms-spring-2015/resources/recitation-1-divide-conquer-smarter-interval-scheduling-master-theorem-strassens-algorithm/), 5/5 source pairs and full MP4 decode pass. Four internal starts have matching recitation, weighted scheduling, Strassen and master-theorem speech/board onsets within ±3 s. Examined media is blackboard lecture under the [MIT OCW noncommercial terms](https://ocw.mit.edu/pages/privacy-and-terms-of-use/), with no observed excluded component. |

**Observed yield:** 2/4 locked candidates pass, adding **two new independent course/lecturer groups**. Recruitment pool is now **N=6, G=6**; the original four remain intact and none of the six has a train/validation/test assignment. The two holds stay in the catalogue with their original labels/times. This four-unit yield is descriptive and too small to extrapolate a reliable pass probability to all VidChapters or other publishers. The current selected catalogue still cannot provide the deferred 50-group design.

The [expansion selection rule](rq1-source-expansion-selection-260929-1951-locked.md) was locked before inspecting media for any *new* source-expansion candidate. Expansion proceeds with metadata first; the completed four-unit batch does not become a pilot or test split.

## Unresolved questions

1. Can a larger source catalogue supply enough independent course/lecturer groups after the observed GT/media/rights attrition?
2. Do other candidate groups satisfy the same boundary and component-rights rule without using model outcomes?
