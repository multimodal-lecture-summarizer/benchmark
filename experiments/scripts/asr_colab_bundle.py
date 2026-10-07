"""Build and verify a portable ASR A0-A5 Colab input bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "experiments/outputs/asr_a0_a5_benchmark_261003_metadata_screen/diagnostic/full"
DEFAULT_BUNDLE = ROOT / "experiments/outputs/asr_architecture_colab_t4_inputs.zip"
FROZEN_NAMES = (
    "dataset.endpoint_matrix.receipt.json",
    "dataset.frozen_manifest.receipt.json",
    "dataset.registry.receipt.json",
    "payloads/dataset.endpoint_matrix.json",
    "payloads/dataset.frozen_manifest.json",
    "payloads/dataset.registry.json",
    "runs/00c_dataset_eda_and_freeze.run.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_inputs(candidate_set: str = "architecture") -> list[Path]:
    """Include Python sources and only the frozen cohort's canonical audio."""
    sources = set()
    for directory in (ROOT / "benchmarks", ROOT / "experiments"):
        sources.update(path for path in directory.rglob("*.py")
                       if not any(part in {"outputs", "datasets", "__pycache__", "scratch"}
                                  for part in path.relative_to(ROOT).parts))
    if candidate_set == "architecture":
        sources.update(ROOT / name for name in (
            "experiments/registry/asr_architecture_candidates.yaml",
            "experiments/registry/asr_architecture_environment.lock.yaml",
            "experiments/notebooks/asr_architecture_colab_t4.ipynb",
            "experiments/notebooks/notebook_manifest.yaml",
        ))
    else:
        raise ValueError(f"unknown ASR candidate set: {candidate_set}")
    sources.update(FREEZE / name for name in FROZEN_NAMES)
    frozen_path = FREEZE / "payloads/dataset.frozen_manifest.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))["records"][0]
    units = frozen["unit_records"]
    if len(units) != 1662 or {row["split"] for row in units} != {"validation", "final_test"}:
        raise RuntimeError("expected exactly 1,662 frozen evaluation units across two splits")
    for row in units:
        relative = Path(row["canonical_audio_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe canonical audio path: {relative}")
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        audio = np.load(path, mmap_mode="r", allow_pickle=False)
        if audio.dtype != np.dtype("float32") or audio.ndim != 1 or not audio.size:
            raise RuntimeError(f"invalid canonical audio: {relative}")
        actual = hashlib.sha256(np.asarray(audio, dtype="<f4").tobytes()).hexdigest()
        if actual != row["decoded_audio_sha256"]:
            raise RuntimeError(f"canonical audio hash mismatch: {relative}")
        sources.add(path)
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing bundle inputs: " + ", ".join(sorted(missing)))
    return sorted(sources)


def build(destination: Path, candidate_set: str = "architecture") -> dict:
    files = collect_inputs(candidate_set)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination in files:
        raise ValueError("bundle output cannot be an input")
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=1,
                 allowZip64=True) as archive:
        for index, path in enumerate(files, 1):
            archive.write(path, path.relative_to(ROOT).as_posix())
            if index % 200 == 0 or index == len(files):
                print(f"packed {index}/{len(files)}", flush=True)
    temporary.replace(destination)
    digest = sha256_file(destination)
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        digest + "  " + destination.name + "\n", encoding="ascii")
    return {"bundle": str(destination), "candidate_set": candidate_set,
            "sha256": digest, "files": len(files),
            "bytes": destination.stat().st_size, "evaluation_units": 1662}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-set", choices=("architecture",), default="architecture")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or DEFAULT_BUNDLE
    print(json.dumps(build(output.resolve(), args.candidate_set), indent=2))


if __name__ == "__main__":
    main()
