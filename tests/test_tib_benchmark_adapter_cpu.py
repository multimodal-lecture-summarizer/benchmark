import pytest

from experiments.scripts.tib_benchmark_adapter_budget import AdapterFailure
from experiments.scripts.tib_benchmark_adapter_cpu import lead3, lexrank


def test_lead3_is_fixed_source_order_and_spans():
    source = "First source sentence. Second sentence! Third? Fourth tail."
    result = lead3(source, word_cap=350)
    assert result["raw_final"] == "First source sentence. Second sentence! Third?"
    assert result["selected_sentence_indices"] == [0, 1, 2]
    assert all(source[a:b] in result["raw_final"] for a, b in result["selected_source_spans"])
    assert result["generation_gpu_memory"] is None


def test_common_run_on_fallback_is_visible():
    result = lead3("one two three four five", word_cap=3)
    assert result["delivered_final"] == "one two three"
    assert result["delivery"]["forced_word_boundary"]


def test_lexrank_graph_includes_all_sentences_and_deterministic_ties():
    source = "Alpha cats. Beta dogs. Gamma birds. Delta fish."
    result = lexrank(source, word_cap=4, threshold=0.99)
    assert result["graph_sentence_count"] == 4
    assert result["selected_sentence_indices"] == [0, 1]
    assert len(result["sentence_scores"]) == 4
    assert result == lexrank(source, word_cap=4, threshold=0.99)


def test_lexrank_explicit_memory_failure_instead_of_topn():
    with pytest.raises(AdapterFailure, match="memory"):
        lexrank("Alpha sentence. Beta sentence.", word_cap=350, graph_memory_limit_bytes=1)


def test_lexrank_run_on_uses_common_fallback():
    result = lexrank("science alpha beta gamma delta", word_cap=2)
    assert result["delivered_final"] == "science alpha"
    assert result["delivery"]["forced_word_boundary"]


def test_no_sentences_and_no_vocabulary_fail():
    with pytest.raises(AdapterFailure, match="sentences"):
        lead3(" ", word_cap=350)
    with pytest.raises(AdapterFailure, match="vocabulary"):
        lexrank("the and or.", word_cap=350)
