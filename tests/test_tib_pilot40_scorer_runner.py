"""Pure orchestration fixtures for the Pilot40 scorer: no model assets, downloads or GPU."""
import hashlib
import json
import sys
import time as real_time
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_pilot40_scorer_runner as runner
from experiments.scripts.tib_benchmark_scorer import METRICS
from experiments.scripts.tib_scorer_colab_checkpoint import file_sha

NL = chr(10)
PROFILES = ["lead3", "lexrank", "bart", "led"]
RECORDS = {"valid:1": "long", "valid:2": "short"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def make_rows():
    rows = []
    for record, stratum in RECORDS.items():
        for profile in PROFILES:
            failed = (profile, record) == ("bart", "valid:2")
            source, reference = "Source " + record, "Reference " + record
            row = {"sample_id": f"{profile}__{record.replace(':', '-')}", "record_id": record,
                   "candidate_id": profile, "profile_id": profile, "source_stratum": stratum,
                   "origin": "fresh", "source": source, "reference": reference,
                   "source_sha256": sha(source), "reference_sha256": sha(reference),
                   "source_receipt_sha256": "a" * 64, "generation_status": "failed" if failed else "completed",
                   "scoreable": not failed}
            if failed:
                row.update(failure_reason="ValueError: Historical persisted config mismatch", warnings=[],
                           delivered_summary=None, delivered_sha256=None, views=None)
            else:
                delivered = f"Delivered one. Delivered two for {profile}."
                row.update(failure_reason=None, warnings=[], delivered_summary=delivered,
                           delivered_sha256=sha(delivered),
                           views={"S": "Delivered one.", "M": delivered, "L": delivered})
            rows.append(row)
    return rows


@pytest.fixture
def package(tmp_path, monkeypatch):
    root, assets = tmp_path / "bundle", tmp_path / "assets"
    rows = make_rows()
    root.mkdir()
    (root / "pilot_outputs.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    write(root / "frozen_scorer_spec.json", {"code_sha256": {}, "bertscore": {"model": "b", "model_revision": "r"},
                                           "source_similarity": {"model": "s", "model_revision": "q"}})
    pins = {"torch": "fixture-only"}
    write(root / "runtime_amendment.json", {
        "runtime_pins": pins, "support_package_pins": {}, "profile_ids": PROFILES,
        "expected_output_count": len(rows), "expected_scoreable_count": len(rows) - 1,
        "frozen_spec_sha256": file_sha(root / "frozen_scorer_spec.json"), "evidence_zip_sha256": "e" * 64})
    for name in ("bert", "sentence"):
        write(assets / name / "asset_manifest.json", {"fixture_only": True})

    def seal():
        write(root / "package_manifest.json", {"schema_version": 1, "files": {
            p.relative_to(root).as_posix(): file_sha(p) for p in root.rglob("*")
            if p.is_file() and p.name != "package_manifest.json"}})
    seal()
    monkeypatch.setattr(runner, "EXPECTED_ROWS", len(rows))
    monkeypatch.setattr(runner, "EXPECTED_SCOREABLE", len(rows) - 1)
    monkeypatch.setitem(sys.modules, "experiments.scripts.tib_scorer_colab_backend", SimpleNamespace(
        RuntimeSemanticScorer=None, runtime_fixtures=None, runtime_pins=lambda: pins))
    calls, view_calls, clock = [], [], SimpleNamespace(offset=0.0)

    class Sampler:
        def start(self): return self
        def finish(self): return {"fixture_only": True, **{k: 1 for k in (
            "wall_seconds", "cpu_seconds", "sampled_peak_process_rss_bytes",
            "cuda_peak_allocated_bytes", "cuda_peak_reserved_bytes", "host_memory_total_bytes")}}

    class Scorer:
        metadata = {"fixture_only": True}
        def _load(self): pass
        def _bertscore(self, *a): return 0.5
        def _sentence_vectors(self, *a, **k): return []

    def score(summary, reference, source, semantic):
        calls.append(summary)
        semantic._bertscore(summary, reference)
        semantic._sentence_vectors([summary])
        return {"metrics": {k: 0.5 for k in METRICS}, "failures": {}}

    def view(text, reference, scorer):
        view_calls.append(text)
        clock.offset += clock.jump
        return {"metrics": {k: 0.4 for k in runner.VIEW_METRICS}, "failures": {}}
    clock.jump = 0.0
    monkeypatch.setattr(runner, "time", SimpleNamespace(
        monotonic=lambda: real_time.monotonic() + clock.offset, perf_counter=real_time.perf_counter,
        process_time=real_time.process_time, time_ns=real_time.time_ns))
    options = {"backend_factory": lambda *a: Scorer(), "fixture_runner": lambda _: {"status": "pass"},
               "runtime_probe": lambda: {"google_colab_imported": True, "cuda_available": True,
                                        "T4_device_observed": True, "device_memory_bytes": 16 * 1024**3,
                                        "device_name": "Tesla T4", "packages": pins},
               "asset_validator": lambda path, **_: path, "sampler_factory": Sampler,
               "score_function": score, "view_function": view}
    return SimpleNamespace(root=root, assets=assets, output=tmp_path / "results", rows=rows,
                           options=options, calls=calls, view_calls=view_calls, clock=clock, seal=seal)


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_failed_cell_stays_in_denominator_and_is_never_scored(package):
    p = package
    result = runner.run(p.root, p.output, p.assets, **p.options)
    assert result["delivered_status"] == "HOLD" and result["orchestration_checks_passed"]
    assert result["testing_dependency_injection"] and result["qwen3_scored"] is False
    rows = read_lines(p.output / "metrics.jsonl")
    assert len(rows) == 8 and len(p.calls) == 7
    failed = next(r for r in rows if r["sample_id"] == "bart__valid-2")
    assert failed["scoring_status"] == "not_scoreable_generation_failed"
    assert all(v is None for v in failed["metrics"].values())
    assert result["failed_generation_cells"] == 1 and result["expected_scoreable"] == 7


def test_long_sources_are_scored_first(package):
    p = package
    runner.run(p.root, p.output, p.assets, **p.options)
    order = [r["source_stratum"] for r in read_lines(p.output / "metrics.jsonl") if r["scoring_status"] == "completed"]
    assert order == sorted(order, key=lambda s: runner.STRATUM_ORDER[s])


def test_component_times_recorded_and_identical_view_text_reused(package):
    p = package
    runner.run(p.root, p.output, p.assets, **p.options)
    row = next(r for r in read_lines(p.output / "metrics.jsonl") if r["scoring_status"] == "completed")
    assert {"bertscore_seconds", "source_similarity_seconds", "rouge_and_other_seconds"} <= set(row)
    assert row["sentence_vector_calls"] == 1
    views = read_lines(p.output / "view_metrics.jsonl")
    assert len(views) == 7
    # S is a new text (scored once); M and L equal the delivered text and reuse its scores.
    assert len(p.view_calls) == 7
    assert views[0]["reused_view"] == {"S": False, "M": True, "L": True}
    assert set(views[0]["views"]["S"]["metrics"]) == set(runner.VIEW_METRICS)
    costs = json.loads((p.output / "cost_evidence.json").read_text())
    assert costs["reused_identical_view_texts"] == 14 and costs["new_view_calls"] == 7
    assert "lead3|long" in costs["latency_by_profile_stratum"]


def test_deadline_before_scoring_is_hold_and_views_not_started(package):
    p = package
    result = runner.run(p.root, p.output, p.assets, wall_hours=1e-9, **p.options)
    assert result["delivered_status"] == "HOLD" and "session_deadline" in result["reasons"]
    assert result["views_status"] == "NOT_STARTED" and not p.calls
    assert all(r["scoring_status"] in ("not_attempted", "not_scoreable_generation_failed")
               for r in read_lines(p.output / "metrics.jsonl"))


def test_deadline_during_views_keeps_delivered_result(package):
    p = package
    p.clock.jump = 10_000.0
    result = runner.run(p.root, p.output, p.assets, **p.options)
    assert result["views_status"] == "PARTIAL_DEADLINE"
    assert result["orchestration_checks_passed"] and len(p.calls) == 7
    assert 0 < len(read_lines(p.output / "view_metrics.jsonl")) < 7


def test_resume_replays_without_new_calls_and_missing_view_cache_holds(package):
    p = package
    runner.run(p.root, p.output, p.assets, **p.options)
    runner.run(p.root, p.output, p.assets, resume=True, **p.options)
    assert len(p.calls) == 7 and len(p.view_calls) == 7
    next((p.output / "view_checkpoints").glob("*.json")).unlink()
    result = runner.run(p.root, p.output, p.assets, resume=True, **p.options)
    assert result["delivered_status"] == "HOLD" and not result["orchestration_checks_passed"]
    assert len(p.calls) == 7


def test_qwen3_profile_or_tampered_file_is_rejected(package):
    p = package
    amendment = json.loads((p.root / "runtime_amendment.json").read_text())
    amendment["profile_ids"] = PROFILES + ["qwen3"]
    write(p.root / "runtime_amendment.json", amendment)
    p.seal()
    with pytest.raises(ValueError, match="profile universe"):
        runner.validate_pilot_bundle(p.root)
    amendment["profile_ids"] = PROFILES
    write(p.root / "runtime_amendment.json", amendment)
    p.seal()
    runner.validate_pilot_bundle(p.root)
    (p.root / "pilot_outputs.jsonl").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        runner.validate_pilot_bundle(p.root)
    result = runner.run(p.root, p.output, p.assets, **p.options)
    assert result["delivered_status"] == "HOLD" and not p.calls


def test_scoreable_flag_must_match_generation_status(package):
    p = package
    rows = [dict(r) for r in p.rows]
    rows[0]["scoreable"] = False
    (p.root / "pilot_outputs.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    p.seal()
    with pytest.raises(ValueError, match="Scoreable flag"):
        runner.validate_pilot_bundle(p.root)


def test_empty_view_text_is_rejected_and_never_imputed(package):
    p = package
    rows = [dict(r) for r in p.rows]
    rows[0]["views"] = {**rows[0]["views"], "S": "  "}
    (p.root / "pilot_outputs.jsonl").write_text(NL.join(json.dumps(r) for r in rows), encoding="utf-8")
    p.seal()
    with pytest.raises(ValueError, match="non-empty"):
        runner.validate_pilot_bundle(p.root)
    with pytest.raises(ValueError, match="empty_or_invalid_view"):
        runner.score_view("", "reference", None)


def test_component_totals_split_between_passes(package):
    p = package
    runner.run(p.root, p.output, p.assets, **p.options)
    costs = json.loads((p.output / "cost_evidence.json").read_text())
    assert costs["component_after_pass1"]["calls"]["bertscore"] == 7
