"""Resume frozen RQ1 development features with a configurable visual device and VRAM guard.

The existing extractor and its receipts stay unchanged. Only train/validation
units from the frozen D2 source are admitted; final-test units are never read.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

from experiments.scripts.benchmark_artifacts import sha256_file
from experiments.scripts.rq1_learned_features import DEFAULT_OUTPUT, REPO, development_sources


DEFAULT_OCR_PYTHON = (
    REPO / "experiments/outputs/rq1_locked_mixed_20/venv_paddle_gpu/Scripts/python.exe"
)
DEFAULT_GUARD = {"max_gpu_used_mib": 3072, "min_gpu_free_mib": 2048,
                 "min_ram_free_mib": 2048, "poll_sec": 1.0}
PROGRESS_RE = re.compile(r"(?P<kind>OCR frames|DINOv2/OCR frames): (?P<done>\d+)/(?P<total>\d+)")


class ProgressLog:
    """Mirror timestamped runner events to the console and a flushed JSONL file."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.file = path.open("a", encoding="utf-8")

    def close(self) -> None:
        self.file.close()

    def emit(self, unit_id: str, stage: str, event: str, message: str,
             **details: object) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record = {"at_utc": timestamp, "unit_id": unit_id, "stage": stage,
                  "event": event, "message": message, **details}
        self.file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.file.flush()
        print(f"[{timestamp}] [{unit_id}] [{stage}] {message}", flush=True)


def _stage_from_output(line: str, current: str) -> tuple[str, dict]:
    progress = PROGRESS_RE.search(line)
    if progress:
        stage = "ocr_gpu" if progress["kind"] == "OCR frames" else "visual_encoding"
        return stage, {"done": int(progress["done"]),
                       "total": int(progress["total"])}
    if "ocr_chunks" in line and line.endswith("manifest.json"):
        return "models_text_audio", {}
    if "materialized learned features" in line:
        return "write_receipt", {}
    if line.startswith("verified "):
        return "verify", {}
    return current, {}


def gpu_memory_mib() -> tuple[int, int, int]:
    """Return used, free, total VRAM from the single NVIDIA GPU."""
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.free,memory.total",
         "--format=csv,noheader,nounits"],
        check=True, capture_output=True, text=True, timeout=8,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"expected one NVIDIA GPU, found {len(lines)}")
    fields = [field.strip() for field in lines[0].split(",")]
    if len(fields) != 3:
        raise RuntimeError(f"invalid nvidia-smi memory output: {lines[0]}")
    return tuple(int(field) for field in fields)


def check_resources(guard: dict) -> dict:
    used, free, total = gpu_memory_mib()
    ram_free = psutil.virtual_memory().available // (1024 * 1024)
    snapshot = {"gpu_used_mib": used, "gpu_free_mib": free,
                "gpu_total_mib": total, "ram_free_mib": ram_free}
    if (used >= guard["max_gpu_used_mib"]
            or free < guard["min_gpu_free_mib"]
            or ram_free < guard["min_ram_free_mib"]):
        raise RuntimeError(f"resource guard stopped the run: {snapshot}; limits={guard}")
    return snapshot


def stop_process_tree(process: subprocess.Popen) -> None:
    """Stop only this runner's child extractor and its OCR subprocess."""
    if process.poll() is not None:
        return
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            child.terminate()
        parent.terminate()
        _, alive = psutil.wait_procs(children + [parent], timeout=5)
        for member in alive:
            member.kill()
    except psutil.NoSuchProcess:
        pass
    finally:
        process.wait(timeout=10)


def _command(unit_id: str, ocr_python: Path, verify: bool,
             output: Path = DEFAULT_OUTPUT, visual_device: str = "cpu",
             visual_batch_size: int = 8) -> list[str]:
    command = [sys.executable, "-m", "experiments.scripts.rq1_learned_features",
               "--output", str(output)]
    if verify:
        command.append("--verify")
    else:
        command.extend(["--device", visual_device, "--visual-batch-size",
                        str(visual_batch_size), "--ocr-gpu",
                        "--ocr-python", str(ocr_python)])
    return command + [f"--unit-id={unit_id}"]


def _run_command(command: list[str], guard: dict, *, monitor: bool,
                 log: ProgressLog | None = None, unit_id: str = "",
                 stage: str = "verify", heartbeat_sec: float = 15.0) -> dict:
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    cpu_threads = int(env.get("RQ1_CPU_THREADS", "4"))
    if cpu_threads < 1:
        raise ValueError("RQ1_CPU_THREADS must be positive")
    env["OMP_NUM_THREADS"] = str(cpu_threads)
    env["MKL_NUM_THREADS"] = str(cpu_threads)
    env["PYTHONUNBUFFERED"] = "1"
    if monitor:
        first = check_resources(guard)
        low_free, peak_used = first["gpu_free_mib"], first["gpu_used_mib"]
    else:
        first, low_free, peak_used = {}, None, None
    process = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1,
                               errors="replace")
    lines: queue.SimpleQueue[str] = queue.SimpleQueue()
    if getattr(process, "stdout", None) is not None:
        def read_output() -> None:
            for raw in process.stdout:
                lines.put(raw.rstrip("\r\n"))

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
    else:
        reader = None

    started = time.monotonic()
    last_heartbeat = started
    current_stage = stage
    progress: dict = {}

    def drain_output() -> None:
        nonlocal current_stage, progress
        while True:
            try:
                line = lines.get_nowait()
            except queue.Empty:
                break
            current_stage, found = _stage_from_output(line, current_stage)
            if found:
                progress = found
            if log is None:
                print(line, flush=True)
            else:
                log.emit(unit_id, current_stage, "child_output", line, **found)

    try:
        while process.poll() is None:
            try:
                process.wait(timeout=min(guard["poll_sec"], heartbeat_sec))
            except subprocess.TimeoutExpired:
                pass
            drain_output()
            if monitor and process.poll() is None:
                snapshot = check_resources(guard)
                low_free = min(low_free, snapshot["gpu_free_mib"])
                peak_used = max(peak_used, snapshot["gpu_used_mib"])
            else:
                snapshot = {}
            now = time.monotonic()
            if log is not None and now - last_heartbeat >= heartbeat_sec:
                detail = f"elapsed={now - started:.0f}s"
                if progress:
                    detail += f" progress={progress['done']}/{progress['total']}"
                if snapshot:
                    detail += (f" RAM_free={snapshot['ram_free_mib']}MiB"
                               f" GPU_used={snapshot['gpu_used_mib']}MiB"
                               f" GPU_free={snapshot['gpu_free_mib']}MiB")
                log.emit(unit_id, current_stage, "heartbeat", detail,
                         elapsed_sec=round(now - started, 1),
                         resources=snapshot, progress=progress)
                last_heartbeat = now
        if reader is not None:
            reader.join(timeout=2)
        drain_output()
        if process.returncode != 0:
            raise RuntimeError(f"extractor exited with code {process.returncode}")
    except BaseException as exc:
        if log is not None:
            log.emit(unit_id, current_stage, "failed", str(exc))
        stop_process_tree(process)
        raise
    return {"gpu_free_before_mib": first.get("gpu_free_mib"),
            "gpu_free_low_mib": low_free, "gpu_used_peak_mib": peak_used}


def resume(output: Path, ocr_python: Path, guard: dict,
           max_new_units: int | None = None, unit_id: str | None = None,
           heartbeat_sec: float = 15.0, visual_device: str = "cpu",
           visual_batch_size: int = 8) -> dict:
    if visual_device not in {"cpu", "cuda"} or visual_batch_size < 1:
        raise ValueError("invalid visual device or batch size")
    if not ocr_python.is_file():
        raise FileNotFoundError(f"isolated OCR interpreter missing: {ocr_python}")
    rows = development_sources()
    if unit_id is not None:
        rows = [row for row in rows if row["unit_id"] == unit_id]
        if not rows:
            raise ValueError(f"unit is outside frozen train/validation split: {unit_id}")
    output.mkdir(parents=True, exist_ok=True)
    log_path = (output / "safe_resume_logs" /
                f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.jsonl")
    log = ProgressLog(log_path)
    try:
        log.emit("run", "setup", "log", f"log file: {log_path}")
        return _resume_logged(rows, output, ocr_python, guard, max_new_units,
                              heartbeat_sec, log, visual_device, visual_batch_size)
    finally:
        log.close()


def _resume_logged(rows: list[dict], output: Path, ocr_python: Path,
                   guard: dict, max_new_units: int | None,
                   heartbeat_sec: float, log: ProgressLog,
                   visual_device: str, visual_batch_size: int) -> dict:
    existing, missing = [], []
    for row in rows:
        uid = row["unit_id"]
        tensor = output / f"{uid}.pt"
        receipt = output / f"{uid}.receipt.json"
        if tensor.is_file() and receipt.is_file():
            existing.append(row)
        else:
            missing.append(row)
    for row in existing:
        log.emit(row["unit_id"], "verify", "start", "verifying existing tensor and receipt")
        _run_command(_command(row["unit_id"], ocr_python, True, output),
                     guard, monitor=False, log=log, unit_id=row["unit_id"],
                     heartbeat_sec=heartbeat_sec)
        log.emit(row["unit_id"], "verify", "complete", "existing tensor verified")
    missing.sort(key=lambda row: (row["duration_sec"], row["unit_id"]))
    selected = missing if max_new_units is None else missing[:max_new_units]
    completed = []
    for row in selected:
        uid = row["unit_id"]
        log.emit(uid, "ocr_gpu", "start",
                 f"starting {row['split']} unit; duration={row['duration_sec']}s; "
                 f"OCR on GPU, visual encoding on {visual_device} (batch {visual_batch_size})")
        usage = _run_command(_command(uid, ocr_python, False, output,
                                      visual_device, visual_batch_size),
                             guard, monitor=True, log=log, unit_id=uid,
                             stage="ocr_gpu", heartbeat_sec=heartbeat_sec)
        log.emit(uid, "verify", "start", "checking tensor and feature receipt")
        _run_command(_command(uid, ocr_python, True, output), guard, monitor=False,
                     log=log, unit_id=uid, heartbeat_sec=heartbeat_sec)
        tensor = output / f"{uid}.pt"
        receipt = output / f"{uid}.receipt.json"
        run_receipt = {
            "schema": "rq1-safe-resume-receipt/1", "unit_id": uid,
            "split": row["split"], "visual_compute": visual_device,
            "visual_batch_size": visual_batch_size, "ocr_compute": "gpu",
            "media_sha256": row["media_sha256"],
            "tensor_sha256": sha256_file(tensor),
            "feature_receipt_sha256": sha256_file(receipt),
            "safe_runner_sha256": sha256_file(Path(__file__)),
            "guard": guard, "observed": usage,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        destination = output / "safe_resume_receipts" / f"{uid}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".json.partial")
        temporary.write_text(json.dumps(run_receipt, indent=2) + "\n", encoding="utf-8")
        temporary.replace(destination)
        completed.append(uid)
        log.emit(uid, "complete", "complete", "tensor and receipt verified",
                 observed=usage)
    result = {"verified_existing": [row["unit_id"] for row in existing],
              "completed_now": completed, "remaining": len(missing) - len(selected)}
    log.emit("run", "complete", "summary", json.dumps(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ocr-python", type=Path, default=DEFAULT_OCR_PYTHON)
    parser.add_argument("--unit-id")
    parser.add_argument("--max-new-units", type=int)
    parser.add_argument("--visual-device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--visual-batch-size", type=int, default=8)
    parser.add_argument("--max-gpu-used-mib", type=int,
                        default=DEFAULT_GUARD["max_gpu_used_mib"])
    parser.add_argument("--min-gpu-free-mib", type=int,
                        default=DEFAULT_GUARD["min_gpu_free_mib"])
    parser.add_argument("--min-ram-free-mib", type=int,
                        default=DEFAULT_GUARD["min_ram_free_mib"])
    parser.add_argument("--poll-sec", type=float, default=DEFAULT_GUARD["poll_sec"])
    parser.add_argument("--heartbeat-sec", type=float, default=15.0,
                        help="seconds between live stage/resource updates")
    args = parser.parse_args()
    if args.max_new_units is not None and args.max_new_units < 1:
        parser.error("--max-new-units must be >= 1")
    guard = {"max_gpu_used_mib": args.max_gpu_used_mib,
             "min_gpu_free_mib": args.min_gpu_free_mib,
             "min_ram_free_mib": args.min_ram_free_mib,
             "poll_sec": args.poll_sec}
    if any(value <= 0 for value in guard.values()):
        parser.error("guard thresholds must be positive")
    if args.heartbeat_sec <= 0:
        parser.error("--heartbeat-sec must be positive")
    if args.visual_batch_size < 1:
        parser.error("--visual-batch-size must be positive")
    result = resume(args.output, args.ocr_python.resolve(), guard,
                    args.max_new_units, args.unit_id, args.heartbeat_sec,
                    args.visual_device, args.visual_batch_size)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
