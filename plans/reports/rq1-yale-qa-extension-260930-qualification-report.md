# RQ1: three further lectures from the preselected Yale QA sample

**2026-09-30; source-only qualification.** The [three-row subset lock](rq1-yale-qa-extension-260930-locked.csv) is drawn from the previously fixed nine-course QA selection, prioritizing ECON 251 and ECON 252 as two previously unqualified lecturers, then PHYS 201 as one held lecturer. The [selection receipt](rq1-yale-qa-extension-260930-selection-receipt.json) binds the prior QA list and GT snapshot. Current publisher `label,time` pairs match that snapshot exactly for **3/3** lectures; [source metadata](rq1-yale-qa-extension-260930-source-metadata.csv) and [original pair table](rq1-yale-qa-extension-260930-source-pairs.csv) retain all labels and seconds.

The [media acquisition manifest](rq1-yale-qa-extension-260930-media-acquisition.csv) preceded transfer. [Full-media decode receipt](rq1-yale-qa-extension-260930-full-media-decode-receipt.json): **3/3** publisher m4v files fully decoded, with exact byte lengths and SHA-256. The [per-start source review](rq1-yale-qa-extension-260930-boundary-review.csv) covers **14** internal starts. The [decision record](rq1-yale-qa-extension-260930-review-decisions.json) distinguishes title and boundary errors; the [unit gate table](rq1-yale-qa-extension-260930-final-gates.csv) records **0/3 pass**.

- [ECON 251 L1](https://oyc.yale.edu/economics/econ-251/lecture-1): four starts pass; 2027 and 2773 s are gradual transitions without a distinguishable onset inside ±3 s. `hold_boundary`.
- [ECON 252 (2008) L6](https://oyc.yale.edu/economics/econ-252-08/lecture-6): two pass, 1200 s uncertain, 2504 and 3419 s boundary errors. At 3419 s the source moves to problem-set logistics rather than the listed forecasting chapter; title status is recorded separately. `hold_boundary`.
- [PHYS 201 L10](https://oyc.yale.edu/physics/phys-201/lecture-10): two pass; at 4027 s the lecturer continues an already introduced Faraday/Lenz formula, so the listed Faraday-law boundary is unaligned. `hold_boundary`.

Whole-lecture visual review shows lecturer/board or course presentation; the scoped internal noncommercial rights gate passes for these exact sources, without media/transcript redistribution. Rights do not override a boundary hold. No original GT was shifted and no candidate chaptering score was consulted.

**Current recruitment pool: N=13/G=13**, still seven independent pass groups short of the prospective **8/4/8** floor. This finite Yale QA extension does not justify lowering the sealed-test floor or opening official RQ1. Cohort, project-use history, split, D2 and candidate/checkpoint/config remain unlocked.

## Unresolved questions

1. Can another predeclared source with independent lecturers and clear component-use terms supply seven or more eligible groups, given the low observed Yale yield?
2. If no such source is available, should the official generalization claim remain `blocked_data` and the 13-group work be reported as qualification feasibility only?
