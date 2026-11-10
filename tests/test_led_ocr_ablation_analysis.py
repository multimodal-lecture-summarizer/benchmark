import json
import shutil
from pathlib import Path

import pytest

from experiments.scripts import led_ocr_ablation_analysis as an
from experiments.scripts import led_ocr_ablation_freeze as freeze

PROTOCOL = Path(__file__).resolve().parents[1] / "experiments/registry/protocols" / freeze.PROTOCOL_ID
RULES = freeze.DECISION_RULES


def iv(mean, low, high):
    return {"mean": mean, "low": low, "high": high}


def test_decision_table():
    ok = iv(0.0, -0.01, 0.01)
    assert an.decide(iv(0.02, 0.005, 0.03), ok, 40, RULES)["label"] == "ocr_helps_summary"
    assert an.decide(iv(0.02, 0.005, 0.03), iv(-0.04, -0.06, -0.01), 40, RULES)["label"] == "ocr_hurts_summary"
    assert an.decide(iv(-0.02, -0.03, -0.005), ok, 40, RULES)["label"] == "ocr_hurts_summary"
    assert an.decide(iv(0.02, -0.001, 0.04), ok, 40, RULES)["label"] == "no_difference"
    assert an.decide(iv(0.005, 0.001, 0.01), ok, 40, RULES)["label"] == "no_difference"  # CI above 0 but under margin
    assert an.decide(iv(0.5, 0.4, 0.6), ok, 31, RULES)["label"] == "no_selection"


def test_helps_needs_guard_within_margin_even_if_guard_interval_straddles_zero():
    guard = iv(-0.04, -0.07, 0.01)  # mean worse than margin but interval touches zero
    assert an.decide(iv(0.02, 0.005, 0.03), guard, 40, RULES)["label"] == "no_difference"


def test_bootstrap_is_deterministic_and_brackets_mean():
    data = {"a": [0.01, 0.02, 0.03, 0.0], "b": [0.02, 0.04]}
    one = an.stratified_bootstrap(data, 2000, 7, 0.95)
    assert one == an.stratified_bootstrap(data, 2000, 7, 0.95)
    assert one["low"] <= one["mean"] <= one["high"] and one["n"] == 6
    assert an.stratified_bootstrap({"a": []}, 10, 1, 0.95)["n"] == 0


def row(vid, arm, rouge, mc, stratum="S1"):
    return {"id": vid, "stratum": stratum, "arm": arm, "rougeL_f1_at_350": rouge,
            "minicheck_evidence_full": {"mean_prob": mc} if mc is not None else None}


def test_pairs_keep_every_video_and_state_the_reason():
    ids = {"v1": "S1", "v2": "S1", "v3": "S1"}
    scores = [row("v1", "A", 0.2, 0.5), row("v1", "D", 0.25, 0.55), row("v2", "A", 0.2, 0.5), row("v2", "D", 0.3, None)]
    cells = [{"id": "v3", "arm": "A", "status": "error"}]
    pairs = an.build_pairs(ids, scores, cells)
    assert [p["comparable"] for p in pairs] == [True, False, False]
    assert pairs[0]["delta"][an.PRIMARY] == pytest.approx(0.05)
    assert "metric missing" in pairs[1]["reason"] and "not scored" in pairs[2]["reason"]


def test_frozen_files_verify_and_tampering_is_detected(tmp_path):
    assert an.check_frozen(PROTOCOL)["primary"]["margin"] == 0.01
    copy = tmp_path / "p"
    shutil.copytree(PROTOCOL, copy)
    rules = json.loads((copy / "decision_rules.json").read_text(encoding="utf-8"))
    rules["primary"]["margin"] = 0.0
    (copy / "decision_rules.json").write_text(json.dumps(rules), encoding="utf-8")
    with pytest.raises(ValueError):
        an.check_frozen(copy)


def test_full_pass_labels_and_refuses_second_run(tmp_path):
    cohort = json.loads((PROTOCOL / "cohort.json").read_text(encoding="utf-8"))
    scores, cells = [], []
    for i, video in enumerate(cohort["videos"]):
        base = 0.2 + 0.001 * (i % 5)
        scores += [row(video["id"], "A", base, 0.6, video["stratum"]), row(video["id"], "D", base + 0.03, 0.6, video["stratum"])]
        for arm in ("A", "D"):
            cells.append({"id": video["id"], "arm": arm, "status": "ok", "model_used": "LED + OCR" if arm == "D" else "LED",
                          "generation_seconds": 1.0})
    for s in scores:
        s.update(word_count=100, bertscore_f1=0.8, rougeL_f1_at_120=0.2, minicheck_evidence_transcript={"mean_prob": 0.5})
    result = an.analyze(PROTOCOL, scores, cells, [{"id": "x", "segmenter": "slide"}])
    assert result["comparable_pairs"] == 40 and result["decision"]["label"] == "ocr_helps_summary"
    assert result["descriptive_only"]["ocr_not_in_input_videos"] == []
