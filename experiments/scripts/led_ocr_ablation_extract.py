"""Phase 2 of the LED OCR ablation: run the real pipeline once per video up to the summary step and keep its inputs.

The app already writes `storage/checkpoints/{job_id}.json` right before summarization (utterances, keyframes,
chapters, visual_result) and deletes it after a successful job. The harness replaces `Summarizer.process` with a
stub that copies that file and returns an empty result, so the app code runs unmodified. Both arms of phase 3 read
the copied file, so transcript, keyframes and OCR are shared.

Videos live on a private drive, never in the repo. A failed video is a ledger row, not a rerun. A video that has no
ledger row (the session died) is processed again on resume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import subprocess
import time
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path

PROTOCOL_ID = "led-ocr-ablation-261110-v1"
EXTRACTION_ENV = {
    "SCENE_SEGMENTER": "slide", "ENABLE_FLORENCE_CAPTIONING": "false", "ENABLE_OBJECT_TRACKING": "false",
    "HF_TOKEN": "", "ASR_ENGLISH_BACKEND": "qwen3",
}
# Only settings the protocol cares about are written to the env dump (allowlist: .env may hold secrets).
ENV_DUMP_PREFIXES = ("SCENE_SEGMENTER", "SLIDE_", "ASR_", "LED_", "SUMMARIZER_", "ENABLE_", "FLORENCE_", "SPRINT_", "FASTER_WHISPER", "HF_TOKEN")
PINNED = {"SCENE_SEGMENTER": "slide", "ENABLE_FLORENCE_CAPTIONING": False, "ENABLE_OBJECT_TRACKING": False,
          "ASR_ENGLISH_BACKEND": "qwen3", "SUMMARIZER_ENGLISH_BACKEND": "led"}


_T0 = time.time()


def log(message: str) -> None:
    """Timestamped console line; the notebook also tees the stream to a Drive log file."""
    print(f"[ablation {datetime.now():%H:%M:%S} +{time.time() - _T0:.0f}s] {message}", flush=True)


def gpu_line() -> str:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or "nvidia-smi: no output"
    except Exception as error:  # noqa: BLE001
        return f"nvidia-smi unavailable: {type(error).__name__}"


def log_traceback(folder: Path, video_id: str) -> None:
    """Full traceback goes to a private log next to the run files, never into a receipt."""
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "errors.log").open("a", encoding="utf-8") as handle:
        handle.write(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} {video_id}\n{traceback.format_exc()}\n")


def video_slug(video_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in video_id)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict]:
    """All JSONL rows; a torn last line (session died mid-write) is ignored, any other bad line raises."""
    if not path.exists():
        return []
    rows, lines = [], path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise
    return rows


def read_ledger(path: Path) -> dict[str, dict]:
    """Last row per id."""
    return {row["id"]: row for row in read_rows(path)}


def append_ledger(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.read_bytes().endswith(b"\n") and path.stat().st_size:
        data = path.read_bytes()
        path.write_bytes(data[: data.rfind(b"\n") + 1])  # cut a torn last line
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def pending(videos: list[dict], ledger: dict[str, dict]) -> list[dict]:
    """Videos without a ledger row. A row (ok or error) is final: no rerun to change a result."""
    return [v for v in videos if v["id"] not in ledger]


def download(video: dict, directory: Path, ledger_path: Path) -> dict:
    """Fetch one video to the private drive; a broken link is recorded, never replaced."""
    target = directory / f"{video_slug(video['id'])}.mp4"
    row = {"id": video["id"], "url": video["media_url"], "path": str(target)}
    if target.exists():
        return {**row, "status": "ok", "bytes": target.stat().st_size, "sha256": sha256_file(target)}
    part = target.with_suffix(".part")
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(video["media_url"], timeout=60) as response, part.open("wb") as handle:
            shutil.copyfileobj(response, handle, 1024 * 1024)
        part.replace(target)
        row.update(status="ok", bytes=target.stat().st_size, sha256=sha256_file(target))
    except Exception as error:  # noqa: BLE001 - recorded, no substitute video
        log_traceback(directory.parent / "run" / "logs", video["id"])
        part.unlink(missing_ok=True)
        row.update(status="error", error=type(error).__name__)
    append_ledger(ledger_path, row)
    return row


def redacted_settings(settings: dict) -> dict:
    """Allowlisted settings only; HF_TOKEN is reported as set/unset, never its value."""
    out = {k: v for k, v in settings.items() if k.upper().startswith(ENV_DUMP_PREFIXES)}
    if "HF_TOKEN" in out:
        out["HF_TOKEN"] = "<set>" if out["HF_TOKEN"] else ""
    return out


def assert_pinned_settings(settings) -> None:
    """Stop when the live settings (defaults or a stray .env) differ from the protocol."""
    wrong = {k: getattr(settings, k) for k, v in PINNED.items() if getattr(settings, k) != v}
    if getattr(settings, "HF_TOKEN", ""):
        wrong["HF_TOKEN"] = "<set>"
    if wrong:
        raise SystemExit(f"settings differ from the protocol: {wrong}")


def assert_app_commit(app_root: Path, protocol_dir: Path) -> None:
    import subprocess

    expected = json.loads((protocol_dir / "protocol.json").read_text(encoding="utf-8"))["app"]["commit"]
    actual = subprocess.run(["git", "-C", str(app_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if actual != expected:
        raise SystemExit(f"app checkout {actual} is not the frozen commit {expected}")


def assert_private_dir(path: Path) -> None:
    """Transcripts and summaries must never land inside a repository checkout."""
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise SystemExit(f"{path} is inside a repository; use a private folder")


def make_stub(checkpoint_path_for, destination: Path, captured: dict):
    """Replacement for Summarizer.process: copy the pre-summary checkpoint, return a valid empty result."""

    def process(self, utterances, slides, chapters, job_id="unknown", output_language="en", summary_length="medium"):
        source = checkpoint_path_for(job_id)
        if not source.exists():
            raise FileNotFoundError("pre-summary checkpoint missing")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        captured["copied"] = True
        return {"video_title": "extract-only", "summary": "", "chapters": chapters, "key_takeaways": [],
                "model_used": "extract-only", "summary_method": "extract_only", "fallback_used": False}

    return process


def describe_inputs(checkpoint: dict, merge) -> dict:
    """Descriptive counts from the copied checkpoint. `merge` is merge_speech_and_ocr, injected for tests."""
    data = checkpoint["data"]
    keyframes = data.get("keyframes") or []
    utterances = data.get("utterances") or []
    visual = data.get("visual_result") or {}
    audio = data.get("audio_result") or {}
    _, stats = merge(utterances, keyframes)
    return {
        "segmenter": visual.get("segmenter"), "scenes": len(visual.get("scenes") or []),
        "keyframes": len(keyframes), "keyframes_with_ocr": sum(1 for k in keyframes if (k.get("ocr_text") or "").strip()),
        "raw_ocr_words": sum(len((k.get("ocr_text") or "").split()) for k in keyframes),
        "utterances": len(utterances), "merge_transcript_words": stats["transcript_words"],
        "merge_ocr_words": stats["ocr_words"], "merge_slides_used": stats["slides_used"],
        "asr_model": audio.get("asr_model"), "language": audio.get("language"),
    }


def extract_one(video: dict, video_path: Path, inputs_dir: Path, run_task, checkpoint_path_for, merge) -> dict:
    """Run the pipeline for one video. `run_task(job_id, path)` returns the task result dict."""
    job_id = f"ocrabl-{video_slug(video['id'])}"
    destination = inputs_dir / f"{video_slug(video['id'])}.json"
    captured: dict = {}
    started = time.perf_counter()
    row = {"id": video["id"], "stratum": video["stratum"], "job_id": job_id}
    try:
        from_stub = make_stub(checkpoint_path_for, destination, captured)
        result = run_task(job_id, str(video_path), from_stub)
        if not captured.get("copied"):
            raise RuntimeError("summarizer stub was never reached")
        checkpoint = json.loads(destination.read_text(encoding="utf-8"))
        asr_model = str((checkpoint["data"].get("audio_result") or {}).get("asr_model"))
        if "qwen3" not in asr_model.lower():
            # The protocol fixes ASR to Qwen3. A fallback engine means a pipeline problem, not a result:
            # keep no input, write no ledger row, and let a later run process the video again.
            destination.unlink(missing_ok=True)
            row.update(status="asr_fallback", detail=f"ASR engine was {asr_model}, expected Qwen3-ASR")
            row["wall_seconds"] = round(time.perf_counter() - started, 1)
            return row
        row.update(status="ok", input_path=str(destination), input_sha256=sha256_file(destination),
                   input_bytes=destination.stat().st_size, pipeline_seconds=result.get("processing_time"),
                   **describe_inputs(checkpoint, merge))
    except Exception as error:  # noqa: BLE001 - ledger row, no rerun
        log_traceback(inputs_dir.parent / "logs", video["id"])
        row.update(status="error", error=type(error).__name__, detail=str(error)[:200])
    row["wall_seconds"] = round(time.perf_counter() - started, 1)
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app-root", required=True, help="multimodal-lecture-summarizer app folder (cwd for the pipeline)")
    parser.add_argument("--videos-dir", required=True, help="private drive folder for downloaded videos")
    parser.add_argument("--out-dir", required=True, help="private output folder: inputs/, ledgers")
    parser.add_argument("--set", choices=("smoke", "cohort"), required=True)
    parser.add_argument("--protocol-dir", required=True, help="registry folder holding the frozen cohort.json")
    args = parser.parse_args(argv)

    protocol_dir, out_dir = Path(args.protocol_dir).resolve(), Path(args.out_dir).resolve()
    videos_dir, app_root = Path(args.videos_dir).resolve(), Path(args.app_root).resolve()
    cohort = json.loads((protocol_dir / "cohort.json").read_text(encoding="utf-8"))
    videos = cohort["smoke_videos" if args.set == "smoke" else "videos"]
    suffix = args.set
    download_ledger, extract_ledger = out_dir / f"download_ledger_{suffix}.jsonl", out_dir / f"extract_ledger_{suffix}.jsonl"
    inputs_dir = out_dir / "inputs"

    assert_app_commit(app_root, protocol_dir)
    assert_private_dir(out_dir)
    assert_private_dir(videos_dir)
    os.chdir(app_root)
    sys.path.insert(0, str(app_root))
    os.environ.update(EXTRACTION_ENV)
    from ai_workers.core.checkpoint import CheckpointManager
    from ai_workers.core.config import worker_settings
    from ai_workers.modules.summarization.ocr_evidence import merge_speech_and_ocr
    from ai_workers.modules.summarization.summarizer import Summarizer
    from ai_workers.tasks import process_video

    assert_pinned_settings(worker_settings)
    (out_dir / f"extract_env_{suffix}.json").write_text(
        json.dumps(redacted_settings(worker_settings.model_dump()), indent=2, sort_keys=True, default=str), encoding="utf-8")
    manager = CheckpointManager()
    process_video.update_state = lambda *a, **k: None  # no Redis result backend outside the worker

    def run_task(job_id: str, path: str, stub):
        original = Summarizer.process
        Summarizer.process = stub
        try:
            return process_video.run(job_id, path, "hybrid", "en", "detailed", "en")
        finally:
            Summarizer.process = original

    done = read_ledger(extract_ledger)
    todo = pending(videos, done)
    log(f"set={args.set}: {len(videos)} videos, {len(done)} already in the ledger, {len(todo)} to do; app={app_root}")
    log(f"GPU: {gpu_line()}")
    fallbacks: list[str] = []
    for index, video in enumerate(todo, 1):
        log(f"[{index}/{len(todo)}] {video['id']} ({video['stratum']}, {video['duration_s']}s, {video['size_mb']} MB): download")
        fetched = download(video, videos_dir, download_ledger)
        if fetched["status"] != "ok":
            log(f"[{index}/{len(todo)}] {video['id']}: download FAILED ({fetched.get('error')}); no substitute video")
            append_ledger(extract_ledger, {"id": video["id"], "stratum": video["stratum"], "status": "error",
                                           "error": "download_failed"})
            continue
        log(f"[{index}/{len(todo)}] {video['id']}: video ready ({fetched['bytes'] / 1e6:.0f} MB, sha256 {fetched['sha256'][:12]}), running pipeline")
        row = extract_one(video, Path(fetched["path"]), inputs_dir, run_task, manager._get_checkpoint_path, merge_speech_and_ocr)
        if row["status"] == "asr_fallback":
            fallbacks.append(video["id"])
            log(f"[{index}/{len(todo)}] {video['id']}: ASR FALLBACK after {row['wall_seconds']}s: {row['detail']}. "
                "No ledger row written; fix Qwen3-ASR and rerun this cell to process the video again.")
            log(f"GPU: {gpu_line()}")
            continue
        append_ledger(extract_ledger, row)
        if row["status"] == "ok":
            log(f"[{index}/{len(todo)}] {video['id']}: OK in {row['wall_seconds']}s | segmenter={row['segmenter']} scenes={row['scenes']} "
                f"keyframes={row['keyframes']} with_ocr={row['keyframes_with_ocr']} raw_ocr_words={row['raw_ocr_words']} | "
                f"transcript_words={row['merge_transcript_words']} ocr_words_in_input={row['merge_ocr_words']} slides_used={row['merge_slides_used']} | "
                f"asr={row['asr_model']} lang={row['language']} | input {row['input_bytes'] / 1e3:.0f} KB sha256 {row['input_sha256'][:12]}")
        else:
            log(f"[{index}/{len(todo)}] {video['id']}: ERROR {row['error']} after {row['wall_seconds']}s: {row.get('detail')} (traceback in run/logs/errors.log)")
        log(f"GPU: {gpu_line()}")
    final = read_ledger(extract_ledger)
    if fallbacks:
        log(f"NOT PROCESSED (Qwen3-ASR fell back): {fallbacks}")
    log(f"finished: {sum(r.get('status') == 'ok' for r in final.values())} ok, {sum(r.get('status') == 'error' for r in final.values())} error of {len(videos)}")
    return 1 if fallbacks else 0


if __name__ == "__main__":
    raise SystemExit(main())
