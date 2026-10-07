# RQ1 project-controlled use history for 13 qualified groups

**2026-09-30, before cohort or split lock.** The [13-row ledger](rq1-existing-13-project-use-history-260930.csv) reconciles the existing pass-gate CSVs with the YTSeg and VidChapters use-history ledgers. This is a project-use audit, not a claim that a public video has never been used by anyone else.

The exact video IDs were searched in project code, notebooks, plans, qualification records, checked-in text and locally present output/cache/checkpoint/probe text. The ECON 159 course aliases were separately searched in the local run/output locations. The ID hits were source-only qualification files and rule/amendment references; no inspected candidate-run output, training/tuning record, model-selection record or final-test record names these 13 videos. The older `checkpoints/c5_real.pt` is dated 2026-09-05; the corresponding benchmark script reads `benchmarks/data/cached_features`, whose 20-item manifest lists a different set of lecture IDs. The existing benchmark summary is aggregate-only and does not cryptographically bind that checkpoint to the manifest. Therefore the negative search is bounded by inspectable records, not proof about opaque or missing historical runs.

**ECON 159 L2:** its earlier nine-course exposure was publisher media and GT metadata QA, followed by source-only boundary and rights qualification. The ID/course alias search finds only that QA path, not candidate predictions or tuning. On available project-controlled evidence this exposure alone does not disqualify the group, but its final-test role stays provisional until run-manifest reconciliation and the entire course/lecturer component is assigned to one split.

The other 12 have the same provisional status. Original YTSeg/VidChapters release split labels describe upstream dataset provenance; they do not demonstrate a project model was trained on these videos. If later local or external checkpoint provenance shows training, tuning or model selection on a group, exclude that whole group from final test. Qualification and title/boundary review do not use model results. No group is assigned to final test in this ledger.

## Unresolved questions

1. Are there opaque historical checkpoint or run manifests outside the inspectable workspace that used any of these groups for training, tuning or selection?
2. Which qualified groups, if 20 become available, can be held entirely unseen after transitive course and lecturer grouping?
