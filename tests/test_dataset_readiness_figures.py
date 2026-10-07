"""Measured EDA rendering checks; executed through the readiness notebook."""

import hashlib
import json

import pytest

from experiments.scripts.dataset_readiness_figures import render_readiness_figures
from experiments.scripts.dataset_readiness_plot_helpers import plot_tables


def _records(image=False):
    return [
        {"unit_id": "val1", "split": "validation", "bytes": 100, "duration_sec": None if image else 1.,
         "reference_text": "one", "decoded": True, "speaker_id": "s1", "talk_id": "t1",
         "sha256": "a" * 64, "decision": "keep", "reasons": []},
        {"unit_id": "test1", "split": "final_test", "bytes": 200, "duration_sec": None if image else 2.,
         "reference_text": "two", "decoded": True, "speaker_id": "s2", "talk_id": "t2",
         "sha256": "b" * 64, "decision": "keep", "reasons": []},
        {"unit_id": "val2", "split": "validation", "bytes": 300, "duration_sec": None,
         "reference_text": "", "decoded": False, "speaker_id": None, "talk_id": None,
         "sha256": "c" * 64, "decision": "exclude", "reasons": ["decode_failed"]},
    ]


def _audit():
    return {"status": "complete", "historical_count": 20,
            "cohort_counts": {"validation": 2, "final_test": 1, "historical": 20},
            "pair_coverage": [
                {"left_split": "validation", "right_split": "final_test", "expected_pairs": 2, "completed_pairs": 2},
                {"left_split": "validation", "right_split": "historical", "expected_pairs": 40, "completed_pairs": 40},
                {"left_split": "final_test", "right_split": "historical", "expected_pairs": 20, "completed_pairs": 20},
                {"left_split": "validation", "right_split": "validation", "expected_pairs": 1, "completed_pairs": 1},
                {"left_split": "historical", "right_split": "historical", "expected_pairs": 0, "completed_pairs": 0},
            ], "pairs": [
        {"left": "val2", "right": "test1", "left_split": "validation", "right_split": "final_test",
         "kind": "exact", "method": "content_sha256", "score": 1., "threshold": 1.,
         "decision": "exclude", "reason": "cross_split"},
        {"left": "val2", "right": "old1", "left_split": "validation", "right_split": "historical",
         "kind": "near", "method": "waveform", "score": .99, "threshold": .98,
         "decision": "exclude", "reason": "historical_similarity"},
    ]}


def test_derived_tables_have_real_denominators_and_missingness():
    tables = plot_tables("tedlium3", _records(), _audit(), {})
    assert len(tables) == 8
    assert tables["scale_bytes"]["bytes"] == [200., 400.]
    assert tables["duration_distribution"]["values"] == [1., 2.]
    assert tables["duration_distribution"]["missing_n"] == 1
    assert tables["missingness_gt_coverage"]["observed_percent"] == [[100.] * 5, [50.] * 5]
    assert tables["attrition_waterfall"] == {"selected": 3, "decoded": 2, "kept": 2, "excluded": 1}
    assert tables["source_overlap"]["matrices"]["talk_id"] == [[1, 0], [0, 1]]
    dup = tables["duplicate_matrix"]
    assert dup["splits"] == ["final_test", "historical", "validation"]
    assert dup["matrices"]["exact"][0][2] == 1
    assert dup["matrices"]["near"][1][2] == 1
    assert dup["pair_count"] == 2


def test_incomplete_pairs_are_na_with_observed_hits_retained_separately():
    audit = _audit()
    audit["pair_coverage"][0]["completed_pairs"] = 1
    dup = plot_tables("tedlium3", _records(), audit, {})["duplicate_matrix"]
    assert dup["matrices"]["exact"][0][2] is None
    assert dup["matrices"]["near"][0][2] is None
    assert dup["recorded_hit_lower_bounds"]["exact"][0][2] == 1
    assert dup["completion"][0][2] == {"expected_pairs": 2, "completed_pairs": 1}
    assert dup["completed_pairs"] == 62 and dup["expected_pairs"] == 63


def test_historical_axis_survives_zero_hits_and_uncompared_is_na():
    audit = _audit()
    audit["pairs"] = []
    dup = plot_tables("tedlium3", _records(), audit, {})["duplicate_matrix"]
    assert dup["splits"] == ["final_test", "historical", "validation"]
    assert dup["matrices"]["near"][1][2] == 0  # all 40 comparisons completed
    assert dup["matrices"]["exact"][1][1] is None  # historical/historical never compared
    audit.pop("pair_coverage")
    dup = plot_tables("tedlium3", _records(), audit, {})["duplicate_matrix"]
    assert all(value is None for row in dup["matrices"]["exact"] for value in row)


def test_duration_na_is_distinct_from_missing_or_zero():
    tables = plot_tables("iiit_cvid", _records(image=True), _audit(), {})
    duration = tables["duration_distribution"]
    assert duration["applicability"] == "not_applicable"
    assert duration["values"] == []
    assert duration["not_applicable_n"] == 3
    assert duration["missing_n"] == 0
    assert all(row[-1] is None for row in tables["missingness_gt_coverage"]["observed_percent"])
    assert tables["source_overlap"]["labels"] == ["course_id", "video_id"]
    bad = _records(image=True)
    bad[0]["duration_sec"] = 0
    with pytest.raises(ValueError, match="still-image duration"):
        plot_tables("iiit_cvid", bad, _audit(), {})


def test_nonempty_ignored_or_invalid_ground_truth_is_not_covered():
    records = _records()
    records[0]["reference_text"] = " ignore_time_segment_in_scoring "
    records[1]["reference_text"] = "nonempty but invalid annotation"
    records[1]["ground_truth_error"] = "annotation_failed_validation"
    records[2]["reference_text"] = "usable released reference"
    coverage = plot_tables("tedlium3", records, _audit(), {})["missingness_gt_coverage"]
    assert coverage["splits"] == ["final_test", "validation"]
    assert coverage["observed_percent"][0][0] == 0
    assert coverage["observed_percent"][1][0] == 50


def test_missing_file_sizes_never_become_measured_zero():
    records = _records()
    records[1]["bytes"] = None  # final_test has no measured sizes
    records[2]["bytes"] = None  # validation has only one measured size
    scale = plot_tables("tedlium3", records, _audit(), {})["scale_bytes"]
    assert scale["bytes"] == [None, 100.]
    assert scale["measured_n"] == [0, 1]
    assert scale["missing_n_by_split"] == [1, 1]
    assert scale["missing_n"] == 2
    assert scale["measure_policy"] == "sum_of_observed_bytes_only"


def test_histogram_edges_are_protocol_bound_and_never_fit_on_test():
    protocol = {"histogram_duration_edges": [0, 1, 3], "histogram_bytes_edges": [0, 150, 400]}
    tables = plot_tables("tedlium3", _records(), _audit(), protocol)
    assert tables["duration_distribution"]["bins"] == [0, 1, 3]
    assert tables["file_size_distribution"]["bins"] == [0, 150, 400]
    protocol["histogram_bytes_edges"] = [0, 150]
    with pytest.raises(ValueError, match="outside preregistered bins"):
        plot_tables("tedlium3", _records(), _audit(), protocol)


@pytest.mark.parametrize("dataset,image", [("tedlium3", False), ("iiit_cvid", True)])
def test_eight_pngs_bind_compact_sidecars_and_complete_inputs(tmp_path, dataset, image):
    records, audit, protocol = _records(image), _audit(), {"version": "test-v1"}
    manifest = render_readiness_figures(tmp_path, dataset, records, audit, protocol)
    assert len(manifest) == len({r["figure_id"] for r in manifest}) == 8
    for entry in manifest:
        png = tmp_path / entry["path"]
        assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert png.stat().st_size > 5000
        assert hashlib.sha256(png.read_bytes()).hexdigest() == entry["sha256"]
        sidecar = tmp_path / entry["source_table_path"]
        assert hashlib.sha256(sidecar.read_bytes()).hexdigest() == entry["source_table_sha256"]
        source = json.loads(sidecar.read_text(encoding="utf-8"))
        assert "records" not in source and "audit" not in source  # large inputs stored once
        for name, expected in (("records", records), ("audit", audit), ("protocol", protocol)):
            linked = source["inputs"][name]
            path = tmp_path / linked["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == linked["sha256"]
            assert json.loads(path.read_text(encoding="utf-8")) == expected
        assert source["inputs"]["protocol"]["sha256"] == entry["protocol_sha256"]
        assert entry["n"] == 3 and entry["kept_n"] == 2
        assert entry["official_d2"] is False
        assert len(entry["code_revision"]) == 64
    duration = next(row for row in manifest if row["figure_id"] == "duration_distribution")
    assert duration["render_status"] == ("not_applicable" if image else "rendered")


def test_unknown_decisions_and_unsafe_dataset_rejected(tmp_path):
    records = _records()
    records[0]["decision"] = "pending"
    with pytest.raises(ValueError, match="explicit keep/exclude"):
        plot_tables("tedlium3", records, {}, {})
    with pytest.raises(ValueError, match="unsafe dataset_id"):
        render_readiness_figures(tmp_path, "../escape", _records(), {}, {})
