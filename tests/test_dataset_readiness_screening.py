"""Protocol decisions and media integrity, without model inference."""
import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from experiments.scripts.dataset_readiness_screening import default_protocol, fingerprint, pair_match, screen_dataset


def row(tmp_path, name, split, pixels):
    path = tmp_path / f"{name}.png"
    Image.fromarray(pixels.astype("uint8")).save(path)
    return dict(unit_id=name, dataset_id="iiit_cvid", split=split, decoded=True,
                media_path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                reference_text="released text", speaker_id=name, talk_id=name)


def permissive_protocol():
    p = default_protocol()
    p["minimum_retained"]["iiit_cvid"] = {"validation": 1, "final_test": 1}
    p["minimum_groups_per_split"] = 1
    return p


def test_cross_split_exact_excludes_validation_without_refill(tmp_path):
    pixels = np.arange(256).reshape(16, 16)
    rows = [row(tmp_path, "val", "validation", pixels), row(tmp_path, "test", "final_test", pixels)]
    result, audit = screen_dataset("iiit_cvid", rows, [], permissive_protocol())
    assert [r["decision"] for r in result] == ["exclude", "keep"]
    assert audit["retained_cross_split_hits"] == 0
    assert audit["status"] == "blocked"  # Empty validation is not a clean successful split.
    assert audit["pairs"][0]["kind"] == "exact"
    assert rows[0].get("decision") is None


def test_historical_similarity_excludes_new_test(tmp_path):
    pixels = np.arange(256).reshape(16, 16)
    new = row(tmp_path, "new", "final_test", pixels)
    old = row(tmp_path, "old", "final_test", pixels)
    result, audit = screen_dataset("iiit_cvid", [new], [old], permissive_protocol())
    assert result[0]["decision"] == "exclude"
    assert audit["historical_count"] == 1
    assert audit["pairs"][0]["right_split"] == "historical"


def test_within_split_hits_retained_and_documented(tmp_path):
    pixels = np.arange(256).reshape(16, 16)
    rows = [row(tmp_path, "a", "validation", pixels), row(tmp_path, "b", "validation", pixels)]
    result, audit = screen_dataset("iiit_cvid", rows, [], permissive_protocol())
    assert all(r["decision"] == "keep" for r in result)
    assert audit["pairs"][0]["decision"] == "retain_within_split"


def test_changed_media_fails_identity_before_features(tmp_path):
    r = row(tmp_path, "x", "validation", np.zeros((10, 10)))
    Path(r["media_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="identity changed"):
        fingerprint(r, default_protocol())


def test_brightness_variant_image_flagged_by_dhash(tmp_path):
    pixels = np.arange(100).reshape(10, 10)
    a, b = row(tmp_path, "a", "validation", pixels), row(tmp_path, "b", "final_test", pixels + 50)
    p = default_protocol()
    match = pair_match(a, b, fingerprint(a, p), fingerprint(b, p), p)
    assert match["kind"] == "near"
    assert match["method"] == "dhash_hamming"


def test_long_transcript_similarity_without_waveform_match():
    p = default_protocol()
    a = dict(decoded_sha256="a", duration=2, waveform=None, text="one two three four five six seven eight nine ten")
    b = dict(a, decoded_sha256="b", duration=8)
    match = pair_match({"sha256": "a"}, {"sha256": "b"}, a, b, p)
    assert match["method"] == "normalized_transcript_sequence"


def test_historical_failure_blocks_clearance(tmp_path):
    old = row(tmp_path, "old", "final_test", np.zeros((10, 10)))
    old["decoded"] = False
    _, audit = screen_dataset("iiit_cvid", [], [old], permissive_protocol())
    assert "historical comparison incomplete" in audit["blockers"]


def test_group_overlap_blocks_even_with_dissimilar_images(tmp_path):
    rng = np.random.default_rng(123)
    a = row(tmp_path, "a", "validation", rng.integers(0, 255, (64, 64)))
    b = row(tmp_path, "b", "final_test", rng.integers(0, 255, (64, 64)))
    b["speaker_id"] = a["speaker_id"]
    _, audit = screen_dataset("iiit_cvid", [a, b], [], permissive_protocol())
    assert "retained cross-split speaker_id overlap" in audit["blockers"]


def test_duplicate_ids_rejected(tmp_path):
    a = row(tmp_path, "a", "validation", np.zeros((10, 10)))
    with pytest.raises(ValueError, match="duplicate unit"):
        screen_dataset("iiit_cvid", [a, a], [], permissive_protocol())


@pytest.mark.parametrize("field,value", [("ground_truth_error", "invalid_annotation"),
                                         ("reference_text", "ignore_time_segment_in_scoring")])
def test_invalid_gt_never_retained(tmp_path, field, value):
    record = row(tmp_path, "a", "validation", np.zeros((10, 10)))
    record[field] = value
    result, audit = screen_dataset("iiit_cvid", [record], [], permissive_protocol())
    assert result[0]["decision"] == "exclude"
    assert len(audit["failures"]) == 1


def test_valid_media_with_ignored_gt_still_has_measured_similarity(tmp_path):
    pixels = np.arange(100).reshape(10, 10)
    a = row(tmp_path, "a", "validation", pixels)
    a["reference_text"] = "ignore_time_segment_in_scoring"
    b = row(tmp_path, "b", "final_test", pixels)
    result, audit = screen_dataset("iiit_cvid", [a, b], [], permissive_protocol())
    cross = next(p for p in audit["pair_coverage"] if p["left_split"] != p["right_split"])
    assert cross["expected_pairs"] == cross["completed_pairs"] == 1
    assert result[0]["decision"] == "exclude"
    assert audit["pairs"][0]["kind"] == "exact"
