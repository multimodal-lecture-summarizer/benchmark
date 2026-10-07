"""Measured provenance and resource gates for local dataset qualification."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import shutil
import wave
from pathlib import Path


def content_hash(paths: list[Path], root: Path) -> str:
    """Bind names and contents, so renames and edits invalidate the identity."""
    records = [{"path": p.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(set(paths))]
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def provenance(root: Path, driver: Path, dataset_id: str, *,
               artifact_root: Path | None = None, notebook_id: str | None = None) -> dict[str, str]:
    # Include local runner dependencies, validators and schemas, not only the entrypoint.
    sources = [driver, * (root / "experiments/scripts").glob("*.py"),
               * (root / "experiments/evaluation").glob("*.py"),
               * (root / "experiments/registry").rglob("*.py")]
    config = [root / f"experiments/registry/datasets/{dataset_id}_d2.yaml",
              * (root / "experiments/registry").rglob("*.json"),
              * (root / "experiments/registry").rglob("*.yaml"),
              * (root / "experiments/registry").rglob("*.yml"),
              * (root / "experiments/evaluation").glob("*.json")]
    locks = [p for p in (root / "requirements.lock.txt", root / "requirements.freeze.txt")
             if p.is_file()]
    installed = sorted((d.metadata["Name"], d.version)
                       for d in importlib.metadata.distributions() if d.metadata["Name"])
    dependencies = {"lock_contents_sha256": content_hash(locks, root),
                    "python": platform.python_version(), "installed": installed}
    if artifact_root is not None:
        dependencies["upstream_evidence_sha256"] = upstream_evidence_hash(artifact_root, notebook_id)
    return {"source_sha256": content_hash(sources, root),
            "config_sha256": content_hash(config, root),
            "dependency_state_sha256": hashlib.sha256(
                json.dumps(dependencies, sort_keys=True).encode()).hexdigest()}


def upstream_evidence_hash(artifact_root: Path, notebook_id: str | None) -> str:
    """Bind validated upstream receipts and the actual payload bytes they name."""
    upstream = {
        "00a_environment_preflight": [],
        "00b_dataset_feasibility": ["environment.profile", "environment.preflight_receipt"],
        "00c_dataset_eda_and_freeze": ["environment.profile", "environment.preflight_receipt",
                                       "dataset.feasibility_receipts", "dataset.acquisition_inventory",
                                       "dataset.d2_registry"],
    }
    if notebook_id not in upstream:
        raise ValueError(f"unsupported dataset provenance stage: {notebook_id}")
    root = artifact_root.resolve()
    paths = []
    for artifact_id in upstream[notebook_id]:
        receipt_path = root / "official/full" / f"{artifact_id}.receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload_path = (root / receipt["payload_path"]).resolve()
        payload_path.relative_to(root)
        if receipt.get("artifact_id") != artifact_id:
            raise ValueError(f"upstream receipt identity mismatch: {artifact_id}")
        if hashlib.sha256(payload_path.read_bytes()).hexdigest() != receipt.get("sha256"):
            raise ValueError(f"upstream payload checksum mismatch: {artifact_id}")
        paths.extend([receipt_path, payload_path])
    return content_hash(paths, root)


def disk_preflight(roots: list[Path], predicted_peak_bytes: int) -> dict:
    """Require the configured peak to fit without consuming the existing reserve."""
    if predicted_peak_bytes < 0:
        raise ValueError("predicted peak must be nonnegative")
    disks = []
    for root in roots:
        existing = root.resolve()
        while not existing.exists():
            existing = existing.parent
        usage = shutil.disk_usage(existing)
        reserve = max(100 * 1024**3, int(usage.total * 0.15))
        disks.append({"path": str(root), "total_bytes": usage.total,
                      "free_bytes": usage.free, "reserve_bytes": reserve,
                      "predicted_peak_bytes": predicted_peak_bytes,
                      "remaining_after_peak_bytes": usage.free - predicted_peak_bytes,
                      "reserve_gate_passed": usage.free - predicted_peak_bytes >= reserve})
    passed = bool(disks) and all(d["reserve_gate_passed"] for d in disks)
    return {"disk": disks, "disk_gate_passed": passed,
            "status": "passed" if passed else "blocked_disk_reserve",
            "scope": "local_dataset_decode_and_artifact_write"}


def decode_audio(path: Path) -> dict:
    """Read every sample in bounded blocks and reject truncated payloads."""
    import soundfile

    # libsndfile may clamp its frame count to available bytes for truncated WAVs.
    # The independent PCM container declaration must match the decoded samples.
    with wave.open(str(path), "rb") as container:
        expected = container.getnframes()
    with soundfile.SoundFile(path) as audio:
        count = sum(len(block) for block in audio.blocks(blocksize=65536))
        if count != expected or count <= 0:
            raise ValueError(f"incomplete audio decode: {count}/{expected} frames")
        return {"frames": count, "sample_rate_hz": audio.samplerate,
                "channels": audio.channels, "duration_sec": count / audio.samplerate}
