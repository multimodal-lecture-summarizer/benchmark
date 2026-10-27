import numpy as np
import pytest

pytest.importorskip("pycocotools")

from experiments.scripts import detection_scoring as ds
from experiments.scripts import paired_bootstrap as pb


def _gt(boxes_by_image, cats=((1, "a"), (2, "b"), (3, "c"))):
    images, anns = [], []
    for img_id, boxes in boxes_by_image.items():
        images.append(dict(id=img_id, width=640, height=480, file_name=f"{img_id}.jpg"))
        for cat, (x, y, w, h), *crowd in boxes:
            anns.append(dict(id=len(anns) + 1, image_id=img_id, category_id=cat, bbox=[x, y, w, h],
                             area=float(w * h), iscrowd=int(bool(crowd and crowd[0]))))
    return dict(images=images, annotations=anns, categories=[dict(id=c, name=n) for c, n in cats])


def _random_case(seed=0, n_images=40):
    rng = np.random.default_rng(seed)
    boxes, preds = {}, []
    for i in range(1, n_images + 1):
        items = []
        for _ in range(int(rng.integers(0, 5))):
            cat = int(rng.integers(1, 4))
            x, y = rng.uniform(0, 400, 2)
            w, h = rng.uniform(20, 200, 2)
            items.append((cat, (float(x), float(y), float(w), float(h))))
            if rng.random() < 0.8:  # a jittered, scored detection
                jx, jy = rng.normal(0, 8, 2)
                preds.append(dict(image_id=i, category_id=cat, bbox=[x + jx, y + jy, w + rng.normal(0, 8), h + rng.normal(0, 8)],
                                  score=float(rng.uniform(0.3, 1.0))))
        for _ in range(int(rng.integers(0, 3))):  # false positives
            preds.append(dict(image_id=i, category_id=int(rng.integers(1, 4)),
                              bbox=[float(rng.uniform(0, 400)), float(rng.uniform(0, 300)), 60.0, 60.0],
                              score=float(rng.uniform(0.0, 0.8))))
        boxes[i] = items
    return _gt(boxes), preds


def test_perfect_and_empty_predictions():
    gt = _gt({1: [(1, (10, 10, 100, 100))], 2: [(2, (50, 50, 80, 60))]})
    perfect = [dict(image_id=1, category_id=1, bbox=[10, 10, 100, 100], score=0.9),
               dict(image_id=2, category_id=2, bbox=[50, 50, 80, 60], score=0.8)]
    assert ds.coco_summary(gt, perfect)["ap_50_95"] == pytest.approx(1.0)
    assert ds.DetectionCache(gt, perfect).metrics()["map_50_95"] == pytest.approx(1.0)
    assert ds.coco_summary(gt, [])["ap_50_95"] == 0.0
    assert ds.DetectionCache(gt, []).metrics()["map_50_95"] == 0.0


def test_shifted_box_has_hand_computed_ap():
    # IoU of a 100x100 box shifted by 10 px = 9000 / 11000 = 0.818 -> matched at thresholds .50 ... .80 (7 of 10)
    gt = _gt({1: [(1, (0, 0, 100, 100))]}, cats=((1, "a"),))
    pred = [dict(image_id=1, category_id=1, bbox=[10, 0, 100, 100], score=0.9)]
    s = ds.coco_summary(gt, pred)
    assert s["ap_50_95"] == pytest.approx(0.7) and s["ap50"] == pytest.approx(1.0) and s["ap75"] == pytest.approx(1.0)
    m = ds.DetectionCache(gt, pred).metrics()
    assert m["map_50_95"] == pytest.approx(0.7) and m["per_class_ap"]["a"] == pytest.approx(0.7)


def test_cache_matches_pycocotools_on_random_data():
    gt, preds = _random_case(seed=1)
    ref = ds.coco_summary(gt, preds)
    got = ds.DetectionCache(gt, preds).metrics()
    assert got["map_50_95"] == pytest.approx(ref["ap_50_95"], abs=1e-12)
    assert got["ap50"] == pytest.approx(ref["ap50"], abs=1e-12)
    assert got["ap75"] == pytest.approx(ref["ap75"], abs=1e-12)


def test_weighted_resample_equals_physically_replicated_dataset():
    gt, preds = _random_case(seed=2, n_images=25)
    ids = [im["id"] for im in gt["images"]]
    weights = np.random.default_rng(3).integers(0, 4, size=len(ids))
    # physical replication: image i appears weights[i] times, adjacent, with fresh ids
    rep_images, rep_anns, rep_preds, new_id = [], [], [], 0
    for i, img in enumerate(gt["images"]):
        for c in range(weights[i]):
            new_id += 1
            rep_images.append(dict(img, id=new_id))
            for a in gt["annotations"]:
                if a["image_id"] == img["id"]:
                    rep_anns.append(dict(a, id=len(rep_anns) + 1, image_id=new_id))
            for p in preds:
                if p["image_id"] == img["id"]:
                    rep_preds.append(dict(p, image_id=new_id))
    rep_gt = dict(images=rep_images, annotations=rep_anns, categories=gt["categories"])
    expected = ds.coco_summary(rep_gt, rep_preds)["ap_50_95"]
    got = ds.DetectionCache(gt, preds).metrics(weights)["map_50_95"]
    assert got == pytest.approx(expected, abs=1e-12)


def test_crowd_boxes_are_ignored_like_pycocotools():
    gt = _gt({1: [(1, (0, 0, 100, 100)), (1, (200, 200, 100, 100), True)]}, cats=((1, "a"),))
    pred = [dict(image_id=1, category_id=1, bbox=[0, 0, 100, 100], score=0.9),
            dict(image_id=1, category_id=1, bbox=[200, 200, 100, 100], score=0.8)]   # lands on the crowd region
    assert ds.coco_summary(gt, pred)["ap_50_95"] == pytest.approx(1.0)               # not a false positive
    assert ds.DetectionCache(gt, pred).metrics()["map_50_95"] == pytest.approx(1.0)


def test_failure_policy_counts_failed_images_as_misses():
    gt = _gt({1: [(1, (0, 0, 50, 50))], 2: [(1, (0, 0, 50, 50))]}, cats=((1, "a"),))
    preds = [dict(image_id=i, category_id=1, bbox=[0, 0, 50, 50], score=0.9) for i in (1, 2)]
    out = ds.apply_failure_policy(preds, [1, 2], failed=[2])
    assert out["n_failed"] == 1 and out["image_ids_success"] == [1]
    assert ds.coco_summary(gt, out["preds"], out["image_ids_all"])["ap50"] == pytest.approx(51 / 101)   # image 2 = miss: recall caps at 0.5, 51 of 101 COCO recall points
    assert ds.coco_summary(gt, out["preds"], out["image_ids_success"])["ap50"] == pytest.approx(1.0)


def test_precision_recall_diagnostic_and_score_less_flag():
    gt = _gt({1: [(1, (0, 0, 50, 50)), (1, (100, 100, 50, 50))]}, cats=((1, "a"),))
    preds = [dict(image_id=1, category_id=1, bbox=[0, 0, 50, 50], score=1.0),
             dict(image_id=1, category_id=1, bbox=[300, 300, 50, 50], score=1.0)]
    pr = ds.DetectionCache(gt, preds).precision_recall(conf=0.5)
    assert (pr["tp"], pr["fp"], pr["fn"]) == (1, 1, 1) and pr["precision"] == 0.5 and pr["recall"] == 0.5
    assert ds.is_score_less(preds) and not ds.is_score_less(preds[:1] + [dict(preds[1], score=0.3)])


def test_open_vocab_mapping_reports_coverage():
    tax = {"person": ["person", "man"], "tv": ["tv", "monitor"]}
    ids = {"person": 1, "tv": 72}
    preds = [dict(image_id=1, label="A Man", bbox=[0, 0, 5, 5], score=1.0),
             dict(image_id=1, label="monitor", bbox=[0, 0, 5, 5], score=1.0),
             dict(image_id=1, label="giraffe", bbox=[0, 0, 5, 5], score=1.0)]
    out = ds.map_open_vocab(preds, tax, ids)
    assert [p["category_id"] for p in out["preds"]] == [1, 72]
    assert out["unknown_concept_rate"] == pytest.approx(1 / 3) and out["taxonomy_mapping_coverage"] == pytest.approx(2 / 3)


def test_paired_bootstrap_and_decision_rule():
    gt, preds_a = _random_case(seed=4, n_images=60)
    rng = np.random.default_rng(5)
    preds_b = [p for p in preds_a if rng.random() < 0.5]        # B = A with half the detections removed
    ca, cb = ds.DetectionCache(gt, preds_a), ds.DetectionCache(gt, preds_b)
    mult = pb.cluster_multiplicities(60, groups=np.repeat(np.arange(20), 3), resamples=200, seed=7)
    assert (mult.sum(axis=1) == 60).all()                         # 20 groups of 3 images drawn per resample
    assert (mult.reshape(200, 20, 3).std(axis=2) == 0).all()      # images of a group always enter together
    res = pb.paired_bootstrap(ca.map_fn(), cb.map_fn(), mult)
    assert res["delta"] > 0.05 and res["delta_lo"] > 0 and pb.decide_difference(res, 0.02) == "a_better"
    assert pb.decide_difference(res, 0.9) == "indistinguishable"  # CI excludes 0 but the gap is below the threshold rule
    same = pb.paired_bootstrap(ca.map_fn(), ca.map_fn(), mult)
    assert same["delta"] == 0 and pb.decide_difference(same, 0.02) == "indistinguishable"
