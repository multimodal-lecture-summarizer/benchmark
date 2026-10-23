"""Score Pilot40 outputs with the frozen scorer v2 and time each component; never generate.

Pass 1 scores the delivered summaries with all five scorer-v2 metrics (long sources first, so a
deadline still leaves the tail measured). Pass 2 scores the S/M/L budget views with the lexical and
BERTScore metrics only. Failed generation cells stay in the denominator with NULL metrics.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

from .tib_benchmark_scorer import METRICS, score_record, validate_assets
from .tib_scorer_colab_checkpoint import ScoreCheckpoints, digest, file_sha
from .tib_scorer_colab_resources import (
    ResourceSampler, input_profile, observe_runtime, resource_errors, synchronize,
)
from .tib_scorer_colab_runner import _finite_result, _write

VIEW_METRICS = ("rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1")
VIEW_NAMES = ("S", "M", "L")
STRATUM_ORDER = {"long": 0, "medium": 1, "short": 2}
STATUSES = {"completed", "completed_with_warning", "failed"}
# Fixed by protocol (Qwen3 dropped 2026-10-23); the bundle's own amendment cannot widen them.
PROFILES = {"lead3", "lexrank", "bart", "led"}
EXPECTED_ROWS, EXPECTED_SCOREABLE = 160, 154


def validate_pilot_bundle(root):
    """Reject modified code, inputs or denominators before any output is scored."""
    root = Path(root).resolve()
    manifest = json.loads((root / "package_manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
              and p.name != "package_manifest.json"
              and not ("__pycache__" in p.parts and p.suffix == ".pyc")}
    if not files or set(files) != actual:
        raise ValueError("Package manifest file set mismatch")
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or file_sha(path) != expected:
            raise ValueError("Package hash/path mismatch: " + name)
    spec = json.loads((root / "frozen_scorer_spec.json").read_text(encoding="utf-8"))
    amendment = json.loads((root / "runtime_amendment.json").read_text(encoding="utf-8"))
    if amendment["frozen_spec_sha256"] != file_sha(root / "frozen_scorer_spec.json"):
        raise ValueError("Frozen scorer spec binding mismatch")
    for name, expected in spec["code_sha256"].items():
        if files.get(name) != expected:
            raise ValueError("Frozen scorer code mismatch: " + name)
    rows = [json.loads(line) for line in
            (root / "pilot_outputs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    profiles = amendment["profile_ids"]
    if (set(profiles) != PROFILES or len(rows) != EXPECTED_ROWS
            or amendment["expected_output_count"] != EXPECTED_ROWS):
        raise ValueError("Wrong profile universe or output count")
    ids = {row["record_id"] for row in rows}
    grid = {(row["record_id"], row["profile_id"]) for row in rows}
    if len(grid) != len(rows) or len({r["sample_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate cell or sample_id")
    if grid != {(i, p) for i in ids for p in profiles}:
        raise ValueError("Incomplete pilot matrix")
    sources = {}
    for row in rows:
        for text, key in (("source", "source_sha256"), ("reference", "reference_sha256")):
            if hashlib.sha256(row[text].encode("utf-8")).hexdigest() != row[key]:
                raise ValueError("Stored text/hash mismatch: " + text)
        if sources.setdefault(row["record_id"], (row["source_sha256"], row["reference_sha256"])) != (
                row["source_sha256"], row["reference_sha256"]):
            raise ValueError("Different source/reference for the same record")
        if row["candidate_id"] != row["profile_id"] or not re.fullmatch(r"[a-f0-9]{64}", row["source_receipt_sha256"]):
            raise ValueError("Candidate/profile or receipt binding invalid")
        if row["generation_status"] not in STATUSES or row["source_stratum"] not in STRATUM_ORDER:
            raise ValueError("Invalid status/stratum")
        if row["scoreable"] != (row["generation_status"] != "failed"):
            raise ValueError("Scoreable flag disagrees with generation status")
        if row["scoreable"]:
            delivered = row["delivered_summary"]
            if (not isinstance(delivered, str) or not delivered.strip()
                    or hashlib.sha256(delivered.encode("utf-8")).hexdigest() != row["delivered_sha256"]
                    or len(delivered.split()) > 350):
                raise ValueError("Delivered summary hash/cap mismatch")
            if (not row.get("views") or set(row["views"]) != set(VIEW_NAMES)
                    or not all(isinstance(t, str) and t.strip() for t in row["views"].values())):
                raise ValueError("Scoreable row lacks non-empty S/M/L views")
        elif not row.get("failure_reason"):
            raise ValueError("Failed cell without recorded reason")
    if (sum(r["scoreable"] for r in rows) != EXPECTED_SCOREABLE
            or amendment["expected_scoreable_count"] != EXPECTED_SCOREABLE):
        raise ValueError("Scoreable count differs from the amendment")
    return manifest, spec, amendment, rows


def run_order(rows):
    """Long sources first, then by sample_id; failed cells are never scored."""
    return sorted((r for r in rows if r["scoreable"]),
                  key=lambda r: (STRATUM_ORDER[r["source_stratum"]], r["sample_id"]))


def describe(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "sum": 0.0, "mean": None, "p50": None, "p90": None, "max": None}
    def at(q):
        pos = (len(values) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return values[lo] + (values[hi] - values[lo]) * (pos - lo)
    return {"n": len(values), "sum": sum(values), "mean": statistics.fmean(values),
            "p50": at(0.5), "p90": at(0.9), "max": values[-1]}


class ComponentTimer:
    """Time the two neural calls of scorer v2 without changing their arithmetic."""

    def __init__(self, scorer, sync):
        self.totals = {"bertscore": 0.0, "sentence_vectors": 0.0}
        self.calls = {"bertscore": 0, "sentence_vectors": 0}
        for name, key in (("_bertscore", "bertscore"), ("_sentence_vectors", "sentence_vectors")):
            setattr(scorer, name, self._wrap(getattr(scorer, name), key, sync))

    def _wrap(self, original, key, sync):
        def timed(*args, **kwargs):
            sync()
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                sync()
                self.totals[key] += time.perf_counter() - start
                self.calls[key] += 1
        return timed

    def snapshot(self):
        return dict(self.totals), dict(self.calls)


def score_view(text, reference, scorer):
    """Same lexical configuration and BERTScore call as score_record; no source similarity."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty_or_invalid_view")  # never impute a zero BERTScore
    from rouge_score.rouge_scorer import RougeScorer
    if importlib.metadata.version("rouge-score") != "0.1.2":
        raise ValueError("Expected rouge-score==0.1.2")
    scores = RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True).score(reference, text)
    metrics = {name + "_f1": float(value.fmeasure) for name, value in scores.items()}
    metrics["bertscore_f1"] = float(scorer._bertscore(text, reference))
    return {"metrics": metrics, "failures": {}}


def _view_result(result):
    metrics, failures = result.get("metrics", {}), dict(result.get("failures", {}))
    clean = {}
    for name in VIEW_METRICS:
        value = metrics.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            clean[name] = float(value)
        else:
            clean[name] = None
            failures.setdefault(name, "undefined_or_nonfinite_metric")
    return {"metrics": clean, "failures": failures}


def run(bundle, output, assets, *, resume=False, wall_hours=1.5, backend_factory=None,
        fixture_runner=None, runtime_probe=None, score_function=None, view_function=None,
        asset_validator=None, sampler_factory=None):
    """Injection hooks test orchestration without model downloads or GPU claims."""
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    bundle, output, assets = Path(bundle), Path(output), Path(assets)
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    run_id = str(time.time_ns())
    archive = output / "runs" / run_id
    archive.mkdir(parents=True)
    rows, results, view_results, reasons = [], [], [], []
    runtime, binding, fixtures, metadata, amendment = {}, None, None, None, {}
    costs = {"initialization_seconds": 0.0, "fixtures_seconds": 0.0, "delivered_scoring_seconds": 0.0,
             "view_scoring_seconds": 0.0, "checkpoint_seconds": 0.0, "validation_seconds": 0.0,
             "input_profiling_seconds": 0.0, "new_metric_calls": 0, "new_view_calls": 0,
             "reused_records": 0, "reused_identical_view_texts": 0}
    injected = any(v is not None for v in (backend_factory, fixture_runner, runtime_probe, score_function,
                                          view_function, asset_validator, sampler_factory))
    sync = (lambda: None) if injected else synchronize
    sampler, resources, views_status, timer = None, {}, "NOT_STARTED", None
    component_after_pass1 = None
    expected_scoreable = 0
    try:
        if not 0 < wall_hours <= 11.5:
            raise ValueError("Scorer session bound must be positive and at most 11.5 hours")
        deadline = started + wall_hours * 3600
        tick = time.perf_counter()
        manifest, spec, amendment, rows = validate_pilot_bundle(bundle)
        expected_scoreable = amendment["expected_scoreable_count"]
        runtime = (runtime_probe or observe_runtime)()
        normalized = {n.lower().replace("_", "-"): v for n, v in runtime["packages"].items()}
        if not (runtime.get("google_colab_imported") and runtime.get("cuda_available")
                and runtime.get("T4_device_observed")):
            raise ValueError("Actual Google Colab CUDA T4 evidence required")
        if not amendment.get("runtime_pins"):
            raise ValueError("Colab runtime package amendment missing runtime pins")
        for key in ("runtime_pins", "support_package_pins"):
            if any(normalized.get(n.lower().replace("_", "-")) != pin for n, pin in amendment[key].items()):
                raise ValueError("Colab runtime package amendment mismatch: " + key)
        if (not isinstance(runtime.get("device_memory_bytes"), int) or runtime["device_memory_bytes"] <= 0
                or runtime.get("device_name") not in ("Tesla T4", "NVIDIA T4", "NVIDIA Tesla T4")):
            raise ValueError("Missing measured T4 device capacity")
        from .tib_scorer_colab_backend import RuntimeSemanticScorer, runtime_fixtures, runtime_pins
        if amendment["runtime_pins"] != runtime_pins():
            raise ValueError("Backend pins differ from runtime amendment")
        if not injected:
            loaded = list(sys.modules.values())
            for module in loaded:
                filename = getattr(module, "__file__", None)
                name = getattr(module, "__name__", "")
                if filename and filename.endswith(".py") and (name.startswith("experiments.scripts.")
                                                              or name == "__main__"):
                    relative = "experiments/scripts/" + Path(filename).name
                    if manifest["files"].get(relative) != file_sha(filename):
                        raise ValueError("Executing unbound scorer module: " + name)
        check_assets = asset_validator or validate_assets
        bert = check_assets(assets / "bert", model=spec["bertscore"]["model"],
                            revision=spec["bertscore"]["model_revision"])
        sentence = check_assets(assets / "sentence", model=spec["source_similarity"]["model"],
                                revision=spec["source_similarity"]["model_revision"])
        binding = {"package_manifest_sha256": file_sha(bundle / "package_manifest.json"),
                   "frozen_spec_sha256": amendment["frozen_spec_sha256"],
                   "runtime_amendment_sha256": file_sha(bundle / "runtime_amendment.json"),
                   "evidence_zip_sha256": amendment["evidence_zip_sha256"],
                   "code_input_files_sha256": digest(manifest["files"]),
                   "asset_manifests_sha256": {n: file_sha(p / "asset_manifest.json")
                                              for n, p in (("bert", bert), ("sentence", sentence))},
                   "runtime_sha256": digest(runtime)}
        costs["validation_seconds"] = time.perf_counter() - tick
        store = ScoreCheckpoints(output / "checkpoints", binding, resume=resume)
        view_store = ScoreCheckpoints(output / "view_checkpoints", binding, resume=resume)
        ordered = run_order(rows)

        def view_key(row):
            return {"sample_id": row["sample_id"] + "__views", "views": row["views"],
                    "reference_sha256": row["reference_sha256"]}

        # Validate every cache entry before expensive initialization; never fill holes on resume.
        cached = {r["sample_id"]: store.load(r) for r in ordered} if resume else {}
        view_cached = {r["sample_id"]: view_store.load(view_key(r)) for r in ordered} if resume else {}
        sampler = (sampler_factory or ResourceSampler)().start()
        tick = time.perf_counter()
        scorer = (backend_factory or RuntimeSemanticScorer)(bert, sentence)
        scorer._load()
        sync()
        metadata = scorer.metadata
        costs["initialization_seconds"] = time.perf_counter() - tick
        tick = time.perf_counter()
        fixtures = (fixture_runner or runtime_fixtures)(scorer)
        sync()
        costs["fixtures_seconds"] = time.perf_counter() - tick
        if str(fixtures.get("status", "")).lower() != "pass":
            raise ValueError("Actual scorer fixtures/probes did not PASS")
        timer = ComponentTimer(scorer, sync)

        # ---- pass 1: delivered summaries, all five scorer-v2 metrics -------------------------
        for row in ordered:
            if time.monotonic() >= deadline:
                reasons.append("session_deadline")
                break
            print("Scorer", "reuse" if resume else "score", row["sample_id"], flush=True)
            base = {k: row[k] for k in ("sample_id", "record_id", "candidate_id", "profile_id",
                                       "source_stratum", "generation_status", "warnings",
                                       "source_receipt_sha256")}
            profile_start = time.perf_counter()
            shape = input_profile(row, scorer)
            costs["input_profiling_seconds"] += time.perf_counter() - profile_start
            sync()
            before, calls_before = timer.snapshot()
            tick, cpu_tick = time.perf_counter(), time.process_time()
            if resume:
                payload = cached[row["sample_id"]]
                scored = _finite_result(payload["result"])
                elapsed, cpu_elapsed, reused = 0.0, 0.0, True
                costs["reused_records"] += 1
            else:
                try:
                    scored = _finite_result((score_function or score_record)(
                        row["delivered_summary"], row["reference"], row["source"], semantic=scorer))
                    sync()
                except Exception as error:
                    scored = {"metrics": dict.fromkeys(METRICS),
                              "failures": {"record": f"{type(error).__name__}: {error}"}}
                elapsed, reused = time.perf_counter() - tick, False
                cpu_elapsed = time.process_time() - cpu_tick
                costs["delivered_scoring_seconds"] += elapsed
                costs["new_metric_calls"] += 1
                start = time.perf_counter()
                store.save(row, scored, elapsed)
                costs["checkpoint_seconds"] += time.perf_counter() - start
            after, calls_after = timer.snapshot()
            bert_seconds = after["bertscore"] - before["bertscore"]
            sentence_seconds = after["sentence_vectors"] - before["sentence_vectors"]
            results.append({**base, **scored, "reused": reused, "scoring_status":
                            "completed" if not scored["failures"] else "failed",
                            "new_scoring_wall_seconds": elapsed, "new_scoring_cpu_seconds": cpu_elapsed,
                            "bertscore_seconds": bert_seconds, "source_similarity_seconds": sentence_seconds,
                            "rouge_and_other_seconds": max(0.0, elapsed - bert_seconds - sentence_seconds),
                            "source_sentence_count": shape["source_sentence_count"],
                            "sentence_vector_calls": calls_after["sentence_vectors"] - calls_before["sentence_vectors"],
                            "input_profile": shape})

        component_after_pass1 = {"totals": dict(timer.totals), "calls": dict(timer.calls)}

        # ---- pass 2: S/M/L views, lexical + BERTScore only ----------------------------------
        by_id = {r["sample_id"]: r for r in results}
        if not reasons:
            views_status = "RUNNING"
            for row in ordered:
                if time.monotonic() >= deadline:
                    views_status = "PARTIAL_DEADLINE"
                    break
                delivered_metrics = {k: by_id[row["sample_id"]]["metrics"].get(k) for k in VIEW_METRICS}
                scored_views, seen = {}, {row["delivered_summary"]: delivered_metrics}
                view_wall, new_calls, reused_flags = 0.0, 0, {}
                if resume:
                    scored_views = view_cached[row["sample_id"]]["result"]
                    reused_flags = dict.fromkeys(VIEW_NAMES, True)
                else:
                    for name in VIEW_NAMES:
                        text = row["views"][name]
                        if text in seen:
                            scored_views[name] = _view_result({"metrics": dict(seen[text]), "failures": {}})
                            reused_flags[name] = True
                            costs["reused_identical_view_texts"] += 1
                            continue
                        tick = time.perf_counter()
                        try:
                            scored = _view_result((view_function or score_view)(text, row["reference"], scorer))
                        except Exception as error:
                            scored = {"metrics": dict.fromkeys(VIEW_METRICS),
                                      "failures": {"record": f"{type(error).__name__}: {error}"}}
                        sync()
                        view_wall += time.perf_counter() - tick
                        new_calls += 1
                        scored_views[name] = scored
                        seen[text] = scored["metrics"]
                        reused_flags[name] = False
                    costs["view_scoring_seconds"] += view_wall
                    costs["new_view_calls"] += new_calls
                    start = time.perf_counter()
                    view_store.save(view_key(row), scored_views, view_wall)
                    costs["checkpoint_seconds"] += time.perf_counter() - start
                view_results.append({"sample_id": row["sample_id"], "record_id": row["record_id"],
                                     "profile_id": row["profile_id"], "source_stratum": row["source_stratum"],
                                     "views": scored_views, "reused_view": reused_flags,
                                     "new_view_wall_seconds": view_wall, "new_view_calls": new_calls})
            else:
                views_status = "COMPLETE"
            if views_status == "COMPLETE" and any(f for v in view_results for s in v["views"].values()
                                                  for f in s["failures"]):
                views_status = "COMPLETED_WITH_FAILURES"
    except Exception as error:
        reasons.append(f"{type(error).__name__}: {error}")
        if views_status == "RUNNING":
            views_status = "FAILED"
    finally:
        if sampler is not None:
            try:
                resources = sampler.finish()
            except Exception as error:
                reasons.append(f"Resource collection failed: {type(error).__name__}: {error}")

    # Denominator: every cell stays; failed generations and unattempted cells are NULL.
    seen_ids = {r["sample_id"] for r in results}
    for row in rows:
        if row["sample_id"] in seen_ids:
            continue
        failed_generation = not row["scoreable"]
        results.append({**{k: row[k] for k in ("sample_id", "record_id", "candidate_id", "profile_id",
                                               "source_stratum", "generation_status", "warnings")},
                        "metrics": dict.fromkeys(METRICS),
                        "failures": {"record": row["failure_reason"] if failed_generation else "not_scored_due_to_HOLD"},
                        "reused": False, "new_scoring_wall_seconds": 0.0,
                        "scoring_status": "not_scoreable_generation_failed" if failed_generation else "not_attempted"})
    scoreable_ids = {row["sample_id"] for row in rows if row["scoreable"]}
    scoreable_results = [r for r in results if r["sample_id"] in scoreable_ids]
    good = sum(not r["failures"] and all(v is not None for v in r["metrics"].values()) for r in scoreable_results)
    if len(scoreable_results) - good:
        reasons.append("metric_failures_or_unscored_records")
    if resources:
        reasons.extend(resource_errors(resources))
    elif good:
        reasons.append("missing_resource_evidence")
    checks_passed = (not reasons and rows != [] and len(results) == len(rows)
                     and good == len(scoreable_results) == expected_scoreable)
    if injected:
        reasons.append("TEST_DEPENDENCY_INJECTION_NOT_ACTUAL_COLAB_EVIDENCE")
    passed = checks_passed and not injected
    status = "PASS" if passed else "HOLD"
    report = {"delivered_status": status, "views_status": views_status, "reasons": reasons,
              "expected_records": len(rows), "expected_scoreable": expected_scoreable,
              "successful_metric_records": good, "failed_generation_cells": sum(not r["scoreable"] for r in rows),
              "failed_or_unscored_scoreable_records": len(scoreable_results) - good,
              "rankings_computed": False, "generation_executed": False, "qwen3_scored": False,
              "formal_benchmark": False, "run_id": run_id, "orchestration_checks_passed": checks_passed,
              "testing_dependency_injection": injected, "selection_start_authorized": False,
              "scope": "Pilot40 4-profile scoring-cost measurement; descriptive, not selection or admission"}
    receipt = {**report, "scorer_pilot40_ready": passed, "binding": binding, "runtime": runtime,
               "backend_metadata": metadata, "fixtures": fixtures,
               "actual_colab_execution": bool(runtime.get("google_colab_imported")) and not injected,
               "T4_verified": passed, "cached_replay_verified": passed and resume}

    def group(values_of, keys):
        out = {}
        for r in results:
            if r.get("reused") or r["scoring_status"] != "completed":
                continue
            out.setdefault("|".join(str(r[k]) for k in keys), []).append(values_of(r))
        return {name: describe(v) for name, v in sorted(out.items())}

    costs.update(status=status, views_status=views_status, resources=resources,
                 total_wall_seconds=time.monotonic() - started, generation_calls=0,
                 component_after_pass1=component_after_pass1, component_all_passes_totals=timer.totals if timer else None,
                 component_all_passes_calls=timer.calls if timer else None,
                 latency_by_profile=group(lambda r: r["new_scoring_wall_seconds"], ("profile_id",)),
                 latency_by_stratum=group(lambda r: r["new_scoring_wall_seconds"], ("source_stratum",)),
                 latency_by_profile_stratum=group(lambda r: r["new_scoring_wall_seconds"], ("profile_id", "source_stratum")),
                 bertscore_by_stratum=group(lambda r: r["bertscore_seconds"], ("source_stratum",)),
                 source_similarity_by_stratum=group(lambda r: r["source_similarity_seconds"], ("source_stratum",)),
                 checkpoint_storage_bytes=sum(p.stat().st_size for d in ("checkpoints", "view_checkpoints")
                                              if (output / d).exists() for p in (output / d).rglob("*") if p.is_file()))
    for name, value in (("cost_evidence.json", costs), ("PASS_HOLD_report.json", report),
                        ("metrics.jsonl", results), ("view_metrics.jsonl", view_results)):
        _write(archive / name, value, lines=name.endswith(".jsonl"))
        _write(output / name, value, lines=name.endswith(".jsonl"))
    receipt["artifact_sha256"] = {n: file_sha(archive / n) for n in
                                  ("cost_evidence.json", "PASS_HOLD_report.json", "metrics.jsonl", "view_metrics.jsonl")}
    _write(archive / "scorer_pilot40_receipt.json", receipt)
    _write(output / "scorer_pilot40_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("bundle", "output", "assets"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--wall-hours", type=float, default=1.5)
    arguments = parser.parse_args()
    result = run(arguments.bundle, arguments.output, arguments.assets,
                 resume=arguments.resume, wall_hours=arguments.wall_hours)
    print(json.dumps({"delivered_status": result["delivered_status"],
                      "views_status": result["views_status"], "run_id": result["run_id"]}, allow_nan=False))
    raise SystemExit(0 if result["delivered_status"] == "PASS" else 2)
