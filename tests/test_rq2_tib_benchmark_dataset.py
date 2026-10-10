"""Offline checks for reusable TIB benchmark input preparation."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "experiments/scripts/rq2_tib_benchmark_dataset.py"
spec = importlib.util.spec_from_file_location("rq2_tib_benchmark_dataset", SCRIPT)
tib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tib)


def row(*, doi="", title="A talk", author="A person", abstract=None, starts=None,
        ends=None, texts=None, transcript=None):
    texts = ["alpha beta", "gamma delta"] if texts is None else texts
    return {
        "doi": doi, "title": title, "author": author, "genre": "Conference/Talk",
        "url": "https://example.org/talk", "license": "CC BY\nextra text",
        "transcript": "alpha beta gamma delta" if transcript is None else transcript,
        "abstract": "word " * 30 if abstract is None else abstract,
        "transcript_segments": {
            "text": texts,
            "start": [0, 2] if starts is None else starts,
            "end": [1, 3] if ends is None else ends,
        },
    }


def test_preserves_full_text_and_reports_reference_limit_separately():
    good = tib.prepare_record("valid", 4, row(abstract="brief abstract"))
    assert good["source_text"] == "alpha beta gamma delta"
    assert good["segment_starts_seconds"] == (0.0, 2.0)
    assert good["segment_ends_seconds"] == (1.0, 3.0)
    assert good["text_usable"] and good["abstract_agreement_candidate"]
    assert "short_abstract_under_30_words" in good["audit_flags"]
    assert "missing_doi" in good["audit_flags"]
    assert good["reference_status"] == "unverified_creator_abstract"

    empty = tib.prepare_record("valid", 5, row(abstract=""))
    assert empty["text_usable"] and not empty["abstract_agreement_candidate"]
    assert empty["reference_reasons"] == ["empty_abstract"]


@pytest.mark.parametrize("change,reason", [
    ({"starts": [0, float("nan")]}, "invalid_segment_times"),
    ({"starts": [2, 0], "ends": [3, 1]}, "unordered_segments"),
    ({"texts": ["alpha beta", ""]}, "empty_segment_text"),
    ({"ends": [1]}, "misaligned_segments"),
])
def test_structural_failures_are_excluded_with_reason(change, reason):
    prepared = tib.prepare_record("train", 0, row(**change))
    assert reason in prepared["structural_reasons"]
    assert not prepared["text_usable"]
    assert not prepared["abstract_agreement_candidate"]


def test_text_only_input_keeps_timing_overlap_and_transcript_disagreement_as_flags():
    prepared = tib.prepare_record("train", 0, row(starts=[0, 0.5], transcript="different words"))
    assert prepared["text_usable"]
    assert prepared["abstract_agreement_candidate"]
    assert prepared["segment_overlap_count"] == 1
    assert prepared["transcript_matches_segments"] is False
    assert "overlapping_segments" in prepared["audit_flags"]
    assert "transcript_segment_mismatch" in prepared["audit_flags"]


def test_cross_split_groups_are_flags_and_audit_omits_large_text():
    prepared = tib.prepare_dataset({
        "train": [row(title=" Shared Talk ", author="Same Author", abstract="first talk " * 30)],
        "valid": [row(title="shared  talk", author="same author", abstract="second talk " * 30)],
    }, verify_counts=False)
    assert prepared["counts_by_split"] == {"train": 1, "valid": 1}
    assert prepared["candidate_count"] == 2
    assert prepared["shared_group_counts"] == {"doi": 0, "title": 1, "author": 1}
    assert prepared["audit"][0]["audit_flags"] == [
        "cross_split_author_group", "cross_split_title_group", "missing_doi"
    ]
    assert "source_text" not in prepared["audit"][0]
    assert "segment_ends_seconds" not in prepared["audit"][0]
    assert prepared["test_content_accessed"] is False


def test_freeze_is_explicit_stable_and_rejects_ineligible_ids():
    prepared = tib.prepare_dataset({
        "valid": [row(doi="a", abstract="first talk " * 30),
                  row(doi="b", abstract="second talk " * 30),
                  row(doi="c", abstract="")],
    }, verify_counts=False)
    forward = tib.freeze_abstract_agreement_cohort(prepared, [("valid", 1), ("valid", 0)])
    reverse = tib.freeze_abstract_agreement_cohort(prepared, [("valid", 0), ("valid", 1)])
    assert forward["selection_sha256"] == reverse["selection_sha256"]
    assert forward["selected_ids"] == [("valid", 0), ("valid", 1)]
    assert forward["selected_count"] == 2
    assert forward["claim"] == "agreement_with_unverified_creator_abstracts_only"
    assert forward["group_safety_verified"] is False
    assert forward["unseen_final_test_claim_supported"] is False
    for ids in ([], [("valid", 0)] * 2, [("valid", 2)], [("test", 0)]):
        with pytest.raises(ValueError):
            tib.freeze_abstract_agreement_cohort(prepared, ids)


def test_broad_pool_keeps_all_genres_and_excludes_reused_abstracts():
    one = row(doi="a", abstract="Unique content " * 20)
    one["genre"] = "Lecture"
    two = row(doi="b", abstract="Shared course summary " * 20)
    two["genre"] = "Conference/Talk"
    three = row(doi="c", abstract=two["abstract"].upper())
    three["genre"] = "Webinar/Tutorial"
    prepared = tib.prepare_dataset({"train": [one, two], "valid": [three]}, verify_counts=False)
    assert prepared["candidate_count"] == 3
    assert prepared["broad_pool_count"] == 1
    assert prepared["broad_pool_ids"] == [("train", 0)]
    assert prepared["broad_pool_diversity"]["genre"] == {"Lecture": 1}
    assert "cross_split_shared_abstract_group" in prepared["audit"][1]["audit_flags"]
    assert "cross_split_shared_abstract_group" in prepared["audit"][2]["audit_flags"]
    with pytest.raises(ValueError, match="ineligible"):
        tib.freeze_abstract_agreement_cohort(prepared, [("valid", 0)])


def test_broad_pool_has_no_genre_or_size_cap_and_scans_all_split_groups():
    rows = {}
    for split, genre in (("train", "Lecture"), ("valid", "Conference/Talk"),
                         ("test", "Webinar/Tutorial")):
        items = [row(doi=f"{split}-{i}", abstract=f"{split} talk {i} " * 30)
                 for i in range(3)]
        for item in items:
            item["genre"] = genre
        rows[split] = items
    prepared = tib.prepare_dataset(rows, verify_counts=False)
    assert prepared["all_splits_scanned"] is True
    assert prepared["broad_pool_count"] == 9
    assert len(prepared["broad_pool_ids"]) == 9
    assert prepared["broad_pool_diversity"]["genre"] == {
        "Lecture": 3, "Conference/Talk": 3, "Webinar/Tutorial": 3
    }
    cohort = tib.freeze_abstract_agreement_cohort(prepared, prepared["broad_pool_ids"])
    assert cohort["selected_count"] == 9
    assert cohort["all_splits_scanned"] is True
    assert cohort["group_safety_verified"] is False


def test_unusable_copy_does_not_remove_the_only_usable_reference():
    original = row(doi="a", abstract="single usable source " * 20)
    unusable = row(doi="b", abstract=original["abstract"], starts=[0, float("nan")])
    prepared = tib.prepare_dataset({"train": [original], "valid": [unusable]},
                                   verify_counts=False)
    assert prepared["broad_pool_ids"] == [("train", 0)]


def test_pinned_loader_requests_only_named_splits(monkeypatch):
    calls = []
    fake = types.ModuleType("datasets")
    fake.load_dataset = lambda name, **kwargs: calls.append((name, kwargs)) or iter(())
    monkeypatch.setitem(sys.modules, "datasets", fake)
    assert list(tib.load_pinned_splits(("valid",))) == ["valid"]
    assert calls == [(tib.DATASET, {"split": "valid", "revision": tib.REVISION,
                                    "streaming": True})]
    with pytest.raises(ValueError):
        tib.load_pinned_splits(("valid", "valid"))


def test_pinned_counts_fail_closed():
    with pytest.raises(ValueError, match="row count changed"):
        tib.prepare_dataset({"valid": [row()]})
