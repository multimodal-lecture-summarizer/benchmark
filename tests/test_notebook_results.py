"""Presentation consumes every supported payload through receipt validation."""

import hashlib
import json
import uuid

import pytest

from experiments.scripts.benchmark_artifacts import RunnerContext, _write_payload, write_run_manifest
from experiments.scripts.notebook_results import context_from_environment_record, render_artifacts


def context(tmp_path):
    return RunnerContext("full", "official", "real", tmp_path, "test_report", str(uuid.uuid4()),
                         *[hashlib.sha256(x.encode()).hexdigest() for x in ("source", "config", "deps")])


def test_environment_record_preserves_final_test_mode(tmp_path):
    values = {
        "MLS_BENCHMARK_PROFILE": "full", "MLS_RUN_NAMESPACE": "diagnostic",
        "MLS_EVIDENCE_STATUS": "real", "MLS_ARTIFACT_ROOT": str(tmp_path),
        "MLS_NOTEBOOK_ID": "01a_asr_model_benchmark", "MLS_RUN_ID": str(uuid.uuid4()),
        "MLS_SOURCE_SHA256": hashlib.sha256(b"source").hexdigest(),
        "MLS_CONFIG_SHA256": hashlib.sha256(b"config").hexdigest(),
        "MLS_DEPENDENCY_STATE_SHA256": hashlib.sha256(b"deps").hexdigest(),
        "MLS_ASR_EVALUATION_MODE": "final_test",
    }
    assert context_from_environment_record(values).evaluation_mode == "final_test"


@pytest.mark.parametrize("suffix,content", [(".csv", "candidate,wer\na,0.2\n"),
                                             (".tsv", "candidate\twer\na\t0.2\n")])
def test_render_tabular_artifacts(tmp_path, monkeypatch, suffix, content):
    ctx = context(tmp_path)
    _write_payload(ctx, "scores", content, suffix, 1, 1)
    write_run_manifest(ctx)
    shown = []
    monkeypatch.setattr("IPython.display.display", lambda item: shown.append(item))
    render_artifacts(ctx, ["scores"])
    tables = [item for item in shown if hasattr(item, "columns")]
    assert len(tables) == 1
    assert tables[0].iloc[0]["wer"] == 0.2


def test_markdown_rejects_wrong_run_identity(tmp_path):
    ctx = context(tmp_path)
    _write_payload(ctx, "report", "# report\n", ".md", 1, 1)
    write_run_manifest(ctx)
    path = ctx.namespace_root / "report.receipt.json"
    receipt = json.loads(path.read_text())
    receipt["run_id"] = str(uuid.uuid4())
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="run_id"):
        render_artifacts(ctx, ["report"])
