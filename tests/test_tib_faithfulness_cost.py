import pytest

from experiments.scripts import tib_faithfulness_cost as fc
from experiments.scripts import tib_summary_constructors as build


def synthetic_rows(n_records=6):
    return [{"record_id": f"r{r}", "group": group, "summary": "x", "source": "y"}
            for r in range(n_records) for group in fc.ALL_GROUPS]


def good_scores(rows, bad=("offtopic", "corrupted")):
    return [0.2 if row["group"] in bad else 0.9 - 0.01 * (i % 5) for i, row in enumerate(rows)]


def test_known_group_and_corruption_checks_pass_for_a_separating_metric():
    rows = synthetic_rows()
    scores = good_scores(rows)
    assert fc.known_group_auroc(rows, scores) == pytest.approx(1.0)
    assert fc.corruption_share(rows, scores) == 1.0


def test_constant_metric_fails_both_checks():
    rows = synthetic_rows()
    scores = [0.5] * len(rows)
    assert fc.known_group_auroc(rows, scores) == pytest.approx(0.5)
    assert fc.corruption_share(rows, scores) == 0.0


def test_missing_scores_are_ignored_and_can_make_checks_unavailable():
    rows = synthetic_rows()
    assert fc.known_group_auroc(rows, [None] * len(rows)) is None
    assert fc.corruption_share(rows, [None] * len(rows)) is None


def test_analyze_reports_admission_cross_family_and_projection():
    rows = synthetic_rows()
    families = {"A": good_scores(rows), "B": [s * 0.5 + 0.1 for s in good_scores(rows)],
                "C": [0.5] * len(rows)}
    result = fc.analyze(rows, families, fc.load_criteria(), {"A": {"seconds_per_summary": 0.36}})
    assert result["admissible_pending_cost_approval"] == ["A", "B"]
    assert result["per_family"]["A"]["cost"]["projected_gpu_hours"] == pytest.approx(0.36 * 12000 / 3600)
    assert result["G3_cross_family"]["pairwise_spearman"]["A|B"] == pytest.approx(1.0)


def test_single_family_has_no_cross_family_verdict():
    rows = synthetic_rows()
    assert fc.analyze(rows, {"A": good_scores(rows)}, fc.load_criteria())["G3_cross_family"]["pass"] is None


def sample_records():
    texts = [" ".join(f"Furnace {i} makes steel at plant {k}. Rolling mills shape steel number {i}." for i in range(80))
             for k in range(3)]
    return [{"id": f"id{k}", "text": t, "words": len(t.split()), "tertile": "short"} for k, t in enumerate(texts)]


def test_build_rows_makes_five_groups_per_record_without_references():
    sample = sample_records()
    rows = fc.build_rows(sample[:2], sample, 120, 1)
    assert len(rows) == 2 * len(fc.ALL_GROUPS)
    assert {r["group"] for r in rows} == set(fc.ALL_GROUPS)
    lead = {r["record_id"]: r["summary"] for r in rows if r["group"] == "lead"}
    corrupted = {r["record_id"]: r["summary"] for r in rows if r["group"] == "corrupted"}
    assert all(corrupted[k].startswith(lead[k]) and len(corrupted[k]) > len(lead[k]) for k in lead)


def test_sampling_is_deterministic_and_stratified():
    records = [{"id": f"r{i}", "words": w, "text": "t"} for i, w in enumerate([1500, 2000, 4000, 5000, 7000, 9000] * 4)]
    first = build.draw_sample(records, 2)
    assert first == build.draw_sample(records, 2)
    assert sorted({r["tertile"] for r in first}) == ["long", "medium", "short"]
    assert len(first) == 6


def test_family_loader_failure_is_reported_not_substituted(monkeypatch):
    monkeypatch.setitem(fc.LOADERS, "Broken", lambda: (_ for _ in ()).throw(ImportError("no module")))
    available, errors = fc.load_families(["Broken"])
    assert not available and "ImportError" in errors["Broken"]
