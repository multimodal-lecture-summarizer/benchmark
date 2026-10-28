import numpy as np
import pytest

from experiments.scripts import detection_tracking_eda as e


def _gt(rows):
    return np.array([r + (1, 1, 1) for r in rows], dtype=float)  # frame,id,x,y,w,h,conf,cls,vis


def test_design_effect_fully_clustered_and_independent():
    clustered = e.design_effect(np.repeat([0, 1, 2], 4), [0] * 4 + [1] * 4 + [2] * 4)
    assert clustered["icc"] == pytest.approx(1.0)
    assert clustered["deff"] == pytest.approx(4.0) and clustered["n_eff"] == pytest.approx(3.0)
    indep = e.design_effect(np.repeat(np.arange(6), 2), [0, 1] * 6)
    assert indep["icc"] == 0.0 and indep["deff"] == pytest.approx(1.0)
    assert np.isnan(e.design_effect([1, 2, 3], [1, 2, 3])["icc"])  # singletons: undefined


def test_cluster_bootstrap_constant_and_group_resampling():
    ci = e.cluster_bootstrap_mean_ci([1, 1, 2, 2, 3, 3], [5.0] * 6, resamples=200, seed=1)
    assert ci["mean"] == ci["lo"] == ci["hi"] == 5.0
    g = np.repeat(np.arange(10), 5)
    v = np.repeat(np.arange(10), 5).astype(float)           # all variance between groups
    wide = e.cluster_bootstrap_mean_ci(g, v, resamples=2000, seed=2)
    assert wide["lo"] < 4.5 < wide["hi"] and wide["hi"] - wide["lo"] > 1.0


def test_components_and_group_merging():
    comp = e.connected_components("abcdef", [("a", "b"), ("b", "c"), ("d", "e")])
    assert comp["a"] == comp["b"] == comp["c"] and comp["d"] == comp["e"] != comp["a"]
    assert len({comp["f"], comp["a"], comp["d"]}) == 3
    merged = e.merged_group_labels({"a": "g1", "b": "g2", "c": "g3"}, [("a", "b")])
    assert merged["a"] == merged["b"] != merged["c"]


def test_ncc_known_values():
    x = np.arange(16.0).reshape(4, 4)
    assert e.ncc(x, x) == pytest.approx(1.0)
    assert e.ncc(x, -x) == pytest.approx(-1.0)
    assert e.ncc(x, np.ones((4, 4))) == 0.0


def test_compare_samples_and_multiplicity():
    r = e.compare_samples([1, 2, 3], [4, 5, 6])
    assert r["cliffs_delta"] == pytest.approx(-1.0) and r["ks"] == pytest.approx(1.0)
    assert e.compare_samples([4, 5, 6], [1, 2, 3])["cliffs_delta"] == pytest.approx(1.0)
    assert e.holm_adjust([0.01, 0.04, 0.03]).tolist() == pytest.approx([0.03, 0.06, 0.06])
    assert [e.effect_label(d) for d in (0.1, 0.2, 0.4, -0.6)] == ["negligible", "small", "medium", "large"]


def test_track_table_and_gaps():
    gt = _gt([(1, 1, 0, 0, 10, 10), (2, 1, 0, 0, 10, 10), (3, 1, 0, 0, 10, 10),
              (1, 2, 0, 0, 10, 20), (3, 2, 0, 0, 10, 20),
              (1, 3, 0, 0, 10, 30), (5, 3, 0, 0, 10, 30)])
    t = e.mot_track_table(gt).set_index("id")
    assert t.loc[1, ["n_frames", "span", "n_gaps"]].tolist() == [3, 3, 0]
    assert t.loc[2, ["n_frames", "span", "n_gaps", "max_gap"]].tolist() == [2, 3, 1, 1]
    assert t.loc[3, ["span", "missing", "h_median"]].tolist() == [5, 3, 30.0]
    assert sorted(e.mot_gap_lengths(gt).tolist()) == [1, 3]


def test_motion_speed_and_turn_angle():
    straight = _gt([(f, 1, f * 1.0, 0, 10, 10) for f in range(1, 6)])
    m = e.mot_motion(straight)
    assert m["speed"] == pytest.approx([0.1] * 4) and m["turn_deg"] == pytest.approx([0.0] * 3, abs=1e-6)
    # right, right, up: one 90 degree turn out of two angle samples
    path = [(1, 1, 0, 0), (2, 1, 1, 0), (3, 1, 2, 0), (4, 1, 2, -1)]
    turn = e.mot_motion(_gt([(f, i, x, y, 10, 10) for f, i, x, y in path]))["turn_deg"]
    assert turn == pytest.approx([0.0, 90.0], abs=1e-6)
    still = e.mot_motion(_gt([(f, 1, 0, 0, 10, 10) for f in range(1, 4)]))
    assert len(still["turn_deg"]) == 0                      # stationary: angle undefined, not counted


def test_frame_overlap_iou_and_close_pairs():
    gt = _gt([(1, 1, 0, 0, 10, 10), (1, 2, 5, 0, 10, 10),   # IoU = 50/150
              (2, 1, 0, 0, 10, 10), (2, 2, 0, 0, 10, 10),   # IoU = 1
              (3, 1, 0, 0, 10, 10)])                        # alone
    o = e.mot_frame_overlap(gt)
    assert o["max_iou"][:2] == pytest.approx([1 / 3, 1 / 3]) and o["max_iou"][2:4] == pytest.approx([1, 1])
    assert o["max_iou"][4] == 0
    assert o["close_pairs"].tolist() == [0, 1, 0]
    assert o["occluded"].tolist() == [True, True, True, True, False]


def test_max_overlap_stats_nested_and_disjoint():
    boxes = np.array([[0, 0, 10, 10], [2, 2, 4, 4], [50, 50, 5, 5]], dtype=float)
    s = e.max_overlap_stats(boxes)
    assert s["max_containment"] == pytest.approx([1.0, 1.0, 0.0])       # small box fully inside big box
    assert s["max_iou"] == pytest.approx([16 / 100, 16 / 100, 0.0])
    assert e.max_overlap_stats(boxes[:1])["max_iou"].tolist() == [0.0]

def test_id_lifelines_split_on_gaps_and_occlusion():
    gt = _gt([(1, 1, 0, 0, 10, 10), (2, 1, 0, 0, 10, 10), (3, 1, 0, 0, 10, 10), (5, 1, 0, 0, 10, 10),
              (3, 2, 5, 0, 10, 10), (4, 2, 100, 0, 10, 10)])
    seg = e.id_lifelines(gt).set_index(["id", "start"])
    # id 1: frames 1-2 alone, frame 3 overlaps id 2 (IoU 1/3 > 0.3), frame 5 alone after a gap
    assert seg.loc[(1, 1), ["end", "occluded"]].tolist() == [2, False]
    assert seg.loc[(1, 3), ["end", "occluded"]].tolist() == [3, True]
    assert seg.loc[(1, 5), ["end", "occluded"]].tolist() == [5, False]
    assert seg.loc[(2, 3), "occluded"] == True and seg.loc[(2, 4), "occluded"] == False


def test_id_confusion_pairs_counts_crossing_and_closeness():
    # two boxes (h=10) pass through each other: x-order flips between frames 2 and 3
    path = {1: [(1, 0), (2, 4), (3, 8), (4, 12)], 2: [(1, 8), (2, 5), (3, 2), (4, -1)]}
    gt = _gt([(f, i, x, 0, 10, 10) for i, pts in path.items() for f, x in pts])
    r = e.id_confusion_pairs(gt)
    assert r["crossings"] == 1
    assert r["close_pair_frames"] == 1          # centre gaps 8,1,6,13 px; only 1 px < 0.5 * height 10
    far = _gt([(f, i, x, 0, 10, 10) for i, x in ((1, 0), (2, 100)) for f in range(1, 5)])
    assert e.id_confusion_pairs(far) == dict(close_pair_frames=0, crossings=0)
    parallel = _gt([(f, i, x, 0, 10, 10) for i, x in ((1, 0), (2, 3)) for f in range(1, 5)])
    assert e.id_confusion_pairs(parallel) == dict(close_pair_frames=4, crossings=0)   # close but never swap


def test_tertiles_tiers_and_train_only_edges():
    assert e.tertile_edges([1, 2, 3, 4, 5, 6, 7]) == pytest.approx((3.0, 5.0))
    assert e.assign_tier([3, 3.1, 5, 9], (3.0, 5.0)) == ["low", "mid", "mid", "high"]
    import pandas as pd
    df = pd.DataFrame(dict(split=["train"] * 7 + ["val"] * 2, seq=list("abcdefghi"),
                           d=[1, 2, 3, 4, 5, 6, 7, 100, 0], cam=[0, 0, 0, 0, 0, 2.0, 0, 0, 0]))
    out, edges = e.stratify_sequences(df, {"density": "d"}, cam_col="cam")
    assert edges["density"] == pytest.approx((3.0, 5.0))               # val outlier 100 does not move the edges
    assert out.tier_density.tolist() == ["low", "low", "low", "mid", "mid", "high", "high", "high", "low"]
    assert out.camera.tolist().count("moving") == 1


def _strata():
    import pandas as pd
    n = 30
    rng = np.random.default_rng(0)
    df = pd.DataFrame(dict(split=["train"] * n, seq=[f"s{i}" for i in range(n)],
                           tier_a=np.resize(["low", "mid", "high"], n), tier_b=rng.permutation(np.resize(["low", "mid", "high"], n)),
                           camera=["moving" if i in (4, 17) else "static" for i in range(n)]))
    return df


def test_select_dev_subset_deterministic_and_constrained():
    s = _strata()
    a = e.select_dev_subset(s, 8, seed=1, tier_cols=["tier_a", "tier_b"])
    assert a == e.select_dev_subset(s, 8, seed=1, tier_cols=["tier_a", "tier_b"])
    pick = s[s.seq.isin(a)]
    assert len(a) == 8 and (pick.camera == "moving").any()
    for c in ("tier_a", "tier_b"):
        assert (pick[c].value_counts() >= 2).all() and len(pick[c].unique()) == 3
    with pytest.raises(ValueError):
        e.select_dev_subset(s, 4, seed=1, tier_cols=["tier_a", "tier_b"], min_per_tier=2, max_tries=50)


def test_coverage_vs_reference_flags_out_of_range():
    import pandas as pd
    ref = pd.DataFrame(dict(seq=list("abc"), x=[1.0, 2.0, 3.0]))
    dev = pd.DataFrame(dict(seq=["d", "e"], x=[2.5, 9.0]))
    c = e.coverage_vs_reference(dev, ref, ["x"])
    assert c.loc["x", "n_outside"] == 1 and c.loc["x", "outside"] == "e"


def _slide(kind, pad=40, shift=0, noise=0.0, seed=0):
    """White 180x320 'slide' with black pillar bars; `kind` selects the drawing."""
    img = np.full((180, 320), 255.0)
    if kind == "a":
        img[30:36, 40:200] = 0
        img[60:150, 60:66] = 0
        img[100:106, 60:260] = 0
    else:
        img[20:100, 150:156] = 0
        img[120:126, 30:220] = 0
        img[40:46, 200:300] = 0
    img = np.roll(img, shift, axis=1)
    if noise:
        img = np.clip(img + np.random.default_rng(seed).normal(0, noise, img.shape), 0, 255)
    return np.pad(img, ((0, 0), (pad, pad)), constant_values=0)


def test_slide_jaccard_separates_slides_where_ncc_does_not():
    a, b = _slide("a"), _slide("b")
    assert e.ncc(a, b) > 0.5                                    # shared white page + black bars inflate NCC
    assert e.slide_jaccard(a, b) < 0.3                          # different content
    assert e.slide_jaccard(a, a) == pytest.approx(1.0)
    assert e.slide_jaccard(a, _slide("a", pad=70, noise=3.0)) > 0.8   # same slide, other bars, re-encoding noise
    assert e.slide_jaccard(np.full((50, 50), 255.0), a) == 0.0  # blank frame has no ink

def test_content_crop_removes_bars():
    assert e.content_crop(_slide("a", pad=40)).shape == (180, 320)

def test_eda_notebook_builds_and_verifies_frozen_inputs(tmp_path, monkeypatch):
    import nbformat
    from experiments.scripts import build_detection_tracking_eda_notebook as builder

    monkeypatch.setattr(builder, "OUTPUT", tmp_path / "eda.ipynb")
    nb = nbformat.read(builder.build(), as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "gt_coco_canonical_sha256" in code and "gt_sha256" in code     # frozen cohorts are hash-checked
    assert "scoring_run=False" in code and "model_inference_run=False" in code
    assert "holm_adjust" in code and "design_effect" in code