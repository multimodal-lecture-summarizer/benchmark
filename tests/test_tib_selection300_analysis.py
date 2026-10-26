"""Tier A/B rule engine on synthetic scores (300 IDs x 4 profiles); hand-computed boundary cases, no real scores."""
import copy
import json
import random
import shutil

import pytest

from experiments.scripts import tib_selection300_analysis as engine

STRATA = engine.STRATA
QUOTAS = {"short": 100, "medium": 90, "long": 110}
IDS = [f"{s}:{n:03d}" for s in STRATA for n in range(QUOTAS[s])]
STRATUM = {i: i.split(":")[0] for i in IDS}
CONTRACT = {"selection_ids": IDS, "source_strata": STRATUM, "quotas": QUOTAS}
RULES = json.loads((engine.BINDING / "admission_rules_v2.json").read_text(encoding="utf-8"))
DECL = json.loads((engine.ANALYSIS / "analysis_declarations_261024_v1.json").read_text(encoding="utf-8"))
PROFILES_DOC = json.loads((engine.BINDING / "selection300_profiles_v2.json").read_text(encoding="utf-8"))


def flat(value):
    return dict.fromkeys(STRATA, value)


def build_rows(scores, failures=None, no_rouge=None):
    """scores: profile -> {stratum: value}; failures: profile -> set of IDs not generated; no_rouge: (profile, id) pairs."""
    failures, no_rouge, rows = failures or {}, no_rouge or set(), []
    for profile in engine.PROFILES:
        for i in IDS:
            base = {"record_id": i, "profile_id": profile, "source_stratum": STRATUM[i]}
            if i in failures.get(profile, ()):
                rows.append({**base, "scoring_status": "not_scoreable_generation_failed", "metrics": {"rougeL_f1": None},
                             "failures": {"record": "x"}})
            else:
                value = None if (profile, i) in no_rouge else scores[profile][STRATUM[i]]
                rows.append({**base, "scoring_status": "completed", "metrics": {"rougeL_f1": value}, "failures": {}})
    return rows


def run(scores, rows=None, rules=RULES, profiles_doc=PROFILES_DOC, **kw):
    rows = rows if rows is not None else build_rows(scores, **kw)
    return engine.apply_rule(rows, CONTRACT, rules, DECL, profiles_doc)


def gate(result, name):
    return next(g for g in result["gates"] if g["gate"].startswith(name))


def scores(bart=0.75, led=0.5, lexrank=0.3, lead3=0.2):
    return {"bart": flat(bart), "led": flat(led), "lexrank": flat(lexrank), "lead3": flat(lead3)}


def test_clear_leader_is_selected():
    result = run(scores())
    assert result["label"] == "selected" and result["selected_profile"] == "bart"
    assert result["selected_profile_id"] == "bart-control" and result["stopped_at"] is None
    assert all(g["passed"] for g in result["gates"])


def test_margin_exactly_on_threshold_passes_including_float_artefact():
    # 0.75 - 0.74 and 0.3 - 0.29 are not exactly 0.01 in float64; both must pass.
    assert run(scores(bart=0.75, led=0.74))["label"] == "selected"
    assert run(scores(bart=0.3, led=0.29, lexrank=0.1, lead3=0.1))["label"] == "selected"


def test_margin_just_below_threshold_fails():
    result = run(scores(bart=0.75, led=0.74000001))
    assert result["label"] == "no_selection" and result["stopped_at"] == "5_leader_margin"
    assert gate(result, "5")["deltas_vs_rivals"]["led"] == pytest.approx(0.00999999)


def test_leader_must_beat_every_rival():
    result = run(scores(bart=0.75, led=0.5, lexrank=0.745))
    assert result["label"] == "no_selection" and gate(result, "5")["passed"] is False


def test_stratum_reversal_is_no_selection():
    s = scores()
    s["bart"] = {"short": 0.3, "medium": 0.6, "long": 0.6}
    s["led"] = flat(0.4)
    result = run(s)
    assert result["label"] == "no_selection" and gate(result, "6")["passed"] is False
    assert gate(result, "6")["deltas"]["led"]["short"] == pytest.approx(-0.1)


def test_zero_stratum_delta_is_not_a_reversal():
    s = scores()
    s["bart"] = {"short": 0.4, "medium": 0.6, "long": 0.6}
    s["led"] = flat(0.4)
    s["lexrank"] = flat(0.1)
    result = run(s)
    assert gate(result, "6")["passed"] is True and result["label"] == "selected"


def test_stratum_without_members_is_not_considered():
    quotas = {"short": 150, "medium": 150, "long": 0}
    ids = [f"{s}:{n:03d}" for s in ("short", "medium") for n in range(150)]
    contract = {"selection_ids": ids, "source_strata": {i: i.split(":")[0] for i in ids}, "quotas": quotas}
    sc = scores()
    rows = []
    for profile in engine.PROFILES:
        for i in ids:
            rows.append({"record_id": i, "profile_id": profile, "source_stratum": i.split(":")[0],
                         "scoring_status": "completed", "metrics": {"rougeL_f1": sc[profile][i.split(":")[0]]}, "failures": {}})
    result = engine.apply_rule(rows, contract, RULES, DECL, PROFILES_DOC)
    assert result["label"] == "selected" and gate(result, "6")["strata_considered"] == ["short", "medium"]


def test_lead3_guard_negative_in_a_stratum_fails():
    s = scores()
    s["bart"] = {"short": 0.3, "medium": 0.6, "long": 0.6}
    s["led"] = flat(0.1)
    s["lexrank"] = flat(0.1)
    s["lead3"] = {"short": 0.5, "medium": 0.2, "long": 0.2}
    result = run(s)
    assert gate(result, "6")["passed"] is True
    assert gate(result, "7")["passed"] is False and result["label"] == "no_selection"
    assert gate(result, "7")["delta_vs_lead3"]["short"] == pytest.approx(-0.2)


def test_lead3_guard_exactly_zero_passes():
    result = run(scores(bart=0.75, led=0.5, lexrank=0.3, lead3=0.75))
    assert gate(result, "7")["passed"] is True and result["label"] == "selected"


def test_exact_tie_goes_by_priority_then_is_no_selection_by_margin():
    result = run(scores(bart=0.6, led=0.6, lexrank=0.1))
    tie = gate(result, "8")
    assert tie["leader"] == "bart" and tie["tied_with"] == ["led"]
    assert result["label"] == "no_selection" and gate(result, "5")["passed"] is False


def test_tie_priority_follows_frozen_order_lexrank_before_led():
    result = run(scores(bart=0.1, led=0.6, lexrank=0.6))
    assert gate(result, "5")["leader"] == "lexrank"


def test_fewer_than_two_families_is_no_selection():
    bad = {"lexrank": set(IDS[:60]), "led": set(IDS[:60])}
    result = run(scores(), failures=bad)
    assert result["label"] == "no_selection" and result["stopped_at"] == "3_tier_a_representatives"
    assert gate(result, "3")["admitted"] == ["bart"]


def test_one_failing_family_does_not_void_the_other_two():
    result = run(scores(), failures={"lexrank": set(IDS[:60])})
    assert gate(result, "3")["admitted"] == ["bart", "led"] and result["label"] == "selected"
    assert gate(result, "3")["by_family"]["lexrank"]["representative"] is False


def test_partial_run_is_no_selection():
    rows = build_rows(scores())
    rows = [r for r in rows if not (r["profile_id"] == "led" and r["record_id"] in IDS[-30:])]
    result = run(None, rows=rows)
    assert result["label"] == "no_selection" and result["stopped_at"] == "1_complete_scoring_run"
    assert gate(result, "1")["missing_cells"] == 30 and len(result["gates"]) == 1


def test_control_below_floors_is_no_selection():
    result = run(scores(), failures={"lead3": set(IDS[:30])})
    assert result["label"] == "no_selection" and result["stopped_at"] == "2_control_config_floors"


def test_c_between_below_floor_when_failures_are_disjoint():
    failures = {}
    for k, profile in enumerate(engine.PROFILES):
        picks = []
        for s in STRATA:
            members = [x for x in IDS if STRATUM[x] == s]
            picks += members[k * 5:k * 5 + 4 + (s == "long")]
        failures[profile] = set(picks)
    result = run(scores(), failures=failures)
    assert gate(result, "3")["passed"] is True
    assert result["label"] == "no_selection" and result["stopped_at"] == "4_c_between_common_floors"
    assert gate(result, "4")["n"] < 270


def test_missing_rouge_on_one_id_shrinks_c_between():
    full = run(scores())
    short = run(scores(), no_rouge={("bart", IDS[0])})
    assert gate(full, "4")["n"] == 300 and gate(short, "4")["n"] == 299
    assert gate(full, "4")["members_sha256"] != gate(short, "4")["members_sha256"]


def test_row_order_does_not_change_result():
    rows = build_rows(scores(bart=0.75, led=0.74))
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    assert json.dumps(run(None, rows=rows), sort_keys=True) == json.dumps(run(None, rows=shuffled), sort_keys=True)


def test_wrong_profile_name_mapping_is_an_error():
    doc = copy.deepcopy(PROFILES_DOC)
    next(p for p in doc["profiles"] if p["candidate_id"] == "bart")["profile_id"] = "bart"
    with pytest.raises(ValueError, match="mapping"):
        run(scores(), profiles_doc=doc)
    doc = copy.deepcopy(PROFILES_DOC)
    doc["config_priority_for_exact_ties"][2] = "bart"
    with pytest.raises(ValueError, match="priority"):
        run(scores(), profiles_doc=doc)


def test_priority_order_matches_frozen_file():
    assert engine.priority_order(PROFILES_DOC) == ["lead3", "lexrank", "bart", "led"]


def test_rules_differing_from_the_declaration_are_refused():
    changed = copy.deepcopy(RULES)
    changed["tier_b"]["leader_margin_rouge_l_min"] = 0.02
    with pytest.raises(ValueError, match="margin"):
        run(scores(), rules=changed)
    changed = copy.deepcopy(RULES)
    changed["ratified"] = False
    with pytest.raises(ValueError, match="ratified"):
        run(scores(), rules=changed)


def test_malformed_rows_are_input_errors():
    rows = build_rows(scores())
    with pytest.raises(ValueError, match="duplicate"):
        run(None, rows=rows + [rows[0]])
    with pytest.raises(ValueError, match="outside"):
        run(None, rows=rows + [{**rows[0], "record_id": "other:1"}])
    bad = copy.deepcopy(rows)
    bad[0]["source_stratum"] = "long"
    with pytest.raises(ValueError, match="stratum"):
        run(None, rows=bad)


def test_load_inputs_refuses_a_changed_bound_file(tmp_path):
    metrics = tmp_path / "metrics.jsonl"
    metrics.write_text("", encoding="utf-8")
    paths = dict(
        declarations_path=engine.ANALYSIS / "analysis_declarations_261024_v1.json",
        rules_path=engine.BINDING / "admission_rules_v2.json", profiles_path=engine.BINDING / "selection300_profiles_v2.json",
        decisions_path=engine.BINDING / "decisions_261023_v1.json", contract_path=engine.SCORING / "scoring_contract.json",
        outcome_path=engine.SCORING / "selection300_scoring_outcome.json", metrics_path=metrics)
    assert engine.load_inputs(**paths)["rules"]["rules_id"] == engine.RULES_ID
    tampered = tmp_path / "admission_rules_v2.json"
    shutil.copy(paths["rules_path"], tampered)
    tampered.write_text(tampered.read_text(encoding="utf-8").replace('"ratified": true', '"ratified": false'), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        engine.load_inputs(**{**paths, "rules_path": tampered})


def test_outcome_is_text_free_and_json_serialisable():
    result = run(scores())
    text = json.dumps(result)
    assert not any(i in text for i in IDS[:5]) and result["label"] in engine.LABELS


def _fail_ids(per_stratum):
    return [i for s, k in per_stratum.items() for i in [x for x in IDS if STRATUM[x] == s][:k]]


def _lexrank_config(failures):
    return gate(run(scores(), failures={"lexrank": set(failures)}), "3")["by_family"]["lexrank"]["config_floors"]


def test_config_overall_floor_boundary_285_of_300():
    ok = _lexrank_config(_fail_ids({"short": 5, "medium": 5, "long": 5}))
    assert ok["n"] == 285 and ok["overall_met"] is True
    bad = _lexrank_config(_fail_ids({"short": 6, "medium": 5, "long": 5}))
    assert bad["n"] == 284 and bad["overall_met"] is False


def test_config_stratum_floor_boundary_90_of_100():
    ok = _lexrank_config(_fail_ids({"short": 10}))
    assert ok["per_stratum_met"]["short"] is True and ok["floors_met"] is True
    bad = _lexrank_config(_fail_ids({"short": 11}))
    assert bad["per_stratum_met"]["short"] is False and bad["overall_met"] is True and bad["floors_met"] is False


def _disjoint_failures(total):
    picks = []
    for s in STRATA:
        picks += [x for x in IDS if STRATUM[x] == s][:10]
    picks += [x for x in IDS if STRATUM[x] == "short"][10:10 + total - 30]
    return {p: set(picks[k::4]) for k, p in enumerate(engine.PROFILES)}


def test_common_floor_boundary_270_of_300():
    at = run(scores(), failures=_disjoint_failures(30))
    assert gate(at, "4")["n"] == 270 and gate(at, "4")["passed"] is True and at["label"] == "selected"
    below = run(scores(), failures=_disjoint_failures(31))
    assert gate(below, "4")["n"] == 269 and gate(below, "4")["overall_met"] is False
    assert below["stopped_at"] == "4_c_between_common_floors"


def test_margin_epsilon_edges():
    assert run(scores(bart=0.75, led=0.75 - (0.01 - 5e-13)))["label"] == "selected"
    assert run(scores(bart=0.75, led=0.75 - (0.01 - 2e-12)))["label"] == "no_selection"


def test_lead3_guard_epsilon_edges():
    assert gate(run(scores(lead3=0.75 + 5e-13)), "7")["passed"] is True
    assert gate(run(scores(lead3=0.75 + 2e-12)), "7")["passed"] is False


def test_reversal_against_a_non_led_rival():
    s = scores(lead3=0.1)
    s["bart"] = {"short": 0.3, "medium": 0.7, "long": 0.7}
    s["lexrank"] = {"short": 0.4, "medium": 0.5, "long": 0.5}
    s["led"] = flat(0.1)
    g = gate(run(s), "6")
    assert g["passed"] is False
    assert g["deltas"]["lexrank"]["short"] == pytest.approx(-0.1) and g["deltas"]["led"]["short"] > 0


def test_view_table_and_lead3_note():
    rows = [{"profile_id": p, "source_stratum": "short", "record_id": f"r{n}",
             "views": {v: {"metrics": dict.fromkeys(engine.VIEW_METRICS, 0.5 + 0.1 * n), "failures": {}} for v in engine.VIEWS}}
            for p in engine.PROFILES for n in range(2)]
    cell = engine.view_table(rows)["means"]["bart|short|S"]
    assert cell["n"] == 2 and cell["rougeL_f1"] == pytest.approx(0.55)
    assert engine.view_table(rows)["means"]["bart|long|M"]["rougeL_f1"] is None
    note_row = {"profile_id": "lead3", "record_id": "valid:139", "scoring_status": "completed",
                "metrics": {"rougeL_f1": 0.3}, "failures": {}}
    assert len(engine.lead3_notes([note_row])) == 1 and engine.lead3_notes([]) == []


def test_cli_writes_result_and_receipt_once(tmp_path, monkeypatch):
    views = tmp_path / "v.jsonl"
    views.write_text("", encoding="utf-8")
    metrics = tmp_path / "m.jsonl"
    metrics.write_text("", encoding="utf-8")
    out = tmp_path / "result.json"
    inputs = {"declarations": DECL, "rules": RULES, "profiles_doc": PROFILES_DOC, "contract": CONTRACT, "rows": build_rows(scores())}
    monkeypatch.setattr(engine, "load_inputs", lambda *a, **k: inputs)
    argv = ["x", "--metrics", str(metrics), "--views", str(views), "--engine-sha256", engine.engine_sha256(), "--out", str(out)]
    monkeypatch.setattr("sys.argv", argv)
    engine.main()
    result = json.loads(out.read_text(encoding="utf-8"))
    receipt = json.loads((tmp_path / "selection300_analysis_receipt.json").read_text(encoding="utf-8"))
    assert result["label"] == "selected" and receipt["engine_sha256"] == engine.engine_sha256() and receipt["runs"] == 1
    with pytest.raises(SystemExit, match="already exists"):
        engine.main()
    monkeypatch.setattr("sys.argv", argv[:6] + ["0" * 64, "--out", str(tmp_path / "other.json")])
    with pytest.raises(SystemExit, match="engine hash"):
        engine.main()
