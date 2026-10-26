"""Final523 scoring notebook: cells compile, the status and live-progress cells run on fixtures, resume advice is honest."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from experiments.scripts import tib_final523_scorer_notebook as notebook

PREPARED = {"archive_sha256": "a" * 64, "manifest_sha256": "b" * 64, "generation_bundle_manifest_sha256": "c" * 64,
            "generation_evidence_zip_name": "tib-final523-evidence-20261101T000000Z.zip",
            "generation_evidence_zip_sha256": "d" * 64, "rows": 2092, "scoreable_rows": 6, "failed_rows": 4,
            "scoring_max_sessions": 2, "scoring_total_hours": 10.85}


@pytest.fixture(scope="module")
def cells(tmp_path_factory):
    registry, root = tmp_path_factory.mktemp("reg"), tmp_path_factory.mktemp("root")
    (root / "experiments/notebooks").mkdir(parents=True)
    (registry / "preparation_receipt.json").write_text(json.dumps(PREPARED))
    result = notebook.create(registry, root)
    return json.loads(Path(result["path"]).read_text(encoding="utf-8"))["cells"], result


def source(cells, needle):
    return next("".join(c["source"]) for c in cells[0] if c["cell_type"] == "code" and needle in "".join(c["source"]))


def test_every_code_cell_compiles(cells):
    for cell in cells[0]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), cell["id"], "exec")


def test_stage_hashes_and_evidence_name_are_embedded_and_no_placeholder_is_left(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0])
    assert "a" * 64 in text and "b" * 64 in text and "c" * 64 in text and "d" * 64 in text
    assert "tib-final523-evidence-20261101T000000Z.zip" in text and "TIB_FINAL523_261024_V1" in text
    assert "@@" not in text and "--stage', 'final523'" in text and "scorer_final523_receipt.json" in text
    assert "tib-final523-scoring-evidence-" in text and "tib-selection300-scoring-evidence-" not in text
    assert "1197" not in text and "--stage', 'selection300'" not in text


def test_markdown_states_the_resume_policy_and_its_guards(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0] if c["cell_type"] == "markdown")
    assert "RESUME_MODE = 'partial'" in text and "scorer_resume_policy_final523_v1.json" in text
    assert "drift canary" in text and "never treated as holes" in text and "quarantined" in text
    assert "restarted from scratch" not in text and "session 3 of at most 4" not in text
    assert "its own ledger" in text and "up to **2 sessions**" in text and "10.85 h in total" in text
    assert "scoring_budget_decision_final523_v1.json" in text and "Disconnect and delete runtime" in text


def status_namespace(tmp_path, scored=0, viewed=0, resume="none"):
    output = tmp_path / "out"
    for folder, count in (("checkpoints", scored), ("view_checkpoints", viewed)):
        (output / folder).mkdir(parents=True)
        for i in range(count):
            (output / folder / f"{i}.json").write_text("{}")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"session_runs": [{}, {}], "gpu_seconds": 7200}))
    return {"json": json, "time": time, "OUTPUT": output, "LEDGER": ledger, "RESUME": resume != "none",
            "RESUME_MODE": resume,
            "contract": {"expected_scoreable": 6, "expected_failed": 4},
            "allocation": {"max_sessions": 4, "total_gpu_hours": 21}}


def test_status_reports_a_fresh_start(cells, tmp_path, capsys):
    exec(source(cells, "def checkpoint_count"), status_namespace(tmp_path))
    out = capsys.readouterr().out
    assert "sessions used 2 of 4" in out and "scored checkpoints 0/6" in out and "Next: score all 6" in out


def test_status_says_a_partial_cache_cannot_be_resumed(cells, tmp_path, capsys):
    exec(source(cells, "def checkpoint_count"), status_namespace(tmp_path, scored=3, viewed=1))
    out = capsys.readouterr().out
    assert "PARTIAL (3 scored, 1 views of 6)" in out and "RESUME_MODE = 'partial' continues it" in out
    assert "COMPLETE" not in out and "start from scratch" not in out and "_attempt1" not in out
    assert "WARNING: RESUME_MODE is 'none'" in out


def test_status_recognises_a_complete_cache(cells, tmp_path, capsys):
    exec(source(cells, "def checkpoint_count"), status_namespace(tmp_path, scored=6, viewed=6))
    out = capsys.readouterr().out
    assert "COMPLETE cache. RESUME_MODE = 'complete' replays it" in out and "WARNING: RESUME_MODE is 'none'" in out


def test_run_cell_prints_live_progress_from_the_scorer_subprocess(cells, tmp_path, capsys):
    bundle, output = tmp_path / "bundle", tmp_path / "out"
    (bundle / "experiments/scripts").mkdir(parents=True)
    (bundle / "experiments/__init__.py").write_text("")
    (bundle / "experiments/scripts/__init__.py").write_text("")
    (bundle / "experiments/scripts/tib_pilot40_scorer_runner.py").write_text(
        "import sys, time, pathlib\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
        "for folder in ('checkpoints', 'view_checkpoints'):\n"
        "    (out / folder).mkdir(parents=True, exist_ok=True)\n"
        "for i in range(3):\n"
        "    (out / 'checkpoints' / f'{i}.json').write_text('{}')\n"
        "    print('Scorer score sample', i, flush=True)\n"
        "    time.sleep(1.2)\n")
    namespace = {"json": json, "time": time, "os": os, "subprocess": subprocess, "BUNDLE": bundle, "OUTPUT": output,
                 "RUN_ENV": dict(os.environ), "PYTHON": sys.executable, "ASSETS": tmp_path / "assets", "LEDGER": tmp_path / "ledger.json",
                 "RESUME": False, "RESUME_MODE": "none", "SESSION_OPENED": True, "SCORER_READY": True, "SESSION_STARTED": time.monotonic(),
                 "SESSION_LIMIT_SECONDS": 4.0 * 3600, "SESSION_DEADLINE_SECONDS": 3.5 * 3600, "EXPORT_RESERVE_SECONDS": 0,
                 "contract": {"expected_scoreable": 3, "expected_failed": 0}, "holds": [],
                 "shutil": type("S", (), {"disk_usage": staticmethod(lambda p: type("U", (), {"free": 30 * 1024**3})())})}
    namespace["bootstrap_hold"] = namespace["holds"].append
    output.mkdir()
    (tmp_path / "ledger.json").write_text(json.dumps({"session_runs": [], "gpu_seconds": 0}))
    namespace.update({"allocation": {"max_sessions": 4, "total_gpu_hours": 21}})
    exec(source(cells, "def checkpoint_count"), namespace)
    capsys.readouterr()
    run = source(cells, "def run_logged").replace("POLL_SECONDS = 30", "POLL_SECONDS = 1").replace("time.sleep(2)", "time.sleep(0.2)")
    exec(run, namespace)
    out = capsys.readouterr().out
    assert "scoring" in out and "ckpt/h" in out and "ETA" in out and "session left" in out and "exit 0" in out
    assert "scored 3/3 | views 0/3" in out
    assert "No actual scorer receipt produced" in namespace["holds"]   # the fake runner writes no receipt: HOLD, never a fake PASS


def test_notebook_is_not_executed_and_recorded(cells):
    assert cells[1]["executed"] is False and len(cells[1]["sha256"]) == 64


def test_status_flags_unfinished_partial_files(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, scored=3, viewed=0)
    (namespace["OUTPUT"] / "checkpoints" / "7.json.partial").write_text("{}")
    exec(source(cells, "def checkpoint_count"), namespace)
    out = capsys.readouterr().out
    assert "WARNING: 1 torn *.partial checkpoint files" in out


def test_kill_is_a_backstop_behind_the_runner_deadline_and_budget_display_uses_the_deadline(cells):
    text = source(cells, "def run_logged")
    assert "remaining_hours * 3600 + 300" in text
    assert "def left_hours(): return (SESSION_DEADLINE_SECONDS - EXPORT_RESERVE_SECONDS" in text


def test_monitor_does_not_hang_without_a_log(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0] if c["cell_type"] == "markdown")
    assert '[ -n "$f" ] && tail -n 6 "$f"' in text


def test_status_in_partial_mode_announces_the_quarantine_and_stays_quiet_about_warnings(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, scored=3, viewed=0, resume="partial")
    (namespace["OUTPUT"] / "checkpoints" / "7.json.partial").write_text("{}")
    exec(source(cells, "def checkpoint_count"), namespace)
    out = capsys.readouterr().out
    assert "1 torn *.partial checkpoint files (a killed write) will be quarantined" in out
    assert "WARNING" not in out


def test_status_without_the_mode_warns_about_torn_files(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, scored=3, viewed=0)
    (namespace["OUTPUT"] / "checkpoints" / "7.json.partial").write_text("{}")
    exec(source(cells, "def checkpoint_count"), namespace)
    assert "only RESUME_MODE = 'partial' can quarantine them" in capsys.readouterr().out


def test_modes_map_to_the_runner_flags_and_the_first_cell_validates_the_mode(cells):
    run = source(cells, "def run_logged")
    assert "if RESUME_MODE == 'complete':\n    command.append('--resume')" in run
    assert "elif RESUME_MODE == 'partial':\n    command.append('--resume-partial')" in run
    config = source(cells, "RESUME_MODE = ")
    assert "RESUME_MODE = 'none'" in config and "assert RESUME_MODE in ('none', 'partial', 'complete')" in config
    verify = source(cells, "Scoring checkpoints exist")
    assert "set RESUME_MODE to partial (continue) or complete (replay)" in verify and "RESUME=True" not in verify
    assert "--resume-partial" in run and "'quarantined'" in run and "'canary'" in run
