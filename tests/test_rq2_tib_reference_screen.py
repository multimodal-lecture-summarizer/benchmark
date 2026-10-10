"""Check screening edge cases; fixtures are not benchmark evidence."""

import ast
import json
from pathlib import Path

import pytest
import experiments.scripts.rq2_tib_reference_screen as reference_screen

from experiments.scripts.rq2_tib_reference_screen import (
    annotate_reference_pool, diverse_review_sample, screen_reference, text_hash,
)


def row(index, abstract, transcript, **metadata):
    return {"split": "valid", "source_index": index, "status": "ok",
            "abstract_words": len(abstract.split()), **metadata,
            **screen_reference({"abstract": abstract, "transcript": transcript})}


def test_full_transcript_tail_used_and_excerpt_is_from_source():
    source = "introductory material " * 400 + "quantum entanglement experiments"
    result = screen_reference({"abstract": "quantum entanglement experiments", "transcript": source})
    assert result["reference_token_coverage"] == 1
    assert result["matched_source_excerpts"][0]["start_word"] > 600
    assert result["matched_source_excerpts"][0]["text"] in source


def test_stopwords_only_and_empty_source_do_not_claim_support():
    empty = screen_reference({"abstract": "the and of", "transcript": "the and of"})
    assert empty["reference_token_coverage"] is None
    assert not empty["matched_source_excerpts"]
    missing = screen_reference({"abstract": "quantum", "transcript": ""})
    assert missing["reference_token_coverage"] == 0
    assert not missing["full_transcript_screened"]


def test_reused_abstracts_excluded_across_splits_but_bad_scan_copy_not_counted():
    first = row(1, "Quantum entanglement", "Quantum entanglement")
    second = {**row(2, " quantum   ENTANGLEMENT ", "other content"), "split": "train"}
    screened = annotate_reference_pool([first, second])
    assert all(item["reference_exclusion_reasons"] == ["reused_abstract"] for item in screened)
    failed = {**second, "status": "error"}
    assert annotate_reference_pool([first, failed])[0]["broad_pool_candidate"]


def test_cues_low_overlap_and_duplicate_transcripts_are_flags_not_exclusions():
    items = [row(1, "This course introduces chemistry", "physics experiments"),
             row(2, "quantum mechanics", "physics experiments")]
    screened = annotate_reference_pool(items)
    assert all(item["broad_pool_candidate"] for item in screened)
    assert "course_scope_cue" in screened[0]["reference_review_flags"]
    assert "low_lexical_coverage" in screened[0]["reference_review_flags"]
    assert "exact_normalized_transcript_duplicate" in screened[0]["reference_review_flags"]


def test_empty_abstract_and_duplicate_ids_fail_clearly():
    item = row(1, "", "source words")
    assert annotate_reference_pool([item])[0]["reference_exclusion_reasons"] == ["empty_abstract"]
    with pytest.raises(ValueError, match="Duplicate"):
        annotate_reference_pool([item, item])
    with pytest.raises(ValueError):
        screen_reference({}, stride_words=0)


def test_shared_prefix_flags_distinct_abstracts_without_excluding_them():
    prefix = " ".join(f"word{i}" for i in range(30))
    items = [row(i, prefix + " " + "tail " * 10 + str(i), "source") for i in range(3)]
    screened = annotate_reference_pool(items)
    assert all(item["broad_pool_candidate"] for item in screened)
    assert all("shared_30_word_prefix_template_cue" in item["reference_review_flags"] for item in screened)


def test_diverse_sample_deterministic_and_covers_rare_genre_without_capping_pool():
    items = [row(i, str(i), "source", genre="Conference", subject="CS", duration_minutes=30)
             for i in range(10)]
    items.append(row(99, "rare", "source", genre="Webinar", subject="Physics", duration_minutes=100))
    sample = diverse_review_sample(items, 2)
    assert sample[0]["source_index"] == 99
    assert sample == diverse_review_sample(list(reversed(items)), 2)
    assert len(items) == 11
    assert diverse_review_sample([], 100) == []
    assert text_hash("A  B") == text_hash("a b")


def test_notebook_embeds_exact_helper_and_all_cells_compile():
    root = Path(__file__).resolve().parents[1]
    helper = (root / "experiments/scripts/rq2_tib_reference_screen.py").read_text(encoding="utf-8")
    notebook = json.loads((root / "experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb").read_text(encoding="utf-8"))
    tree = ast.parse("".join(notebook["cells"][1]["source"]))
    detail = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "DETAIL_SOURCE" for target in node.targets))
    assert detail.startswith(helper)
    compile(detail, "DETAIL_SOURCE", "exec")
    assert "found[source_index].update(screen_reference(record))" in detail
    assert '"subject": str(record.get("subject")' in detail
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell-{index}", "exec")


def test_reference_appendix_tables_plots_and_decisions_execute_offline():
    """Exercise cell integration with fixtures, never save them as EDA outputs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    from collections import Counter

    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "experiments/notebooks/diagnostics/rq2-tib-all-splits-eda-colab.ipynb").read_text(encoding="utf-8"))
    items = []
    for index, abstract in enumerate(("quantum entanglement experiments", "chemical equilibrium reactions")):
        items.append({**row(index, abstract, abstract, subject="Physics", genre="Lecture",
                            duration_minutes=30), "doi": str(index), "source_url": "",
                      "abstract_text": abstract, "abstract_preview": abstract,
                      "transcript_words": 3})
    namespace = {"pd": pd, "plt": plt, "Counter": Counter, "display": lambda *args: None,
                 "Markdown": lambda value: value, "show_figure": lambda fig: plt.close(fig),
                 "detail_ns": vars(reference_screen), "details": items,
                 "detail_df": pd.DataFrame(items), "splits": ["train", "valid", "test"],
                 "cohort": {"source_count": 2, "usable_count": 2},
                 "coverage": {"structural_eda_complete": True}}
    for index in (12, 13, 15, 17):
        exec(compile("".join(notebook["cells"][index]["source"]), f"cell-{index}", "exec"), namespace)
    assert len(namespace["benchmark_candidate_ids"]) == 2
    assert namespace["benchmark_decision_df"]["manual_review_status"].eq("not_reviewed").all()
