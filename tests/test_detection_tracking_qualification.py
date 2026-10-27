import json
import zipfile

import numpy as np
import pytest
from PIL import Image

from experiments.scripts import detection_tracking_qualification as q


def _make_lvvo(root, boxes_by_stem, size=(100, 80)):
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    (root / "dataset_info.json").write_text(json.dumps(
        {"categories": {"Table": 1, "Chart": 2, "Photo": 3, "Illustration": 4}}))
    for n, (stem, boxes) in enumerate(boxes_by_stem.items()):
        Image.new("RGB", size, (n * 40 % 255, 10, 10)).save(root / "images" / f"{stem}.jpg")
        objs = [{"class": c, "boundingBox": dict(zip(("xmin", "ymin", "xmax", "ymax"), b))}
                for c, b in boxes]
        (root / "labels" / f"{stem}.json").write_text(json.dumps({"objects": objs}))


def test_lvvo_to_coco_counts_and_negatives(tmp_path):
    _make_lvvo(tmp_path, {
        "i1_c2_v3_a": [(1, (0, 0, 10, 10)), (2, (5, 5, 50, 40))],
        "i1_c2_v3_b": [],                                  # valid negative
        "i1_c2_v4_c": [(3, (0, 0, 500, 10))],              # outside image -> excluded
    })
    out = q.lvvo_to_coco(tmp_path)
    assert len(out["coco"]["images"]) == 3                 # negatives and bad-box images kept
    assert len(out["coco"]["annotations"]) == 2
    assert len(out["excluded"]) == 1 and out["excluded"][0]["reason"] == "invalid_box_or_class"
    assert [i["id"] for i in out["coco"]["images"]] == [1, 2, 3]
    assert out["ledger"][0]["group"] == "i1/c2/v3"
    boxes = sum(len(x["bbox"]) == 4 for x in out["coco"]["annotations"])
    assert boxes == 2


def test_reconcile_rejects_silent_drop():
    assert q.reconcile(10, 7, 2, 1)["raw"] == 10
    with pytest.raises(ValueError):
        q.reconcile(10, 7, 2, 0)


def test_safe_extract_blocks_traversal(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../evil.txt", "x")
    with pytest.raises(ValueError):
        q.safe_extract(bad, tmp_path / "out")
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as zf:
        zf.writestr("val/seq/gt/gt.txt", "1,1,0,0,5,5,1,1,1")
        zf.writestr("val/seq/img1/skip.bin", "z")
    done = q.safe_extract(good, tmp_path / "out", keep=lambda n: n.endswith("gt.txt"))
    assert done == ["val/seq/gt/gt.txt"]


def _coco(n_images=300):
    rng = np.random.default_rng(1)
    cats = list(q.COCO_TAXONOMY)
    images, anns = [], []
    for i in range(1, n_images + 1):
        images.append(dict(id=i, width=640, height=480, file_name=f"{i:012d}.jpg"))
        for _ in range(rng.integers(0, 4)):
            c = int(rng.choice(cats, p=[0.5] + [0.5 / 9] * 9))
            w, h = rng.integers(5, 300, 2)
            anns.append(dict(id=len(anns) + 1, image_id=i, category_id=c, bbox=[0, 0, int(w), int(h)],
                             area=float(w * h), iscrowd=int(rng.random() < 0.05)))
    return dict(images=images, annotations=anns)


def test_select_coco_subset_deterministic_and_covers_classes():
    coco = _coco()
    a = q.select_coco_subset(coco, n_images=100, seed=7)
    b = q.select_coco_subset(coco, n_images=100, seed=7)
    c = q.select_coco_subset(coco, n_images=100, seed=8)
    assert a["image_ids"] == b["image_ids"] != c["image_ids"]
    assert len(a["image_ids"]) == 100
    assert {x["category_id"] for x in a["annotations"]} == set(q.COCO_TAXONOMY)
    assert all(x["image_id"] in set(a["image_ids"]) for x in a["annotations"])


def test_select_coco_subset_caps_at_eligible():
    coco = _coco(20)
    out = q.select_coco_subset(coco, n_images=1000, seed=1)
    assert len(out["image_ids"]) == out["eligible_images"] <= 20


def test_mot_stats_hand_checked():
    # id1 frames 1,2,3 ; id2 frames 1,3 (gap) ; boxes 1 and 2 overlap in frames 1 and 3
    text = "\n".join([
        "1,1,0,0,10,10,1,1,1", "2,1,0,0,10,10,1,1,1", "3,1,0,0,10,10,1,1,1",
        "1,2,2,0,10,10,1,1,1", "3,2,2,0,10,10,1,1,1"])
    s = q.mot_sequence_stats(q.parse_mot_gt(text), seq_length=3, im_width=100, im_height=100)
    assert (s["boxes"], s["tracks"], s["tracks_with_gaps"]) == (5, 2, 1)
    assert s["track_len_min"] == 2 and s["track_len_max"] == 3
    assert s["occluded_box_fraction"] == pytest.approx(4 / 5)
    assert q.mot_blocking_issues(s) == 0


def test_mot_blocking_detects_duplicates_and_bad_ids():
    text = "1,1,0,0,10,10,1,1,1\n1,1,0,0,10,10,1,1,1\n9,0,0,0,0,10,1,1,1"
    s = q.mot_sequence_stats(q.parse_mot_gt(text), seq_length=3, im_width=50, im_height=50)
    assert s["duplicate_frame_id_rows"] == 1
    assert s["frame_out_of_range_rows"] == 1
    assert s["nonpositive_size_rows"] == 1
    assert q.mot_blocking_issues(s) == 3        # id 0 is valid (DanceTrack is 0-based)
    neg = q.mot_sequence_stats(q.parse_mot_gt('1,-1,0,0,5,5,1,1,1'), 3, 50, 50)
    assert neg['ids_valid'] is False and q.mot_blocking_issues(neg) == 1


def test_sample_frames_and_member_regex():
    idx = q.sample_frame_indices(100)
    assert idx[0] == 1 and idx[-1] == 100 and max(idx) <= 100
    m = q.MOT_MEMBER.match("dataset/val/v_x/img1/000012.jpg")
    assert m and m["split"] == "val" and m["seq"] == "v_x" and m["frame"] == "000012"
    assert q.MOT_MEMBER.match("dancetrack/train/dancetrack0001/gt/gt.txt")


def test_parse_mot_member_handles_split_variants():
    p = q.parse_mot_member
    assert p("val/dancetrack0004/gt/gt.txt")["split"] == "val"
    assert p("train1/dancetrack0001/seqinfo.ini")["split"] == "train"        # train1.zip layout
    assert p("dancetrack/train2/dancetrack0050/img1/00000001.jpg")["frame"] == "00000001"
    assert p("dancetrack0001/gt/gt.txt") is None                              # no split info
    assert p("dancetrack0001/gt/gt.txt", default_split="train")["split"] == "train"
    assert p("dataset/val/v_x/img1/000012.jpg")["seq"] == "v_x"
    assert p("val/../img1/1.jpg") is None


def test_camera_motion_proxy_detects_shift():
    rng = np.random.default_rng(0)
    a = rng.random((64, 64)).astype(np.float32)
    shifted = np.roll(a, 5, axis=1)
    assert q.camera_motion_pixels([(a, a)]) == pytest.approx(0.0, abs=0.1)
    assert q.camera_motion_pixels([(a, shifted)]) == pytest.approx(5.0, abs=0.6)


def test_near_duplicates_ignore_identical_bytes():
    hashes = {"a": 0b1010, "b": 0b1011, "c": (1 << 63) - 1}
    sha = {"a": "1", "b": "2", "c": "3"}
    groups = {"a": "g1", "b": "g2", "c": "g3"}
    pairs = q.near_duplicate_pairs(hashes, groups, sha, max_distance=4)
    assert [(p["left"], p["right"], p["distance"], p["same_group"]) for p in pairs] == [("a", "b", 1, False)]
    sha["b"] = "1"
    assert q.near_duplicate_pairs(hashes, groups, sha, max_distance=4) == []


def test_qualification_notebook_builds_valid_nbformat(tmp_path, monkeypatch):
    import nbformat
    from experiments.scripts import build_detection_tracking_qualification_notebook as builder

    monkeypatch.setattr(builder, "OUTPUT", tmp_path / "nb.ipynb")
    nb = nbformat.read(builder.build(), as_version=4)
    nbformat.validate(nb)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "detection_tracking_qualification" in code and "LICENSE_ACK" in code
    assert "model_inference_run=False" in code     # phase 2 must not run models


def test_decision_gates():
    ok = dict(license_verified=True, license_ack=True, blocking_qa=0, exact_leakage=0, acquired=True)
    assert q.qualification_decision(**ok)["decision"] == "KEEP"
    assert q.qualification_decision(**{**ok, "license_verified": False})["decision"] == "REJECT"
    assert q.qualification_decision(**{**ok, "license_ack": False})["decision"] == "HOLD"
    assert q.qualification_decision(**{**ok, "exact_leakage": 2})["decision"] == "REPAIR"
    assert q.qualification_decision(**{**ok, "acquired": False})["decision"] == "HOLD"
