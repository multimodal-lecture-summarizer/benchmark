"""Contract tests for architecture worker responses."""

import numpy as np
import pytest

from experiments.evaluation.asr_architecture_adapters import ArchitectureCandidateAdapter
from experiments.evaluation.asr_selection_scoring import score_asr_pairs


@pytest.mark.parametrize("worker_text", ["", " \t "])
def test_empty_worker_transcript_is_scored_as_deletions(monkeypatch, worker_text):
    candidate = {"id": "RQ0_ARCH.A1_Wav2Vec2CTC", "model_repo": "example/model",
                 "revision": "pinned"}
    adapter = ArchitectureCandidateAdapter(candidate)
    monkeypatch.setattr(adapter, "_request", lambda _payload: {
        "status": "result", "text": worker_text, "inference_seconds": 0.01,
    })

    result = adapter.transcribe(np.ones(1600, dtype=np.float32))

    assert result.text == ""
    assert score_asr_pairs([("two words", result.text)])["wer"] == 1.0


@pytest.mark.parametrize("response", [{"status": "result"},
                                      {"status": "result", "text": None}])
def test_missing_worker_transcript_is_rejected(monkeypatch, response):
    candidate = {"id": "RQ0_ARCH.A1_Wav2Vec2CTC", "model_repo": "example/model",
                 "revision": "pinned"}
    adapter = ArchitectureCandidateAdapter(candidate)
    monkeypatch.setattr(adapter, "_request", lambda _payload: response)

    with pytest.raises(RuntimeError, match="architecture_worker_missing_transcript"):
        adapter.transcribe(np.ones(1600, dtype=np.float32))
