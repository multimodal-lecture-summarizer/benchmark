"""Preflight pinned architecture candidates and their isolated Python workers."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
from pathlib import Path

from experiments.evaluation.asr_architecture_adapters import REGISTRY, registered_asr_candidates

ROOT = Path(__file__).resolve().parents[2]
def _pkg_version(python: str, package: str) -> str | None:
    import subprocess
    code = ("import importlib.metadata as m,sys; "
            "print(m.version(sys.argv[1]))")
    distribution = package.partition("[")[0]
    result = subprocess.run([python, "-c", code, distribution], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _snapshot(repo: str, revision: str, cache: Path, framework: str = "") -> dict:
    path = cache / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
    required = {"transformers_ctc": "pytorch_model.bin",
                "nemo_ctc": "*.nemo", "nemo_rnnt": "*.nemo"}.get(framework)
    checkpoint_present = (any(item.is_file() for item in path.glob(required))
                          if required else path.is_dir())
    return {"repo": repo, "revision": revision, "cached": checkpoint_present,
            "required_checkpoint": required,
            "snapshot_path": str(path) if path.is_dir() else None}


def inspect_environment(drive_root: Path | None = None) -> dict:
    lock_path = ROOT / "experiments/registry/asr_architecture_environment.lock.yaml"
    try:
        import yaml
        package_lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))["groups"]
    except Exception as exc:
        raise RuntimeError(f"architecture dependency lock is invalid: {exc}") from exc
    cache = Path(os.environ.get("HF_HUB_CACHE") or
                 (Path(os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub"))
    results = []
    for candidate in registered_asr_candidates():
        group = candidate["package_group"]
        python = os.environ.get(f"ASR_ARCH_PYTHON_{group.upper()}") or os.environ.get("ASR_ARCH_PYTHON")
        if not python:
            python = shutil.which("python") or "python"
        missing = []
        mismatches = []
        versions = {}
        # Use every key in the lock so no declared pin can silently escape preflight.
        for package in package_lock[group]:
            version = _pkg_version(python, package)
            versions[package] = version
            if version is None:
                missing.append(package)
            else:
                expected = str(package_lock[group][package])
                if version.split("+", 1)[0] != expected:
                    mismatches.append({"package": package, "installed": version,
                                       "expected": expected})
        pip_check = subprocess.run([python, "-m", "pip", "check"],
                                   capture_output=True, text=True)
        snapshot = _snapshot(candidate["model_repo"], candidate["revision"], cache,
                             candidate["framework"])
        results.append({"candidate": candidate["id"], "family": candidate["family"],
                        "python": python, "dependencies": versions,
                        "missing_dependencies": missing,
                        "package_version_mismatches": mismatches,
                        "pip_check": {"passed": pip_check.returncode == 0,
                                      "output": (pip_check.stdout + pip_check.stderr).strip()},
                        "model": snapshot,
                        "resource_blockers": [],
                        "ready": not missing and not mismatches and pip_check.returncode == 0
                                 and snapshot["cached"]})
    cuda = {"available": False}
    try:
        import torch
        cuda["available"] = bool(torch.cuda.is_available())
        if cuda["available"]:
            cuda["name"] = torch.cuda.get_device_name(0)
            cuda["compute_capability"] = list(torch.cuda.get_device_capability(0))
            cuda["vram_total_bytes"] = int(torch.cuda.get_device_properties(0).total_memory)
    except Exception as exc:
        cuda["error"] = f"{type(exc).__name__}: {exc}"
    if not cuda["available"]:
        for row in results:
            row["ready"] = False
            row["resource_blockers"].append("cuda_unavailable")
    elif "t4" not in str(cuda.get("name", "")).lower():
        for row in results:
            row["ready"] = False
            row["resource_blockers"].append("expected_colab_t4_gpu")
    disk_space = {"local_free_bytes": shutil.disk_usage(ROOT).free}
    if drive_root is not None:
        try:
            disk_space["drive_reported_free_bytes"] = shutil.disk_usage(drive_root).free
        except OSError as exc:
            disk_space["drive_error"] = f"{type(exc).__name__}: {exc}"
    if disk_space["local_free_bytes"] < 12 * 1024**3:
        for row in results:
            row["ready"] = False
            row["resource_blockers"].append("less_than_12_gib_local_free_disk")
    if ("drive_reported_free_bytes" in disk_space
            and disk_space["drive_reported_free_bytes"] < 12 * 1024**3):
        for row in results:
            row["ready"] = False
            row["resource_blockers"].append("less_than_12_gib_drive_reported_free_space")
    if "drive_error" in disk_space:
        for row in results:
            row["ready"] = False
            row["resource_blockers"].append("drive_free_space_unavailable")
    return {"candidate_count": len(results), "candidates": results, "cuda": cuda,
            "disk_space": disk_space,
            "all_candidates_ready": all(row["ready"] for row in results),
            "inference_started": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--drive-root", type=Path)
    args = parser.parse_args(argv)
    result = inspect_environment(args.drive_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["all_candidates_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
