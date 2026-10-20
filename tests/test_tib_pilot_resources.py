import json
from types import SimpleNamespace

import pytest

from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_pilot_resources import ALLOCATION_FIELDS, GIB, PilotBudget, allocated


def allocation():
    result = dict.fromkeys(ALLOCATION_FIELDS, 0)
    result.update(state='ALLOCATED', total_gpu_hours=11.5, total_cpu_hours=23, total_wall_hours=11.5,
        max_sessions=2, session_wall_hours=11.5, persistent_storage_bytes=2*GIB,
        minimum_local_free_bytes=32*GIB, local_working_storage_bytes=24*GIB, transfer_bytes=16*GIB,
        checkpoint_bytes=GIB, checkpoint_flush_seconds=600, recovery_time_hours=.5,
        session_headroom_fraction=.15, scoring_gpu_hours=1.5, scoring_cpu_hours=3,
        pilot_total_profile_cap=5)
    return result


def ledger(path, a, **updates):
    value = dict(session_started_monotonic=100, boot_id='boot', cpu_seconds=10, gpu_seconds=0,
        transfer_bytes=0, checkpoint_bytes=0, checkpoint_flush_seconds=0, candidate_runs=[],
        allocation_sha256=digest(a), completed_session_wall_seconds=0, session_limit_seconds=5.75*3600,
        session_runs=[{'boot_id': 'boot'}], local_working_root='/content/work')
    value.update(updates)
    (path/'resource_ledger.json').write_text(json.dumps(value))
    return value


@pytest.mark.parametrize('field', ALLOCATION_FIELDS)
def test_every_numeric_allocation_required(field):
    value = allocation(); value[field] = None
    with pytest.raises(ValueError, match='Numeric allocation'):
        allocated(value, 11.5)


@pytest.mark.parametrize('field', ['retry_limit_per_node', 'retry_cost_reserve',
    'pilot_metric_tuning_trial_cap_per_candidate', 'pilot_feasibility_probe_cap_per_candidate'])
def test_no_retry_or_search_allocation(field):
    value = allocation(); value[field] = 1
    with pytest.raises(ValueError, match='No retry or search'):
        allocated(value, 11.5)


def test_missing_approval_and_min_free_separate_from_working_cap():
    value = allocation()
    assert allocated(value, 11.5)['local_working_storage_bytes'] == 24*GIB
    value['state'] = 'REQUIRED_NO_START'
    with pytest.raises(ValueError, match='REQUIRED_NO_START'):
        allocated(value, 11.5)


def test_zero_flush_interval_requires_explicit_per_node_fsync():
    value = allocation(); value['checkpoint_flush_seconds'] = 0
    with pytest.raises(ValueError, match='Zero flush interval'):
        allocated(value, 11.5)
    value['checkpoint_flush_policy'] = 'fsync_after_every_committed_node'
    assert allocated(value, 11.5) is value


def test_setup_clock_not_reset_and_scoring_reserve_protected(tmp_path):
    a = allocation(); ledger(tmp_path, a, gpu_seconds=10*3600-5)
    deps = SimpleNamespace(clock=lambda: 200, cpu_clock=lambda: 20, boot_id='boot')
    budget = PilotBudget(tmp_path/'bart', a, 'bart', 11.5, dependencies=deps)
    assert budget.deadline == 100+5.75*3600*.85
    with pytest.raises(ValueError, match='Reserved scorer GPU'):
        budget.guard(forecast_seconds=10)


def test_remaining_cli_wall_starts_now_and_all_t4_time_charged_on_cpu_control(tmp_path):
    a = allocation(); ledger(tmp_path, a)
    clock = [200]
    deps = SimpleNamespace(clock=lambda: clock[0], cpu_clock=lambda: 20, boot_id='boot')
    budget = PilotBudget(tmp_path/'lead3', a, 'lead3', .1, dependencies=deps)
    assert budget.deadline == 200+.1*3600
    budget.guard()
    assert budget.ledger['gpu_seconds'] == 100
    clock[0] = 210; budget.guard()
    assert budget.ledger['gpu_seconds'] == 110


def test_cpu_reserve_and_old_session_wall_protected(tmp_path):
    a = allocation(); ledger(tmp_path, a, cpu_seconds=20*3600-5)
    deps = SimpleNamespace(clock=lambda: 200, cpu_clock=lambda: 20, boot_id='boot')
    budget = PilotBudget(tmp_path/'lead3', a, 'lead3', 11.5, dependencies=deps)
    with pytest.raises(ValueError, match='Reserved scorer CPU'):
        budget.guard(forecast_seconds=3)
    ledger(tmp_path, a, completed_session_wall_seconds=11*3600-50)
    budget = PilotBudget(tmp_path/'lead3', a, 'lead3', 11.5, dependencies=deps)
    with pytest.raises(ValueError, match='wall quota'):
        budget.guard()


def test_boot_and_allocation_mismatch_do_not_reset_ledger(tmp_path):
    a = allocation(); original = ledger(tmp_path, a)
    deps = SimpleNamespace(clock=lambda: 200, cpu_clock=lambda: 20, boot_id='different')
    with pytest.raises(ValueError, match='boot changed'):
        PilotBudget(tmp_path/'bart', a, 'bart', 11.5, dependencies=deps)
    assert json.loads((tmp_path/'resource_ledger.json').read_text()) == original
