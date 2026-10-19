"""CLI for the first local P1 evidence audit (exit 2 means pending gates)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.scripts.tib_model_benchmark_contract import comparison_contract, load_registry
from experiments.scripts.tib_model_benchmark_snapshot import inspect_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New output directory; existing evidence is never overwritten")
    args = parser.parse_args()
    snapshot_path, output_path = args.snapshot.resolve(), args.output.resolve()
    if output_path == snapshot_path or snapshot_path in output_path.parents:
        parser.error("Output must be outside the immutable snapshot directory")
    if args.output.exists():
        parser.error("Output exists; select a new audit directory to preserve evidence")
    registry = load_registry()
    manifest, rights = inspect_snapshot(args.snapshot)
    # Inspect inputs first; an error cannot produce a misleading partial manifest.
    args.output.mkdir(parents=True)
    for name, value in (("dataset_manifest.json", manifest), ("rights_ledger.json", rights),
                        ("comparison_contract.json", comparison_contract(registry))):
        (args.output / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    # Last-file marker distinguishes a complete audit export from an interrupted one.
    receipt = {"state": "audit_unsealed", "export_complete": True, "files": {}}
    for path in sorted(args.output.glob("*.json")):
        receipt["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt["tool_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in Path(__file__).parent.glob("tib_model_benchmark_*.py")
    }
    (args.output / "audit_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"g1_status": manifest["g1_status"],
                      "observed_counts": manifest["observed_counts"],
                      "blocking_reasons": manifest["blocking_reasons"],
                      "output": str(args.output.resolve())}, indent=2))
    return 2 if manifest["g1_status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
