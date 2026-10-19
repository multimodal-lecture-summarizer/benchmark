import pytest

from experiments.scripts.tib_benchmark_adapter_budget import (
    AdapterFailure, Budget, materialize_batch, plan_windows,
)


def wrapper(ids, stage):
    return [90] + ids + [91]


def test_encoder_decoder_reserves_are_independent():
    budget = Budget("encoder_decoder", 8, 7, decoder_cap=8)
    assert budget.prepare(list(range(6)), wrapper, "map")["padded_length"] == 8
    with pytest.raises(ValueError, match="decoder"):
        Budget("encoder_decoder", 8, 8, decoder_cap=8)


def test_causal_reserves_prompt_and_output():
    budget = Budget("causal", 10, 3)
    assert budget.prepare(list(range(5)), wrapper, "map")["padded_length"] == 7
    with pytest.raises(AdapterFailure, match="overflow"):
        budget.prepare(list(range(6)), wrapper, "map")


def test_led_padding_and_global_attention_mask():
    budget = Budget("encoder_decoder", 8, 3, decoder_cap=8,
                    padding_multiple=4, global_first_token=True)
    prepared = budget.prepare([1, 2, 3], wrapper, "map")
    actual = materialize_batch(prepared, 0)
    assert actual["input_ids"] == [90, 1, 2, 3, 91, 0, 0, 0]
    assert actual["attention_mask"] == [1, 1, 1, 1, 1, 0, 0, 0]
    assert actual["global_attention_mask"] == [1, 0, 0, 0, 0, 0, 0, 0]
    with pytest.raises(AdapterFailure, match="pad token"):
        materialize_batch(prepared, None)


def test_window_plan_preserves_tail_and_overlap():
    source = list(range(21))
    budget = Budget("causal", 10, 3)
    windows = plan_windows(source, budget, wrapper, overlap=1)
    assert windows[0]["start"] == 0
    assert windows[-1]["end"] == len(source)
    assert set().union(*(set(range(w["start"], w["end"])) for w in windows)) == set(range(21))
    assert all(b["start"] == a["end"] - 1 for a, b in zip(windows, windows[1:]))


def test_impossible_wrapper_and_nonprogress_fail():
    with pytest.raises(AdapterFailure, match="capacity"):
        plan_windows([1], Budget("causal", 2, 1), wrapper)
    with pytest.raises(AdapterFailure, match="progress"):
        plan_windows([1, 2, 3], Budget("causal", 5, 2), wrapper, overlap=1)


def test_padding_not_only_unpadded_input_checked():
    with pytest.raises(AdapterFailure, match="overflow"):
        Budget("causal", 10, 3, padding_multiple=8).prepare([1], wrapper, "map")


@pytest.mark.parametrize("architecture", ["encoder_decoder", "causal"])
def test_empty_source_fails(architecture):
    budget = Budget(architecture, 20, 3, decoder_cap=8)
    with pytest.raises(AdapterFailure, match="empty"):
        plan_windows([], budget, wrapper)
