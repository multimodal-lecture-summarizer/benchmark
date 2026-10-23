"""Four frozen profiles on the sealed 300-ID selection set; generation only, no scores, no search.

Derived from tib_pilot_runtime (left untouched). Differences: no historical import or historical store,
the denominator is the contract's selection set, node-time forecasts come from the bundle (measured on
Pilot40), the stage ledger replaces the pilot ledger, and a user start authorization bound to the bundle
manifest is required before anything is loaded.
"""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

from . import tib_benchmark_checkpoint as checkpoint
from . import tib_benchmark_capacity_runtime as runtime
from . import tib_benchmark_adapter_generation as generation
from . import tib_benchmark_adapter_transformers as bindings
from . import tib_benchmark_output as delivery
from . import tib_benchmark_reduction_diagnostics as diagnostics
from . import tib_benchmark_generation_telemetry as telemetry
from .tib_benchmark_adapter_cpu import lead3, lexrank
from .tib_benchmark_development_trials import development_node_seed
from .tib_p4_generation_recovery import sha
from .tib_stage_resources import (
    ResourceSample, StageBudget, admit_assets, allocated_stage, atomic_json, require, runtime_environment,
)
from .tib_selection_validation import (
    CANDIDATES, PREFERRED, check_authorization, validate_bundle, validate_cpu, validate_neural,
)


def original_api(bundle):
    """The bundle ships byte-identical frozen modules; verify them before use."""
    modules = dict(checkpoint=checkpoint, runtime=runtime, generation=generation, bindings=bindings,
                   output=delivery, diagnostics=diagnostics, telemetry=telemetry)
    manifest = json.loads((bundle / "bundle_manifest.json").read_text(encoding="utf-8"))
    for module in modules.values():
        name = "experiments/scripts/" + Path(module.__file__).name
        require(sha(module.__file__) == manifest["files"][name], "Frozen adapter differs from original: " + name)
    return SimpleNamespace(**modules)


def summary(records, ids):
    counts = Counter(records.get(i, {}).get("status", "pending") for i in ids)
    return {"denominator": len(ids), "status_counts": dict(counts),
            "successful": counts["completed"] + counts["completed_with_warning"],
            "failed_or_interrupted": counts["failed"] + counts["started"], "pending": counts["pending"],
            "fresh": sum(r.get("origin") == "fresh" and r["status"] in ("completed", "completed_with_warning")
                         for r in records.values()), "NULL_quality_for_failures": True}


def run(bundle, output, candidate, *, resume=False, wall_hours, allocation, authorization, dependencies=None):
    bundle, output = map(Path, (bundle, output))
    require(candidate in CANDIDATES, "Unknown selection candidate")
    require(not output.resolve().is_relative_to(bundle.resolve())
            and not bundle.resolve().is_relative_to(output.resolve()), "Selection output overlaps the immutable bundle")
    receipt = {"status": "HOLD", "scope": "selection300_generation_only", "candidate_id": candidate,
               "test_only": dependencies is not None, "formal_benchmark": False, "selection_authorized": False,
               "new_metric_calls": 0, "records": {}, "new_generation_calls": 0, "new_generation_wall_seconds": 0,
               "automatic_retries": 0, "quality_evaluation": None}
    started, budget, model, tokenizer = time.monotonic(), None, None, None
    original_commit = checkpoint.commit
    try:
        allocated_stage(allocation, wall_hours)
        contract, sources, bundle_sha = (dependencies.validate_bundle(bundle) if dependencies else validate_bundle(bundle))
        check_authorization(authorization, bundle_sha)  # before any ledger, store or model is touched
        require(checkpoint.digest(allocation) == contract["allocation_sha256"],
                "Allocation differs from the one bound in the bundle contract")
        if dependencies is None:
            original_api(bundle / "original_generation")
        forecast = json.loads((bundle / "node_forecast.json").read_text(encoding="utf-8"))
        budget = StageBudget(output, allocation, candidate, wall_hours,
                             dependencies=dependencies.resources if dependencies else None)
        require(budget.ledger.get("bundle_sha256") == bundle_sha, "Selection bundle/ledger identity mismatch")
        budget.guard()
        profile = next(p for p in contract["profiles"] if p["candidate_id"] == candidate)
        binding = {"bundle_sha256": bundle_sha, "profile_sha256": profile["profile_sha256"],
                   "profile_id": profile["profile_id"], "acceptance_policy_sha256": contract["acceptance_policy_sha256"],
                   "allocation_sha256": checkpoint.digest(allocation), "candidate_id": candidate}
        if output.exists():
            require(resume, "Existing output requires explicit resume")
            require(checkpoint.restore(output / "run_identity.json") == binding, "Selection resume identity mismatch")
        else:
            require(not resume, "Resume output missing")
            output.mkdir(parents=True)
            checkpoint.commit(output / "run_identity.json", binding)

        def measured_commit(path, payload):
            require(Path(path).resolve().is_relative_to(output.resolve()), "Checkpoint write outside candidate output")
            size_before = Path(path).stat().st_size if Path(path).exists() else 0
            t = time.perf_counter()
            value = original_commit(path, payload)
            budget.flush(bytes_added=max(0, Path(path).stat().st_size - size_before), flush_seconds=time.perf_counter() - t)
            return value
        checkpoint.commit = measured_commit
        if not resume:
            receipt["store_probe"] = checkpoint.probe_store(output / "probe")
        ids = contract["selection_ids"]
        for row in sources:
            saved = output / "records" / (row["record_id"].replace(":", "-") + ".json")
            if saved.exists():
                existing = checkpoint.restore(saved)
                require(existing["binding"] == binding and existing["source_sha256"] == row["source_normalized_sha256"],
                        "Saved selection record identity mismatch")
                require(existing["status"] in ("started", "failed", "completed", "completed_with_warning"),
                        "Invalid saved record status")
                receipt["records"][row["record_id"]] = existing
        if resume:  # validate every envelope; no corrupt or orphan attempt is repaired
            for path in output.rglob("*.json"):
                if path.name != "candidate_receipt.json":
                    checkpoint.restore(path)
        # A `started` record (VM lost mid-record) is terminal: it is never retried and counts as interrupted.
        if resume and len(receipt["records"]) == len(ids) and all(
                r["status"] in ("completed", "completed_with_warning", "failed", "started") for r in receipt["records"].values()):
            runtime_ids = {r["runtime_sha256"] for r in receipt["records"].values()}
            require(len(runtime_ids) == 1, "Cached candidate has inconsistent runtime identities")
            for row in sources:
                saved = receipt["records"][row["record_id"]]
                require(saved["quality"] is None, "Generation quality must remain NULL")
                if saved["status"] not in ("failed", "started"):
                    result = saved["result"]
                    require(saved["validation"]["acceptance"]["status"] == saved["status"]
                            and result["delivery"] == delivery.select_delivered(result["raw_final"], 350)
                            and result["delivered_final"] == result["delivery"]["text"], "Cached acceptance/delivery mismatch")
                    for node in result.get("nodes", []):
                        require(node["canonical_source_sha256"] == row["source_normalized_sha256"]
                                and hashlib.sha256(node["output_text"].encode()).hexdigest() == node["output_sha256"],
                                "Cached node/source/output hash mismatch")
            receipt.update(runtime_sha256=next(iter(runtime_ids)), execution_mode="cached_candidate_resume",
                           runtime_verification="prior bound runtime; no model reload or fresh latency claim",
                           model_load_wall_seconds=0, cached_reused_records=len(ids), fresh_new_outputs=0)
            receipt["summary"] = summary(receipt["records"], ids)
            receipt["status"] = receipt["terminal_status_if_real"] = (
                "COMPLETED_WITH_FAILURES" if receipt["summary"]["failed_or_interrupted"] else "PASS")
            if dependencies:
                receipt["status"] = "HOLD"
            return receipt
        attempted_keys = {checkpoint.digest(checkpoint.restore(p)["key"])
                          for p in (output / "nodes" / "attempts").glob("*.json")}
        neural = candidate in PREFERRED
        environment = dependencies.environment(candidate) if dependencies else runtime_environment(candidate)
        receipt["environment"] = environment
        stage_forecast = {}
        if neural:
            stage_forecast = dict(forecast["stage_seconds"][candidate])
            require(all(v > 0 for v in stage_forecast.values()), "Missing node cost forecasts")
            receipt["node_admission_forecast"] = {"stage_seconds": dict(stage_forecast), "rule": forecast["rule"],
                                                  "source": "Pilot40 measured nodes; operational guard, not a statistical bound"}
            budget.guard(forecast_seconds=forecast["load_seconds"][candidate])
            receipt["asset_admission"] = (dependencies.admit_assets(profile["profile"], budget) if dependencies
                                          else admit_assets(profile["profile"], budget))
            load_started = time.perf_counter()
            load_sample = dependencies.sample(True) if dependencies else ResourceSample(True)
            with load_sample as init_resources:
                receipt["model_load_resources"] = init_resources
                model, tokenizer = (dependencies.load_assets(profile["profile"], environment) if dependencies
                                    else runtime.load_runtime_assets(profile["profile"], environment))
            receipt["model_load_wall_seconds"] = time.perf_counter() - load_started
            runtime_sha = runtime.runtime_identity(environment)
        else:
            runtime_sha = checkpoint.digest(environment)
            receipt["model_load_wall_seconds"] = 0
        for existing in receipt["records"].values():
            require(existing["runtime_sha256"] == runtime_sha, "Saved selection runtime mismatch; no forced reuse")
        receipt["runtime_sha256"] = runtime_sha
        for row in sources:
            identifier = row["record_id"]
            if identifier in receipt["records"]:
                continue  # includes started/failed: an attempted record is never retried
            budget.guard()
            path = output / "records" / (identifier.replace(":", "-") + ".json")
            record = {"record_id": identifier, "source_sha256": row["source_normalized_sha256"],
                      "source_stratum": row["source_stratum"], "binding": binding, "runtime_sha256": runtime_sha,
                      "status": "started", "origin": "fresh", "quality": None, "retain_in_denominator": True,
                      "automatic_retry": False}
            receipt["records"][identifier] = record
            checkpoint.commit(path, record)
            generator = None
            result, events, resources, stage_resources = None, [], {}, []
            try:
                sample = dependencies.sample(neural) if dependencies else ResourceSample(neural)
                with sample as resources:
                    if neural:
                        backend = (dependencies.backend(model, tokenizer, profile, candidate) if dependencies else
                                   bindings.LoadedGenerator(model, tokenizer, architecture=profile["profile"]["architecture"],
                                                            device="cuda:0", decode_parameters=profile["profile"]["decode"],
                                                            led_global_attention=candidate == "led"))

                        class Backend:
                            last_receipt = None

                            def __call__(self, batch, maximum, stage):
                                require(stage in stage_forecast, "Unknown stage capacity: HOLD before generation")
                                budget.guard(forecast_seconds=stage_forecast[stage])
                                t, cpu = time.perf_counter(), time.process_time()
                                receipt["new_generation_calls"] += 1
                                try:
                                    return backend(batch, maximum, stage)
                                finally:
                                    self.last_receipt = backend.last_receipt
                                    elapsed = time.perf_counter() - t
                                    receipt["new_generation_wall_seconds"] += elapsed
                                    stage_resources.append({"stage": stage, "wall_seconds": elapsed,
                                                            "cpu_seconds": time.process_time() - cpu})
                                    stage_forecast[stage] = max(stage_forecast[stage], elapsed * 1.5)
                                    budget.flush()

                        def before_call(key):
                            budget.guard(checkpoint_reserve_bytes=4 * 1024 * 1024)
                            key_hash = checkpoint.digest(key)
                            require(key_hash not in attempted_keys, "Node already attempted; automatic retry forbidden")
                            attempted_keys.add(key_hash)
                            if dependencies is None:
                                import torch
                                seed = development_node_seed(key)
                                torch.manual_seed(seed)
                                torch.cuda.manual_seed_all(seed)
                        generator = checkpoint.NodeCheckpointGenerator(
                            Backend(), output / "nodes",
                            {**binding, "record_id": identifier, "source_sha256": row["source_normalized_sha256"],
                             "runtime_sha256": runtime_sha}, budget.deadline, before_call=before_call)
                        result = generation.summarize_source(
                            row["source_normalized"], **(dependencies.native_bindings(tokenizer, profile) if dependencies
                                                         else bindings.native_bindings(tokenizer, profile["profile"])),
                            generate=generator, selector=delivery.select_delivered, word_cap=350)
                        events = generator.events
                        record.update(stage_resources=stage_resources,
                                      new_generation_wall_seconds=sum(e["new_attempt_wall_seconds"] for e in events))
                    else:
                        cpu_fn = {"lead3": lead3, "lexrank": lexrank}[candidate]
                        result = cpu_fn(row["source_normalized"], word_cap=350)
                        events = []
                    record["result"] = result
                    validated = (validate_neural(row["source_normalized"], result, events, tokenizer, profile["profile"],
                                                 environment["resolved_generation_config"]) if neural
                                 else validate_cpu(row["source_normalized"], result, candidate))
                    record.update(status=validated["acceptance"]["status"], validation=validated, result=result,
                                  events=events, calls=dict(Counter(n["stage"] for n in result.get("nodes", []))),
                                  native_tokens=sum(e["backend_receipt"]["generated_native_tokens"] for e in events),
                                  maximum_layer=max((n["layer"] for n in result.get("nodes", [])), default=0),
                                  delivered_words=len(result["delivered_final"].split()), delivery=result["delivery"])
                record["resources"] = resources
            except Exception as error:
                record.update(status="failed", quality=None, error=f"{type(error).__name__}: {error}")
                if generator is not None:
                    record["events"] = generator.events
            finally:
                record["resources"] = resources
                record["stage_resources"] = stage_resources
                if generator is not None:
                    record["events"] = generator.events
                record["new_generation_wall_seconds"] = sum(s["wall_seconds"] for s in stage_resources)
                record["new_generation_calls"] = len(stage_resources)
                if result is not None:
                    record["result"] = result
            checkpoint.commit(path, record)
            print(json.dumps({"candidate_id": candidate, "record_id": identifier, "status": record["status"]},
                             allow_nan=False), flush=True)
            budget.guard()
        receipt["summary"] = summary(receipt["records"], ids)
        if receipt["summary"]["pending"] == 0:  # interrupted (`started`) records count as failed_or_interrupted
            receipt["status"] = receipt["terminal_status_if_real"] = (
                "COMPLETED_WITH_FAILURES" if receipt["summary"]["failed_or_interrupted"] else "PASS")
        if dependencies:
            receipt["status"] = "HOLD"
    except Exception as error:
        receipt.update(status="HOLD", error=f"{type(error).__name__}: {error}")
    finally:
        checkpoint.commit = original_commit
        if "contract" in locals():
            receipt["summary"] = summary(receipt["records"], contract["selection_ids"])
        receipt.update(total_wall_seconds=time.monotonic() - started)
        if budget:
            try:
                budget.flush(final=True)
                receipt["resource_ledger"] = budget.ledger
            except Exception as error:
                receipt.update(status="HOLD", resource_ledger_error=str(error))
        if output.exists():
            atomic_json(output / "candidate_receipt.json", receipt)
        if model is not None:
            model = tokenizer = None
            gc.collect()
            if not dependencies:
                import torch
                torch.cuda.empty_cache()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("bundle", "output", "allocation", "authorization"):
        parser.add_argument("--" + option, required=True, type=Path)
    parser.add_argument("--candidate", required=True, choices=CANDIDATES)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--wall-hours", required=True, type=float)
    args = parser.parse_args()
    result = run(args.bundle, args.output, args.candidate, resume=args.resume, wall_hours=args.wall_hours,
                 allocation=json.loads(args.allocation.read_text(encoding="utf-8")),
                 authorization=json.loads(args.authorization.read_text(encoding="utf-8")))
    print(json.dumps({"status": result["status"], "summary": result.get("summary"), "error": result.get("error")},
                     allow_nan=False), flush=True)
    return 0 if result["status"] in ("PASS", "COMPLETED_WITH_FAILURES") else 1


if __name__ == "__main__":
    raise SystemExit(main())
