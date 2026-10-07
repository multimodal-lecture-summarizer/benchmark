# Research migration — 2026-10-06

## Scope

Research code, notebooks, tests, plans, reports, documentation, local datasets, model caches, checkpoints, and run outputs were moved from the application checkout and the surrounding workspace into this `benchmark` checkout. Existing `audio/` and `visual/` files in this repository were preserved. No Git commit or push was made.

| Location | Files | Size |
| --- | ---: | ---: |
| `benchmarks/` | 150,521 | 4.499 GiB |
| `experiments/` | 161,527 | 85.690 GiB |
| `research-data/` | 286 | 11.810 GiB |
| `cache/` | 148 | 0.309 GiB |
| `external-results/` | 1 | 0.046 GiB |

`plans/`, `reports/`, `docs/`, `tests/`, `outputs/`, `checkpoints/`, `probes/`, `brainstorm-reports/`, `images/`, root research scripts, and requirement snapshots also moved. `docs/workspace/` holds the surrounding workspace's research documents. `plans/reports/` now includes those workspace reports.

## ASR evidence

- Current notebook: `experiments/notebooks/asr_architecture_colab_t4.ipynb`.
- Complete input bundle: `experiments/outputs/asr_architecture_colab_t4_inputs_empty_transcript_261005_clean.zip`; SHA-256 `25ce9f1f300bd1944f081aac9c1543ee6fe3d2a027105c7f03f637505051027b`.
- Run export moved from Downloads: `external-results/runs-20261005T055449Z-1-001.zip`; SHA-256 `8f6e359f947097cb85b67b59024b2e58a7872a86fbcacb8a0a6180310270b1cf`. Its 26,164 ZIP members passed integrity testing; the source file was removed after hash verification.
- Historical notebook archive and manifest remain in `experiments/`.

## Local execution and limits

Large datasets, media, caches, checkpoints, and outputs are ignored by `.gitignore`. Check `git status` before staging any research files. Some experiments still import the application repository's `ai_workers`; set `PYTHONPATH` to this repository and the sibling application repository as shown in the root README. The separate, clean `mit001-publication-worktree` remains outside this repository because it is a Git worktree linked to the application repository, not a research data directory.

The migrated ASR adapter tests passed (8 tests). RQ1 artifact and source-feature tests passed (20 tests) with pytest temporary files under this checkout. The notebook executor suite currently rejects `notebook_manifest.yaml`: it contains 23 entries where the validator expects 22, and both ASR notebooks declare the same four output keys. This manifest conflict predates the migration and needs a separate scientific decision before using the general notebook launcher.

Historical receipts were preserved as evidence of prior runs. Changed source paths and code hashes require a new run identity when executing again; do not relabel earlier receipts as runs from this repository.

## Unresolved questions

- Decide whether `01a_asr_model_benchmark` and `01c_asr_architecture_benchmark` should use separate output namespaces or one should leave the general manifest.
