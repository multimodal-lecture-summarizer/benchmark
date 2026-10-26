"""Dry run of scoring session 3 with fake scorer dependencies, a fake clock and a ledger shaped like the real one.

No GPU, no model, no real source/reference/output: every ID is `fixture:*` and lives under tmp_path.
"""
import functools
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts import tib_selection300_scorer_notebook as notebook_writer
from experiments.scripts import tib_selection300_scorer_validation as selection
from experiments.scripts import tib_stage_session as stage_session
from experiments.scripts.tib_pilot_bundle import SEALED
from experiments.scripts.tib_stage_session import begin_session, finish_session, record_setup
from selection_scoring_fixtures import (
    PROFILES, build_bundle, install_fakes, make_assets, make_ledger, make_world, observation,
)
from test_tib_pilot40_scorer_runner import package as pilot_package  # noqa: F401  (Pilot40 regression fixture)

SETUP_SECONDS = 0.3 * 3600
EXPORT_RESERVE_SECONDS = 0.3 * 3600


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return make_world(tmp_path_factory.mktemp("dry-run-world"))


@pytest.fixture(scope="module")
def built(world, tmp_path_factory):
    receipt, local, registry = build_bundle(world, tmp_path_factory.mktemp("dry-run-built"))
    return SimpleNamespace(receipt=receipt, bundle=local / "bundle", registry=registry, archive=local / "tib-selection300-scoring-261024-v1.zip")


def make_env(world, built, tmp_path, monkeypatch, scale=1.0, ledger_open=True):
    fakes = install_fakes(monkeypatch, runner, world, scale)
    ledger = make_ledger(world, tmp_path / "ledger.json", third_open=ledger_open)
    return SimpleNamespace(bundle=built.bundle, output=tmp_path / "scoring", assets=make_assets(tmp_path / "assets"),
                           ledger=ledger, fakes=fakes, calls=fakes.calls, view_calls=fakes.view_calls, clock=fakes.clock)


def run(env, **kwargs):
    arguments = dict(validator=selection.validate_selection_scoring_bundle, order=selection.interleaved_order,
                     stage=selection.SELECTION_STAGE, ledger=env.ledger, **env.fakes.options)
    arguments.update(kwargs)
    return runner.run(env.bundle, env.output, env.assets, **arguments)


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def deadline_hours(env):
    state = json.loads(Path(env.ledger).read_text())
    return (state["session_limit_seconds"] * 0.85 - SETUP_SECONDS - EXPORT_RESERVE_SECONDS) / 3600


def test_fixture_ids_never_touch_the_sealed_cohort(world):
    cohort = json.loads((SEALED / "development_cohort.json").read_text(encoding="utf-8"))
    sealed = set(cohort["selected_ids"]["selection"]) | set(cohort["selected_ids"]["pilot"])
    assert not sealed & set(world.ids) and all(i.startswith("fixture:") for i in world.ids)


@pytest.fixture(scope="module")
def base_run(world, built, tmp_path_factory):
    """One complete session at Pilot40 mean speed, reused by the scenarios that only read its outcome."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        tmp = tmp_path_factory.mktemp("base-run")
        env = make_env(world, built, tmp, monkeypatch)
        result = run(env, wall_hours=deadline_hours(env))
        yield SimpleNamespace(env=env, result=result, simulated=env.clock.offset)
    finally:
        monkeypatch.undo()


# --- 1. a full session fits -------------------------------------------------------------------------------------
def settle_ledger(env, simulated_seconds):
    """Charge the setup, then close session 3 at the simulated end of scoring, as the notebook would."""
    record_setup(env.ledger, cpu_seconds=60.0, transfer_bytes=5 * 1024**3, wall_seconds=SETUP_SECONDS)
    return finish_session(env.ledger, "scoring_evidence_exported",
                          observation=observation("boot-3", 100.0 + SETUP_SECONDS + simulated_seconds))


def assert_session_inside_the_ceilings(env, simulated_seconds):
    closed = settle_ledger(env, simulated_seconds)
    allocation = closed["allocation"]
    assert closed["gpu_seconds"] <= allocation["total_gpu_hours"] * 3600
    assert len(closed["session_runs"]) == 3 <= allocation["max_sessions"]
    assert closed["session_runs"][-1]["measured_wall_seconds"] < 4.25 * 3600
    return closed


def test_complete_session_at_pilot40_mean_speed(base_run):
    result = base_run.result
    assert result["orchestration_checks_passed"] and result["views_status"] == "COMPLETE"
    assert result["successful_metric_records"] == 1197 and result["failed_generation_cells"] == 3
    assert result["reasons"] == ["TEST_DEPENDENCY_INJECTION_NOT_ACTUAL_COLAB_EVIDENCE"]  # never a PASS from fakes
    assert result["delivered_status"] == "HOLD" and result["scorer_selection300_ready"] is False
    assert 1.2 * 3600 < base_run.simulated < 2.0 * 3600   # near the 1.42 h base estimate
    assert_session_inside_the_ceilings(base_run.env, base_run.simulated)


def test_complete_session_at_conservative_speed(world, built, tmp_path, monkeypatch, base_run):
    scale = 3.0 * 3600 / base_run.simulated   # conservative estimate: 3.0 h for 4 x 300 cells including views
    env = make_env(world, built, tmp_path, monkeypatch, scale=scale)
    result = run(env, wall_hours=deadline_hours(env))
    assert result["orchestration_checks_passed"] and result["views_status"] == "COMPLETE"
    assert 2.9 * 3600 < env.clock.offset < 3.1 * 3600
    assert_session_inside_the_ceilings(env, env.clock.offset)


def test_the_stress_case_is_not_hidden(world, built, tmp_path, monkeypatch, base_run):
    """4.2 h of scoring does not fit the 4.25 h deadline once setup and export are reserved: an honest partial HOLD."""
    env = make_env(world, built, tmp_path, monkeypatch, scale=4.2 * 3600 / base_run.simulated)
    result = run(env, wall_hours=deadline_hours(env))
    assert not result["orchestration_checks_passed"] and result["delivered_status"] == "HOLD"
    assert result["successful_metric_records"] + sum(
        r["scoring_status"] == "not_attempted" for r in lines(env.output / "metrics.jsonl")) == 1197


# --- 2. the session opens on the generation hash only -----------------------------------------------------------
def test_session_opens_only_with_the_generation_hash_and_a_free_slot(world, built, tmp_path):
    ledger = make_ledger(world, tmp_path / "ledger.json", closed_sessions=2)
    scoring_hash = built.receipt["manifest_sha256"]
    assert scoring_hash != world.manifest_sha
    before = ledger.read_bytes()
    with pytest.raises(ValueError, match="allocation/bundle binding mismatch"):
        begin_session(ledger, world.allocation, scoring_hash, observation=observation("boot-3", 100.0))
    assert ledger.read_bytes() == before
    state = json.loads(before)
    assert selection.check_ledger_ready(state, world.allocation, world.manifest_sha)["sessions_used"] == 2
    with pytest.raises(ValueError, match="another bundle"):
        selection.check_ledger_ready(state, world.allocation, scoring_hash)
    opened = begin_session(ledger, world.allocation, world.manifest_sha, observation=observation("boot-3", 100.0))
    assert opened["session_status"] == "active" and len(opened["session_runs"]) == 3
    with pytest.raises(ValueError, match="active session"):
        selection.check_ledger_ready(json.loads(ledger.read_bytes()), world.allocation, world.manifest_sha)


def test_no_fourth_session_and_an_open_one_blocks_the_precheck(world, tmp_path):
    ledger = make_ledger(world, tmp_path / "ledger.json", closed_sessions=3)
    with pytest.raises(ValueError, match="session count exhausted"):
        begin_session(ledger, world.allocation, world.manifest_sha, observation=observation("boot-4", 100.0))
    with pytest.raises(ValueError, match="No authorized session"):
        selection.check_ledger_ready(json.loads(ledger.read_bytes()), world.allocation, world.manifest_sha)


# --- 3. wrong runtime is refused before the ledger ----------------------------------------------------------------
def notebook_sources(world, built, tmp_path):
    root = tmp_path / "nb-root"
    (root / "experiments/notebooks").mkdir(parents=True)
    registry = tmp_path / "nb-registry"
    registry.mkdir()
    (registry / "preparation_receipt.json").write_text(json.dumps(built.receipt))
    path = notebook_writer.create(registry=registry, root=root, expected_evidence_sha=world.archive_sha)["path"]
    notebook = json.loads(Path(path).read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]


def cell_with(sources, needle):
    return next(s for s in sources if needle in s)


def test_cpu_runtime_stops_before_the_ledger_and_costs_no_session(world, built, tmp_path):
    sources = notebook_sources(world, built, tmp_path)
    ledger = make_ledger(world, tmp_path / "ledger.json", closed_sessions=2)
    before = ledger.read_bytes()
    namespace = {"subprocess": SimpleNamespace(
        run=lambda *a, **k: SimpleNamespace(returncode=0, stdout=""), SubprocessError=RuntimeError)}
    with pytest.raises(SystemExit, match="ledger was not touched"):
        exec(cell_with(sources, "nvidia-smi"), namespace)
    assert ledger.read_bytes() == before and "begin_session" not in namespace and "LEDGER" not in namespace


# --- 4. deadline in the middle of the delivered pass ------------------------------------------------------------
def test_deadline_mid_pass_is_an_honest_partial_with_balanced_profiles(world, built, tmp_path, monkeypatch):
    env = make_env(world, built, tmp_path, monkeypatch)
    result = run(env, wall_hours=1000 / 3600)
    assert result["delivered_status"] == "HOLD" and "session_deadline" in result["reasons"]
    assert result["views_status"] == "NOT_STARTED" and not env.view_calls
    metrics = lines(env.output / "metrics.jsonl")
    assert len(metrics) == 1200 and result["expected_scoreable"] == 1197          # the denominator stays whole
    done = [r for r in metrics if r["scoring_status"] == "completed"]
    pending = [r for r in metrics if r["scoring_status"] == "not_attempted"]
    assert 0 < len(done) < 1197 and len(done) + len(pending) == 1197 and result["successful_metric_records"] == len(done)
    assert all(all(v is None for v in r["metrics"].values()) for r in pending)
    failed_records = {r["record_id"] for r in metrics if r["scoring_status"] == "not_scoreable_generation_failed"}
    counts = [sum(r["profile_id"] == p for r in done) for p in PROFILES]
    assert max(counts) - min(counts) <= 1 + len(failed_records & {r["record_id"] for r in done})
    assert not result["orchestration_checks_passed"]


# --- 5. interruption and resume -----------------------------------------------------------------------------------
def test_resume_after_a_partial_run_holds_without_filling_holes(world, built, tmp_path, monkeypatch):
    env = make_env(world, built, tmp_path, monkeypatch)
    run(env, wall_hours=1000 / 3600)
    first = len(env.calls)
    with pytest.raises(ValueError, match="use --resume"):
        runner.ScoreCheckpoints(env.output / "checkpoints", {}, resume=False)
    result = run(env, resume=True, wall_hours=deadline_hours(env))
    assert result["delivered_status"] == "HOLD" and not result["orchestration_checks_passed"]
    assert any("Required resume checkpoint missing" in reason for reason in result["reasons"])
    assert len(env.calls) == first and not env.view_calls      # nothing re-scored, nothing new attempted


def test_resume_of_a_complete_cache_replays_without_new_calls(world, built, tmp_path, monkeypatch):
    env = make_env(world, built, tmp_path, monkeypatch)
    run(env, wall_hours=deadline_hours(env))
    scored, views = len(env.calls), len(env.view_calls)
    result = run(env, resume=True, wall_hours=deadline_hours(env))
    assert result["orchestration_checks_passed"] and len(env.calls) == scored and len(env.view_calls) == views
    costs = json.loads((env.output / "cost_evidence.json").read_text())
    assert costs["reused_records"] == 1197 and costs["new_metric_calls"] == 0


# --- 6. failed cells ---------------------------------------------------------------------------------------------------
def test_failed_cells_never_reach_the_scorer_and_stay_in_the_denominator(base_run):
    env, result = base_run.env, base_run.result
    assert len(env.calls) == 1197 and all(summary for summary, _ in env.calls)
    metrics = lines(env.output / "metrics.jsonl")
    failed = [r for r in metrics if r["scoring_status"] == "not_scoreable_generation_failed"]
    assert len(metrics) == 1200 and len(failed) == 3 and {r["profile_id"] for r in failed} == {"led"}
    assert all("AdapterFailure" in r["failures"]["record"] and all(v is None for v in r["metrics"].values()) for r in failed)
    views = lines(env.output / "view_metrics.jsonl")
    assert len(views) == 1197 and not {r["sample_id"] for r in failed} & {v["sample_id"] for v in views}


# --- 7. export and close are idempotent -------------------------------------------------------------------------------
class FakeFiles:
    def __init__(self): self.downloaded = []
    def download(self, path): self.downloaded.append(Path(path))


def export_namespace(world, built, tmp_path, ledger):
    store = tmp_path / "drive" / "STORE"
    output, bundle = store / "scoring", tmp_path / "work" / "scoring"
    output.mkdir(parents=True)
    bundle.mkdir(parents=True)
    (output / "scorer_selection300_receipt.json").write_text("{}")
    (bundle / "scoring_outputs.jsonl").write_text("PRIVATE TEXT")
    (bundle / "package_manifest.json").write_text("{}")
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return {"Path": Path, "sys": sys, "zipfile": zipfile, "json": json, "STORE": store, "OUTPUT": output, "BUNDLE": bundle,
            "LEDGER": ledger, "sha": sha, "files": FakeFiles(),
            "finish_session": functools.partial(finish_session, observation=observation("boot-3", 100.0 + 5000.0))}


def test_export_never_touches_the_ledger_and_close_acts_once(world, built, tmp_path, monkeypatch):
    monkeypatch.setattr(stage_session, "finish_session", functools.partial(finish_session, observation=observation("boot-3", 5100.0)))
    sources = notebook_sources(world, built, tmp_path)
    ledger = make_ledger(world, tmp_path / "ledger.json", third_open=True)
    namespace = export_namespace(world, built, tmp_path, ledger)
    export_cell, close_cell = cell_with(sources, "zipfile.ZipFile(export"), cell_with(sources, "finish_session(")
    before = ledger.read_bytes()
    exec(export_cell, namespace)
    exec(export_cell, namespace)
    assert ledger.read_bytes() == before and json.loads(before)["session_status"] == "active"
    exports = sorted(namespace["STORE"].glob("tib-selection300-scoring-evidence-*.zip"))
    assert exports
    with zipfile.ZipFile(exports[-1]) as z:
        names = z.namelist()
        assert "bundle/package_manifest.json" in names and "evidence/scorer_selection300_receipt.json" in names
        assert "ledger/resource_ledger_at_export.json" in names
        assert not any(n.endswith("scoring_outputs.jsonl") for n in names)   # sources/references stay out
        assert not any(b"PRIVATE TEXT" in z.read(n) for n in names)
    exec(close_cell, namespace)
    closed = json.loads(ledger.read_bytes())
    assert closed["session_status"] == "scoring_evidence_exported" and len(closed["session_runs"]) == 3
    exec(close_cell, namespace)                   # a second close is a no-op, not an error
    exec(export_cell, namespace)                  # exporting after the close is fine too
    assert json.loads(ledger.read_bytes()) == closed
    assert (namespace["STORE"] / "resource_ledger_after_scoring.json").exists()
    assert len(namespace["files"].downloaded) >= 4


def test_close_on_a_different_vm_leaves_the_ledger_alone_without_crashing(world, built, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(stage_session, "finish_session", functools.partial(finish_session, observation=observation("another-vm", 5000.0)))
    sources = notebook_sources(world, built, tmp_path)
    ledger = make_ledger(world, tmp_path / "ledger.json", third_open=True)
    namespace = export_namespace(world, built, tmp_path, ledger)
    namespace["finish_session"] = functools.partial(finish_session, observation=observation("another-vm", 5000.0))
    before = ledger.read_bytes()
    exec(cell_with(sources, "finish_session("), namespace)
    assert ledger.read_bytes() == before and "NOT closed" in capsys.readouterr().out


# --- 8. missing or wrong authorization ---------------------------------------------------------------------------------
def verify_namespace(world, built, tmp_path, monkeypatch, uploads):
    drive_root = tmp_path / "MyDrive"
    store = drive_root / notebook_writer.STORE_NAME
    (store / "selection").mkdir(parents=True)
    shutil.copyfile(world.archive, store / notebook_writer.EVIDENCE_NAME)
    ledger = make_ledger(world, store / "selection" / "resource_ledger.json", closed_sessions=2)
    (store / "selection" / "allocation.json").write_text(json.dumps(world.allocation))
    google = SimpleNamespace(colab=SimpleNamespace(drive=SimpleNamespace(mount=lambda path: None),
                                                  files=SimpleNamespace(upload=lambda: uploads)))
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", google.colab)
    monkeypatch.chdir(tmp_path)
    for name, data in uploads.items():
        if name.endswith(".zip"):
            Path(name).write_bytes(data)
    receipt = built.receipt
    namespace = {"Path": Path, "hashlib": hashlib, "json": json, "time": __import__("time"), "zipfile": zipfile, "sys": sys,
                 "RESUME": False, "EXPECTED_ZIP_SHA256": receipt["archive_sha256"],
                 "EXPECTED_MANIFEST_SHA256": receipt["manifest_sha256"], "GENERATION_MANIFEST_SHA256": world.manifest_sha,
                 "GENERATION_EVIDENCE_NAME": notebook_writer.EVIDENCE_NAME, "GENERATION_EVIDENCE_SHA256": world.archive_sha,
                 "BUNDLE": tmp_path / "work" / "scoring", "WORK": tmp_path / "work"}
    return namespace, ledger, store, drive_root


def authorization(built, **changes):
    value = {"manifest_sha256": built.receipt["manifest_sha256"], "scoring_readiness_receipt_sha256": "d" * 64,
             "authorized_by": "user", "authorized_on": "2026-10-24", "statement": "I authorize the selection300 scoring run."}
    value.update(changes)
    return json.dumps(value).encode()


def run_verify(world, built, tmp_path, monkeypatch, uploads):
    sources = notebook_sources(world, built, tmp_path)
    namespace, ledger, store, drive_root = verify_namespace(world, built, tmp_path, monkeypatch, uploads)
    boot = tmp_path / "boot_id"
    boot.write_text("boot-3")
    source = (cell_with(sources, "drive.mount").replace("/content/drive/MyDrive", drive_root.as_posix())
              .replace("/proc/sys/kernel/random/boot_id", boot.as_posix()))
    return namespace, ledger, source


def extracted_files(namespace):
    bundle = namespace["BUNDLE"]
    return [p for p in bundle.rglob("*") if p.is_file()] if bundle.exists() else []


def test_missing_authorization_holds_before_extraction_install_or_ledger(world, built, tmp_path, monkeypatch):
    zip_bytes = built.archive.read_bytes()
    namespace, ledger, source = run_verify(world, built, tmp_path, monkeypatch, {"scoring.zip": zip_bytes})
    before = ledger.read_bytes()
    with pytest.raises(SystemExit, match="HOLD: start_authorization_scoring.json missing"):
        exec(source, namespace)
    assert not extracted_files(namespace) and ledger.read_bytes() == before and "LEDGER" not in namespace


@pytest.mark.parametrize("changes", [
    {"authorized_by": "agent"}, {"manifest_sha256": "0" * 64}, {"scoring_readiness_receipt_sha256": "abc"},
    {"scoring_readiness_receipt_sha256": "G" * 64}, {"statement": "  "}, {"authorized_by": "user", "manifest_sha256": None}])
def test_wrong_authorization_holds_before_extraction_install_or_ledger(world, built, tmp_path, monkeypatch, changes):
    uploads = {"scoring.zip": built.archive.read_bytes(),
               "start_authorization_scoring.json": authorization(built, **changes)}
    namespace, ledger, source = run_verify(world, built, tmp_path, monkeypatch, uploads)
    before = ledger.read_bytes()
    with pytest.raises(SystemExit, match="authorization invalid"):
        exec(source, namespace)
    assert not extracted_files(namespace) and ledger.read_bytes() == before


def test_missing_field_in_authorization_holds(world, built, tmp_path, monkeypatch):
    broken = json.loads(authorization(built))
    broken.pop("authorized_on")
    uploads = {"scoring.zip": built.archive.read_bytes(), "start_authorization_scoring.json": json.dumps(broken).encode()}
    namespace, ledger, source = run_verify(world, built, tmp_path, monkeypatch, uploads)
    with pytest.raises(SystemExit, match="authorization invalid"):
        exec(source, namespace)
    assert not extracted_files(namespace)


def test_valid_authorization_verifies_everything_read_only(world, built, tmp_path, monkeypatch, capsys):
    uploads = {"scoring.zip": built.archive.read_bytes(), "start_authorization_scoring.json": authorization(built)}
    namespace, ledger, source = run_verify(world, built, tmp_path, monkeypatch, uploads)
    before = ledger.read_bytes()
    exec(source, namespace)
    assert ledger.read_bytes() == before and namespace["usage"]["sessions_used"] == 2
    assert (namespace["BUNDLE"] / "package_manifest.json").exists()
    assert "Authorization and bundle verified" in capsys.readouterr().out


def test_a_zip_that_is_not_the_prepared_bundle_is_refused(world, built, tmp_path, monkeypatch):
    uploads = {"scoring.zip": built.archive.read_bytes() + b"x", "start_authorization_scoring.json": authorization(built)}
    namespace, ledger, source = run_verify(world, built, tmp_path, monkeypatch, uploads)
    with pytest.raises(AssertionError, match="ZIP differs"):
        exec(source, namespace)
    assert not extracted_files(namespace)


# --- 9. a closed ledger session stops the runner -----------------------------------------------------------------
def test_runner_refuses_when_the_ledger_session_is_not_active(world, built, tmp_path, monkeypatch):
    env = make_env(world, built, tmp_path, monkeypatch, ledger_open=False)   # last session closed: the session-2 situation
    result = run(env, wall_hours=deadline_hours(env))
    assert result["delivered_status"] == "HOLD" and not env.calls
    assert any("no active session" in reason for reason in result["reasons"])
    assert all(r["scoring_status"] in ("not_attempted", "not_scoreable_generation_failed")
               for r in lines(env.output / "metrics.jsonl"))


def test_runner_accepts_an_active_ledger_session(base_run):
    assert not any("no active session" in reason for reason in base_run.result["reasons"])


# --- Pilot40 regression -----------------------------------------------------------------------------------------------
def common_fields(receipt):
    return {k: v for k, v in receipt.items() if k not in ("run_id", "artifact_sha256", "binding", "runtime")}


def test_generalised_runner_matches_the_default_pilot40_behaviour(pilot_package, tmp_path):
    p = pilot_package
    default = runner.run(p.root, p.output, p.assets, **p.options)
    calls_default = len(p.calls)
    explicit = runner.run(p.root, tmp_path / "second", p.assets, validator=runner.validate_pilot_bundle,
                          order=runner.run_order, stage=runner.PILOT40_STAGE, ledger=None, **p.options)
    assert common_fields(default) == common_fields(explicit) and len(p.calls) == 2 * calls_default
    assert "scorer_pilot40_ready" in default and (p.output / "scorer_pilot40_receipt.json").exists()
    assert default["scope"].startswith("Pilot40 4-profile scoring-cost measurement")


def test_same_vm_reentry_is_allowed_other_vm_is_not(world, tmp_path):
    ledger = make_ledger(world, tmp_path / "ledger.json", third_open=True)
    state = json.loads(ledger.read_bytes())
    ok = selection.check_ledger_ready(state, world.allocation, world.manifest_sha, boot_id="boot-3")
    assert ok["sessions_used"] == 3
    with pytest.raises(ValueError, match="active session"):
        selection.check_ledger_ready(state, world.allocation, world.manifest_sha, boot_id="other-vm")


def test_close_cell_imports_what_it_needs_on_a_fresh_kernel(world, built, tmp_path):
    sources = notebook_sources(world, built, tmp_path)
    close = cell_with(sources, "finish_session(")
    assert "from experiments.scripts.tib_stage_session import finish_session" in close and "sys.path.insert" in close
    assert "assert GPU_OK" in cell_with(sources, "begin_session(LEDGER")
