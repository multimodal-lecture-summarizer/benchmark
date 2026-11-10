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
