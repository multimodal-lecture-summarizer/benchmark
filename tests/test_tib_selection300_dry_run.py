"""Dry-run of the three-session selection300 flow with a controllable clock; no model, GPU or real source.

The neural backend is a fake that advances a shared clock by per-record costs scaled to the conservative
projection (bart 1.27 h and led 1.71 h for 300 records, scaled to the miniature). This certifies session,
resume, denominator and ledger logic only; it is not T4 evidence.
"""
import json
import time
from types import SimpleNamespace

import pytest

from selection_fixtures import REGISTRY, authorization, mini_bundle, real_allocation
from experiments.scripts import tib_selection_runtime as selection
from experiments.scripts import tib_stage_session as session
from experiments.scripts.tib_benchmark_checkpoint import restore
from experiments.scripts.tib_p4_generation_recovery import sha

N = 6
SCALE = 300 / N
# Conservative per-record seconds for 300 records (bart 1.27 h, led 1.71 h), scaled up for the miniature.
PER_RECORD = {"bart": 1.27 * 3600 / 300 * SCALE, "led": 1.71 * 3600 / 300 * SCALE}
ENVIRONMENT = {"device_name": "Tesla T4", "packages": {}, "cuda_runtime": "13", "actual_parameter_dtype": "float16",
               "runtime_dependencies": {}, "actual_attention_backend": "eager", "actual_device_map": {},
               "asset_sha256": {}, "tokenizer_class": "Fake", "device_memory_bytes": 1, "resolved_generation_config": {}}


class World:
    def __init__(self, tmp_path, monkeypatch, allocation=None):
        self.offset = 0.0
        self.bundle = tmp_path / "bundle"
        self.contract, self.rows = mini_bundle(self.bundle, monkeypatch)
        self.output = tmp_path / "selection"
        self.output.mkdir()
        self.allocation = allocation or real_allocation()
        self.auth = authorization(self.bundle)
        self.bundle_sha = sha(self.bundle / "selection_manifest.json")
        self.ledger = self.output / "resource_ledger.json"
        self.calls = []
        self.fail_records = set()
        self.interrupt_after = None
        self.boot = None
        self.per_record = dict(PER_RECORD)
        monkeypatch.setattr(selection, "validate_neural", lambda *a: {
            "technical_valid": True, "node_evidence": [], "node_decisions": [],
            "acceptance": {"status": "completed", "warnings": [], "technical_errors": []}})
        world = self

        class Pipeline:
            current = None

            def __call__(self, source, *, generate, **kwargs):
                generate.set_node_context({"layer": 0, "node": 0, "source_intervals": [[0, 1]]})
                text = generate({"input_ids": [world.index(source)]}, 4, "final")
                delivery = selection.delivery.select_delivered(text, 350)  # the real selector, so cache replay checks hold
                return {"nodes": [{"stage": "final", "layer": 0, "canonical_source_sha256": world.source_sha(source),
                                   "output_text": text, "output_sha256": __import__("hashlib").sha256(text.encode()).hexdigest()}],
                        "raw_final": text, "delivered_final": delivery["text"], "delivery": delivery}
        monkeypatch.setattr(selection.generation, "summarize_source", Pipeline())

    def index(self, source):
        return len(self.calls)

    def source_sha(self, source):
        return __import__("hashlib").sha256(source.encode()).hexdigest()

    def clock(self):
        return time.monotonic() + self.offset

    def start_session(self, boot):
        self.boot = boot
        return session.begin_session(self.ledger, self.allocation, self.bundle_sha,
                                     observation={"boot_id": boot, "monotonic": self.clock(), "epoch_ns": time.time_ns(),
                                                  "logical_cpu_count": 2}, local_working_root="/content/work")

    def end_session(self):
        return session.finish_session(self.ledger, observation={
            "boot_id": self.boot, "monotonic": self.clock(), "epoch_ns": time.time_ns(), "logical_cpu_count": 2})

    def deps(self, candidate):
        world = self

        class Backend:
            last_receipt = None

            def __call__(self, batch, maximum, stage):
                world.calls.append((candidate, len(world.calls)))
                if len(world.calls) in world.fail_records:
                    raise RuntimeError("synthetic backend failure")
                if world.interrupt_after is not None and len(world.calls) > world.interrupt_after:
                    raise KeyboardInterrupt("simulated VM loss")
                world.offset += world.per_record[candidate]
                self.last_receipt = {"generated_native_tokens": 5}
                return "A short generated sentence."
        deps = SimpleNamespace(
            validate_bundle=selection.validate_bundle,
            resources=SimpleNamespace(clock=self.clock, cpu_clock=time.process_time, boot_id=self.boot),
            environment=lambda c: ENVIRONMENT, load_assets=lambda *a: (object(), object()),
            admit_assets=lambda *a: {"test_only": True}, native_bindings=lambda *a: {},
            backend=lambda *a: Backend(),
            sample=lambda neural: __import__("contextlib").nullcontext({"wall_seconds": 0, "cpu_seconds": 0, "cuda_peak_reserved_bytes": None}))
        return deps

    def run(self, candidate, **kw):
        used = (self.clock() - json.loads(self.ledger.read_text())["session_started_monotonic"]) / 3600
        limit = json.loads(self.ledger.read_text())["session_limit_seconds"] / 3600
        return selection.run(self.bundle, self.output / candidate, candidate, wall_hours=min(5.75, limit - used),
                             allocation=self.allocation, authorization=self.auth, dependencies=self.deps(candidate), **kw)

    def session_pass(self, candidates=("lead3", "lexrank", "bart", "led"), resume=False):
        out = {}
        for candidate in candidates:
            path = self.output / candidate / "candidate_receipt.json"
            if path.exists() and not resume:
                continue
            out[candidate] = self.run(candidate, resume=(self.output / candidate).exists())
            if out[candidate]["status"] not in ("HOLD",):
                break
        return out


def ids_done(world, candidate):
    return {p.stem for p in (world.output / candidate / "records").glob("*.json")}


def test_scenario_one_session_covers_all_four_profiles_within_deadline(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.start_session("vm1")
    for candidate in ("lead3", "lexrank", "bart", "led"):
        result = w.run(candidate)
        assert result["summary"]["denominator"] == N and result["summary"]["pending"] == 0, candidate
        assert result["summary"]["successful"] == N, (candidate, result.get("error"))
    ledger = w.end_session()
    elapsed_h = ledger["completed_session_wall_seconds"] / 3600
    assert elapsed_h == pytest.approx(PER_RECORD["bart"] * N / 3600 + PER_RECORD["led"] * N / 3600, abs=0.05)
    assert elapsed_h < 5.0 * 0.85 and ledger["gpu_seconds"] <= w.allocation["total_gpu_hours"] * 3600
    assert len(w.calls) == 2 * N  # only neural nodes call the backend; CPU profiles never do


def test_scenario_interrupt_in_bart_then_resume_never_retries_the_attempted_record(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.start_session("vm1")
    w.run("lead3")
    w.interrupt_after = 3
    with pytest.raises(KeyboardInterrupt):
        w.run("bart")
    first_calls = len(w.calls)
    w.interrupt_after = None
    ledger = w.start_session("vm2")  # new VM: vm1 was never closed
    assert ledger["session_runs"][0]["status"] == "interrupted"
    assert ledger["unobserved_loss_reserve"]["wall_seconds"] == 5.0 * 3600
    result = w.run("bart", resume=True)
    assert result["summary"]["denominator"] == N and result["summary"]["pending"] == 0
    # Outside the test override this candidate is finished, so the notebook moves on to the next profile.
    assert result["terminal_status_if_real"] == "COMPLETED_WITH_FAILURES"
    cached = w.run("bart", resume=True)
    assert cached["execution_mode"] == "cached_candidate_resume" and cached["terminal_status_if_real"] == "COMPLETED_WITH_FAILURES"
    assert len(w.calls) - first_calls == N - 4  # record 4 was attempted before the loss and is not repeated
    started = [r for r in result["records"].values() if r["status"] == "started"]
    assert len(started) == 1 and started[0]["quality"] is None
    total = json.loads(w.ledger.read_text())
    assert total["gpu_seconds"] <= w.allocation["total_gpu_hours"] * 3600


def test_scenario_budget_exhaustion_reports_partial_on_the_whole_denominator(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.per_record = {"bart": 3600.0 * 1.0, "led": 3600.0 * 1.5}  # far above the conservative projection
    w.start_session("vm1")
    w.run("lead3")
    result = w.run("bart")
    if result["summary"]["pending"] == 0:
        result = w.run("led")
    assert result["summary"]["denominator"] == N and "terminal_status_if_real" not in result
    assert result["summary"]["pending"] > 0 or result["summary"]["failed_or_interrupted"] > 0
    assert all(r["quality"] is None for r in result["records"].values())
    assert result["summary"]["successful"] < N


def test_scenario_fourth_session_is_refused_and_leaves_the_ledger_unchanged(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    for boot in ("vm1", "vm2", "vm3"):
        w.start_session(boot)
        w.end_session()
    before = w.ledger.read_text()
    with pytest.raises(ValueError, match="session count exhausted"):
        w.start_session("vm4")
    assert w.ledger.read_text() == before


def test_scenario_final523_allocation_allows_four_sessions_of_5_25_hours(tmp_path, monkeypatch):
    allocation = json.loads((REGISTRY / "compute_budget_final523.json").read_text())
    w = World(tmp_path, monkeypatch, allocation=allocation)
    for boot in ("vm1", "vm2", "vm3", "vm4"):
        ledger = w.start_session(boot)
        assert ledger["session_limit_seconds"] == 5.25 * 3600
        w.end_session()
    with pytest.raises(ValueError, match="session count exhausted"):
        w.start_session("vm5")


def test_scenario_missing_authorization_stops_before_the_ledger_or_a_model(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.start_session("vm1")
    w.auth = None
    deps = w.deps("bart")
    deps.environment = lambda _: pytest.fail("no environment or model without authorization")
    before = w.ledger.read_text()
    result = selection.run(w.bundle, w.output / "bart", "bart", wall_hours=4.0, allocation=w.allocation,
                           authorization=None, dependencies=deps)
    assert result["status"] == "HOLD" and "authorization" in result["error"].lower()
    assert w.ledger.read_text() == before and not (w.output / "bart").exists()


def test_scenario_one_backend_failure_is_isolated_and_never_retried(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.start_session("vm1")
    w.fail_records = {3}
    result = w.run("bart")
    assert result["summary"]["denominator"] == N and result["summary"]["failed_or_interrupted"] == 1
    assert result["summary"]["successful"] == N - 1
    failed = next(r for r in result["records"].values() if r["status"] == "failed")
    assert "synthetic backend failure" in failed["error"] and failed["quality"] is None
    calls_before = len(w.calls)
    again = w.run("bart", resume=True)
    assert len(w.calls) == calls_before and again["execution_mode"] == "cached_candidate_resume"


def test_scenario_complete_cache_replays_identically_without_generation(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    w.start_session("vm1")
    first = w.run("bart")
    calls = len(w.calls)
    second = w.run("bart", resume=True)
    assert len(w.calls) == calls and second["new_generation_calls"] == 0
    assert second["execution_mode"] == "cached_candidate_resume" and second["cached_reused_records"] == N
    for identifier, record in first["records"].items():
        assert second["records"][identifier]["result"]["delivered_final"] == record["result"]["delivered_final"]


def test_no_real_selection_id_is_used_by_the_dry_run(tmp_path, monkeypatch):
    w = World(tmp_path, monkeypatch)
    path = REGISTRY.parents[1] / "datasets/tib-text-model-benchmark-v1/qualification-261019-1703/development_cohort.json"
    cohort = json.loads(path.read_text())
    assert not set(w.contract["selection_ids"]) & set(cohort["selected_ids"]["selection"])
