"""Three-session ledger lifecycle under the approved selection300 allocation."""
import pytest

from selection_fixtures import real_allocation
from experiments.scripts import tib_stage_session as session

SHA = "b" * 64


def obs(boot, t, cpus=2):
    return {"boot_id": boot, "monotonic": t, "epoch_ns": 1_000 + int(t), "logical_cpu_count": cpus}


def test_three_sessions_then_fourth_is_refused(tmp_path):
    a, path = real_allocation(), tmp_path / "ledger.json"
    for index, boot in enumerate(("vm1", "vm2", "vm3")):
        ledger = session.begin_session(path, a, SHA, observation=obs(boot, 100.0), local_working_root="/content/work")
        assert len(ledger["session_runs"]) == index + 1
        assert ledger["session_limit_seconds"] == 5.0 * 3600
        session.finish_session(path, observation=obs(boot, 100.0 + 600))
    with pytest.raises(ValueError, match="session count exhausted"):
        session.begin_session(path, a, SHA, observation=obs("vm4", 100.0), local_working_root="/content/work")


def test_unfinished_session_is_charged_conservatively_on_the_next_vm(tmp_path):
    a, path = real_allocation(), tmp_path / "ledger.json"
    session.begin_session(path, a, SHA, observation=obs("vm1", 100.0), local_working_root="/content/work")
    ledger = session.begin_session(path, a, SHA, observation=obs("vm2", 50.0), local_working_root="/content/work")
    assert ledger["session_runs"][0]["status"] == "interrupted"
    assert ledger["unobserved_loss_reserve"]["wall_seconds"] == 5.0 * 3600
    assert ledger["gpu_seconds"] >= 5.0 * 3600


def test_total_gpu_hours_never_exceed_the_ceiling(tmp_path):
    a, path = real_allocation(), tmp_path / "ledger.json"
    for boot in ("vm1", "vm2", "vm3"):
        try:
            session.begin_session(path, a, SHA, observation=obs(boot, 0.0), local_working_root="/content/work")
        except ValueError:
            break  # exhausted before opening another
    ledger = session._load(path)
    assert ledger["gpu_seconds"] <= a["total_gpu_hours"] * 3600


def test_changed_allocation_or_bundle_is_refused(tmp_path):
    a, path = real_allocation(), tmp_path / "ledger.json"
    session.begin_session(path, a, SHA, observation=obs("vm1", 0.0), local_working_root="/content/work")
    with pytest.raises(ValueError, match="binding mismatch"):
        session.begin_session(path, a, "c" * 64, observation=obs("vm1", 1.0), local_working_root="/content/work")
