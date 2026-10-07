"""Offline contract tests for the registered A0-A5 adapter dispatch."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from experiments.evaluation.asr_candidate_adapters import CandidateAdapter, registered_asr_candidates
from experiments.evaluation import asr_candidate_adapters as adapters


def test_registry_exposes_exactly_the_six_planned_asr_candidates():
    from pathlib import Path
    registry = Path(__file__).resolve().parents[1] / "experiments/registry/candidates.yaml"
    candidates = registered_asr_candidates(registry)
    assert [candidate["id"].split(".")[-1][:2] for candidate in candidates] == [
        "A0", "A1", "A2", "A3", "A4", "A5"
    ]


@pytest.mark.parametrize("candidate_id", [
    "RQ0_A.A0_WhisperBase", "RQ0_A.A1_FasterWhisperSmall_GPU",
    "RQ0_A.A2_DistilWhisper", "RQ0_A.A3_FasterWhisperMedium_GPU",
    "RQ0_A.A4_WhisperX", "RQ0_A.A5_DeepFilterNet",
])
def test_adapter_rejects_empty_or_noncanonical_audio_before_loading(candidate_id):
    import numpy as np

    adapter = CandidateAdapter({"id": candidate_id, "model_kwargs": {}})
    with pytest.raises(ValueError, match="canonical ASR input"):
        adapter.transcribe(np.zeros(0, dtype=np.float32))
    with pytest.raises(ValueError, match="canonical ASR input"):
        adapter.transcribe(np.ones(20, dtype=np.float32), sample_rate=8000)


def test_adapter_requires_explicit_registered_id():
    adapter = CandidateAdapter({"id": "RQ0_A.A6_Future", "model_kwargs": {}})
    with pytest.raises(RuntimeError, match="unregistered ASR candidate"):
        adapter.load()


def test_whisperx_scores_transcript_before_alignment(monkeypatch):
    import numpy as np

    class Model:
        def transcribe(self, _samples, **_kwargs):
            return {"segments": [{"text": "original transcript"}]}

    class WhisperX:
        @staticmethod
        def align(*_args, **_kwargs):
            return {"segments": [{"text": "alignment altered transcript"}]}

    adapter = CandidateAdapter({"id": "RQ0_A.A4_WhisperX", "model_kwargs": {}})
    adapter.model = Model()
    adapter.align_model = object()
    adapter.align_metadata = {}
    adapter._whisperx = WhisperX()

    result = adapter.transcribe(np.ones(1600, dtype=np.float32))

    assert result.text == "original transcript"
    assert result.alignment_seconds >= 0


def test_faster_whisper_loads_exact_cached_revision_without_passing_revision_to_ctranslate2(monkeypatch):
    calls = []
    module = ModuleType("faster_whisper")
    module.WhisperModel = lambda path, **kwargs: calls.append((path, kwargs)) or object()
    monkeypatch.setitem(sys.modules, "faster_whisper", module)
    monkeypatch.setattr(adapters, "_cached_snapshot", lambda repo, revision: f"/snapshots/{revision}")
    candidate = next(row for row in registered_asr_candidates(
        adapters.Path(__file__).resolve().parents[1] / "experiments/registry/candidates.yaml")
        if row["id"].endswith("A1_FasterWhisperSmall_GPU"))
    adapter = CandidateAdapter(candidate)
    monkeypatch.setattr(adapter, "_version", lambda _name: "1.1.0")

    adapter.load()

    assert calls[0][0].endswith(candidate["model_kwargs"]["revision"])
    assert "revision" not in calls[0][1]


def test_distil_processor_uses_its_separately_pinned_revision(monkeypatch):
    paths = []
    torch = ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: True)
    torch.float16 = "float16"
    transformers = ModuleType("transformers")
    transformers.AutoProcessor = SimpleNamespace(
        from_pretrained=lambda path, **_kwargs: paths.append(path) or object())
    generation = SimpleNamespace(is_multilingual=False, forced_decoder_ids=[[1, 50362]],
                                 language="<|en|>", task="transcribe")
    model = SimpleNamespace(to=lambda _device: model, generation_config=generation)
    transformers.AutoModelForSpeechSeq2Seq = SimpleNamespace(
        from_pretrained=lambda path, **_kwargs: paths.append(path) or model)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    monkeypatch.setattr(adapters, "_cached_snapshot", lambda repo, revision: f"/snapshots/{revision}")
    candidate = next(row for row in registered_asr_candidates(
        adapters.Path(__file__).resolve().parents[1] / "experiments/registry/candidates.yaml")
        if row["id"].endswith("A2_DistilWhisper"))
    adapter = CandidateAdapter(candidate)
    monkeypatch.setattr(adapter, "_version", lambda _name: "pinned")

    adapter.load()

    assert paths == [f"/snapshots/{candidate['model_kwargs']['processor_revision']}",
                     f"/snapshots/{candidate['model_kwargs']['revision']}"]
    assert generation.language is None and generation.task is None
    assert generation.forced_decoder_ids == [[1, 50362]]


def test_english_only_distil_generate_omits_language_and_task(monkeypatch):
    from contextlib import nullcontext
    import numpy as np

    calls = []
    torch = ModuleType("torch")
    torch.float16 = "float16"
    torch.inference_mode = nullcontext
    monkeypatch.setitem(sys.modules, "torch", torch)

    features = SimpleNamespace(to=lambda **_kwargs: "features")
    adapter = CandidateAdapter({"id": "RQ0_A.A2_DistilWhisper", "model_kwargs": {}})
    adapter.model = SimpleNamespace(generate=lambda *args, **kwargs: calls.append((args, kwargs)) or [1])
    class Processor:
        def __call__(self, *_args, **_kwargs):
            return SimpleNamespace(input_features=features)

        def batch_decode(self, *_args, **_kwargs):
            return ["recognized speech"]

    adapter.processor = Processor()

    result = adapter.transcribe(np.ones(1600, dtype=np.float32))

    assert result.text == "recognized speech"
    assert calls == [(('features',), {})]


def test_deepfilternet_accepts_the_three_value_pinned_api(monkeypatch):
    torch = ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: True)
    df = ModuleType("df")
    enhance = ModuleType("df.enhance")
    enhance.enhance = lambda *_args: None
    enhance.init_df = lambda **_kwargs: (object(), object(), "DeepFilterNet3_pf")
    faster_whisper = ModuleType("faster_whisper")
    faster_whisper.WhisperModel = lambda *_args, **_kwargs: object()
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "df", df)
    monkeypatch.setitem(sys.modules, "df.enhance", enhance)
    monkeypatch.setitem(sys.modules, "faster_whisper", faster_whisper)
    monkeypatch.setattr(adapters, "_cached_snapshot", lambda repo, revision: f"/snapshots/{revision}")
    candidate = next(row for row in registered_asr_candidates(
        adapters.Path(__file__).resolve().parents[1] / "experiments/registry/candidates.yaml")
        if row["id"].endswith("A5_DeepFilterNet"))
    adapter = CandidateAdapter(candidate)
    monkeypatch.setattr(adapter, "_version", lambda _name: "pinned")

    adapter.load()

    assert adapter.denoiser_name == "DeepFilterNet3_pf"
    assert adapter.model_revision == candidate["model_kwargs"]["decoder_revision"]
