"""Isolated worker adapters for the architecture-diverse ASR matrix."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments/registry/asr_architecture_candidates.yaml"


def registered_asr_candidates(path: Path = REGISTRY) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("architecture registry requires PyYAML") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != 6:
        raise RuntimeError("architecture registry must contain exactly six candidates")
    ids = [row.get("id") for row in rows]
    if len(set(ids)) != 6 or any(not str(value).startswith("RQ0_ARCH.A") for value in ids):
        raise RuntimeError("architecture candidate IDs must be unique RQ0_ARCH.A* IDs")
    return rows


class ArchitectureCandidateAdapter:
    """Keep each model in its compatible Python environment behind JSONL IPC."""

    def __init__(self, candidate: dict[str, Any]):
        self.candidate = candidate
        self.id = candidate["id"]
        self.model_size = candidate["model_repo"]
        self.device = candidate.get("device", "cuda")
        self.compute_type = candidate.get("compute_type", "fp16")
        self.model_revision = candidate["revision"]
        self.dependency_versions: dict[str, str] = {}
        self.load_gpu_memory: dict[str, int] = {}
        self.load_seconds = 0.0
        self._process: subprocess.Popen[str] | None = None

    def load(self) -> None:
        if self._process is not None:
            return
        group = self.candidate["package_group"]
        python = os.environ.get(f"ASR_ARCH_PYTHON_{group.upper()}") or os.environ.get("ASR_ARCH_PYTHON") or sys.executable
        python_path = Path(python)
        if not python_path.is_file():
            raise RuntimeError(f"blocked_dependency: Python environment not found for {group}: {python}")
        started = time.perf_counter()
        self._process = subprocess.Popen(
            [str(python_path), "-u", "-m", "experiments.evaluation.asr_architecture_worker",
             "--candidate-id", self.id], cwd=ROOT, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=None, text=True, encoding="utf-8", bufsize=1,
            env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        )
        response = self._request({"op": "load", "candidate": self.candidate})
        if response.get("status") != "ready":
            self.close()
            raise RuntimeError(response.get("error", "architecture_worker_load_failed"))
        self.dependency_versions = response.get("dependency_versions", {})
        self.load_gpu_memory = response.get("gpu_memory", {})
        self.load_seconds = time.perf_counter() - started

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("architecture worker is not running")
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()
        timeout_seconds = 1800 if payload.get("op") == "load" else 600
        lines: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_response() -> None:
            lines.put(process.stdout.readline())

        reader = threading.Thread(target=read_response, daemon=True)
        reader.start()
        try:
            line = lines.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            process.kill()
            process.wait()
            self._process = None
            for stream in (process.stdin, process.stdout):
                if stream and not stream.closed:
                    stream.close()
            raise TimeoutError(
                f"architecture_worker_timeout:{payload.get('op')}:{timeout_seconds}s"
            ) from exc
        if not line:
            code = process.poll()
            raise RuntimeError(f"architecture_worker_exited:{code}")
        response = json.loads(line)
        if response.get("status") == "error":
            raise RuntimeError(response.get("error", "architecture_worker_error"))
        return response

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000):
        from experiments.evaluation.asr_candidate_adapters import TranscriptResult

        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not samples.size or sample_rate != 16000 or not np.isfinite(samples).all():
            raise ValueError("canonical ASR input must be finite, non-empty mono 16 kHz float32")
        started = time.perf_counter()
        with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as handle:
            audio_path = Path(handle.name)
        try:
            np.save(audio_path, samples, allow_pickle=False)
            response = self._request({"op": "transcribe", "audio_path": str(audio_path)})
        finally:
            audio_path.unlink(missing_ok=True)
        raw_text = response.get("text")
        if not isinstance(raw_text, str):
            raise RuntimeError("architecture_worker_missing_transcript")
        # A blank ASR prediction is valid evidence: the scorer counts deletions.
        text = raw_text.strip()
        result = TranscriptResult(text=text,
                                  inference_seconds=float(response.get("inference_seconds", time.perf_counter() - started)))
        result.gpu_memory = response.get("gpu_memory", {})
        return result

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            if process.stdin and process.poll() is None:
                process.stdin.write('{"op":"close"}\n')
                process.stdin.flush()
                process.wait(timeout=10)
        except Exception:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
