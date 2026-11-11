import pytest

from experiments.scripts import led_ocr_ablation_generate as gen
from experiments.scripts import led_ocr_ablation_score as sc

VIDEO = {"id": "10.5446/1", "stratum": "S1_cs_talk_scored"}
INPUTS = {"_sha256": "h", "data": {"utterances": [{"text": " one two "}, {"text": ""}, {"text": "three"}],
                                   "keyframes": [], "chapters": []}}


def merge(utterances, keyframes):
    return "one Slide: Gamma delta. two three", {"transcript_words": 3, "ocr_words": 3, "slides_used": 1}


def make_led(method="led", model="LED (x, map-reduce)", summary="Hello there."):
    def led(*args):
        return {"summary_method": method, "model_used": model, "summary": summary} if method else None
    return led


def run(arm, led, match=None):
    flags, observed = [], {}

    def watching(*args):
        observed["match"] = match
        return led(*args)

    row, private = gen.generate_cell(VIDEO, arm, INPUTS, watching, flags.append, merge, [2], observed)
    return row, private, flags


def test_arm_a_source_is_plain_transcript_and_flag_off():
    row, private, flags = run("A", make_led())
    assert flags == [False]
    assert private["source_text"] == "one two three"
    assert row["source_sha256"] == gen.sha256_text("one two three") and row["ocr_words"] == 0


def test_arm_d_source_is_merged_and_flag_on():
    row, private, flags = run("D", make_led(model="LED (x, map-reduce + OCR)"))
    assert flags == [True] and "Slide:" in private["source_text"] and row["ocr_words"] == 3


def test_invalid_cells_become_error_rows():
    assert run("A", make_led(method=None))[0]["status"] == "error"
    assert run("A", make_led(method="llm"))[0]["error"] == "ValueError"
    row = run("A", make_led(model="LED (x, + OCR)"))[0]
    assert row["status"] == "error" and "arm_a_contains_ocr" in row["detail"]
    assert run("D", make_led(model="LED (x, + OCR)"))[0]["status"] == "ok"


def test_source_check_flags_mismatched_inputs():
    a = {"id": "v", "arm": "A", "input_sha256": "1", "source_sha256": "s", "ocr_words": 0}
    d = {"id": "v", "arm": "D", "input_sha256": "2", "source_sha256": "s", "ocr_words": 0}
    assert gen.source_check([a, d]) == ["v: arms read different inputs"]
    assert gen.source_check([a]) == ["v: missing arm ['D']"]


def test_slide_terms_and_coverage():
    terms = sc.slide_terms("one Slide: Gamma delta. two three", "one two three")
    assert terms == {"gamma", "delta"}
    assert sc.term_coverage(terms, "The gamma result") == 0.5
    assert sc.term_coverage(set(), "anything") is None


def scorers(fail=None):
    def claims(evidence, sentences):
        return [0.9 if "good" in s else 0.2 for s in sentences]

    def bert(hyp, ref):
        if fail == "bert":
            raise RuntimeError("x")
        return 0.7

    return {"rouge": lambda ref, hyp: 0.3, "bert": bert, "claims": claims, "split": lambda t: [s for s in t.split(". ") if s]}


def test_score_cell_isolated_failures_are_null_not_zero():
    cell = {"id": "v", "stratum": "S1", "arm": "D"}
    private = {"summary_text": "good one. bad one"}
    row = sc.score_cell(cell, private, "ref", "ev Slide: Gamma", "ev", scorers(fail="bert"))
    assert row["bertscore_f1"] is None and row["errors"]["bertscore_f1"] == "RuntimeError"
    assert row["rougeL_f1_at_350"] == 0.3
    assert row["minicheck_evidence_full"]["mean_prob"] == pytest.approx(0.55)
    assert row["minicheck_evidence_full"]["flagged_share"] == 0.5


def test_minicheck_rejects_bad_probabilities():
    with pytest.raises(ValueError):
        sc.minicheck_stats(["a"], "e", lambda e, s: [1.5])


def test_source_mismatch_and_merge_failure_become_error_cells():
    assert "source_mismatch" in run("A", make_led(), match=False)[0]["detail"]
    assert run("A", make_led(), match=True)[0]["source_observed_match"] is True
    flags = []
    row, _ = gen.generate_cell(VIDEO, "D", INPUTS, make_led(), flags.append, lambda u, k: 1 / 0, [0])
    assert row["status"] == "error" and flags == []


def test_arm_d_ocr_flag_disagreement_is_an_error():
    assert "ocr_flag_inconsistent" in run("D", make_led(model="LED (x, map-reduce)"))[0]["detail"]


def test_doi_normalization_matches_dataset_format():
    assert sc.normalize_doi("10.5446/18349 (DOI)") == "10.5446/18349"
    assert sc.normalize_doi(None) == ""


def test_segment_evidence_splits_runs_without_full_stops():
    pytest.importorskip("nltk")
    import nltk

    try:
        nltk.data.find("tokenizers/punkt_tab")
    except LookupError:
        nltk.download("punkt_tab", quiet=True)
    run_on = " ".join(f"w{i}" for i in range(150))  # no sentence boundary at all
    passages = sc.segment_evidence(run_on, max_words=60).split("\n")
    assert [len(p.split()) for p in passages] == [60, 60, 30]
    assert sc.segment_evidence("One. Two three.", max_words=60) == "One.\nTwo three."


def test_slide_text_is_recovered_from_the_interleaved_source():
    texts = ["one two", "three", "four"]
    source = "one two Slide: Alpha beta. three Slide: Gamma. four"
    assert sc.slide_text_from(source, texts) == "Slide: Alpha beta.\nSlide: Gamma."
    assert sc.slide_text_from("one two three four", texts) == ""
    assert sc.slide_text_from("one two four", texts) is None  # utterance missing: no guess
    assert sc.slide_text_from(source + " Slide: Tail.", texts).endswith("Slide: Tail.")


def test_union_never_scores_below_either_source_and_ignores_empty_sources():
    def claims(evidence, sentences):
        return [0.9 if "gamma" in evidence else 0.2 for _ in sentences]

    both = sc.minicheck_union(["s1", "s2"], ["plain speech", "Slide: gamma"], claims)
    assert both["mean_prob"] == pytest.approx(0.9) and both["sources"] == 2
    only = sc.minicheck_union(["s1"], ["plain speech", "   "], claims)
    assert only["mean_prob"] == pytest.approx(0.2) and only["sources"] == 1
    with pytest.raises(ValueError):
        sc.minicheck_union(["s1"], ["", " "], claims)


def test_score_cell_marks_guard_null_when_slide_alignment_failed():
    cell = {"id": "v", "stratum": "S1", "arm": "D"}
    row = sc.score_cell(cell, {"summary_text": "good one. bad one"}, "ref", "ev", "ev", scorers(), slide_text=None)
    assert row["minicheck_evidence_full"] is None and row["errors"]["minicheck_evidence_full"] == "LookupError"
