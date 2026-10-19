"""Verify source identity and reversible interval traces, not semantic cleanup."""
import unicodedata

import pytest

from experiments.scripts.tib_model_benchmark_canonical import canonical_record, normalize_with_offsets
from experiments.scripts.tib_model_benchmark_eda import analyze, quantiles


@pytest.mark.parametrize("raw,expected", [
    ("  Cafe\u0301\n\tworld  ", "Café world"),
    ("same source", "same source"), (" \t\n", ""), ("", ""),
    ("mispelled \ufffd source", "mispelled \ufffd source"),
])
def test_normalization_retains_raw_trace_and_never_rewrites_semantics(raw, expected):
    text, runs, trim = normalize_with_offsets(raw)
    assert text == expected
    position = 0
    for a, b, c, d, kind in runs:
        assert a == position and b > a and 0 <= c < d <= len(raw)
        if kind == "identity":
            assert text[a:b] == raw[c:d]
        elif raw[c:d].isspace():
            assert text[a:b] == " "
        else:
            assert text[a:b] == unicodedata.normalize("NFC", raw[c:d])
        position = b
    assert position == len(text)
    assert trim["trailing_raw_span"][1] == len(raw)


def test_segments_never_replace_canonical_transcript_or_force_exclusion():
    row = canonical_record("train", 2, "train.parquet", {
        "transcript": " Full transcript. ", "abstract": "Reference",
        "transcript_segments": {"text": ["Other text"], "start": [0.0], "end": [1.0]},
    })
    assert row["source_raw"] == " Full transcript. "
    assert row["source_normalized"] == "Full transcript."
    assert row["structure_pass"] is True
    assert "transcript_segment_mismatch" in row["quality_flags"]
    assert row["primary_prompt_timestamps"] is False


def test_invalid_sidecars_flag_without_synthesizing_source():
    row = canonical_record("test", 0, "test.parquet", {
        "transcript": None, "abstract": None,
        "transcript_segments": {"text": ["Sidecar text"], "start": None, "end": [0.0]},
    })
    assert row["structure_pass"] is False and row["source_normalized"] == ""
    assert "invalid_segment_sidecar_shape" in row["quality_flags"]
    assert "empty_reference" in row["quality_flags"]


def test_compression_quantiles_skip_unknown_and_never_zero_fill():
    result = quantiles([1, 2, float("nan"), 3])
    assert result["n"] == 3 and result["p50"] == 2 and result["max"] == 3
    assert quantiles([])["p95"] is None


def test_eda_refuses_output_inside_immutable_snapshot(tmp_path):
    snapshot = tmp_path / "source"
    snapshot.mkdir()
    with pytest.raises(ValueError, match="immutable snapshot"):
        analyze(snapshot, tmp_path / "not-loaded", snapshot / "output")
    assert not (snapshot / "output").exists()
