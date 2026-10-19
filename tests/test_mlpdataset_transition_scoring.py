"""Scientific matching and qualification contracts for slide-end scoring."""

import math
from itertools import product

import pytest

from experiments.scripts.mlpdataset_transition_scoring import match_events, score_videos


def source(**changes):
    return {"duration_sec": 10, "group": "course-a", "eligible": True,
            "fully_annotated_scope": True, "hold_intervals": [], **changes}


def test_maximum_cardinality_beats_nearest_first_greedy():
    pairs = match_events([1.0, 1.6], [0.6, 1.1], 0.5)
    assert [(p["reference_index"], p["prediction_index"]) for p in pairs] == [(0, 0), (1, 1)]


def test_minimum_error_and_one_to_one():
    assert match_events([1], [0.6, 1.1])[0]["prediction_index"] == 1
    assert len(match_events([1, 1.1], [1])) == 1
    assert len(match_events([1], [1, 1])) == 1


def test_ties_original_indices_and_inclusive_collar():
    assert match_events([1], [1.5, 0.5])[0]["prediction_index"] == 0
    assert len(match_events([1], [1.5])) == 1
    assert not match_events([1], [1.500001])
    assert match_events([1, 1], [1, 1]) == [
        {"reference_index": 0, "prediction_index": 0, "absolute_error_sec": 0},
        {"reference_index": 1, "prediction_index": 1, "absolute_error_sec": 0}]


def test_sort_is_internal_and_original_indices_survive():
    refs, preds = [3, 1], [1, 3]
    assert [(r["reference_index"], r["prediction_index"])
            for r in match_events(refs, preds)] == [(1, 0), (0, 1)]
    assert refs == [3, 1] and preds == [1, 3]


@pytest.mark.parametrize("values", [[math.nan], [math.inf], [-1], [True], ["1"], "1"])
def test_invalid_times(values):
    with pytest.raises(ValueError):
        match_events(values, [])
    with pytest.raises(ValueError):
        match_events([], values)


@pytest.mark.parametrize("collar", [-1, math.nan, math.inf, True])
def test_invalid_collar(collar):
    with pytest.raises(ValueError):
        match_events([], [], collar)


def test_empty_source_has_undefined_metrics():
    scored = score_videos({"a": []}, {}, {"a": source()})
    assert scored["pooled"] == {"tp": 0, "fp": 0, "fn": 0,
                                 "precision": None, "recall": None, "f1": None}
    assert scored["macro_group"]["f1_defined_groups"] == 0
    assert match_events([], [1]) == []
    assert match_events([1], []) == []


def test_source_partition_pooled_and_macro_groups():
    scored = score_videos({"a": [1], "b": [2]}, {"a": [2], "b": [1]},
                          {"a": source(), "b": source(group="course-b")})
    assert scored["pooled"]["tp"] == 0
    assert scored["pooled"]["fp"] == scored["pooled"]["fn"] == 2
    assert len(scored["per_group"]) == 2
    assert scored["macro_group"]["f1"] == 0


def test_unresolved_intervals_block_whole_source_not_only_gt():
    scored = score_videos({"a": [1], "b": [2]}, {"a": [1, 7], "b": [2]},
                          {"a": source(hold_intervals=[[0.5, 1.5]], ignored_event_count=2),
                           "b": source()})
    assert scored["blocked"]["a"]["prediction_count"] == 2
    assert scored["pooled"]["tp"] == 1 and scored["pooled"]["fp"] == 0
    assert scored["ignored_event_count"] == 2
    assert scored["blocked_video_count"] == 1


def test_unlabeled_and_incomplete_scope_never_become_negatives():
    scored = score_videos({}, {"a": [1]}, {"a": source(fully_annotated_scope=False)})
    assert scored["scored_video_count"] == 0
    assert "unlabeled" in scored["blocked"]["a"]["reasons"]


@pytest.mark.parametrize("values", [[10], [11], [-1], [math.nan]])
def test_out_of_range_values(values):
    with pytest.raises(ValueError):
        score_videos({"a": values}, {}, {"a": source()})
    with pytest.raises(ValueError):
        score_videos({"a": []}, {"a": values}, {"a": source()})


def test_unknown_video_and_track_and_unregistered_collar():
    with pytest.raises(ValueError, match="unknown"):
        score_videos({"a": []}, {"b": []}, {"a": source()})
    with pytest.raises(ValueError):
        score_videos({}, {}, {}, label_track="mixed")
    with pytest.raises(ValueError):
        score_videos({}, {}, {}, collar=0.7)


def test_formal_aggregate_is_blocked_until_gt_and_cohort_frozen():
    with pytest.raises(ValueError, match="pending"):
        score_videos({"a": [1]}, {"a": [1]}, {"a": source()}, formal=True)
    qualified = {"gt_status": "frozen", "cohort_status": "frozen",
                 "label_track": "reviewed", "manifest_sha256": "a" * 64}
    scored = score_videos({"a": [1]}, {"a": [1]}, {"a": source()},
                          formal=True, qualification=qualified)
    assert scored["status"] == "formal"
    with pytest.raises(ValueError, match="unresolved"):
        score_videos({"a": [1]}, {}, {"a": source(hold_intervals=[[0, 2]])},
                     formal=True, qualification=qualified)


def test_ignored_non_target_annotations_do_not_remove_predictions():
    scored = score_videos({"a": [1]}, {"a": [1, 5]},
                          {"a": source(ignored_event_count=1)})
    assert scored["pooled"]["fp"] == 1
    assert scored["ignored_event_count"] == 1


def test_missing_predictions_are_audited_and_count_as_misses_in_diagnostics():
    scored = score_videos({"a": [1]}, {}, {"a": source()})
    assert scored["missing_prediction_videos"] == ["a"]
    assert scored["per_video"]["a"]["prediction_status"] == "missing_output"
    assert scored["pooled"]["fn"] == 1


def test_formal_requires_real_hash_nonempty_manifest_and_outputs():
    qualified = {"gt_status": "frozen", "cohort_status": "frozen",
                 "label_track": "reviewed", "manifest_sha256": "bad"}
    with pytest.raises(ValueError, match="pending"):
        score_videos({}, {}, {}, formal=True, qualification=qualified)
    qualified["manifest_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="nonempty"):
        score_videos({}, {}, {}, formal=True, qualification=qualified)
    with pytest.raises(ValueError, match="missing output"):
        score_videos({"a": [1]}, {}, {"a": source()}, formal=True, qualification=qualified)


def test_explicit_eligibility_boolean_required():
    scored = score_videos({"a": [1]}, {"a": [1]}, {"a": source(eligible="yes")})
    assert scored["scored_video_count"] == 0


def test_matching_objectives_against_exhaustive_small_oracle():
    # Independent enumeration allows crossing edges, unlike production DP.
    def oracle(refs, preds, index=0, used=frozenset()):
        if index == len(refs):
            return (0, 0.0)
        options = [oracle(refs, preds, index + 1, used)]
        for j, value in enumerate(preds):
            error = abs(refs[index] - value)
            if j not in used and error <= 0.5:
                count, total = oracle(refs, preds, index + 1, used | {j})
                options.append((count + 1, total + error))
        return min(options, key=lambda pair: (-pair[0], pair[1]))

    arrays = list(product((0, 0.5, 1), repeat=3))
    for refs in arrays:
        for preds in arrays:
            pairs = match_events(refs, preds)
            assert (len(pairs), sum(p["absolute_error_sec"] for p in pairs)) == oracle(refs, preds)
