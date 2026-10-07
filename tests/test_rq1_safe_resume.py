"""Safety checks for the one-unit-at-a-time RQ1 development runner."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import rq1_safe_resume as runner


def test_negative_id_command_keeps_visual_on_cpu():
    command = runner._command("-7xg8pGcP6w", Path("ocr-python.exe"), False)
    assert command[-1] == "--unit-id=-7xg8pGcP6w"
    assert command[command.index("--device") + 1] == "cpu"
    assert "--ocr-gpu" in command


def test_cuda_visual_command_passes_batch_size():
    command = runner._command("unit", Path("ocr-python.exe"), False,
                              visual_device="cuda", visual_batch_size=16)
    assert command[command.index("--device") + 1] == "cuda"
    assert command[command.index("--visual-batch-size") + 1] == "16"


def test_gpu_guard_fails_closed_on_low_free_memory(monkeypatch):
    monkeypatch.setattr(runner, "gpu_memory_mib", lambda: (3900, 1800, 6141))
    monkeypatch.setattr(runner.psutil, "virtual_memory",
                        lambda: SimpleNamespace(available=8 * 1024**3))
    with pytest.raises(RuntimeError, match="resource guard stopped"):
        runner.check_resources(runner.DEFAULT_GUARD)


def test_parallel_colab_worker_limits_cpu_threads(monkeypatch):
    captured = {}

    class CompletedProcess:
        stdout = None
        returncode = 0

        def poll(self):
            return 0

    def popen(*args, **kwargs):
        captured.update(kwargs["env"])
        return CompletedProcess()

    monkeypatch.setenv("RQ1_CPU_THREADS", "1")
    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    runner._run_command(["fixture"], runner.DEFAULT_GUARD, monitor=False)
    assert captured["OMP_NUM_THREADS"] == "1"
    assert captured["MKL_NUM_THREADS"] == "1"


def test_watchdog_stops_only_its_child_when_guard_trips(monkeypatch):
    class RunningProcess:
        returncode = None

        def poll(self):
            return None

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("extractor", timeout)

    process = RunningProcess()
    stopped = []
    snapshots = iter([{"gpu_free_mib": 5000, "gpu_used_mib": 500}, None])

    def check(_guard):
        value = next(snapshots)
        if value is None:
            raise RuntimeError("resource guard stopped the run")
        return value

    monkeypatch.setattr(runner, "check_resources", check)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runner, "stop_process_tree", lambda child: stopped.append(child))
    with pytest.raises(RuntimeError, match="resource guard stopped"):
        runner._run_command(["extractor"], runner.DEFAULT_GUARD, monitor=True)
    assert stopped == [process]


def test_stop_process_tree_terminates_own_sleeping_child():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        runner.stop_process_tree(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_resume_prefers_shortest_missing_unit_and_writes_bound_receipt(
    tmp_path, monkeypatch,
):
    interpreter = tmp_path / "ocr-python.exe"
    interpreter.write_bytes(b"fixture")
    output = tmp_path / "features"
    rows = [
        {"unit_id": "long", "split": "train", "duration_sec": 90,
         "media_sha256": "media-long"},
        {"unit_id": "short", "split": "validation", "duration_sec": 10,
         "media_sha256": "media-short"},
    ]
    monkeypatch.setattr(runner, "development_sources", lambda: rows)
    calls = []

    def run_command(command, guard, *, monitor, **kwargs):
        calls.append((command[-1], monitor))
        if monitor:
            uid = command[-1].split("=", 1)[1]
            (output / f"{uid}.pt").write_bytes(b"tensor")
            (output / f"{uid}.receipt.json").write_text("{}", encoding="utf-8")
        return {"gpu_free_before_mib": 5000, "gpu_free_low_mib": 4500,
                "gpu_used_peak_mib": 700}

    monkeypatch.setattr(runner, "_run_command", run_command)
    result = runner.resume(output, interpreter, runner.DEFAULT_GUARD, max_new_units=1)
    assert result == {"verified_existing": [], "completed_now": ["short"], "remaining": 1}
    assert calls == [("--unit-id=short", True), ("--unit-id=short", False)]
    receipt = json.loads((output / "safe_resume_receipts/short.json").read_text())
    assert receipt["visual_compute"] == "cpu" and receipt["ocr_compute"] == "gpu"
    assert receipt["tensor_sha256"] == runner.sha256_file(output / "short.pt")


def test_progress_log_records_child_stage_and_idle_heartbeat(tmp_path, capsys):
    log = runner.ProgressLog(tmp_path / "progress.jsonl")
    command = [sys.executable, "-u", "-c",
               "import time; print('  OCR frames: 2/4', flush=True); "
               "time.sleep(0.3); print('  DINOv2/OCR frames: 4/4', flush=True)"]
    try:
        runner._run_command(command, {**runner.DEFAULT_GUARD, "poll_sec": 0.05},
                            monitor=False, log=log, unit_id="fixture",
                            stage="ocr_gpu", heartbeat_sec=0.1)
    finally:
        log.close()
    records = [json.loads(line) for line in (tmp_path / "progress.jsonl").read_text().splitlines()]
    assert any(record["stage"] == "ocr_gpu" and record["done"] == 2
               for record in records)
    assert any(record["stage"] == "visual_encoding" and record["done"] == 4
               for record in records)
    assert any(record["event"] == "heartbeat" for record in records)
    assert "[fixture] [visual_encoding]" in capsys.readouterr().out
