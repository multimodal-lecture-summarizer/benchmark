"""Read-only replay of the original 21 scorer checkpoints; never run metrics.

Standalone use: PYTHONPATH must point to the unchanged original scorer bundle.
This verifies cached evidence; independent boot witnesses establish freshness.
"""
import argparse
import json
import math
import os
from pathlib import Path
import time

from experiments.scripts import tib_scorer_colab_checkpoint as checkpoints
from experiments.scripts import tib_scorer_colab_resources as resources

METRICS = {"rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1",
           "source_sentence_similarity_v1"}


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def _rss():
    """Current process RSS using OS interfaces, without model/psutil imports."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counter = Counters()
        counter.cb = ctypes.sizeof(counter)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counter), counter.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        return counter.WorkingSetSize
    return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")


def _store_hashes(store):
    if not store.is_dir():
        raise ValueError("Original checkpoint store missing; no creation/fill allowed")
    return {path.relative_to(store).as_posix(): checkpoints.file_sha(path)
            for path in store.rglob("*") if path.is_file()}


def _origin_binding(bundle, manifests, manifest, amendment, runtime):
    return {"package_manifest_sha256": checkpoints.file_sha(bundle / "package_manifest.json"),
            "frozen_spec_sha256": amendment["frozen_spec_sha256"],
            "runtime_amendment_sha256": checkpoints.file_sha(bundle / "runtime_amendment.json"),
            "code_input_files_sha256": checkpoints.digest(manifest["files"]),
            "asset_manifests_sha256": {name: checkpoints.file_sha(manifests / name / "asset_manifest.json")
                                       for name in ("bert", "sentence")},
            "runtime_sha256": checkpoints.digest(runtime)}


def replay(bundle, store, origin_ready, asset_manifests, expected, output, runtime_probe=None,
           session_context=None):
    """Validate and copy cached scores. Injected runtime probes always yield HOLD."""
    bundle, store, manifests, output = map(Path, (bundle, store, asset_manifests, output))
    # Refuse an existing destination and any output inside immutable inputs.
    protected = (bundle, store, manifests, Path(origin_ready), Path(expected))
    if any(output.resolve() == path.resolve() or output.resolve().is_relative_to(path.resolve())
           for path in protected):
        raise ValueError("Replay output overlaps original inputs")
    stage_session_context = None
    if runtime_probe is None:
        try:
            if session_context is None:
                raise ValueError("Current recovery session context required for actual replay PASS")
            try:
                from tib_p4_session_recovery import validate_stage_context
            except ModuleNotFoundError as error:
                if error.name != "tib_p4_session_recovery":
                    raise
                from .tib_p4_session_recovery import validate_stage_context
            stage_session_context = validate_stage_context(session_context, output, "scorer")
            if not isinstance(stage_session_context, dict) or not stage_session_context:
                raise ValueError("Invalid verified stage session context")
        except Exception as error:
            # Fail closed without creating even a directory inside an untrusted store.
            return {"status": "HOLD", "reasons": [f"{type(error).__name__}: {error}"],
                    "reused_records": 0, "new_metric_calls": 0,
                    "orchestration_checks_passed": False, "testing_dependency_injection": False,
                    "stage_checks": {}, "stage_session_context": None}
    output.mkdir(parents=True, exist_ok=False)
    started, cpu_started = time.perf_counter(), time.process_time()
    reasons, results, runtime, binding, before = [], [], {}, None, None
    stage_checks = {"current_recovery_session_context_verified": True} if stage_session_context else {}
    original_seconds, hash_seconds, restore_seconds, rss_before, rss_after = 0.0, 0.0, 0.0, None, None
    try:
        rss_before = _rss()
        manifest, _, amendment, rows = checkpoints.validate_bundle(bundle)
        stage_checks["original_bundle_verified"] = True
        origin = _json(origin_ready)
        if (origin.get("status") != "PASS" or origin.get("scorer_ready") is not True
                or origin.get("testing_dependency_injection") is not False
                or origin.get("actual_colab_execution") is not True
                or origin.get("T4_verified") is not True
                or origin.get("successful_metric_records") != 21
                or origin.get("selected_denominator") != 21
                or origin.get("failed_or_unscored_records") != 0
                or origin.get("fixtures", {}).get("status") != "pass"):
            raise ValueError("Original actual scorer-ready PASS/fixture proof required")
        stage_checks["original_ready_fixture_proof_verified"] = True
        runtime = (runtime_probe or resources.observe_runtime)()
        if not all(runtime.get(key) is True for key in
                   ("google_colab_imported", "cuda_available", "T4_device_observed")):
            raise ValueError("Actual Google Colab CUDA T4 required")
        normalized = {name.lower().replace("_", "-"): value for name, value in runtime["packages"].items()}
        for pins in (amendment["runtime_pins"], amendment.get("support_package_pins", {})):
            if any(normalized.get(name.lower().replace("_", "-")) != pin for name, pin in pins.items()):
                raise ValueError("Original exact runtime pins differ")
        binding = _origin_binding(bundle, manifests, manifest, amendment, runtime)
        if binding != origin["binding"] or checkpoints.digest(origin["runtime"]) != binding["runtime_sha256"]:
            raise ValueError("Original binding/full observed runtime differs")
        stage_checks["exact_original_runtime_and_binding_verified"] = True
        if runtime_probe is None:
            for module in (checkpoints, resources):
                name = "experiments/scripts/" + Path(module.__file__).name
                if manifest["files"].get(name) != checkpoints.file_sha(module.__file__):
                    raise ValueError("Executing unbound original helper: " + name)
        tick = time.perf_counter()
        before = _store_hashes(store)
        expected_manifest = _json(expected)
        expected_files = expected_manifest["files"]
        if (expected_manifest.get("origin_ready_sha256") != checkpoints.file_sha(origin_ready)
                or expected_manifest.get("asset_manifest_sha256") != binding["asset_manifests_sha256"]):
            raise ValueError("Expected original receipt/asset manifest hashes differ")
        keys = {checkpoints.digest({"binding": binding, "sample_id": row["sample_id"],
                                   "input_sha256": checkpoints.digest(row)}) + ".json" for row in rows}
        if len(expected_files) != 21 or set(expected_files) != keys or before != expected_files:
            raise ValueError("Exact21 expected checkpoint hashes/file set differ")
        stage_checks["exact21_original_file_hashes_verified"] = True
        hash_seconds += time.perf_counter() - tick
        tick = time.perf_counter()
        cache = checkpoints.ScoreCheckpoints(store, binding, resume=True)
        for row in rows:
            payload = cache.load(row)
            result = payload["result"]
            metrics = result.get("metrics", {})
            if (result.get("failures") != {} or set(metrics) != METRICS
                    or any(isinstance(value, bool) or not isinstance(value, (int, float))
                           or not math.isfinite(value) for value in metrics.values())):
                raise ValueError("Cached metric failure/nonfinite/missing value")
            seconds = payload["original_scoring_wall_seconds"]
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("Invalid original scoring cost")
            original_seconds += seconds
            results.append({**{key: row[key] for key in ("sample_id", "record_id", "candidate_id", "profile_id",
                            "generation_status", "warnings", "source_receipt_sha256")},
                            **result, "result_sha256": checkpoints.digest(result),
                            "input_sha256": checkpoints.digest(row), "reused": True,
                            "new_scoring_wall_seconds": 0.0})
        restore_seconds = time.perf_counter() - tick
        stage_checks["all21_checkpoint_keys_inputs_metrics_verified"] = True
    except Exception as error:
        reasons.append(f"{type(error).__name__}: {error}")
    finally:
        if before is not None:
            tick = time.perf_counter()
            try:
                stage_checks["original_store_unchanged"] = _store_hashes(store) == before
                if not stage_checks["original_store_unchanged"]:
                    reasons.append("Original checkpoint store changed during read-only replay")
            except Exception as error:
                reasons.append(f"Read-only after-check failed: {error}")
            hash_seconds += time.perf_counter() - tick
        try:
            rss_after = _rss()
        except Exception as error:
            reasons.append(f"RSS measurement failed: {error}")
    checks_passed = not reasons and len(results) == 21
    if runtime_probe is not None:
        reasons.append("TEST_DEPENDENCY_INJECTION_NOT_ACTUAL_COLAB_EVIDENCE")
    receipt = {"status": "PASS" if checks_passed and runtime_probe is None else "HOLD",
               "reasons": reasons, "orchestration_checks_passed": checks_passed,
               "testing_dependency_injection": runtime_probe is not None,
               "stage_checks": stage_checks,
               "stage_session_context": stage_session_context,
               "scope": "Read-only original21 scorer checkpoints; separate boot witnesses required for freshness",
               "binding": binding, "runtime": runtime, "reused_records": len(results),
               "expected_records": 21, "selected_denominator": 21,
               "new_metric_calls": 0, "new_scoring_seconds": 0.0,
               "original_scoring_seconds": original_seconds, "hash_seconds": hash_seconds,
               "restore_seconds": restore_seconds, "wall_seconds": time.perf_counter() - started,
               "cpu_seconds": time.process_time() - cpu_started,
               "rss_before_bytes": rss_before, "rss_after_bytes": rss_after,
               "memory_measurement": "Process RSS at operation boundaries; not sampled peak",
               "model_reload_executed": False, "scoring_executed": False, "fixtures_executed": False,
               "asset_manifest_scope": "Archived original manifest hashes only; model binaries not reloaded/validated",
               "origin_fixture_proof": "Retained in hash-bound original scorer-ready receipt; not rerun",
               "cross_session_survival_verified": False, "generation_executed": False,
               "selection_start_authorized": False,
               "input_artifact_sha256": {name: checkpoints.file_sha(path) if Path(path).is_file() else None
                                         for name, path in (("origin_ready", origin_ready), ("expected", expected))}}
    with (output / "metrics_replay.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    receipt["artifact_sha256"] = {"metrics_replay.jsonl": checkpoints.file_sha(output / "metrics_replay.jsonl")}
    _write(output / "scorer_replay_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("bundle", "store", "origin-ready", "asset-manifests", "expected", "output"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--session-context", type=Path)
    result = replay(**vars(parser.parse_args()))
    print(json.dumps({"status": result["status"], "reused_records": result["reused_records"]}, allow_nan=False))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
