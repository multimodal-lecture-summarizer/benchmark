"""Projection arithmetic and timing tables of the Pilot40 scoring audit, on hand-checkable numbers."""
import math

import pytest

from experiments.scripts import tib_pilot40_scoring_audit as audit

FLAT = {s: {"mean": 1.0, "p90": 2.0, "max": 4.0} for s in audit.STRATA}


def test_describe_interpolates_percentiles():
    d = audit.describe([1.0, 2.0, 3.0, 4.0, 10.0])
    assert d["n"] == 5 and d["mean"] == 4.0 and d["p50"] == 3.0 and d["max"] == 10.0
    assert d["p90"] == pytest.approx(7.6)


def test_base_projection_matches_hand_calculation():
    out = audit.project(FLAT, 0.0)["selection300|base"]
    scoring = 1.0 * 300 * 4 / 3600
    assert out["scoring_hours"] == pytest.approx(scoring)
    work = audit.GENERATION_HOURS[("selection300", "base")] + scoring
    sessions = math.ceil(work / audit.WORK_PER_SESSION)
    assert out["sessions"] == sessions
    assert out["wall_equals_gpu_hours"] == pytest.approx(work + 0.75 * sessions + 0.5 * (sessions - 1))


def test_conservative_uses_p90_times_safety_factor():
    out = audit.project(FLAT, 0.0)["final523|conservative"]
    assert out["scoring_hours"] == pytest.approx(2.0 * 523 * 4 * 1.5 / 3600)


def test_drop_sbert_subtracts_component_and_never_goes_negative():
    sbert = {s: {"mean": 5.0, "p90": 5.0, "max": 5.0} for s in audit.STRATA}
    assert audit.project(FLAT, 0.0, sbert, drop_sbert=True)["selection300|base"]["scoring_hours"] == 0.0


def test_timing_tables_ignore_unscored_cells():
    rows = [{"profile_id": "led", "source_stratum": "long", "scoring_status": "completed", "new_scoring_wall_seconds": 3.0},
            {"profile_id": "led", "source_stratum": "long", "scoring_status": "not_attempted", "new_scoring_wall_seconds": 0.0}]
    cell, stratum = audit.timing_tables(rows)
    assert cell["led|long"]["n"] == 1 and stratum["long"]["mean"] == 3.0
