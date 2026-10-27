import numpy as np
import pytest

pytest.importorskip("trackeval")

from experiments.scripts import paired_bootstrap as pb
from experiments.scripts import tracking_scoring as ts


def _rows(spec):
    """spec: list of (frame, id, x, y, w, h) -> MOT rows with conf=1, class=1, vis=1."""
    return np.array([r + (1, 1, 1) for r in spec], dtype=float)


def _two_tracks(n=10):
    """Track A at x=0 and track B at x=500, both 50x50, present in all n frames (disjoint boxes)."""
    a = [(f, 1, 0, 0, 50, 50) for f in range(1, n + 1)]
    b = [(f, 2, 500, 0, 50, 50) for f in range(1, n + 1)]
    return a, b


def test_perfect_prediction_scores_100():
    a, b = _two_tracks()
    gt = _rows(a + b)
    s = ts.score_sequences([ts.evaluate_sequence(gt, gt, 10)])
    for k in ("HOTA", "DetA", "AssA", "LocA", "IDF1", "MOTA"):
        assert s[k] == pytest.approx(100.0)
    assert (s["IDSW"], s["Frag"], s["FP"], s["FN"]) == (0, 0, 0, 0)


def test_id_swap_halfway_has_hand_derived_scores():
    # A is predicted as id 1 for frames 1-5 and id 2 for 6-10; B the other way round.
    a, b = _two_tracks()
    gt = _rows(a + b)
    pred = _rows([(f, 1 if f <= 5 else 2, 0, 0, 50, 50) for f in range(1, 11)] +
                 [(f, 2 if f <= 5 else 1, 500, 0, 50, 50) for f in range(1, 11)])
    s = ts.score_sequences([ts.evaluate_sequence(gt, pred, 10)])
    assert s["DetA"] == pytest.approx(100.0) and s["LocA"] == pytest.approx(100.0)
    assert s["AssA"] == pytest.approx(100 / 3)                          # each match: 5 / (5 + 5 + 5)
    assert s["HOTA"] == pytest.approx(100 * np.sqrt(1 / 3))
    assert s["IDF1"] == pytest.approx(50.0)                             # IDTP 10, IDFN 10, IDFP 10
    assert s["IDSW"] == 2 and s["MOTA"] == pytest.approx(90.0)          # 1 - 2/20


def test_missed_detections_lower_deta_and_assa_of_the_interrupted_track():
    a, b = _two_tracks()
    gt = _rows(a + b)
    pred = _rows(a + b[:5])                                             # B lost from frame 6 on: 15 of 20 found
    s = ts.score_sequences([ts.evaluate_sequence(gt, pred, 10)])
    # DetA = 15 / (15 + 5 + 0). AssA is averaged over the 15 true positives: the 10 of A score 1,
    # the 5 of B score 5 / (5 + 5 + 0) = 0.5 (its other 5 ground-truth boxes count as misses of that association).
    assert s["DetA"] == pytest.approx(75.0) and s["AssA"] == pytest.approx(100 * (10 * 1 + 5 * 0.5) / 15)
    assert s["HOTA"] == pytest.approx(100 * np.sqrt(0.75 * 12.5 / 15)) and s["FN"] == 5 and s["FP"] == 0
    assert s["MOTA"] == pytest.approx(75.0)


def test_localisation_error_lowers_loca_not_deta_at_low_alpha():
    a, b = _two_tracks()
    gt = _rows(a)
    pred = _rows([(f, 1, 5, 0, 50, 50) for f in range(1, 11)])          # shifted 5 px: IoU = 45*50/(5000-2250) = 0.818
    s = ts.score_sequences([ts.evaluate_sequence(gt, pred, 10)])
    assert 0 < s["LocA"] < 100 and s["HOTA"] < 100
    assert s["MOTA"] == pytest.approx(100.0)                            # CLEAR uses a fixed 0.5 threshold


def test_zero_marked_ground_truth_is_ignored_and_duplicate_ids_rejected():
    a, b = _two_tracks()
    gt = _rows(a + b)
    gt[len(a):, 6] = 0                                                   # all of B marked "do not evaluate"
    pred = _rows(a)
    s = ts.score_sequences([ts.evaluate_sequence(gt, pred, 10)])
    assert s["HOTA"] == pytest.approx(100.0) and s["FN"] == 0
    with pytest.raises(ValueError):
        ts.prepare_sequence(gt, _rows([(1, 1, 0, 0, 5, 5), (1, 1, 9, 9, 5, 5)]), 10)
    with pytest.raises(ValueError):
        ts.prepare_sequence(gt, _rows([(11, 1, 0, 0, 5, 5)]), 10)       # frame beyond sequence length


def _random_sequence(rng, n_frames=40, n_tracks=6):
    gt, pred = [], []
    for tid in range(n_tracks):
        start, end = sorted(rng.integers(1, n_frames + 1, 2))
        x0, y0 = rng.uniform(0, 600, 2)
        vx, vy = rng.normal(0, 2, 2)
        pid = tid + 100
        for f in range(start, end + 1):
            box = (x0 + vx * f, y0 + vy * f, 40.0, 80.0)
            gt.append((f, tid, *box))
            if rng.random() < 0.85:
                if rng.random() < 0.05:
                    pid += 1000                                          # identity switch
                pred.append((f, pid, box[0] + rng.normal(0, 3), box[1] + rng.normal(0, 3), box[2], box[3]))
    for _ in range(15):                                                  # false positives
        f = int(rng.integers(1, n_frames + 1))
        pred.append((f, 5000 + _, float(rng.uniform(0, 600)), float(rng.uniform(0, 400)), 40.0, 80.0))
    return _rows(gt), _rows(pred)


def test_agrees_with_official_trackeval_evaluator(tmp_path):
    te = ts.load_trackeval()
    rng = np.random.default_rng(11)
    lengths = {"seqA": 40, "seqB": 25, "seqC": 60}
    per_seq = []
    (tmp_path / "gt").mkdir()
    (tmp_path / "trk" / "t" / "data").mkdir(parents=True)
    for seq, n in lengths.items():
        gt, pred = _random_sequence(rng, n_frames=n)
        per_seq.append(ts.evaluate_sequence(gt, pred, n))
        (tmp_path / "gt" / seq / "gt").mkdir(parents=True)
        (tmp_path / "gt" / seq / "gt" / "gt.txt").write_text(ts.format_mot_rows(gt))
        (tmp_path / "trk" / "t" / "data" / f"{seq}.txt").write_text(ts.format_mot_rows(pred))
    ev = te.Evaluator({"USE_PARALLEL": False, "PRINT_RESULTS": False, "PRINT_ONLY_COMBINED": False, "PRINT_CONFIG": False,
                       "TIME_PROGRESS": False, "OUTPUT_SUMMARY": False, "OUTPUT_DETAILED": False, "PLOT_CURVES": False,
                       "OUTPUT_EMPTY_CLASSES": True, "BREAK_ON_ERROR": True, "LOG_ON_ERROR": str(tmp_path / "err.log"),
                       "DISPLAY_LESS_PROGRESS": True, "NUM_PARALLEL_CORES": 1})
    ds = te.datasets.MotChallenge2DBox({
        "GT_FOLDER": str(tmp_path / "gt"), "TRACKERS_FOLDER": str(tmp_path / "trk"), "OUTPUT_FOLDER": str(tmp_path / "out"),
        "TRACKERS_TO_EVAL": ["t"], "SKIP_SPLIT_FOL": True, "DO_PREPROC": False, "PRINT_CONFIG": False,
        "SEQ_INFO": dict(lengths), "GT_LOC_FORMAT": "{gt_folder}/{seq}/gt/gt.txt"})
    metrics = [te.metrics.HOTA(), te.metrics.CLEAR({"PRINT_CONFIG": False}), te.metrics.Identity({"PRINT_CONFIG": False})]
    res, _ = ev.evaluate([ds], metrics)
    official = res["MotChallenge2DBox"]["t"]["COMBINED_SEQ"]["pedestrian"]
    mine = ts.combine(per_seq)
    assert np.allclose(mine["HOTA"]["HOTA"], official["HOTA"]["HOTA"], atol=1e-12)
    assert np.allclose(mine["HOTA"]["AssA"], official["HOTA"]["AssA"], atol=1e-12)
    assert np.allclose(mine["HOTA"]["LocA"], official["HOTA"]["LocA"], atol=1e-12)
    for key in ("MOTA", "IDSW", "Frag", "MT", "ML", "CLR_TP", "CLR_FN", "CLR_FP"):
        assert mine["CLEAR"][key] == pytest.approx(official["CLEAR"][key], abs=1e-12), key
    for key in ("IDF1", "IDTP", "IDFN", "IDFP"):
        assert mine["Identity"][key] == pytest.approx(official["Identity"][key], abs=1e-12), key


def test_video_bootstrap_pairs_trackers_on_the_same_videos():
    rng = np.random.default_rng(21)
    good, bad = [], []
    for _ in range(12):
        gt, pred = _random_sequence(rng, n_frames=30)
        good.append(ts.evaluate_sequence(gt, pred, 30))
        drop = pred[rng.random(len(pred)) > 0.4]                          # tracker B misses 40% of its boxes
        bad.append(ts.evaluate_sequence(gt, drop, 30))
    mult = pb.cluster_multiplicities(12, None, resamples=60, seed=3)
    res = pb.paired_bootstrap(ts.metric_on_resample(good), ts.metric_on_resample(bad), mult)
    assert res["delta"] == pytest.approx(ts.score_sequences(good)["HOTA"] - ts.score_sequences(bad)["HOTA"])
    assert res["delta"] > 2.0 and res["delta_lo"] > 0 and pb.decide_difference(res, 2.0) == "a_better"
