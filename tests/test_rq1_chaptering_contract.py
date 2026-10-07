"""RQ1 chaptering contract: independent GT, split sealing, same-unit features, scorer."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import nbformat
import pytest

from benchmarks.scripts import run_chaptering_benchmark as run04a
from benchmarks.scripts import run_chaptering_modality_ablation as run04b
from benchmarks.scripts.execute_all_notebooks import load_manifest
from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.chapter_benchmark_contract import (
    ChapterContractError,
    admitted_splits,
    build_input_feature_record,
    index_features,
    learned_candidate_status,
    reject_chapter_speaker_split_leakage,
    reject_course_split_leakage,
    score_chapters,
    validate_chapter_ground_truth,
)
from experiments.scripts.stage_benchmark_helpers import load_eligible_units

HASH_A = hashlib.sha256(b"fixture-source").hexdigest()
HASH_B = hashlib.sha256(b"fixture-config").hexdigest()
HASH_C = hashlib.sha256(b"fixture-dependency").hexdigest()
DATASET = "fixture_lectures"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _gt(**overrides: Any) -> dict[str, Any]:
    gt = {
        "source": "fixture publisher", "revision": "r1",
        "annotation_origin": "publisher_timed_toc",
        "timestamp_convention": "seconds from media start",
    }
    gt.update(overrides)
    return gt


def _unit(uid: str, split: str, course: str, *, with_gt: bool = True, **extra: Any) -> dict[str, Any]:
    words = " ".join(f"alpha{i % 7}" for i in range(400)) + " " + " ".join(
        f"omega{i % 5}" for i in range(400)
    )
    unit = {
        "unit_id": uid, "dataset_id": DATASET, "split": split, "course_id": course,
        "duration_sec": 1200.0, "sha256": hashlib.sha256(uid.encode()).hexdigest(),
        "transcript": words,
    }
    if with_gt:
        unit["chapter_boundaries_sec"] = [300.0, 600.0, 900.0]
        unit["chapter_gt"] = _gt()
    unit.update(extra)
    return unit


def _context(root: Path, notebook_id: str, *, profile: str = "full",
             mode: str | None = "selection") -> RunnerContext:
    return RunnerContext(
        profile=profile, run_namespace="diagnostic", status="real", artifact_root=root,
        notebook_id=notebook_id, run_id=str(uuid.uuid4()), source_sha256=HASH_A,
        config_sha256=HASH_B, dependency_state_sha256=HASH_C, evaluation_mode=mode,
    )


def _seed(root: Path, units: list[dict[str, Any]], *, profile: str = "full") -> None:
    ctx = _context(root, "00c_dataset_eda_and_freeze", profile=profile, mode=None)
    write_json_artifact(ctx, "dataset.frozen_manifest", [{
        "dataset_id": DATASET, "freeze_status": "eligible",
        "scientific_selection_eligible": True,
        "unit_ids": [u["unit_id"] for u in units], "unit_records": units,
        "reason": "fixture", "profile": profile,
    }])
    write_json_artifact(ctx, "dataset.registry", [{"dataset_id": DATASET, "revision": "r1"}])
    write_json_artifact(ctx, "dataset.endpoint_matrix", [{
        "dataset_id": DATASET, "endpoint": "chapter", "eligibility": "fixture",
        "scientific_selection_eligible": True, "reason": "fixture",
    }])
    write_run_manifest(ctx)


def _argv(root: Path, notebook_id: str, *, profile: str = "full",
          mode: str | None = "selection") -> list[str]:
    argv = [
        "--profile", profile, "--run-namespace", "diagnostic", "--evidence-status", "real",
        "--artifact-root", str(root), "--notebook-id", notebook_id,
        "--run-id", str(uuid.uuid4()), "--source-sha256", HASH_A,
        "--config-sha256", HASH_B, "--dependency-state-sha256", HASH_C,
    ]
    if mode:
        argv += ["--evaluation-mode", mode]
    return argv


def _payload(root: Path, artifact_id: str, profile: str = "full") -> dict[str, Any]:
    path = root / "diagnostic" / profile / "payloads" / f"{artifact_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _video_features(unit: dict[str, Any], *, scene: list[float],
                    ocr: list[dict[str, Any]]) -> dict[str, Any]:
    features: dict[str, Any] = {"source_sha256": unit["sha256"]}
    for name, content in (("scene", scene), ("ocr", ocr)):
        extractor = f"fixture_{name}"
        config = {"version": 1}
        digest = hashlib.sha256(json.dumps(
            {"content": content, "extractor": extractor, "config": config},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        features[name] = {
            "available": bool(content), "sha256": digest, "extractor": extractor,
            "config": config,
            "boundaries_sec" if name == "scene" else "observations": content,
        }
    return features


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


def test_scorer_primary_collar_is_3s_with_inclusive_edge():
    ref = [100.0, 200.0]
    assert score_chapters([103.0, 200.0], ref, 400.0)["collar_f1_3s"] == 1.0
    edge_miss = score_chapters([103.01, 200.0], ref, 400.0)
    assert edge_miss["collar_f1_3s"] == pytest.approx(0.5)
    assert edge_miss["collar_f1_5s"] == 1.0 and edge_miss["collar_f1_10s"] == 1.0


def test_scorer_empty_prediction_is_zero_not_midpoint():
    metrics = score_chapters([], [100.0, 200.0], 400.0)
    assert metrics["collar_f1_3s"] == 0.0
    assert metrics["predicted_boundary_count"] == 0.0
    assert metrics["pk"] > 0 and metrics["window_diff"] > 0


def test_scorer_one_and_multiple_boundaries_and_one_to_one_matching():
    assert score_chapters([50.0], [50.0], 100.0)["collar_f1_3s"] == 1.0
    many = score_chapters([99.0, 101.0, 300.0], [100.0, 300.0], 600.0)
    # two predictions near one reference: only one may match
    assert many["collar_precision_3s"] == pytest.approx(2 / 3)
    assert many["collar_recall_3s"] == 1.0
    exact = score_chapters([100.0, 300.0], [100.0, 300.0], 600.0)
    assert exact["pk"] == 0.0 and exact["window_diff"] == 0.0


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mutate, message", [
    (lambda u: u.pop("chapter_boundaries_sec"), "missing chapter_boundaries_sec"),
    (lambda u: u.pop("chapter_gt"), "missing chapter_gt"),
    (lambda u: u.update(chapter_gt=_gt(annotation_origin="scene_detection")), "not independent"),
    (lambda u: u.update(chapter_gt=_gt(annotation_origin="duration_midpoint")), "not independent"),
    (lambda u: u.update(chapter_gt=_gt(annotation_origin="made_up")), "not allowed"),
    (lambda u: u.update(chapter_boundaries_sec=[600.0, 300.0]), "strictly increasing"),
    (lambda u: u.update(chapter_boundaries_sec=[300.0, 1500.0]), "outside"),
    (lambda u: u.pop("duration_sec"), "positive duration_sec"),
])
def test_chapter_gt_validation_fails_closed(mutate, message):
    unit = _unit("u1", "validation", "c1")
    mutate(unit)
    with pytest.raises(ChapterContractError, match=message):
        validate_chapter_ground_truth(unit)


def test_empty_boundary_list_is_single_chapter_gt():
    unit = _unit("u1", "validation", "c1", chapter_boundaries_sec=[])
    assert validate_chapter_ground_truth(unit) == []


def test_course_leakage_across_train_validation_and_test():
    reject_course_split_leakage(
        [_unit("a", "train", "c1"), _unit("b", "validation", "c2"),
         _unit("c", "final_test", "c3")], DATASET)
    with pytest.raises(ChapterContractError, match="course_id occurs in multiple splits"):
        reject_course_split_leakage(
            [_unit("a", "train", "c1"), _unit("b", "final_test", "c1")], DATASET)


def test_chapter_speaker_must_be_known_and_disjoint_across_all_splits():
    units = [
        _unit("a", "train", "c1", speaker_id="lecturer-a"),
        _unit("b", "validation", "c2", speaker_id="lecturer-b"),
        _unit("c", "final_test", "c3", speaker_id="lecturer-c"),
    ]
    reject_chapter_speaker_split_leakage(units, DATASET)
    for held_out in ("validation", "final_test"):
        changed = [dict(unit) for unit in units]
        next(unit for unit in changed if unit["split"] == held_out)["speaker_id"] = " Lecturer-A "
        with pytest.raises(ChapterContractError, match="speaker_id occurs in multiple chapter splits"):
            reject_chapter_speaker_split_leakage(changed, DATASET)
    units[1]["speaker_id"] = " Unknown "
    with pytest.raises(ChapterContractError, match="chapter split requires speaker_id"):
        reject_chapter_speaker_split_leakage(units, DATASET)


# ---------------------------------------------------------------------------
# Split sealing
# ---------------------------------------------------------------------------


def test_evaluation_mode_is_required_and_final_test_is_sealed():
    assert admitted_splits("selection") == frozenset({"validation"})
    with pytest.raises(ChapterContractError, match="--evaluation-mode"):
        admitted_splits(None)
    with pytest.raises(ChapterContractError, match="sealed"):
        admitted_splits("final_test")


def test_loader_excludes_final_test_even_when_first_and_smoke(tmp_path):
    units = [_unit("t0", "final_test", "c9"), _unit("v1", "validation", "c1"),
             _unit("r2", "train", "c5")]
    _seed(tmp_path, units, profile="smoke")
    ctx = _context(tmp_path, run04a.NOTEBOOK_ID, profile="smoke")
    loaded = load_eligible_units(ctx, allowed_splits={"validation"})
    assert [u["unit_id"] for u in loaded] == ["v1"]


def test_loader_split_scope_rejects_unit_without_split(tmp_path):
    unit = _unit("v1", "validation", "c1")
    unit.pop("split")
    _seed(tmp_path, [unit])
    with pytest.raises(RuntimeError, match="no valid split"):
        load_eligible_units(_context(tmp_path, run04a.NOTEBOOK_ID), allowed_splits={"validation"})


# ---------------------------------------------------------------------------
# Runners end to end
# ---------------------------------------------------------------------------


def test_04a_rejects_scene_boundaries_as_chapter_gt(tmp_path, capsys):
    unit = _unit("v1", "validation", "c1", with_gt=False, scene_boundaries_sec=[300.0, 600.0])
    _seed(tmp_path, [unit])
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 1
    assert "blocked_gt" in capsys.readouterr().out
    assert not (tmp_path / "diagnostic" / "full" / "payloads" / "chapter.shortlist.json").exists()


def test_04a_requires_explicit_evaluation_mode(tmp_path, capsys):
    _seed(tmp_path, [_unit("v1", "validation", "c1")])
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID, mode=None)) == 1
    assert "--evaluation-mode" in capsys.readouterr().out


def test_04a_and_04b_validation_only_chain(tmp_path):
    units = [_unit("t0", "final_test", "c9"), _unit("v1", "validation", "c1"),
             _unit("v2", "validation", "c2", chapter_boundaries_sec=[])]
    _seed(tmp_path, units)
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 0

    predictions = _payload(tmp_path, "chapter.raw_predictions")["records"]
    features = _payload(tmp_path, "chapter.input_features")["records"]
    status = {r["candidate"]: r for r in _payload(tmp_path, "chapter.candidate_status")["records"]}
    aggregate = _payload(tmp_path, "chapter.aggregate")["records"]
    assert {p["unit_id"] for p in predictions} == {"v1", "v2"}
    assert {f["unit_id"] for f in features} == {"v1", "v2"}
    assert all(p["split"] == "validation" for p in predictions)
    assert all("collar_f1_3s" in row["metrics"] for row in aggregate)
    assert status["multimodal_scene_aligned"]["status"] == "not_run"
    assert status["multimodal_scene_aligned"]["reason"] == "missing_modality"
    assert status["C5_cross_attention"]["status"] == "not_run"
    assert "provenance" in status["C5_cross_attention"]["reason"] or \
        status["C5_cross_attention"]["reason"] == "checkpoint_missing"
    receipt = json.loads((tmp_path / "diagnostic" / "full" / "chapter.shortlist.receipt.json")
                         .read_text(encoding="utf-8"))
    assert receipt["evaluation_mode"] == "selection"
    assert "t0" not in json.dumps(_payload(tmp_path, "chapter.per_unit_metrics"))

    assert run04b.main(_argv(tmp_path, run04b.NOTEBOOK_ID)) == 0
    frozen = _payload(tmp_path, "chapter.frozen_configuration")["records"][0]
    assert frozen["selection_unit_ids"] == ["v1", "v2"]
    assert frozen["selection_split"] == "validation"
    assert frozen["final_test_evaluated"] is False
    assert frozen["configuration_scope"] == "ablation_predictor_only"
    assert frozen["evaluated_predictor"] == frozen["frozen_modality_variant"]
    assert frozen["joint_04a_04b_configuration_evaluated"] is False
    assert frozen["official_selection_eligible"] is False
    assert "frozen_algorithm" not in frozen
    ablation = {r["ablation"]: r for r in _payload(tmp_path, "chapter.ablation_status")["records"]}
    assert ablation["transcript+scene"]["status"] == "not_run"
    assert "t0" not in json.dumps(_payload(tmp_path, "chapter.ablation_predictions"))


def test_source_backed_scene_and_ocr_run_in_04a_and_04b(tmp_path):
    unit = _unit("v1", "validation", "c1")
    unit["transcript"] = ("alpha " * 400 + "omega " * 400).strip()
    unit["rq1_video_features"] = _video_features(
        unit, scene=[598.0], ocr=[
            {"time_sec": 100.0, "text": "alpha topic"},
            {"time_sec": 603.0, "text": "omega topic"},
        ],
    )
    _seed(tmp_path, [unit])
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 0
    feature = _payload(tmp_path, "chapter.input_features")["records"][0]
    assert feature["modalities"]["scene"]["boundaries_sec"] == [598.0]
    assert feature["modalities"]["ocr"]["observations"][1]["text"] == "omega topic"
    assert feature["modalities"]["scene"]["sha256"] == unit["rq1_video_features"]["scene"]["sha256"]
    predictions = _payload(tmp_path, "chapter.raw_predictions")["records"]
    scene_prediction = next(p for p in predictions if p["candidate"] == "multimodal_scene_aligned")
    assert scene_prediction["predictions"]["chapter_boundaries_sec"] == [598.0]

    assert run04b.main(_argv(tmp_path, run04b.NOTEBOOK_ID)) == 0
    status = {row["ablation"]: row for row in _payload(tmp_path, "chapter.ablation_status")["records"]}
    assert status["transcript+scene"]["status"] == "run"
    assert status["transcript+ocr"]["status"] == "run"
    assert status["transcript+visual"]["status"] == "not_run"
    ablation = _payload(tmp_path, "chapter.ablation_predictions")["records"]
    assert next(p for p in ablation if p["ablation_variant"] == "transcript+scene")["predictions"]["chapter_boundaries_sec"] == [598.0]
    assert next(p for p in ablation if p["ablation_variant"] == "transcript+ocr")["predictions"]["chapter_boundaries_sec"] == [603.0]


def test_source_backed_visual_acoustic_and_full_ablation_run(tmp_path):
    unit = _unit("v1", "validation", "c1")
    unit["transcript"] = ("alpha " * 400 + "omega " * 400).strip()
    video = _video_features(unit, scene=[598.0], ocr=[
        {"time_sec": 100.0, "text": "alpha topic"},
        {"time_sec": 603.0, "text": "omega topic"},
    ])
    for name, times in (("visual", [101.0, 601.0]), ("acoustic", [102.0, 604.0])):
        observations = [{"time_sec": time, "change_score": score} for time, score in zip(times, [0.1, 0.9])]
        extractor, config = f"fixture_{name}", {"version": 1}
        digest = hashlib.sha256(json.dumps({
            "content": observations, "extractor": extractor, "config": config,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        video[name] = {
            "available": True, "observations": observations, "sha256": digest,
            "extractor": extractor, "config": config,
        }
    unit["rq1_video_features"] = video
    _seed(tmp_path, [unit])
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 0
    assert run04b.main(_argv(tmp_path, run04b.NOTEBOOK_ID)) == 0
    status = {r["ablation"]: r for r in _payload(tmp_path, "chapter.ablation_status")["records"]}
    for name in ("transcript+visual", "transcript+acoustic", "all_modalities"):
        assert status[name]["status"] == "run"
    predictions = {r["ablation_variant"]: r["predictions"]["chapter_boundaries_sec"]
                   for r in _payload(tmp_path, "chapter.ablation_predictions")["records"]}
    assert predictions["transcript+visual"] == [601.0]
    assert predictions["transcript+acoustic"] == [604.0]
    assert predictions["all_modalities"] == [603.0]

    video["visual"]["observations"][1]["change_score"] = 1.1
    with pytest.raises(ChapterContractError, match="change_score"):
        build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)


def test_invalid_candidate_prediction_keeps_unit_in_selection_denominator(tmp_path, monkeypatch):
    _seed(tmp_path, [_unit("v1", "validation", "c1")])
    monkeypatch.setitem(
        run04a.HEURISTIC_CANDIDATES,
        "fixed_window_300s",
        ((), lambda unit, feature: [float("nan")]),
    )
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 0
    rows = _payload(tmp_path, "chapter.per_unit_metrics")["records"]
    failed = next(row for row in rows if row["candidate"] == "fixed_window_300s")
    assert failed["score_status"] == "candidate_unit_failure"
    assert failed["metrics"]["collar_f1_3s"] == 0.0
    assert failed["metrics"]["pk"] is None
    aggregate = _payload(tmp_path, "chapter.aggregate")["records"]
    fixed = next(row for row in aggregate if row["candidate"] == "fixed_window_300s")
    assert fixed["unit_count"] == 1
    assert fixed["failure_count"] == 1
    monkeypatch.setitem(
        run04b.ABLATIONS,
        "duration_only",
        ((), lambda unit, feature: [feature["duration_sec"] + 1]),
    )
    assert run04b.main(_argv(tmp_path, run04b.NOTEBOOK_ID)) == 0
    ablations = _payload(tmp_path, "chapter.ablation_metrics")["records"]
    failed_ablation = next(row for row in ablations if row["ablation_variant"] == "duration_only")
    assert failed_ablation["score_status"] == "candidate_unit_failure"
    assert failed_ablation["metrics"]["collar_f1_3s"] == 0.0


def test_predictor_runtime_error_aborts_selection(tmp_path, monkeypatch):
    _seed(tmp_path, [_unit("v1", "validation", "c1")])

    def broken_predictor(unit, feature):
        raise RuntimeError("checkpoint could not load")

    monkeypatch.setitem(run04a.HEURISTIC_CANDIDATES, "fixed_window_300s", ((), broken_predictor))
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 1
    assert not (tmp_path / "official" / "full" / "chapter.aggregate.receipt.json").exists()


def test_video_feature_identity_and_timestamps_fail_closed():
    unit = _unit("v1", "validation", "c1")
    unit["rq1_video_features"] = _video_features(
        unit, scene=[600.0], ocr=[{"time_sec": 500.0, "text": "slide"}],
    )
    assert build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)["modalities"]["scene"]["available"]
    unit["rq1_video_features"]["source_sha256"] = HASH_B
    with pytest.raises(ChapterContractError, match="source_sha256"):
        build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)
    unit["rq1_video_features"]["source_sha256"] = unit["sha256"]
    unit["rq1_video_features"]["scene"]["boundaries_sec"] = [1200.0]
    with pytest.raises(ChapterContractError, match="timestamps outside media"):
        build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)
    unit["rq1_video_features"]["scene"]["boundaries_sec"] = [600.0]
    unit["rq1_video_features"]["scene"]["sha256"] = HASH_B
    with pytest.raises(ChapterContractError, match="feature sha256 mismatch"):
        build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)


def test_empty_video_features_do_not_run_multimodal(tmp_path):
    unit = _unit("v1", "validation", "c1")
    unit["rq1_video_features"] = _video_features(unit, scene=[], ocr=[])
    _seed(tmp_path, [unit])
    assert run04a.main(_argv(tmp_path, run04a.NOTEBOOK_ID)) == 0
    status = {row["candidate"]: row for row in _payload(tmp_path, "chapter.candidate_status")["records"]}
    assert status["multimodal_scene_aligned"]["status"] == "not_run"
    assert run04b.main(_argv(tmp_path, run04b.NOTEBOOK_ID)) == 0
    status = {row["ablation"]: row for row in _payload(tmp_path, "chapter.ablation_status")["records"]}
    assert status["transcript+scene"]["status"] == "not_run"
    assert status["transcript+ocr"]["status"] == "not_run"


def test_multimodal_predictors_never_fall_back_to_text_only():
    unit = _unit("v1", "validation", "c1")
    unit["transcript"] = ("alpha " * 400 + "omega " * 400).strip()
    feature = {
        "duration_sec": 1200.0,
        "modalities": {
            "scene": {"boundaries_sec": [100.0]},
            "ocr": {"observations": [{"time_sec": 100.0, "text": "alpha topic"}]},
        },
    }
    assert run04a.lexical_texttiling_boundaries(unit["transcript"], 1200.0) == [600.0]
    assert run04a.transcript_scene_boundaries(unit, feature) == []
    assert run04b.transcript_ocr_boundaries(unit, feature) == []


def test_blank_ocr_sample_preserved_but_not_a_topic_change():
    unit = _unit("v1", "validation", "c1")
    unit["transcript"] = ("alpha " * 400 + "omega " * 400).strip()
    observations = [
        {"time_sec": 100.0, "text": "alpha topic"},
        {"time_sec": 590.0, "text": ""},
        {"time_sec": 603.0, "text": "omega topic"},
    ]
    unit["rq1_video_features"] = _video_features(unit, scene=[], ocr=observations)
    feature = build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)
    assert feature["modalities"]["ocr"]["observations"] == observations
    assert run04b.transcript_ocr_boundaries(unit, feature) == [603.0]

    blank_only = _video_features(unit, scene=[], ocr=[{"time_sec": 100.0, "text": ""}])
    blank_only["ocr"]["available"] = True
    unit["rq1_video_features"] = blank_only
    with pytest.raises(ChapterContractError, match="without text"):
        build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)


def test_feature_records_must_match_units_exactly():
    unit = _unit("v1", "validation", "c1")
    feature = build_input_feature_record(unit, evaluation_mode="selection", code_sha256=HASH_A)
    index_features([feature], [unit], "selection")
    other = dict(unit, sha256=hashlib.sha256(b"other media").hexdigest())
    with pytest.raises(ChapterContractError, match="source_sha256"):
        index_features([feature], [other], "selection")
    with pytest.raises(ChapterContractError, match="do not match"):
        index_features([feature], [unit, _unit("v2", "validation", "c2")], "selection")
    with pytest.raises(ChapterContractError, match="evaluation_mode"):
        index_features([feature], [unit], "final_test")


def test_final_test_artifact_cannot_feed_selection_consumer(tmp_path):
    producer = _context(tmp_path, "00c_dataset_eda_and_freeze", mode="final_test")
    write_json_artifact(producer, "chapter.input_features", [{"unit_id": "x"}])
    write_run_manifest(producer)
    with pytest.raises(ValueError, match="evaluation_mode"):
        read_json_artifact(_context(tmp_path, run04b.NOTEBOOK_ID), "chapter.input_features")
    with pytest.raises(ValueError, match="evaluation_mode"):
        read_json_artifact(_context(tmp_path, "05a_summarization_benchmark", mode=None),
                           "chapter.input_features")


def test_learned_checkpoint_requires_disjoint_train_provenance(tmp_path):
    ckpt = tmp_path / "c5.pt"
    units = [_unit("v1", "validation", "c1")]
    assert learned_candidate_status("C5_cross_attention", units,
                                    checkpoints={})["reason"] == "checkpoint_missing"
    ckpt.write_bytes(b"weights")
    status = learned_candidate_status("C5_cross_attention", units,
                                      checkpoints={"C5_cross_attention": ckpt})
    assert status["status"] == "not_run" and "provenance_missing" in status["reason"]
    provenance = {
        "candidate": "C5_cross_attention", "architecture": "fixture", "code_sha256": HASH_A,
        "seed": 1, "train_dataset_id": DATASET, "train_unit_ids": ["r1"],
        "train_course_ids": ["c1"], "train_data_sha256": HASH_B,
        "checkpoint_sha256": hashlib.sha256(b"weights").hexdigest(),
    }
    ckpt.with_suffix(".provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    status = learned_candidate_status("C5_cross_attention", units,
                                      checkpoints={"C5_cross_attention": ckpt})
    assert status["reason"].startswith("train_eval_leakage")


def test_repository_c5_checkpoint_is_not_run():
    status = learned_candidate_status("C5_cross_attention", [_unit("v1", "validation", "cX")])
    assert status["status"] == "not_run"
