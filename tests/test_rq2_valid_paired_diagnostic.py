"""Focused safety checks for the validation-only RQ2 paired runner."""

import json
import hashlib

import pytest

from experiments.scripts import rq2_valid_paired_diagnostic as runner


def _record(texts, starts=None, ends=None):
    starts = starts or list(range(len(texts)))
    ends = ends or [value + 1 for value in starts]
    return {
        "doi": "10.5446/1 (DOI)",
        "transcript_segments": {"text": texts, "start": starts, "end": ends},
    }


def test_prefix_preserves_timebase_and_reports_truncation(monkeypatch):
    monkeypatch.setattr(runner, "SOURCE_CAP", 4)
    texts, starts, end, truncated = runner._aligned_prefix(
        _record(["one two three four", "five six"], [0, 4], [4, 6])
    )
    assert texts == ["one two three"]
    assert starts == [0.0]
    assert end == 3.0
    assert truncated is True


@pytest.mark.parametrize("record", [
    _record(["one", ""], [0, 1], [1, 2]),
    _record(["one", "two"], [0, 0.5], [1, 2]),
    _record(["one"], [float("nan")], [1]),
])
def test_bad_segments_fail_closed(record):
    with pytest.raises(ValueError):
        runner._aligned_prefix(record)


def test_zero_duration_source_segment_is_retained():
    texts, starts, end, truncated = runner._aligned_prefix(_record(["one", "two"], [0, 1], [0, 2]))
    assert (texts, starts, end, truncated) == (["one", "two"], [0.0, 1.0], 2.0, False)


def test_resume_rejects_corrupt_or_incomplete_result(tmp_path):
    path = tmp_path / "item.json"
    record = _record(["one two"])
    receipt = {"selected_doi_sha256": "selection"}
    path.write_text("{broken", encoding="utf-8")
    assert not runner._valid_resume(path, record, receipt, False)
    path.write_text(json.dumps({"doi": record["doi"], "revision": runner.REVISION}), encoding="utf-8")
    assert not runner._valid_resume(path, record, receipt, False)
    path.write_text("[]", encoding="utf-8")
    assert not runner._valid_resume(path, record, receipt, False)
    path.write_text(json.dumps({"arms": {"S1": {"summary": 5}}}), encoding="utf-8")
    assert not runner._valid_resume(path, record, receipt, False)


def test_resume_requires_matching_transcript_and_complete_pair(tmp_path):
    path = tmp_path / "item.json"
    record = _record(["one two"])
    receipt = {"selected_doi_sha256": "selection"}
    result = {
        "doi": record["doi"], "dataset": runner.DATASET, "revision": runner.REVISION,
        "runner_sha256": runner.RUNNER_SHA256, "selection_sha256": "selection",
        "transcript_sha256": hashlib.sha256(b"one two").hexdigest(),
        "sbert_model_available": False,
        "formal_h2_eligible": False,
        "arms": {name: {"summary": "source-specific", "calls": [{"prompt_words": 2}]}
                 for name in ("S1", "S3_lexical_cohesion")},
    }
    runner._write_json_atomic(path, result)
    assert runner._valid_resume(path, record, receipt, False)
    assert not runner._valid_resume(path, record, receipt, True)
    assert not runner._valid_resume(path, _record(["different words"]), receipt, False)


def test_runner_rejects_wrong_receipt_before_dataset_read(tmp_path, monkeypatch):
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"dataset": runner.DATASET, "revision": runner.REVISION,
                                   "split_read": "test"}), encoding="utf-8")
    monkeypatch.setattr(runner, "RECEIPT_PATH", receipt)
    monkeypatch.setattr(runner, "load_dataset", lambda *args, **kwargs: pytest.fail("dataset accessed"))
    with pytest.raises(ValueError, match="declared validation cohort"):
        runner.run(1)
