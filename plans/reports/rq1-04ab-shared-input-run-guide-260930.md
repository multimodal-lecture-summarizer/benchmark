# RQ1 04a/04b shared input lock and local run guide

**Retired guide, 2026-10-07:** RQ1 will not be rerun. The dedicated `rq1_d2_notebook_manifest.yaml` and unused 00c RQ1 notebook referenced below were removed during notebook cleanup. Commands in this dated report are historical records and must not be used as a current run guide; retained results and receipts remain available.

## Current state

- D2 source cohort: 20 independent units, split 8 train / 4 validation / 8 final test.
- `rq1-04ab-shared-input-recipe-260930.json` locks the exact D2 source bundle, independent ASR selection, `tiny.en` snapshot revision and model-file hashes, CPU int8 decoding parameters, feature extractor code and dependency hashes, FFmpeg identity, and each modality's preprocessing config.
- The recipe has `status=recipe_locked_payloads_pending`; its null output-hash fields describe the pre-materialization recipe. The separate `materialization.receipt.json` now binds all 12 development transcript and video-feature payload hashes. No 04a/04b result is evidence from this cohort yet.
- `04a` writes `chapter.input_features`; `04b` consumes that exact artifact. The dedicated RQ1 `00c_rq1_d2_inputs` notebook has now published `dataset.frozen_manifest`, `dataset.registry`, and `dataset.endpoint_matrix` under `experiments/outputs/rq1_locked_mixed_20/notebook_artifacts/official/full/`. Its selection manifest embeds source-bound inputs for development units only; the eight final-test entries carry only ID, dataset, split, course and speaker, with no GT, media path, transcript or feature.
- All 12 development units are materialized and verified locally: 8 train, 4 validation, all four video modalities available on each. Materialization receipt SHA256: `6ceceafd7a87ea1fb8f969fa25a4bf6df3cacca7192e4b961b7defc5225dbe11`. Final-test inputs remain sealed.
- Learned candidate C5/C6 checkpoint provenance and the validation precision gate remain unresolved. Final test stays sealed. The current 00c run ID is `24d1d076-c59a-4ca1-885c-3e32091a7836`; its frozen-manifest receipt SHA256 is `f9676eb51423422712dcb69e77f0a521313360d740aee98b73020301cfd09b6c`. This official input namespace is immutable; a revised source/input recipe requires a fresh artifact root.
- A train-only source handoff now binds the exact eight train units to the D2 split, media, transcript and video-feature hashes. Its status is `train_sources_bound_learned_tensors_pending`: it is input provenance, not checkpoint proof. C2/C3/C4 model code now consumes transcript plus its added modality, matching the frozen matrix.
- A separate learned path now extracts text/DINOv2/OCR/log-mel tensors for exactly 8 train + 4 validation units, trains C1-C6 with 3 seeds, writes checkpoint provenance, chooses each seed by validation BCE, scores all four validation groups, and invokes the pretest precision calculation. Its scripts and a short real-media extraction fixture have been tested; full 12-unit extraction/training has not run. The current 04a/04b notebook runners remain heuristic and do not consume these new learned outputs, so they cannot yet be called official C1-C6 notebook evidence.

## Local preparation

Run from the inner repository directory `multimodal-lecture-summarizer/multimodal-lecture-summarizer` in PowerShell:

```powershell
python -m experiments.scripts.rq1_freeze_input_recipe --verify
python -m experiments.scripts.rq1_materialize_shared_inputs --unit-id 679FGDpZBew
python -m experiments.scripts.rq1_materialize_shared_inputs
python -m experiments.scripts.rq1_materialize_shared_inputs --verify
python -m experiments.scripts.rq1_train_source_handoff --verify
```

The single train unit was an integration check of source processing only; it was not a pilot used for model choice. The development materialization commands above have completed. Each unit has a transcript JSON, video-feature JSON, and a receipt under `experiments/outputs/rq1_locked_mixed_20/shared_inputs/`. Keep the final-test flag off during selection. The materializer verifies the D2 media SHA256 and refuses unreceipted or changed outputs. If the recipe check fails after dependency/model changes, investigate and issue a new recipe revision before continuing.

The receipt has exactly 8 train and 4 validation units and all four feature modalities available. The dedicated official 00c run has published these payloads. The ordinary 22-notebook manifest still describes the general benchmark; use the dedicated RQ1 manifest below for this cohort.

## Notebook planning and execution

The notebooks are thin orchestrators and fail when run directly in a notebook UI without executor-controlled environment variables. These commands validate the execution plan only:

```powershell
python -m benchmarks.scripts.execute_all_notebooks --manifest experiments/notebooks/rq1_d2_notebook_manifest.yaml --notebook 04a_chaptering_benchmark --profile full --dry-plan --artifact-root experiments/outputs/rq1_locked_mixed_20/notebook_artifacts
python -m benchmarks.scripts.execute_all_notebooks --manifest experiments/notebooks/rq1_d2_notebook_manifest.yaml --notebook 04b_chaptering_modality_ablation --profile full --dry-plan --artifact-root experiments/outputs/rq1_locked_mixed_20/notebook_artifacts
```

Keep these as planning commands while 04a/04b still use heuristic runners. The old `benchmarks.scripts.run_rq1_benchmark` uses a random split of a separate feature cache, so its C5 checkpoint cannot prove train-only use of these eight groups. The separate learned path below computes the pretest precision gate automatically after complete C1-C6 validation scores; final test remains sealed.

## Learned train/validation path

Run from the inner repository. Each feature unit writes an immutable `.pt` plus a SHA-bound receipt; rerunning skips verified units. Start with one train unit, then complete the twelve development units:

```powershell
python -m experiments.scripts.rq1_learned_features --unit-id=-7xg8pGcP6w --device cuda
python -m experiments.scripts.rq1_learned_features --device cuda
python -m experiments.scripts.rq1_learned_features --verify
python -m experiments.scripts.rq1_train_learned --device cuda
```

The full trainer uses seeds `42,1337,2026`, up to 35 epochs per seed/candidate, patience 5, 128-token chunks and the same learning-rate/early-stop budget for C1-C6. It updates weights on train units only. Validation GT controls early stopping and seed choice, and creates `learned_training/full/validation_scores.json`, `validation_precision.json`, `selected.json`, one checkpoint and provenance file per seed, and a frozen `configuration.json`. Resume uses verified checkpoint/provenance pairs; changed source, code, split or configuration stops the run. `--smoke` is a one-seed/one-epoch diagnostic in a separate output directory and is not eligible for official selection. None of these commands accesses final-test inputs.

Feature extraction uses MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, official Facebook DINOv2-small revision `ed25f3a31f01632728cabb09d1542f84ab7b0056` (ViT-S/14, 384 dimensions), PaddleOCR `ch_PP-OCRv4` at confidence 0.6, 32-band log-mel audio, 2-second temporal tokens, and the D-T04 1-fps fallback when TransNetV2 is unavailable. Visual and OCR use exactly the same sampled frames. A lecture with no recognized OCR produces zero OCR embeddings; it is not removed from the locked cohort. The TensorFlow TransNetV2 inference dependency is absent locally, so this fallback is the selected path before feature extraction. The DINOv2 implementation is the official Hugging Face distribution rather than the `torch.hub` entry named in D-T04; this implementation amendment is recorded in the decisions log.

## Machine choice

Use local Windows for the completed source-only pass. The RTX 4050 Laptop can load DINOv2, but installed PaddleOCR is CPU-only. The `ch_PP-OCRv4` detection, recognition and angle-classification weights now cache inside ignored `experiments/outputs/rq1_locked_mixed_20/model_cache/paddleocr/`; six inference files are SHA256-bound in each feature receipt. The earlier eight-second extraction test used a different OCR language configuration; no reliable full-run duration estimate exists for the final `ch_PP-OCRv4` path. For full extraction, a Colab GPU with CUDA-enabled PaddleOCR is preferable after media transfer and dependency preflight; pass `--ocr-gpu` and retain one compute setting across all twelve receipts. Copy the frozen D2 files, the 00c published manifest and receipt, all 12 media files, and `shared_inputs/` under the same repository-relative locations. The extractor rebases original Windows paths to those locations and verifies each SHA256 before reading. Training itself may also need Colab's larger GPU. Do not silently lower the sampling rate. Interrupted tensor/checkpoint writes without a matching receipt are recomputed; verified completed units and seeds are reused.

## Unresolved questions

- Full 12-unit learned extraction/training and validation precision result are pending. Integrate the selected learned predictions with the 04a/04b official notebook artifact contract before presenting them as notebook evidence; keep final test sealed until the gate and checkpoint/config lock pass.
