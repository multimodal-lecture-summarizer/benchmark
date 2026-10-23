import pytest

from experiments.scripts.tib_budget_views import CONTRACT_CAP, PRIMARY_BUDGETS, build_views
from experiments.scripts.tib_fact_inventory import (
    DocumentFrequency, build_document_frequency, build_inventory, key_set, stem, tokenize,
)
from experiments.scripts.tib_reference_free_metrics import (
    auc, coverage, index_source, score_views, temporal_coverage, unsupported_rate,
)

SOURCE = (
    "The blast furnace makes iron. Coke feeds the blast furnace. "
    "Casting follows steel making. The casting line needs water. "
    "Rolling mills shape the steel. Rolling mills used 1,200 tons last year. "
    "Engineers at Tata Steel manage the rolling mills. The blast furnace runs hot."
)
EMPTY_DF = DocumentFrequency(1000, {})


def sentences(n: int) -> str:
    return " ".join(f"Word{i} alpha beta gamma delta." for i in range(n))


def test_views_are_nested_sentence_prefixes_within_budgets():
    raw = sentences(120)  # 600 words
    views = build_views(raw)
    assert list(views) == ["S", "M", "L", "contract"]
    texts = [views[name]["text"] for name in views]
    for shorter, longer in zip(texts, texts[1:]):
        assert longer.startswith(shorter)
    for name, cap in PRIMARY_BUDGETS.items():
        assert views[name]["delivered_words"] <= cap
    assert views["contract"]["delivered_words"] <= CONTRACT_CAP
    assert views["L"]["delivered_words"] > views["M"]["delivered_words"] > views["S"]["delivered_words"]


def test_short_output_is_identical_across_views_and_empty_fails():
    views = build_views("One short answer.")
    assert len({v["text"] for v in views.values()}) == 1 and not views["S"]["capped"]
    with pytest.raises(ValueError):
        build_views("   ")


def test_budget_validation():
    with pytest.raises(ValueError):
        build_views("Text here.", {"S": 60, "L": 400})
    with pytest.raises(ValueError):
        build_views("Text here.", {"L": 240, "S": 60})


def test_tokenizer_normalizes_numbers_and_stops_break_phrases():
    kinds = {t.norm: t.kind for t in tokenize("In 1,200 tons of the blast furnace")}
    assert kinds["1200"] == "num" and kinds["in"] == "stop"
    keys = key_set("blast furnace and coke")
    assert ("b", stem("blast"), stem("furnace")) in keys
    assert ("b", stem("furnace"), stem("coke")) not in keys


def test_inventory_keeps_recurring_facts_deterministically():
    inv = build_inventory(SOURCE, "A", EMPTY_DF)
    keys = [key for key, _, _ in inv.facts]
    assert ("b", stem("blast"), stem("furnace")) in keys
    assert ("u", stem("coke")) not in keys  # appears once
    assert inv.facts == build_inventory(SOURCE, "A", EMPTY_DF).facts
    weights = [w for _, w, _ in inv.facts]
    assert weights == sorted(weights, reverse=True)


def test_generic_facts_are_filtered_by_definition_a_only():
    generic = DocumentFrequency(10, {("u", stem("furnace")): 9})
    a = {key for key, _, _ in build_inventory(SOURCE, "A", generic).facts}
    b = {key for key, _, _ in build_inventory(SOURCE, "B", generic).facts}
    assert ("u", stem("furnace")) not in a
    assert ("u", stem("furnace")) in b


def test_coverage_is_set_based_and_ignores_padding_and_repeats():
    inv = build_inventory(SOURCE, "A", EMPTY_DF)
    summary = "The blast furnace makes iron."
    base = coverage(inv, summary)
    assert 0 < base < 1
    assert coverage(inv, summary + " " + summary) == base
    assert coverage(inv, summary + " the of and to a") == base
    assert coverage(inv, "Nothing relevant appears here.") == 0
    assert coverage(inv, SOURCE) == pytest.approx(1.0)
    assert coverage(build_inventory("", "A", EMPTY_DF), summary) is None


def test_temporal_coverage_follows_where_facts_are_covered():
    inv = build_inventory(SOURCE, "A", EMPTY_DF)
    assert temporal_coverage(inv, SOURCE) == pytest.approx(1.0)
    assert temporal_coverage(inv, "Nothing relevant appears here.") == 0


def test_unsupported_rate_flags_unseen_names_and_numbers_only():
    src = index_source(SOURCE)
    assert unsupported_rate(src, "The blast furnace makes iron.") is None  # no names or numbers
    assert unsupported_rate(src, "Engineers at Tata Steel used 1,200 tons.") == 0
    # one unseen number and one unseen mid-sentence name out of three items
    rate = unsupported_rate(src, "Engineers at Tata praised Siemens with 999 tons.")
    assert rate == pytest.approx(2 / 3)
    # sentence-initial capitalized words are not names
    assert unsupported_rate(src, "Plumbers arrived. Tata Steel used 1200 tons.") == 0


def test_auc_and_monotone_flag():
    assert auc(0.2, 0.4, 0.6) == pytest.approx(0.4)
    inv = build_inventory(SOURCE, "A", EMPTY_DF)
    views = {"S": "The blast furnace.", "M": "The blast furnace. Rolling mills shape steel.",
             "L": SOURCE}
    scored = score_views(inv, index_source(SOURCE), views)
    assert scored["monotone"] and scored["auc"] == pytest.approx(
        auc(scored["S"]["coverage"], scored["M"]["coverage"], scored["L"]["coverage"]))
    assert score_views(inv, index_source(SOURCE), {"S": "x"})["auc"] is None


def test_document_frequency_counts_documents_not_occurrences():
    df = build_document_frequency(["blast blast furnace", "furnace"])
    assert df.n_documents == 2 and df.counts[("u", stem("furnace"))] == 2
    assert df.counts[("u", stem("blast"))] == 1
