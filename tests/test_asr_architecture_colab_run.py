import hashlib
import json

import pytest

from experiments.scripts import asr_architecture_preflight as preflight
from experiments.scripts import asr_architecture_colab_run as colab_run


def test_probe_receipt_is_bound_to_manifest_audio_and_ordered_candidate_set(monkeypatch, tmp_path):
    freeze = tmp_path / "freeze"
    manifest = freeze / "payloads/dataset.frozen_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(colab_run, "FREEZE", freeze)
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    receipt = {
        "unit_id": "validation:u1",
        "audio_sha256": "a" * 64,
        "dataset_manifest_sha256": manifest_sha,
        "outcomes": [{"candidate": "A0", "status": "passed"},
                     {"candidate": "A1", "status": "passed"}],
    }

    assert colab_run._probe_matches(receipt, "validation:u1", "a" * 64, ["A0", "A1"])
    assert not colab_run._probe_matches(receipt, "validation:u2", "a" * 64, ["A0", "A1"])
    assert not colab_run._probe_matches(receipt, "validation:u1", "b" * 64, ["A0", "A1"])
    assert not colab_run._probe_matches(receipt, "validation:u1", "a" * 64, ["A1", "A0"])

    manifest.write_text(json.dumps({"changed": True}), encoding="utf-8")
    assert not colab_run._probe_matches(receipt, "validation:u1", "a" * 64, ["A0", "A1"])


def test_validation_reads_probe_audio_before_identity_gate(monkeypatch, tmp_path):
    from benchmarks.scripts import run_asr_model_benchmark as benchmark

    (tmp_path / "architecture_probe.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(colab_run, "_first_validation_unit", lambda: {"unit_id": "validation:u1"})
    monkeypatch.setattr(benchmark, "_audio", lambda unit: (None, 1.0, "a" * 64))
    monkeypatch.setattr(colab_run, "_source_digest", lambda: "current-source")

    with pytest.raises(RuntimeError, match="architecture probe failed or is stale"):
        colab_run.run("validation", tmp_path)


def test_preflight_checks_distribution_version_for_extra_package(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "2.4.0\n"

    def fake_run(command, **kwargs):
        calls.append(command)
        return Result()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)

    assert preflight._pkg_version("python", "nemo-toolkit[asr]") == "2.4.0"
    assert calls[0][-1] == "nemo-toolkit"


def test_preflight_rejects_snapshot_without_nemo_weights(tmp_path):
    cache = tmp_path / "hub"
    snapshot = cache / "models--nvidia--ctc" / "snapshots" / "pinned"
    snapshot.mkdir(parents=True)

    missing = preflight._snapshot("nvidia/ctc", "pinned", cache, "nemo_ctc")
    assert not missing["cached"]
    assert missing["required_checkpoint"] == "*.nemo"

    (snapshot / "model.nemo").write_bytes(b"checkpoint")
    assert preflight._snapshot("nvidia/ctc", "pinned", cache, "nemo_ctc")["cached"]
