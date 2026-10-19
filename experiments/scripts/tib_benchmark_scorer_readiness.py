"""Seal CPU-only scorer readiness after verified local probe and real E2E fixture."""

import argparse
import json
import math
import os
from pathlib import Path
import time

from experiments.scripts.tib_benchmark_scorer import (
    BERT_MODEL, BERT_REVISION, SBERT_MODEL, SBERT_REVISION, METRICS, PACKAGE_PINS,
    LocalSemanticScorer, package_versions, score_record, sha256, validate_assets,
)

REGISTRY = "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/"
DATA = "research-data/tib-p4-261019-1802/"
# Reviewed, previously executed artifacts. Changed evidence needs an explicit amendment.
BINDINGS = {
    REGISTRY + "scorer_spec_v2.json": "b83258fab60ee98d6d70e4f3ee2a2fc6f8956f2a8bd95b1a4a6db271a6ac7fdf",
    REGISTRY + "scorer_implementation_receipt_v2.json": "96de6f7ac4bf80d6d4320a8517b9fde1f2ea997e8d87ba04a169e043b965cf0c",
    DATA + "scorer-neural-probe.json": "f2666f6e217d8bc8ca98745b4d2daf576e59d638665968a0343bb2924af8b7a3",
    DATA + "scorer-neural-runtime.json": "9e023273005fc8c6a278ced525a7730a0583f0042feeb7146b828a024d559747",
    DATA + "scorer-assets/bert/asset_manifest.json": "9937514963f6f3efd6742b7314d3b793b1e48e71057409dccf0d7f98c74d78ef",
    DATA + "scorer-assets/sentence/asset_manifest.json": "070e91efc5608fae27f224293516e6af92f2ba383d423192a8553d5c4c75d8f1",
}


def verify_binding(path, expected):
    if sha256(path) != expected:
        raise ValueError("Bound artifact changed: " + str(path))
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_probe(probe, runtime, installed):
    if (probe.get("status") != "pass" or probe.get("actual_pinned_neural_probe") is not True
            or probe.get("long_sentence_exact_token_ids_preserved") is not True
            or installed != PACKAGE_PINS or probe.get("packages") != PACKAGE_PINS):
        raise ValueError("Probe or package pin gate failed")
    for key in ("bert_native_max_abs_error", "sentence_native_max_abs_error"):
        number = probe.get(key)
        if type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= 1e-5:
            raise ValueError("Native equivalence tolerance failed")
    count = probe.get("long_bert_content_tokens")
    if type(count) is not int or count <= 510 or count != probe.get("long_bert_preserved_content_tokens"):
        raise ValueError("Long BERT token preservation failed")
    if type(probe.get("long_sentence_content_tokens")) is not int or probe["long_sentence_content_tokens"] <= 126:
        raise ValueError("Long sentence probe missing")
    if (runtime.get("device") != "cpu" or runtime.get("exit_code") != 0
            or runtime.get("threads") != 4 or runtime.get("T4_verified") is not False
            or runtime.get("formal_generation_executed") is not False):
        raise ValueError("Runtime scope mismatch")
    for key in ("wall_seconds", "sampled_peak_process_rss_bytes", "sampling_interval_seconds"):
        number = runtime.get(key)
        if type(number) not in (int, float) or not math.isfinite(number) or number <= 0:
            raise ValueError("Missing measured CPU resource field")


def require_new_output(path):
    if Path(path).exists():
        raise FileExistsError("Preserve existing readiness receipt: " + str(path))


def seal(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    require_new_output(output)
    evidence = {name: verify_binding(root / name, digest) for name, digest in BINDINGS.items()}
    spec = evidence[REGISTRY + "scorer_spec_v2.json"]
    fixtures = evidence[REGISTRY + "scorer_implementation_receipt_v2.json"]
    for name, digest in spec["code_sha256"].items():
        if sha256(root / name) != digest:
            raise ValueError("Scorer code changed: " + name)
    if (fixtures["spec_sha256"] != BINDINGS[REGISTRY + "scorer_spec_v2.json"]
            or fixtures.get("fixture_pass_count") != 19 or fixtures.get("fixture_fail_count") != 0
            or fixtures["code_sha256"] != spec["code_sha256"] or spec["package_pins"] != PACKAGE_PINS):
        raise ValueError("Fixture/spec binding mismatch")
    probe = evidence[DATA + "scorer-neural-probe.json"]
    runtime = evidence[DATA + "scorer-neural-runtime.json"]
    if runtime.get("probe_sha256") != BINDINGS[DATA + "scorer-neural-probe.json"]:
        raise ValueError("Runtime/probe binding mismatch")
    validate_probe(probe, runtime, package_versions())
    bert = validate_assets(root / DATA / "scorer-assets/bert", model=BERT_MODEL, revision=BERT_REVISION)
    sentence = validate_assets(root / DATA / "scorer-assets/sentence", model=SBERT_MODEL, revision=SBERT_REVISION)
    sentence_config = json.loads((sentence / "sentence_bert_config.json").read_text())
    if sentence_config.get("max_seq_length") != 128 or spec["bertscore"]["idf"] is not False:
        raise ValueError("Capacity/IDF gate failed")
    import torch
    torch.set_num_threads(4)
    started = time.perf_counter()
    text = "The lecture explains quantum states. Electrons occupy discrete energy levels."
    scorer = LocalSemanticScorer(bert_path=bert, sentence_path=sentence)
    fixture = score_record(text, text, text, semantic=scorer)
    if fixture["failures"] or set(fixture["metrics"]) != set(METRICS):
        raise ValueError("Actual E2E scorer fixture failed: " + str(fixture))
    if any(not math.isfinite(v) or abs(v - 1) > 1e-5 for v in fixture["metrics"].values()):
        raise ValueError("Actual identity fixture metric mismatch")
    receipt = {"schema_version": 1, "scorer_ready": True, "state": "ready_cpu_fixture_scope_only",
               "spec_file": "scorer_spec_v2.json", "bindings_sha256": BINDINGS,
               "scorer_code_sha256": spec["code_sha256"], "writer_sha256": sha256(__file__),
               "runtime_profile": {"device": "cpu", "threads": 4, "batch_size": 1, "dtype": "float32",
                                   "bert_max_sequence_tokens": 512, "sentence_max_sequence_tokens": 128,
                                   "idf": False, "idf_fit_ids": [], "package_pins": PACKAGE_PINS},
               "actual_e2e_fixture": {"controlled_text": text, "result": fixture,
                                      "elapsed_seconds": time.perf_counter() - started},
               "prior_neural_probe": probe, "prior_neural_probe_runtime": runtime,
               "unit_fixture_count": 19, "capacity_limit": "fixtures only; no full-corpus throughput projection",
               "T4_verified": False, "full_compute_budget_verified": False,
               "selection_start_authorized": False, "formal_benchmark_executed": False,
               "remaining_gates": ["candidate profiles", "T4 feasibility", "compute/storage budget", "final cohort seal"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ[name] = "1"
    result = seal(args.root, args.output)
    print(json.dumps({"scorer_ready": result["scorer_ready"], "scope": result["state"]}))


if __name__ == "__main__":
    main()
