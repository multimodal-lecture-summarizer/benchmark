"""Offline integration contracts: automatic TIB preparation, paired calls and resume."""

import hashlib
import ast
import json
from pathlib import Path

import pytest

from experiments.scripts import rq2_tib_benchmark as runner
from experiments.scripts import rq2_tib_benchmark_results as scoring


class UsageBackend:
    model_id = "fixture-model"
    tokenizer_id = "fixture-whitespace-v1"

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def count_tokens(self, text):
        return len(text.split())

    def generate(self, prompt, *, max_output_tokens, temperature, seed):
        self.calls.append((prompt, max_output_tokens, temperature, seed))
        if self.fail:
            raise RuntimeError("fixture generation failure")
        text = "source summary"
        return {"text": text, "attempts": [{"status": "success",
                "prompt_tokens": self.count_tokens(prompt), "output_tokens": 2}]}


def test_s3_failure_preserves_s1_usage_and_retry_reuses_completed_arm(tmp_path, rows):
    class FailS3(UsageBackend):
        first_section_seen = False

        def generate(self, prompt, **kwargs):
            if "lecture section 1 " in prompt:
                if self.first_section_seen:
                    raise RuntimeError("S3 fixture failure")
                self.first_section_seen = True
            return super().generate(prompt, **kwargs)

    first = execute(tmp_path, FailS3(), rows)
    failed = first["results"][0]
    assert failed["status"] == "failed"
    assert failed["arms"]["S1"]["status"] == "completed"
    assert failed["arms"]["S1"]["prompt_tokens"] > 0
    assert failed["arms"]["S3"]["status"] == "failed"
    retry_backend = UsageBackend()
    resumed = execute(tmp_path, retry_backend)
    retried = resumed["results"][0]
    assert retried["status"] == "completed"
    assert retried["arms"]["S1"]["reused"]
    assert retried["prior_attempts"][0]["arms"]["S1"]["calls"] == failed["arms"]["S1"]["calls"]
    assert resumed["summary"]["resources"]["known_prompt_tokens"] >= failed["arms"]["S1"]["prompt_tokens"]


def test_interruption_after_s1_has_persisted_checkpoint(tmp_path, rows):
    class InterruptS3(UsageBackend):
        first_section_seen = False

        def generate(self, prompt, **kwargs):
            if "lecture section 1 " in prompt:
                if self.first_section_seen:
                    raise KeyboardInterrupt()
                self.first_section_seen = True
            return super().generate(prompt, **kwargs)

    with pytest.raises(KeyboardInterrupt):
        execute(tmp_path, InterruptS3(), rows)
    checkpoint = json.loads((tmp_path / "predictions/train-0.json").read_text(encoding="utf-8"))
    assert checkpoint["status"] == "in_progress"
    assert checkpoint["arms"]["S1"]["status"] == "completed"
    resumed = execute(tmp_path, UsageBackend())
    assert resumed["results"][0]["arms"]["S1"]["reused"]
    assert resumed["summary"]["resources"]["attempts_with_incomplete_usage"] >= 1


def test_benchmark_notebook_embeds_exact_sources_and_executes_run_cells(tmp_path, rows, monkeypatch):
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda: None)

    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "experiments/notebooks/rq2-tib-benchmark-colab.ipynb").read_text(encoding="utf-8"))
    tree = ast.parse("".join(notebook["cells"][5]["source"]))
    embedded = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)}
    for variable, filename in {
        "PREPARATION_SOURCE": "rq2_tib_benchmark_dataset", "BUNDLE_SOURCE": "rq2_tib_benchmark_bundle",
        "ENGINE_SOURCE": "rq2_controlled_validation", "BACKEND_SOURCE": "rq2_local_hf_backend",
        "RESULTS_SOURCE": "rq2_tib_benchmark_results", "PAIR_SOURCE": "rq2_tib_benchmark_pair",
        "METRICS_SOURCE": "rq2_tib_benchmark_metrics",
        "BENCHMARK_SOURCE": "rq2_tib_benchmark",
    }.items():
        assert embedded[variable] == (root / "experiments/scripts" / f"{filename}.py").read_text(encoding="utf-8")
        compile(embedded[variable], filename, "exec")
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            # User-executed evidence may coexist with updated source cells.
            assert isinstance(cell["outputs"], list)
            compile("".join(cell["source"]), f"cell-{index}", "exec")
    path = tmp_path / "data.gz"
    bundle = runner.load_or_prepare_data(path, rows_by_split=rows, verify_counts=False)
    ns = {"MODEL_ID": "fixture-model", "MODEL_REVISION": "fixture-revision",
          "backend": UsageBackend(), "benchmark_module": runner,
          "BUNDLE_PATH": path, "OUTPUT_DIR": tmp_path,
          "ready": {"selection_sha256": bundle["metadata"]["selection_sha256"]},
          "pd": pd, "plt": plt, "display": lambda *args, **kwargs: None,
          "semantic_scorer": FixtureSemanticScorer()}
    config_source = "".join(notebook["cells"][3]["source"])
    config_assignment = next(node for node in ast.parse(config_source).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "BENCHMARK_CONFIG" for target in node.targets))
    exec(ast.get_source_segment(config_source, config_assignment), ns)
    by_tag = {tag: cell for cell in notebook["cells"] for tag in cell.get("metadata", {}).get("tags", [])}
    for tag in ("rq2-run-setup", "rq2-generate", "rq2-generation-status", "rq2-evaluate", "rq2-aggregate",
                "rq2-metric-report", "rq2-strata-report", "rq2-item-report", "rq2-quality-plots", "rq2-cost-report"):
        exec("".join(by_tag[tag]["source"]), ns)
    assert ns["benchmark"]["summary"]["overall"]["completed"] == 3


@pytest.fixture
def rows():
    result = {}
    for split, genre in zip(runner.data.SPLITS, ("Lecture", "Conference/Talk", "Webinar/Tutorial")):
        texts = [f"{split} alpha beta gamma", "delta epsilon zeta eta", "theta iota kappa tail"]
        result[split] = [{"doi": f"10.fixture/{split}", "title": f"Title {split}",
            "author": f"Author {split}", "genre": genre, "subject": "Science",
            "abstract": f"REFERENCE_ONLY_{split} independent abstract",
            "transcript": " ".join(texts),
            "transcript_segments": {"text": texts, "start": [0, 600, 1200],
                                    "end": [600, 1200, 1800]}}]
    return result


def execute(tmp_path, backend, rows=None, **kwargs):
    return runner.run_benchmark(backend, data_path=tmp_path / "data.jsonl.gz",
        output_dir=tmp_path / "predictions", rows_by_split=rows, verify_counts=False,
        config=kwargs.pop("config", runner.BenchmarkConfig(chunk_tokens=6, map_output_tokens=4,
                                                           final_output_tokens=8)),
        semantic_scorer=kwargs.pop("semantic_scorer", None), **kwargs)


class FixtureSemanticScorer:
    metadata = {"implementation": "numeric_test_adapter_v1"}

    def __init__(self):
        self.calls = []

    def score_pair(self, arms, reference, transcript):
        self.calls.append((reference, transcript))
        return {name: {"S1": .2, "S3": .5, "S3_minus_S1": .3}
                for name in ("bertscore", "sbertscore")}


def test_new_metrics_rescore_saved_generations_and_resume_by_evaluation_identity(tmp_path, rows):
    first = execute(tmp_path, UsageBackend(), rows)
    backend, scorer = UsageBackend(), FixtureSemanticScorer()
    second = execute(tmp_path, backend, semantic_scorer=scorer)
    assert backend.calls == []
    assert len(scorer.calls) == 3
    for row in second["results"]:
        assert row["evaluation_status"] == "completed"
        assert row["semantic_scores"]["sbertscore"]["S3_minus_S1"] == .3
    assert second["summary"]["metrics"]["bertscore"]["overall"]["scored"] == 3
    assert second["summary"]["metrics"]["sbertscore"]["paired_bootstrap"]["ci95"] == pytest.approx([.3, .3])
    assert second["summary"]["resources_by_arm"] == first["summary"]["resources_by_arm"]
    scorer.calls.clear()
    third = execute(tmp_path, backend, semantic_scorer=scorer)
    assert not scorer.calls
    assert third == second
    scorer.metadata = {"implementation": "numeric_test_adapter_v2"}
    execute(tmp_path, backend, semantic_scorer=scorer)
    assert len(scorer.calls) == 3 and not backend.calls


def test_changing_bootstrap_does_not_invalidate_generation(tmp_path, rows):
    execute(tmp_path, UsageBackend(), rows)
    backend = UsageBackend()
    result = execute(tmp_path, backend, config=runner.BenchmarkConfig(
        chunk_tokens=6, map_output_tokens=4, final_output_tokens=8,
        bootstrap_samples=37, bootstrap_seed=101))
    assert not backend.calls
    assert result["summary"]["metrics"]["rouge_l"]["paired_bootstrap"]["samples"] == 37
    assert result["summary"]["metrics"]["rouge_l"]["paired_bootstrap"]["seed"] == 101


def test_generation_evaluation_aggregation_are_separate_resumable_stages(tmp_path, rows):
    from types import SimpleNamespace
    backend, scorer, events = UsageBackend(), FixtureSemanticScorer(), []
    generated = execute(tmp_path, backend, rows, phase="generate", summarize=False,
                        semantic_scorer=scorer, on_event=events.append)
    assert generated["summary"] is None
    assert not (tmp_path / "predictions/summary.json").exists()
    assert not scorer.calls
    assert all(row["status"] == "completed" for row in generated["results"])
    assert any(e["stage"] == "generation" and e.get("step") == "map" for e in events)
    scorer.on_event = lambda event: None
    original_callback = scorer.on_event
    identities = SimpleNamespace(model_id=backend.model_id, tokenizer_id=backend.tokenizer_id)
    evaluated = execute(tmp_path, identities, phase="evaluate", summarize=False,
                        semantic_scorer=scorer, on_event=events.append)
    assert scorer.on_event is original_callback
    assert evaluated["summary"] is None and len(scorer.calls) == 3
    assert all(row["evaluation_status"] == "completed" for row in evaluated["results"])
    final = runner.summarize_benchmark(evaluated, output_dir=tmp_path / "predictions")
    assert final["summary"]["metrics"]["sbertscore"]["overall"]["scored"] == 3
    assert (tmp_path / "predictions/summary.json").exists()
    assert any(e["stage"] == "evaluation" and e["status"] == "completed" for e in events)
    for event in events:
        if "id" in event:
            assert event["total"] == 3 and 1 <= event["index"] <= 3


def test_evaluation_never_generates_missing_predictions(tmp_path, rows):
    from types import SimpleNamespace
    runner.load_or_prepare_data(tmp_path / "data.jsonl.gz", rows_by_split=rows, verify_counts=False)
    identities = SimpleNamespace(model_id="fixture-model", tokenizer_id="fixture-whitespace-v1")
    with pytest.raises(FileNotFoundError, match="Generation checkpoint missing"):
        execute(tmp_path, identities, phase="evaluate", semantic_scorer=FixtureSemanticScorer())


def test_notebook_generator_reload_is_safe_after_preparation_cleanup(monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace
    notebook = json.loads((Path(__file__).resolve().parents[1] /
        "experiments/notebooks/rq2-tib-benchmark-colab.ipynb").read_text(encoding="utf-8"))
    loads = []
    torch = ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: True, empty_cache=lambda: None)
    hub = ModuleType("huggingface_hub")
    hub.snapshot_download = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)

    def load(*args, **kwargs):
        loads.append(kwargs)
        return SimpleNamespace(model_id="fixture-model", device="cuda")
    ns = {"Path": Path, "MODEL_ID": "fixture-model", "MODEL_REVISION": "pinned",
          "backend_module": SimpleNamespace(LocalHfUsageBackend=load), "bundle": {}}
    source = "".join(notebook["cells"][17]["source"])
    exec(source, ns)
    exec(source, ns)
    assert len(loads) == 2 and "bundle" not in ns


def test_metric_failure_does_not_regenerate_and_is_excluded_from_paired_estimate(tmp_path, rows):
    class FailingScorer(FixtureSemanticScorer):
        def score_pair(self, *args):
            raise RuntimeError("metric failure")
    first = execute(tmp_path, UsageBackend(), rows, semantic_scorer=FailingScorer())
    assert first["summary"]["overall"]["completed"] == 3
    assert first["summary"]["evaluation"]["failed"] == 3
    assert first["summary"]["metrics"]["bertscore"]["overall"]["scored"] == 0
    assert first["summary"]["metrics"]["bertscore"]["paired_bootstrap"]["ci95"] is None
    backend = UsageBackend()
    second = execute(tmp_path, backend, semantic_scorer=FixtureSemanticScorer())
    assert not backend.calls
    assert second["summary"]["evaluation"]["completed"] == 3
    assert all(len(row["evaluation_attempts"]) == 2 for row in second["results"])
    assert second["summary"]["evaluation"]["seconds"] >= first["summary"]["evaluation"]["seconds"]


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), "missing"])
def test_invalid_metric_output_remains_retryable_not_saved_as_a_score(tmp_path, rows, invalid):
    class InvalidScorer(FixtureSemanticScorer):
        def score_pair(self, *args):
            scores = super().score_pair(*args)
            scores["bertscore"]["S1"] = invalid
            return scores
    result = execute(tmp_path, UsageBackend(), rows, semantic_scorer=InvalidScorer())
    assert result["summary"]["evaluation"]["failed"] == 3
    assert all("semantic_scores" not in row for row in result["results"])
    assert result["summary"]["metrics"]["bertscore"]["strata"]["subject"]["Science"]["failed"] == 3


def test_cold_benchmark_automatically_acquires_processes_all_splits(tmp_path, monkeypatch, rows):
    loaded, processed = [], []
    prepare = runner.data.prepare_dataset

    def load(splits):
        loaded.append(tuple(splits))
        return rows

    def process(value, **kwargs):
        processed.append((set(value), kwargs))
        return prepare(value, **kwargs)

    monkeypatch.setattr(runner.data, "load_pinned_splits", load)
    monkeypatch.setattr(runner.data, "prepare_dataset", process)
    backend = UsageBackend()
    result = execute(tmp_path, backend)
    assert loaded == [runner.data.SPLITS]
    assert processed == [(set(runner.data.SPLITS), {"verify_counts": False})]
    assert result["summary"]["overall"]["completed"] == 3
    assert result["metadata"]["counts_by_split"] == {split: 1 for split in rows}
    assert (tmp_path / "data.jsonl.gz").is_file()
    assert backend.calls


def test_actual_pair_keeps_full_source_equal_budgets_and_no_reference_leakage(tmp_path, rows):
    backend = UsageBackend()
    result = execute(tmp_path, backend, rows)
    bundle = runner.bundles.load_benchmark_bundle(tmp_path / "data.jsonl.gz")
    call_index = 0
    for item, prediction in zip(bundle["items"], result["results"]):
        assert prediction["status"] == "completed"
        assert prediction["source_tokens"] == backend.count_tokens(item["source_text"])
        assert prediction["generation_source_sha256"] == hashlib.sha256(item["source_text"].encode()).hexdigest()
        assert set(prediction["arms"]) == {"S1", "S3"}
        arms = list(prediction["arms"].values())
        assert arms[0]["map_output_budget"] == arms[1]["map_output_budget"]
        assert arms[0]["final_output_budget"] == arms[1]["final_output_budget"] == 8
        for arm in arms:
            prompts = backend.calls[call_index:call_index + arm["chunk_count"]]
            chunks = [call[0].split("CONTENT:\n")[1].split("\nSECTION SUMMARY:")[0] for call in prompts]
            assert " ".join(chunks) == item["source_text"]
            assert [call[1] for call in prompts] == arm["map_output_caps"]
            assert sum(arm["map_output_caps"]) == arm["map_output_budget"]
            assert backend.calls[call_index + arm["chunk_count"]][1] == 8
            assert arm["prompt_tokens"] <= prediction["common_cumulative_prompt_budget"]
            call_index += arm["chunk_count"] + 1
        assert prediction["scores"] == scoring.score_pair(prediction["arms"], item["reference_text"])
    assert call_index == len(backend.calls)
    assert all("REFERENCE_ONLY" not in call[0] for call in backend.calls)
    assert all(call[2:] == (0.0, 42) for call in backend.calls)


def test_warm_cache_resumes_without_acquisition_processing_or_generation(tmp_path, rows, monkeypatch):
    first = execute(tmp_path, UsageBackend(), rows)

    def forbidden(*args, **kwargs):
        pytest.fail("warm resume invoked preprocessing or generation")

    monkeypatch.setattr(runner.data, "load_pinned_splits", forbidden)
    monkeypatch.setattr(runner.data, "prepare_dataset", forbidden)
    backend = UsageBackend()
    monkeypatch.setattr(backend, "generate", forbidden)
    second = execute(tmp_path, backend)
    assert second == first
    for item in first["results"]:
        saved = json.loads((tmp_path / "predictions" / f"{item['split']}-{item['source_index']}.json").read_text())
        assert saved == item
        assert all(len(saved[key]) == 64 for key in ("source_sha256", "reference_sha256", "run_sha256", "identity_sha256"))
        assert saved["result_sha256"] == runner._hash({k: v for k, v in saved.items() if k != "result_sha256"})


@pytest.mark.parametrize("change", ["config", "model", "tokenizer", "content"])
def test_resume_rejects_different_identity_or_modified_prediction(tmp_path, rows, change):
    execute(tmp_path, UsageBackend(), rows)
    backend, options = UsageBackend(), {}
    if change == "config":
        options["config"] = runner.BenchmarkConfig(chunk_tokens=7)
    elif change in ("model", "tokenizer"):
        setattr(backend, f"{change}_id", "different")
    else:
        path = tmp_path / "predictions/train-0.json"
        item = json.loads(path.read_text())
        item["arms"]["S1"]["summary"] = "modified"
        path.write_text(json.dumps(item))
    with pytest.raises(ValueError, match="identity/content differs"):
        execute(tmp_path, backend, **options)
    assert backend.calls == []


def test_failed_items_retained_then_retried(tmp_path, rows):
    failed = execute(tmp_path, UsageBackend(fail=True), rows)
    assert failed["summary"]["overall"] == {"selected": 3, "completed": 0, "failed": 3,
                                           "S1": None, "S3": None, "S3_minus_S1": None}
    assert failed["summary"]["paired_bootstrap"]["ci95"] is None
    for item in failed["results"]:
        assert item["error"] == "fixture generation failure"
        assert item["error_type"] == "RuntimeError"
        assert item["status"] == "failed"
    backend = UsageBackend()
    repaired = execute(tmp_path, backend)
    assert repaired["summary"]["overall"]["completed"] == 3
    assert backend.calls
    assert [item["identity_sha256"] for item in failed["results"]] == [item["identity_sha256"] for item in repaired["results"]]


@pytest.mark.parametrize("reference,hypothesis,expected", [
    ("a b c", "a c", .8), ("a b", "b a", .5), ("CAFÉ, β!", "café β", 1),
    ("", "source", 0), ("source", "", 0), ("a a b", "a b b", 2 / 3),
])
def test_rouge_l_known_lcs(reference, hypothesis, expected):
    assert scoring.rouge_l(reference, hypothesis) == pytest.approx(expected)


def test_summary_strata_failures_duration_boundaries_and_paired_ci():
    rows = [{"status": "completed", "split": "train", "genre": "Lecture", "subject": "Science",
             "duration_minutes": minutes, "scores": {"S1": .2, "S3": .5, "S3_minus_S1": .3}}
            for minutes in (None, 0, 15, 30, 60, 90)]
    rows.append({"status": "failed", "split": "test", "genre": "", "subject": "", "duration_minutes": 90})
    summary = scoring.summarize_results(rows, bootstrap_samples=100)
    assert summary["overall"]["selected"] == 7
    assert summary["overall"]["completed"] == 6
    assert summary["overall"]["failed"] == 1
    assert summary["overall"]["S3_minus_S1"] == pytest.approx(.3)
    assert summary["paired_bootstrap"]["ci95"] == pytest.approx([.3, .3])
    assert set(summary["strata"]["duration_band"]) == {"unknown", "<15", "15-30", "30-60", "60-90", ">=90"}
    assert summary["strata"]["duration_band"][">=90"]["failed"] == 1
    assert summary["strata"]["genre"]["(missing)"]["selected"] == 1
    assert summary["strata"]["subject"]["(missing)"]["failed"] == 1
    assert summary["strata"]["split"]["test"]["S1"] is None
    assert scoring.summarize_results(rows, bootstrap_samples=100) == summary
    assert scoring.summarize_results([])["paired_bootstrap"]["ci95"] is None
    with pytest.raises(ValueError, match="positive"):
        scoring.summarize_results(rows, bootstrap_samples=0)
