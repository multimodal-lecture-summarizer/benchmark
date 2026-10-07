"""Execute or inspect the notebook DAG declared by notebook_manifest.yaml."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import nbformat
import yaml
from nbclient import NotebookClient

# Support both ``python -m benchmarks.scripts...`` and direct script execution.
# The latter otherwise places only ``benchmarks/scripts`` on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiments.registry.contract_validator import (
    DEFAULT_NOTEBOOKS,
    load_yaml,
    validate_notebook_manifest,
)


DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "experiments" / "outputs" / "executed_notebooks"
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "experiments" / "outputs" / "artifacts"
ELIGIBLE_ARTIFACT_STATUS = "real"
EVIDENCE_STATUSES = {
    "real", "dry", "proxy", "partial", "failed", "not_run", "not_eligible", "blocked_decision"
}
USABLE_DIAGNOSTIC_STATUSES = {"real", "dry", "proxy", "partial"}
FALLBACK_MARKERS = {"dry", "fallback", "mock", "proxy"}
DATASET_SELECTOR_NOTEBOOK_ID = "00b_dataset_feasibility"
DATASET_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class ManifestError(ValueError):
    """Raised when the notebook execution contract is invalid."""


def load_manifest(path: Path = DEFAULT_NOTEBOOKS) -> dict[str, Any]:
    """Load and fail closed on an invalid notebook manifest."""
    try:
        manifest = load_yaml(path)
        errors = validate_notebook_manifest(manifest)
    except (OSError, UnicodeError, yaml.YAMLError, TypeError, ValueError, KeyError) as exc:
        raise ManifestError(f"Cannot load notebook manifest {path}: {exc}") from exc
    if errors:
        raise ManifestError("Invalid notebook manifest:\n- " + "\n- ".join(errors))
    return manifest


def _producer_map(entries: Sequence[dict[str, Any]]) -> dict[str, str]:
    return {
        artifact: entry["id"]
        for entry in entries
        for artifact in entry["produces"]
    }


def topological_order(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a stable manifest-order topological sort."""
    by_id = {entry["id"]: entry for entry in entries}
    producers = _producer_map(entries)
    dependencies = {
        entry["id"]: {
            producers[artifact]
            for artifact in entry["requires"]
            if artifact in producers and producers[artifact] != entry["id"]
        }
        for entry in entries
    }
    ordered: list[dict[str, Any]] = []
    remaining = set(by_id)
    while remaining:
        notebook_id = next(
            (
                entry["id"]
                for entry in entries
                if entry["id"] in remaining and not (dependencies[entry["id"]] & remaining)
            ),
            None,
        )
        if notebook_id is None:
            raise ManifestError(f"Notebook dependency cycle: {sorted(remaining)}")
        ordered.append(by_id[notebook_id])
        remaining.remove(notebook_id)
    return ordered


def select_entries(
    manifest: dict[str, Any],
    *,
    notebook: str | None = None,
    group: str | None = None,
    task: str | None = None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """Select manifest entries without maintaining a second notebook list."""
    if profile not in (None, "full"):
        raise ManifestError("Notebook smoke profile was retired; use --profile full")
    selected = list(manifest["notebooks"])
    if notebook:
        selected = [
            entry
            for entry in selected
            if notebook in {entry["id"], entry["path"], Path(entry["path"]).name}
        ]
    elif group:
        selected = [entry for entry in selected if entry["group"] == group]
    elif task:
        selected = [entry for entry in selected if entry["task_id"] == task]
    if profile:
        selected = [entry for entry in selected if profile in entry["profiles"]]
    if not selected:
        if not any((notebook, group, task)):
            return []
        selector = notebook or group or task or profile
        raise ManifestError(f"No notebook matches selector {selector!r}")
    return topological_order(selected)


def apply_dataset_selector(
    entries: Sequence[dict[str, Any]], dataset: str | None, profile: str
) -> list[dict[str, Any]]:
    """Validate and bind a dataset selector to the sole supported notebook."""
    selected_ids = [entry["id"] for entry in entries]
    if dataset is not None:
        if not dataset or DATASET_SLUG_PATTERN.fullmatch(dataset) is None:
            raise ManifestError(
                "--dataset must be a non-empty lowercase slug containing only "
                "letters, digits, underscores, or hyphens"
            )
        if selected_ids != [DATASET_SELECTOR_NOTEBOOK_ID]:
            raise ManifestError(
                "--dataset is only valid when the selected entries are exactly "
                f"{DATASET_SELECTOR_NOTEBOOK_ID}"
            )
        bound = deepcopy(entries[0])
        bound["runtime_options"] = {
            **bound.get("runtime_options", {}),
            "dataset_filter": dataset,
        }
        if dataset == "tedlium3":
            bound["network_policy"] = "none"
        return [bound]
    return list(entries)


def validate_dataset_execution_scope(
    entries: Sequence[dict[str, Any]], profile: str
) -> None:
    """Require an explicit dataset only when a full 00b run will execute."""
    if profile != "full":
        return
    for entry in entries:
        if (
            entry["id"] == DATASET_SELECTOR_NOTEBOOK_ID
            and not entry.get("runtime_options", {}).get("dataset_filter")
        ):
            raise ManifestError(
                f"full profile for {DATASET_SELECTOR_NOTEBOOK_ID} requires --dataset"
            )


def _dataset_scope_error(location: Path, detail: str) -> ManifestError:
    return ManifestError(
        f"dataset-scoped namespace {location} {detail}; use distinct "
        "--artifact-root and --output-root"
    )


def _validate_existing_dataset_evidence(
    path: Path, requested: str, *, label: str
) -> None:
    if not os.path.lexists(path):
        return
    is_junction = getattr(path, "is_junction", lambda: False)
    if path.is_symlink() or is_junction() or not path.is_file():
        raise _dataset_scope_error(path, f"has non-regular {label}")
    try:
        prior = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _dataset_scope_error(path, f"has unreadable {label} ({exc})") from exc
    occupied_by = prior.get("dataset_filter")
    if occupied_by != requested:
        owner = repr(occupied_by) if occupied_by is not None else "legacy/unknown"
        raise _dataset_scope_error(path, f"has {label} owned by dataset {owner}")
    if label == "scope claim" and (
        prior.get("schema_version") != 1
        or prior.get("notebook_id") != DATASET_SELECTOR_NOTEBOOK_ID
    ):
        raise _dataset_scope_error(path, "has malformed scope claim identity")


def validate_dataset_namespace_evidence(
    entry: dict[str, Any], artifact_root: Path, output_root: Path,
    profile: str, run_namespace: str,
) -> None:
    """Fail closed on pre-claim evidence from another or unknown dataset."""
    if entry["id"] != DATASET_SELECTOR_NOTEBOOK_ID or run_namespace != "official":
        return
    requested = entry.get("runtime_options", {}).get("dataset_filter")
    if not requested:
        return
    artifact_manifest = (
        _namespace_root(artifact_root.resolve(), run_namespace, profile)
        / "runs"
        / f"{DATASET_SELECTOR_NOTEBOOK_ID}.run.json"
    )
    output_receipt = (
        output_root.resolve() / run_namespace / profile
        / f"{DATASET_SELECTOR_NOTEBOOK_ID}.run.json"
    )
    _validate_existing_dataset_evidence(
        artifact_manifest, requested, label="artifact run manifest"
    )
    _validate_existing_dataset_evidence(
        output_receipt, requested, label="executed-output receipt"
    )


def _claim_dataset_root(path: Path, requested: str) -> bool:
    """Atomically establish persistent dataset ownership; return whether created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "notebook_id": DATASET_SELECTOR_NOTEBOOK_ID,
        "dataset_filter": requested,
    }
    encoded = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if os.path.lexists(path):
        _validate_existing_dataset_evidence(path, requested, label="scope claim")
        return False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        _validate_existing_dataset_evidence(path, requested, label="scope claim")
        return False
    except OSError as exc:
        raise _dataset_scope_error(path, f"could not be atomically created ({exc})") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        # A partial claim remains intentionally fail-closed and requires a new root.
        raise _dataset_scope_error(path, "could not be durably written")
    return True


def claim_dataset_execution_scope(
    entry: dict[str, Any], artifact_root: Path, output_root: Path,
    profile: str, run_namespace: str,
) -> None:
    """Persistently claim both artifact and executed-output namespaces."""
    if entry["id"] != DATASET_SELECTOR_NOTEBOOK_ID or run_namespace != "official":
        return
    requested = entry.get("runtime_options", {}).get("dataset_filter")
    if not requested:
        return
    artifact_claim = (
        _namespace_root(artifact_root.resolve(), run_namespace, profile)
        / ".00b-dataset-scope.json"
    )
    output_claim = (
        output_root.resolve() / run_namespace / profile / ".00b-dataset-scope.json"
    )
    artifact_created = _claim_dataset_root(artifact_claim, requested)
    try:
        _claim_dataset_root(output_claim, requested)
    except ManifestError as exc:
        partial = " after the artifact claim was created" if artifact_created else ""
        raise ManifestError(
            f"dataset scope claim failed{partial}: {exc}; choose new matching roots"
        ) from exc


def build_plan(
    entries: Sequence[dict[str, Any]],
    profile: str,
    all_entries: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a serializable, side-effect-free execution plan."""
    if profile != "full":
        raise ManifestError("Notebook smoke profile was retired; use --profile full")
    producers = _producer_map(all_entries or load_manifest()["notebooks"])
    return [
        {
            "order": index,
            "id": entry["id"],
            "task_id": entry["task_id"],
            "group": entry["group"],
            "profile": profile,
            "path": entry["path"],
            "source_exists": (PROJECT_ROOT / entry["path"]).is_file(),
            "timeout_seconds": entry["timeout_seconds"],
            "network_policy": entry["network_policy"],
            "runner": entry["runner"],
            "runner_exists": _runner_source_path(entry).is_file(),
            "runner_source_sha256": _runner_source_sha256(entry),
            "runtime_options": entry.get("runtime_options", {}),
            "dataset_filter": entry.get("runtime_options", {}).get("dataset_filter"),
            "disk_budget": _disk_budget(profile),
            "network_budget": _network_budget(entry["network_policy"], profile),
            "requires": entry["requires"],
            "upstream_notebooks": sorted(
                {producers[item] for item in entry["requires"] if item in producers}
            ),
            "produces": entry["produces"],
        }
        for index, entry in enumerate(entries, start=1)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _runner_source_path(entry: dict[str, Any]) -> Path:
    return PROJECT_ROOT.joinpath(*entry["runner"].split(".")).with_suffix(".py")


def _runner_source_sha256(entry: dict[str, Any]) -> str | None:
    path = _runner_source_path(entry)
    return _sha256(path) if path.is_file() else None


def _code_state_sha256(entry: dict[str, Any]) -> str:
    fixed_candidates = (
        Path(__file__).resolve(),
        _runner_source_path(entry),
        PROJECT_ROOT / "experiments" / "scripts" / "benchmark_artifacts.py",
        PROJECT_ROOT / "experiments" / "registry" / "contract_validator.py",
    )
    dependency_roots = tuple(
        PROJECT_ROOT / package for package in ("ai_workers", "benchmarks", "experiments")
    )
    candidates = set(fixed_candidates)
    for dependency_root in dependency_roots:
        if dependency_root.is_dir():
            candidates.update(dependency_root.rglob("*.py"))
    state = []
    for path in sorted(candidates, key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        try:
            label = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            label = path.name
        state.append({"path": label, "sha256": _sha256(path)})
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _disk_budget(profile: str) -> dict[str, Any]:
    return {
        "status": "requires_preflight_estimate",
        "estimated_peak_bytes": None,
        "estimate_kind": "runner_specific",
        "reserve_rule": "max(100 GiB, 15% volume)",
    }


def _network_budget(policy: str, profile: str) -> dict[str, Any]:
    if policy == "none":
        return {"policy": policy, "network_allowed": False, "max_download_bytes": 0}
    return {
        "policy": policy,
        "network_allowed": True,
        "max_download_bytes": None,
        "status": "registry_receipt_required",
        "runtime_metering": "runner_receipt_required",
    }


def _declared_metric_names() -> set[str]:
    registry_path = PROJECT_ROOT / "experiments" / "registry" / "metric_registry.yaml"
    try:
        registry = load_yaml(registry_path)
    except (OSError, UnicodeError, yaml.YAMLError):
        return set()
    names: set[str] = set()
    tracks = registry.get("tracks", registry)
    if isinstance(tracks, dict):
        track_values = tracks.values()
    elif isinstance(tracks, list):
        track_values = tracks
    else:
        return names
    for track in track_values:
        if not isinstance(track, dict):
            continue
        primary = track.get("primary_metric")
        if isinstance(primary, dict) and isinstance(primary.get("name"), str):
            names.add(primary["name"].lower())
        for field in ("secondary_metrics", "diagnostic_metrics"):
            values = track.get(field, [])
            if isinstance(values, list):
                names.update(str(value).lower() for value in values)
    return names


def _entry_config_sha256(entry: dict[str, Any], profile: str, run_namespace: str) -> str:
    payload = {
        "entry": entry,
        "profile": profile,
        "run_namespace": run_namespace,
        "runner_source_sha256": _runner_source_sha256(entry),
        "code_state_sha256": _code_state_sha256(entry),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _namespace_root(artifact_root: Path, run_namespace: str, profile: str) -> Path:
    return artifact_root / run_namespace / profile


def _artifact_receipt_path(
    artifact_root: Path, run_namespace: str, profile: str, artifact_id: str
) -> Path:
    return _namespace_root(artifact_root, run_namespace, profile) / f"{artifact_id}.receipt.json"


def _validate_payload(payload_path: Path, artifact_id: str) -> tuple[list[str], int | None]:
    if not payload_path.is_file() or payload_path.stat().st_size == 0:
        return [f"{artifact_id}: payload is missing or empty: {payload_path}"], 0
    suffix = payload_path.suffix.lower()
    try:
        if suffix == ".json":
            value = json.loads(payload_path.read_text(encoding="utf-8"))
            if value in (None, {}, []):
                return [f"{artifact_id}: JSON payload has no records"], 0
            if isinstance(value, list):
                return [], len(value)
            for key in ("records", "rows", "items", "predictions", "metrics", "results"):
                if isinstance(value, dict) and key in value:
                    collection = value[key]
                    if collection in (None, {}, []):
                        return [f"{artifact_id}: JSON field {key!r} is empty"], 0
                    if isinstance(collection, (list, dict)):
                        return [], len(collection)
            return [], 1
        elif suffix in {".csv", ".tsv"}:
            rows = [line for line in payload_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if len(rows) < 2:
                return [f"{artifact_id}: tabular payload requires a header and data row"], 0
            return [], len(rows) - 1
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"{artifact_id}: payload is not parseable: {exc}"], 0
    return [], None


def _fallback_only_errors(payload_path: Path, artifact_id: str) -> list[str]:
    scientific_tokens = (
        "prediction", "metric", "aggregate", "ranking", "shortlist", "selection"
    )
    if payload_path.suffix.lower() != ".json" or not any(
        token in artifact_id for token in scientific_tokens
    ):
        return []
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    def is_fallback(value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "fallback_used" and child is True:
                    return True
                if key == "model_loaded" and child is False:
                    return True
                if key in {"evidence_status", "execution_mode", "mode", "status"}:
                    marker = re.sub(r"[\s-]+", "_", str(child).strip().lower())
                    if any(
                        marker == item
                        or marker.startswith(f"{item}_")
                        for item in FALLBACK_MARKERS
                    ):
                        return True
                if is_fallback(child):
                    return True
        elif isinstance(value, list):
            return any(is_fallback(child) for child in value)
        return False

    if is_fallback(payload):
        return [f"{artifact_id}: fallback-only evidence is not eligible for official success"]
    return []


def _scientifically_empty_errors(payload_path: Path, artifact_id: str) -> list[str]:
    scientific_tokens = ("prediction", "metric", "aggregate", "ranking")
    if payload_path.suffix.lower() != ".json" or not any(
        token in artifact_id for token in scientific_tokens
    ):
        return []
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []

    metric_keys = {"metric", "metrics", "score", "scores"}
    prediction_keys = {"prediction", "predictions"}
    ranking_keys = {"ranking", "rankings"}
    invalid_sentinels = {
        "n/a", "na", "nan", "none", "null", "not_run", "not-run", "failed",
        "failure", "blocked", "blocked_decision", "not_eligible", "not-eligible",
        "fallback", "mock", "proxy", "dry",
    }
    metadata_keys = {
        "candidate", "count", "denominator", "evidence_status", "execution_mode",
        "fallback_used", "id", "model_loaded", "mode", "n", "provenance",
        "record_count", "sample_count", "status", "unit_id",
    }
    metric_name_tokens = {
        "accuracy", "ap", "bertscore", "bleu", "cer", "collar", "coverage",
        "density", "elapsed", "error", "f1", "factuality", "faithfulness", "fps",
        "hallucination", "hit", "iou", "latency", "loss", "map", "memory",
        "meteor", "mrr", "ndcg", "pk", "precision", "rate", "ratio", "recall",
        "rouge", "rtf", "runtime", "score", "similarity", "speed", "throughput",
        "wall_time", "wer", "window_diff",
    }
    allowed_count_metrics = {"chapter_count", "keyframe_count", "token_count"}
    metric_statistic_keys = {
        "ci_high", "ci_low", "lower", "mean", "median", "std", "upper", "value",
    }

    def is_metadata_key(key: str) -> bool:
        normalized = key.lower()
        return normalized in metadata_keys or normalized.endswith(
            ("_at", "_bytes", "_count", "_duration", "_id", "_seconds")
        )

    def is_metric_key(key: str) -> bool:
        normalized = key.lower()
        if normalized.endswith("_count"):
            return normalized in allowed_count_metrics
        if normalized in {"offset", "rank"} or normalized.startswith("timestamp_"):
            return False
        if normalized.endswith(("_id", "_index")):
            return False
        return normalized in allowed_count_metrics | metric_name_tokens | _declared_metric_names()

    def finite_metric(value: Any, *, scalar_allowed: bool = False) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return scalar_allowed and math.isfinite(float(value))
        if isinstance(value, list):
            return any(finite_metric(item, scalar_allowed=scalar_allowed) for item in value)
        if isinstance(value, dict):
            return any(
                finite_metric(
                    child,
                    scalar_allowed=is_metric_key(key)
                    or (scalar_allowed and key.lower() in metric_statistic_keys),
                )
                for key, child in value.items()
                if not is_metadata_key(key) or is_metric_key(key)
            )
        return False

    def meaningful_prediction(value: Any) -> bool:
        if value is None or value == "":
            return False
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return math.isfinite(float(value))
        if isinstance(value, str):
            normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
            return bool(normalized) and normalized not in invalid_sentinels
        if isinstance(value, list):
            return any(meaningful_prediction(item) for item in value)
        if isinstance(value, dict):
            return any(
                meaningful_prediction(child)
                for key, child in value.items()
                if not is_metadata_key(key)
            )
        return False

    keyed_values: dict[str, list[Any]] = {
        "metric": [], "prediction": [], "ranking": [],
    }

    def collect_measurements(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = key.lower()
                if normalized_key in metric_keys:
                    keyed_values["metric"].append(child)
                elif normalized_key in prediction_keys:
                    keyed_values["prediction"].append(child)
                elif normalized_key in ranking_keys:
                    keyed_values["ranking"].append(child)
                collect_measurements(child)
        elif isinstance(value, list):
            for child in value:
                collect_measurements(child)

    collect_measurements(payload)
    if "metric" in artifact_id or "aggregate" in artifact_id:
        candidates = keyed_values["metric"] or [payload]
        is_meaningful = any(
            finite_metric(value, scalar_allowed=not isinstance(value, (dict, list)))
            for value in candidates
        )
    elif "prediction" in artifact_id:
        is_meaningful = bool(keyed_values["prediction"]) and any(
            meaningful_prediction(value) for value in keyed_values["prediction"]
        )
    elif "ranking" in artifact_id:
        is_meaningful = bool(keyed_values["ranking"]) and any(
            meaningful_prediction(value) for value in keyed_values["ranking"]
        )
    else:
        candidates = keyed_values["metric"] + keyed_values["prediction"] + keyed_values["ranking"]
        is_meaningful = any(
            finite_metric(value, scalar_allowed=not isinstance(value, (dict, list)))
            or meaningful_prediction(value)
            for value in candidates
        )
    if not is_meaningful:
        return [f"{artifact_id}: scientific payload has no finite metric or non-empty prediction"]
    return []


def _validate_artifacts(
    artifact_ids: Sequence[str],
    schema_version: int,
    artifact_root: Path,
    profile: str,
    run_namespace: str,
    expected_provenance: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    root = artifact_root.resolve()
    for artifact_id in artifact_ids:
        receipt_path = _artifact_receipt_path(root, run_namespace, profile, artifact_id)
        if not receipt_path.is_file():
            errors.append(f"{artifact_id}: missing receipt {receipt_path}")
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{artifact_id}: unreadable receipt: {exc}")
            continue
        expected: dict[str, Any] = {
            "artifact_id": artifact_id,
            "schema_version": schema_version,
            "profile": profile,
            "run_namespace": run_namespace,
        }
        status = receipt.get("status")
        if run_namespace == "official" and status != ELIGIBLE_ARTIFACT_STATUS:
            errors.append(f"{artifact_id}: official artifact status must be real, got {status!r}")
            continue
        if run_namespace == "diagnostic" and status not in USABLE_DIAGNOSTIC_STATUSES:
            errors.append(f"{artifact_id}: unusable diagnostic artifact status {status!r}")
            continue
        if run_namespace == "official":
            from experiments.scripts.benchmark_artifacts import validate_provenance_hashes

            try:
                validate_provenance_hashes(receipt)
            except ValueError as exc:
                errors.append(f"{artifact_id}: {exc}")
        if expected_provenance:
            expected.update(expected_provenance)
        mismatches = [
            f"{key}={receipt.get(key)!r} (expected {wanted!r})"
            for key, wanted in expected.items()
            if receipt.get(key) != wanted
        ]
        if mismatches:
            errors.append(f"{artifact_id}: receipt mismatch: {', '.join(mismatches)}")
            continue
        payload_value = receipt.get("payload_path")
        expected_hash = receipt.get("sha256")
        if not isinstance(payload_value, str) or not isinstance(expected_hash, str):
            errors.append(f"{artifact_id}: payload_path and sha256 are required")
            continue
        payload_path = (root / payload_value).resolve()
        try:
            payload_path.relative_to(root)
        except ValueError:
            errors.append(f"{artifact_id}: payload_path escapes artifact root")
            continue
        payload_errors, observed_records = _validate_payload(payload_path, artifact_id)
        if payload_errors:
            errors.extend(payload_errors)
        elif _sha256(payload_path) != expected_hash:
            errors.append(f"{artifact_id}: payload checksum mismatch")
        elif run_namespace == "official":
            errors.extend(_fallback_only_errors(payload_path, artifact_id))
            errors.extend(_scientifically_empty_errors(payload_path, artifact_id))
        if receipt.get("enrichments"):
            from experiments.scripts.artifact_enrichment import validate_enrichment

            try:
                validate_enrichment(root, receipt)
            except (OSError, KeyError, TypeError, ValueError) as exc:
                errors.append(f"{artifact_id}: invalid enrichment history: {exc}")
        record_count = receipt.get("record_count")
        denominator = receipt.get("denominator")
        if not isinstance(record_count, int) or record_count <= 0:
            errors.append(f"{artifact_id}: record_count must be a positive integer")
        elif observed_records is not None and record_count != observed_records:
            errors.append(
                f"{artifact_id}: record_count={record_count} does not match payload rows={observed_records}"
            )
        if not isinstance(denominator, int) or denominator <= 0:
            errors.append(f"{artifact_id}: denominator must be a positive integer")
        elif isinstance(record_count, int) and denominator < record_count:
            errors.append(f"{artifact_id}: denominator cannot be smaller than record_count")
    return errors


def validate_required_artifacts(
    entry: dict[str, Any], artifact_root: Path, profile: str, run_namespace: str,
    expected_producers: dict[str, str] | None = None,
) -> list[str]:
    """Validate every required artifact receipt, payload, schema, status and hash."""
    errors = _validate_artifacts(
        entry["requires"], entry["expected_schema_version"], artifact_root, profile, run_namespace
    )
    receipts_by_producer: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for artifact_id in entry["requires"]:
        receipt_path = _artifact_receipt_path(
            artifact_root.resolve(), run_namespace, profile, artifact_id
        )
        if not receipt_path.is_file():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        producer = receipt.get("producer_notebook_id")
        if not isinstance(producer, str) or not producer:
            errors.append(f"{artifact_id}: producer_notebook_id is required")
        elif expected_producers and producer != expected_producers.get(artifact_id):
            errors.append(
                f"{artifact_id}: producer {producer!r} does not match manifest "
                f"{expected_producers.get(artifact_id)!r}"
            )
        elif expected_producers:
            receipts_by_producer.setdefault(producer, []).append((artifact_id, receipt))
        run_id = receipt.get("run_id")
        try:
            uuid.UUID(str(run_id))
        except (ValueError, TypeError, AttributeError):
            errors.append(f"{artifact_id}: run_id must be a UUID")
        for field in ("source_sha256", "config_sha256", "dependency_state_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(field, ""))):
                errors.append(f"{artifact_id}: {field} must be a SHA-256 hex digest")
        if artifact_id == "dataset.frozen_manifest":
            try:
                payload_path = (
                    artifact_root.resolve() / str(receipt["payload_path"])
                ).resolve()
                payload_path.relative_to(artifact_root.resolve())
                payload = json.loads(payload_path.read_text(encoding="utf-8"))
                records = payload.get("records", [])
                eligible = [
                    record
                    for record in records
                    if record.get("freeze_status") == "eligible"
                    and record.get("scientific_selection_eligible") is True
                    and (record.get("unit_ids") or record.get("unit_id"))
                ]
                if not eligible:
                    errors.append(
                        "dataset.frozen_manifest: no scientifically eligible frozen units"
                    )
            except (
                KeyError, OSError, UnicodeError, json.JSONDecodeError, AttributeError, ValueError
            ) as exc:
                errors.append(f"dataset.frozen_manifest: semantic validation failed: {exc}")
    for producer, producer_receipts in receipts_by_producer.items():
        manifest_path = (
            _namespace_root(artifact_root.resolve(), run_namespace, profile)
            / "runs"
            / f"{producer}.run.json"
        )
        try:
            run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{producer}: upstream run manifest is missing or unreadable: {exc}")
            continue
        expected_manifest = {
            "schema_version": 1,
            "notebook_id": producer,
            "profile": profile,
            "run_namespace": run_namespace,
        }
        for key, wanted in expected_manifest.items():
            if run_manifest.get(key) != wanted:
                errors.append(
                    f"{producer}: upstream run manifest {key}={run_manifest.get(key)!r} "
                    f"(expected {wanted!r})"
                )
        for artifact_id, receipt in producer_receipts:
            for key in (
                "run_id", "status", "source_sha256", "config_sha256",
                "dependency_state_sha256",
            ):
                if receipt.get(key) != run_manifest.get(key):
                    errors.append(
                        f"{artifact_id}: {key} does not match upstream run manifest"
                    )
    return errors


def validate_produced_artifacts(
    entry: dict[str, Any], artifact_root: Path, profile: str, run_namespace: str,
    run_context: dict[str, Any],
) -> list[str]:
    """Reject successful kernels that did not emit complete scientific evidence."""
    expected_provenance = {
        "producer_notebook_id": entry["id"],
        "run_id": run_context["run_id"],
        "source_sha256": run_context["source_sha256"],
        "config_sha256": run_context["config_sha256"],
        "dependency_state_sha256": run_context["dependency_state_sha256"],
        "status": run_context["status"],
    }
    if "dataset_filter" in run_context:
        expected_provenance["dataset_filter"] = run_context["dataset_filter"]
    errors = _validate_artifacts(
        entry["produces"], entry["expected_schema_version"], artifact_root, profile, run_namespace,
        expected_provenance,
    )
    runner_manifest = (
        _namespace_root(artifact_root.resolve(), run_namespace, profile)
        / "runs"
        / f"{entry['id']}.run.json"
    )
    if not runner_manifest.is_file():
        errors.append(f"run manifest missing: {runner_manifest}")
        return errors
    try:
        payload = json.loads(runner_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"run manifest unreadable: {exc}")
        return errors
    expected = {
        "schema_version": 1,
        "notebook_id": entry["id"],
        "profile": profile,
        "run_namespace": run_namespace,
        "status": run_context["status"],
        "config_sha256": run_context["config_sha256"],
        "run_id": run_context["run_id"],
        "source_sha256": run_context["source_sha256"],
        "dependency_state_sha256": run_context["dependency_state_sha256"],
    }
    if "dataset_filter" in run_context:
        expected["dataset_filter"] = run_context["dataset_filter"]
    mismatches = [key for key, wanted in expected.items() if payload.get(key) != wanted]
    if mismatches:
        errors.append(f"run manifest mismatch: {mismatches}")
    return errors


def dependency_state_sha256(
    entry: dict[str, Any], artifact_root: Path, profile: str, run_namespace: str
) -> str:
    state = []
    for artifact_id in sorted(entry["requires"]):
        receipt_path = _artifact_receipt_path(
            artifact_root.resolve(), run_namespace, profile, artifact_id
        )
        state.append({"artifact_id": artifact_id, "receipt_sha256": _sha256(receipt_path)})
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def produced_state_sha256(
    entry: dict[str, Any], artifact_root: Path, profile: str, run_namespace: str
) -> str:
    paths = [
        _artifact_receipt_path(artifact_root.resolve(), run_namespace, profile, artifact_id)
        for artifact_id in sorted(entry["produces"])
    ]
    state = [{"path": str(path), "sha256": _sha256(path)} for path in paths]
    return hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _run_receipt_path(destination: Path) -> Path:
    return destination.with_suffix(".run.json")


def notebook_source_sha256(source: Path) -> str:
    """Identify executable notebook content without incorporating saved results."""
    notebook = nbformat.read(source, as_version=4)
    identity = {
        "experiment_contract": notebook.metadata.get("experiment_contract"),
        "cells": [
            {
                "id": cell.get("id"),
                "cell_type": cell.cell_type,
                "source": cell.source,
                "tags": cell.get("metadata", {}).get("tags", []),
            }
            for cell in notebook.cells
        ],
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _atomic_write_notebook(notebook: Any, destination: Path) -> None:
    """Replace a notebook only after its complete serialized form reaches disk."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with pending.open("wb") as handle:
            handle.write(nbformat.writes(notebook).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)


def _mark_notebook_run(destination: Path, run_context: dict[str, Any], status: str,
                       error: str | None = None) -> None:
    notebook = nbformat.read(destination, as_version=4)
    notebook.metadata["benchmark_execution"] = {
        "run_id": run_context["run_id"],
        "profile": run_context["profile"],
        "run_namespace": run_context["run_namespace"],
        "dataset_filter": run_context.get("dataset_filter"),
        "source_sha256": run_context["source_sha256"],
        "status": status,
        **({"error": error} if error else {}),
    }
    _atomic_write_notebook(notebook, destination)


def can_resume(
    entry: dict[str, Any], source: Path, destination: Path, profile: str,
    run_namespace: str, dependency_sha256: str, evidence_status: str,
    produced_sha256: str,
) -> tuple[bool, str]:
    """Accept resume only for a parseable output backed by matching hashes."""
    receipt_path = _run_receipt_path(destination)
    if not source.is_file():
        return False, "source notebook is missing"
    if not destination.is_file() or not receipt_path.is_file():
        return False, "executed notebook or run receipt is missing"
    try:
        executed = nbformat.read(destination, as_version=4)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, nbformat.reader.NotJSONError) as exc:
        return False, f"invalid executed output or receipt: {exc}"
    execution = executed.metadata.get("benchmark_execution", {})
    if execution and (
        execution.get("status") != "validated"
        or execution.get("run_id") != receipt.get("run_id")
    ):
        return False, "notebook execution status or run ID is not validated"
    if source.resolve() == destination.resolve() and not execution:
        return False, "in-place notebook lacks validated execution metadata"
    expected = {
        "schema_version": 1,
        "notebook_id": entry["id"],
        "profile": profile,
        "run_namespace": run_namespace,
        "status": evidence_status,
        "source_sha256": notebook_source_sha256(source),
        "output_sha256": _sha256(destination),
        "config_sha256": _entry_config_sha256(entry, profile, run_namespace),
        "dependency_state_sha256": dependency_sha256,
        "produced_state_sha256": produced_sha256,
    }
    if "dataset_filter" in entry.get("runtime_options", {}):
        expected["dataset_filter"] = entry["runtime_options"]["dataset_filter"]
    mismatches = [key for key, wanted in expected.items() if receipt.get(key) != wanted]
    return (not mismatches, "matching receipt" if not mismatches else f"receipt mismatch: {mismatches}")


def _write_run_receipt(
    entry: dict[str, Any], source: Path, destination: Path, profile: str,
    run_namespace: str, run_context: dict[str, Any], produced_sha256: str,
) -> None:
    receipt = {
        "schema_version": 1,
        "notebook_id": entry["id"],
        "profile": profile,
        "run_namespace": run_namespace,
        "status": run_context["status"],
        "source_sha256": notebook_source_sha256(source),
        "output_sha256": _sha256(destination),
        "config_sha256": _entry_config_sha256(entry, profile, run_namespace),
        "dependency_state_sha256": run_context["dependency_state_sha256"],
        "produced_state_sha256": produced_sha256,
        "run_id": run_context["run_id"],
        "dataset_filter": run_context.get("dataset_filter"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _run_receipt_path(destination).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


def _write_start_record(
    entry: dict[str, Any], artifact_root: Path, profile: str,
    run_namespace: str, run_context: dict[str, Any],
) -> None:
    path = (
        _namespace_root(artifact_root.resolve(), run_namespace, profile)
        / "runs"
        / f"{entry['id']}.start.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run_context, indent=2) + "\n", encoding="utf-8")


def execute_notebook(
    entry: dict[str, Any],
    source: Path,
    destination: Path,
    timeout: int,
    profile: str,
    run_namespace: str,
    artifact_root: Path,
    run_context: dict[str, Any],
) -> tuple[bool, float, str | None]:
    """Execute clean cells and preserve visible partial outputs on failure."""
    started = time.perf_counter()
    notebook = None
    try:
        notebook = nbformat.read(source, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.outputs = []
                cell.execution_count = None
        _run_receipt_path(destination).unlink(missing_ok=True)
        notebook.metadata["benchmark_execution"] = {
            "run_id": run_context["run_id"],
            "profile": profile,
            "run_namespace": run_namespace,
            "dataset_filter": entry.get("runtime_options", {}).get("dataset_filter"),
            "source_sha256": run_context["source_sha256"],
            "status": "running",
        }
        _atomic_write_notebook(notebook, destination)
        dataset_filter = str(entry.get("runtime_options", {}).get("dataset_filter", ""))
        NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(PROJECT_ROOT)}},
        ).execute(
            env={
                **os.environ,
                "MLS_BENCHMARK_PROFILE": profile,
                "MLS_RUN_NAMESPACE": run_namespace,
                "MLS_NOTEBOOK_ID": entry["id"],
                "MLS_CONFIG_SHA256": run_context["config_sha256"],
                "MLS_ARTIFACT_ROOT": str(artifact_root.resolve()),
                "MLS_RUN_ID": run_context["run_id"],
                "MLS_SOURCE_SHA256": run_context["source_sha256"],
                "MLS_DEPENDENCY_STATE_SHA256": run_context["dependency_state_sha256"],
                "MLS_EVIDENCE_STATUS": run_context["status"],
                # Always override the ambient process value so a prior shell cannot
                # silently change the benchmark selection.
                "MLS_DATASET_FILTER": str(
                    entry.get("runtime_options", {}).get("dataset_filter", "")
                ),
                "HF_DATASETS_OFFLINE": (
                    "1" if dataset_filter == "tedlium3"
                    else os.environ.get("HF_DATASETS_OFFLINE", "")
                ),
                "HF_HUB_OFFLINE": (
                    "1" if dataset_filter == "tedlium3"
                    else os.environ.get("HF_HUB_OFFLINE", "")
                ),
            }
        )
        notebook.metadata["benchmark_execution"]["status"] = "executed_unvalidated"
        _atomic_write_notebook(notebook, destination)
        return True, time.perf_counter() - started, None
    except Exception as exc:  # nbclient exposes several backend-specific errors
        if notebook is not None:
            try:
                notebook.metadata["benchmark_execution"]["status"] = "failed"
                notebook.metadata["benchmark_execution"]["error"] = str(exc)
                _atomic_write_notebook(notebook, destination)
            except Exception as save_exc:
                return False, time.perf_counter() - started, f"{exc}; failed to save notebook: {save_exc}"
        return False, time.perf_counter() - started, str(exc)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_NOTEBOOKS)
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--notebook", help="Notebook ID, path, or filename")
    selectors.add_argument("--group", help="Two-digit notebook group")
    selectors.add_argument("--task", help="Exact task_id")
    parser.add_argument("--profile", help="Notebook execution profile (full only)")
    parser.add_argument(
        "--dataset",
        help="Exact local dataset slug (supported only for 00b_dataset_feasibility)",
    )
    parser.add_argument("--list", action="store_true", help="List selected notebooks")
    parser.add_argument("--dry-plan", action="store_true", help="Print the plan without executing")
    parser.add_argument("--resume", action="store_true", help="Skip an existing executed output")
    parser.add_argument("--run-namespace", choices=("official", "diagnostic"), default="official")
    parser.add_argument("--evidence-status", choices=sorted(EVIDENCE_STATUSES))
    parser.add_argument("--output-root", type=Path,
                        help="Compatibility output directory; by default update the source notebook")
    parser.add_argument("--artifact-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.profile not in (None, "full"):
            raise ManifestError("Notebook smoke profile was retired; use --profile full")
        manifest = load_manifest(args.manifest)
        profile = args.profile or manifest["official_default_profile"]
        evidence_status = args.evidence_status or (
            ELIGIBLE_ARTIFACT_STATUS if args.run_namespace == "official" else "dry"
        )
        if args.run_namespace == "official" and evidence_status != ELIGIBLE_ARTIFACT_STATUS:
            raise ManifestError("official namespace requires evidence-status=real")
        if args.run_namespace == "diagnostic" and evidence_status not in USABLE_DIAGNOSTIC_STATUSES:
            raise ManifestError(
                f"diagnostic execution requires one of {sorted(USABLE_DIAGNOSTIC_STATUSES)}"
            )
        entries = select_entries(
            manifest,
            notebook=args.notebook,
            group=args.group,
            task=args.task,
            profile=profile,
        )
        entries = apply_dataset_selector(entries, args.dataset, profile)
    except (FileNotFoundError, ValueError, ManifestError) as exc:
        print(f"[FAIL] {exc}")
        return 2

    plan = build_plan(entries, profile, manifest["notebooks"])
    if args.list:
        for item in plan:
            print(f"{item['id']}\t{item['task_id']}\t{item['path']}")
        return 0
    if args.dry_plan:
        print(json.dumps({"profile": profile, "notebooks": plan}, indent=2))
        return 0

    if not entries:
        print("[FAIL] No notebook is registered; create and register one when needed")
        return 2

    try:
        validate_dataset_execution_scope(entries, profile)
    except ManifestError as exc:
        print(f"[FAIL] {exc}")
        return 2

    dataset_scope = (
        entries[0].get("runtime_options", {}).get("dataset_filter")
        if len(entries) == 1 and entries[0]["id"] == DATASET_SELECTOR_NOTEBOOK_ID
        else None
    )
    # A single visible 00b notebook may display different datasets on different
    # runs; evidence and ownership claims remain isolated outside that file.
    default_scope = Path("datasets") / dataset_scope if dataset_scope else Path()
    artifact_root = args.artifact_root or DEFAULT_ARTIFACT_ROOT / default_scope
    output_root = args.output_root or DEFAULT_OUTPUT_ROOT / default_scope

    failed = False
    outcomes: dict[str, str] = {}
    selected_ids = {entry["id"] for entry in entries}
    producers = _producer_map(manifest["notebooks"])
    for entry in entries:
        source = PROJECT_ROOT / entry["path"]
        destination = (
            output_root / args.run_namespace / profile / f"{entry['id']}.ipynb"
            if args.output_root is not None else source
        )
        upstream = {
            producers[artifact]
            for artifact in entry["requires"]
            if artifact in producers and producers[artifact] in selected_ids
        }
        blocked_by = sorted(
            notebook_id for notebook_id in upstream if outcomes.get(notebook_id) in {"failed", "blocked"}
        )
        if blocked_by:
            print(f"[BLOCKED] {entry['id']}: failed upstream notebooks: {blocked_by}")
            outcomes[entry["id"]] = "blocked"
            failed = True
            continue
        if not source.is_file():
            print(f"[FAIL] {entry['id']}: source notebook not found: {source}")
            outcomes[entry["id"]] = "failed"
            failed = True
            continue
        runner_source = _runner_source_path(entry)
        if not runner_source.is_file():
            print(f"[FAIL] {entry['id']}: runner source module not found: {runner_source}")
            outcomes[entry["id"]] = "failed"
            failed = True
            continue
        try:
            validate_dataset_namespace_evidence(
                entry, artifact_root, output_root, profile, args.run_namespace
            )
        except ManifestError as exc:
            print(f"[FAIL] {entry['id']}: {exc}")
            outcomes[entry["id"]] = "failed"
            failed = True
            continue
        artifact_errors = validate_required_artifacts(
            entry, artifact_root, profile, args.run_namespace, producers
        )
        if artifact_errors:
            print(f"[FAIL] {entry['id']}: required artifact validation failed")
            for error in artifact_errors:
                print(f"  - {error}")
            outcomes[entry["id"]] = "failed"
            failed = True
            continue
        dependency_sha256 = dependency_state_sha256(
            entry, artifact_root, profile, args.run_namespace
        )
        try:
            claim_dataset_execution_scope(
                entry, artifact_root, output_root, profile, args.run_namespace
            )
        except ManifestError as exc:
            print(f"[FAIL] {entry['id']}: {exc}")
            outcomes[entry["id"]] = "failed"
            failed = True
            continue
        if args.resume:
            try:
                prior_receipt = json.loads(
                    _run_receipt_path(destination).read_text(encoding="utf-8")
                )
                resume_context = {
                    key: prior_receipt[key]
                    for key in (
                        "run_id", "status", "source_sha256", "config_sha256",
                        "dependency_state_sha256", "dataset_filter",
                    )
                }
                produced_errors = validate_produced_artifacts(
                    entry, artifact_root, profile, args.run_namespace, resume_context
                )
                produced_sha256 = produced_state_sha256(
                    entry, artifact_root, profile, args.run_namespace
                ) if not produced_errors else ""
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError):
                produced_errors = ["missing or invalid prior run receipt"]
                produced_sha256 = ""
            resumable, reason = can_resume(
                entry, source, destination, profile, args.run_namespace,
                dependency_sha256, evidence_status, produced_sha256,
            )
            if resumable and not produced_errors:
                print(f"[SKIP] {entry['id']}: {reason}")
                outcomes[entry["id"]] = evidence_status
                continue
            detail = reason if not resumable else f"invalid produced evidence: {produced_errors}"
            print(f"[RERUN] {entry['id']}: {detail}")
        run_context = {
            "schema_version": 1,
            "notebook_id": entry["id"],
            "profile": profile,
            "run_namespace": args.run_namespace,
            "status": evidence_status,
            "run_id": str(uuid.uuid4()),
            "source_sha256": notebook_source_sha256(source),
            "config_sha256": _entry_config_sha256(entry, profile, args.run_namespace),
            "dependency_state_sha256": dependency_sha256,
            "runner_source_sha256": _runner_source_sha256(entry),
            "code_state_sha256": _code_state_sha256(entry),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "dataset_filter": entry.get("runtime_options", {}).get("dataset_filter"),
        }
        _write_start_record(
            entry, artifact_root, profile, args.run_namespace, run_context
        )
        ok, elapsed, error = execute_notebook(
            entry,
            source,
            destination,
            entry["timeout_seconds"],
            profile,
            args.run_namespace,
            artifact_root,
            run_context,
        )
        if ok:
            produced_errors = validate_produced_artifacts(
                entry, artifact_root, profile, args.run_namespace, run_context
            )
            if produced_errors:
                _mark_notebook_run(
                    destination, run_context, "failed",
                    "produced evidence validation failed: " + "; ".join(produced_errors),
                )
                print(f"[FAIL] {entry['id']}: produced evidence validation failed")
                for produced_error in produced_errors:
                    print(f"  - {produced_error}")
                outcomes[entry["id"]] = "failed"
                failed = True
                continue
            produced_sha256 = produced_state_sha256(
                entry, artifact_root, profile, args.run_namespace
            )
            _mark_notebook_run(destination, run_context, "validated")
            _write_run_receipt(
                entry, source, destination, profile, args.run_namespace,
                run_context, produced_sha256,
            )
            print(f"[OK] {entry['id']} ({elapsed:.1f}s) -> {destination}")
            outcomes[entry["id"]] = evidence_status
        else:
            print(f"[FAIL] {entry['id']} ({elapsed:.1f}s): {error}")
            outcomes[entry["id"]] = "failed"
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
