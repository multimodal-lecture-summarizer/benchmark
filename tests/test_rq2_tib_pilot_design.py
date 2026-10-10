"""Offline development-selection boundaries and complete runtime accounting."""

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts import rq2_tib_benchmark_dataset as tib
from experiments.scripts.rq2_tib_pilot_cohort import select_pilot
from experiments.scripts.rq2_tib_pilot_forecast import forecast_pilot


@pytest.fixture
def full():
    def record(index, split):
        texts = ["source " * (index + 1), "end " + str(index)]
        return {"doi": f"doi-{split}-{index}", "abstract": f"unique abstract {split} {index}",
                "transcript": " ".join(texts), "transcript_segments": {
                    "text": texts, "start": [0, 2], "end": [1, 3]}}
    prepared = tib.prepare_dataset({s: [record(i, s) for i in range(30 if s == "train" else 40)]
                                    for s in tib.SPLITS}, verify_counts=False)
    bundle = bundles.build_benchmark_bundle(prepared)
    return bundles.add_token_counts(bundle, lambda s: list(s.encode()),
                                    tokenizer_id="offline-byte-tokenizer", tokenizer_revision="pinned")


def test_train_only_extremes_population_and_bundle_roundtrip(full, tmp_path):
    subset, design = select_pilot(full)
    assert len(subset["items"]) == 9
    assert {row["split"] for row in subset["items"]} == {"train"}
    assert sum(design["population_by_stratum"].values()) == len(full["items"])
    assert design["train_max_source_tokens"] == max(r["source_tokens"] for r in subset["items"])
    assert design["full_pool_exceeds_pilot_length_range"]
    assert len({row["id"] for row in design["selected"]}) == 9
    assert {row["length_stratum"] for row in design["selected"]} == {"short", "medium", "long"}
    assert subset["metadata"]["status"] == "pilot_not_frozen"
    path = tmp_path / "pilot.gz"
    bundles.save_benchmark_bundle(subset, path)
    assert bundles.load_benchmark_bundle(path) == json.loads(json.dumps(subset))
    assert all(r["source_index"] in range(30) for r in subset["items"])


def test_selector_hash_and_ids_do_not_depend_on_references_or_scores(full):
    _, before = select_pilot(full)
    altered = copy.deepcopy(full)
    for row in altered["items"]:
        row["reference_text"] = "Different valid reference"
        row["reference_sha256"] = hashlib.sha256(row["reference_text"].encode()).hexdigest()
        row["quality_score"] = -1000
    altered["metadata"]["selection_sha256"] = hashlib.sha256(
        bundles._json(bundles._identity(altered["items"])).encode()).hexdigest()
    _, after = select_pilot(altered)
    assert before["selection_source_sha256"] == after["selection_source_sha256"]
    assert before["selected"] == after["selected"]
    assert select_pilot(full)[1] == before


def test_collapsed_ties_or_unmeasured_tokens_rejected(full):
    altered = copy.deepcopy(full)
    for row in altered["items"]:
        row["source_tokens"] = 100
    with pytest.raises(ValueError, match="tied cutpoints"):
        select_pilot(altered)
    full["metadata"].pop("tokenizer")
    with pytest.raises(ValueError, match="tokenizer"):
        select_pilot(full)


def profiles():
    return [{"id": f"train/{i}", "length_stratum": name, "source_tokens": 100 * (i + 1),
             "status": "completed", "arms": {
                 "S1": {"status": "completed", "wall_seconds": 10},
                 "S3": {"status": "completed", "wall_seconds": 20}},
             "scoring_seconds": 3, "shared_preparation_seconds": 2, "checkpoint_seconds": 1}
            for i, name in enumerate(("short", "medium", "long"))]


def test_forecast_counts_both_arms_every_stage_and_safety_margin():
    result = forecast_pilot(profiles(), initialization_seconds=100,
                            population_by_stratum={"short": 2, "medium": 3, "long": 5},
                            io_retry_seconds=20)
    assert result["credible_forecast"]
    assert result["predicted_seconds"] == pytest.approx((100 + 20 + 10 * 36) * 1.3)
    assert result["observed_scenario_range_seconds"] == [result["predicted_seconds"]] * 2
    assert result["within_budget"]
    assert result["evaluation_cohort_frozen"] is False
    result = forecast_pilot(profiles(), initialization_seconds=0,
                            population_by_stratum=dict.fromkeys(("short", "medium", "long"), 1000))
    assert result["within_budget"] is False


@pytest.mark.parametrize("damage", ["missing_arm", "failed", "missing_stage", "resumed", "coverage"])
def test_incomplete_or_reused_profiles_cannot_forecast(damage):
    rows = profiles()
    if damage == "missing_arm":
        rows[0]["arms"].pop("S3")
    elif damage == "failed":
        rows[0]["status"] = "failed"
    elif damage == "missing_stage":
        rows[0].pop("checkpoint_seconds")
    elif damage == "resumed":
        rows[0]["resumed"] = True
    else:
        rows.pop()
    result = forecast_pilot(rows, initialization_seconds=0,
                            population_by_stratum=dict.fromkeys(("short", "medium", "long"), 10))
    assert not result["credible_forecast"]
    assert "predicted_seconds" not in result


@pytest.mark.parametrize("kwargs,blocker", [({"hardware_consistent": False}, "heterogeneous_hardware"),
    ({"length_range_covered": False}, "target_length_outside_pilot_range"),
    ({"initialization_seconds": None}, "unknown_initialization_or_io_retry_cost")])
def test_unknown_profile_domain_rejected(kwargs, blocker):
    options = {"initialization_seconds": 0, "population_by_stratum": {
        "short": 1, "medium": 1, "long": 1}}
    options.update(kwargs)
    result = forecast_pilot(profiles(), **options)
    assert blocker in result["blockers"]
    assert not result["credible_forecast"]
