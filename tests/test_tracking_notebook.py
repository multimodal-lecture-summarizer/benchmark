import json
import sys

import pytest

pytest.importorskip("trackeval")
pytest.importorskip("supervision")
pytest.importorskip("trackers")
pytest.importorskip("pandas")
pytest.importorskip("matplotlib")

from experiments.scripts import build_tracking_benchmark_notebook as builder


@pytest.fixture(scope="module")
def notebook(tmp_path_factory):
    """Build into a temp file so the committed notebook is untouched."""
    original = builder.OUTPUT
    builder.OUTPUT = tmp_path_factory.mktemp("nb") / "03b.ipynb"
    try:
        path = builder.build()
        yield json.loads(path.read_text(encoding="utf-8"))
    finally:
        builder.OUTPUT = original


def run_cells(nb, workdir, monkeypatch, overrides=None):
    """Execute the code cells in one namespace, like the notebook runtime; config lines can be overridden."""
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("DT_SKIP_PIP", "1")
    monkeypatch.setattr(sys, "path", list(sys.path))
    ns = {"__name__": "__main__"}
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        src = "".join(cell["source"])
        for key, value in (overrides or {}).items():
            for line in src.splitlines():
                if line.startswith(f"{key} ="):
                    src = src.replace(line, f"{key} = {value}")
        exec(compile(src, "<cell>", "exec"), ns)
    return ns


def test_notebook_structure_and_defaults(notebook):
    import nbformat
    nbformat.validate(nbformat.from_dict({**notebook, "cells": [{**c, "id": f"c{i}"} for i, c in enumerate(notebook["cells"])]}))
    code = "".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")
    assert "MODE = 'dry'" in code                         # the safe default: nothing downloaded, nothing GPU
    assert "LICENSE_ACK = False" in code and "ALLOW_OVER_BUDGET = False" in code
    assert "DETECTOR_TRAIN_DATA_UNVERIFIED" in code and "imagenet" in code.lower()


def test_embedded_code_is_the_repo_code(notebook):
    embed = next("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code" and "SOURCES = " in "".join(c["source"]))
    for module in builder.MODULES:
        text = (builder.ROOT / module).read_text(encoding="utf-8")
        assert repr(text) in embed, f"{module} in the notebook differs from the repo file"


def test_dry_runs_end_to_end_and_is_never_reportable(notebook, tmp_path, monkeypatch):
    ns = run_cells(notebook, tmp_path, monkeypatch)
    out = ns["OUT"]
    manifest = json.loads((out / "dry_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reportable"] is False and manifest["mode"] == "dry"
    gate = json.loads((out / "dry-budget-gate.json").read_text(encoding="utf-8"))
    assert gate["valid"] is False                          # a dry gate can never unlock `full`
    assert {"HOTA", "DetA", "AssA"} <= set(ns["TABLES"]["dry"].columns)
    assert (out / "bundle_dry.zip").exists()
    diag = ns["DIAG_DF"]                                    # detection diagnostics: dry detections are GT + jitter, so recall is high
    assert set(diag.thr) == {0.1, 0.3, 0.5, 0.7} and (diag[diag.thr == 0.1].recall > 0.7).all()
    assert (out / "tables" / "dry_det_diagnostics.csv").exists()
    assert set(manifest["sequence_frame_rates"]) == set(ns["VAL"] + ns["DEV"])


def test_dry_rerun_reuses_runs_instead_of_recomputing(notebook, tmp_path, monkeypatch):
    run_cells(notebook, tmp_path, monkeypatch)
    ns = run_cells(notebook, tmp_path, monkeypatch)       # same RUN_ID: every run and score must come from disk
    runs = list((ns["OUT"] / "runs").rglob("*.json"))
    assert runs and all(json.loads(p.read_text())["ok"] for p in runs)


def test_full_is_refused_without_a_valid_smoke_gate(notebook, tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="smoke"):
        run_cells(notebook, tmp_path, monkeypatch, {"MODE": "'full'"})


def test_smoke_is_refused_until_the_license_is_acknowledged(notebook, tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="LICENSE_ACK"):
        run_cells(notebook, tmp_path, monkeypatch, {"MODE": "'smoke'"})
