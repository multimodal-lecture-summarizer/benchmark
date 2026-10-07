"""Guard against synthetic YTSeg manifests from the unfinished fetcher."""

import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "benchmarks" / "scripts" / "fetch_ytseg_subset.py"


@pytest.mark.parametrize("dry_run,expected_code", [(True, 0), (False, 2)])
def test_unimplemented_fetch_never_creates_manifest_or_cache(tmp_path, dry_run, expected_code):
    manifest = tmp_path / "new" / "manifest.json"
    cache = tmp_path / "new" / "cache"
    command = [sys.executable, str(SCRIPT), "--manifest", str(manifest), "--cache-dir", str(cache)]
    if dry_run:
        command.append("--dry-run")

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    assert result.returncode == expected_code
    assert "[BLOCKED]" in result.stdout
    assert not manifest.exists()
    assert not cache.exists()
    assert not manifest.parent.exists()


def test_existing_manifest_is_not_modified(tmp_path):
    manifest = tmp_path / "manifest.json"
    original = b'{"items":[{"item_id":"existing"}]}'
    manifest.write_bytes(original)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert manifest.read_bytes() == original
