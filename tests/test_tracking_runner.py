import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("trackeval")
sv = pytest.importorskip("supervision")

from experiments.scripts import tracking_runner as tr
from experiments.scripts import tracking_scoring as ts

REGISTRY = Path(__file__).resolve().parents[1] / "experiments/registry/datasets/tracker-search-space-dancetrack-261027.json"


# ---------------------------------------------------------------- helpers
def _gt(n=10):
    """Two disjoint 50x50 tracks (ids 1 and 2) in every frame; MOT rows with conf=1, class=1, vis=1."""
    rows = [(f, i, x, 0, 50, 50, 1, 1, 1) for f in range(1, n + 1) for i, x in ((1, 0), (2, 500))]
    return np.array(rows, dtype=float)


def _dets_from_gt(gt):
    return np.column_stack([gt[:, 0], np.full(len(gt), -1.0), gt[:, 2:6], np.ones(len(gt))])


class IouTracker:
    """Greedy nearest-box tracker: keeps the id of the previous box with the highest IoU, else a new id."""

    def __init__(self, rename_after=None, unconfirmed_first=False, duplicate=False, boom_at=None):
        self.prev, self.next_id, self.t = [], 1, 0
        self.rename_after, self.unconfirmed_first, self.duplicate, self.boom_at = rename_after, unconfirmed_first, duplicate, boom_at

    def update(self, detections, frame=None):
        self.t += 1
        if self.boom_at == self.t:
            raise RuntimeError("boom")
        xyxy, ids, cur = detections.xyxy, [], []
        for box in xyxy:
            xywh = np.array([[box[0], box[1], box[2] - box[0], box[3] - box[1]]])
            best, best_iou = None, 0.3
            for pid, pbox in self.prev:
                iou = ts.box_iou_xywh(xywh, pbox)[0, 0]
                if iou > best_iou:
                    best, best_iou = pid, iou
            if best is None:
                best, self.next_id = self.next_id, self.next_id + 1
                if self.unconfirmed_first:
                    ids.append(-1)
                    cur.append((best, xywh))
                    continue
            ids.append(best)
            cur.append((best, xywh))
        self.prev = cur
        if self.duplicate and len(ids) > 1:
            ids = [ids[0]] * len(ids)
        if self.rename_after is not None and self.t > self.rename_after:
            ids = [i + 100 if i >= 0 else i for i in ids]
        out = sv.Detections(xyxy=xyxy, confidence=detections.confidence, class_id=detections.class_id)
        out.tracker_id = np.array(ids, dtype=int)
        return out


def _run(gt, tracker, n=10, **kw):
    return tr.run_sequence(tracker, _dets_from_gt(gt), n, **kw)


# ---------------------------------------------------------------- detection I/O
def test_dets_roundtrip_and_checksum(tmp_path):
    rows = tr.det_rows(3, np.array([[1.5, 2.5, 30, 40], [5, 6, 7, 8]]), np.array([0.9, 0.2]))
    tr.write_mot_dets(tmp_path / "d.txt", rows)
    back = tr.read_mot_dets(tmp_path / "d.txt")
    assert np.allclose(back, rows)
    assert tr.dets_checksum(back) == tr.dets_checksum(rows)
    edited = rows.copy()
    edited[0, 2] += 0.001
    assert tr.dets_checksum(edited) != tr.dets_checksum(rows)


def test_write_returns_stored_values_so_checksum_survives_reload(tmp_path):
    rng = np.random.default_rng(0)
    raw = tr.det_rows(1, rng.random((5, 4)) * 1000 + 0.123456789, rng.random(5))      # more digits than the file keeps
    stored = tr.write_mot_dets(tmp_path / "d.txt", raw)
    assert tr.dets_checksum(stored) == tr.dets_checksum(tr.read_mot_dets(tmp_path / "d.txt"))
    assert tr.dets_checksum(stored) != tr.dets_checksum(raw)         # the unrounded input is NOT what is frozen


def test_empty_detection_file_roundtrip(tmp_path):
    tr.write_mot_dets(tmp_path / "e.txt", np.zeros((0, 7)))
    assert tr.read_mot_dets(tmp_path / "e.txt").shape == (0, 7)


# ---------------------------------------------------------------- search space
def test_specs_refuse_unapproved(tmp_path):
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reg["status"] = "proposed"
    bad = tmp_path / "ss.json"
    bad.write_text(json.dumps(reg), encoding="utf-8")
    with pytest.raises(ValueError, match="approved"):
        tr.load_specs(bad)


def test_frozen_registry_loads_four_families():
    specs = tr.load_specs(REGISTRY)
    assert set(specs) == {"sort", "bytetrack", "ocsort", "botsort"}
    assert specs["botsort"].needs_frame and not specs["sort"].needs_frame


def test_sample_configs_default_first_and_reproducible():
    specs = tr.load_specs(REGISTRY)
    a, b = tr.sample_configs(specs["sort"], 20, 20261027), tr.sample_configs(specs["sort"], 20, 20261027)
    assert len(a) == 21 and a == b
    assert a[0] == specs["sort"].defaults                      # config 0 = published default
    assert tr.sample_configs(specs["sort"], 20, 1) != a        # another seed, other configs


def test_sample_configs_within_search_space():
    specs = tr.load_specs(REGISTRY)
    for spec in specs.values():
        for cfg in tr.sample_configs(spec, 20, 7)[1:]:
            for p, rule in spec.search.items():
                v = cfg[p]
                assert v in rule["values"] if rule["type"] == "choice" else rule["low"] <= v <= rule["high"]


def test_shared_params_identical_across_trackers_same_seed():
    specs = tr.load_specs(REGISTRY)
    cfgs = {k: tr.sample_configs(s, 20, 20261027) for k, s in specs.items()}
    for i in range(1, 21):
        for p in ("lost_track_buffer", "minimum_consecutive_frames"):
            assert len({cfgs[k][i][p] for k in cfgs}) == 1


# ---------------------------------------------------------------- running a sequence
def test_gt_as_detections_with_iou_tracker_is_perfect():
    gt = _gt()
    run = _run(gt, IouTracker())
    assert run["ok"] and run["n_unconfirmed_dropped"] == 0
    s = ts.score_sequences([ts.evaluate_sequence(gt, run["rows"], 10)])
    assert s["HOTA"] == pytest.approx(100.0) and s["IDSW"] == 0


def test_id_swap_halfway_lowers_assa_and_counts_two_switches():
    gt = _gt()
    run = _run(gt, IouTracker(rename_after=5))      # both tracks get new ids after frame 5: 2 identity switches
    s = ts.score_sequences([ts.evaluate_sequence(gt, run["rows"], 10)])
    assert s["IDSW"] == 2 and s["DetA"] == pytest.approx(100.0) and s["AssA"] < 100.0


def test_unconfirmed_rows_are_dropped_not_written():
    gt = _gt()
    run = _run(gt, IouTracker(unconfirmed_first=True))
    assert run["ok"] and run["n_unconfirmed_dropped"] == 2          # first frame of each of the 2 tracks
    assert (run["rows"][:, 1] >= 0).all() and len(run["rows"]) == len(gt) - 2


def test_empty_frames_and_empty_sequence():
    gt = _gt()
    sparse = gt[gt[:, 0].astype(int) % 2 == 0]                      # detections only on even frames
    run = tr.run_sequence(IouTracker(), _dets_from_gt(sparse), 10)
    assert run["ok"] and set(run["rows"][:, 0].astype(int)) == {2, 4, 6, 8, 10}
    none = tr.run_sequence(IouTracker(), np.zeros((0, 7)), 10)
    assert none["ok"] and none["rows"].shape == (0, 7) and none["fps"] is not None


def test_duplicate_id_in_frame_is_a_failure_with_reason():
    run = _run(_gt(), IouTracker(duplicate=True))
    assert not run["ok"] and run["reason"] == "duplicate_id_in_frame:1"


def test_exception_is_recorded_not_raised():
    run = _run(_gt(), IouTracker(boom_at=4))
    assert not run["ok"] and run["reason"].startswith("exception:RuntimeError:boom")


def test_missing_frame_for_frame_hungry_tracker():
    run = _run(_gt(), IouTracker(), needs_frame=True, frames=None)
    assert not run["ok"] and run["reason"] == "frame_missing:1"


def test_detection_outside_sequence_is_rejected():
    with pytest.raises(ValueError):
        tr.run_sequence(IouTracker(), _dets_from_gt(_gt(12)), 10)


def test_timing_excludes_warmup_frames():
    run = _run(_gt(), IouTracker(), warmup=3)
    assert run["update_seconds"] > 0 and run["median_update_ms"] > 0 and run["fps"] > 0


# ---------------------------------------------------------------- resume
def _store_run(store, params, dets, calls):
    def run():
        calls.append(1)
        return tr.run_sequence(IouTracker(), dets, 10)
    return tr.run_or_load(store, "sort", 0, "seqA", params, dets, run)


def test_resume_skips_finished_run_and_reruns_on_change(tmp_path):
    dets, calls, params = _dets_from_gt(_gt()), [], {"lost_track_buffer": 30}
    first = _store_run(tmp_path, params, dets, calls)
    again = _store_run(tmp_path, params, dets, calls)
    assert len(calls) == 1 and not first["loaded"] and again["loaded"]
    assert np.allclose(first["rows"], again["rows"])
    edited = dets.copy()
    edited[0, 2] += 1.0
    _store_run(tmp_path, params, edited, calls)                      # detections changed -> rerun
    assert len(calls) == 2
    _store_run(tmp_path, {"lost_track_buffer": 60}, edited, calls)   # parameters changed -> rerun
    assert len(calls) == 3


def test_failed_run_is_retried(tmp_path):
    dets, calls = _dets_from_gt(_gt()), []

    def failing():
        calls.append(1)
        return tr.run_sequence(IouTracker(boom_at=2), dets, 10)
    tr.run_or_load(tmp_path, "sort", 0, "s", {}, dets, failing)
    tr.run_or_load(tmp_path, "sort", 0, "s", {}, dets, failing)
    assert len(calls) == 2


# ---------------------------------------------------------------- scoring / decisions
def test_failed_sequence_is_not_scored_as_zero():
    gt = _gt()
    ok = tr.score_run(gt, _run(gt, IouTracker()), 10)
    bad = tr.score_run(gt, _run(gt, IouTracker(boom_at=3)), 10)
    out = tr.score_config({"a": ok, "b": bad})
    assert out["score"] is None and "b" in out["failed"]
    assert tr.score_config({"a": ok})["score"]["HOTA"] == pytest.approx(100.0)


def test_paired_decision_separates_perfect_from_swapped_and_equal_is_indistinguishable():
    gt = _gt()
    perfect = [ts.evaluate_sequence(gt, _run(gt, IouTracker())["rows"], 10) for _ in range(6)]
    swapped = [ts.evaluate_sequence(gt, _run(gt, IouTracker(rename_after=5))["rows"], 10) for _ in range(6)]
    assert tr.paired_decision(perfect, swapped, resamples=200, seed=1)["decision"] == "a_better"
    assert tr.paired_decision(perfect, perfect, resamples=200, seed=1)["decision"] == "indistinguishable"


def test_estimate_budget_arithmetic():
    out = tr.estimate_budget({"sort": 2.0}, n_frames=1000, configs_per_tracker={"sort": 21}, max_hours=1.0)
    assert out["total_hours"] == pytest.approx(2.0 / 1000 * 1000 * 21 * 1.3 / 3600)      # 0.015167 h
    assert out["within_budget"] is True
    assert tr.estimate_budget({"sort": 2.0}, 1000, {"sort": 21}, max_hours=0.01)["within_budget"] is False


# ---------------------------------------------------------------- source (b) input handling
def test_yolox_letterbox_scale_channel_order_and_normalisation():
    cv2 = pytest.importorskip("cv2")
    img = np.zeros((1080, 1920, 3), np.uint8)
    img[:] = (10, 100, 200)                                            # BGR
    x, scale = tr.yolox_letterbox(img)
    assert x.shape == (1, 3, 800, 1440) and x.dtype == np.float32
    assert scale == pytest.approx(800 / 1080)
    mean, std = np.array(tr.YOLOX_MEAN), np.array(tr.YOLOX_STD)
    expect_rgb = (np.array([200, 100, 10]) / 255 - mean) / std          # channel 0 must be R
    assert np.allclose(x[0, :, 0, 0], expect_rgb, atol=1e-5)
    pad = (114 / 255 - mean) / std                                      # bottom-right is padding (114)
    assert np.allclose(x[0, :, -1, -1], pad, atol=1e-5)


def test_yolox_letterbox_matches_the_smoke_script_variant():
    pytest.importorskip("cv2")
    from experiments.scripts import yolox_checkpoint_smoke as smoke
    img = (np.random.default_rng(0).random((540, 960, 3)) * 255).astype(np.uint8)
    mine, s1 = tr.yolox_letterbox(img)
    ref, s2 = smoke.preprocess(img, tr.YOLOX_INPUT_SIZE, "imagenet_rgb")
    assert s1 == pytest.approx(s2) and np.allclose(mine, ref, atol=1e-5)


def test_yolox_outputs_to_rows_hand_checked():
    out = np.array([[10, 20, 110, 220, 0.8, 0.5, 0]], float)           # letterbox px, scale 0.5
    rows = tr.yolox_outputs_to_rows(out, 0.5, frame=7)
    assert rows.tolist() == [[7, -1, 20, 40, 200, 400, pytest.approx(0.4)]]
    assert tr.yolox_outputs_to_rows(None, 0.5, 1).shape == (0, 7)


# ---------------------------------------------------------------- real library (skipped without `trackers`)
@pytest.fixture(scope="module")
def specs():
    pytest.importorskip("trackers")
    return tr.load_specs(REGISTRY)


@pytest.mark.parametrize("family", ["sort", "bytetrack", "ocsort"])
def test_real_trackers_track_two_disjoint_boxes(specs, family):
    gt = _gt(30)
    tracker = tr.build_tracker(specs[family], specs[family].defaults, frame_rate=20)
    run = tr.run_sequence(tracker, _dets_from_gt(gt), 30)
    assert run["ok"], run["reason"]
    assert len(set(run["rows"][:, 1].astype(int))) == 2                # one id per dancer, no fragmentation
    s = ts.score_sequences([ts.evaluate_sequence(gt, run["rows"], 30)])
    assert s["HOTA"] > 80.0 and s["IDSW"] == 0                         # only the activation delay costs recall


def test_real_botsort_needs_frames_and_runs_with_them(specs):
    spec, gt = specs["botsort"], _gt(30)
    img = np.zeros((1080, 1920, 3), np.uint8)
    missing = tr.run_sequence(tr.build_tracker(spec, spec.defaults, 20), _dets_from_gt(gt), 30, frames=None, needs_frame=True)
    assert not missing["ok"] and missing["reason"] == "frame_missing:1"
    run = tr.run_sequence(tr.build_tracker(spec, spec.defaults, 20), _dets_from_gt(gt), 30, frames=lambda t: img, needs_frame=True)
    assert run["ok"], run["reason"]

