"""Tests for manifest-driven notebook execution planning."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

import nbformat
import pytest

from benchmarks.scripts.execute_all_notebooks import (
    ManifestError,
    _entry_config_sha256,
    apply_dataset_selector,
    build_plan,
    can_resume,
    execute_notebook,
    claim_dataset_execution_scope,
    load_manifest,
    main,
    notebook_source_sha256,
    select_entries,
    topological_order,
    validate_dataset_namespace_evidence,
    validate_produced_artifacts,
    validate_required_artifacts,
)




def _fixture_manifest():
    """Minimal full-profile entries for executor behavior, not active notebooks."""
    base = {
        "group": "00", "responsibility": "fixture", "profiles": ["full"],
        "timeout_seconds": 30, "network_policy": "none",
        "expected_schema_version": 1,
    }
    first = {**base, "id": "00a_environment_preflight", "task_id": "FIXTURE_ENV",
             "path": "experiments/notebooks/fixture_environment.ipynb",
             "runner": "benchmarks.runners.fixture_environment",
             "requires": [], "produces": ["environment.profile"]}
    second = {**base, "id": "00b_dataset_feasibility", "task_id": "FIXTURE_DATA",
              "path": "experiments/notebooks/fixture_dataset.ipynb",
              "runner": "benchmarks.runners.fixture_dataset",
              "requires": ["environment.profile"], "produces": ["dataset.profile"]}
    return {"official_default_profile": "full", "notebooks": [first, second]}


def test_unknown_selector_fails_closed():
    with pytest.raises(ManifestError, match="No notebook matches"):
        select_entries(load_manifest(), notebook="does-not-exist")


def test_topological_order_rejects_cycle():
    entries = [
        {"id": "a", "requires": ["b.out"], "produces": ["a.out"]},
        {"id": "b", "requires": ["a.out"], "produces": ["b.out"]},
    ]
    with pytest.raises(ManifestError, match="cycle"):
        topological_order(entries)


def test_topological_order_preserves_manifest_order_when_dependencies_allow():
    entries = [
        {"id": "a", "requires": [], "produces": ["a.out"]},
        {"id": "b", "requires": ["a.out"], "produces": ["b.out"]},
        {"id": "c", "requires": [], "produces": ["c.out"]},
    ]
    assert [entry["id"] for entry in topological_order(entries)] == ["a", "b", "c"]


def test_malformed_manifest_returns_controlled_cli_error(tmp_path, capsys):
    manifest_path = tmp_path / "malformed.yaml"
    manifest_path.write_text("[", encoding="utf-8")
    assert main(["--manifest", str(manifest_path), "--list"]) == 2
    assert "[FAIL] Cannot load notebook manifest" in capsys.readouterr().out


def test_required_artifact_receipt_validates_schema_status_profile_and_hash(tmp_path):
    entry = deepcopy(_fixture_manifest()["notebooks"][1])
    artifact_id = entry["requires"][0]
    entry["requires"] = [artifact_id]
    payload = tmp_path / "official" / "full" / "payload.json"
    payload.parent.mkdir(parents=True)
    payload.write_text('{"row": 1}', encoding="utf-8")
    import hashlib
    import json

    receipt = {
        "artifact_id": artifact_id,
        "schema_version": 1,
        "profile": "full",
        "run_namespace": "official",
        "status": "real",
        "payload_path": "official/full/payload.json",
        "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        "record_count": 1,
        "denominator": 1,
        "producer_notebook_id": "00a_environment_preflight",
        "run_id": "00000000-0000-4000-8000-000000000001",
        "source_sha256": hashlib.sha256(b"fixture-source").hexdigest(),
        "config_sha256": hashlib.sha256(b"fixture-config").hexdigest(),
        "dependency_state_sha256": hashlib.sha256(b"fixture-dependency").hexdigest(),
    }
    receipt_path = tmp_path / "official" / "full" / f"{artifact_id}.receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert validate_required_artifacts(entry, tmp_path, "full", "official") == []
    receipt["status"] = "proxy"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any(
        "official artifact status must be real" in error
        for error in validate_required_artifacts(entry, tmp_path, "full", "official")
    )
    receipt["status"] = "real"
    payload.write_bytes(b"")
    receipt["sha256"] = hashlib.sha256(payload.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert any(
        "payload is missing or empty" in error
        for error in validate_required_artifacts(entry, tmp_path, "full", "official")
    )


def test_produced_artifacts_require_receipts_and_runner_manifest(tmp_path):
    entry = deepcopy(_fixture_manifest()["notebooks"][0])
    context = {
        "run_id": "run-1",
        "status": "real",
        "source_sha256": hashlib.sha256(b"fixture-source").hexdigest(),
        "config_sha256": hashlib.sha256(b"fixture-config").hexdigest(),
        "dependency_state_sha256": hashlib.sha256(b"fixture-dependency").hexdigest(),
    }
    errors = validate_produced_artifacts(entry, tmp_path, "full", "official", context)
    assert any("missing receipt" in error for error in errors)
    assert any("run manifest missing" in error for error in errors)


def test_profile_and_namespace_are_propagated_to_kernel(tmp_path, monkeypatch):
    # Test the unset-environment case independently of an offline parent notebook.
    monkeypatch.delenv("HF_DATASETS_OFFLINE", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    notebook = tmp_path / "source.ipynb"
    destination = tmp_path / "executed.ipynb"
    notebook.write_text(
        '{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}', encoding="utf-8"
    )
    captured = {}

    class FakeClient:
        def __init__(self, nb, **kwargs):
            self.nb = nb

        def execute(self, **kwargs):
            captured.update(kwargs["env"])

    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.NotebookClient", FakeClient)
    entry = deepcopy(_fixture_manifest()["notebooks"][0])
    ok, _, error = execute_notebook(
        entry, notebook, destination, 30, "full", "diagnostic", tmp_path,
        {
            "run_id": "run-1",
            "status": "dry",
            "source_sha256": hashlib.sha256(b"fixture-source").hexdigest(),
            "config_sha256": hashlib.sha256(b"fixture-config").hexdigest(),
            "dependency_state_sha256": hashlib.sha256(b"fixture-dependency").hexdigest(),
        },
    )
    assert ok and error is None
    assert captured["MLS_BENCHMARK_PROFILE"] == "full"
    assert captured["MLS_RUN_NAMESPACE"] == "diagnostic"
    assert captured["MLS_NOTEBOOK_ID"] == entry["id"]
    assert captured["MLS_ARTIFACT_ROOT"] == str(tmp_path.resolve())
    assert captured["MLS_DATASET_FILTER"] == ""
    assert captured["HF_DATASETS_OFFLINE"] == ""
    assert captured["HF_HUB_OFFLINE"] == ""


def test_resume_rejects_empty_or_unreceipted_output(tmp_path):
    entry = deepcopy(_fixture_manifest()["notebooks"][0])
    source = tmp_path / "source.ipynb"
    destination = tmp_path / "output.ipynb"
    source.write_text(
        '{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}', encoding="utf-8"
    )
    destination.write_bytes(b"")
    assert can_resume(
        entry, source, destination, "full", "official", "dependency-hash", "real", "produced-hash"
    )[0] is False


def test_executor_does_not_overwrite_source_notebook(tmp_path, monkeypatch):
    manifest = _fixture_manifest()
    entry = deepcopy(manifest["notebooks"][0])
    source = tmp_path / "source.ipynb"
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("pass")]), source)
    entry["path"] = str(source)
    before = source.read_bytes()
    runner_source = tmp_path.joinpath(*entry["runner"].split(".")).with_suffix(".py")
    runner_source.parent.mkdir(parents=True, exist_ok=True)
    runner_source.write_text("# fixture runner\n", encoding="utf-8")

    def fake_execute(
        entry_value, source_path, destination, timeout, profile, run_namespace,
        artifact_root, run_context,
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            '{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}', encoding="utf-8"
        )
        return True, 0.1, None

    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.execute_notebook", fake_execute)
    monkeypatch.setattr(
        "benchmarks.scripts.execute_all_notebooks.validate_produced_artifacts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "benchmarks.scripts.execute_all_notebooks.produced_state_sha256",
        lambda *args, **kwargs: "produced-state",
    )
    monkeypatch.setattr(
        "benchmarks.scripts.execute_all_notebooks.select_entries", lambda *args, **kwargs: [entry]
    )
    monkeypatch.setattr(
        "benchmarks.scripts.execute_all_notebooks.load_manifest", lambda *args, **kwargs: manifest
    )
    output_root = tmp_path / "outputs"
    assert main([
        "--notebook", entry["id"], "--output-root", str(output_root),
        "--artifact-root", str(tmp_path / "artifacts"),
    ]) == 0
    assert source.read_bytes() == before
    executed = output_root / "official" / "full" / f"{entry['id']}.ipynb"
    assert executed.is_file()
    assert executed.with_suffix(".run.json").is_file()


def test_source_identity_ignores_outputs_but_tracks_code_and_contract(tmp_path):
    source = tmp_path / "source.ipynb"
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_code_cell("print('first')")],
        metadata={"experiment_contract": {"notebook_id": "sample", "schema_version": 1}},
    )
    nbformat.write(notebook, source)
    first = notebook_source_sha256(source)
    notebook.cells[0].outputs = [nbformat.v4.new_output("stream", text="first\n")]
    notebook.cells[0].execution_count = 3
    notebook.metadata["benchmark_execution"] = {"status": "validated"}
    nbformat.write(notebook, source)
    assert notebook_source_sha256(source) == first
    notebook.cells[0].source = "print('second')"
    nbformat.write(notebook, source)
    assert notebook_source_sha256(source) != first
    second = notebook_source_sha256(source)
    notebook.metadata["experiment_contract"]["schema_version"] = 2
    nbformat.write(notebook, source)
    assert notebook_source_sha256(source) != second


def test_in_place_execution_clears_stale_outputs_and_saves_failure(tmp_path, monkeypatch):
    source = tmp_path / "source.ipynb"
    notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("print('new')")])
    notebook.cells[0].outputs = [nbformat.v4.new_output("stream", text="stale\n")]
    notebook.cells[0].execution_count = 99
    nbformat.write(notebook, source)
    source_hash = notebook_source_sha256(source)

    class FailingClient:
        def __init__(self, notebook_value, **kwargs):
            self.notebook = notebook_value

        def execute(self, **kwargs):
            self.notebook.cells[0].outputs = [nbformat.v4.new_output("stream", text="partial\n")]
            self.notebook.cells[0].execution_count = 1
            raise RuntimeError("fixture kernel failure")

    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.NotebookClient", FailingClient)
    entry = deepcopy(_fixture_manifest()["notebooks"][0])
    context = {
        "run_id": "fixture-run", "profile": "full", "run_namespace": "diagnostic",
        "status": "dry", "source_sha256": source_hash,
        "config_sha256": hashlib.sha256(b"config").hexdigest(),
        "dependency_state_sha256": hashlib.sha256(b"dependency").hexdigest(),
    }
    ok, _, error = execute_notebook(
        entry, source, source, 30, "full", "diagnostic", tmp_path, context
    )
    assert not ok and "fixture kernel failure" in error
    saved = nbformat.read(source, as_version=4)
    assert saved.cells[0].outputs[0].text == "partial\n"
    assert saved.cells[0].execution_count == 1
    assert saved.metadata["benchmark_execution"]["status"] == "failed"
    assert notebook_source_sha256(source) == source_hash
    assert not source.with_suffix(".run.json").exists()


def test_cli_default_destination_is_canonical_source(tmp_path, monkeypatch):
    manifest = _fixture_manifest()
    entry = deepcopy(manifest["notebooks"][0])
    source = tmp_path / "experiments" / "notebooks" / f"{entry['id']}.ipynb"
    source.parent.mkdir(parents=True)
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("pass")]), source)
    entry["path"] = str(source.relative_to(tmp_path))
    runner = tmp_path.joinpath(*entry["runner"].split(".")).with_suffix(".py")
    runner.parent.mkdir(parents=True)
    runner.write_text("# fixture runner\n", encoding="utf-8")
    destinations = []

    def fake_execute(entry_value, source_path, destination, *args):
        destinations.append(destination)
        assert source_path == destination == source
        return True, 0.0, None

    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.select_entries", lambda *args, **kwargs: [entry])
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.load_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.execute_notebook", fake_execute)
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.validate_produced_artifacts", lambda *args: [])
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks.produced_state_sha256", lambda *args: "produced")
    monkeypatch.setattr("benchmarks.scripts.execute_all_notebooks._mark_notebook_run", lambda *args: None)
    assert main(["--notebook", entry["id"], "--artifact-root", str(tmp_path / "artifacts")]) == 0
    assert destinations == [source]
    assert source.with_suffix(".run.json").is_file()
