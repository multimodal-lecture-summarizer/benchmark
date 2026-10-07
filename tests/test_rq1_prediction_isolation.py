"""The chapter predictors must never receive published annotation columns."""

from experiments.scripts.chapter_benchmark_contract import predictor_input


def test_predictor_input_only_exposes_source_text() -> None:
    unit = {
        "transcript": "Source ASR text",
        "target_ts": "[CSTART] 00:01:00 - leaked title [CEND]",
        "raw_chapters": [{"start_time": 60, "title": "leaked title"}],
        "chapter_boundaries_sec": [60.0],
        "chapter_gt": {"source": "held out"},
        "duration_sec": 100.0,
    }
    assert predictor_input(unit) == {"transcript": "Source ASR text"}
