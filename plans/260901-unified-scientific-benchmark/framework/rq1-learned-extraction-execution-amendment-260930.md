# RQ1 learned-feature execution amendment — 2026-09-30

**Status:** pre-validation execution amendment. No learned checkpoint or validation score existed when this was written. The frozen 20-unit D2 cohort, 8/4/8 group split, GT, media, transcript revision, 1 fps frame sampling, DINOv2 and MiniLM revisions, 2 s feature grid, OCR weights, and confidence threshold stay fixed.

## Reason

The initial Windows extractor ran PaddleOCR on CPU in the same process as CUDA Torch. The first 4,847-frame train unit reached frame 3,600 and was manually interrupted inside PaddleOCR recognition; it had no complete tensor or receipt. The CPU path held memory near the 16 GB machine limit and used the NVIDIA GPU only intermittently. `--verify` correctly rejected missing learned features. No training output from this attempt can be treated as a checkpoint.

## Amended execution

Run PaddleOCR 2.8.1 / PP-OCRv4 on the NVIDIA GPU in an isolated Python process using PaddlePaddle GPU 2.6.2, CUDA 11.8, cuBLAS 11, and cuDNN 8.9.4. Save OCR text and decoded-frame SHA-256 in source-bound, 100-frame atomic chunks. An interrupted run resumes at the first missing chunk. Once OCR completes, the Torch process re-decodes the same 1 fps frame times, requires the frame hash to match, and computes DINOv2 features on CUDA. The final tensor receipt binds the OCR worker code hash, OCR chunk manifest hash, model weight hashes, media/split hashes, and extractor hash. Training verifies the cache again. The final-test units remain inaccessible to this command.

GPU and CPU floating-point inference may disagree near the fixed 0.6 OCR confidence threshold. Therefore all 12 development units must use one compute setting; the trainer rejects mixed settings. There were no completed CPU learned tensors to mix with this amended run. This change affects execution and possible OCR text values, so its code and compute setting must be fixed before validation selection. It does not authorize any GT changes or selection based on test predictions.

## Local execution

The isolated interpreter on this machine is `experiments/outputs/rq1_locked_mixed_20/venv_paddle_gpu/Scripts/python.exe`; it is ignored by Git. From the nested repository root:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python -m experiments.scripts.rq1_learned_features --device cuda --ocr-gpu --ocr-python .\experiments\outputs\rq1_locked_mixed_20\venv_paddle_gpu\Scripts\python.exe
python -m experiments.scripts.rq1_learned_features --verify
python -m experiments.scripts.rq1_train_learned --device cuda
```

The first command prints OCR progress every 100 frames, then visual progress every 300 frames. On interruption, rerun the same first command; completed OCR chunks are reused after integrity checks. The second command succeeds only when all 12 train/validation tensors and receipts exist. The third command should run only after that verification. Do not open final test until the existing validation precision gate and candidate/configuration lock have passed.

After the 2026-09-30 Windows graphics-kernel bugcheck during CUDA visual encoding, use the separate safe-resume runner for remaining development units:

```powershell
python -m experiments.scripts.rq1_safe_resume --max-new-units 1
python -m experiments.scripts.rq1_safe_resume
python -m experiments.scripts.rq1_learned_features --verify
```

The first invocation checks the existing `-7xg8pGcP6w` tensor and processes only the shortest missing unit (`679FGDpZBew`, whose GPU OCR cache is already complete). Subsequent invocations process the remaining frozen train/validation units in ascending duration order. DINOv2 and MiniLM run on CPU; OCR alone uses GPU in a separate process. The runner checks `nvidia-smi` every second and stops its own extractor process tree if GPU memory used reaches 3,072 MiB, free VRAM falls below 2,048 MiB, or free system RAM falls below 2,048 MiB. Completed OCR chunks remain reusable; a completed tensor is checked before the next unit. Per-unit execution receipts record CPU visual compute, GPU OCR compute, resource limits, observed memory, and tensor/feature-receipt hashes. This guard reduces memory pressure but cannot guarantee prevention of a Windows driver bugcheck. A resource-stop or nonzero child exit requires diagnosis before another attempt.

Offline model loading is needed on the current shell because its HTTP proxy points to `127.0.0.1:9`. The exact MiniLM and DINOv2 revisions are already in the local model cache. If those cache files are absent on another machine, populate the pinned revisions before using offline mode.

## Verification before full run

- Isolated Paddle GPU/CUDA/cuDNN self-check passed on this Windows GPU.
- GPU OCR produced real text on 89 of the first 100 frames of a train video; 100/100 frame hashes matched a separate OpenCV decode.
- The 100-frame GPU OCR smoke took about 17 seconds including startup on this machine. This is a local observation, not a full-cohort runtime estimate.
- The resumable-chunk test verifies restart without repeating a completed chunk and rejection of tampered chunk content.
- One 1,125-frame train unit (`679FGDpZBew`) completed end to end with GPU OCR and CUDA DINOv2; its receipt and OCR manifest verified. The other 11 development units still require materialization before training.

## CLI correction on 2026-09-30

The first full-cohort invocation stopped before OCR on the YTSeg unit `-7xg8pGcP6w`: `argparse` treated its leading hyphen as an option when the parent process passed `--unit-id` and the value as separate arguments. The parent now passes `--unit-id=<id>`. A GPU OCR smoke with that exact negative ID completed and its manifest preserved the ID. The earlier `679FGDpZBew` tensor/receipt were preserved under `learned_features/superseded_20260930_cli_fix/`; the full command will regenerate that unit under the corrected extractor code hash. No GT, split, model choice, or validation score changed.
