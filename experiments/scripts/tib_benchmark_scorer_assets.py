"""Acquire only pinned official scorer assets with byte/hash receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import requests

MODELS = {
    "bert": ("FacebookAI/xlm-roberta-large", "c23d21b0620b635a76227c604d44e43a9f0ee389"),
    "sentence": ("sentence-transformers/paraphrase-multilingual-mpnet-base-v2", "4328cf26390c98c5e3c738b4460a05b95f4911f5"),
}


def acquire(root, *, inspect_only=False):
    session = requests.Session()
    catalogs, total = {}, 0
    for key, (model, revision) in MODELS.items():
        response = session.get(f"https://huggingface.co/api/models/{model}/revision/{revision}?blobs=true", timeout=45)
        response.raise_for_status()
        catalog = response.json()
        if catalog["sha"] != revision:
            raise ValueError("Official model revision mismatch")
        files = [f for f in catalog["siblings"] if (f["rfilename"].endswith(".json")
                 or f["rfilename"] in {"model.safetensors", "sentencepiece.bpe.model"})
                 and not any(x in f["rfilename"] for x in ("onnx/", "openvino/"))]
        if not any(f["rfilename"] == "model.safetensors" for f in files):
            raise ValueError("Pinned safetensors weights absent")
        catalogs[key] = files
        total += sum(f["size"] for f in files)
        print(json.dumps({"model": model, "revision": revision, "files": [(f["rfilename"], f["size"]) for f in files]}), flush=True)
    print(json.dumps({"download_bytes": total, "free_bytes": shutil.disk_usage(root.parent if root.parent.exists() else Path.cwd()).free}), flush=True)
    if inspect_only:
        return
    if shutil.disk_usage(Path.cwd()).free < total * 2:
        raise ValueError("Insufficient working disk headroom")
    for key, files in catalogs.items():
        model, revision = MODELS[key]
        target = root / key
        target.mkdir(parents=True, exist_ok=True)
        receipt = {"model": model, "revision": revision, "files": {}, "official_files": {}}
        if (target / "asset_manifest.json").exists():
            raise ValueError("Existing asset manifest requires explicit readback, not replacement")
        for record in files:
            name = record["rfilename"]
            path = target / name
            if path.resolve().is_relative_to(target.resolve()) is False:
                raise ValueError("Unsafe remote filename")
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            if not path.exists():
                partial = path.with_name(path.name + ".partial")
                with session.get(f"https://huggingface.co/{model}/resolve/{revision}/{name}", stream=True, timeout=(30,180)) as r:
                    r.raise_for_status()
                    with partial.open("xb") as handle:
                        for block in r.iter_content(4 * 1024 * 1024):
                            handle.write(block)
                            digest.update(block)
                partial.rename(path)
            else:
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                        digest.update(block)
            actual = digest.hexdigest()
            expected = record.get("lfs", {}).get("sha256")
            if path.stat().st_size != record["size"] or (expected and actual != expected):
                raise ValueError(f"Official asset byte/hash mismatch: {name}")
            receipt["files"][name] = actual
            receipt["official_files"][name] = {"bytes": record["size"], "lfs_sha256": expected, "git_blob_id": record.get("blobId")}
            print(f"Verified {key}/{name}: {path.stat().st_size} bytes", flush=True)
        with (target / "asset_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--inspect-only", action="store_true")
    args = parser.parse_args()
    acquire(args.root, inspect_only=args.inspect_only)
