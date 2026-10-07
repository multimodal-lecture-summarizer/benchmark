# MIT001 multimodal diagnostic completion

## Scope

- Extract source-bound visual change and acoustic change observations for each of the same 35 local MIT001 MP4 files. Keep scene, OCR and transcript inputs and their provenance checks.
- Admit visual/acoustic features only when timestamp, digest, source hash and extraction metadata validate.
- Add fixed, GT-independent heuristic predictors for transcript+visual, transcript+acoustic and all_modalities. Keep C5/C6 learned models as `not_run` without valid training/checkpoint provenance.
- Run 04a/04b on all 35 units and generate a paired report including every executed ablation, preserving diagnostic-only status.

## Checks

- Focused extraction, contract, runner and report tests.
- Inspect artifact status, feature coverage, cohort identity, per-variant prediction counts and paired metrics.
- Report runtime failures or missing modalities explicitly; never infer scores for unexecuted variants.
