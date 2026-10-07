"""Protect historical notebook bytes across interrupted consolidation runs."""

import json
import zipfile

import pytest

from experiments.scripts import consolidate_notebooks as migration


def test_consolidation_resume_does_not_duplicate_archived_files(tmp_path, monkeypatch):
    experiments = tmp_path / "experiments"
    legacy = experiments / "legacy"
    legacy.mkdir(parents=True)
    original = legacy / "old.ipynb"
    payload = b"historical notebook bytes"
    original.write_bytes(payload)
    monkeypatch.setattr(migration, "ROOT", tmp_path)
    monkeypatch.setattr(migration, "EXPERIMENTS", experiments)
    monkeypatch.setattr(migration, "HISTORY_DIRS", (legacy,))
    monkeypatch.setattr(migration, "ARCHIVE", experiments / "notebook_history_20260926.zip")
    monkeypatch.setattr(migration, "INDEX", experiments / "notebook_history_20260926.manifest.json")
    monkeypatch.setattr(migration, "_migrate_diagnostics", lambda: [])

    first = migration.consolidate()
    assert len(first["entries"]) == 1
    assert not original.exists()

    # A crash after writing the archive but before deleting this source file.
    original.write_bytes(payload)
    second = migration.consolidate()
    assert len(second["entries"]) == 1
    assert not original.exists()
    with zipfile.ZipFile(migration.ARCHIVE) as archive:
        assert archive.namelist().count(first["entries"][0]["member"]) == 1
        assert archive.read(first["entries"][0]["member"]) == payload
        assert json.loads(archive.read("manifest.json"))["entries"] == second["entries"]

    original.write_bytes(b"changed since archiving")
    with pytest.raises(RuntimeError, match="different bytes"):
        migration.consolidate()
    assert original.read_bytes() == b"changed since archiving"
