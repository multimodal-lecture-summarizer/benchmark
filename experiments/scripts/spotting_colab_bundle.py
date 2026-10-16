"""Build a self-contained, hash-bound Colab runner without images or model binaries."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
FREEZE = "experiments/registry/datasets/iiit-cvid-spotting-test-261014-freeze.json"
DEFAULT = ROOT / "experiments/outputs/iiit-cvid-spotting-colab-t4-inputs.zip"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root=ROOT):
    root = Path(root)
    files = set((root / "experiments/scripts").glob("*.py"))
    for name in ("experiments/__init__.py", "experiments/scripts/__init__.py"):
        if (root / name).exists():
            files.add(root / name)
    registry = root / "experiments/registry/datasets"
    files.update(registry.glob("iiit-cvid*.json"))
    files.update(registry.glob("iiit-cvid*.txt"))
    files.update(registry.glob("*spotting*colab*"))
    for path in (root / "experiments/scripts").glob("*spotting*colab*.txt"):
        files.add(path)
    freeze = json.loads((root / FREEZE).read_text(encoding="utf-8"))
    for entry in freeze["artifacts"]:
        path = root / entry["path"]
        if sha(path) != entry["sha256"]:
            raise ValueError(f"frozen artifact changed: {entry['path']}")
        files.add(path)
    required = ("run_spotting_colab.py", "spotting_colab_candidates.py",
                "spotting_colab_environments.py", "spotting_colab_adapters.py", "spotting_colab_worker.py")
    for name in required:
        path = root / "experiments/scripts" / name
        if not path.is_file():
            raise FileNotFoundError(path)
    candidate_registry = registry / "iiit-cvid-spotting-colab-t4-candidates-261015.json"
    if not candidate_registry.is_file():
        raise FileNotFoundError(candidate_registry)
    return sorted(files)


def build(destination=DEFAULT, root=ROOT):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    files = collect(root)
    manifest = {"schema": "cvid_colab_portable_bundle_v1", "test_frames": 1754,
                "test_objects": 40063, "contains_images": False,
                "contains_model_weights": False,
                "files": [{"path": p.relative_to(root).as_posix(),
                           "sha256": sha(p), "bytes": p.stat().st_size} for p in files]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
        archive.writestr("bundle-manifest.json", json.dumps(manifest, indent=2) + "\n")
    verify(temporary)
    temporary.replace(destination)
    digest = sha(destination)
    destination.with_suffix(".zip.sha256").write_text(digest + "  " + destination.name + "\n")
    return {"path": str(destination), "sha256": digest, "files": len(files),
            "bytes": destination.stat().st_size, "test_frames": 1754, "test_objects": 40063}


def verify(path):
    """Validate exact members before extraction, including duplicates and traversal."""
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate bundle members")
        for name in names:
            parts = PurePosixPath(name)
            if parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
                raise ValueError("unsafe bundle member")
        manifest = json.loads(archive.read("bundle-manifest.json"))
        entries = manifest["files"]
        expected = [entry["path"] for entry in entries]
        if len(expected) != len(set(expected)) or set(names) != set(expected) | {"bundle-manifest.json"}:
            raise ValueError("bundle membership mismatch")
        for entry in entries:
            data = archive.read(entry["path"])
            if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError("bundle content mismatch: " + entry["path"])
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
