"""Prepare clean local cohorts and EDA in a fresh, independently verifiable bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.scripts.benchmark_artifacts import sha256_file
from experiments.scripts.dataset_freeze_evidence import disk_preflight, provenance
from experiments.scripts.dataset_readiness_screening import default_protocol, screen_dataset


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)


def run(root: Path, destination: Path) -> dict:
    from experiments.scripts.dataset_readiness_selection import select_inputs, extract_inputs
    from experiments.scripts.dataset_readiness_figures import render_readiness_figures

    if destination.exists() and any(destination.iterdir()):
        raise ValueError("fresh empty destination required")
    destination.mkdir(parents=True, exist_ok=True)
    protocol = default_protocol()
    # Bound exported audio plus diagnostic plots without reading media first.
    preflight = disk_preflight([root / "experiments/datasets", destination], 2 * 1024**3)
    write_json(destination / "preflight.json", preflight)
    write_json(destination / "protocol.json", protocol)
    write_json(destination / "provenance.json", provenance(root, Path(__file__), "tedlium3"))
    if not preflight["disk_gate_passed"]:
        raise RuntimeError("disk reserve gate failed before selection")
    selection = select_inputs(root, protocol)
    write_json(destination / "selection.json", selection)
    selection_sha = sha256_file(destination / "selection.json")
    print("Protocol and selected IDs saved before selected-media decoding", flush=True)
    extracted = extract_inputs(root, destination, selection)
    if sha256_file(destination / "selection.json") != selection_sha:
        raise ValueError("selection changed during extraction")
    write_json(destination / "extraction.json", extracted)
    summary = {}
    for dataset_id, dataset in extracted["datasets"].items():
        records, audit = screen_dataset(dataset_id, dataset["selected"], dataset.get("historical", []), protocol)
        if dataset.get("issues"):
            audit["input_issues"] = dataset["issues"]
            audit["blockers"].append("input inventory issues require resolution")
            audit["status"] = "blocked"
        directory = destination / dataset_id
        write_json(directory / "units.json", records)
        write_json(directory / "screening.json", audit)
        retained = [r for r in records if r["decision"] == "keep"]
        write_json(directory / "split-manifest.json", {
            "dataset_id": dataset_id, "status": audit["status"],
            "protocol_sha256": sha256_file(destination / "protocol.json"),
            "selection_sha256": selection_sha, "units_sha256": sha256_file(directory / "units.json"),
            "screening_sha256": sha256_file(directory / "screening.json"),
            "scientific_selection_eligible": False,
            "scope": "preparation evidence screened under protocol; official eligibility requires separate qualification",
            "retained_unit_ids": [r["unit_id"] for r in retained],
            "blockers": audit["blockers"],
        })
        figures = render_readiness_figures(destination, dataset_id, records, audit, protocol)
        write_json(directory / "figure-manifest.json", figures)
        summary[dataset_id] = {k: v for k, v in audit.items() if k not in ("pairs", "failures")}
        summary[dataset_id]["pair_count"] = len(audit["pairs"])
        summary[dataset_id]["failure_count"] = len(audit["failures"])
        summary[dataset_id]["figures"] = len(figures)
        print(json.dumps(summary[dataset_id], ensure_ascii=False), flush=True)
    write_json(destination / "summary.json", summary)
    # The receipt binds protocol, selections, extraction, decisions and all figures.
    files = [{"path": p.relative_to(destination).as_posix(), "sha256": sha256_file(p)}
             for p in sorted(destination.rglob("*")) if p.is_file()]
    write_json(destination / "bundle-receipt.json", {"version": 1, "files": files,
               "scope": "dataset readiness preparation; not an official benchmark receipt"})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = run(root, args.output.resolve())
    return 3 if any(r["status"] == "blocked" for r in result.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
