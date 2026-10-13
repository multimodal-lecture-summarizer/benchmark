"""Verify the real frozen cohort uses only source identity and declared strata."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts.rq2_tib_frozen_cohort import CUTS, SEED, _stratum
from experiments.scripts.rq2_tib_pilot_runtime import digest


ROOT = Path(__file__).resolve().parents[1]


def test_real_frozen_selection_reconstructs_without_scores():
    manifest = json.loads((ROOT / "experiments/registry/datasets/"
                           "tib-rq2-rq4-120-cohort-261012.json").read_text(encoding="utf-8"))
    full_path = ROOT / "experiments/outputs/rq2_tib_benchmark/tib-benchmark-data.jsonl.gz"
    subset_path = ROOT / "experiments/outputs/rq2_tib_120_261012/data/tib-evaluation-120.jsonl.gz"
    token_path = ROOT / "experiments/outputs/rq2_tib_pilot_261010/data/source-token-lengths.json"
    if not all(path.exists() for path in (full_path, subset_path, token_path)):
        pytest.skip("Local ignored TIB bundles/ledger unavailable")
    full = bundles.load_benchmark_bundle(full_path)
    subset = bundles.load_benchmark_bundle(subset_path)
    tokens = json.loads(token_path.read_text(encoding="utf-8"))
    assert manifest["manifest_sha256"] == digest(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"})
    assert tokens["identity"]["full_selection"] == full["metadata"]["selection_sha256"]
    token_by_id = {row["id"]: row["source_tokens"] for row in tokens["rows"]}
    expected = []
    for label in ("short", "medium", "long"):
        frame = [row for row in full["items"] if row["split"] == "valid"
                 and _stratum(token_by_id[f"valid/{row['source_index']}"]) == label]
        frame.sort(key=lambda row: (hashlib.sha256(
            f"{SEED}|valid/{row['source_index']}".encode()).hexdigest(),
            f"valid/{row['source_index']}"))
        expected.extend(f"valid/{row['source_index']}" for row in frame[:40])
    expected.sort(key=lambda name: int(name.split("/")[1]))
    selected = manifest["selected"]
    assert [row["id"] for row in selected] == expected
    assert [f"{row['split']}/{row['source_index']}" for row in subset["items"]] == expected
    assert Counter(row["length_stratum"] for row in selected) == {
        "short": 40, "medium": 40, "long": 40}
    assert manifest["source_token_cutpoints_inclusive"] == list(CUTS)
    assert all(row["id"].startswith("valid/") for row in selected)
    assert not set(manifest["pilot_excluded_ids"]) & set(expected)
    assert subset["metadata"]["selection_sha256"] == manifest["selection_sha256"]
    assert all(row["source_sha256"] == item["source_sha256"]
               and row["reference_sha256"] == item["reference_sha256"]
               for row, item in zip(selected, subset["items"]))


def test_selected_groups_are_declared_and_arm_order_counterbalanced():
    manifest = json.loads((ROOT / "experiments/registry/datasets/"
                           "tib-rq2-rq4-120-cohort-261012.json").read_text(encoding="utf-8"))
    rows = manifest["selected"]
    assert all(row["dependence_group"] and row["author_group"] for row in rows)
    assert [row["arm_order"] for row in rows] == [
        ["S1", "S3"] if i % 2 == 0 else ["S3", "S1"] for i in range(120)]
    assert manifest["within_selected_high_overlap_pairs"] == 0
    assert "off-cohort within-valid" in manifest["group_limit"]
