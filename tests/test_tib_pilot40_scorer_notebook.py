"""Generated Pilot40 notebook is checked for syntax and guards without Colab."""
import ast
import json
from pathlib import Path

import pytest

from experiments.scripts import tib_pilot40_scorer_notebook as writer


@pytest.fixture
def notebook(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    registry.mkdir()
    (tmp_path / "experiments/notebooks").mkdir(parents=True)
    (registry / "preparation_receipt.json").write_text(json.dumps({
        "archive_sha256": "a" * 64, "manifest_sha256": "b" * 64, "rows": 160,
        "scoreable_rows": 154, "failed_rows": 6}))
    monkeypatch.setattr(writer, "REGISTRY", registry)
    monkeypatch.setattr(writer, "ROOT", tmp_path)
    return json.loads(Path(writer.create_notebook()["notebook"]).read_text(encoding="utf-8"))


def test_cells_parse_and_carry_no_execution_claim(notebook):
    code = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(code) == 6
    for cell in code:
        ast.parse("".join(cell["source"]))
        assert cell["execution_count"] is None and cell["outputs"] == []


def test_notebook_targets_pilot40_runner_without_generation_or_qwen(notebook):
    text = json.dumps(notebook)
    assert "tib_pilot40_scorer_runner" in text and "scorer_pilot40_receipt.json" in text
    assert "NodeCheckpointGenerator" not in text and "qwen3" not in text.lower().replace("no qwen3", "")
    assert "SESSION_LIMIT_SECONDS = 1.5 * 3600" in text


def test_zip_and_manifest_verified_before_install(notebook):
    sources = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    assert "assert sha(archive)==EXPECTED_ZIP_SHA256" in sources[1]
    assert "assert sha(BUNDLE/'package_manifest.json')==EXPECTED_MANIFEST_SHA256" in sources[1]
    assert "pip" not in sources[1] and "pip" in sources[2]  # install happens only in the later cell
