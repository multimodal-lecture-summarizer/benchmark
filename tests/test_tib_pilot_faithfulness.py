import json
import zipfile

import pytest

from experiments.scripts import tib_pilot_faithfulness as pf

SOURCE = "Source text about steel."


def sentences(n, prefix="Claim"):
    return " ".join(f"{prefix} number {i} has some words in it." for i in range(n))


def fake_scorer(calls):
    def score(source, claims):
        calls.append(list(claims))
        return [0.9 if "good" in c or "Claim" in c else 0.1 for c in claims]
    return score


def make_zip(path, records):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("package/pilot_sources.jsonl", "\n".join(
            json.dumps({"record_id": rid, "source_normalized": SOURCE, "source_stratum": "short"}) for rid in ("r1", "r2")))
        archive.writestr("pilot/bart/candidate_receipt.json", json.dumps({"records": records}))
        archive.writestr("pilot/lead3/candidate_receipt.json", json.dumps({"records": {}}))


def test_each_distinct_sentence_is_scored_once_and_views_derive_from_it():
    calls = []
    row = {"candidate": "bart", "record_id": "r1", "stratum": "short", "status": "completed",
           "source": SOURCE, "raw": sentences(60)}
    scored = pf.score_row(row, fake_scorer(calls))
    assert len(calls) == 1 and len(calls[0]) == scored["distinct_sentences"]
    counts = [scored["views"][n]["sentences"] for n in pf.VIEW_NAMES]
    assert counts == sorted(counts) and counts[0] < counts[-1]
    assert all(v["mean_prob"] == pytest.approx(0.9) and v["flagged_share"] == 0 for v in scored["views"].values())


def test_view_score_is_the_mean_of_its_sentence_scores():
    raw = " ".join(["Claim one here today.", "Bad item two here now."] * 30)
    scored = pf.score_row({"candidate": "c", "record_id": "r", "stratum": "short", "status": "completed",
                           "source": SOURCE, "raw": raw}, fake_scorer([]))
    # alternating 0.9 / 0.1 sentences give a mean of 0.5 and half of the sentences flagged
    for view in scored["views"].values():
        assert view["mean_prob"] == pytest.approx(0.5, abs=0.05)
        assert view["flagged_share"] == pytest.approx(0.5, abs=0.1)


def test_collect_rows_skips_failed_and_missing_records(tmp_path):
    zip_path = tmp_path / "evidence.zip"
    make_zip(zip_path, {
        "r1": {"status": "completed", "result": {"raw_final": sentences(10)}},
        "r2": {"status": "failed", "error": "boom"},
    })
    rows, skipped = pf.collect_rows(zip_path)
    assert [(r["candidate"], r["record_id"]) for r in rows] == [("bart", "r1")]
    assert {(s["candidate"], s["record_id"], s["status"]) for s in skipped} >= {
        ("bart", "r2", "failed"), ("lead3", "r1", "missing"), ("lead3", "r2", "missing")}


def test_checkpoint_resume_does_not_rescore_and_errors_stay_errors(tmp_path):
    rows = [{"candidate": "bart", "record_id": "r1", "stratum": "short", "status": "completed",
             "source": SOURCE, "raw": sentences(10)},
            {"candidate": "bart", "record_id": "r2", "stratum": "short", "status": "completed",
             "source": SOURCE, "raw": "   "}]
    checkpoint = tmp_path / "scores.jsonl"
    first_calls = []
    first = pf.score_rows(rows, fake_scorer(first_calls), checkpoint)
    assert "views" in first[0] and "error" in first[1] and "views" not in first[1]
    second_calls = []
    pf.score_rows(rows, fake_scorer(second_calls), checkpoint)
    assert second_calls == []  # both rows came from the checkpoint


def test_sentence_detail_goes_to_the_private_file_and_never_into_the_summary(tmp_path):
    raw = " ".join(["Claim one here today.", "Bad item two here now."] * 30)
    rows = [{"candidate": "bart", "record_id": "r1", "stratum": "short", "status": "completed",
             "source": SOURCE, "raw": raw},
            {"candidate": "bart", "record_id": "r2", "stratum": "short", "status": "completed",
             "source": SOURCE, "raw": "   "}]
    detail_path = tmp_path / "detail.jsonl"
    results = pf.score_rows(rows, fake_scorer([]), tmp_path / "scores.jsonl", detail_path=detail_path)
    details = [json.loads(line) for line in detail_path.read_text(encoding="utf-8").splitlines()]
    assert [d["record_id"] for d in details] == ["r1"]  # the failed row has no detail
    by_text = {s["text"]: s for s in details[0]["sentences"]}
    assert by_text["Claim one here today."]["prob"] == pytest.approx(0.9)
    assert by_text["Bad item two here now."]["prob"] == pytest.approx(0.1)
    assert all(s["in_views"] for s in details[0]["sentences"])
    assert "Claim one here today." not in json.dumps(results)
    assert "Claim one here today." not in (tmp_path / "scores.jsonl").read_text(encoding="utf-8")


def test_detail_and_summary_agree_with_score_row():
    row = {"candidate": "c", "record_id": "r", "stratum": "short", "status": "completed",
           "source": SOURCE, "raw": sentences(60)}
    summary, detail = pf.score_row_detailed(row, fake_scorer([]))
    assert summary == pf.score_row(row, fake_scorer([]))
    assert len(detail["sentences"]) == summary["distinct_sentences"]


def test_max_abs_view_diff_reports_drift_and_missing_rows():
    def entry(rid, p):
        return {"candidate": "c", "record_id": rid, "views": {v: {"mean_prob": p} for v in pf.VIEW_NAMES}}
    drift = pf.max_abs_view_diff([entry("a", 0.50), entry("b", 0.70), entry("new", 0.1)],
                                 [entry("a", 0.52), entry("b", 0.70)])
    assert drift["compared_views"] == 6
    assert drift["max_abs_diff"] == pytest.approx(0.02)
    assert drift["missing_in_previous"] == [("c", "new")]


def test_summary_reports_denominators_without_ranking(tmp_path):
    zip_path = tmp_path / "evidence.zip"
    make_zip(zip_path, {"r1": {"status": "completed", "result": {"raw_final": sentences(10)}},
                        "r2": {"status": "failed"}})
    rows, skipped = pf.collect_rows(zip_path)
    table = pf.summarize(pf.score_rows(rows, fake_scorer([])), skipped)
    assert table["bart"]["scored_records"] == 1 and table["bart"]["not_scored_records"] == 1
    assert table["lead3"]["scored_records"] == 0 and table["lead3"]["views"]["M"]["mean_prob"] is None
    assert not any(key in table["bart"] for key in ("rank", "winner"))
