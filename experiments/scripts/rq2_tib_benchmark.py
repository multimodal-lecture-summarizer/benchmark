"""TIB benchmark entry point: prepare data automatically, then run paired S1/S3."""

import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from experiments.scripts import rq2_tib_benchmark_dataset as data
from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts.rq2_tib_benchmark_pair import run_source_pair


def load_or_prepare_data(path, *, rebuild=False, rows_by_split=None, verify_counts=True):
    """Shared by the benchmark and preparation notebook; no prior prep run needed."""
    path = Path(path)
    if path.exists() and not rebuild:
        return bundles.load_benchmark_bundle(path)
    rows = rows_by_split if rows_by_split is not None else data.load_pinned_splits(data.SPLITS)
    prepared = data.prepare_dataset(rows, verify_counts=verify_counts)
    bundle = bundles.build_benchmark_bundle(prepared)
    bundles.save_benchmark_bundle(bundle, path, overwrite=rebuild)
    return bundle


@dataclass(frozen=True)
class BenchmarkConfig:
    chunk_tokens: int = 512
    map_output_tokens: int = 96
    final_output_tokens: int = 384
    seed: int = 42
    temperature: float = 0.0
    bootstrap_samples: int = 5000
    bootstrap_seed: int = 20261009

    def validate(self):
        budgets = (self.chunk_tokens, self.map_output_tokens, self.final_output_tokens, self.bootstrap_samples)
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in budgets):
            raise ValueError("Token budgets must be positive")
        if self.temperature != 0:
            raise ValueError("This runner uses deterministic greedy decoding")


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _save_result(value, path):
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=1, allow_nan=False)
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as exc:
                # Windows indexers can briefly lock a just-replaced checkpoint.
                # Preserve atomic replacement and still surface persistent errors.
                if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 4:
                    raise
                time.sleep(.05 * (attempt + 1))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)



def run_benchmark(backend, *, data_path, output_dir, config=None, rebuild_data=False,
                  rows_by_split=None, verify_counts=True, progress=None, semantic_scorer="auto",
                  phase="all", summarize=True, on_event=None):
    """Single benchmark call includes acquisition, processing, generation and scoring.

    Existing completed predictions resume by full run/item identity. Failed
    items remain in the denominator and are retried on the next invocation.
    """
    from experiments.scripts.rq2_tib_benchmark_results import (
        SCORER, score_pair, summarize_results, validate_semantic_scores,
    )

    if phase not in {"all", "generate", "evaluate"}:
        raise ValueError("phase must be all, generate or evaluate")
    config = config or BenchmarkConfig()
    config.validate()
    def emit(**event):
        if on_event:
            on_event(event)
    emit(stage="data", status="started")
    if phase == "generate":
        semantic_scorer = None
    elif semantic_scorer == "auto":
        from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
        semantic_scorer = SemanticScorer()
    bundle = load_or_prepare_data(data_path, rebuild=rebuild_data,
                                 rows_by_split=rows_by_split, verify_counts=verify_counts)
    emit(stage="data", status="completed", total=len(bundle["items"]))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Retain legacy default cache identity, but aggregation-only settings must
    # never invalidate generation. These historical placeholders are not used
    # for bootstrap computation; summarize_results gets the requested settings.
    generation_config = {**asdict(config), "bootstrap_samples": 5000, "bootstrap_seed": 20261009}
    run_identity = _hash({"selection": bundle["metadata"]["selection_sha256"],
                          "config": generation_config, "model": backend.model_id,
                          "tokenizer": backend.tokenizer_id, "runner_version": 1, "scorer": SCORER})
    results = []
    for index, item in enumerate(bundle["items"], 1):
        source = bundles.generation_input(item)
        identity = _hash({"run": run_identity, "id": source["id"],
                          "source": item["source_sha256"], "reference": item["reference_sha256"],
                          "timed_segments": _hash(source["transcript_segments"])})
        path = output_dir / f"{item['split']}-{item['source_index']}.json"
        def item_event(event):
            emit(**{**event, "index":index, "total":len(bundle["items"]), "id":source["id"]})
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if phase == "evaluate" and old is None:
            raise FileNotFoundError(f"Generation checkpoint missing; run generation cell first: {path}")
        if old is not None:
            checksum = old.get("result_sha256")
            if old.get("identity_sha256") != identity or checksum != _hash({k:v for k,v in old.items() if k != "result_sha256"}):
                raise ValueError(f"Existing prediction identity/content differs: {path}")
        if old is not None and old.get("status") == "completed":
            result = old
            item_event({"stage":"generation", "status":"reused"})
        elif phase == "evaluate":
            result = old
            item_event({"stage":"evaluation", "status":"skipped", "reason":old["status"]})
        else:
            result = {"id": source["id"], "split": item["split"], "source_index": item["source_index"],
                      "doi": item["doi"], "genre": item["genre"], "subject": item["subject"],
                      "duration_minutes": item["duration_minutes"], "identity_sha256": identity,
                      "run_sha256": run_identity, "source_sha256": item["source_sha256"],
                      "reference_sha256": item["reference_sha256"], "config": asdict(config)}
            if old is not None:
                result["prior_attempts"] = old.get("prior_attempts", []) + [{
                    "arms": old.get("arms", {}), "seconds": old.get("seconds", 0),
                    "error": old.get("error", ""), "status": old["status"],
                    "shared_preparation_seconds": old.get("shared_preparation_seconds")}]
            started = time.perf_counter()
            def checkpoint(partial):
                result.update(partial, status="in_progress", seconds=time.perf_counter() - started)
                _save_result({**result, "result_sha256": _hash(result)}, path)
            try:
                result.update(run_source_pair(source, backend, config,
                    completed_arms=old.get("arms", {}) if old else None, on_progress=checkpoint, on_event=item_event))
                item_event({"stage":"rouge_l", "status":"started"})
                result["scores"] = score_pair(result["arms"], bundles.evaluation_target(item)["reference_text"])
                result["status"] = "completed"
                item_event({"stage":"rouge_l", "status":"completed", "scores":result["scores"]})
            except (ValueError, RuntimeError, OSError) as exc:
                result.update(getattr(exc, "partial_pair", {}))
                item_event({"stage":"generation", "status":"failed", "error":str(exc)})
                result.update(status="failed", error_type=getattr(exc, "original_error_type", type(exc).__name__), error=str(exc))
            result["seconds"] = time.perf_counter() - started
            result["result_sha256"] = _hash(result)
            _save_result(result, path)
        # Evaluation has a separate identity so adding/changing scorers never
        # invalidates saved generation. A failed score is retried, not regenerated.
        if phase != "generate" and result["status"] == "completed" and semantic_scorer is not None:
            evaluation = {"scorer": semantic_scorer.metadata,
                          "prediction": _hash({name: arm["summary"] for name, arm in result["arms"].items()}),
                          "source": item["source_sha256"], "reference": item["reference_sha256"]}
            evaluation_identity = _hash(evaluation)
            if result.get("evaluation_sha256") != evaluation_identity or result.get("evaluation_status") != "completed":
                evaluation_history = list(result.get("evaluation_attempts", []))
                if not evaluation_history and result.get("evaluation_status"):
                    evaluation_history.append({"identity": result.get("evaluation_sha256"),
                        "configuration": result.get("evaluation_config"), "status": result["evaluation_status"],
                        "seconds": result.get("evaluation_seconds", 0), "error": result.get("evaluation_error")})
                item_event({"stage":"evaluation", "status":"started"})
                score_started = time.perf_counter()
                result.pop("semantic_scores", None)
                result.pop("evaluation_error", None)
                original_callback = getattr(semantic_scorer, "on_event", None)
                if on_event is not None and hasattr(semantic_scorer, "on_event"):
                    semantic_scorer.on_event = item_event
                try:
                    result["semantic_scores"] = validate_semantic_scores(semantic_scorer.score_pair(
                        result["arms"], bundles.evaluation_target(item)["reference_text"], source["transcript"]))
                    result["evaluation_status"] = "completed"
                except (ValueError, RuntimeError, OSError, ImportError) as exc:
                    result.update(evaluation_status="failed", evaluation_error=f"{type(exc).__name__}: {exc}")
                finally:
                    if on_event is not None and hasattr(semantic_scorer, "on_event"):
                        semantic_scorer.on_event = original_callback
                item_event({"stage":"evaluation", "status":result["evaluation_status"], "error":result.get("evaluation_error")})
                result.update(evaluation_sha256=evaluation_identity, evaluation_config=evaluation["scorer"],
                              evaluation_seconds=time.perf_counter() - score_started)
                result["evaluation_attempts"] = evaluation_history + [{"identity": evaluation_identity,
                    "configuration": evaluation["scorer"], "status": result["evaluation_status"],
                    "seconds": result["evaluation_seconds"], "error": result.get("evaluation_error")}]
                result.pop("result_sha256", None)
                result["result_sha256"] = _hash(result)
                _save_result(result, path)
            else:
                item_event({"stage":"evaluation", "status":"reused"})
        results.append(result)
        if progress:
            progress(index, len(bundle["items"]), result)
    benchmark = {"metadata": bundle["metadata"], "results": results, "summary": None,
                 "run_sha256": run_identity,
                 "evaluation_configuration": semantic_scorer.metadata if semantic_scorer is not None else None}
    if summarize:
        emit(stage="aggregation", status="started")
        summarize_benchmark(benchmark, output_dir=output_dir, config=config)
        emit(stage="aggregation", status="completed")
    return benchmark


def summarize_benchmark(benchmark, *, output_dir, config=None):
    """Aggregate already saved generation/evaluation; never loads an encoder."""
    from experiments.scripts.rq2_tib_benchmark_results import summarize_results
    config = config or BenchmarkConfig()
    config.validate()
    results, metadata = benchmark["results"], benchmark["metadata"]
    summary = summarize_results(results, bootstrap_samples=config.bootstrap_samples, seed=config.bootstrap_seed)
    summary.update(run_sha256=benchmark["run_sha256"], selected_count=len(results),
                   selection_sha256=metadata["selection_sha256"])
    summary["evaluation"] = {"configuration": benchmark.get("evaluation_configuration"),
                             "completed": sum(row.get("evaluation_status") == "completed" for row in results),
                             "failed": sum(row.get("evaluation_status") == "failed" for row in results),
                             "seconds": sum(sum(attempt["seconds"] for attempt in row["evaluation_attempts"])
                                            if row.get("evaluation_attempts") else row.get("evaluation_seconds", 0)
                                            for row in results)}
    _save_result(summary, Path(output_dir) / "summary.json")
    benchmark["summary"] = summary
    return benchmark
