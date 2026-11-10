"""Diagnose why Qwen3-ASR rejects a chunk (empty waveform) on a video the ablation extracts.

Run in the app venv on the 16 kHz WAV that the extract step left next to the video. For every chunk the app
would send, it prints the raw and denoised shapes and then calls Qwen3-ASR on that chunk alone, so the failing
chunk and the reason (empty denoise output, odd shape, tiny tail) are named. Nothing here changes the app.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback


def describe(name, array):
    import numpy as np

    array = np.asarray(array)
    finite = bool(np.isfinite(array).all()) if array.size else True
    peak = float(np.abs(array).max()) if array.size else 0.0
    return f"{name}: shape={array.shape} dtype={array.dtype} seconds={array.size / 16000:.2f} finite={finite} peak={peak:.4f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--wav", required=True)
    parser.add_argument("--max-chunks", type=int, default=0, help="0 = all chunks")
    args = parser.parse_args()
    os.chdir(args.app_root)
    sys.path.insert(0, args.app_root)
    os.environ.setdefault("PADDLEOCR_USE_GPU", "0")

    from ai_workers.modules.audio_v2.qwen_transcriber import QwenEnglishTranscriber, split_audio_chunks

    engine = QwenEnglishTranscriber({})
    raw = engine.load_samples(args.wav)
    print(describe("raw audio", raw), flush=True)
    chunks = split_audio_chunks(raw)
    print(f"{len(chunks)} chunks: " + ", ".join(f"{c.size / 16000:.1f}s" for _, c in chunks), flush=True)
    model = engine._load_model()
    for index, (offset, chunk) in enumerate(chunks, 1):
        if args.max_chunks and index > args.max_chunks:
            break
        print(f"--- chunk {index}/{len(chunks)} at {offset:.1f}s", flush=True)
        print("  " + describe("raw chunk", chunk), flush=True)
        clean = engine.denoise_samples(chunk)
        print("  " + describe("denoised", clean), flush=True)
        for label, audio in (("denoised", clean), ("raw", chunk)):
            started = time.perf_counter()
            try:
                result = model.transcribe(audio=(audio, 16000), language="English", return_time_stamps=True)[0]
                print(f"  qwen on {label}: OK {len(result.text.split())} words in {time.perf_counter() - started:.1f}s", flush=True)
            except Exception as error:  # noqa: BLE001 - diagnostic
                print(f"  qwen on {label}: FAILED {type(error).__name__}: {str(error)[:160]}", flush=True)
                print("    " + traceback.format_exc().splitlines()[-3].strip(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
