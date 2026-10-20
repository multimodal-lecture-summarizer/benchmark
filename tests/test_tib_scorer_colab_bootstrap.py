"""Regression for missing ensurepip and a Python left by unsuccessful venv setup."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import venv
import zipfile

import pytest

from experiments.scripts.tib_scorer_colab_bootstrap import SETUP_CELL


@pytest.mark.parametrize("failed_stage", [None, 0, 1, 2])
def test_partial_environment_is_repaired_and_each_failure_is_logged(tmp_path, failed_stage):
    target = tmp_path / "venv/bin/python"
    target.parent.mkdir(parents=True)
    target.write_text("partial environment from failed ensurepip")
    calls, holds = [], []
    def run(command, **kwargs):
        index = len(calls)
        calls.append(command)
        kwargs["stdout"].write("diagnostic for stage " + str(index))
        return SimpleNamespace(returncode=1 if index == failed_stage else 0)
    environment = {"WORK": tmp_path, "OUTPUT": tmp_path, "BUNDLE": tmp_path,
        "os": os, "sys": SimpleNamespace(executable="base-python"),
        "shutil": SimpleNamespace(disk_usage=lambda _: SimpleNamespace(free=20 * 1024**3)),
        "time": SimpleNamespace(monotonic=lambda: 1), "SESSION_LIMIT_SECONDS": 100,
        "SESSION_STARTED": 0, "subprocess": SimpleNamespace(run=run, STDOUT=subprocess.STDOUT),
        "bootstrap_hold": holds.append}
    if failed_stage is None:
        exec(SETUP_CELL, environment)
        assert not holds
    else:
        with pytest.raises(AssertionError, match="HOLD"):
            exec(SETUP_CELL, environment)
        assert holds and len(calls) == failed_stage + 1
    assert "--without-pip" in calls[0]
    assert "--clear" not in calls[0]
    assert (tmp_path / "create-venv.log").read_text() == "diagnostic for stage 0"
    if failed_stage is None:
        assert calls[2][:5] == ["base-python", "-m", "pip", "--python", str(target)]
        assert "requirements-colab-t4.txt" in calls[2][-1]


def test_real_pip_can_install_offline_into_repaired_pipless_environment(tmp_path):
    """Real stdlib/pip smoke only; no network, scorer packages or model execution."""
    target = tmp_path / "environment"
    broken = venv.EnvBuilder(with_pip=True)
    def unavailable(context):
        raise RuntimeError("controlled ensurepip unavailable")
    broken._setup_pip = unavailable
    with pytest.raises(RuntimeError, match="ensurepip unavailable"):
        broken.create(target)
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert python.exists()
    command = [sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(target)]
    repaired = subprocess.run(command, capture_output=True, text=True, timeout=45)
    assert repaired.returncode == 0, repaired.stderr
    wheel = tmp_path / "tib_bootstrap_fixture-0.0.0-py3-none-any.whl"
    info = "tib_bootstrap_fixture-0.0.0.dist-info/"
    contents = {"tib_bootstrap_fixture.py": "MARKER = 'target-only'\n",
        info + "METADATA": "Metadata-Version: 2.1\nName: tib-bootstrap-fixture\nVersion: 0.0.0\n",
        info + "WHEEL": "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    contents[info + "RECORD"] = "".join(name + ",,\n" for name in [*contents, info + "RECORD"])
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)
    installed = subprocess.run([sys.executable, "-m", "pip", "--python", str(python),
        "install", "--no-index", "--no-deps", "--disable-pip-version-check", str(wheel)],
        capture_output=True, text=True, timeout=45)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    probe = subprocess.run([str(python), "-c",
        "import sys,tib_bootstrap_fixture; assert sys.prefix != sys.base_prefix; print(tib_bootstrap_fixture.__file__)"],
        capture_output=True, text=True, timeout=45)
    assert probe.returncode == 0, probe.stderr
    assert str(target).lower() in probe.stdout.lower()
