"""Generated selection300 notebook: syntax, start gate, ordering and monitoring recipe, without Colab."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from selection_fixtures import REGISTRY as BINDING_REGISTRY
from experiments.scripts import tib_selection300_notebook as writer


@pytest.fixture
def notebook(tmp_path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (tmp_path / "experiments/notebooks").mkdir(parents=True)
    (registry / "preparation_receipt.json").write_text(json.dumps({
        "archive_sha256": "a" * 64, "manifest_sha256": "b" * 64, "expected_cells": 1200}))
    (registry / "selection_allocation.json").write_text((BINDING_REGISTRY / "compute_budget_selection300.json").read_text())
    path = Path(writer.create(registry, tmp_path)["path"])
    return json.loads(path.read_text(encoding="utf-8"))


def code_cells(notebook):
    return ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]


def test_all_code_cells_parse_and_make_no_execution_claim(notebook):
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert len(cells) == 6
    for cell in cells:
        ast.parse("".join(cell["source"]))
        assert cell["execution_count"] is None and cell["outputs"] == []


def test_hashes_embedded_and_only_one_setting(notebook):
    sources = code_cells(notebook)
    assert "EXPECTED_ZIP_SHA256 = " + repr("a" * 64) in sources[0] and "EXPECTED_MANIFEST_SHA256 = " + repr("b" * 64) in sources[0]
    assert sum(line.startswith("RESUME = ") for src in sources for line in src.splitlines()) == 1
    text = " ".join(code_cells(notebook)).lower()
    assert "qwen" not in text and "reference" not in text


def test_authorization_gate_precedes_install_and_model_loading(notebook):
    sources = code_cells(notebook)
    upload, setup, preflight, run = sources[1], sources[2], sources[3], sources[4]
    assert upload.index("start_authorization.json missing") < upload.index("begin_session(")
    assert "HOLD: start_authorization.json missing" in upload and "authorized_by'] == 'user'" in upload
    assert "pip" in setup and "pip" not in upload and "tib_selection_runtime" in run and "--authorization" in run
    assert preflight.index("runtime_environment('bart')") < preflight.index("preflight_receipt.json")
    assert "install.log" in setup


def test_missing_authorization_stops_with_hold_before_any_install(notebook, tmp_path):
    upload = code_cells(notebook)[1]
    output = tmp_path / "out"
    output.mkdir()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    holds = []
    zip_path = tmp_path / "z.zip"
    import zipfile
    manifest = bundle / "selection_manifest.json"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("selection_manifest.json", '{"files": {}}')
    import hashlib
    env = {"files": SimpleNamespace(upload=lambda: {str(zip_path): b""}), "Path": Path, "zipfile": zipfile,
           "OUTPUT": output, "BUNDLE": bundle, "EXPECTED_ZIP_SHA256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
           "EXPECTED_MANIFEST_SHA256": hashlib.sha256(b'{"files": {}}').hexdigest(), "json": json, "sha": lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
           "bootstrap_hold": holds.append}
    with pytest.raises(SystemExit):
        exec(compile(upload, "upload-cell", "exec"), env)
    assert holds and "missing" in holds[0] and "begin_session" not in env


def test_run_cell_leaves_complete_candidates_alone_and_requires_resume(notebook):
    run = code_cells(notebook)[3 + 1]
    assert "already complete; kept untouched" in run and "Existing candidate output requires RESUME=True" in run


def test_monitoring_recipe_lists_all_four_profiles_and_log_tail(notebook):
    text = "".join(c["source"][0] if False else "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "markdown")
    for token in ("lead3 lexrank bart led", "nvidia-smi", "Get-ChildItem", "attempted", "/300"):
        assert token in text


def test_no_code_path_creates_an_authorization():
    from experiments.scripts import tib_selection300_bundle as bundle
    from experiments.scripts import tib_selection300_readiness as readiness
    for module in (bundle, writer, readiness):
        assert not hasattr(module, "make_authorization")


def run_cell(notebook, tmp_path, contract_ids, receipts, resume, execute_results):
    """Execute the RUN cell with fake subprocess execution and prepared candidate receipts."""
    import hashlib
    output, bundle = tmp_path / "out", tmp_path / "bundle"
    output.mkdir(parents=True, exist_ok=True)
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "selection_contract.json").write_text(json.dumps({"selection_ids": contract_ids, "candidate_order": list(receipts)}))
    for name, receipt in receipts.items():
        if receipt is not None:
            (output / name).mkdir(exist_ok=True)
            (output / name / "candidate_receipt.json").write_text(json.dumps(receipt))
            (output / name / "run_identity.json").write_text("{}")
    calls, holds = [], []
    def execute(command, log):
        name = command[command.index("--candidate") + 1]
        calls.append((name, "--resume" in command))
        status = execute_results.get(name, "PASS")
        (output / name).mkdir(exist_ok=True)
        (output / name / "candidate_receipt.json").write_text(json.dumps({"status": status, "summary": {"pending": 0, "denominator": len(contract_ids)}}))
        return 0
    env = {"DEPENDENCIES_READY": True, "PREFLIGHT_OK": True, "BUNDLE": bundle, "OUTPUT": output, "Path": Path, "json": json,
           "time": SimpleNamespace(monotonic=lambda: 1.0, time_ns=lambda: 7), "SESSION_LIMIT_SECONDS": 5 * 3600,
           "SESSION_STARTED": 0.0, "PYTHON": Path("python"), "ALLOCATION": output / "a.json", "AUTH": output / "auth.json",
           "RESUME": resume, "execute": execute, "bootstrap_hold": holds.append}
    exec(compile(code_cells(notebook)[4], "run-cell", "exec"), env)
    return calls, holds


def terminal(n):
    return {"status": "COMPLETED_WITH_FAILURES", "summary": {"pending": 0, "denominator": n, "status_counts": {"started": 1}}}


def test_run_cell_skips_finished_candidates_including_one_with_an_interrupted_record(notebook, tmp_path):
    ids = ["a", "b", "c"]
    receipts = {"lead3": terminal(3), "lexrank": None, "bart": None, "led": None}
    calls, holds = run_cell(notebook, tmp_path, ids, receipts, resume=True, execute_results={})
    assert [c[0] for c in calls] == ["lexrank", "bart", "led"] and not holds


def test_run_cell_stops_after_a_hold_and_never_runs_later_profiles(notebook, tmp_path):
    receipts = {"lead3": None, "lexrank": None, "bart": None, "led": None}
    calls, _ = run_cell(notebook, tmp_path, ["a"], receipts, resume=False, execute_results={"lexrank": "HOLD"})
    assert [c[0] for c in calls] == ["lead3", "lexrank"]


def test_run_cell_requires_resume_for_an_existing_candidate_and_passes_the_flag(notebook, tmp_path):
    started = {"status": "HOLD", "summary": {"pending": 2, "denominator": 3}}
    with pytest.raises(AssertionError, match="RESUME"):
        run_cell(notebook, tmp_path / "a", ["a", "b", "c"], {"lead3": started, "lexrank": None, "bart": None, "led": None},
                 resume=False, execute_results={})
    calls, _ = run_cell(notebook, tmp_path / "b", ["a", "b", "c"], {"lead3": started, "lexrank": None, "bart": None, "led": None},
                        resume=True, execute_results={})
    assert calls[0] == ("lead3", True)


def test_run_cell_refuses_to_start_without_a_successful_preflight(notebook, tmp_path):
    env_notebook = json.loads(json.dumps(notebook))
    source = code_cells(env_notebook)[4]
    assert "PREFLIGHT_OK" in source
    with pytest.raises(AssertionError, match="preflight"):
        exec(compile(source, "run-cell", "exec"), {"DEPENDENCIES_READY": True, "PREFLIGHT_OK": False})


def test_start_gate_rejects_malformed_readiness_hash_before_any_ledger(notebook, tmp_path):
    import hashlib
    import zipfile
    upload = code_cells(notebook)[1]
    output, bundle = tmp_path / "out", tmp_path / "bundle"
    output.mkdir()
    bundle.mkdir()
    zip_path = tmp_path / "z.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("selection_manifest.json", '{"files": {}}')
    manifest_sha = hashlib.sha256(b'{"files": {}}').hexdigest()
    bad = json.dumps({"manifest_sha256": manifest_sha, "readiness_receipt_v2_sha256": "short", "authorized_by": "user",
                      "authorized_on": "2026-10-24", "statement": "start"}).encode()
    holds = []
    env = {"files": SimpleNamespace(upload=lambda: {str(zip_path): b"", "start_authorization.json": bad}), "Path": Path,
           "zipfile": zipfile, "OUTPUT": output, "BUNDLE": bundle, "json": json, "bootstrap_hold": holds.append,
           "EXPECTED_ZIP_SHA256": hashlib.sha256(zip_path.read_bytes()).hexdigest(), "EXPECTED_MANIFEST_SHA256": manifest_sha,
           "sha": lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(), "sys": __import__("sys")}
    with pytest.raises(SystemExit):
        exec(compile(upload, "upload-cell", "exec"), env)
    assert holds and "authorization" in holds[0] and "begin_session" not in env
