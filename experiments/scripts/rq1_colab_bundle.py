"""Build a portable input bundle for the RQ1 Colab notebook.

The bundle contains source code, locked D2 inputs, train/validation media,
existing OCR chunks, and pinned PaddleOCR weights. It excludes final-test media.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from experiments.scripts.rq1_learned_features import (
    DEFAULT_OUTPUT, PUBLISHED_MANIFEST, PUBLISHED_RECEIPT,
    development_sources,
)
from experiments.scripts.rq1_train_source_handoff import FREEZE, MATERIALIZATION, REPO, SOURCE, SPLIT


OUTER = REPO.parent
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "venv_paddle_gpu", "node_modules", "__pycache__",
    ".next", ".pytest_cache", "datasets", "notebooks", "official_datasets", "outputs",
    "storage", "cache", "checkpoints", "probes", "target", "dist",
}
EXCLUDED_FILES = {"credentials.json", "token.json", ".env"}


def _project_files() -> set[Path]:
    selected: set[Path] = set()
    for current, dirs, files in os.walk(REPO):
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
        root = Path(current)
        selected.update(root / name for name in files
                        if name not in EXCLUDED_FILES
                        and not (name.startswith(".env.") and name != ".env.example"))
    return selected


def collect_files() -> list[Path]:
    rows = development_sources()
    selected = _project_files()
    selected.update((FREEZE, MATERIALIZATION, SOURCE, SPLIT,
                     PUBLISHED_MANIFEST, PUBLISHED_RECEIPT))
    for row in rows:
        selected.update((Path(row["media_path"]), Path(row["transcript_path"]),
                         Path(row["source_feature_path"])))

    output = DEFAULT_OUTPUT
    # Reuse verified OCR chunks, including the current interrupted unit.
    for row in rows:
        cache = output / "ocr_chunks" / row["unit_id"]
        if cache.is_dir():
            selected.update(path for path in cache.rglob("*") if path.is_file())
    # OCR model weights are frozen by the existing feature receipts.
    paddle_models = REPO / "experiments/outputs/rq1_locked_mixed_20/model_cache/paddleocr"
    selected.update(path for path in paddle_models.rglob("*") if path.is_file())

    missing = [str(path) for path in selected if not path.is_file()]
    if missing:
        raise FileNotFoundError("bundle inputs missing:\n" + "\n".join(sorted(missing)))
    return sorted(selected)


def build(destination: Path) -> dict:
    files = collect_files()
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = sum(path.stat().st_size for path in files)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED, compresslevel=1) as archive:
        for index, path in enumerate(files, 1):
            try:
                relative = path.relative_to(OUTER)
            except ValueError as exc:
                raise ValueError(f"input is outside the portable project root: {path}") from exc
            archive.write(path, relative.as_posix())
            if index % 100 == 0 or index == len(files):
                print(f"packed {index}/{len(files)} files", flush=True)
    return {"bundle": str(destination), "files": len(files),
            "source_bytes": total, "archive_bytes": destination.stat().st_size}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=REPO / "experiments/outputs/rq1_locked_mixed_20/rq1_colab_bundle.zip")
    args = parser.parse_args()
    print(build(args.output.resolve()))


if __name__ == "__main__":
    main()
