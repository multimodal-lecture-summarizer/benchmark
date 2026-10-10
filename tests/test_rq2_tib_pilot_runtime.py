"""Offline pilot execution and failure accounting; no research scores produced."""

import copy
import hashlib
import json
from dataclasses import replace

import pytest

from test_rq2_tib_pilot_design import full
from test_rq2_tib_map_batching import Backend as MapBackend
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig
from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts.rq2_tib_benchmark_bundle import generation_input
from experiments.scripts.rq2_tib_benchmark_pair import PairGenerationError, run_source_pair
from experiments.scripts.rq2_tib_pilot import evaluate_pilot, forecast_receipt, run_pilot
from experiments.scripts.rq2_tib_pilot_cohort import select_pilot
from experiments.scripts.rq2_tib_pilot_runtime import TimedPilotBackend


class Backend(MapBackend):
    device = "cpu"
    model_id = "offline-test-generator"
    tokenizer_id = "offline-byte-tokenizer"
    map_batch_size = 1

    def __init__(self, failure=None, empty=False):
        super().__init__()
        self.failure = failure
        self.empty = empty

    def generate(self, prompt, **kwargs):
        if self.failure and not self.requests:
            self.requests.append(([prompt], kwargs["max_output_tokens"]))
            raise RuntimeError(self.failure)
        if self.empty:
            self.requests.append(([prompt], kwargs["max_output_tokens"]))
            return {"text": "", "attempts": [{"status": "success",
                    "prompt_tokens": self.count_tokens(prompt), "output_tokens": 0}]}
        return super().generate(prompt, **kwargs)


@pytest.fixture
def pilot_data(full):
    return select_pilot(full)


@pytest.mark.parametrize("order", [("S1", "S3"), ("S3", "S1")])
def test_pair_executes_declared_counterbalance_order_without_references(pilot_data, order):
    bundle, _ = pilot_data
    backend, events = Backend(), []
    source = generation_input(bundle["items"][0])
    assert "reference_text" not in source
    assert "reference_sha256" not in source
    result = run_source_pair(source, backend, BenchmarkConfig(), on_event=events.append, arm_order=order)
    actual = [e["arm"] for e in events if e["stage"] == "generation"
              and e["status"] == "started" and e["step"] == "reduce"]
    assert actual == list(order) == result["arm_order"]
    reference = bundle["items"][0]["reference_text"]
    assert all(reference not in prompt for prompts, _ in backend.requests for prompt in prompts)


@pytest.mark.parametrize("order", [("S1", "S1"), ("S1",), ("S1", "S2")])
def test_invalid_arm_order_fails_before_generation(pilot_data, order):
    backend = Backend()
    with pytest.raises(ValueError, match="arm_order"):
        run_source_pair(generation_input(pilot_data[0]["items"][0]), backend,
                        BenchmarkConfig(), arm_order=order)
    assert backend.requests == []


def test_first_arm_failure_default_stops_but_pilot_attempts_second(pilot_data):
    source = generation_input(pilot_data[0]["items"][0])
    default = Backend(failure="transient test failure")
    with pytest.raises(PairGenerationError):
        run_source_pair(source, default, BenchmarkConfig())
    assert len(default.requests) == 1
    pilot = Backend(failure="transient test failure")
    result = run_source_pair(source, pilot, BenchmarkConfig(), continue_on_arm_failure=True)
    assert result["arms"]["S1"]["status"] == "failed"
    assert result["arms"]["S3"]["status"] == "completed"
    assert len(pilot.requests) > 1


def test_empty_output_is_pilot_failure_and_legacy_default_is_unchanged(pilot_data):
    source = generation_input(pilot_data[0]["items"][0])
    result = run_source_pair(source, Backend(empty=True), BenchmarkConfig(),
                             continue_on_arm_failure=True, reject_empty=True)
    assert all(arm["status"] == "failed" for arm in result["arms"].values())
    # Existing shared usage validator already rejects empty text; the legacy
    # default stops at the first failure instead of attempting both arms.
    legacy = Backend(empty=True)
    with pytest.raises(PairGenerationError, match="empty or malformed"):
        run_source_pair(source, legacy, BenchmarkConfig())
    assert len(legacy.requests) == 1


def test_deadline_prevents_model_dispatch(tmp_path):
    backend = Backend()
    wrapped = TimedPilotBackend(backend, tmp_path / "dispatch.jsonl", wall_limit_seconds=0)
    with pytest.raises(TimeoutError, match="deadline"):
        wrapped.generate("source prompt", max_output_tokens=5)
    assert backend.requests == []
    assert wrapped.blocked_reason
    assert not (tmp_path / "dispatch.jsonl").exists()


def test_cuda_failure_stops_next_dispatch_and_preserves_unknown_usage(tmp_path):
    backend = Backend(failure="CUDA device-side assert triggered")
    path = tmp_path / "dispatch.jsonl"
    wrapped = TimedPilotBackend(backend, path)
    wrapped.item_id, wrapped.arm = "train/42", "S3"
    with pytest.raises(RuntimeError, match="CUDA"):
        wrapped.generate("known input words", max_output_tokens=5)
    with pytest.raises(RuntimeError, match="fresh_runtime"):
        wrapped.generate("second source", max_output_tokens=5)
    assert len(backend.requests) == 1
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["prompt_tokens"] == [3]
    assert rows[0]["output_tokens"] is None
    assert rows[0]["status"] == "failed"
    assert rows[0]["id"] == "train/42"
    assert "known input words" not in path.read_text()


def test_runner_retains_all_selected_ids_and_failure_and_alternates(pilot_data, tmp_path):
    bundle, design = pilot_data
    receipt = run_pilot(Backend(failure="ordinary test failure"), bundle, design,
                        output_dir=tmp_path, initialization_seconds=1)
    assert {r["id"] for r in receipt["rows"]} == {r["id"] for r in design["selected"]}
    assert receipt["rows"][0]["status"] == "failed"
    assert receipt["counts"]["selected"] == receipt["counts"]["observed"] == 9
    assert receipt["counts"]["failed"] == 1
    assert receipt["rows"][1]["arm_order"] == ["S3", "S1"]
    assert receipt["cohort_frozen"] is False
    assert (tmp_path / "pilot-receipt.json").exists()


def test_changed_config_requires_new_output_root(pilot_data, tmp_path):
    bundle, design = pilot_data
    run_pilot(Backend(), bundle, design, output_dir=tmp_path,
              initialization_seconds=1, wall_limit_seconds=0)
    with pytest.raises(ValueError, match="NEW output directory"):
        run_pilot(Backend(), bundle, design, output_dir=tmp_path, initialization_seconds=1,
                  wall_limit_seconds=0, config=replace(BenchmarkConfig(), final_output_tokens=256))


def test_forecast_cannot_claim_complete_metric_profile_before_semantic_scoring(pilot_data, tmp_path):
    bundle, design = pilot_data
    receipt = run_pilot(Backend(), bundle, design, output_dir=tmp_path, initialization_seconds=1)
    assert all(r["status"] == "generated" for r in receipt["rows"])
    result = forecast_receipt(receipt)
    assert not result["credible_forecast"]
    assert "predicted_seconds" not in result
    assert "unknown_initialization_or_io_retry_cost" in result["blockers"]


@pytest.mark.parametrize("damage", ["id", "source_hash", "duplicate_id"])
def test_declared_source_identity_mismatch_prevents_dispatch(pilot_data, tmp_path, damage):
    bundle, design = pilot_data
    design = copy.deepcopy(design)
    if damage == "id":
        design["selected"][0]["id"] = "train/99999"
    elif damage == "source_hash":
        design["selected"][0]["source_sha256"] = "0" * 64
    else:
        design["selected"][1] = dict(design["selected"][0])
    backend = Backend()
    with pytest.raises(ValueError, match="IDs/source hashes"):
        run_pilot(backend, bundle, design, output_dir=tmp_path, initialization_seconds=1)
    assert backend.requests == []
    assert not (tmp_path / "dispatches.jsonl").exists()


class TestOnlySemanticScorer:
    __test__ = False
    metadata = {"test_adapter": True, "purpose": "runtime_contract_only"}

    def __init__(self, failure=False):
        self.calls = []
        self.failure = failure

    def score_pair(self, arms, reference, source):
        self.calls.append((arms, reference, source))
        if self.failure:
            raise RuntimeError("test evaluator failure")
        return {metric: {"S1": 0, "S3": 0, "S3_minus_S1": 0}
                for metric in ("bertscore", "sbertscore")}


def test_complete_semantic_receipt_forecasts_all_stages(full, tmp_path):
    # Restrict this synthetic target pool to the measured train length range;
    # a longer reserved record is tested separately as an extrapolation blocker.
    train_max = max(r["source_tokens"] for r in full["items"] if r["split"] == "train")
    full["items"] = [r for r in full["items"] if r["source_tokens"] <= train_max]
    full["metadata"]["selected_count"] = len(full["items"])
    full["metadata"]["selection_sha256"] = hashlib.sha256(
        bundles._json(bundles._identity(full["items"])).encode()).hexdigest()
    bundle, design = select_pilot(full)
    backend = Backend()
    receipt = run_pilot(backend, bundle, design, output_dir=tmp_path, initialization_seconds=2)
    request_count = len(backend.requests)
    before_scoring = sum(r["scoring_seconds"] for r in receipt["rows"])
    scorer = TestOnlySemanticScorer()
    result = evaluate_pilot(receipt, bundle, scorer, output_dir=tmp_path,
                            metric_initialization_seconds=3)
    assert len(backend.requests) == request_count
    assert len(scorer.calls) == 9
    assert all(r["status"] == "completed" for r in result["rows"])
    assert sum(r["scoring_seconds"] for r in result["rows"]) >= before_scoring
    assert result["counts"]["semantic_evaluated"] == 9
    assert result["semantic_metadata"] == scorer.metadata
    saved = json.loads((tmp_path / "pilot-receipt.json").read_text())
    assert saved == result
    forecast = forecast_receipt(result)
    assert forecast["credible_forecast"]
    expected = 5
    for name, count in design["population_by_stratum"].items():
        rows = [r for r in result["rows"] if r["length_stratum"] == name]
        costs = [sum(r["arms"][a]["wall_seconds"] for a in ("S1", "S3"))
                 + r["scoring_seconds"] + r["shared_preparation_seconds"]
                 + r["checkpoint_seconds"] for r in rows]
        expected += count * sum(costs) / len(costs)
    assert forecast["predicted_seconds"] == pytest.approx(expected * 1.3)


def test_semantic_failure_is_retained_stops_evaluator_and_blocks_forecast(pilot_data, tmp_path):
    bundle, design = pilot_data
    receipt = run_pilot(Backend(), bundle, design, output_dir=tmp_path, initialization_seconds=1)
    scorer = TestOnlySemanticScorer(failure=True)
    result = evaluate_pilot(receipt, bundle, scorer, output_dir=tmp_path,
                            metric_initialization_seconds=1)
    assert len(scorer.calls) == 1
    assert result["rows"][0]["status"] == "evaluation_failed"
    assert all(r["status"] == "generated" for r in result["rows"][1:])
    assert result["counts"]["semantic_failed"] == 1
    assert "test evaluator failure" in result["rows"][0]["evaluation_error"]
    assert not forecast_receipt(result)["credible_forecast"]
    assert json.loads((tmp_path / "pilot-receipt.json").read_text()) == result
