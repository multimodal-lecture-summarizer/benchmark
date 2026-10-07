from pathlib import Path

from experiments.scripts import asr_benchmark_preflight as preflight


def test_preflight_searches_configured_huggingface_cache(monkeypatch, tmp_path):
    cache = tmp_path / "custom-hf-cache"
    snapshot = cache / "models--org--model" / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    monkeypatch.setenv("HF_HUB_CACHE", str(cache))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)

    roots = preflight._hub_cache_dirs()
    found = preflight._snapshot("org/model", "abc123", roots)

    assert cache.resolve() in roots
    assert found["cached"] is True
    assert Path(found["snapshot_path"]) == snapshot


def test_preflight_reads_exact_dependency_pins_from_lockfile():
    assert preflight._locked_version("faster-whisper") == "1.1.0"
    assert preflight._locked_version("whisperx") == "3.3.1"
    assert preflight._locked_version("torch") == "2.5.1"
