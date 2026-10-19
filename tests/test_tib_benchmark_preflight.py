"""Local inventory does not claim T4 feasibility or inspect credentials."""
from experiments.scripts.tib_benchmark_preflight import inventory


def test_inventory_reports_only_scoped_aggregate_weights(tmp_path, monkeypatch):
    root = tmp_path / "research-data"; root.mkdir()
    (root / "model.safetensors").write_bytes(b"123")
    (root / "token.json").write_text("secret fixture")
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = inventory(tmp_path)
    assert result["workspace_weight_inventory"]["bytes"] == 3
    assert result["workspace_weight_inventory"]["file_count"] == 1
    assert not result["T4_feasibility_verified"] and not result["inference_executed"]
    assert result["remote_compute_quota"] is None
    assert "secret" not in str(result)
