"""Final523 notebook: every code cell compiles, the status and live-progress cells really run on fixtures, output stays text-free."""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from experiments.scripts import tib_final523_notebook as notebook

PREPARED = {"archive_sha256": "a" * 64, "manifest_sha256": "b" * 64, "expected_cells": 2092}


@pytest.fixture(scope="module")
def cells(tmp_path_factory):
    registry = tmp_path_factory.mktemp("reg")
    root = tmp_path_factory.mktemp("root")
    (root / "experiments/notebooks").mkdir(parents=True)
    (registry / "preparation_receipt.json").write_text(json.dumps(PREPARED))
    shutil.copyfile(notebook.REGISTRY / "selection_allocation.json", registry / "selection_allocation.json")
    result = notebook.create(registry, root)
    data = json.loads(open(result["path"], encoding="utf-8").read())
    return data["cells"], result


def code(cells, index):
    return "".join(cells[0][index]["source"])


def test_every_code_cell_compiles(cells):
    for cell in cells[0]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), cell["id"], "exec")


def test_stage_name_is_final_and_hashes_are_embedded(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0])
    assert "a" * 64 in text and "b" * 64 in text and "TIB_FINAL523_261024_V1" in text
    leftovers = [l for l in text.splitlines() if "selection300" in l.lower()]
    assert all("selection300 run" in l or "from selection300" in l for l in leftovers)


def test_cells_declare_the_new_settings_and_never_self_authorize(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0])
    assert "SESSION_PROFILES = ['lead3', 'lexrank', 'bart']" in text and "RESUME = False" in text
    assert "selection_start_authorized': False" in text and "start_authorization.json missing" in text


def find(cells, needle):
    return next(i for i, c in enumerate(cells[0]) if c["cell_type"] == "code" and needle in "".join(c["source"]))


def status_namespace(tmp_path, profiles, resume=False, attempted=None, complete=()):
    bundle, output = tmp_path / "bundle", tmp_path / "out"
    bundle.mkdir()
    output.mkdir()
    ids = [f"test:{i}" for i in range(10)]
    (bundle / "selection_contract.json").write_text(json.dumps(
        {"candidate_order": ["lead3", "lexrank", "bart", "led"], "selection_ids": ids}))
    for name, count in (attempted or {}).items():
        (output / name / "records").mkdir(parents=True)
        for i in range(count):
            (output / name / "records" / f"{i}.json").write_text("{}")
        (output / name / "run_identity.json").write_text("{}")
    for name in complete:
        (output / name).mkdir(exist_ok=True)
        (output / name / "candidate_receipt.json").write_text(json.dumps(
            {"status": "PASS", "summary": {"pending": 0, "denominator": 10, "status_counts": {"completed": 10}}}))
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"session_runs": [{}], "gpu_seconds": 3600}))
    return {"json": json, "time": time, "Path": __import__("pathlib").Path, "BUNDLE": bundle, "OUTPUT": output,
            "SESSION_PROFILES": profiles, "RESUME": resume, "LEDGER": ledger, "SESSION_STARTED": time.monotonic(),
            "SESSION_LIMIT_SECONDS": 4.0 * 3600, "allocation": {"max_sessions": 4, "total_gpu_hours": 21},
            "authorization": {"authorized_by": "user", "authorized_on": "2026-11-01", "statement": "start final523 generation"}}


def test_status_cell_reports_progress_and_resume_warning(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, ["lead3", "lexrank", "bart"], attempted={"bart": 4}, complete=("lead3",))
    exec(code(cells, find(cells, "def progress_table")), namespace)
    out = capsys.readouterr().out
    assert "sessions used 1 of 4" in out and "complete" in out and "4/10" in out
    assert "Authorization: by user on 2026-11-01 | start final523 generation" in out
    assert "WARNING: bart has earlier output: set RESUME=True" in out
    assert "WARNING: bart projects ~2.40 h" not in out   # 4 h left in the fixture session
    assert "Next: run lexrank, bart" in out


def test_status_cell_warns_when_the_session_is_too_short(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, ["led"], resume=True)
    namespace["SESSION_LIMIT_SECONDS"] = 2.0 * 3600
    exec(code(cells, find(cells, "def progress_table")), namespace)
    assert "WARNING: led projects ~3.10 h of work but only" in capsys.readouterr().out


@pytest.mark.parametrize("profiles", [[], ["bart", "bart"], ["gpt"], ["bart", "led"]])
def test_invalid_session_profiles_are_refused(cells, tmp_path, profiles):
    namespace = status_namespace(tmp_path, profiles)
    with pytest.raises(AssertionError):
        exec(code(cells, find(cells, "def progress_table")), namespace)


def test_live_progress_runner_prints_during_the_run_and_keeps_text_out(cells, tmp_path, capsys):
    namespace = status_namespace(tmp_path, ["lead3"])
    exec(code(cells, find(cells, "def progress_table")), namespace)
    capsys.readouterr()
    run_source = code(cells, find(cells, "def run_logged")).replace("POLL_SECONDS = 30", "POLL_SECONDS = 1").replace(
        "time.sleep(2)", "time.sleep(0.2)")
    run_source = run_source.split("exits = {}")[0]
    helper = (
        "import json,sys,time\n"
        "for i in range(3):\n"
        "    print(json.dumps({'candidate_id':'lead3','record_id':'test:%d'%i,'status':'completed'}),flush=True)\n"
        "    time.sleep(1.2)\n")
    fake_shutil = type("FakeShutil", (), {"disk_usage": staticmethod(lambda path: type("U", (), {"free": 30 * 1024**3})())})
    namespace.update({"DEPENDENCIES_READY": True, "PREFLIGHT_OK": True, "subprocess": subprocess, "shutil": fake_shutil, "os": os,
                      "BUNDLE": tmp_path, "RUN_ENV": dict(os.environ), "sha": lambda p: "x", "bootstrap_hold": lambda r: None,
                      "PYTHON": sys.executable})
    exec(run_source, namespace)
    (namespace["OUTPUT"] / "lead3" / "records").mkdir(parents=True)
    code_returned = namespace["candidate_runner"]([sys.executable, "-c", helper], "lead3-test.log", "lead3")
    out = capsys.readouterr().out
    assert code_returned == 0 and "test:0 completed" in out and "lead3" in out
    assert "rec/h" in out and "ETA" in out and "session left" in out and "exit 0" in out
    assert "source_normalized" not in out


def test_checkpoint_summary_is_written_atomically_and_text_free(cells, tmp_path):
    namespace = status_namespace(tmp_path, ["lead3"], attempted={"lead3": 3}, complete=("lexrank",))
    exec(code(cells, find(cells, "def progress_table")), namespace)
    source = code(cells, find(cells, "def write_checkpoint_summary")).split("exits = {}")[0]
    namespace.update({"os": os, "subprocess": subprocess, "shutil": shutil, "DEPENDENCIES_READY": True, "PREFLIGHT_OK": True,
                      "sha": lambda p: "h" * 64})
    exec(source, namespace)
    namespace["write_checkpoint_summary"]()
    summary = json.loads((namespace["OUTPUT"] / "checkpoint_summary.json").read_text())
    assert summary["profiles"]["lead3"]["attempted"] == 3 and summary["profiles"]["lexrank"]["complete"] is True
    assert summary["profiles"]["lexrank"]["receipt_sha256"] == "h" * 64
    assert not (namespace["OUTPUT"] / "checkpoint_summary.json.tmp").exists()


def test_notebook_is_not_executed_and_preparation_is_recorded(cells):
    _, result = cells
    assert result["executed"] is False and len(result["sha256"]) == 64


def run_namespace(cells, tmp_path, profiles=("lead3",)):
    namespace = status_namespace(tmp_path, list(profiles))
    exec(code(cells, find(cells, "def progress_table")), namespace)
    fake_shutil = type("FakeShutil", (), {"disk_usage": staticmethod(lambda path: type("U", (), {"free": 30 * 1024**3})())})
    namespace.update({"DEPENDENCIES_READY": True, "PREFLIGHT_OK": True, "subprocess": subprocess, "shutil": fake_shutil, "os": os,
                      "BUNDLE": tmp_path, "RUN_ENV": dict(os.environ), "sha": lambda p: "x", "bootstrap_hold": lambda r: None,
                      "PYTHON": sys.executable})
    return namespace


def test_run_cell_rechecks_the_session_profile_rule(cells, tmp_path):
    namespace = run_namespace(cells, tmp_path)
    namespace["SESSION_PROFILES"] = ["bart", "led"]   # edited after the status cell ran
    with pytest.raises(AssertionError, match="BART and LED"):
        exec(code(cells, find(cells, "def run_logged")).split("exits = {}")[0], namespace)


def test_runtime_stops_before_the_notebook_kills_it(cells):
    text = code(cells, find(cells, "def run_logged"))
    assert "RUNTIME_MARGIN_HOURS = 0.25" in text
    assert "'--wall-hours', str(min(5.75, remaining - RUNTIME_MARGIN_HOURS))" in text
    assert "if remaining - RUNTIME_MARGIN_HOURS <= 0:" in text


def test_stop_process_ends_a_running_subprocess(cells, tmp_path):
    namespace = run_namespace(cells, tmp_path)
    exec(code(cells, find(cells, "def run_logged")).split("exits = {}")[0], namespace)
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    namespace["stop_process"](process)
    assert process.poll() is not None


def test_a_log_line_split_across_polls_is_reassembled(cells, tmp_path, capsys):
    namespace = run_namespace(cells, tmp_path)
    run_source = code(cells, find(cells, "def run_logged")).replace("POLL_SECONDS = 30", "POLL_SECONDS = 0").replace(
        "time.sleep(2)", "time.sleep(0.1)").split("exits = {}")[0]
    exec(run_source, namespace)
    capsys.readouterr()
    helper = ("import sys, time\n"
              "sys.stdout.write('{\"record_id\": \"test:9\", '); sys.stdout.flush()\n"
              "time.sleep(1.0)\n"
              "sys.stdout.write('\"status\": \"completed\"}\\n'); sys.stdout.flush()\n"
              "time.sleep(0.5)\n")
    namespace["candidate_runner"]([sys.executable, "-c", helper], "split.log", "lead3")
    out = capsys.readouterr().out
    assert "test:9 completed" in out and "log: {" not in out


def test_monitor_does_not_hang_without_a_log(cells):
    text = "\n".join("".join(c["source"]) for c in cells[0] if c["cell_type"] == "markdown")
    assert '[ -n "$f" ] && tail -n 6 "$f"' in text
