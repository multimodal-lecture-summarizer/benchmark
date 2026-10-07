"""Compare bounded decoded HF/OCW A/V near three fragment marks per selected video."""

from __future__ import annotations

import csv
import hashlib
import io
import os
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from scipy.signal import correlate


ROOT = Path(__file__).resolve().parents[2]
REVISION = "f5a5047e040ecf0f80a3cb67d64e324407f323ec"
SOURCE = ROOT / "plans/reports/mitfld-rq1-35-260928-1135-ocw-source-rights-ledger.csv"
SOURCE_SHA256 = "36419f9a3209405647a854032ce7b7acd654dad7fc4086d68aedcb7b44019d10"
ANNOTATIONS = ROOT / "plans/reports/mitfld-rq1-35-260928-1126-annotation-ledger.csv"
CHECKPOINT = ROOT / "plans/reports/mitfld-rq1-35-260928-1214-landmark-in-progress.csv"
OUTPUT = ROOT / "plans/reports/mitfld-rq1-35-260928-1214-three-landmark-ledger.csv"
FIELDS = (
    "video_id", "course_id", "split_proposed", "mark_role", "frag_s", "frames_each",
    "frame_corr_min", "frame_corr_max", "frame_mae_max_255", "audio_corr_best",
    "audio_lag_samples_4000hz", "status", "error",
)
DECODE_TIMEOUT = int(os.environ.get("RQ1_FFMPEG_TIMEOUT", "40"))


def get_marks(video_id: str, expected_hash: str) -> list[tuple[str, float]]:
    url = f"https://huggingface.co/datasets/robotwang/MITFLD/resolve/{REVISION}/frags/{video_id}.json"
    with urllib.request.urlopen(url, timeout=20) as response:
        body = response.read(100_001)
    if len(body) > 100_000 or hashlib.sha256(body).hexdigest() != expected_hash:
        raise ValueError(f"fragment file changed for {video_id}")
    import json
    marks = [float(value) for value in json.loads(body) if float(value) > 0]
    if len(marks) < 2:
        raise ValueError(f"too few internal marks for {video_id}")
    choices = [("first", marks[0]), ("middle", marks[len(marks) // 2]), ("last", marks[-1])]
    return [(role, mark) for role, mark in choices if not any(mark == prior for _, prior in choices[:choices.index((role, mark))])]


def decode(url: str, second: float) -> tuple[np.ndarray, np.ndarray]:
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    common = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{second:.3f}", "-i", url, "-t", "3"]
    video = subprocess.run(
        common + ["-an", "-vf", "fps=1,scale=64:36,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=DECODE_TIMEOUT, env=env,
    )
    if video.returncode != 0:
        raise RuntimeError(video.stderr[-400:].decode("utf-8", errors="replace"))
    audio = subprocess.run(
        common + ["-vn", "-ac", "1", "-ar", "4000", "-f", "s16le", "-"],
        capture_output=True, timeout=DECODE_TIMEOUT, env=env,
    )
    if audio.returncode != 0:
        raise RuntimeError(audio.stderr[-400:].decode("utf-8", errors="replace"))
    frames = np.frombuffer(video.stdout, dtype=np.uint8)
    samples = np.frombuffer(audio.stdout, dtype=np.int16)
    if frames.size < 2 * 64 * 36 or samples.size < 4000:
        raise ValueError("decoded window too short")
    return frames.reshape(-1, 64 * 36).astype(np.float32), samples.astype(np.float32)


def compare_audio(hf: np.ndarray, ocw: np.ndarray) -> tuple[float, int]:
    hf = hf - hf.mean()
    ocw = ocw - ocw.mean()
    raw = correlate(ocw, hf, mode="full", method="fft")
    zero = len(hf) - 1
    lo, hi = max(0, zero - 600), min(len(raw), zero + 601)
    lag = int(np.argmax(raw[lo:hi]) + lo - zero)
    if lag >= 0:
        a, b = hf[: min(len(hf), len(ocw) - lag)], ocw[lag: lag + len(hf)]
    else:
        a, b = hf[-lag: -lag + len(ocw)], ocw[: min(len(ocw), len(hf) + lag)]
    size = min(len(a), len(b))
    a, b = a[:size], b[:size]
    if size < 4000 or a.std() < 1 or b.std() < 1:
        raise ValueError("audio window silent or too short")
    return float(np.corrcoef(a, b)[0, 1]), lag


def check_one(row: dict[str, str], marks: list[tuple[str, float]]) -> list[dict[str, object]]:
    video_id = row["video_id"]
    hf_url = f"https://huggingface.co/datasets/robotwang/MITFLD/resolve/{REVISION}/videos/{video_id}.mp4"
    results: list[dict[str, object]] = []
    for role, second in marks:
        result: dict[str, object] = {
            "video_id": video_id, "course_id": row["course_id"],
            "split_proposed": row["split_proposed"], "mark_role": role, "frag_s": second,
        }
        try:
            hf_frames, hf_audio = decode(hf_url, second)
            ocw_frames, ocw_audio = decode(row["ocw_mp4_url"], second)
            count = min(len(hf_frames), len(ocw_frames))
            frame_corr = [float(np.corrcoef(hf_frames[i], ocw_frames[i])[0, 1])
                          for i in range(count) if hf_frames[i].std() >= 1 and ocw_frames[i].std() >= 1]
            if not frame_corr:
                raise ValueError("no nonconstant paired frames")
            mae = max(float(np.abs(hf_frames[i] - ocw_frames[i]).mean()) for i in range(count))
            audio_corr, lag = compare_audio(hf_audio, ocw_audio)
            result.update({
                "frames_each": count, "frame_corr_min": f"{min(frame_corr):.6f}",
                "frame_corr_max": f"{max(frame_corr):.6f}",
                "frame_mae_max_255": f"{mae:.3f}", "audio_corr_best": f"{audio_corr:.6f}",
                "audio_lag_samples_4000hz": lag,
                "status": "local_av_match" if min(frame_corr) >= 0.95 and audio_corr >= 0.90 else "review_low_correlation",
            })
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            result["status"] = "decode_or_compare_failed"
            result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
    return results


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("source ledger changed")
    source = list(csv.DictReader(io.StringIO(source_bytes.decode("utf-8"))))
    annotations = {row["video_id"]: row for row in csv.DictReader(ANNOTATIONS.open(encoding="utf-8", newline=""))}
    if len(source) != 35 or set(annotations) != {row["video_id"] for row in source}:
        raise ValueError("selected and annotation ID sets differ")
    jobs = [(row, get_marks(row["video_id"], annotations[row["video_id"]]["frags_sha256"])) for row in source]
    expected = {(row["video_id"], role) for row, marks in jobs for role, _ in marks}
    existing = list(csv.DictReader(CHECKPOINT.open(encoding="utf-8", newline=""))) if CHECKPOINT.exists() else []
    done = {(row["video_id"], row["mark_role"]) for row in existing}
    if len(done) != len(existing) or not done <= expected:
        raise ValueError("checkpoint has duplicate or unexpected landmarks")
    pending = [(row, [(role, mark) for role, mark in marks if (row["video_id"], role) not in done])
               for row, marks in jobs if any((row["video_id"], role) not in done for role, _ in marks)]
    with CHECKPOINT.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not existing:
            writer.writeheader()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(check_one, row, marks): row["video_id"] for row, marks in pending}
            for future in as_completed(futures):
                records = future.result()
                writer.writerows(records)
                stream.flush()
                print(f"completed {futures[future]} ({len(records)} marks)", flush=True)
    rows = list(csv.DictReader(CHECKPOINT.open(encoding="utf-8", newline="")))
    if {(row["video_id"], row["mark_role"]) for row in rows} != expected:
        raise ValueError("landmark checkpoint incomplete")
    order = {row["video_id"]: i for i, row in enumerate(source)}
    role_order = {"first": 0, "middle": 1, "last": 2}
    rows.sort(key=lambda row: (order[row["video_id"]], role_order[row["mark_role"]]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue().encode("utf-8")
    if OUTPUT.exists() and OUTPUT.read_bytes() != content:
        raise ValueError("locked final landmark ledger differs")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(content)
    print(f"videos={len(source)} landmarks={len(rows)} statuses="
          f"{{'match': {sum(row['status']=='local_av_match' for row in rows)}, "
          f"'review': {sum(row['status']=='review_low_correlation' for row in rows)}, "
          f"'failed': {sum(row['status']=='decode_or_compare_failed' for row in rows)}}}")


if __name__ == "__main__":
    main()
