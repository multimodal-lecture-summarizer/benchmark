"""Contract checks for the on-demand, full-profile notebook workflow."""

from copy import deepcopy

import pytest
import yaml

from benchmarks.scripts.execute_all_notebooks import (
    ManifestError,
    build_plan,
    main,
    select_entries,
)
from experiments.registry.contract_validator import validate_notebook_manifest


def _manifest():
    return {
        "schema_version": 1,
        "manifest_status": "on_demand",
        "official_default_profile": "full",
        "allowed_profiles": ["full"],
        "allowed_network_policies": ["none", "bounded_acquisition", "registry_controlled"],
        "notebooks": [],
    }


def test_empty_on_demand_manifest_is_valid_and_listable(tmp_path, capsys):
    manifest = _manifest()
    assert validate_notebook_manifest(manifest) == []
    assert select_entries(manifest, profile="full") == []
    path = tmp_path / "notebook_manifest.yaml"
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    assert main(["--manifest", str(path), "--list"]) == 0
    assert capsys.readouterr().out == ""
    assert main(["--manifest", str(path)]) == 2
    assert "No notebook is registered" in capsys.readouterr().out


def test_smoke_profile_is_rejected_by_contract_and_cli(capsys):
    manifest = _manifest()
    invalid = deepcopy(manifest)
    invalid["allowed_profiles"] = ["smoke", "full"]
    assert any("allowed_profiles must be exactly" in error for error in validate_notebook_manifest(invalid))
    with pytest.raises(ManifestError, match="smoke profile was retired"):
        select_entries(manifest, profile="smoke")
    with pytest.raises(ManifestError, match="smoke profile was retired"):
        build_plan([], "smoke", [])
    assert main(["--profile", "smoke", "--list"]) == 2
    assert "smoke profile was retired" in capsys.readouterr().out
