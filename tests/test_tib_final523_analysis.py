"""Final523 confirmatory engine on synthetic scores (523 IDs x 4 profiles); hand-built boundary cases, no real scores."""
import copy
import json
import math

import pytest

from experiments.scripts import tib_final523_analysis as engine

STRATA = engine.STRATA
QUOTAS = {"short": 182, "medium": 172, "long": 169}
IDS = [f"test:{s}-{n:03d}" for s in STRATA for n in range(QUOTAS[s])]
STRATUM = {i: i.split(":")[1].split("-")[0] for i in IDS}
CONTRACT = {"selection_ids": IDS, "source_strata": STRATUM, "quotas": QUOTAS}
RULES = json.loads((engine.base.BINDING / "admission_rules_v2.json").read_text(encoding="utf-8"))
DECL = json.loads(engine.DECLARATION.read_text(encoding="utf-8"))
B = 400  # resamples: enough for the synthetic effects below, fast in tests


def index(i):
    return IDS.index(i)


def build(score, failures=None):
    """score(profile, id) -> ROUGE-L; failures: profile -> set of IDs whose generation failed."""
    failures, rows = failures or {}, []
    for p in engine.PROFILES:
        for i in IDS:
            base = {"record_id": i, "profile_id": p, "source_stratum": STRATUM[i]}
            if i in failures.get(p, ()):
                rows.append({**base, "scoring_status": "not_scoreable_generation_failed",
                             "metrics": {"rougeL_f1": None}, "failures": {"record": "x"}})
            else:
                rows.append({**base, "scoring_status": "completed", "failures": {},
                             "metrics": {"rougeL_f1": score(p, i), "bertscore_f1": 0.8 + 0.1 * score(p, i)}})
    return rows


def views(rows):
    out = []
    for r in rows:
        if r["scoring_status"] != "completed":
            continue
        cell = {"metrics": dict(r["metrics"]), "failures": {}}
        out.append({"record_id": r["record_id"], "profile_id": r["profile_id"], "source_stratum": r["source_stratum"],
                    "views": {"S": cell, "M": copy.deepcopy(cell), "L": copy.deepcopy(cell)}})
    return out


def spread(n, start=0):
    """n IDs taken round-robin across the three strata from offset `start` (keeps per-stratum coverage balanced)."""
    pools = [[i for i in IDS if STRATUM[i] == s] for s in STRATA]
    return {pools[k % 3][start + k // 3] for k in range(n)}


def noise(i):
    return 0.01 * math.sin(index(i))


LEVEL = {"lead3": 0.20, "lexrank": 0.18, "bart": 0.19, "led": 0.25}


def clear(p, i):
    return LEVEL[p] + noise(i)


def run(score=clear, failures=None, rows=None, declaration=DECL, rules=RULES):
    rows = rows if rows is not None else build(score, failures)
    return engine.apply_rule(rows, views(rows), CONTRACT, rules, declaration, resamples=B)


def gate(result, name):
    return next(g for g in result["gates"] if g["gate"] == name)


def test_clear_advantage_is_confirmed():
    result = run()
    assert result["label"] == "confirmed" and result["c_final_n"] == 523 and result["stopped_at"] is None
    contrasts = gate(result, "4_confirmatory_family")["contrasts"]
    assert set(contrasts) == {"led-bart", "led-lexrank"}
    assert all(c["lower_bound_above_zero"] and c["practical_margin_met"] for c in contrasts.values())


def test_one_contrast_interval_straddling_zero_is_not_confirmed():
    def score(p, i):
        # led - bart alternates +-0.05, so its mean is about 0 and its interval contains 0; led still beats lexrank
        sign = 1 if index(i) % 2 else -1
        return clear(p, i) + (0.06 + 0.05 * sign if p == "bart" else 0.0)
    result = run(score)
    c = gate(result, "4_confirmatory_family")["contrasts"]
    assert not c["led-bart"]["lower_bound_above_zero"] and c["led-lexrank"]["lower_bound_above_zero"]
    assert result["label"] == "not_confirmed"


def test_practical_margin_is_descriptive_only():
    def score(p, i):  # led beats both by 0.004 everywhere: lower bound > 0 but under the 0.01 margin
        return {"lead3": 0.19, "lexrank": 0.19, "bart": 0.19, "led": 0.194}[p] + noise(i)
    result = run(score)
    c = gate(result, "4_confirmatory_family")["contrasts"]
    assert result["label"] == "confirmed"
    assert not c["led-bart"]["practical_margin_met"] and not c["led-lexrank"]["practical_margin_met"]


def test_negative_lead3_guard_is_not_confirmed():
    def score(p, i):
        return {"lead3": 0.30, "lexrank": 0.18, "bart": 0.19, "led": 0.25}[p] + noise(i)
    result = run(score)
    guard = gate(result, "4_confirmatory_family")["lead3_guard"]
    assert guard["met"] is False and result["label"] == "not_confirmed"


def test_lead3_guard_exactly_zero_passes():
    def score(p, i):
        return {"lead3": 0.25, "lexrank": 0.18, "bart": 0.19, "led": 0.25}[p] + noise(i)
    result = run(score)
    assert gate(result, "4_confirmatory_family")["lead3_guard"]["met"] is True
    assert result["label"] == "confirmed"


def test_partial_run_is_not_evaluable_and_reads_no_scores():
    rows = [r for r in build(clear) if not (r["profile_id"] == "led" and r["record_id"] == IDS[0])]
    result = run(rows=rows)
    assert result["label"] == "not_evaluable" and result["stopped_at"] == "1_complete_run"
    assert result["descriptive"]["partial"] is True and len(result["gates"]) == 1


def test_config_floor_boundaries_for_one_profile():
    assert run(failures={"led": spread(26)})["label"] == "confirmed"  # 497/523 = 0.9503, every stratum above 0.90
    overall = run(failures={"led": spread(27)})  # 496/523 = 0.9484
    assert overall["label"] == "not_evaluable" and overall["stopped_at"] == "2_config_floors"
    medium = [i for i in IDS if STRATUM[i] == "medium"][:20]  # medium 152/172 = 0.884 while overall is 0.962
    stratum = run(failures={"led": set(medium)})
    assert stratum["label"] == "not_evaluable" and stratum["stopped_at"] == "2_config_floors"


def test_disjoint_failures_break_the_common_floor_only():
    # 26 failures per profile keep each profile above its own floors; the union is 104 IDs, C_final = 419 < 0.90 * 523
    fails = {p: spread(26, start=9 * k) for k, p in enumerate(engine.PROFILES)}
    assert len(set().union(*fails.values())) == 104
    result = run(failures=fails)
    assert result["label"] == "not_evaluable" and result["stopped_at"] == "3_common_floors"
    assert gate(result, "3_common_floors")["common"]["n"] == 419


def test_missing_led_cells_shrink_c_final_and_are_reported():
    result = run(failures={"led": set(IDS[:3])})
    assert result["label"] == "confirmed" and result["c_final_n"] == 520
    d = result["descriptive"]
    assert d["missing_cells"]["led"]["short"] == 3
    assert d["pairwise_complete_sensitivity"]["led-bart"]["n"] == 520


def test_row_order_does_not_change_result():
    rows = build(clear)
    forward = run(rows=rows)
    backward = run(rows=list(reversed(rows)))
    assert json.dumps(forward, sort_keys=True) == json.dumps(backward, sort_keys=True)


def test_result_is_text_free_json_and_deterministic():
    first, second = run(), run()
    text = json.dumps(first, allow_nan=False, sort_keys=True)
    assert text == json.dumps(second, allow_nan=False, sort_keys=True)
    assert "source_normalized" not in text and "title" not in text


def test_stratum_reversal_is_listed_but_does_not_change_the_label():
    def score(p, i):
        if p == "led" and STRATUM[i] == "long":
            return LEVEL["bart"] - 0.02 + noise(i)  # led worse than bart in the long stratum only
        return clear(p, i)
    result = run(score)
    strata = result["descriptive"]["strata"]["led-bart"]
    assert strata["long"]["reversal_against_overall"] is True and strata["short"]["reversal_against_overall"] is False
    assert result["label"] == "confirmed"


def test_other_pairs_are_exploratory_and_complete():
    pairs = run()["descriptive"]["other_pairs"]
    assert set(pairs) == {"lead3-lexrank", "lead3-bart", "lead3-led", "lexrank-bart"}
    assert all(p["label"].startswith("exploratory") for p in pairs.values())


def test_view_table_has_holm_and_identical_shares():
    d = run()["descriptive"]["views"]
    cell = d["contrasts"]["led-bart|rougeL_f1"]
    assert set(cell) == {"S", "M", "L"} and all(0 <= c["p_holm_over_three_views"] <= 1 for c in cell.values())
    assert all(v["share_metric_identical_S_M_L"] == 1.0 for v in d["identical_share"].values())


def test_holm_adjustment_hand_values():
    assert engine.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert engine.holm([0.5]) == [0.5]
    assert engine.holm([0.4, 0.5, 0.6]) == pytest.approx([1.0, 1.0, 1.0])


def test_bootstrap_is_seeded_and_brackets_a_constant_effect():
    by = {"short": [0.05] * 10, "medium": [0.05] * 10, "long": []}
    a, b = engine.bootstrap(by, resamples=200), engine.bootstrap(by, resamples=200)
    assert a == b and a["low"] == pytest.approx(0.05) and a["high"] == pytest.approx(0.05)
    assert a["p_two_sided"] == pytest.approx(2 / 201)


def test_diagnostic_cases_are_36_distinct_and_deterministic():
    rows = build(lambda p, i: clear(p, i) + (0.03 * math.cos(index(i)) if p == "led" else 0.0))
    cases = engine.diagnostic_cases(rows, set(IDS), STRATUM)
    flat = [i for s in cases.values() for part in s.values() for i in part]
    assert len(flat) == 36 and len(set(flat)) == 36
    assert all(len(cases[s][k]) == 4 for s in STRATA for k in ("most_negative", "most_positive", "random"))
    assert cases == engine.diagnostic_cases(rows, set(IDS), STRATUM)


def test_declaration_must_be_the_pinned_one():
    other = copy.deepcopy(DECL)
    other["profiles"]["leader"] = "bart"
    with pytest.raises(ValueError):
        run(declaration=other)
    other = copy.deepcopy(DECL)
    other["post_hoc"] = True
    with pytest.raises(ValueError):
        run(declaration=other)


def test_rules_must_be_the_ratified_ones():
    other = copy.deepcopy(RULES)
    other["ratified"] = False
    with pytest.raises(ValueError):
        run(rules=other)


def test_unknown_or_duplicate_rows_are_input_errors():
    rows = build(clear)
    with pytest.raises(ValueError):
        run(rows=rows + [rows[0]])
    bad = copy.deepcopy(rows)
    bad[0]["profile_id"] = "qwen"
    with pytest.raises(ValueError):
        run(rows=bad)


def test_load_inputs_refuses_a_changed_bound_file(tmp_path):
    shutil_tree = tmp_path / "protocols"
    for relative in DECL["bound_paths_relative_to_protocols_dir"].values():
        target = shutil_tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((engine.PROTOCOLS / relative).read_bytes())
    outcome, contract = tmp_path / "outcome.json", tmp_path / "contract.json"
    outcome.write_text(json.dumps({"audit_pass": True}))
    contract.write_text(json.dumps(CONTRACT))
    metrics, views_path = tmp_path / "m.jsonl", tmp_path / "v.jsonl"
    metrics.write_text("")
    views_path.write_text("")
    args = (engine.DECLARATION, engine.DECLARATION_RECEIPT, shutil_tree, contract, outcome, metrics, views_path)
    assert engine.load_inputs(*args)["declaration"]["declaration_id"] == DECL["declaration_id"]
    tampered = shutil_tree / "tib-selection300-binding-261023-v1/admission_rules_v2.json"
    tampered.write_text(tampered.read_text(encoding="utf-8") + " ")
    with pytest.raises(ValueError):
        engine.load_inputs(*args)
    tampered.write_bytes((engine.PROTOCOLS / "tib-selection300-binding-261023-v1/admission_rules_v2.json").read_bytes())
    outcome.write_text(json.dumps({"audit_pass": False}))
    with pytest.raises(ValueError):
        engine.load_inputs(*args)


def test_cli_runs_once_writes_cases_after_result_and_refuses_wrong_engine_hash(tmp_path, monkeypatch):
    rows = build(clear)
    files = {"m.jsonl": rows, "v.jsonl": views(rows)}
    for name, content in files.items():
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in content), encoding="utf-8")
    (tmp_path / "contract.json").write_text(json.dumps(CONTRACT))
    (tmp_path / "outcome.json").write_text(json.dumps({"audit_pass": True}))
    out = tmp_path / "out"

    def argv(engine_hash):
        return ["x", "--metrics", str(tmp_path / "m.jsonl"), "--views", str(tmp_path / "v.jsonl"), "--contract",
                str(tmp_path / "contract.json"), "--outcome", str(tmp_path / "outcome.json"), "--engine-sha256", engine_hash,
                "--out", str(out)]

    monkeypatch.setattr("sys.argv", argv("0" * 64))
    with pytest.raises(SystemExit):
        engine.main()
    assert not out.exists()
    monkeypatch.setattr("sys.argv", argv(engine.engine_sha256()))
    engine.main()
    result = json.loads((out / engine.RESULT_NAME).read_text(encoding="utf-8"))
    assert result["label"] == "confirmed" and result["engine_sha256"] == engine.engine_sha256()
    cases = json.loads((out / "final523_diagnostic_case_ids.json").read_text(encoding="utf-8"))
    assert sum(len(v) for s in cases.values() for v in s.values()) == 36
    with pytest.raises(SystemExit):
        engine.main()


def test_engine_receipt_pins_this_engine_and_the_declaration():
    receipt = json.loads((engine.ANALYSIS / "final523_analysis_engine_receipt.json").read_text(encoding="utf-8"))
    assert receipt["engine_sha256"] == engine.engine_sha256()
    assert receipt["declaration_sha256"] == engine.sha256_file(engine.DECLARATION)
