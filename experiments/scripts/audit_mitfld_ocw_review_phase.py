"""Recheck the three flagged MITFLD/OCW landmarks with a measured A/V phase shift.

Run from the nested repository: python -m experiments.scripts.audit_mitfld_ocw_review_phase
The output is a local-window diagnostic, not full-video synchronization evidence.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.signal import correlate


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "plans/reports"
REVISION = "f5a5047e040ecf0f80a3cb67d64e324407f323ec"
SOURCE = REPORTS / "mitfld-rq1-35-260928-1135-ocw-source-rights-ledger.csv"
SOURCE_SHA256 = "36419f9a3209405647a854032ce7b7acd654dad7fc4086d68aedcb7b44019d10"
LANDMARKS = REPORTS / "mitfld-rq1-35-260928-1300-three-landmark-final.csv"
LANDMARKS_SHA256 = "fc62970ccb45a05869bb5f4f1562eb22d9cbae0a3208e416294d71d0d32d9a5f"
OUTPUT = REPORTS / "mitfld-rq1-35-260928-review-phase-verified.csv"
FRAME_RATE = 20
FRAME_SIZE = 160 * 90
AUDIO_RATE = 16000
WINDOW_SECONDS = 5


def locked_rows(path: Path, expected_sha256: str) -> list[dict[str, str]]:
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError(f"locked input changed: {path}")
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


def decode(url: str, start: float) -> tuple[np.ndarray, np.ndarray, str, str]:
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    common = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{start:.3f}", "-i", url, "-t", str(WINDOW_SECONDS)]
    video = subprocess.run(
        common + ["-an", "-vf", "fps=20,scale=160:90,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=180, env=env,
    )
    audio = subprocess.run(
        common + ["-vn", "-ac", "1", "-ar", str(AUDIO_RATE), "-f", "s16le", "-"],
        capture_output=True, timeout=180, env=env,
    )
    for result in (video, audio):
        if result.returncode:
            raise RuntimeError(result.stderr[-500:].decode(errors="replace"))
    frame_sha = hashlib.sha256(video.stdout).hexdigest()
    audio_sha = hashlib.sha256(audio.stdout).hexdigest()
    frames = np.frombuffer(video.stdout, np.uint8).reshape(-1, FRAME_SIZE).astype(np.float32)
    samples = np.frombuffer(audio.stdout, np.int16).astype(np.float32)
    if len(frames) < 90 or len(samples) < 4 * AUDIO_RATE:
        raise ValueError("decoded window too short")
    # Bind evidence to decoded bytes before converting them to float arrays.
    return frames, samples, frame_sha, audio_sha


def audio_match(hf: np.ndarray, ocw: np.ndarray) -> tuple[int, float]:
    hf, ocw = hf - hf.mean(), ocw - ocw.mean()
    full = correlate(ocw, hf, mode="full", method="fft")
    zero, span = len(hf) - 1, AUDIO_RATE // 2
    lag = int(np.argmax(full[zero - span:zero + span + 1]) - span)
    if lag >= 0:
        a, b = hf[:min(len(hf), len(ocw) - lag)], ocw[lag:]
    else:
        a, b = hf[-lag:], ocw[:min(len(ocw), len(hf) + lag)]
    count = min(len(a), len(b))
    return lag, float(np.corrcoef(a[:count], b[:count])[0, 1])


def frame_sweep(hf: np.ndarray, ocw: np.ndarray) -> dict[int, dict[str, float]]:
    result = {}
    for shift in range(-3, 4):
        # Compare the central 4 seconds; negative shift pairs HF[i] with earlier OCW[i+shift].
        pairs = [(hf[i], ocw[i + shift]) for i in range(10, min(90, len(hf), len(ocw) - shift))]
        correlations = np.array([np.corrcoef(a, b)[0, 1] for a, b in pairs])
        errors = np.array([np.abs(a - b).mean() for a, b in pairs])
        result[shift] = {
            "pairs": len(pairs),
            "corr_median": round(float(np.median(correlations)), 6),
            "corr_min": round(float(correlations.min()), 6),
            "corr_p10": round(float(np.quantile(correlations, 0.1)), 6),
            "mae_mean_255": round(float(errors.mean()), 6),
        }
    return result


def check(row: dict[str, str], ocw_url: str, ffmpeg_version: str) -> dict[str, object]:
    video_id, mark = row["video_id"], float(row["frag_s"])
    hf_url = f"https://huggingface.co/datasets/robotwang/MITFLD/resolve/{REVISION}/videos/{video_id}.mp4"
    with ThreadPoolExecutor(max_workers=2) as pool:
        hf_job = pool.submit(decode, hf_url, mark - 1)
        ocw_job = pool.submit(decode, ocw_url, mark - 1)
        hf_frames, hf_audio, hf_frame_sha, hf_audio_sha = hf_job.result()
        ocw_frames, ocw_audio, ocw_frame_sha, ocw_audio_sha = ocw_job.result()
    lag, audio_corr = audio_match(hf_audio, ocw_audio)
    sweep = frame_sweep(hf_frames, ocw_frames)
    best_shift = max(sweep, key=lambda shift: sweep[shift]["corr_median"])
    return {
        "video_id": video_id, "course_id": row["course_id"], "mark_role": row["mark_role"],
        "frag_s": row["frag_s"], "hf_revision": REVISION, "ffmpeg_version": ffmpeg_version,
        "window_start_s": f"{mark - 1:.3f}",
        "window_duration_s": WINDOW_SECONDS, "frame_rate_fps": FRAME_RATE, "frame_size": "160x90_gray",
        "hf_frames": len(hf_frames), "ocw_frames": len(ocw_frames), "audio_rate_hz": AUDIO_RATE,
        "hf_audio_samples": len(hf_audio), "ocw_audio_samples": len(ocw_audio),
        "hf_raw_frames_sha256": hf_frame_sha, "ocw_raw_frames_sha256": ocw_frame_sha,
        "hf_raw_audio_sha256": hf_audio_sha, "ocw_raw_audio_sha256": ocw_audio_sha,
        "ocw_minus_hf_audio_lag_samples": lag, "ocw_minus_hf_audio_lag_ms": f"{lag * 1000 / AUDIO_RATE:.4f}",
        "audio_corr_after_lag": f"{audio_corr:.6f}", "best_ocw_frame_shift": best_shift,
        "best_ocw_frame_shift_ms": f"{best_shift * 1000 / FRAME_RATE:.1f}",
        "best_frame_corr_median": f"{sweep[best_shift]['corr_median']:.6f}",
        "zero_shift_frame_corr_median": f"{sweep[0]['corr_median']:.6f}",
        "frame_shift_sweep_json": json.dumps(sweep, separators=(",", ":")),
    }


def main() -> None:
    version = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=15, check=True)
    ffmpeg_version = version.stdout.splitlines()[0]
    sources = {row["video_id"]: row for row in locked_rows(SOURCE, SOURCE_SHA256)}
    flagged = [row for row in locked_rows(LANDMARKS, LANDMARKS_SHA256)
               if row["status"] == "review_low_correlation"]
    if len(sources) != 35 or len(flagged) != 3 or {row["video_id"] for row in flagged} != {"tKyaGnPni3U", "DvGNpuan4rw"}:
        raise ValueError("unexpected locked cohort or flagged landmarks")
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(check, row, sources[row["video_id"]]["ocw_mp4_url"], ffmpeg_version) for row in flagged]
        results = [job.result() for job in jobs]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)
    data = stream.getvalue().encode("utf-8")
    OUTPUT.write_bytes(data)
    print(f"rows={len(results)} sha256={hashlib.sha256(data).hexdigest()} output={OUTPUT}")


if __name__ == "__main__":
    main()
