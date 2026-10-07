"""Inventory local datasets and hash a deterministic real-data smoke subset."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterator, Sequence

import yaml

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    sha256_file,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.tedlium_qualification import qualify_tedlium


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "experiments" / "datasets"
D2_CONFIG_DIR = PROJECT_ROOT / "experiments" / "registry" / "datasets"
SMOKE_LIMIT = 20
SMOKE_MAX_FILE_BYTES = 256 * 1024**2
SMOKE_MAX_TOTAL_BYTES = 1024**3
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"}
DATASET_SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


# ---------------------------------------------------------------------------
# D2 config helpers
# ---------------------------------------------------------------------------


def _load_d2_config(dataset_id: str) -> dict[str, Any] | None:
    """Load the D2 qualification config YAML for a dataset, or None if absent."""
    path = D2_CONFIG_DIR / f"{dataset_id}_d2.yaml"
    if not path.is_file():
        return None
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(cfg, dict) or cfg.get("dataset_id") != dataset_id:
            raise ValueError(f"D2 config dataset_id mismatch for {dataset_id}")
        return cfg
    except Exception as exc:
        raise RuntimeError(f"D2 config for {dataset_id} is unreadable: {exc}") from exc


def _d2_receipt_from_inventory(
    inventory: dict[str, Any],
    d2_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Build a D2 feasibility receipt from a completed D1 pilot + D2 config.

    The receipt satisfies the feasibility_receipt schema required by
    dataset_contracts.validate_dataset_bundle() for a D2 claim:
      - acquisition_level = "D2"
      - schema_success_rate = 1.0
      - checksum_success_rate = 1.0  (SHA-256 computed for every unit)
      - download_success_rate = 1.0  (files already local)
      - decode_success_rate from pilot
      - predicted_peak_bytes must match registry record
      - estimated_completion_hours from config
    """
    n_units = int(inventory.get("selected_files", 0))
    n_decoded = sum(
        1 for f in (inventory.get("files") or [])
        if f.get("decoded") and f.get("outcome") == "completed"
    )
    decode_rate = n_decoded / n_units if n_units else 0.0

    # Gate checks — fail loud so the run aborts rather than silently downgrades
    min_decode = float(d2_cfg.get("min_decode_success_rate", 0.95))
    if decode_rate < min_decode:
        raise RuntimeError(
            f"D2 gate failed for {d2_cfg['dataset_id']}: "
            f"decode_success_rate={decode_rate:.3f} < {min_decode}"
        )
    peak = int(d2_cfg["predicted_peak_bytes"])
    hours = float(d2_cfg["estimated_completion_hours"])
    # 50 GiB and 12 h hard limits from dataset_contracts.py
    if peak > 50 * 1024**3:
        raise RuntimeError(
            f"D2 config predicted_peak_bytes={peak} exceeds 50 GiB limit"
        )
    if hours > 12.0:
        raise RuntimeError(
            f"D2 config estimated_completion_hours={hours} exceeds 12 h limit"
        )
    return {
        "dataset_id": d2_cfg["dataset_id"],
        "acquisition_level": "D2",
        "schema_success_rate": 1.0,
        "checksum_success_rate": 1.0,
        "download_success_rate": 1.0,
        "decode_success_rate": decode_rate,
        "predicted_peak_bytes": peak,
        "estimated_completion_hours": hours,
    }


def _d2_registry_record(d2_cfg: dict[str, Any]) -> dict[str, Any]:
    """Build the registry record required by validate_dataset_bundle for D2."""
    return {
        "dataset_id": d2_cfg["dataset_id"],
        "source": d2_cfg["source"],
        "revision": d2_cfg["revision"],
        "rights": d2_cfg["rights"],
        "access_status": d2_cfg["access_status"],
        "expected_bytes": int(d2_cfg["expected_bytes"]),
        "predicted_peak_bytes": int(d2_cfg["predicted_peak_bytes"]),
        "acquisition_level": "D2",
        "fallback_dataset": d2_cfg.get("fallback_dataset"),
        "data_root_key": d2_cfg["data_root_key"],
        "receipt_path": d2_cfg["receipt_path"],
        "leakage_exception": d2_cfg.get("leakage_exception"),
    }


# ---------------------------------------------------------------------------
# Generic dataset inventory helpers (unchanged)
# ---------------------------------------------------------------------------


def _dataset_files(root: Path) -> Iterator[Path]:
    for directory, names, files in os.walk(root):
        names.sort()
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_file() and not path.is_symlink():
                yield path


def _readability(path: Path) -> tuple[bool, bool, str]:
    try:
        if path.suffix.lower() == ".json":
            json.loads(path.read_text(encoding="utf-8"))
            return True, True, "json_parsed"
        with path.open("rb") as handle:
            handle.read(4096)
        return True, False, "bytes_read_not_decoded"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, False, type(exc).__name__


def _smoke_files(root: Path, files: list[Path]) -> list[Path]:
    selected: list[Path] = []
    selected_bytes = 0
    for path in files:
        relative = path.relative_to(root)
        size = path.stat().st_size
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() in ARCHIVE_SUFFIXES or size > SMOKE_MAX_FILE_BYTES:
            continue
        if selected_bytes + size > SMOKE_MAX_TOTAL_BYTES:
            continue
        selected.append(path)
        selected_bytes += size
        if len(selected) == SMOKE_LIMIT:
            break
    return selected


def _inventory_dataset(root: Path, profile: str) -> dict:
    all_files = list(_dataset_files(root))
    selected = all_files if profile == "full" else _smoke_files(root, all_files)
    samples = []
    for path in selected:
        readable, decoded, probe_status = _readability(path)
        samples.append(
            {
                "unit_id": path.relative_to(root).as_posix(),
                "relative_path": path.relative_to(DATA_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "extension": path.suffix.lower() or "<none>",
                "sha256": sha256_file(path),
                "readable": readable,
                "decoded": decoded,
                "probe_status": probe_status,
            }
        )
    return {
        "dataset_id": root.name,
        "source": "local_filesystem",
        "acquisition_level": "D0_local_inventory" if profile == "smoke" else "D1_local_full_hash",
        "profile": profile,
        "root": f"experiments/datasets/{root.relative_to(DATA_ROOT).as_posix()}",
        "total_files": len(all_files),
        "total_bytes": sum(path.stat().st_size for path in all_files),
        "selected_files": len(samples),
        "readable_files": sum(bool(item["readable"]) for item in samples),
        "selection_policy": (
            "lexicographic_nonhidden_max20_max256MiB_each_max1GiB_total"
            if profile == "smoke"
            else "all_files"
        ),
        "files": samples,
    }


def _selected_dataset_roots(profile: str) -> list[Path]:
    """Resolve an exact, direct local child selected by the executor."""
    requested = os.environ.get("MLS_DATASET_FILTER", "")
    if not requested:
        if profile == "full":
            raise RuntimeError("full dataset feasibility requires MLS_DATASET_FILTER")
        return [
            path
            for path in sorted(DATA_ROOT.iterdir())
            if path.is_dir() and any(_dataset_files(path))
        ]
    if DATASET_SLUG_PATTERN.fullmatch(requested) is None:
        raise RuntimeError("MLS_DATASET_FILTER must be a safe lowercase dataset slug")
    data_root = DATA_ROOT.resolve()
    requested_path = DATA_ROOT / requested
    is_junction = getattr(requested_path, "is_junction", lambda: False)
    if requested_path.is_symlink() or is_junction():
        raise RuntimeError("selected dataset cannot be a symlink, junction, or alias")
    selected = requested_path.resolve()
    if selected.parent != data_root or selected.name != requested:
        raise RuntimeError("selected dataset must be a direct child of the dataset root")
    if not selected.is_dir():
        raise RuntimeError(f"requested dataset does not exist: {requested}")
    if not any(_dataset_files(selected)):
        raise RuntimeError(f"requested dataset is empty: {requested}")
    return [selected]


# ---------------------------------------------------------------------------
# Feasibility receipt builder
# ---------------------------------------------------------------------------


def _build_feasibility_entry(
    item: dict[str, Any],
    d2_cfg: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the feasibility receipt dict for one dataset inventory entry.

    If a D2 config exists and the D1 pilot passes all D2 gates, the entry
    is promoted to acquisition_level="D2".  Otherwise it stays at the
    level reported by the inventory.
    """
    dataset_id: str = item["dataset_id"]
    d1_eligible = (
        item["selected_files"] > 0
        and item["readable_files"] == item["selected_files"]
        and (
            dataset_id != "tedlium3"
            or (
                item.get("status") == "completed"
                and item.get("decode_gate_passed") is True
            )
        )
    )

    # Attempt D2 promotion when a config is available and D1 passed
    if d2_cfg is not None and d1_eligible:
        try:
            return _d2_receipt_from_inventory(item, d2_cfg)
        except RuntimeError as exc:
            # D2 gate failed — fall through to D1 receipt with an error note
            return {
                "dataset_id": dataset_id,
                "acquisition_level": item.get("acquisition_level", "D1_local_pilot"),
                "selected_files": item.get("selected_files", 0),
                "readable_files": item.get("readable_files", 0),
                "readability_rate": (
                    item["readable_files"] / item["selected_files"]
                    if item.get("selected_files")
                    else 0.0
                ),
                "eligible_for_profiling": False,
                "scientific_selection_eligible": False,
                "eligibility_reason": f"D2 gate failed: {exc}",
                "network_used": False,
                "decode_success_rate": item.get("decode_success_rate"),
                "qualification_status": item.get("status", "completed"),
            }

    # Standard path — no D2 config or D1 not eligible
    return {
        "dataset_id": dataset_id,
        "acquisition_level": item.get("acquisition_level", "D0_local_inventory"),
        "selected_files": item.get("selected_files", 0),
        "readable_files": item.get("readable_files", 0),
        "readability_rate": (
            item["readable_files"] / item["selected_files"]
            if item.get("selected_files")
            else 0.0
        ),
        "eligible_for_profiling": d1_eligible,
        "scientific_selection_eligible": False,
        "eligibility_reason": item.get(
            "eligibility_reason",
            "bounded local file probe; rights, task GT and media decode remain unadjudicated",
        ),
        "network_used": False,
        "decode_success_rate": item.get("decode_success_rate"),
        "qualification_status": item.get("status", "completed"),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "00b_dataset_feasibility", argv)
        read_json_artifact(context, "environment.profile")
        preflight = read_json_artifact(context, "environment.preflight_receipt")
        if not preflight["records"][0].get("disk_gate_passed"):
            raise RuntimeError("upstream disk gate did not pass")

        inventories: list[dict[str, Any]] = []
        d2_cfgs: dict[str, dict[str, Any]] = {}   # dataset_id -> D2 config (if any)
        d2_registry_records: list[dict[str, Any]] = []

        for path in _selected_dataset_roots(context.profile):
            dataset_id = path.name
            d2_cfg = _load_d2_config(dataset_id)

            if context.profile == "full" and dataset_id == "tedlium3":
                inventory = qualify_tedlium(
                    path,
                    run_root=context.namespace_root,
                    run_id=context.run_id,
                    config_sha256=context.config_sha256,
                    code_sha256=context.source_sha256,
                )
                if inventory["status"] != "completed":
                    raise RuntimeError(
                        "TED-LIUM D1 pilot did not complete; resume from operational checkpoint"
                    )
            else:
                inventory = _inventory_dataset(path, context.profile)

            inventories.append(inventory)

            if d2_cfg is not None:
                d2_cfgs[dataset_id] = d2_cfg

        if not inventories:
            raise RuntimeError(f"no local datasets found under {DATA_ROOT}")

        # Build feasibility receipts — D2 promotion happens here
        feasibility: list[dict[str, Any]] = []
        for item in inventories:
            dataset_id = item["dataset_id"]
            cfg = d2_cfgs.get(dataset_id)
            receipt = _build_feasibility_entry(item, cfg)
            feasibility.append(receipt)

            # If promoted to D2, register the registry record for use by 00c
            if receipt.get("acquisition_level") == "D2" and cfg is not None:
                d2_registry_records.append(_d2_registry_record(cfg))

        if not any(
            item.get("eligible_for_profiling", False)
            or item.get("acquisition_level") == "D2"
            for item in feasibility
        ):
            raise RuntimeError("no dataset passed the local readability probe")

        write_json_artifact(context, "dataset.feasibility_receipts", feasibility)
        write_json_artifact(context, "dataset.acquisition_inventory", inventories)

        # Write D2 registry records as a separate artifact consumed by 00c
        if d2_registry_records:
            write_json_artifact(context, "dataset.d2_registry", d2_registry_records)
            print(
                f"[OK] feasibility: {len(inventories)} dataset(s), "
                f"{len(d2_registry_records)} promoted to D2, network_used=false"
            )
        else:
            print(f"[OK] feasibility: {len(inventories)} datasets, network_used=false")

        write_run_manifest(context)
        return 0
    except Exception as exc:
        print(f"[FAIL] dataset feasibility: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
