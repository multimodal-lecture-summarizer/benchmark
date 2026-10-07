"""Drive-backed orchestration for the separate ASR architecture benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from experiments.scripts.asr_colab_bundle import FREEZE, FROZEN_NAMES, ROOT
from experiments.scripts.asr_architecture_preflight import inspect_environment


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid.uuid4()}.partial")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with temporary.open("rb") as stream:
        os.fsync(stream.fileno())
    temporary.replace(path)


def _source_digest() -> str:
    root = ROOT
    files = [path for base in (root / "benchmarks", root / "experiments")
             for path in base.rglob("*.py")
             if not any(part in {"outputs", "datasets", "__pycache__", "scratch"}
                        for part in path.relative_to(root).parts)]
    files += [root / name for name in (
        "experiments/registry/asr_architecture_candidates.yaml",
        "experiments/registry/asr_architecture_environment.lock.yaml",
        "experiments/notebooks/asr_architecture_colab_t4.ipynb",
    )]
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _config_digest() -> str:
    registry = ROOT / "experiments/registry/asr_architecture_candidates.yaml"
    payload = {"candidate_set": "architecture", "profile": "full",
               "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(),
               "dataset_manifest_sha256": hashlib.sha256(
                   (FREEZE / "payloads/dataset.frozen_manifest.json").read_bytes()).hexdigest(),
               "notebook_id": "01c_asr_architecture_benchmark"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _first_validation_unit() -> dict:
    frozen = json.loads((FREEZE / "payloads/dataset.frozen_manifest.json").read_text(encoding="utf-8"))["records"][0]
    return next(row for row in frozen["unit_records"] if row["split"] == "validation")


def _probe_matches(payload: dict, unit_id: str, audio_sha256: str,
                   candidate_ids: list[str]) -> bool:
    outcomes = payload.get("outcomes")
    return (payload.get("unit_id") == unit_id
            and payload.get("audio_sha256") == audio_sha256
            and payload.get("dataset_manifest_sha256") == hashlib.sha256(
                (FREEZE / "payloads/dataset.frozen_manifest.json").read_bytes()).hexdigest()
            and isinstance(outcomes, list)
            and [row.get("candidate") for row in outcomes] == candidate_ids
            and all(row.get("status") == "passed" for row in outcomes))


def _seed(root: Path) -> None:
    for name in FROZEN_NAMES:
        source = FREEZE / name
        target = root / "diagnostic/full" / name
        if target.exists():
            if target.read_bytes() != source.read_bytes():
                raise RuntimeError(f"frozen input differs in existing artifact root: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".partial")
        temporary.write_bytes(source.read_bytes())
        temporary.replace(target)


def probe(drive_root: Path) -> int:
    os.environ["MPLBACKEND"] = "Agg"
    from benchmarks.scripts.run_asr_model_benchmark import _audio
    from experiments.evaluation.asr_architecture_adapters import (
        ArchitectureCandidateAdapter, registered_asr_candidates,
    )

    unit = _first_validation_unit()
    audio, _, audio_sha256 = _audio(unit)
    manifest_sha256 = hashlib.sha256(
        (FREEZE / "payloads/dataset.frozen_manifest.json").read_bytes()).hexdigest()
    outcomes = []
    for candidate in registered_asr_candidates():
        adapter = ArchitectureCandidateAdapter(candidate)
        try:
            adapter.load()
            result = adapter.transcribe(audio)
            outcomes.append({"candidate": candidate["id"], "family": candidate["family"],
                             "status": "passed", "load_seconds": adapter.load_seconds,
                             "inference_seconds": result.inference_seconds,
                             "dependency_versions": adapter.dependency_versions,
                             "gpu_memory_after_load": adapter.load_gpu_memory,
                             "gpu_memory_after_inference": getattr(result, "gpu_memory", {})})
        except Exception as exc:
            outcomes.append({"candidate": candidate["id"], "family": candidate["family"],
                             "status": "failed", "reason": f"{type(exc).__name__}: {exc}"})
        finally:
            adapter.close()
        print(outcomes[-1], flush=True)
    _atomic_json(drive_root / "architecture_probe.json", {
        "unit_id": unit["unit_id"], "audio_sha256": audio_sha256,
        "dataset_manifest_sha256": manifest_sha256, "source_sha256": _source_digest(),
        "config_sha256": _config_digest(), "outcomes": outcomes,
    })
    return 0 if all(row["status"] == "passed" for row in outcomes) else 2


def run(split: str, drive_root: Path) -> int:
    from benchmarks.scripts.run_asr_model_benchmark import _audio

    drive_root = drive_root.resolve()
    probe_path = drive_root / "architecture_probe.json"
    if not probe_path.is_file():
        raise RuntimeError("run all six real architecture probes before full work")
    probe_payload = json.loads(probe_path.read_text(encoding="utf-8"))
    unit = _first_validation_unit()
    _, _, audio_sha256 = _audio(unit)
    from experiments.evaluation.asr_architecture_adapters import registered_asr_candidates
    expected_candidate_ids = [row["id"] for row in registered_asr_candidates()]
    if (probe_payload.get("source_sha256") != _source_digest()
            or probe_payload.get("config_sha256") != _config_digest()
            or not _probe_matches(probe_payload, unit["unit_id"], audio_sha256,
                                  expected_candidate_ids)):
        raise RuntimeError("architecture probe failed or is stale for this source/config")
    validation_root = drive_root / "validation"
    root = validation_root if split == "validation" else drive_root / "native_test"
    _seed(validation_root)
    if split == "native_test":
        _seed(root)
        receipt = validation_root / "diagnostic/full/selection_receipt.json"
        saved = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
        if saved.get("status") != "complete":
            raise RuntimeError("complete architecture validation selection required before native test")
    readiness = inspect_environment(drive_root)
    if not readiness["all_candidates_ready"]:
        raise RuntimeError("architecture preflight blocked: " + json.dumps(
            [row for row in readiness["candidates"] if not row["ready"]]))
    dependency_snapshot = [{"candidate": row["candidate"],
                            "family": row["family"],
                            "status": row["status"],
                            "dependency_versions": row.get("dependency_versions", {})}
                           for row in probe_payload["outcomes"]]
    dependency_state = hashlib.sha256(json.dumps(
        dependency_snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    identity = {"source_sha256": _source_digest(), "config_sha256": _config_digest(),
                "dependency_state_sha256": dependency_state}
    identity_path = root / "diagnostic/full/asr_architecture_run_config.json"
    if identity_path.is_file():
        old = json.loads(identity_path.read_text(encoding="utf-8"))
        if any(old.get(key) != value for key, value in identity.items()):
            raise RuntimeError("architecture identity changed; use a fresh Drive run root")
        run_id = old["run_id"]
    else:
        run_id = str(uuid.uuid4())
        _atomic_json(identity_path, {**identity, "run_id": run_id})
    command = [sys.executable, "-u", "-m", "benchmarks.scripts.run_asr_model_benchmark",
               "--profile", "full", "--run-namespace", "diagnostic",
               "--evidence-status", "real", "--artifact-root", str(root),
               "--notebook-id", "01c_asr_architecture_benchmark", "--run-id", run_id,
               "--source-sha256", identity["source_sha256"], "--config-sha256", identity["config_sha256"],
               "--dependency-state-sha256", identity["dependency_state_sha256"],
               "--evaluation-mode", "selection" if split == "validation" else "final_test"]
    env = os.environ.copy()
    env["MLS_ASR_CANDIDATE_SET"] = "architecture"
    if split == "native_test":
        env["MLS_ASR_SELECTION_RECEIPT"] = str(validation_root / "diagnostic/full/selection_receipt.json")
    print(f"Starting architecture {split}; durable artifacts: {root}", flush=True)
    return subprocess.call(command, cwd=ROOT, env=env)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("split", choices=("probe", "validation", "native_test"))
    parser.add_argument("--drive-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        args.drive_root.mkdir(parents=True, exist_ok=True)
        if args.split == "probe":
            return probe(args.drive_root.resolve())
        return run(args.split, args.drive_root)
    except Exception as exc:
        print(f"[FAIL] ASR architecture orchestration: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
