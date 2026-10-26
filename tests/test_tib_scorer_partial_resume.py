"""Scorer partial resume: golden pins for the unchanged stages, store semantics, and runner scenarios on fakes."""
import json
from pathlib import Path

import pytest

from experiments.scripts.tib_scorer_colab_checkpoint import ScoreCheckpoints, digest

BINDING = {"package_manifest_sha256": "a" * 64, "runtime_sha256": digest({"x": 1})}
ROW = {"sample_id": "lead3__fixture-001", "delivered_summary": "text", "reference": "ref"}


def test_golden_key_and_runtime_digest_are_unchanged(tmp_path):
    """Selection300 and Pilot40 evidence was produced with these exact derivations; they must never move."""
    assert digest({"x": 1}) == "5041bf1f713df204784353e82f6a4a535931cb64f1f4b4a5aeaffcb720918b22"
    store = ScoreCheckpoints(tmp_path, BINDING)
    assert digest(store.key(ROW)) == "f87c341338775ec57c067e188d363f65ce61033ce30024da5bee0646ce3e349d"


def test_default_save_payload_shape_is_unchanged(tmp_path):
    store = ScoreCheckpoints(tmp_path, BINDING)
    saved = store.save(ROW, {"metrics": {"a": 1.0}, "failures": {}}, 1.5)
    assert set(saved) == {"key", "result", "original_scoring_wall_seconds"}


def test_default_mode_still_refuses_partial_and_populated_folders(tmp_path):
    store = ScoreCheckpoints(tmp_path, BINDING)
    store.save(ROW, {"metrics": {}, "failures": {}}, 0.1)
    with pytest.raises(ValueError, match="use --resume"):
        ScoreCheckpoints(tmp_path, BINDING)
    resumed = ScoreCheckpoints(tmp_path, BINDING, resume=True)
    assert resumed.load(ROW)["result"] == {"metrics": {}, "failures": {}}
    with pytest.raises(ValueError, match="Required resume checkpoint missing"):
        resumed.load({**ROW, "sample_id": "lead3__fixture-002"})
    (tmp_path / "x.json.partial").write_text("{}")
    with pytest.raises(ValueError, match="Partial scorer checkpoint"):
        ScoreCheckpoints(tmp_path, BINDING, resume=True)


def test_quarantine_never_overwrites_and_runs_only_when_asked(tmp_path):
    stores = ScoreCheckpoints(tmp_path, BINDING, partial=True, run_id="r1")
    (tmp_path / "a.json.partial").write_text("{}")
    assert (tmp_path / "a.json.partial").exists()                       # construction alone changes nothing
    again = ScoreCheckpoints(tmp_path, BINDING, partial=True, run_id="r1")
    (tmp_path / "a.json.partial.quarantined-r1").write_text("earlier evidence")
    with pytest.raises(ValueError, match="already exists"):
        again.quarantine_torn()
    assert (tmp_path / "a.json.partial").exists() and (tmp_path / "a.json.partial.quarantined-r1").read_text() == "earlier evidence"
    assert stores.quarantined == []


def test_require_only_accepts_torn_and_quarantined_files_and_rejects_any_other_name(tmp_path):
    store = ScoreCheckpoints(tmp_path, BINDING, partial=True, run_id="r2")
    store.save(ROW, {"metrics": {}, "failures": {}}, 0.1)
    (tmp_path / "b.json.partial.quarantined-r0").write_text("{}")
    (tmp_path / "c.json.partial").write_text("{}")
    store = ScoreCheckpoints(tmp_path, BINDING, partial=True, run_id="r3")
    store.require_only([ROW])
    (tmp_path / "stray.txt").write_text("x")
    with pytest.raises(ValueError, match="do not belong"):
        store.require_only([ROW])
