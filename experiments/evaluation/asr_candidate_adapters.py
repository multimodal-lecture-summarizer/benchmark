"""Versioned execution adapters for the six registered TED-LIUM ASR systems."""
from __future__ import annotations

import gc
import importlib.metadata
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _cached_snapshot(repo: str, revision: str) -> str:
    """Use only the exact model revision downloaded during Colab setup."""
    from huggingface_hub import snapshot_download

    snapshot = Path(snapshot_download(repo_id=repo, revision=revision, local_files_only=True))
    if snapshot.name != revision:
        raise RuntimeError(f"blocked_unpinned_model: expected {revision}, got {snapshot}")
    return str(snapshot)


@dataclass
class TranscriptResult:
    text: str
    inference_seconds: float
    preprocessing_seconds: float = 0.0
    alignment_seconds: float = 0.0
    word_segments: list[dict[str, Any]] | None = None


class CandidateAdapter:
    """One candidate, loaded once and reused for a deterministic unit shard."""

    def __init__(self, candidate: dict[str, Any]):
        self.candidate = candidate
        self.id = candidate["id"]
        self.kwargs = dict(candidate.get("model_kwargs", {}))
        self.model = None
        self.processor = None
        self.tokenizer = None
        self.align_model = None
        self.align_metadata = None
        self.denoiser = None
        self.load_seconds = 0.0
        self.dependency_versions = {}

    def _version(self, package: str) -> str:
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            raise RuntimeError(f"blocked_dependency: missing package {package}")

    def load(self) -> None:
        started = time.perf_counter()
        suffix = self.id.split(".", 1)[-1]
        if suffix.startswith("A0_") or suffix.startswith("A1_") or suffix.startswith("A3_"):
            self.dependency_versions["faster-whisper"] = self._version("faster-whisper")
            from faster_whisper import WhisperModel

            revision = self.kwargs.get("revision")
            if not isinstance(revision, str) or len(revision) != 40:
                raise RuntimeError(f"blocked_unpinned_model: {self.id} has no immutable weight revision")
            size = self.kwargs["model_size"]
            device, compute = self.kwargs["device"], self.kwargs["compute_type"]
            if suffix == "A0_WhisperBase" and (device, compute) != ("cpu", "int8"):
                raise RuntimeError("blocked_configuration: A0 must remain CPU int8")
            if suffix != "A0_WhisperBase" and device != "cuda":
                raise RuntimeError(f"blocked_configuration: {self.id} requires CUDA")
            repo = self.kwargs["model_repo"]
            self.model = WhisperModel(_cached_snapshot(repo, revision), device=device,
                                      compute_type=compute)
            self.model_size, self.device, self.compute_type = size, device, compute
            self.model_revision = revision
        elif suffix == "A2_DistilWhisper":
            self.dependency_versions["transformers"] = self._version("transformers")
            self.dependency_versions["torch"] = self._version("torch")
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

            name = self.kwargs["model_name"]
            revision = self.kwargs.get("revision")
            if not isinstance(revision, str) or len(revision) != 40:
                raise RuntimeError(f"blocked_unpinned_model: {self.id} has no immutable weight revision")
            processor_revision = self.kwargs.get("processor_revision")
            if not isinstance(processor_revision, str) or len(processor_revision) != 40:
                raise RuntimeError(f"blocked_unpinned_model: {self.id} has no immutable processor revision")
            if self.kwargs.get("device") != "cuda" or not torch.cuda.is_available():
                raise RuntimeError("blocked_resource: candidate A2 requires CUDA")
            self.processor = AutoProcessor.from_pretrained(
                _cached_snapshot(name, processor_revision), local_files_only=True)
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                _cached_snapshot(name, revision), torch_dtype=torch.float16,
                low_cpu_mem_usage=True, use_safetensors=True, local_files_only=True
            ).to("cuda")
            generation = self.model.generation_config
            if (getattr(generation, "is_multilingual", None) is not False
                    or getattr(generation, "forced_decoder_ids", None) != [[1, 50362]]):
                raise RuntimeError("blocked_configuration: unexpected English-only Distil-Whisper generation config")
            # This old checkpoint also records language/task defaults, but has
            # no lang_to_id/task_to_id maps for Transformers 4.57.6. Keep its
            # no-timestamps token; the checkpoint itself is English-only.
            generation.language = None
            generation.task = None
            self.device, self.model_size = "cuda", name
            self.model_revision = revision
        elif suffix == "A4_WhisperX":
            self.dependency_versions["whisperx"] = self._version("whisperx")
            self.dependency_versions["torchaudio"] = self._version("torchaudio")
            import torch
            import whisperx

            if not torch.cuda.is_available():
                raise RuntimeError("blocked_resource: candidate A4 requires CUDA")
            self.model_size = self.kwargs["model_name"]
            self.device, self.compute_type = self.kwargs["device"], self.kwargs["compute_type"]
            if self.device != "cuda":
                raise RuntimeError("blocked_configuration: candidate A4 requires CUDA")
            revision = self.kwargs.get("revision")
            if not isinstance(revision, str) or len(revision) != 40:
                raise RuntimeError(f"blocked_unpinned_model: {self.id} has no immutable weight revision")
            from whisperx.asr import WhisperModel as WhisperXWhisperModel
            pinned_asr = WhisperXWhisperModel(
                _cached_snapshot(self.kwargs["model_repo"], revision), device=self.device,
                compute_type=self.compute_type,
            )
            self.model = whisperx.load_model(self.model_size, self.device,
                                             compute_type=self.compute_type,
                                             language="en", model=pinned_asr)
            self._whisperx = whisperx
            self.align_model, self.align_metadata = whisperx.load_align_model(
                language_code="en", device="cuda", model_name=self.kwargs["alignment_model"]
            )
            self.model_revision = revision
        elif suffix == "A5_DeepFilterNet":
            self.dependency_versions["deepfilternet"] = self._version("deepfilternet")
            self.dependency_versions["faster-whisper"] = self._version("faster-whisper")
            self.dependency_versions["torch"] = self._version("torch")
            import torch
            try:
                from df.enhance import enhance, init_df
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError("blocked_dependency: DeepFilterNet API unavailable") from exc
            model_dir = self.kwargs.get("model_dir")
            try:
                self.denoiser, df_state, self.denoiser_name = init_df(
                    model_base_dir=model_dir, post_filter=bool(self.kwargs.get("post_filter", True)),
                    log_file=None,
                )
            except TypeError as exc:
                raise RuntimeError("blocked_configuration: installed DeepFilterNet does not support registered model_dir") from exc
            self._df_enhance = enhance
            self._df_state = df_state
            if not torch.cuda.is_available():
                raise RuntimeError("blocked_resource: candidate A5 requires CUDA")
            revision = self.kwargs.get("decoder_revision")
            if not isinstance(revision, str) or len(revision) != 40:
                raise RuntimeError(f"blocked_unpinned_model: {self.id} has no immutable decoder revision")
            self.model = WhisperModel(
                _cached_snapshot("Systran/faster-whisper-small", revision),
                device="cuda", compute_type="float16")
            self.model_size, self.device, self.compute_type = "DeepFilterNet -> A1 small", "cuda", "float16"
            self.model_revision = revision
            self.dependency_versions["torch"] = self._version("torch")
        else:
            raise RuntimeError(f"unregistered ASR candidate {self.id!r}")
        self.load_seconds = time.perf_counter() - started

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptResult:
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not samples.size or sample_rate != 16000:
            raise ValueError("canonical ASR input must be non-empty mono 16 kHz float32")
        if self.model is None:
            raise RuntimeError("adapter must be loaded before inference")
        suffix = self.id.split(".", 1)[-1]
        preprocessing = alignment = 0.0
        if suffix.startswith(("A0_", "A1_", "A3_")):
            started = time.perf_counter()
            segments, _ = self.model.transcribe(samples, language="en", task="transcribe", beam_size=5)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            elapsed = time.perf_counter() - started
        elif suffix == "A2_DistilWhisper":
            import torch

            started = time.perf_counter()
            inputs = self.processor(samples, sampling_rate=16000, return_tensors="pt")
            input_features = inputs.input_features.to(device="cuda", dtype=torch.float16)
            with torch.inference_mode():
                # This registered checkpoint is English-only. Transformers
                # rejects explicit language/task controls for that model.
                tokens = self.model.generate(input_features)
            text = self.processor.batch_decode(tokens, skip_special_tokens=True)[0].strip()
            elapsed = time.perf_counter() - started
        elif suffix == "A4_WhisperX":
            started = time.perf_counter()
            result = self.model.transcribe(samples, batch_size=1, language="en")
            transcription_seconds = time.perf_counter() - started
            started = time.perf_counter()
            aligned = self._whisperx.align(
                result["segments"], self.align_model, self.align_metadata, samples,
                "cuda", return_char_alignments=False,
            )
            alignment = time.perf_counter() - started
            # WER belongs to the ASR transcript; alignment may split, omit, or
            # normalize words and is measured only as a separate composite cost.
            text = " ".join(str(segment.get("text", "")).strip()
                            for segment in result.get("segments", [])).strip()
            elapsed = transcription_seconds + alignment
        elif suffix == "A5_DeepFilterNet":
            started = time.perf_counter()
            import scipy.signal
            import torch

            target_rate = int(self._df_state.sr())
            divisor = np.gcd(sample_rate, target_rate)
            up = scipy.signal.resample_poly(samples, target_rate // divisor,
                                            sample_rate // divisor).astype(np.float32, copy=False)
            tensor = torch.from_numpy(up).unsqueeze(0)
            enhanced = self._df_enhance(self.denoiser, self._df_state, tensor)
            enhanced = enhanced.squeeze().detach().cpu().numpy()
            back_divisor = np.gcd(target_rate, sample_rate)
            canonical = scipy.signal.resample_poly(enhanced, sample_rate // back_divisor,
                                                   target_rate // back_divisor).astype(np.float32, copy=False)
            if abs(len(canonical) - len(samples)) > 1:
                raise RuntimeError("denoise_duration_changed")
            preprocessing = time.perf_counter() - started
            started = time.perf_counter()
            segments, _ = self.model.transcribe(canonical, language="en", task="transcribe", beam_size=5)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            elapsed = preprocessing + time.perf_counter() - started
        else:
            raise RuntimeError(f"no transcription implementation for {self.id}")
        if not text:
            raise RuntimeError("empty_transcript")
        return TranscriptResult(text, elapsed, preprocessing, alignment)

    def close(self) -> None:
        self.model = self.processor = self.tokenizer = self.align_model = self.denoiser = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def registered_asr_candidates(registry_path) -> list[dict[str, Any]]:
    import yaml

    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    records = [item for item in payload.get("candidates", []) if item.get("task") == "RQ0_A"]
    wanted = {f"RQ0_A.{name}" for name in (
        "A0_WhisperBase", "A1_FasterWhisperSmall_GPU", "A2_DistilWhisper",
        "A3_FasterWhisperMedium_GPU", "A4_WhisperX", "A5_DeepFilterNet",
    )}
    found = {item["id"] for item in records}
    if found != wanted:
        raise RuntimeError(f"ASR registry must contain exactly A0-A5; found {sorted(found)}")
    return records
