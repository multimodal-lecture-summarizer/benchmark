import hashlib
import json
import zipfile

import pytest

from experiments.scripts import tib_final523_faithfulness as ff

SOURCE = "Source text about steel."


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def summary(n, word="Claim"):
    return " ".join(f"{word} number {i} has some words in it." for i in range(n))


def cell(profile, rid, stratum="short", text=None, scoreable=True):
    text = summary(3) if text is None else text
    return {"sample_id": f"{profile}__{rid}", "record_id": rid, "profile_id": profile, "source_stratum": stratum,
            "source": SOURCE, "source_sha256": sha(SOURCE), "generation_status": "completed" if scoreable else "failed",
            "scoreable": scoreable, "failure_reason": None if scoreable else "AdapterFailure",
            "delivered_summary": text, "delivered_sha256": sha(text),
            "views": {"S": text.split(". ")[0] + ".", "M": text, "L": text}}


def make_bundle(path, cells):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("scoring_outputs.jsonl", "\n".join(json.dumps(c) for c in cells))
    return path


def fake_scorer(calls):
    def score(source, claims):
        calls.append(list(claims))
        return [0.1 if "bad" in c else 0.9 for c in claims]
    return score


def test_collect_rows_keeps_failed_cells_as_skipped_and_ignores_other_profiles(tmp_path):
    bundle = make_bundle(tmp_path / "b.zip", [cell("led", "t:1"), cell("led", "t:2", scoreable=False),
                                              cell("bart", "t:1"), cell("lead3", "t:1")])
    rows, skipped = ff.collect_rows(bundle)
    assert sorted((r["candidate"], r["record_id"]) for r in rows) == [("bart", "t:1"), ("led", "t:1")]
    assert [(s["candidate"], s["record_id"], s["failure_reason"]) for s in skipped] == [("led", "t:2", "AdapterFailure")]
    assert set(rows[0]["views"]) == set(ff.VIEW_NAMES)


def test_collect_rows_stops_on_a_text_hash_mismatch(tmp_path):
    bad = cell("led", "t:1")
    bad["delivered_summary"] += " tampered"
    with pytest.raises(ValueError, match="hash mismatch"):
        ff.collect_rows(make_bundle(tmp_path / "b.zip", [bad]))


def test_each_distinct_sentence_is_scored_once_and_views_derive_from_it():
    calls = []
    row = {"candidate": "led", "record_id": "t:1", "stratum": "short", "status": "completed", "source": SOURCE,
           "views": {"contract": "A good claim. A bad claim.", "S": "A good claim.", "M": "A good claim. A bad claim.",
                     "L": "A good claim. A bad claim."}}
    scored, detail = ff.score_row_detailed(row, fake_scorer(calls))
    assert len(calls) == 1 and len(calls[0]) == 2 == scored["distinct_sentences"]
    assert scored["views"]["S"] == {"sentences": 1, "mean_prob": 0.9, "flagged_share": 0.0}
    assert scored["views"]["contract"]["mean_prob"] == pytest.approx(0.5)
    assert scored["views"]["contract"]["flagged_share"] == 0.5
    assert "text" not in json.dumps(scored)
    assert [s["in_views"] for s in detail["sentences"]] == [["contract", "S", "M", "L"], ["contract", "M", "L"]]


def plain_rows(n):
    return [{"candidate": "led", "record_id": f"t:{i}", "stratum": "short", "status": "completed", "source": SOURCE,
             "views": {v: "A good claim." for v in ff.VIEW_NAMES}} for i in range(n)]


def test_score_rows_resumes_keeps_text_free_errors_and_retries_them(tmp_path):
    rows = plain_rows(3)
    ckpt, detail = tmp_path / "c.jsonl", tmp_path / "d.jsonl"
    calls = []
    ff.score_rows(rows[:2], fake_scorer(calls), ckpt, detail)

    def broken(source, claims):
        raise KeyError("A private summary sentence")
    results = ff.score_rows(rows, broken, ckpt, detail)
    assert len(calls) == 2  # the first two are restored, not rescored
    assert "views" in results[0] and "views" in results[1]
    assert results[2]["error"] == "KeyError" and "private" not in ckpt.read_text()
    assert len(detail.read_text().splitlines()) == 2

    retried = ff.score_rows(rows, fake_scorer(calls), ckpt, detail)
    assert len(calls) == 3 and all("views" in r for r in retried)  # only the error row is scored again


def test_score_rows_stops_after_consecutive_errors(tmp_path):
    def broken(source, claims):
        raise RuntimeError("CUDA error: device-side assert triggered")
    with pytest.raises(RuntimeError, match="3 consecutive"):
        ff.score_rows(plain_rows(5), broken, tmp_path / "c.jsonl", tmp_path / "d.jsonl", max_consecutive_errors=3)
    assert len((tmp_path / "c.jsonl").read_text().splitlines()) == 3


@pytest.mark.parametrize("returned", [[0.9], [0.9, 0.9, 0.9], [float("nan"), 0.9], [1.5, 0.2]])
def test_scorer_output_must_match_the_claims(returned):
    row = {"candidate": "led", "record_id": "t:1", "stratum": "short", "status": "completed", "source": SOURCE,
           "views": {v: "A good claim. Another claim." for v in ff.VIEW_NAMES}}
    with pytest.raises(ValueError) as caught:
        ff.score_row_detailed(row, lambda source, claims: returned)
    assert "claim" not in str(caught.value)  # the message never quotes a sentence


def test_a_half_written_last_line_is_cut_off_the_file_on_resume(tmp_path):
    ckpt, detail = tmp_path / "c.jsonl", tmp_path / "d.jsonl"
    calls = []
    ff.score_rows(plain_rows(2), fake_scorer(calls), ckpt, detail)
    ckpt.write_text(ckpt.read_text() + '{"candidate": "led", "rec')
    detail.write_text(detail.read_text() + '{"candidate": "led", "rec')
    results = ff.score_rows(plain_rows(3), fake_scorer(calls), ckpt, detail)
    assert len(calls) == 3 and all("views" in r for r in results)
    for path in (ckpt, detail):  # the third row was appended on a clean line: every line parses
        assert len([json.loads(line) for line in path.read_text().splitlines()]) == 3
    (tmp_path / "bad.jsonl").write_text('{"a": \n{"b": 1}\n')
    with pytest.raises(json.JSONDecodeError):
        ff.read_jsonl(tmp_path / "bad.jsonl")


def record(p, rid, stratum, prob, flagged=0.0):
    view = {"sentences": 2, "mean_prob": prob, "flagged_share": flagged}
    return {"candidate": p, "record_id": rid, "stratum": stratum, "status": "completed",
            "views": {n: view for n in ff.VIEW_NAMES}}


def receipt_with(led_prob, bart_prob, n=30, with_error=False):
    scores = []
    for i in range(n):
        stratum = ff.STRATA[i % 3]
        scores += [record("led", f"t:{i}", stratum, led_prob + 0.001 * (i % 5)),
                   record("bart", f"t:{i}", stratum, bart_prob)]
    if with_error:
        scores.append({"candidate": "led", "record_id": "t:err", "stratum": "short", "status": "completed", "error": "x"})
        scores.append(record("bart", "t:err", "short", 0.9))
    return {"protocol_id": ff.PROTOCOL_ID, "scores": scores,
            "skipped": [{"candidate": "led", "record_id": "t:fail", "stratum": "long"}]}


def labels(led_s, bart_s, n=12):
    out = []
    for p, k in (("led", led_s), ("bart", bart_s)):
        out += [{"candidate": p, "flagged": True, "label": "S" if i < k else "U"} for i in range(n)]
        out += [{"candidate": p, "flagged": True, "label": "N"}, {"candidate": p, "flagged": False, "label": "S"}]
    return out


def test_common_ids_need_a_scored_led_and_bart_row():
    ids = ff.common_ids(receipt_with(0.7, 0.8, with_error=True)["scores"])
    assert len(ids) == 30 and "t:err" not in ids


def needs_engine():
    # The analysis runs locally; the Colab code bundle carries only the scoring code.
    pytest.importorskip("experiments.scripts.tib_final523_analysis")


def test_analysis_labels_led_less_faithful_only_with_comparable_false_flag_rates():
    needs_engine()
    receipt = receipt_with(0.70, 0.80)
    result = ff.analyze(receipt, labels(3, 4), resamples=500, expected_c_final=30)
    primary = result["contrasts"]["contract"]["mean_prob"]
    assert primary["n"] == 30 and primary["mean"] < -0.05 and primary["high"] < 0
    assert result["interpretation"]["label"] == "led_less_faithful"
    assert result["false_flag_rates"]["led"]["n"] == 12  # N labels excluded
    assert result["descriptive"]["led"]["not_scoreable"] == 1
    assert ff.analyze(receipt, labels(12, 0), resamples=500,
                      expected_c_final=30)["interpretation"]["label"] == "no_difference_established"


def test_an_incomplete_run_gets_no_directional_label():
    needs_engine()
    with_error = ff.analyze(receipt_with(0.70, 0.80, with_error=True), labels(3, 4), resamples=500, expected_c_final=30)
    assert with_error["error_rows"] == 1 and with_error["interpretation"]["label"] == "not_evaluable"
    short = ff.analyze(receipt_with(0.70, 0.80), labels(3, 4), resamples=500)  # 30 != 519
    assert short["complete"] is False and short["interpretation"]["label"] == "not_evaluable"


def test_analysis_waits_for_the_hand_review_and_respects_the_margin():
    needs_engine()
    assert ff.analyze(receipt_with(0.70, 0.80), None, resamples=500,
                      expected_c_final=30)["interpretation"]["label"] == "pending_hand_review"
    small = ff.analyze(receipt_with(0.78, 0.80), labels(3, 4), resamples=500, expected_c_final=30)
    assert small["interpretation"]["label"] == "no_difference_established"
    assert small["interpretation"]["conditions"]["beyond_margin"] is False


def test_analysis_rejects_another_protocol():
    with pytest.raises(ValueError):
        ff.analyze({"protocol_id": "other", "scores": [], "skipped": []})


def test_latest_by_keeps_the_last_occurrence_in_first_seen_order():
    items = [{"k": "a", "v": 1}, {"k": "b", "v": 2}, {"k": "a", "v": 3}]
    assert ff.latest_by(items, "k") == [{"k": "a", "v": 3}, {"k": "b", "v": 2}]


def test_wilson_interval():
    w = ff.wilson(8, 27)
    assert w["rate"] == pytest.approx(8 / 27)
    assert w["low"] == pytest.approx(0.159, abs=0.002) and w["high"] == pytest.approx(0.484, abs=0.002)
    assert ff.wilson(0, 0)["rate"] is None


def test_review_sample_is_deterministic_and_balanced(tmp_path):
    path = tmp_path / "d.jsonl"
    lines = []
    for p in ff.PROFILES:
        for j, stratum in enumerate(ff.STRATA):
            for r in range(3):
                lines.append({"candidate": p, "record_id": f"t:{j}{r}", "stratum": stratum,
                              "sentences": [{"index": i, "text": "x", "prob": 0.1 if i % 2 else 0.9,
                                             "in_views": ["contract"]} for i in range(6)]
                              + [{"index": 9, "text": "y", "prob": 0.1, "in_views": ["S"]}]})
    path.write_text("\n".join(json.dumps(x) for x in lines + lines[:1]))
    detail = ff.load_detail(path)
    first, second = ff.draw_review_sample(detail), ff.draw_review_sample(detail)
    assert first == second and len(first) == 2 * 3 * (ff.REVIEW_FLAGGED + ff.REVIEW_UNFLAGGED)
    assert all(s["sentence_index"] != 9 for s in first)  # only contract-view sentences
    assert sum(s["flagged"] for s in first) == 2 * 3 * ff.REVIEW_FLAGGED
