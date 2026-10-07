"""YTSeg subset entry point.

The acquisition and freeze pipeline is not implemented. Keep this command
read-only until real media, released GT, rights, features, and leakage evidence
can be verified per video. In particular, never emit a plausible fake manifest.
"""

import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "benchmarks" / "manifests" / "frozen_manifest_v2.json"
DEFAULT_CACHE = PROJECT_ROOT / "cache" / "feature_store_real"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="YTSeg subset acquisition status (read-only)")
    parser.add_argument("--limit", type=int, default=300, help="Target number of videos")
    parser.add_argument("--over-fetch", type=int, default=500, help="Candidate count before attrition")
    parser.add_argument("--shard", type=str, default=None, help="Reserved shard id, e.g. 0/6")
    parser.add_argument("--resume", action="store_true", help="Reserved for a verified acquisition pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Read-only status check")
    parser.add_argument("--manifest", type=str, default=str(DEFAULT_MANIFEST), help="Future frozen manifest path")
    parser.add_argument("--cache-dir", type=str, default=str(DEFAULT_CACHE), help="Future feature cache path")
    args = parser.parse_args(argv)
    if args.limit <= 0 or args.over_fetch <= 0:
        parser.error("--limit and --over-fetch must be positive")
    return args


def main(argv=None):
    args = parse_args(argv)
    manifest = Path(args.manifest)
    print(
        f"[fetch_ytseg_subset] target={args.limit} candidates={args.over_fetch} "
        f"shard={args.shard} resume={args.resume}"
    )
    if manifest.exists():
        print(f"[status] Manifest path already exists: {manifest}; this command does not verify or modify it.")
    print(
        "[BLOCKED] Genuine per-video rights, media/decode, released chapter GT, "
        "features, split leakage, and freeze are not implemented."
    )
    if args.dry_run:
        print("[dry-run] Read-only status complete; no files or directories were written.")
        return 0
    print("[ERROR] Refusing acquisition and manifest creation until those checks exist.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
