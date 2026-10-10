"""Move historical notebook copies into a verified archive.

The active notebooks remain under experiments/notebooks. This migration keeps
old run bytes and receipts available without leaving duplicate runnable files.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments"
HISTORY_DIRS = (
    EXPERIMENTS / "notebooks" / "legacy",
    EXPERIMENTS / "legacy_notebooks",
    EXPERIMENTS / "legacy_notebooks_backup",
    EXPERIMENTS / "outputs" / "executed_notebooks",
    EXPERIMENTS / "outputs" / "phase1_smoke_audit" / "executed",
)
ARCHIVE = EXPERIMENTS / "notebook_history_20260926.zip"
INDEX = EXPERIMENTS / "notebook_history_20260926.manifest.json"
DIAGNOSTIC_MIGRATIONS = {
    "phase12_evidence_repair.ipynb": "phase12_repair_260926/phase12-evidence-repair-20260926T094151043461Z.ipynb",
    "phase12_qualification_supplement.ipynb": "phase12_repair_260926/phase12_qualification_supplement-20260926T094714806867Z.ipynb",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(data)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _history_files() -> list[Path]:
    files = []
    for directory in HISTORY_DIRS:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and (path.suffix == ".ipynb" or path.name.endswith(".run.json")):
                resolved = path.resolve()
                if not resolved.is_relative_to(directory.resolve()):
                    raise RuntimeError(f"History path escapes approved directory: {path}")
                files.append(path)
    return sorted(files)


def _remove_verified(path: Path, entry: dict) -> None:
    resolved = path.resolve()
    if not any(resolved.is_relative_to(directory.resolve()) for directory in HISTORY_DIRS):
        raise RuntimeError(f"Refusing to remove path outside history roots: {path}")
    if _sha(path.read_bytes()) != entry["sha256"]:
        raise RuntimeError(f"History changed during archive: {path}")
    path.unlink()


def _code_sources(notebook: nbformat.NotebookNode) -> list[str]:
    return [str(cell.source) for cell in notebook.cells if cell.cell_type == "code"]


def _migrate_diagnostics() -> list[dict[str, str | int]]:
    migrated = []
    for filename, old_relative in DIAGNOSTIC_MIGRATIONS.items():
        destination = EXPERIMENTS / "notebooks" / "diagnostics" / filename
        historical = EXPERIMENTS / "outputs" / "executed_notebooks" / old_relative
        current = nbformat.read(destination, as_version=4)
        previous = nbformat.read(historical, as_version=4)
        if _code_sources(current) != _code_sources(previous):
            raise RuntimeError(f"Cannot migrate changed code into {destination}")
        old_code = (cell for cell in previous.cells if cell.cell_type == "code")
        output_count = 0
        for cell in current.cells:
            if cell.cell_type == "code":
                old_cell = next(old_code)
                cell.outputs = copy.deepcopy(old_cell.outputs)
                cell.execution_count = old_cell.execution_count
                output_count += len(cell.outputs)
        if output_count == 0:
            raise RuntimeError(f"Historical notebook has no outputs: {historical}")
        current.metadata["consolidated_historical_run"] = str(historical.relative_to(ROOT)).replace("\\", "/")
        nbformat.validate(current)
        _atomic_bytes(destination, nbformat.writes(current).encode("utf-8"))
        migrated.append({"canonical": str(destination.relative_to(ROOT)).replace("\\", "/"), "historical": str(historical.relative_to(ROOT)).replace("\\", "/"), "outputs": output_count})
    return migrated


def consolidate() -> dict:
    candidates = _history_files()
    if ARCHIVE.exists() != INDEX.exists():
        raise RuntimeError("Archive and index must either both exist or both be absent")
    prior = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else None
    previous_entries = prior["entries"] if prior else []
    previous_by_path = {entry["original"]: entry for entry in previous_entries}
    files = []
    already_archived = []
    for path in candidates:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        prior_entry = previous_by_path.get(relative)
        if prior_entry is None:
            files.append(path)
        elif _sha(path.read_bytes()) == prior_entry["sha256"]:
            already_archived.append((path, prior_entry))
        else:
            raise RuntimeError(f"Archived path now has different bytes: {path}")
    if not files:
        if prior:
            with zipfile.ZipFile(ARCHIVE) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("Archive CRC validation failed")
                for entry in prior["entries"]:
                    if _sha(archive.read(entry["member"])) != entry["sha256"]:
                        raise RuntimeError(f"Archive SHA validation failed: {entry['original']}")
            current_name = str(ARCHIVE.relative_to(ROOT)).replace("\\", "/")
            if prior["archive"] != current_name:
                prior["archive"] = current_name
                with tempfile.NamedTemporaryFile(dir=ARCHIVE.parent, prefix=".notebook_history.", suffix=".zip", delete=False) as handle:
                    temporary = Path(handle.name)
                try:
                    with zipfile.ZipFile(ARCHIVE) as old_archive, zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as new_archive:
                        for entry in prior["entries"]:
                            new_archive.writestr(entry["member"], old_archive.read(entry["member"]))
                        new_archive.writestr("manifest.json", json.dumps(prior, indent=2, ensure_ascii=False))
                    with zipfile.ZipFile(temporary) as archive:
                        if archive.testzip() is not None:
                            raise RuntimeError("Relocated archive CRC validation failed")
                        for entry in prior["entries"]:
                            if _sha(archive.read(entry["member"])) != entry["sha256"]:
                                raise RuntimeError(f"Relocated archive SHA validation failed: {entry['original']}")
                    os.replace(temporary, ARCHIVE)
                    _atomic_bytes(INDEX, json.dumps(prior, indent=2, ensure_ascii=False).encode("utf-8"))
                finally:
                    temporary.unlink(missing_ok=True)
            for path, entry in already_archived:
                _remove_verified(path, entry)
            return prior
        raise RuntimeError("No historical notebook files found; archive cannot be verified")
    entries = []
    for path in files:
        data = path.read_bytes()
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        entries.append({"original": relative, "member": f"history/{relative}", "sha256": _sha(data), "bytes": len(data), "kind": "run_receipt" if path.name.endswith(".run.json") else "notebook"})
    if prior:
        with zipfile.ZipFile(ARCHIVE) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Prior archive CRC validation failed")
            for entry in previous_entries:
                if _sha(archive.read(entry["member"])) != entry["sha256"]:
                    raise RuntimeError(f"Prior archive SHA validation failed: {entry['original']}")
    manifest = {"schema_version": 1, "archive": str(ARCHIVE.relative_to(ROOT)).replace("\\", "/"), "entries": [*previous_entries, *entries], "diagnostic_migrations": prior["diagnostic_migrations"] if prior else []}
    if not prior:
        manifest["diagnostic_migrations"] = _migrate_diagnostics()
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=ARCHIVE.parent, prefix=".notebook_history.", suffix=".zip", delete=False) as handle:
        temp = Path(handle.name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            if prior:
                with zipfile.ZipFile(ARCHIVE) as old_archive:
                    for entry in previous_entries:
                        archive.writestr(entry["member"], old_archive.read(entry["member"]))
            for path, entry in zip(files, entries):
                archive.write(path, entry["member"])
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        with zipfile.ZipFile(temp) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Archive CRC validation failed")
            for entry in manifest["entries"]:
                if _sha(archive.read(entry["member"])) != entry["sha256"]:
                    raise RuntimeError(f"Archive SHA validation failed: {entry['original']}")
        # The external index records the same verified entries as the archive.
        os.replace(temp, ARCHIVE)
        _atomic_bytes(INDEX, json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"))
        for path, entry in [*zip(files, entries), *already_archived]:
            _remove_verified(path, entry)
        return manifest
    finally:
        temp.unlink(missing_ok=True)


if __name__ == "__main__":
    result = consolidate()
    print(f"Archived {len(result['entries'])} historical files to {ARCHIVE}")
    print(f"Migrated output into {len(result['diagnostic_migrations'])} canonical diagnostic notebooks")
    print(f"Index: {INDEX}")
