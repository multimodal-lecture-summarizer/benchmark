import pytest

from experiments.scripts.tib_benchmark_adapter_budget import AdapterFailure, Budget
from experiments.scripts.tib_benchmark_adapter_generation import summarize_source, stable_node_seed
from experiments.scripts.tib_benchmark_output import select_delivered


def run(source, generate, **kwargs):
    budget = Budget("encoder_decoder", 20, 12, decoder_cap=20)
    return summarize_source(source, encode=lambda text: list(text), decode=lambda ids: "".join(ids),
                            wrapper=lambda ids, stage: ids, generate=generate,
                            budgets={stage: budget for stage in ("map", "reduce", "final")},
                            selector=select_delivered, word_cap=350, **kwargs)


def test_fullsource_lineage_all_notes_and_immediate_node_callbacks():
    checkpoints = []
    result = run("a" * 100, lambda batch, reserve, stage: "x", on_node=checkpoints.append)
    assert result["map_windows"] == 5
    assert result["source_intervals"] == [[0, 20], [20, 40], [40, 60], [60, 80], [80, 100]]
    assert [node["stage"] for node in checkpoints] == ["map"] * 5 + ["reduce", "final"]
    assert result["raw_final"] == result["delivered_final"] == "x"


def test_empty_generated_node_is_failure():
    with pytest.raises(AdapterFailure, match="empty"):
        run("hello", lambda *args: "")


def test_direct_final_only_when_entire_source_fits_final_budget():
    result = run("hello", lambda batch, reserve, stage: "x")
    assert result["map_windows"] == 0
    assert [node["stage"] for node in result["nodes"]] == ["final"]
    assert result["source_intervals"] == [[0, 5]]


def test_generated_native_reserve_is_checked():
    with pytest.raises(AdapterFailure, match="reserve"):
        run("hello", lambda *args: "x" * 13)


def test_no_reduction_progress_is_failure():
    with pytest.raises(AdapterFailure, match="fan-in|singleton|reduce note"):
        run("a" * 100, lambda *args: "x" * 12)


def test_depth_bound_does_not_drop_notes():
    with pytest.raises(AdapterFailure, match="depth"):
        run("a" * 100, lambda *args: "x", max_depth=1)


def test_seed_identity_does_not_include_attempt_index():
    assert stable_node_seed("study", "valid:1", "hash", 0, 2, 42) == stable_node_seed(
        "study", "valid:1", "hash", 0, 2, 42)
    assert stable_node_seed("study", "valid:1", "hash", 0, 2, 42) != stable_node_seed(
        "study", "valid:1", "hash", 0, 3, 42)


def test_oversized_note_fragments_are_never_decoded_and_keep_native_ids():
    # These Qwen byte fragments individually decode to replacement characters.
    fragments = [56252, 253, 247, 378, 235, 56252]
    seen = []

    def encode(text):
        if text == "source":
            return list(range(20))
        if text == "generated":
            return fragments
        return []  # explicit empty separator in this fixture

    def wrap(ids, stage):
        seen.append((stage, list(ids)))
        return ids

    def forbidden_decode(ids):
        raise AssertionError("Splitting a note must preserve IDs, not decode it")

    with pytest.raises(AdapterFailure, match="fan-in"):
        summarize_source("source", encode=encode, decode=forbidden_decode, wrapper=wrap,
                         generate=lambda *args: "generated", selector=select_delivered,
                         word_cap=350, budgets={
                             "map": Budget("encoder_decoder", 10, 8, decoder_cap=12),
                             "reduce": Budget("encoder_decoder", 5, 3, decoder_cap=12),
                             "final": Budget("encoder_decoder", 5, 8, decoder_cap=12)})
    assert ("reduce", fragments[:5]) in seen
    assert ("reduce", fragments[5:]) in seen
