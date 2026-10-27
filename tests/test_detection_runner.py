import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("pycocotools")

from experiments.scripts import detection_runner as dr


class FakeAdapter(dr.Adapter):
    """Returns the ground-truth box of each image, fails on chosen ids, and counts calls."""

    def __init__(self, truth, fail_ids=(), oom_ids=()):
        self.truth, self.fail_ids, self.oom_ids, self.calls = truth, set(fail_ids), set(oom_ids), 0

    def predict(self, rgb):
        self.calls += 1
        key = int(rgb[0, 0, 0])                     # image id is encoded in the first pixel
        if key in self.fail_ids:
            raise ValueError("decode problem")
        if key in self.oom_ids:
            raise RuntimeError("CUDA out of memory")
        return [dict(label=self.truth[key][0], bbox=self.truth[key][1], score=0.5 + 0.05 * key)]   # distinct scores


def _make(tmp_path, n=5, size=(64, 48)):
    items, gt_images, anns, truth = [], [], [], {}
    for i in range(1, n + 1):
        path = tmp_path / f"{i}.png"
        arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        arr[0, 0, 0] = i
        Image.fromarray(arr).save(path)
        items.append((i, path, size))
        gt_images.append(dict(id=i, width=size[0], height=size[1], file_name=path.name))
        anns.append(dict(id=i, image_id=i, category_id=1, bbox=[5, 5, 20, 20], area=400.0, iscrowd=0))
        truth[i] = ("person", [5.0, 5.0, 20.0, 20.0])
    gt = dict(images=gt_images, annotations=anns, categories=[dict(id=1, name="person")])
    return items, gt, truth


def test_run_track_is_resumable_and_records_every_failure(tmp_path):
    items, gt, truth = _make(tmp_path)
    out = tmp_path / "preds.jsonl"
    ad = FakeAdapter(truth, fail_ids={2}, oom_ids={4})
    info = dr.run_track(ad, items, out, warmup=0)
    rows = {r["image_id"]: r for r in dr.read_rows(out)}
    assert info["n_rows"] == 5 and info["n_ok"] == 3
    assert rows[2]["reason"].startswith("ValueError") and rows[4]["reason"] == "oom" and not rows[2]["ok"]
    calls = ad.calls
    again = dr.run_track(ad, items, out, warmup=0)               # nothing left to do
    assert ad.calls == calls and again["n_rows"] == 5


def test_size_mismatch_is_a_failure_not_a_silent_skip(tmp_path):
    items, gt, truth = _make(tmp_path, n=2)
    wrong = [(items[0][0], items[0][1], (99, 99))] + items[1:]
    dr.run_track(FakeAdapter(truth), wrong, tmp_path / "p.jsonl", warmup=0)
    rows = {r["image_id"]: r for r in dr.read_rows(tmp_path / "p.jsonl")}
    assert rows[1]["reason"].startswith("size_mismatch") and rows[2]["ok"]


def test_soft_timeout_discards_the_output(tmp_path):
    items, gt, truth = _make(tmp_path, n=1)
    dr.run_track(FakeAdapter(truth), items, tmp_path / "p.jsonl", warmup=0, max_seconds=-1.0)
    row = dr.read_rows(tmp_path / "p.jsonl")[0]
    assert row["reason"] == "timeout" and not row["ok"] and row["dets"] == []


def test_score_track_counts_failures_as_misses_and_reports_both_views(tmp_path):
    items, gt, truth = _make(tmp_path, n=4)
    dr.run_track(FakeAdapter(truth, fail_ids={1, 2}), items, tmp_path / "p.jsonl", warmup=0)
    rows = dr.read_rows(tmp_path / "p.jsonl")
    s = dr.score_track(gt, rows, "closed", {}, image_ids=[i[0] for i in items])
    assert s["n_failed"] == 2 and s["failure_reasons"] == {"ValueError": 2}
    assert s["scored_success_only"]["ap_50_95"] == pytest.approx(1.0)          # the two good images are perfect
    assert s["scored"]["ap50"] == pytest.approx(51 / 101)                      # failures cap recall at 0.5
    assert s["latency"]["n"] == 2 and not s["score_less"]


def test_images_never_attempted_are_counted(tmp_path):
    items, gt, truth = _make(tmp_path, n=3)
    dr.run_track(FakeAdapter(truth), items[:2], tmp_path / "p.jsonl", warmup=0)
    s = dr.score_track(gt, dr.read_rows(tmp_path / "p.jsonl"), "closed", {}, image_ids=[1, 2, 3])
    assert s["n_not_attempted"] == 1


def test_closed_vocabulary_ignores_classes_outside_the_taxonomy(tmp_path):
    items, gt, truth = _make(tmp_path, n=2)
    rows = [dict(image_id=1, ok=True, reason=None, latency_ms=5.0, dets=[
        dict(label="person", bbox=[5, 5, 20, 20], score=0.9), dict(label="boat", bbox=[30, 30, 10, 10], score=0.9)]),
            dict(image_id=2, ok=True, reason=None, latency_ms=5.0, dets=[dict(label="person", bbox=[5, 5, 20, 20], score=0.8)])]
    s = dr.score_track(gt, rows, "closed", {}, image_ids=[1, 2])
    assert s["scored"]["ap_50_95"] == pytest.approx(1.0)                       # the boat is not a false positive
    assert s["mapping"]["outside_taxonomy"] == 1


def test_open_vocabulary_goes_through_the_frozen_map_and_reports_score_less(tmp_path):
    items, gt, truth = _make(tmp_path, n=2)
    rows = [dict(image_id=i, ok=True, reason=None, latency_ms=900.0, dets=[
        dict(label="a man", bbox=[5, 5, 20, 20], score=1.0), dict(label="poster", bbox=[0, 0, 5, 5], score=1.0)]) for i in (1, 2)]
    s = dr.score_track(gt, rows, "open", {"person": ["person", "man"]}, image_ids=[1, 2], score_less=True)
    assert s["scored"]["ap50"] == pytest.approx(1.0) and s["score_less"]
    assert s["mapping"]["coverage"] == pytest.approx(0.5) and s["mapping"]["unknown_rate"] == pytest.approx(0.5)


def test_budget_estimate_and_candidate_registry():
    est = dr.estimate_gpu_hours({"a|D-B": 1000.0, "b|D-A": 500.0}, {"D-B": 3600, "D-A": 7200}, overhead=1.0, load_minutes=0)
    assert est["per_job_hours"]["a|D-B"] == pytest.approx(1.0) and est["per_job_hours"]["b|D-A"] == pytest.approx(1.0)
    assert est["total_hours"] == pytest.approx(2.0)
    by_id = {c.id: c for c in dr.CANDIDATES}
    assert all(by_id[i].tracks == ("D-B",) for i in ("yolov8n", "yolo11n", "rtdetr_r18"))   # no LVVO classes in COCO-80
    assert by_id["florence2_base"].score_less and by_id["florence2_base_ovd"].tracks == ("D-A",)
    assert by_id["grounding_dino_base"].tracks == ("D-A", "D-B")


def test_florence_asset_verification_detects_tampering(tmp_path):
    for name in dr.FLORENCE_ASSET_SHA256:
        (tmp_path / name).write_bytes(b"not the real asset")
    checks = dr.verify_florence_assets(tmp_path)
    assert not any(checks.values()) and set(checks) == set(dr.FLORENCE_ASSET_SHA256)
    assert not dr.verify_florence_assets(tmp_path / "missing")["model.safetensors"]


def test_find_phrase_spans_in_prompt_order():
    prompt = [101, 7, 8, 1012, 9, 1012, 7, 5, 1012, 102]          # CLS a b . c . a d . SEP  ("a b. c. a d.")
    spans = dr.find_phrase_spans(prompt, [[7, 8], [9], [7, 5]])
    assert spans == [(1, 3), (4, 5), (6, 8)]                      # the second "a ..." is not confused with the first
    with pytest.raises(ValueError):
        dr.find_phrase_spans(prompt, [[7, 8], [99]])