"""Score21 stored development outputs only; never import/run a generator."""
import argparse
import json
import math
import os
import sys
from pathlib import Path
import time

from .tib_benchmark_scorer import METRICS, score_record, validate_assets
from .tib_scorer_colab_checkpoint import ScoreCheckpoints, digest, file_sha, validate_bundle
from .tib_scorer_colab_resources import ResourceSampler, observe_runtime, synchronize, resource_errors, input_profile, latency_description


def _finite_result(result):
    metrics = result.get("metrics", {})
    failures = dict(result.get("failures", {}))
    clean = {}
    for name in METRICS:
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            clean[name] = float(value)
        else:
            clean[name] = None
            failures.setdefault(name, "undefined_or_nonfinite_metric")
    return {"metrics": clean, "failures": failures}


def _write(path, value, *, lines=False):
    temporary = path.with_suffix(path.suffix + ".tmp")
    data = ("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in value)
            if lines else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run(bundle, output, assets, *, resume=False, wall_hours=11.5,
        backend_factory=None, fixture_runner=None, runtime_probe=None, score_function=None,
        asset_validator=None, sampler_factory=None):
    """Injection hooks test orchestration without model downloads or GPU claims."""
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    bundle, output, assets = Path(bundle), Path(output), Path(assets)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    run_id = str(time.time_ns())
    archive = output / "runs" / run_id
    archive.mkdir(parents=True)
    rows, results, reasons = [], [], []
    runtime, binding, fixtures, metadata = {}, None, None, None
    costs = {"initialization_seconds": 0.0, "fixtures_seconds": 0.0, "scoring_seconds": 0.0,
             "checkpoint_seconds": 0.0, "validation_seconds": 0.0, "new_metric_calls": 0,
             "reused_records": 0, "original_reused_scoring_seconds": 0.0, "input_profiling_seconds": 0.0}
    injected = any(value is not None for value in (backend_factory, fixture_runner, runtime_probe,
                                                  score_function, asset_validator, sampler_factory))
    sampler, resources = None, {}
    try:
        if not 0 < wall_hours <= 11.5:
            raise ValueError("Scorer session bound must be positive and at most11.5hours")
        deadline = started + wall_hours * 3600
        tick = time.perf_counter()
        manifest, spec, amendment, rows = validate_bundle(bundle)
        runtime = (runtime_probe or observe_runtime)()
        normalized = {name.lower().replace("_", "-"): version for name, version in runtime["packages"].items()}
        if not (runtime.get("google_colab_imported") and runtime.get("cuda_available")
                and runtime.get("T4_device_observed")):
            raise ValueError("Actual Google Colab CUDA T4 evidence required")
        if not amendment.get("runtime_pins") or any(normalized.get(name.lower().replace("_", "-")) != pin
                                                   for name, pin in amendment["runtime_pins"].items()):
            raise ValueError("Colab runtime package amendment mismatch")
        if any(normalized.get(name.lower().replace("_", "-")) != pin
               for name, pin in amendment.get("support_package_pins", {}).items()):
            raise ValueError("Colab support package lock mismatch")
        if (not isinstance(runtime.get("device_memory_bytes"), int) or runtime["device_memory_bytes"] <= 0
                or runtime.get("device_name") not in ("Tesla T4", "NVIDIA T4", "NVIDIA Tesla T4")):
            raise ValueError("Missing measured T4 device capacity")
        from .tib_scorer_colab_backend import RuntimeSemanticScorer, runtime_fixtures, runtime_pins
        if amendment["runtime_pins"] != runtime_pins():
            raise ValueError("Backend pins differ from runtime amendment")
        if not injected:
            for module in tuple(sys.modules.values()):
                filename = getattr(module, "__file__", None)
                module_name = getattr(module, "__name__", "")
                if filename and module_name.startswith("experiments.scripts.") and filename.endswith(".py"):
                    relative = "experiments/scripts/" + Path(filename).name
                    if manifest["files"].get(relative) != file_sha(filename):
                        raise ValueError("Executing unbound scorer module: " + module_name)
        check_assets = asset_validator or validate_assets
        bert = check_assets(assets / "bert", model=spec["bertscore"]["model"],
                            revision=spec["bertscore"]["model_revision"])
        sentence = check_assets(assets / "sentence", model=spec["source_similarity"]["model"],
                                revision=spec["source_similarity"]["model_revision"])
        binding = {"package_manifest_sha256": file_sha(bundle / "package_manifest.json"),
                   "frozen_spec_sha256": amendment["frozen_spec_sha256"],
                   "runtime_amendment_sha256": file_sha(bundle / "runtime_amendment.json"),
                   "code_input_files_sha256": digest(manifest["files"]),
                   "asset_manifests_sha256": {name: file_sha(path / "asset_manifest.json")
                                              for name, path in (("bert", bert), ("sentence", sentence))},
                   "runtime_sha256": digest(runtime)}
        costs["validation_seconds"] = time.perf_counter() - tick
        store = ScoreCheckpoints(output / "checkpoints", binding, resume=resume)
        # Validate every existing record before expensive initialization; never fill holes on resume.
        cached = {row["sample_id"]: store.load(row) for row in rows} if resume else {}
        sampler = (sampler_factory or ResourceSampler)().start()
        tick = time.perf_counter()
        scorer = (backend_factory or RuntimeSemanticScorer)(bert, sentence)
        scorer._load()
        if not injected:
            synchronize()
        metadata = scorer.metadata
        costs["initialization_seconds"] = time.perf_counter() - tick
        tick = time.perf_counter()
        fixtures = (fixture_runner or runtime_fixtures)(scorer)
        if not injected:
            synchronize()
        costs["fixtures_seconds"] = time.perf_counter() - tick
        if str(fixtures.get("status", "")).lower() != "pass":
            raise ValueError("Actual scorer fixtures/probes did not PASS")
        for row in rows:
            print("Scorer", "reuse" if resume else "score", row["sample_id"], flush=True)
            base = {key: row[key] for key in ("sample_id", "record_id", "candidate_id", "profile_id",
                                             "generation_status", "warnings", "source_receipt_sha256")}
            if time.monotonic() >= deadline:
                reasons.append("session_deadline")
                break
            profile_start = time.perf_counter()
            shape = input_profile(row, scorer)
            costs["input_profiling_seconds"] += time.perf_counter() - profile_start
            if not injected:
                synchronize()
            tick, cpu_tick = time.perf_counter(), time.process_time()
            if resume:
                payload = cached[row["sample_id"]]
                scored = _finite_result(payload["result"])
                elapsed, cpu_elapsed, reused = 0.0, 0.0, True
                costs["original_reused_scoring_seconds"] += payload["original_scoring_wall_seconds"]
                costs["reused_records"] += 1
            else:
                try:
                    scored = _finite_result((score_function or score_record)(row["delivered_summary"],
                                             row["reference"], row["source"], semantic=scorer))
                    if not injected:
                        synchronize()
                except Exception as error:
                    scored = {"metrics": dict.fromkeys(METRICS), "failures": {"record": f"{type(error).__name__}: {error}"}}
                elapsed, reused = time.perf_counter() - tick, False
                cpu_elapsed = time.process_time() - cpu_tick
                costs["scoring_seconds"] += elapsed
                costs["new_metric_calls"] += 1
                checkpoint_start = time.perf_counter()
                store.save(row, scored, elapsed)
                costs["checkpoint_seconds"] += time.perf_counter() - checkpoint_start
            results.append({**base, **scored, "reused": reused, "new_scoring_wall_seconds": elapsed,
                            "new_scoring_cpu_seconds": cpu_elapsed,
                            "scoring_status": "completed" if not scored["failures"] else "failed",
                            "input_profile": shape})
            if resume:
                costs["checkpoint_seconds"] += time.perf_counter() - tick
        if time.monotonic() >= deadline:
            reasons.append("session_deadline")
    except Exception as error:
        reasons.append(f"{type(error).__name__}: {error}")
    finally:
        if sampler is not None:
            try:
                resources = sampler.finish()
            except Exception as error:
                reasons.append(f"Resource collection failed: {type(error).__name__}: {error}")
    seen = {result["sample_id"] for result in results}
    for row in rows:
        if row["sample_id"] not in seen:
            results.append({**{key: row[key] for key in ("sample_id", "record_id", "candidate_id", "profile_id", "generation_status", "warnings")},
                            "metrics": dict.fromkeys(METRICS), "failures": {"record": "not_scored_due_to_HOLD"},
                            "reused": False, "scoring_status": "not_attempted", "new_scoring_wall_seconds": 0.0})
    good = sum(not result["failures"] and all(value is not None for value in result["metrics"].values()) for result in results)
    if len(results) - good:
        reasons.append("metric_failures_or_unscored_records")
    if resources:
        reasons.extend(resource_errors(resources))
    elif good:
        reasons.append("missing_resource_evidence")
    checks_passed = not reasons and len(results) == good == 21
    if injected:
        reasons.append("TEST_DEPENDENCY_INJECTION_NOT_ACTUAL_COLAB_EVIDENCE")
    passed = checks_passed and not injected
    status = "PASS" if passed else "HOLD"
    report = {"status": status, "reasons": reasons, "expected_records": 21,
              "selected_denominator": len(rows), "successful_metric_records": good,
              "failed_or_unscored_records": len(results) - good, "rankings_computed": False,
              "generation_executed": False, "formal_benchmark": False, "run_id": run_id}
    report.update(orchestration_checks_passed=checks_passed, testing_dependency_injection=injected,
                  scope="scorer fixtures and21 stored outputs /3 existing IDs; not pilot40/selection/final",
                  selection_start_authorized=False, full_compute_budget_verified=False)
    receipt = {**report, "scorer_ready": passed, "binding": binding, "runtime": runtime,
               "backend_metadata": metadata, "fixtures": fixtures,
               "actual_colab_execution": bool(runtime.get("google_colab_imported")) and not injected,
               "T4_verified": passed,
               "immediate_checkpoint_readback_verified": passed,
               "cached_replay_verified": passed and resume,
               "cross_session_survival_verified": False,
               "replay_note": "Cached replay is not proof of a separate Colab session; provenance review required"}
    costs.update(status=status, resources=resources, total_wall_seconds=time.monotonic() - started,
                 costs_include_fixture_calls_separately=True, generation_calls=0)
    costs.update(new_record_throughput_per_second=costs["new_metric_calls"] / costs["scoring_seconds"] if costs["scoring_seconds"] > 0 else None,
                 successful_records_per_total_wall_second=good / costs["total_wall_seconds"],
                 checkpoint_storage_bytes=sum(path.stat().st_size for path in (output / "checkpoints").rglob("*") if path.is_file()))
    costs["latency_by_profile"] = {profile: latency_description([
        row["new_scoring_wall_seconds"] for row in results if row["profile_id"] == profile
        and not row["reused"] and row.get("scoring_status") != "not_attempted"])
        for profile in sorted({row["profile_id"] for row in results})}
    for name, value in (("cost_evidence.json", costs), ("PASS_HOLD_report.json", report), ("metrics.jsonl", results)):
        _write(archive / name, value, lines=name.endswith(".jsonl"))
        _write(output / name, value, lines=name.endswith(".jsonl"))
    receipt["artifact_sha256"] = {name: file_sha(archive / name) for name in ("cost_evidence.json", "PASS_HOLD_report.json", "metrics.jsonl")}
    _write(archive / "scorer_ready_receipt.json", receipt)
    _write(output / "scorer_ready_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("bundle", "output", "assets"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--wall-hours", type=float, default=11.5)
    arguments = parser.parse_args()
    result = run(arguments.bundle, arguments.output, arguments.assets,
                 resume=arguments.resume, wall_hours=arguments.wall_hours)
    print(json.dumps({"status": result["status"], "run_id": result["run_id"]}, allow_nan=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
