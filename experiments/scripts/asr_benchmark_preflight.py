"""Read-only dependency, model-cache, CUDA and disk preflight for A0-A5."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import re
import shutil
from pathlib import Path

from experiments.evaluation.asr_candidate_adapters import registered_asr_candidates

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = PROJECT_ROOT / "experiments/registry/candidates.yaml"


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _hub_cache_dirs() -> list[Path]:
    candidates = []
    for key in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "TRANSFORMERS_CACHE"):
        if os.environ.get(key):
            candidates.append(Path(os.environ[key]).expanduser())
    if os.environ.get("HF_HOME"):
        candidates.append(Path(os.environ["HF_HOME"]).expanduser() / "hub")
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        candidates.append(Path(HF_HUB_CACHE))
    except Exception:
        pass
    candidates.append(Path.home() / ".cache/huggingface/hub")
    result = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in result:
            result.append(resolved)
    return result


def _snapshot(repo: str, revision: str | None, hubs: list[Path]) -> dict:
    folder_name = "models--" + repo.replace("/", "--")
    for hub in hubs:
        snapshot = hub / folder_name / "snapshots" / str(revision)
        if snapshot.is_dir():
            return {"repo": repo, "revision": revision, "cached": True,
                    "snapshot_path": str(snapshot)}
    return {"repo": repo, "revision": revision, "cached": False, "snapshot_path": None,
            "searched_cache_roots": [str(path) for path in hubs]}


def _locked_version(package: str) -> str | None:
    lock_path = PROJECT_ROOT / "requirements.lock.txt"
    pattern = re.compile(rf"(?<![A-Za-z0-9_.-]){re.escape(package)}==([^\s\\]+)", re.IGNORECASE)
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).rstrip(",")
    return None


def inspect_environment() -> dict:
    hubs = _hub_cache_dirs()
    candidates = registered_asr_candidates(REGISTRY)
    candidate_rows = []
    for candidate in candidates:
        key = candidate["id"].split(".", 1)[1]
        kwargs = candidate.get("model_kwargs", {})
        suffix = key[:2]
        if suffix in {"A0", "A1", "A3"}:
            deps = ["faster-whisper"]
            model = _snapshot(kwargs["model_repo"], kwargs.get("revision"), hubs)
        elif suffix == "A2":
            deps = ["transformers", "torch"]
            model = _snapshot(kwargs["model_name"], kwargs.get("revision"), hubs)
            processor = _snapshot(kwargs["model_name"], kwargs.get("processor_revision"), hubs)
            model["processor_snapshot"] = processor
            model["cached"] = bool(
                model["cached"] and processor["cached"]
                and (Path(processor["snapshot_path"]) / "preprocessor_config.json").is_file()
            )
        elif suffix == "A4":
            deps = ["whisperx", "torchaudio", "faster-whisper"]
            model = _snapshot(kwargs["model_repo"], kwargs.get("revision"), hubs)
        else:
            deps = ["deepfilternet", "faster-whisper", "torch"]
            decoder = _snapshot("Systran/faster-whisper-small", kwargs.get("decoder_revision"), hubs)
            model = {"repo": "registered-local-directory", "revision": kwargs.get("decoder_revision"),
                     "cached": (PROJECT_ROOT / str(kwargs.get("model_dir", ""))).is_dir()
                               and decoder["cached"],
                     "snapshot_path": str(PROJECT_ROOT / str(kwargs.get("model_dir", ""))),
                     "decoder_snapshot": decoder}
        missing = [name for name in deps if _version(name) is None]
        version_mismatches = []
        for name in deps:
            installed, locked = _version(name), _locked_version(name)
            if installed and locked and installed.split("+", 1)[0] != locked.split("+", 1)[0]:
                version_mismatches.append({"package": name, "installed": installed, "locked": locked})
        candidate_rows.append({"candidate": candidate["id"], "dependencies":
                               {name: _version(name) for name in deps},
                               "missing_dependencies": missing,
                               "package_version_mismatches": version_mismatches,
                               "model": model,
                               "ready": not missing and not version_mismatches and model["cached"]})
    gpu = {"available": False}
    try:
        import torch
        gpu["available"] = torch.cuda.is_available()
        if gpu["available"]:
            gpu["name"] = torch.cuda.get_device_name(0)
            free, total = torch.cuda.mem_get_info(0)
            gpu.update(vram_free_bytes=free, vram_total_bytes=total)
    except Exception as exc:
        gpu["error"] = f"{type(exc).__name__}: {exc}"
    for candidate, row in zip(candidates, candidate_rows):
        blockers = []
        candidate_id = candidate["id"].split(".", 1)[-1]
        requires_cuda = candidate["model_kwargs"].get("device") == "cuda" or candidate_id == "A5_DeepFilterNet"
        if requires_cuda and not gpu.get("available"):
            blockers.append("cuda_unavailable")
        warnings = []
        required_vram = int(candidate.get("compute_budget", {}).get("max_vram_mb", 0))
        if required_vram and gpu.get("available") and gpu.get("vram_free_bytes", 0) < required_vram * 1024**2:
            warnings.append(f"vram_budget_exceeds_free:{required_vram}MiB")
        row["resource_blockers"] = blockers
        row["resource_warnings"] = warnings
        row["ready"] = bool(row["ready"] and not blockers)
    disk = shutil.disk_usage(PROJECT_ROOT)
    return {"candidate_count": len(candidate_rows), "candidates": candidate_rows,
            "cuda": gpu, "disk": {"path": str(PROJECT_ROOT), "free_bytes": disk.free,
                                     "total_bytes": disk.total},
            "all_candidates_ready": all(row["ready"] for row in candidate_rows),
            "inference_started": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=PROJECT_ROOT / "experiments/outputs/asr_a0_a5_benchmark_261003/preflight.json")
    args = parser.parse_args(argv)
    result = inspect_environment()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["all_candidates_ready"] and result["cuda"].get("available") else 2


if __name__ == "__main__":
    raise SystemExit(main())
