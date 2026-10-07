"""Model-family worker process. Stdout is reserved for the JSONL protocol."""
from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import numpy as np

MODEL = None
PROCESSOR = None
CANDIDATE = None


def _use_paraformer_vocabulary(tokenizer_class, pieces: list[str]) -> None:
    """Decode model output IDs with its token list, not SentencePiece's ID order."""
    if (not isinstance(pieces, list) or len(pieces) != 10020
            or not all(isinstance(piece, str) for piece in pieces)):
        raise RuntimeError("blocked_model: unexpected Paraformer token list")

    def ids2tokens(self, ids):
        values = [int(value) for value in ids]
        if any(value < 0 or value >= len(pieces) for value in values):
            raise RuntimeError("paraformer_token_id_outside_model_vocabulary")
        return [pieces[value] for value in values]

    def tokens2text(self, tokens):
        # SentencePiece uses U+2581 as a word boundary in its piece strings.
        return "".join(tokens).replace("▁", " ").strip()

    tokenizer_class.ids2tokens = ids2tokens
    tokenizer_class.tokens2text = tokens2text


def _versions(names: list[str]) -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in names}


def _load(candidate: dict) -> dict:
    global MODEL, PROCESSOR, CANDIDATE
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("blocked_resource: CUDA/T4 unavailable")
    framework = candidate["framework"]
    repo, revision = candidate["model_repo"], candidate["revision"]
    if len(revision) != 40:
        raise RuntimeError("blocked_unpinned_model: revision must be a full commit SHA")
    from huggingface_hub import snapshot_download
    path = snapshot_download(repo_id=repo, revision=revision, local_files_only=True)
    if Path(path).name != revision:
        raise RuntimeError("blocked_unpinned_model: cached snapshot does not match revision")
    deps: list[str]
    if framework == "faster_whisper":
        from faster_whisper import WhisperModel
        MODEL = WhisperModel(path, device="cuda", compute_type="float16")
        deps = ["faster-whisper", "ctranslate2"]
    elif framework == "transformers_ctc":
        from transformers import AutoModelForCTC, AutoProcessor
        PROCESSOR = AutoProcessor.from_pretrained(path, local_files_only=True)
        MODEL = AutoModelForCTC.from_pretrained(path, local_files_only=True,
                                                use_safetensors=False).to("cuda").eval()
        deps = ["transformers", "torch"]
    elif framework in {"nemo_ctc", "nemo_rnnt"}:
        import nemo.collections.asr as nemo_asr
        nemo_path = next(Path(path).glob("*.nemo"), None)
        if nemo_path is None:
            raise RuntimeError("blocked_model: pinned NeMo snapshot has no .nemo checkpoint")
        cls = (nemo_asr.models.EncDecCTCModelBPE if framework == "nemo_ctc"
               else nemo_asr.models.EncDecRNNTBPEModel)
        MODEL = cls.restore_from(str(nemo_path), map_location=torch.device("cuda")).eval()
        deps = ["nemo_toolkit", "torch"]
    elif framework == "funasr_paraformer":
        from funasr import AutoModel
        from funasr.tokenizer.sentencepiece_tokenizer import SentencepiecesTokenizer

        # The pinned checkpoint's token IDs follow tokens.json, not bpe.model.
        pieces = json.loads((Path(path) / "tokens.json").read_text(encoding="utf-8"))
        _use_paraformer_vocabulary(SentencepiecesTokenizer, pieces)
        MODEL = AutoModel(model=path, vad_model=None, punc_model=None,
                          device="cuda:0", disable_update=True, disable_pbar=True)
        deps = ["funasr", "torch"]
    elif framework == "qwen3_asr":
        from qwen_asr import Qwen3ASRModel
        MODEL = Qwen3ASRModel.from_pretrained(path, device_map="cuda:0",
                                               dtype=torch.float16)
        deps = ["qwen-asr", "transformers", "torch"]
    else:
        raise RuntimeError(f"unsupported architecture framework: {framework}")
    CANDIDATE = candidate
    torch.cuda.synchronize()
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    return {"status": "ready", "dependency_versions": _versions(deps),
            "gpu_memory": {"free_bytes_after_load": int(free_bytes),
                           "total_bytes": int(total_bytes),
                           "torch_allocated_bytes_after_load": int(torch.cuda.memory_allocated(0)),
                           "torch_reserved_bytes_after_load": int(torch.cuda.memory_reserved(0))}}


def _wav_path(audio: np.ndarray) -> Path:
    import soundfile as sf
    import tempfile
    handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    handle.close()
    path = Path(handle.name)
    sf.write(path, audio, 16000, subtype="PCM_16")
    return path


def _transcribe(audio_path: str) -> dict:
    import torch
    audio = np.load(audio_path, allow_pickle=False)
    if audio.dtype != np.float32 or audio.ndim != 1 or not audio.size:
        raise RuntimeError("canonical_input_invalid")
    framework = CANDIDATE["framework"]
    torch.cuda.reset_peak_memory_stats(0)
    start = time.perf_counter()
    with torch.inference_mode():
        if framework == "faster_whisper":
            segments, _ = MODEL.transcribe(audio, language="en", task="transcribe", beam_size=5)
            text = " ".join(row.text.strip() for row in segments).strip()
        elif framework == "transformers_ctc":
            features = PROCESSOR(audio, sampling_rate=16000, return_tensors="pt").input_values.to("cuda")
            logits = MODEL(features).logits
            text = PROCESSOR.batch_decode(logits.argmax(dim=-1))[0].strip()
        elif framework in {"nemo_ctc", "nemo_rnnt"}:
            path = _wav_path(audio)
            try:
                result = MODEL.transcribe([str(path)], batch_size=1, verbose=False)
            finally:
                path.unlink(missing_ok=True)
            first = result[0]
            text = str(getattr(first, "text", first)).strip()
        elif framework == "funasr_paraformer":
            path = _wav_path(audio)
            try:
                result = MODEL.generate(input=str(path), batch_size=1)
            finally:
                path.unlink(missing_ok=True)
            text = str(result[0].get("text", "")).strip()
        else:
            result = MODEL.transcribe(audio=(audio, 16000), language="English")
            first = result[0]
            text = str(getattr(first, "text", first)).strip()
    torch.cuda.synchronize()
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    return {"status": "result", "text": text,
            "inference_seconds": time.perf_counter() - start,
            "gpu_memory": {"free_bytes_after_inference": int(free_bytes),
                           "total_bytes": int(total_bytes),
                           "torch_peak_allocated_bytes": int(torch.cuda.max_memory_allocated(0)),
                           "torch_peak_reserved_bytes": int(torch.cuda.max_memory_reserved(0))}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-id", required=True)
    args = parser.parse_args()
    protocol_out = sys.stdout
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if message.get("op") == "close":
                break
            with contextlib.redirect_stdout(sys.stderr):
                if message.get("op") == "load":
                    if message["candidate"].get("id") != args.candidate_id:
                        raise RuntimeError("worker_candidate_identity_mismatch")
                    response = _load(message["candidate"])
                elif message.get("op") == "transcribe" and MODEL is not None:
                    response = _transcribe(message["audio_path"])
                else:
                    raise RuntimeError("worker_not_loaded_or_unknown_operation")
        except Exception as exc:
            response = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        protocol_out.write(json.dumps(response, ensure_ascii=False) + "\n")
        protocol_out.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
