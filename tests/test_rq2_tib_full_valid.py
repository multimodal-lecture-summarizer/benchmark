"""Offline contract checks for TIB all-split and historical validation cohorts."""

import importlib.util
import json
import sys
import types
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "experiments" / "scripts"


def _load(path: Path, monkeypatch):
    datasets = types.ModuleType("datasets")
    datasets.load_dataset = lambda *args, **kwargs: iter(())
    monkeypatch.setitem(sys.modules, "datasets", datasets)
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(index, doi, genre="Other"):
    return {
        "source_index": index,
        "doi": doi,
        "genre": genre,
        "source_url_present": True,
        "transcript_words": 10,
        "segment_count": 2,
        "segments_aligned": True,
        "segments_valid_times": True,
        "segments_ordered": True,
    }


def test_full_cohort_includes_every_genre_and_explains_exclusions(tmp_path, monkeypatch):
    module = _load(SCRIPTS / "rq2-tib-valid-eda.py", monkeypatch)
    rows = [_row(2, "dup", "Lecture"), _row(0, "dup"), _row(1, "valid", "Conference"), _row(3, "")]
    rows[3]["transcript_words"] = 0
    target = tmp_path / "full-valid.json"
    receipt = module.build_full_validation_cohort(rows, target)
    assert receipt["source_count"] == 4
    assert receipt["usable_count"] == 3
    assert receipt["usable"] == [
        {"source_index": 0, "doi": "dup"},
        {"source_index": 1, "doi": "valid"},
        {"source_index": 2, "doi": "dup"},
    ]
    assert receipt["manifest"][0]["audit_flags"] == ["duplicate_doi"]
    assert receipt["manifest"][3]["audit_flags"] == ["missing_doi"]
    assert receipt["manifest"][3]["exclusion_reasons"] == ["missing_transcript"]
    assert receipt["split_read"] == "valid" and receipt["test_content_accessed"] is False
    assert json.loads(target.read_text(encoding="utf-8")) == receipt
    assert module.build_full_validation_cohort(list(reversed(rows)), target)["usable_index_doi_sha256"] == receipt["usable_index_doi_sha256"]


def test_scan_rejects_nonfinite_segment_times(monkeypatch):
    module = _load(SCRIPTS / "rq2-tib-valid-eda.py", monkeypatch)
    module.load_dataset = lambda *args, **kwargs: iter([{
        "doi": "x", "transcript": "one two", "transcript_segments": {
            "start": [0.0, float("nan")], "end": [1.0, 2.0], "text": ["one", "two"]
        }
    }])
    row = module.scan_validation()[0]
    assert row["segments_valid_times"] is False
    assert row["segments_ordered"] is False


def test_all_splits_cohort_tracks_split_index_and_test_access(tmp_path, monkeypatch):
    module = _load(SCRIPTS / "rq2-tib-valid-eda.py", monkeypatch)
    records = {split: [{"doi": "same", "genre": "Conference", "url": "source",
                        "transcript": "a b", "transcript_segments": {
                            "start": [0, 2], "end": [1, 3], "text": ["a", "b"]
                        }}] for split in ("train", "valid", "test")}
    seen = []
    def load(*args, split, **kwargs):
        seen.append(split)
        return iter(records[split])
    module.load_dataset = load
    rows = module.scan_all_splits()
    receipt = module.build_full_dataset_cohort(rows, tmp_path / "all-tib.json")
    assert seen == ["train", "valid", "test"]
    assert receipt["source_count"] == receipt["usable_count"] == 3
    assert [(row["split"], row["source_index"]) for row in receipt["manifest"]] == [
        ("train", 0), ("valid", 0), ("test", 0)
    ]
    assert all(row["audit_flags"] == ["duplicate_doi_across_dataset"]
               for row in receipt["manifest"])
    assert receipt["test_content_accessed"] is True
    assert receipt["final_test_holdout_sealed"] is False
    assert receipt["split_counts"]["test"] == {"source_count": 1, "usable_count": 1}
    assert receipt["cross_split_shared_group_counts"]["doi"] == 1


def test_detail_scan_records_errors_and_missing_without_aborting(monkeypatch):
    module = _load(SCRIPTS / "rq2_tib_valid_detail_eda.py", monkeypatch)
    records = [
        {"doi": "broken", "transcript_segments": {"start": [0, 2], "end": [1], "text": ["a", "b"]}},
        {"doi": "good", "genre": "Conference", "transcript": "a b", "abstract": "summary",
         "transcript_segments": {"start": [0, 2], "end": [1, 3], "text": ["a", "b"]}},
    ]
    module.load_dataset = lambda *args, **kwargs: iter(records)
    details = module.scan_all_usable_details([_row(0, "broken"), _row(1, "good"), _row(4, "lost")])
    assert [item["status"] for item in details] == ["error", "ok", "missing"]
    assert details[1]["genre"] == "Conference"
    assert details[1]["abstract_words"] == 1
    assert details[1]["keyframe_pixels_read"] is False


def test_all_dataset_detail_scan_keys_rows_by_split(monkeypatch):
    module = _load(SCRIPTS / "rq2_tib_valid_detail_eda.py", monkeypatch)
    seen = []
    def load(*args, split, **kwargs):
        seen.append(split)
        return iter([{"doi": split, "transcript": "a b", "abstract": "summary",
                      "transcript_segments": {"start": [0, 2], "end": [1, 3],
                                              "text": ["a", "b"]}}])
    module.load_dataset = load
    usable = [{"split": split, "source_index": 0, "doi": split}
              for split in ("train", "valid", "test")]
    details = module.scan_all_dataset_details(usable)
    assert seen == ["train", "valid", "test"]
    assert [(row["split"], row["source_index"], row["status"]) for row in details] == [
        ("train", 0, "ok"), ("valid", 0, "ok"), ("test", 0, "ok")
    ]


def test_train_overlap_reports_every_matching_doi(monkeypatch):
    module = _load(SCRIPTS / "rq2-tib-valid-eda.py", monkeypatch)
    class Batch:
        def to_pylist(self):
            return [{"doi": "train", "title": "SAME", "author": "SAME AUTHOR"}]
    class ParquetFile:
        def __init__(self, source):
            pass
        def iter_batches(self, **kwargs):
            return [Batch()]
    class FS:
        def open(self, *args):
            from io import BytesIO
            return BytesIO(b"")
    pyarrow = types.ModuleType("pyarrow")
    parquet = types.ModuleType("pyarrow.parquet")
    parquet.ParquetFile = ParquetFile
    pyarrow.parquet = parquet
    hub = types.ModuleType("huggingface_hub")
    hub.HfFileSystem = FS
    monkeypatch.setitem(sys.modules, "pyarrow", pyarrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", parquet)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    rows = [{"source_index": 0, "doi": "a", "title": "Same", "author": "Same Author"},
            {"source_index": 1, "doi": "b", "title": "Same", "author": "Same Author"}]
    receipt = module.scan_train_metadata_overlap(rows)
    assert receipt["selected_exact_title_in_train"] == ["a", "b"]
    assert receipt["selected_author_train_record_counts"] == {"a": 2, "b": 2}
    assert receipt["selected_source_index_exact_title_in_train"] == [0, 1]
    assert receipt["selected_source_index_author_train_record_counts"] == {"0": 2, "1": 2}
