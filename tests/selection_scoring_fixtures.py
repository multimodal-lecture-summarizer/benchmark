"""Synthetic full-size (300 IDs x 4 profiles) selection300 evidence for scoring tests; no real data.

Fixture IDs start with `fixture:` so they can never collide with the sealed cohort.
"""
import gzip
import hashlib
import json
import os
import random
import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace

from experiments.scripts import tib_selection300_scorer_bundle as bundle
from experiments.scripts.tib_stage_session import digest

PROFILES = ("lead3", "lexrank", "bart", "led")
RAW = ("Alpha beta gamma delta. " * 20 + "Second sentence here. " * 20).strip()
FAILED_LED = ("fixture:005", "fixture:100", "fixture:250")
BINDING_COPIED = ("scorer_freeze_receipt.json", "admission_rules_v2.json", "decisions_261023_v1.json")


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def jsonl(rows):
    return "".join(json.dumps(r) + "\n" for r in rows)


def make_ids():
    ids = [f"fixture:{i:03d}" for i in range(1, 301)]
    strata = ["long"] * 110 + ["medium"] * 90 + ["short"] * 100
    random.Random(7).shuffle(strata)
    return ids, dict(zip(ids, strata))


def make_record(record_id, stratum, profile, profile_sha, status="completed", delivered=RAW):
    base = {"origin": "fresh", "record_id": record_id, "source_stratum": stratum, "retain_in_denominator": True,
            "source_sha256": sha("source " + record_id), "status": status, "binding": {"profile_sha256": profile_sha}}
    if status == "failed":
        return {**base, "error": "AdapterFailure: reduction does not reduce note count and native tokens"}
    return {**base, "result": {"raw_final": RAW, "delivered_final": delivered,
                               "delivery": {"delivered_sha256": sha(delivered)}},
            "validation": {"acceptance": {"warnings": ["sentence_ending"] if status == "completed_with_warning" else []}}}


def make_world(tmp_path):
    """Write evidence ZIP, qualification folder, cohort, binding and generation registry under tmp_path."""
    root = Path(tmp_path) / "world"
    ids, strata = make_ids()
    qualification, binding, registry = root / "qual", root / "binding", root / "generation-registry"
    (qualification / "qualified_cohort").mkdir(parents=True)
    (qualification / "eda").mkdir()
    binding.mkdir()
    registry.mkdir()
    (qualification / "source_use_ledger.jsonl").write_text(jsonl(
        [{"record_id": i, "allowed_for_current_local_use": True, "allowed_for_reference_scoring": True} for i in ids]))
    (qualification / "qualified_cohort/qualification_ledger.jsonl").write_text(jsonl(
        [{"record_id": i, "role_eligible": True, "source_normalized_sha256": sha("source " + i),
          "reference_normalized_sha256": sha("reference " + i)} for i in ids]))
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(jsonl([{"record_id": i, "source_normalized": "source " + i,
                             "reference_normalized": "reference " + i} for i in ids]))
    cohort = root / "development_cohort.json"
    cohort.write_text(json.dumps({"selected_ids": {"pilot": ["fixture:pilot-1"], "selection": ids}}))
    profile_shas = {p: sha("profile " + p) for p in PROFILES}
    profile_list = binding / "selection300_profiles_v2.json"
    profile_list.write_text(json.dumps({"profiles": [{"candidate_id": p, "profile_sha256": profile_shas[p]} for p in PROFILES]}))
    for name in BINDING_COPIED:
        shutil.copyfile(bundle.BINDING / name, binding / name)
    allocation = json.loads((bundle.BINDING / "compute_budget_selection300.json").read_text(encoding="utf-8"))
    manifest_bytes = b'{"schema_version": 1, "files": {}}'
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    ledger = {"bundle_sha256": manifest_sha, "allocation_sha256": digest(allocation), "allocation": allocation}
    (registry / "preparation_receipt.json").write_text(json.dumps({"manifest_sha256": manifest_sha}))
    (registry / "selection300_generation_outcome.json").write_text(json.dumps({"audit_pass": True}))
    archive = root / "evidence.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("package/selection_contract.json", json.dumps({"selection_ids": ids, "source_strata": strata}))
        z.writestr("package/selection_sources.jsonl", jsonl(
            [{"record_id": i, "source_normalized_sha256": sha("source " + i), "source_stratum": strata[i]} for i in ids]))
        z.writestr("package/selection_manifest.json", manifest_bytes)
        z.writestr("package/selection_allocation.json", json.dumps(allocation))
        z.writestr("selection/resource_ledger.json", json.dumps(ledger))
        for profile in PROFILES:
            records = {}
            for i in ids:
                status = "failed" if (profile == "led" and i in FAILED_LED) else (
                    "completed_with_warning" if profile in ("bart", "led") else "completed")
                records[i] = make_record(i, strata[i], profile, profile_shas[profile], status)
            z.writestr(f"selection/{profile}/candidate_receipt.json", json.dumps({
                "candidate_id": profile, "status": "COMPLETED_WITH_FAILURES" if profile == "led" else "PASS",
                "records": records}))
            z.writestr(f"selection/{profile}/run_identity.json", json.dumps({"payload": {"profile_sha256": profile_shas[profile]}}))
    return SimpleNamespace(root=root, ids=ids, strata=strata, qualification=qualification, binding=binding,
                           registry=registry, cohort=cohort, archive=archive, profile_list=profile_list,
                           manifest_sha=manifest_sha, allocation=allocation, profile_shas=profile_shas,
                           archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest())


def build_bundle(world, tmp_path):
    """Run the real builder on the synthetic world; returns (receipt, local, registry)."""
    local, registry = Path(tmp_path) / "local", Path(tmp_path) / "registry"
    receipt = bundle.build(local=local, registry=registry, evidence_zip=world.archive,
                           expected_evidence_sha=world.archive_sha, qualification=world.qualification,
                           cohort_path=world.cohort, binding=world.binding, generation_registry=world.registry)
    return receipt, local, registry


SESSION_SECONDS = (489.2502023039999, 151.27375117599996)   # the two real, closed generation-stage sessions
CLOSED_AS = "preflight_failed_before_any_model"
BASE_SECONDS = {"long": 6.68, "medium": 3.35, "short": 2.09}   # Pilot40 measured mean seconds per output


def observation(boot, monotonic, epoch_ns=1_792_766_000_000_000_000):
    return {"boot_id": boot, "monotonic": monotonic, "epoch_ns": epoch_ns + int(monotonic * 1e9), "logical_cpu_count": 2}


def make_ledger(world, path, closed_sessions=2, third_open=False):
    """A shared stage ledger in the real situation: sessions 1 and 2 closed, optionally session 3 open."""
    from experiments.scripts.tib_stage_session import begin_session, finish_session
    path = Path(path)
    start = 187.0
    for index in range(closed_sessions):
        boot = f"boot-{index + 1}"
        begin_session(path, world.allocation, world.manifest_sha, observation=observation(boot, start),
                      local_working_root="/content/TIB_SELECTION300_261023_V1")
        finish_session(path, CLOSED_AS, observation=observation(boot, start + SESSION_SECONDS[index % 2]))
        start += 1000.0
    if third_open:
        begin_session(path, world.allocation, world.manifest_sha, observation=observation("boot-3", 100.0),
                      local_working_root="/content/TIB_SELECTION300_261023_V1")
    return path


def install_fakes(monkeypatch, runner, world, scale=1.0):
    """Dependency-injected runner environment with a fake clock; returns the hooks and recorders.

    Every scored output advances the clock by `scale` x the Pilot40 mean seconds of its stratum; each view call
    costs 0.04x of that (Pilot40 views, checkpoints and profiling added about 10% in total).
    """
    from types import SimpleNamespace
    import sys
    import time as real_time
    from experiments.scripts.tib_benchmark_scorer import METRICS
    from experiments.scripts.tib_scorer_colab_bundle import PINS, SUPPORT
    clock = SimpleNamespace(offset=0.0)
    calls, view_calls = [], []
    monkeypatch.setattr(os, "fsync", lambda fd: None)   # ~2,400 checkpoint writes per run; durability is not under test
    monkeypatch.setitem(sys.modules, "experiments.scripts.tib_scorer_colab_backend", SimpleNamespace(
        RuntimeSemanticScorer=None, runtime_fixtures=None, runtime_pins=lambda: PINS))
    monkeypatch.setattr(runner, "time", SimpleNamespace(
        monotonic=lambda: real_time.monotonic() + clock.offset, perf_counter=real_time.perf_counter,
        process_time=real_time.process_time, time_ns=real_time.time_ns))

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

    def stratum_of(reference):
        return world.strata[reference.split(" ", 1)[1]]

    def score(summary, reference, source, semantic):
        calls.append((summary, reference))
        clock.offset += scale * BASE_SECONDS[stratum_of(reference)]
        semantic._bertscore(summary, reference)
        semantic._sentence_vectors([summary])
        return {"metrics": {k: 0.5 for k in METRICS}, "failures": {}}

    def view(text, reference, scorer):
        view_calls.append((text, reference))
        clock.offset += 0.04 * scale * BASE_SECONDS[stratum_of(reference)]
        return {"metrics": {k: 0.4 for k in runner.VIEW_METRICS}, "failures": {}}

    options = {"backend_factory": lambda *a: Scorer(), "fixture_runner": lambda _: {"status": "pass"},
               "runtime_probe": lambda: {"google_colab_imported": True, "cuda_available": True,
                                        "T4_device_observed": True, "device_memory_bytes": 16 * 1024**3,
                                        "device_name": "Tesla T4", "packages": {**PINS, **SUPPORT}},
               "asset_validator": lambda path, **_: path, "sampler_factory": Sampler,
               "score_function": score, "view_function": view}
    return SimpleNamespace(options=options, calls=calls, view_calls=view_calls, clock=clock)


def make_assets(root):
    for name in ("bert", "sentence"):
        (Path(root) / name).mkdir(parents=True, exist_ok=True)
        (Path(root) / name / "asset_manifest.json").write_text(json.dumps({"fixture_only": True}))
    return Path(root)


def reseal(root):
    """Rewrite package_manifest.json after a test edited a bundle file."""
    root = Path(root)
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(root.rglob("*")) if p.is_file() and p.name != "package_manifest.json"
             and "__pycache__" not in p.parts}
    (root / "package_manifest.json").write_text(json.dumps({"schema_version": 1, "files": files}))
