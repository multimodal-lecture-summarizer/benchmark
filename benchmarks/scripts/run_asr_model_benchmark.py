"""Resumable A0-A5 ASR benchmark runner for the executor-controlled 01a notebook."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

import numpy as np

if os.environ.get("MLS_ASR_CANDIDATE_SET") == "architecture":
    from experiments.evaluation.asr_architecture_adapters import (
        ArchitectureCandidateAdapter as CandidateAdapter,
        registered_asr_candidates,
    )
    _ARCHITECTURE_SET = True
else:
    from experiments.evaluation.asr_candidate_adapters import CandidateAdapter, registered_asr_candidates
    _ARCHITECTURE_SET = False
from experiments.evaluation.asr_selection_scoring import (
    score_asr_pairs, selection_metadata, validation_units,
)
from experiments.scripts.benchmark_artifacts import parse_context, write_json_artifact, write_run_manifest
from experiments.scripts.stage_benchmark_helpers import load_eligible_units, require_media

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ("experiments/registry/asr_architecture_candidates.yaml"
                   if _ARCHITECTURE_SET else "experiments/registry/candidates.yaml")
CHECKPOINT_VERSION = 2
ADAPTER_FACTORY = CandidateAdapter


def _audio(unit: dict[str, Any], *, verify_cache: bool = True) -> tuple[np.ndarray, float, str]:
    """Read verified frozen media or a row locator; return canonical mono 16 kHz audio."""
    if unit.get("canonical_audio_path"):
        raw_path = Path(str(unit["canonical_audio_path"]))
        path = (raw_path if raw_path.is_absolute() else ROOT / raw_path).resolve()
        if not raw_path.is_absolute():
            path.relative_to(ROOT.resolve())
        mono = np.load(path, mmap_mode="r", allow_pickle=False)
        if mono.dtype != np.dtype("float32") or mono.ndim != 1 or not mono.size:
            raise RuntimeError("canonical_audio_cache_invalid")
        digest = str(unit.get("decoded_audio_sha256") or "")
        if verify_cache:
            actual = hashlib.sha256(np.asarray(mono, dtype="<f4").tobytes()).hexdigest()
            if actual != digest:
                raise RuntimeError("canonical_audio_cache_hash_mismatch")
        return mono, len(mono) / 16000.0, digest
    if unit.get("arrow_path"):
        from experiments.scripts.asr_full_corpus import decode_selected

        repo_path = ROOT / str(unit["arrow_path"])
        data_root = ROOT if repo_path.is_file() else ROOT / "experiments/datasets/tedlium3"
        evidence, mono = decode_selected(data_root, {**unit, "asr_eligible": True})
        digest = evidence["canonical_audio_sha256"]
        if unit.get("decoded_audio_sha256") and digest != unit["decoded_audio_sha256"]:
            raise RuntimeError("decoded_audio_hash_mismatch")
        return mono, len(mono) / 16000.0, digest
    else:
        import soundfile as sf

        path = next((Path(str(unit[key])) for key in ("media_path", "audio_path", "path")
                     if unit.get(key) and Path(str(unit[key])).is_file()), None)
        if path is None:
            raise RuntimeError("media_missing")
        samples, rate = sf.read(path, dtype="float32", always_2d=True)
    if samples.size == 0 or rate <= 0:
        raise RuntimeError("invalid_audio")
    mono = np.mean(samples, axis=1, dtype=np.float32)
    if rate != 16000:
        from scipy.signal import resample_poly
        from math import gcd
        factor = gcd(int(rate), 16000)
        mono = resample_poly(mono, 16000 // factor, int(rate) // factor).astype(np.float32)
    if not np.isfinite(mono).all():
        raise RuntimeError("non_finite_audio")
    payload = mono.astype("<f4", copy=False).tobytes()
    digest = hashlib.sha256(payload).hexdigest()
    expected = unit.get("decoded_audio_sha256")
    if expected and expected != digest:
        raise RuntimeError("decoded_audio_hash_mismatch")
    return mono, len(mono) / 16000.0, digest


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _frozen_cohort(context) -> tuple[dict[str, Any], str]:
    from experiments.scripts.benchmark_artifacts import read_json_artifact

    payload = read_json_artifact(context, "dataset.frozen_manifest")
    if len(payload.get("records", [])) != 1:
        raise RuntimeError("expected exactly one frozen TED-LIUM manifest")
    manifest = payload["records"][0]
    path = context.namespace_root / "payloads/dataset.frozen_manifest.json"
    return manifest, _sha(path)


def _unit_ids_sha256(units: list[dict[str, Any]]) -> str:
    values = sorted(str(unit["unit_id"]) for unit in units)
    return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()


def _rank_validation_candidates(complete_metrics: dict[str, dict[str, float]],
                                selection: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank complete validation candidates and select the lowest micro-WER."""
    ordered = sorted(complete_metrics, key=lambda key: (complete_metrics[key]["wer"], key))
    shortlist = [{"candidate": key, "selected": rank == 1, "rank": rank,
                  "metrics": complete_metrics[key], **selection}
                 for rank, key in enumerate(ordered, 1)]
    if sum(row["selected"] is True for row in shortlist) != 1:
        raise RuntimeError("complete validation requires exactly one selected candidate")
    return shortlist


def _verify_frozen_units(units: list[dict[str, Any]], manifest: dict[str, Any], split: str,
                        *, allow_subset: bool = False) -> None:
    expected_units = [row for row in manifest.get("unit_records", []) if row.get("split") == split]
    expected_ids = sorted(str(row.get("unit_id")) for row in expected_units)
    actual_ids = sorted(str(row.get("unit_id")) for row in units)
    valid = (len(actual_ids) == len(set(actual_ids)) and
             (set(actual_ids).issubset(expected_ids) if allow_subset else actual_ids == expected_ids))
    if not expected_ids or not actual_ids or not valid:
        raise RuntimeError(f"{split} loader cohort differs from frozen manifest")
    if not allow_subset and manifest.get("dataset_id") == "tedlium3" and len(expected_ids) != {
            "validation": 507, "final_test": 1155}[split]:
        raise RuntimeError(f"frozen manifest has unexpected {split} cohort size: {len(expected_ids)}")


def _checkpoint_path(context, split: str) -> Path:
    return context.namespace_root / "checkpoints" / split


def _read_checkpoints(path: Path, identity: str) -> dict[str, dict[str, Any]]:
    if not path.is_dir():
        return {}
    records = {}
    for entry in sorted(path.glob("*.json")):
        row = json.loads(entry.read_text(encoding="utf-8"))
        if row.get("identity") != identity:
            raise RuntimeError(f"stale ASR checkpoint {entry.name}; identity changed")
        key = f"{row['candidate']}::{row['unit_id']}"
        # Re-evaluate blocked rows on resume: preflight/environment may have changed.
        # Only successful inference is reusable as a completed checkpoint.
        if row.get("status") == "completed":
            records[key] = row
    return records


def _append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{row['candidate']}\0{row['unit_id']}".encode()).hexdigest()
    target = path / f"{key}.json"
    temporary = target.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(target)


def _hardware_identity() -> dict[str, Any]:
    result = {"platform": platform.platform(), "machine": platform.machine(),
              "processor": platform.processor()}
    try:
        import torch
        result["torch"] = torch.__version__
        result["cuda_runtime"] = torch.version.cuda
        result["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            result.update(gpu=props.name, gpu_total_memory=props.total_memory,
                          gpu_capability=f"{props.major}.{props.minor}")
    except Exception as exc:
        result["torch_error"] = type(exc).__name__
    return result


def _identity(context, units: list[dict[str, Any]], candidates: list[dict[str, Any]], split: str) -> str:
    hardware = _hardware_identity()
    # Colab can resume on another host/kernel. Keep the model execution ABI in
    # the checkpoint key and record each host on its completed rows below.
    stable_hardware = {key: hardware.get(key) for key in (
        "machine", "torch", "cuda_runtime", "cuda_available", "gpu",
        "gpu_total_memory", "gpu_capability")}
    payload = {"version": CHECKPOINT_VERSION, "split": split,
               "source_sha256": context.source_sha256, "config_sha256": context.config_sha256,
               "dependency_state_sha256": context.dependency_state_sha256,
               "units": [(u["unit_id"], u.get("reference_text"), u.get("decoded_audio_sha256"),
                           u.get("arrow_sha256")) for u in units],
               "candidates": [(c["id"], c.get("model_kwargs")) for c in candidates],
               "hardware": stable_hardware}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _per_talk(rows: list[dict[str, Any]], units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    talk_by_unit = {unit["unit_id"]: unit.get("talk_id") or unit["unit_id"] for unit in units}
    grouped: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        grouped.setdefault(str(talk_by_unit[row["unit_id"]]), []).append(
            (row["reference"], row["hypothesis"]))
    return [{"talk_id": talk_id, "unit_count": len(pairs),
             "edit_counts": score_asr_pairs(pairs)}
            for talk_id, pairs in sorted(grouped.items())]


def _write_parent_index(context, selection_receipt: Path, selection: dict,
                        checkpoint_identity: str, status: str) -> Path:
    """Bind separate validation and native-test roots without changing selection evidence."""
    validation_root = selection_receipt.resolve().parents[2]
    validation_context = replace(context, artifact_root=validation_root,
                                 evaluation_mode="selection")
    shortlist_path = validation_context.namespace_root / "payloads/asr.shortlist.json"
    validation_manifest = validation_context.namespace_root / "runs" / f"{context.notebook_id}.run.json"
    test_manifest = context.namespace_root / "runs" / f"{context.notebook_id}.run.json"
    payload = {
        "schema_version": 1,
        "status": status,
        "validation": {
            "artifact_root": str(validation_root),
            "run_id": selection["run_id"],
            "selection_receipt_sha256": selection["receipt_sha256"],
            "shortlist_sha256": _sha(shortlist_path),
            "run_manifest_sha256": _sha(validation_manifest),
        },
        "native_test": {
            "artifact_root": str(context.artifact_root.resolve()),
            "run_id": context.run_id,
            "evaluation_mode": "final_test",
            "checkpoint_identity": checkpoint_identity,
            "run_manifest_sha256": _sha(test_manifest),
            "artifact_receipts": {
                artifact: _sha(context.namespace_root / f"{artifact}.receipt.json")
                for artifact in ("asr.raw_predictions", "asr.per_unit_metrics",
                                 "asr.aggregate", "asr.shortlist", "asr.failure_ledger")
            },
        },
    }
    index_path = context.namespace_root / "parent_index.json"
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if index_path.exists():
        previous = json.loads(index_path.read_text(encoding="utf-8"))
        if previous.get("status") == "complete":
            raise RuntimeError("completed ASR parent index is immutable; use a fresh test artifact root")
    temporary = index_path.with_suffix(f".{context.run_id}.tmp")
    temporary.write_text(serialized, encoding="utf-8")
    temporary.replace(index_path)
    return index_path


def main(argv: Sequence[str] | None = None) -> int:
    context = None
    try:
        expected_notebook_id = ("01c_asr_architecture_benchmark" if _ARCHITECTURE_SET
                                else "01a_asr_model_benchmark")
        context = parse_context(__doc__ or "", expected_notebook_id, argv)
        if context.run_namespace != "diagnostic":
            raise RuntimeError("A0-A5 run is diagnostic because TED-LIUM test references were previously exposed")
        evaluation_mode = context.evaluation_mode or os.environ.get("MLS_ASR_EVALUATION_MODE", "selection")
        if evaluation_mode not in {"selection", "final_test"}:
            raise RuntimeError("ASR evaluation mode must be selection or final_test")
        split = "validation" if evaluation_mode == "selection" else "final_test"
        if context.profile == "smoke" and split != "validation":
            raise RuntimeError("ASR smoke is validation-only and cannot create a test subrun")
        context = replace(context, evaluation_mode=evaluation_mode)
        try:
            units = load_eligible_units(context, limit_smoke=False, allowed_splits={split})
        except TypeError as exc:
            # Narrow compatibility for injected test loaders predating split allowlists.
            if "allowed_splits" not in str(exc):
                raise
            units = load_eligible_units(context, limit_smoke=False)
        if split == "validation":
            units = validation_units(units)
        else:
            invalid = [unit.get("unit_id") for unit in units
                       if unit.get("split") not in {"validation", "final_test", "train"}]
            if invalid:
                raise RuntimeError(f"ASR units have invalid split values: {invalid[:5]}")
            units = [unit for unit in units if unit.get("split") == "final_test"]
        if context.profile == "smoke":
            units = units[:1]
        if not units:
            raise RuntimeError(f"no eligible {split} units")
        frozen_manifest, frozen_manifest_sha256 = _frozen_cohort(context)
        _verify_frozen_units(units, frozen_manifest, split,
                             allow_subset=context.profile == "smoke")
        for unit in units:
            if unit.get("canonical_audio_path"):
                _audio(unit, verify_cache=True)
        if split == "validation":
            selection = selection_metadata(units)
            if len(validation_units(units)) != len(units):
                raise RuntimeError("selection cohort contains non-validation units")
            if (context.profile != "smoke" and frozen_manifest.get("dataset_id") == "tedlium3"
                    and len(units) != 507):
                raise RuntimeError("full validation selection requires all 507 frozen units")
            stale_receipt = context.artifact_root / "diagnostic" / context.profile / "selection_receipt.json"
            if stale_receipt.exists():
                prior_receipt = json.loads(stale_receipt.read_text(encoding="utf-8"))
                if prior_receipt.get("status") == "complete":
                    raise RuntimeError("completed validation selection receipt is immutable; use a fresh artifact root")
                if prior_receipt.get("status") != "partial":
                    raise RuntimeError("existing validation selection receipt has an unknown status")
        else:
            selection = {}
            selection_receipt = Path(os.environ.get("MLS_ASR_SELECTION_RECEIPT") or (
                context.artifact_root / "diagnostic" / context.profile / "selection_receipt.json"))
            if selection_receipt.resolve().parents[2] == context.artifact_root.resolve():
                raise RuntimeError("final_test output must use an artifact root separate from validation")
            if not selection_receipt.is_file():
                raise RuntimeError("final_test requires immutable validation selection_receipt.json")
            frozen_selection = json.loads(selection_receipt.read_text(encoding="utf-8"))
            if frozen_selection.get("status") != "complete" or not frozen_selection.get("receipt_sha256"):
                raise RuntimeError("validation selection receipt is incomplete or malformed")
            if frozen_selection.get("candidate_count") != 6 or frozen_selection.get("unit_count") != 507:
                raise RuntimeError("validation selection receipt has unexpected candidate/unit counts")
            if frozen_selection.get("dataset_manifest_sha256") != frozen_manifest_sha256:
                raise RuntimeError("final-test frozen dataset manifest differs from validation")
            if frozen_selection.get("test_unit_ids_sha256") != _unit_ids_sha256(
                    [row for row in frozen_manifest["unit_records"] if row.get("split") == "final_test"]):
                raise RuntimeError("final-test cohort identity differs from validation receipt")
            for key in ("source_sha256", "config_sha256", "dependency_state_sha256"):
                if frozen_selection.get(key) != getattr(context, key):
                    raise RuntimeError(f"final-test {key} differs from the validation run")
            signed_body = {key: value for key, value in frozen_selection.items() if key != "receipt_sha256"}
            actual_receipt_hash = hashlib.sha256(json.dumps(signed_body, sort_keys=True).encode()).hexdigest()
            if actual_receipt_hash != frozen_selection["receipt_sha256"]:
                raise RuntimeError("validation selection receipt hash mismatch")
            existing_parent_index = context.namespace_root / "parent_index.json"
            if existing_parent_index.is_file():
                previous_index = json.loads(existing_parent_index.read_text(encoding="utf-8"))
                if previous_index.get("status") == "complete":
                    raise RuntimeError("completed ASR parent index is immutable; use a fresh test artifact root")
            validation_root = selection_receipt.resolve().parents[2]
            validation_context = replace(context, artifact_root=validation_root, evaluation_mode="selection")
            from experiments.scripts.benchmark_artifacts import read_json_artifact
            validation_shortlist = read_json_artifact(validation_context, "asr.shortlist")["records"]
            validation_shortlist_path = validation_context.namespace_root / "payloads/asr.shortlist.json"
            if _sha(validation_shortlist_path) != frozen_selection.get("shortlist_sha256"):
                raise RuntimeError("validation shortlist no longer matches the frozen selection receipt")
            if len(validation_shortlist) != 6 or sum(row.get("selected") is True for row in validation_shortlist) != 1:
                raise RuntimeError("validation shortlist is not a complete six-candidate selection")
            candidate_ids = [candidate["id"] for candidate in registered_asr_candidates(REGISTRY)]
            if frozen_selection.get("candidate_ids") != candidate_ids:
                raise RuntimeError("validation receipt candidate IDs do not match the current frozen A0-A5 registry")
            if any(row.get("selection_unit_ids_sha256") != frozen_selection.get("selection_unit_ids_sha256")
                   for row in validation_shortlist):
                raise RuntimeError("validation shortlist cohort identity disagrees with its receipt")
            from experiments.scripts.benchmark_artifacts import validated_payload_path
            _, validation_artifact_receipt = validated_payload_path(validation_context, "asr.shortlist")
            for key in ("run_id", "source_sha256", "config_sha256"):
                if validation_artifact_receipt.get(key) != frozen_selection.get(key):
                    raise RuntimeError(f"selection receipt {key} does not match validation evidence")
            selection = {"validation_selection_receipt_sha256": frozen_selection["receipt_sha256"]}
        candidates = registered_asr_candidates(REGISTRY)
        identity = _identity(context, units, candidates, split)
        checkpoint_path = _checkpoint_path(context, split)
        completed = _read_checkpoints(checkpoint_path, identity)
        expected_keys = {f"{candidate['id']}::{unit['unit_id']}" for candidate in candidates for unit in units}
        if not set(completed).issubset(expected_keys):
            raise RuntimeError("checkpoint contains rows outside this candidate/unit matrix")
        results = dict(completed)
        adapters: dict[str, CandidateAdapter] = {}
        preflight_failures: dict[str, str] = {}
        if ADAPTER_FACTORY is CandidateAdapter:
            if _ARCHITECTURE_SET:
                from experiments.scripts.asr_architecture_preflight import inspect_environment
            else:
                from experiments.scripts.asr_benchmark_preflight import inspect_environment

            preflight = inspect_environment()
            by_id = {row["candidate"]: row for row in preflight["candidates"]}
            for candidate in candidates:
                readiness = by_id[candidate["id"]]
                if not readiness.get("ready", False):
                    causes = []
                    if readiness["missing_dependencies"]:
                        causes.append("missing_dependencies=" + ",".join(readiness["missing_dependencies"]))
                    for mismatch in readiness.get("package_version_mismatches", []):
                        causes.append(f"package_version_mismatch={mismatch['package']}:{mismatch['installed']}!={mismatch['locked']}")
                    if not readiness["model"]["cached"]:
                        causes.append("pinned_model_snapshot_not_cached")
                    causes.extend(readiness.get("resource_blockers", []))
                    if not causes:
                        causes.append("candidate_requirements_not_met")
                    preflight_failures[candidate["id"]] = "blocked_preflight: " + "; ".join(causes)
        try:
            for candidate in candidates:
                adapter = ADAPTER_FACTORY(candidate)
                adapters[candidate["id"]] = adapter
                resumed_count = sum(
                    f"{candidate['id']}::{unit['unit_id']}" in completed for unit in units)
                print(f"[ASR] {split} {candidate['id']}: "
                      f"{resumed_count}/{len(units)} resumed", flush=True)
                if candidate["id"] in preflight_failures:
                    for unit in units:
                        key = f"{candidate['id']}::{unit['unit_id']}"
                        if key not in results:
                            row = {"identity": identity, "candidate": candidate["id"],
                                   "unit_id": unit["unit_id"], "status": "blocked",
                                   "reason": preflight_failures[candidate["id"]], "hypothesis": None,
                                   "reference": str(unit.get("reference_text") or ""), "split": split}
                            _append_checkpoint(checkpoint_path, row)
                            results[key] = row
                    continue
                try:
                    adapter.load()
                except Exception as exc:
                    adapter_error = f"{type(exc).__name__}: {exc}"
                    for unit in units:
                        key = f"{candidate['id']}::{unit['unit_id']}"
                        if key not in results:
                            row = {"identity": identity, "candidate": candidate["id"],
                                   "unit_id": unit["unit_id"], "status": "blocked",
                                   "reason": adapter_error, "hypothesis": None,
                                   "reference": str(unit.get("reference_text") or ""),
                                   "split": split}
                            _append_checkpoint(checkpoint_path, row)
                            results[key] = row
                    adapter.close()
                    continue
                for unit_index, unit in enumerate(units, 1):
                    key = f"{candidate['id']}::{unit['unit_id']}"
                    if key in results:
                        continue
                    row = {"identity": identity, "candidate": candidate["id"],
                           "unit_id": unit["unit_id"], "split": split,
                           "reference": str(unit.get("reference_text") or ""),
                           "status": "failed", "reason": "not_started", "hypothesis": None}
                    try:
                        audio, duration, audio_hash = _audio(unit, verify_cache=False)
                        if not row["reference"].strip():
                            raise RuntimeError("reference_missing")
                        result = adapter.transcribe(audio)
                        row.update(status="completed", reason=None, hypothesis=result.text,
                                   duration_seconds=duration, decoded_audio_sha256=audio_hash,
                                   inference_seconds=result.inference_seconds,
                                   preprocessing_seconds=result.preprocessing_seconds,
                                   alignment_seconds=result.alignment_seconds,
                                   model_id=candidate["id"], model_size=adapter.model_size,
                                   model_revision=getattr(adapter, "model_revision", None),
                                   device=adapter.device, load_seconds=adapter.load_seconds,
                                   dependency_versions=adapter.dependency_versions,
                                   hardware_identity=_hardware_identity())
                        score = score_asr_pairs([(row["reference"], result.text)])
                        row["metrics"] = score
                    except Exception as exc:
                        row["reason"] = f"{type(exc).__name__}: {exc}"
                    _append_checkpoint(checkpoint_path, row)
                    results[key] = row
                    if unit_index % 25 == 0 or unit_index == len(units):
                        print(f"[ASR] {split} {candidate['id']}: {unit_index}/{len(units)} visited",
                              flush=True)
                adapter.close()
        finally:
            for adapter in adapters.values():
                adapter.close()

        predictions, per_unit = [], []
        aggregate, complete_metrics, all_complete = [], {}, True
        for candidate in candidates:
            rows = [results[f"{candidate['id']}::{unit['unit_id']}"] for unit in units]
            good = [row for row in rows if row["status"] == "completed"]
            is_complete = len(good) == len(units)
            all_complete &= is_complete
            for row in rows:
                predictions.append({"unit_id": row["unit_id"], "split": split,
                                    "dataset_id": next((u.get("dataset_id") for u in units if u["unit_id"] == row["unit_id"]), None),
                                    "talk_id": next((u.get("talk_id") for u in units if u["unit_id"] == row["unit_id"]), None),
                                    "candidate": candidate["id"], **selection, "status": row["status"],
                                    "reason": row.get("reason"), "predictions": {
                                        "hypothesis": row.get("hypothesis"), "reference": row.get("reference"),
                                        "decoded_audio_sha256": row.get("decoded_audio_sha256")},
                                    "timing": {key: row.get(key) for key in (
                                        "load_seconds", "inference_seconds", "preprocessing_seconds",
                                        "alignment_seconds", "duration_seconds")},
                                    "device": row.get("device"), "model_size": row.get("model_size"),
                                    "model_revision": row.get("model_revision"),
                                    "dependency_versions": row.get("dependency_versions"),
                                    "model_loaded": bool(row.get("model_id")), "execution_mode": "real"})
                if row["status"] == "completed":
                    per_unit.append({"unit_id": row["unit_id"], "split": split,
                                     "talk_id": next((u.get("talk_id") for u in units if u["unit_id"] == row["unit_id"]), None),
                                     "candidate": candidate["id"], **selection, "metrics": {
                                         "wer": row["metrics"]["wer"], "cer": row["metrics"]["cer"],
                                         "rtf": row["inference_seconds"] / row["duration_seconds"]},
                                     "timing": {key: row.get(key) for key in (
                                         "load_seconds", "inference_seconds", "preprocessing_seconds",
                                         "alignment_seconds", "duration_seconds")},
                                     "device": row.get("device"),
                                     "edit_counts": row["metrics"], "status": "completed"})
                else:
                    per_unit.append({"unit_id": row["unit_id"], "split": split,
                                     "candidate": candidate["id"], **selection, "metrics": None,
                                     "edit_counts": None, "status": row["status"], "reason": row["reason"]})
            if is_complete:
                scores = score_asr_pairs([(r["reference"], r["hypothesis"]) for r in good])
                metrics = {"wer": scores["wer"], "cer": scores["cer"],
                           "rtf": sum(r["inference_seconds"] for r in good) / sum(r["duration_seconds"] for r in good)}
                complete_metrics[candidate["id"]] = metrics
                status = "complete"
            else:
                scores, metrics, status = None, None, "partial"
            aggregate.append({"candidate": candidate["id"], **selection, "status": status,
                              "expected_units": len(units), "completed_units": len(good),
                              "failed_units": sum(row["status"] == "failed" for row in rows),
                              "blocked_units": sum(row["status"] == "blocked" for row in rows),
                              "metrics": metrics, "edit_counts": scores,
                              "device": sorted({str(row.get("device")) for row in good}),
                              "hardware_profiles": sorted({
                                  json.dumps(row.get("hardware_identity"), sort_keys=True)
                                  for row in good}),
                              "runtime": {"load_seconds": max((float(row.get("load_seconds", 0)) for row in good), default=None),
                                          "inference_seconds": sum(float(row.get("inference_seconds", 0)) for row in good),
                                          "preprocessing_seconds": sum(float(row.get("preprocessing_seconds", 0)) for row in good),
                                          "alignment_seconds": sum(float(row.get("alignment_seconds", 0)) for row in good)},
                              "per_talk": _per_talk(rows, units) if is_complete else None})
        if split == "validation" and all_complete and context.profile != "smoke":
            shortlist = _rank_validation_candidates(complete_metrics, selection)
        else:
            shortlist = [{"candidate": "no_selection", "selected": False,
                          "status": ("smoke_cannot_select" if context.profile == "smoke" else
                                     "partial" if split == "validation" else "final_test_cannot_select"),
                          "reason": ("smoke_is_preflight_only" if context.profile == "smoke" else
                                     "incomplete_validation_matrix" if split == "validation" else
                                     "selection_is_validation_only"),
                          **selection}]
        status = "real" if all_complete else "partial"
        if context.status != status:
            context = replace(context, status=status)
        metadata = {"candidate_count": len(candidates), "unit_count": len(units),
                    "expected_pairs": len(expected_keys), "completed_pairs": sum(r["status"] == "completed" for r in results.values()),
                    "split": split, "checkpoint_identity": identity}
        for artifact, rows in (("asr.raw_predictions", predictions), ("asr.per_unit_metrics", per_unit),
                               ("asr.aggregate", aggregate), ("asr.shortlist", shortlist)):
            write_json_artifact(context, artifact, rows, metadata=metadata,
                                denominator=len(expected_keys) if artifact != "asr.aggregate" else len(candidates))
        failures = [{**row, **selection} for row in results.values() if row["status"] != "completed"]
        write_json_artifact(context, "asr.failure_ledger", failures or [{"status": "none", **selection}], metadata=metadata)
        # Commit the upstream identity before publishing an immutable complete
        # selection receipt. A disconnect after the receipt must leave readable evidence.
        write_run_manifest(context)
        if split == "validation" and context.profile != "smoke":
            receipt_path = context.artifact_root / "diagnostic" / context.profile / "selection_receipt.json"
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_body = {"status": "complete" if all_complete else "partial",
                            "candidate_count": len(candidates), "unit_count": len(units),
                            "candidate_ids": [candidate["id"] for candidate in candidates],
                            "selection_unit_ids_sha256": selection.get("selection_unit_ids_sha256"),
                            "test_unit_ids_sha256": _unit_ids_sha256(
                                [row for row in frozen_manifest["unit_records"] if row.get("split") == "final_test"]),
                            "dataset_manifest_sha256": frozen_manifest_sha256,
                            "checkpoint_identity": identity,
                            "source_sha256": context.source_sha256,
                            "config_sha256": context.config_sha256,
                            "dependency_state_sha256": context.dependency_state_sha256,
                            "run_id": context.run_id,
                            "candidate_ids": [candidate["id"] for candidate in candidates],
                            "shortlist_sha256": _sha(context.namespace_root / "payloads/asr.shortlist.json")}
            receipt_body["receipt_sha256"] = hashlib.sha256(json.dumps(receipt_body, sort_keys=True).encode()).hexdigest()
            temporary_receipt = receipt_path.with_suffix(f".{context.run_id}.tmp")
            temporary_receipt.write_text(json.dumps(receipt_body, indent=2) + "\n", encoding="utf-8")
            temporary_receipt.replace(receipt_path)
        if split == "final_test":
            _write_parent_index(context, selection_receipt, frozen_selection, identity,
                                "complete" if all_complete else "partial")
        print(f"[{'OK' if all_complete else 'PARTIAL'}] ASR {split}: {len(units)} unit(s), {len(candidates)} candidates, {metadata['completed_pairs']}/{len(expected_keys)} complete")
        return 0 if all_complete else 2
    except Exception as exc:
        print(f"[FAIL] ASR model benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
