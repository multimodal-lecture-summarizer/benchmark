"""Pure gate tests; these fixtures are not actual neural execution evidence."""

import json

import pytest

from experiments.scripts.tib_benchmark_scorer import PACKAGE_PINS, sha256
from experiments.scripts.tib_benchmark_scorer_readiness import (
    require_new_output, validate_probe, verify_binding,
)


def inputs():
    probe = {"status": "pass", "actual_pinned_neural_probe": True,
             "long_sentence_exact_token_ids_preserved": True, "packages": PACKAGE_PINS.copy(),
             "bert_native_max_abs_error": 1e-7, "sentence_native_max_abs_error": 1e-8,
             "long_bert_content_tokens": 1800, "long_bert_preserved_content_tokens": 1800,
             "long_sentence_content_tokens": 640}
    runtime = {"device": "cpu", "exit_code": 0, "threads": 4, "T4_verified": False,
               "formal_generation_executed": False, "wall_seconds": 40,
               "sampled_peak_process_rss_bytes": 2500000000, "sampling_interval_seconds": .1}
    return probe, runtime


def test_valid_numeric_gate():
    validate_probe(*inputs(), PACKAGE_PINS)


@pytest.mark.parametrize("key,value", [("status", "pending"), ("actual_pinned_neural_probe", "true"),
    ("long_sentence_exact_token_ids_preserved", False), ("bert_native_max_abs_error", float("nan")),
    ("sentence_native_max_abs_error", .1), ("long_bert_preserved_content_tokens", 1799),
    ("long_sentence_content_tokens", 126)])
def test_probe_rejects_mutation(key, value):
    probe, runtime = inputs()
    probe[key] = value
    with pytest.raises(ValueError):
        validate_probe(probe, runtime, PACKAGE_PINS)


@pytest.mark.parametrize("key,value", [("device", "cuda"), ("threads", 8), ("exit_code", 1),
    ("T4_verified", True), ("formal_generation_executed", True), ("wall_seconds", 0)])
def test_runtime_rejects_wrong_scope(key, value):
    probe, runtime = inputs()
    runtime[key] = value
    with pytest.raises(ValueError):
        validate_probe(probe, runtime, PACKAGE_PINS)


def test_package_drift_rejected():
    changed = dict(PACKAGE_PINS, numpy="different")
    with pytest.raises(ValueError):
        validate_probe(*inputs(), changed)


def test_binding_rejects_mutated_artifact(tmp_path):
    path = tmp_path / "probe.json"
    path.write_text(json.dumps({"test_fixture": 1}))
    digest = sha256(path)
    assert verify_binding(path, digest) == {"test_fixture": 1}
    path.write_text(json.dumps({"test_fixture": 2}))
    with pytest.raises(ValueError, match="changed"):
        verify_binding(path, digest)


def test_existing_receipt_preserved(tmp_path):
    path = tmp_path / "readiness.json"
    path.write_text("preserved")
    with pytest.raises(FileExistsError):
        require_new_output(path)
    assert path.read_text() == "preserved"
