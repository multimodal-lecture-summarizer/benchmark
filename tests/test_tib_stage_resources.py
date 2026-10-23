"""Stage allocation contract and session arithmetic, using the real approved selection300/final523 files."""
import copy
import json

import pytest

from selection_fixtures import REGISTRY
from experiments.scripts.tib_stage_resources import GIB, allocated_stage, validate_stage_allocation


def load(stage):
    return json.loads((REGISTRY / f"compute_budget_{stage}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("stage", ["selection300", "final523"])
def test_approved_allocations_pass(stage):
    assert allocated_stage(load(stage), 4.0)["stage"] == stage


@pytest.mark.parametrize("field", ["total_gpu_hours", "max_sessions", "transfer_bytes", "checkpoint_bytes",
                                   "scoring_gpu_hours", "recovery_time_hours", "retry_limit_per_node"])
def test_missing_numeric_field_is_no_start(field):
    value = load("selection300")
    value[field] = None
    with pytest.raises(ValueError, match="REQUIRED_NO_START"):
        validate_stage_allocation(value)


def test_retry_state_and_floor_violations_are_refused():
    for change, text in (({"retry_limit_per_node": 1}, "retries"), ({"state": "REQUIRED_NO_START"}, "ALLOCATED"),
                         ({"minimum_local_free_bytes": 8 * GIB}, "32GiB"), ({"session_wall_hours": 12}, "11.5h"),
                         ({"profile_ids": ["lead3", "lexrank", "bart", "qwen3"]}, "four approved")):
        value = copy.deepcopy(load("selection300"))
        value.update(change)
        with pytest.raises(ValueError, match=text):
            validate_stage_allocation(value)


def test_requested_wall_cannot_exceed_session_grant():
    with pytest.raises(ValueError, match="session grant"):
        allocated_stage(load("selection300"), 6.0)


@pytest.mark.parametrize("stage,per_session,deadline", [("selection300", 5.0, 4.25), ("final523", 5.25, 4.4625)])
def test_session_limit_and_deadline_arithmetic(stage, per_session, deadline):
    a = load(stage)
    limit = min(a["session_wall_hours"], a["total_wall_hours"] / a["max_sessions"])
    assert limit == per_session and limit * (1 - a["session_headroom_fraction"]) == pytest.approx(deadline)
