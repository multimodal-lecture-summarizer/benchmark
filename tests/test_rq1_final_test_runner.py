"""Sealed scorer tests use invented units; no recruitment unit becomes a pilot."""

import hashlib
import json

import pytest

from experiments.scripts.rq1_final_test_runner import FinalTestLockError, run_sealed_scores
from experiments.scripts.rq1_grouped_bootstrap import grouped_paired_bootstrap


def _save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _fixture(tmp_path):
    units = []
    history = []
    targets = []
    rows = []
    for i in range(3):
        uid = f"synthetic-{i}"
        units.append({"video_id": uid, "dataset_ids": ["ytseg"],
                      "source_refs": {"ytseg": {"source": "synthetic", "revision": "v1"}},
                      "course_id": f"synthetic-course-{i}", "lecturer_ids": [f"synthetic-lecturer-{i}"],
                      "split": "final_test"})
        history.append({"video_id": uid, "qualification_observed": "synthetic_fixture",
                        "training_or_tuning_evidence": "audited_no_project_development_use",
                        "model_selection_evidence": "audited_no_project_development_use",
                        "historical_use_outside_records": "unknown"})
        targets.append({"video_id": uid, "reference_sec": [10.0], "duration_sec": 30.0,
                        "annotation_sha256": "a" * 64, "media_sha256": "b" * 64})
        rows.extend([{"video_id": uid, "candidate": "C1", "status": "run", "predicted_sec": [10.0]},
                     {"video_id": uid, "candidate": "C2", "status": "run", "predicted_sec": [11.0]}])
    config = {"candidates": ["C1", "C2"], "contrasts": [{"candidate": "C2", "baseline": "C1"}],
              "bootstrap_seed": 23, "bootstrap_resamples": 10_000}
    lock = {"schema": "rq1-final-test-lock/1", "mode": "fixture", "run_id": "synthetic-001"}
    for name, payload in (("cohort", units), ("history", history), ("targets", targets), ("candidate_config", config)):
        lock[name] = _save(tmp_path / f"{name}.json", payload)
    lock_path = tmp_path / "lock.json"
    _save(lock_path, lock)
    pred_path = tmp_path / "predictions.json"
    _save(pred_path, {"lock_sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
                      "candidate_config_sha256": lock["candidate_config"]["sha256"], "rows": rows})
    return lock_path, pred_path


def test_synthetic_fixture_runs_without_real_candidates(tmp_path):
    lock, pred = _fixture(tmp_path)
    report = run_sealed_scores(lock, pred, tmp_path / "out")
    assert report["status"] == "fixture_only"
    assert report["test_video_ids"] == [f"synthetic-{i}" for i in range(3)]
    assert report["paired_grouped_comparisons"][0]["group_count"] == 3
    assert report["paired_grouped_comparisons"][0]["holm_family_size"] == 1
    assert (tmp_path / "out" / "report.sha256").is_file()
    with pytest.raises(FinalTestLockError, match="already exists"):
        run_sealed_scores(lock, pred, tmp_path / "out")


def test_hash_drift_fails_before_output(tmp_path):
    lock, pred = _fixture(tmp_path)
    (tmp_path / "targets.json").write_text("[]", encoding="utf-8")
    with pytest.raises(FinalTestLockError, match="hash drift"):
        run_sealed_scores(lock, pred, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_prediction_coverage_fails(tmp_path):
    lock, pred = _fixture(tmp_path)
    payload = json.loads(pred.read_text(encoding="utf-8"))
    payload["rows"].pop()
    _save(pred, payload)
    with pytest.raises(FinalTestLockError, match="one row"):
        run_sealed_scores(lock, pred, tmp_path / "out")


def test_official_mode_needs_pretest_scale_decision(tmp_path):
    lock, pred = _fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["mode"] = "official"
    _save(lock, payload)
    with pytest.raises(FinalTestLockError, match="scale/scope decision"):
        run_sealed_scores(lock, pred, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_group_bootstrap_weights_groups_equally_and_keeps_pairs():
    scores = {"a": {"C1": 0.0, "C2": 1.0}, "b": {"C1": 0.0, "C2": 1.0},
              "c": {"C1": 1.0, "C2": 0.0}}
    result = grouped_paired_bootstrap(scores, [["a", "b"], ["c"]],
                                      candidate="C2", baseline="C1", seed=1, resamples=10_000)
    assert result["video_macro_paired_delta"] == pytest.approx(1 / 3)
    assert result["equal_group_mean_delta"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="duplicate"):
        grouped_paired_bootstrap(scores, [["a", "b"], ["b", "c"]],
                                 candidate="C2", baseline="C1", seed=1)
