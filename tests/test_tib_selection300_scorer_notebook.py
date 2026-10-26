"""The generated scoring notebook is checked for syntax, ordering of its gates and absence of a loose close cell."""
import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_selection300_scorer_notebook as writer

PREPARED = {"archive_sha256": "a" * 64, "manifest_sha256": "b" * 64, "generation_bundle_manifest_sha256": "c" * 64,
            "generation_evidence_zip_sha256": writer.EVIDENCE_SHA256, "rows": 1200, "scoreable_rows": 1197, "failed_rows": 3}


@pytest.fixture(scope="module")
def notebook(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("scoring-notebook")
    registry = tmp / "registry"
    registry.mkdir()
    (tmp / "experiments/notebooks").mkdir(parents=True)
    (registry / "preparation_receipt.json").write_text(json.dumps(PREPARED))
    return json.loads(Path(writer.create(registry=registry, root=tmp)["path"]).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sources(notebook):
    return ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]


def index_of(sources, needle):
    return next(i for i, s in enumerate(sources) if needle in s)


def test_cells_parse_and_carry_no_execution_claim(notebook, sources):
    assert len(sources) == 9
    for cell in (c for c in notebook["cells"] if c["cell_type"] == "code"):
        ast.parse("".join(cell["source"]))
        assert cell["execution_count"] is None and cell["outputs"] == []
    assert not any("@@" in s for s in sources)


def test_exactly_one_user_setting(sources):
    assert sum(s.count("RESUME = ") for s in sources) == 1 and sources[0].count("RESUME = ") == 1
    assert "RESUME = False" in sources[0]


def test_gpu_gate_precedes_drive_and_ledger(sources):
    gate = index_of(sources, "nvidia-smi")
    assert gate < index_of(sources, "drive.mount") < index_of(sources, "begin_session(")
    assert "Path(" in sources[0] and "drive" not in sources[0].replace("drive.", "")  # config touches no Drive
    assert "LEDGER" not in sources[0] and "LEDGER" not in sources[gate]


def test_authorization_is_checked_before_extraction_install_and_ledger(sources):
    verify = sources[index_of(sources, "drive.mount")]
    assert verify.index("authorized_by") < verify.index("extractall") < verify.index("LEDGER.exists()")
    assert "scoring_readiness_receipt_sha256" in verify and "start_authorization_scoring.json" in verify
    assert "begin_session" not in verify and "record_setup" not in verify and "finish_session" not in verify
    assert index_of(sources, "begin_session(") < index_of(sources, "pip")  # install only after the authorized session opens


def test_session_opens_with_the_generation_hash_not_the_scoring_one(sources):
    opened = sources[index_of(sources, "begin_session(")]
    call = opened[opened.index("begin_session(LEDGER"):]
    assert "GENERATION_MANIFEST_SHA256" in call.split("\n")[0] and "EXPECTED_MANIFEST_SHA256" not in call
    assert repr("c" * 64) in sources[0] and repr("b" * 64) in sources[0] and repr("a" * 64) in sources[0]


def test_only_the_last_cell_closes_the_session_and_only_while_active(sources):
    closers = [i for i, s in enumerate(sources) if "finish_session(" in s]
    assert closers == [len(sources) - 1]
    close = sources[-1]
    assert close.count("finish_session(") == 1 and "session_status'] == 'active'" in close
    export = sources[index_of(sources, "zipfile.ZipFile(export")]
    assert not any(token in export for token in ("finish_session", "begin_session", "record_setup", "write_bytes(LEDGER"))
    assert "scoring_outputs.jsonl" in export  # references/sources never travel back in the evidence ZIP


def test_runner_call_uses_ledger_stage_and_headroom(sources):
    run = sources[index_of(sources, "tib_pilot40_scorer_runner")]
    for token in ("'--stage', 'selection300'", "'--ledger', str(LEDGER)", "EXPORT_RESERVE_SECONDS", "SESSION_DEADLINE_SECONDS",
                  "scorer_selection300_receipt.json"):
        assert token in run
    assert "session_headroom_fraction" in sources[index_of(sources, "begin_session(")]


def test_no_generation_or_qwen_in_code(sources):
    text = "\n".join(sources).lower()
    assert "qwen" not in text and "nodecheckpointgenerator" not in text and "tib_selection_runtime" not in text


def run_gpu_gate(sources, outcome):
    """Execute the real gate cell against a fake subprocess; return (raised SystemExit text or None)."""
    def fake_run(*args, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(returncode=outcome[0], stdout=outcome[1])
    namespace = {"subprocess": SimpleNamespace(run=fake_run, SubprocessError=RuntimeError)}
    try:
        exec(sources[index_of(sources, "nvidia-smi")], namespace)
    except SystemExit as stop:
        return str(stop)
    return None


@pytest.mark.parametrize("outcome", [(0, ""), (0, "Tesla V100\n"), (0, "Tesla T4\nTesla T4\n"), (9, "Tesla T4\n"),
                                     OSError("nvidia-smi missing")])
def test_wrong_runtime_stops_before_the_ledger(sources, outcome):
    message = run_gpu_gate(sources, outcome)
    assert message and message.startswith("HOLD") and "ledger was not touched" in message


def test_single_tesla_t4_passes_the_gate(sources):
    assert run_gpu_gate(sources, (0, "Tesla T4\n")) is None
