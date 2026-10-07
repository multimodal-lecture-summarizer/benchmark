"""Focused validation of RQ2 automatic diagnostic provenance and metric labels."""

import hashlib

import pytest

from experiments.scripts import rq2_valid_automatic_evaluation as evaluation


def _fixture(monkeypatch):
    doi = "10.5446/123 (DOI)"
    record = {
        "doi": doi,
        "abstract": "This lecture explains numerical optimization methods.",
        "subject": "Mathematics",
        "transcript_segments": {
            "text": ["Numerical optimization methods solve important problems."],
            "start": [0.0],
            "end": [10.0],
        },
    }
    source_hash = hashlib.sha256(record["transcript_segments"]["text"][0].encode()).hexdigest()
    pair = {
        "transcript_sha256": source_hash,
        "input": {"prefix_truncated": False, "full_transcript_words": 6},
        "arms": {
            "S1": {
                "summary": "Numerical optimization methods solve problems.",
                "cumulative_prompt_token_estimate": 100,
                "estimated_prompt_cap_exceeded": False,
                "call_count": 2,
            },
            "S3_lexical_cohesion": {
                "summary": "Unrelated invented assertion.",
                "cumulative_prompt_token_estimate": 120,
                "estimated_prompt_cap_exceeded": False,
                "call_count": 3,
            },
        },
    }
    monkeypatch.setattr(evaluation, "_load_pair", lambda entry, selection_hash: pair)
    receipt = {"selected_doi_sha256": "selection", "selected": [{"doi": doi}]}
    manifest = {
        "status": "development_diagnostic_only",
        "split": "valid",
        "test_content_accessed": False,
        "selection_sha256": "selection",
        "completed": [{"doi": doi, "path": "ignored-in-test"}],
        "failed": [],
        "missing": [],
    }
    screen = {
        "dataset": evaluation.DATASET,
        "revision": evaluation.REVISION,
        "split": "valid",
        "test_content_accessed": False,
        "items": {"123": {"screen": "candidate_unverified"}},
    }
    return manifest, receipt, {doi: record}, screen


def test_evaluator_reports_proxy_and_paired_delta(monkeypatch):
    manifest, receipt, records, screen = _fixture(monkeypatch)
    result = evaluation.evaluate_records(manifest, receipt, records, screen)
    row = result["rows"][0]
    assert result["n"] == 1
    assert row["arms"]["S1"]["source_lexical_support_proxy"] == 1.0
    assert row["arms"]["S3"]["source_lexical_support_proxy"] == 0.0
    assert row["delta_s3_minus_s1"]["source_lexical_support_proxy"] == -1.0
    assert result["limits"]["factuality_measured"] is False
    assert result["limits"]["reference_validity_verified"] is False
    assert result["strata"]["full_transcript"]["n"] == 1
    assert result["strata"]["reference_candidate_unverified"]["n"] == 1
    assert result["strata"]["reference_unsuitable"]["n"] == 0


def test_evaluator_rejects_missing_or_test_evidence(monkeypatch):
    manifest, receipt, records, screen = _fixture(monkeypatch)
    manifest["test_content_accessed"] = True
    with pytest.raises(ValueError, match="validation diagnostic"):
        evaluation.evaluate_records(manifest, receipt, records, screen)
    manifest["test_content_accessed"] = False
    manifest["missing"] = ["another-doi"]
    with pytest.raises(ValueError, match="validation diagnostic"):
        evaluation.evaluate_records(manifest, receipt, records, screen)
    manifest["missing"] = []
    screen["items"] = {"999": {"screen": "unsuitable"}}
    with pytest.raises(ValueError, match="Reference screen DOI set"):
        evaluation.evaluate_records(manifest, receipt, records, screen)


def test_paired_bootstrap_is_deterministic_and_handles_no_reference():
    assert evaluation.paired_interval([])["ci95"] is None
    a = evaluation.paired_interval([0.2, -0.1, 0.3], samples=200)
    b = evaluation.paired_interval([0.2, -0.1, 0.3], samples=200)
    assert a == b
    assert a["ci95"][0] <= a["mean_s3_minus_s1"] <= a["ci95"][1]
