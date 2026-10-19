"""Read-only local inventory; never a substitute for actual T4 inference receipts."""
import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def inventory(workspace):
    workspace = Path(workspace).resolve()
    packages = {}
    for name in ("torch", "transformers", "accelerate", "bitsandbytes", "rouge-score", "bert-score", "sentence-transformers"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    gpu = {"query": "unavailable", "devices": []}
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=15, check=False)
            gpu["query"] = "pass" if result.returncode == 0 else "failed"
            if result.returncode == 0:
                for row in result.stdout.strip().splitlines():
                    name, memory, driver = [value.strip() for value in row.split(",")]
                    gpu["devices"].append({"name": name, "memory_MiB": int(memory), "driver": driver})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            gpu["query"] = "failed"
    # Inspect aggregate file sizes only; no environment variables, credentials or filenames exported.
    cache = workspace / "research-data"
    weights = {"scope": "workspace research-data only; external caches unverified", "file_count": 0, "bytes": 0}
    if cache.is_dir():
        for suffix in ("*.safetensors", "pytorch_model*.bin"):
            for path in cache.rglob(suffix):
                if path.is_file():
                    weights["file_count"] += 1
                    weights["bytes"] += path.stat().st_size
    disk = shutil.disk_usage(workspace)
    return {"state": "inventory_only_no_inference", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": sys.version.split()[0], "packages": packages, "gpu": gpu,
            "workspace_free_disk_bytes": disk.free, "workspace_weight_inventory": weights,
            "T4_feasibility_verified": False, "inference_executed": False,
            "remote_compute_quota": None, "persistent_store_authorization": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.workspace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
