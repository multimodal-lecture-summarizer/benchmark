"""Notebook execution guards are checked without Colab or a model runtime."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_scorer_colab_notebook as notebook_writer


@pytest.fixture
def notebook(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    registry.mkdir()
    (tmp_path / "experiments/notebooks").mkdir(parents=True)
    (registry / "scorer_ready_receipt.json").write_text(json.dumps({
        "archive_sha256": "a" * 64, "manifest_sha256": "b" * 64}))
    monkeypatch.setattr(notebook_writer, "REGISTRY", registry)
    monkeypatch.setattr(notebook_writer, "ROOT", tmp_path)
    path = Path(notebook_writer.create_notebook()["notebook"])
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_generated_cells_have_valid_python_and_no_execution_claim(notebook):
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert len(code_cells) == 6
    for cell in code_cells:
        ast.parse("".join(cell["source"]))
        assert cell["execution_count"] is None and cell["outputs"] == []
    text = json.dumps(notebook)
    assert "NodeCheckpointGenerator" not in text
    assert "tib_scorer_colab_runner" in text


@pytest.mark.parametrize("exit_code", [0, 2, 9])
def test_old_pass_cannot_certify_new_failed_or_stale_subprocess(notebook, tmp_path, exit_code):
    output = tmp_path / "evidence"
    output.mkdir()
    receipt = output / "scorer_ready_receipt.json"
    receipt.write_text(json.dumps({"status": "PASS", "run_id": "1"}))
    events = []
    def hold(reason):
        events.append(reason)
        receipt.write_text(json.dumps({"status": "HOLD", "reason": reason}))
        (output / "bootstrap_hold.json").write_text(receipt.read_text())
    environment = {"OUTPUT": output, "BUNDLE": tmp_path, "ASSETS": tmp_path,
        "PYTHON": Path("python"), "SESSION_LIMIT_SECONDS": 11.5 * 3600,
        "SESSION_STARTED": 0, "time": SimpleNamespace(monotonic=lambda: 1, time_ns=lambda: 100),
        "execute": lambda command, name: exit_code, "bootstrap_hold": hold, "json": json}
    source = next("".join(cell["source"]) for cell in notebook["cells"]
                  if cell["cell_type"] == "code" and "RESUME = False" in "".join(cell["source"]))
    exec(compile(source, "notebook-scorer-cell", "exec"), environment)
    assert json.loads(receipt.read_text())["status"] == "HOLD"
    assert len(events) >= 2


def test_zip_and_file_manifest_verified_before_subprocess_install(notebook):
    sources = ["".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert "assert sha(archive)==EXPECTED_ZIP_SHA256" in sources[1]
    assert "assert sha(BUNDLE/'package_manifest.json')==EXPECTED_MANIFEST_SHA256" in sources[1]
    assert "target.is_relative_to(BUNDLE.resolve())" in sources[1]
    assert "'pip','--python',str(PYTHON),'install'" in sources[2]
