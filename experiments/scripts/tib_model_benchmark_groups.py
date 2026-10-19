"""Full-corpus TIB source grouping; no reference use or model execution."""
from __future__ import annotations

import csv
import hashlib
import json
import time
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import numba
import pandas as pd
import pyarrow
import pyarrow.parquet as pq

from experiments.scripts.tib_model_benchmark_group_core import (
    HASH_KEY, canonical, component_ledger, confirm_pair, digest, fingerprints,
    url_key, words,
)

ROOT = Path(__file__).resolve().parents[2]
REVISION = "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee"
DATA = ROOT / "research-data/tib-evidence-261019-1507" / REVISION / "data"
OUT = ROOT / "research-data/tib-qualification-261019-1703"
POLICY = ROOT / "experiments/registry/datasets/tib-text-model-benchmark-v1/qualification-261019-1703/group_policy.json"
OLD = ROOT / "experiments/outputs/rq2_tib_split_audit/cross_split_pair_evidence.csv"
OLD_HASH = "c3576fb2b34ac90312914ecd1c904e2c3dd74c7e5af256f6f610330d01df6fb0"


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def enrich_summary():
    """Derive review denominators and group tails from saved per-record evidence."""
    summary_path = OUT / "source_group_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    ledger = [json.loads(line) for line in (OUT / "source_group_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    pairs = [json.loads(line) for line in (OUT / "source_group_pairs.jsonl").read_text(encoding="utf-8").splitlines()]
    groups, reasons, split_edges = defaultdict(list), Counter(), Counter()
    for row in ledger:
        groups[row["group_id"]].append(row["record_id"])
    for pair in pairs:
        if pair["accepted"]:
            reasons.update(pair["reasons"])
            split_edges["/".join(sorted((pair["left_id"].split(":")[0], pair["right_id"].split(":")[0])))] += 1
    known_ids = {"train:2341", "valid:433", "test:782"}
    known_edges = [pair for pair in pairs if pair["accepted"] and {pair["left_id"], pair["right_id"]} <= known_ids]
    completed = len(ledger) == len({r["record_id"] for r in ledger}) == 9103 and summary["historical_pairs_checked"] == 2658 and len(known_edges) == 3
    summary.update({"status": "completed" if completed else "incomplete", "completed": completed,
                    "known_historical_three_edges": known_edges,
                    "policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(),
                    "source_group_ledger_sha256": hashlib.sha256((OUT / "source_group_ledger.jsonl").read_bytes()).hexdigest(),
                    "source_group_pairs_sha256": hashlib.sha256((OUT / "source_group_pairs.jsonl").read_bytes()).hexdigest(),
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "group_core_sha256": hashlib.sha256(Path(__file__).with_name("tib_model_benchmark_group_core.py").read_bytes()).hexdigest(),
                    "runtime_versions": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "pyarrow": pyarrow.__version__, "numba": numba.__version__},
                    "accepted_reason_counts": dict(reasons), "accepted_edge_split_counts": dict(split_edges),
                    "component_size_distribution": dict(Counter(len(ids) for ids in groups.values())),
                    "largest_components": sorted((ids for ids in groups.values() if len(ids) > 1), key=lambda ids: (-len(ids), ids))[:20],
                    "cross_split_components": sum(len({identity.split(":")[0] for identity in ids}) > 1 for ids in groups.values()),
                    "source_word_count_quantiles": dict(zip(("p0", "p50", "p90", "p95", "p99", "p100"),
                                                           np.percentile([row["source_word_count"] for row in ledger], [0, 50, 90, 95, 99, 100]).tolist()))})
    save(summary_path, summary)
    return summary


def frozen_policy():
    policy = {
        "version": "tib-canonical-source-groups-v1-261019-1703",
        "frozen_before_audit_outcomes": True, "source_revision": REVISION,
        "canonical_source": "transcript; NFC then collapse whitespace; segments sidecar only",
        "shingle_tokens": "canonical source casefold then Unicode regex \\b\\w+\\b; five contiguous words",
        "jaccard_threshold": .30, "containment_threshold": .80,
        "minimum_shared_fivegrams": 100, "bottom_k": 256,
        "maximum_posting_length": 500, "seed": "deterministic fixed hash key, no random sampling",
        "fingerprint": "pandas.util.hash_array uint64; sorted unique; accepted near pairs confirmed with string shingles",
        "hash_key": HASH_KEY, "numpy_version": np.__version__,
        "pandas_version": pd.__version__, "pyarrow_version": pyarrow.__version__,
        "candidate_retrieval": "any shared bottom-256 fingerprint with posting <=500; all exact DOI/URLs/source hash; all same normalized author/title; every historical queued pair",
        "metadata_rule": "nonempty exact normalized DOI/source URL/video URL is source identity evidence; author/title only retrieve candidates, never auto-group",
        "url_normalization": "casefold host and path; strip trailing slash; omit query and fragment, same as historical audit",
        "doi_normalization": "strip and casefold only",
        "minimum_group_id": "SHA256 newline-joined lexically sorted component record IDs, first 24 hex; prefix tib-source-",
        "empty_source": "empty hashes never auto-group; metadata identity may still link",
        "coverage": "all 9103 canonical transcripts within/cross split; near candidate retrieval not exhaustive; recall unknown; known-dependent groups only",
        "eligibility": "all records retained; no automatic exclusion; no unseen/pristine claim",
        "historical_pair_sha256": OLD_HASH,
    }
    if POLICY.exists():
        if json.loads(POLICY.read_text(encoding="utf-8")) != policy:
            raise ValueError("Frozen policy differs; version amendment required")
    else:
        POLICY.parent.mkdir(parents=True, exist_ok=True)
        save(POLICY, policy)
    return policy


def load_rows():
    rows, arrays, counts = [], [], Counter()
    columns = ["transcript", "doi", "url", "video_url", "author", "title"]
    started = last = time.monotonic()
    for split in ("train", "valid", "test"):
        for path in sorted(DATA.glob(split + "-*.parquet")):
            for batch in pq.ParquetFile(path).iter_batches(batch_size=32, columns=columns):
                for raw in batch.to_pylist():
                    text = str(raw["transcript"] or "")
                    normalized = canonical(text)
                    row = {"record_id": f"{split}:{counts[split]}", "split": split,
                           "source_index": counts[split], "source_raw_sha256": digest(text),
                           "source_normalized_sha256": digest(normalized),
                           "source_normalized": normalized, "source_word_count": len(words(normalized)),
                           "doi": str(raw["doi"] or "").strip().casefold(),
                           "source_url": url_key(raw["url"]), "video_url": url_key(raw["video_url"]),
                           "author_flag_key": " ".join(words(raw["author"])),
                           "title_flag_key": " ".join(words(raw["title"]))}
                    rows.append(row)
                    arrays.append(fingerprints(normalized))
                    counts[split] += 1
                    if time.monotonic() - last >= 30:
                        print(f"fingerprints {len(rows)}/9103 elapsed={time.monotonic()-started:.1f}s", flush=True)
                        last = time.monotonic()
    if dict(counts) != {"train": 7282, "valid": 910, "test": 911}:
        raise ValueError(f"Unexpected source accounting {counts}")
    return rows, arrays


def run():
    started = time.monotonic()
    policy = frozen_policy()  # Persist numerical decisions before looking at the corpus.
    if hashlib.sha256(OLD.read_bytes()).hexdigest() != OLD_HASH:
        raise ValueError("Historical pair evidence hash changed")
    rows, arrays = load_rows()
    index, metadata, historical = defaultdict(list), defaultdict(list), defaultdict(set)
    by_id = {row["record_id"]: i for i, row in enumerate(rows)}
    for i, (row, fp) in enumerate(zip(rows, arrays)):
        for token in fp[:policy["bottom_k"]]:
            index[int(token)].append(i)
        for field in ("doi", "source_url", "video_url", "source_normalized_sha256", "author_flag_key", "title_flag_key"):
            if row[field] and (field != "source_normalized_sha256" or row["source_normalized"]):
                metadata[field, row[field]].append(i)
    with OLD.open(encoding="utf-8-sig", newline="") as handle:
        for old in csv.DictReader(handle):
            a = by_id[f'{old["left_split"]}:{old["left_index"]}']
            b = by_id[f'{old["right_split"]}:{old["right_index"]}']
            historical[max(a, b)].add(min(a, b))
    omitted = sum(len(posting) > policy["maximum_posting_length"] for posting in index.values())
    index = {key: value for key, value in index.items() if len(value) <= policy["maximum_posting_length"]}
    OUT.mkdir(parents=True, exist_ok=True)
    edges, checked, historical_checked, last = [], 0, 0, time.monotonic()
    with (OUT / "source_group_pairs.jsonl").open("w", encoding="utf-8") as output:
        for i, row in enumerate(rows):
            candidates = set(historical[i])
            for token in arrays[i][:policy["bottom_k"]]:
                candidates.update(j for j in index.get(int(token), ()) if j < i)
            for field in ("doi", "source_url", "video_url", "source_normalized_sha256", "author_flag_key", "title_flag_key"):
                candidates.update(j for j in metadata.get((field, row[field]), ()) if j < i)
            for j in sorted(candidates):
                result = confirm_pair(rows[j], row, arrays[j], arrays[i], policy)
                checked += 1
                old_pair = j in historical[i]
                historical_checked += old_pair
                if result["accepted"]:
                    edges.append((rows[j]["record_id"], row["record_id"]))
                if result["accepted"] or old_pair:
                    output.write(json.dumps({"left_id": rows[j]["record_id"], "right_id": row["record_id"],
                                             "historical_queue": old_pair, **result}) + "\n")
            if time.monotonic() - last >= 30:
                print(f"pairs rows={i+1}/9103 checked={checked} accepted={len(edges)} elapsed={time.monotonic()-started:.1f}s", flush=True)
                last = time.monotonic()
    ledger = component_ledger(rows, edges)
    with (OUT / "source_group_ledger.jsonl").open("w", encoding="utf-8") as output:
        for row in ledger:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
    known = {tuple(sorted(pair)) for pair in edges}
    triplet = ["train:2341", "valid:433", "test:782"]
    reproduced = all(tuple(sorted((a, b))) in known for k, a in enumerate(triplet) for b in triplet[k+1:])
    summary = {"policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(), "records": len(rows),
               "split_counts": dict(Counter(r["split"] for r in rows)), "candidate_pairs_checked": checked,
               "historical_pairs_checked": historical_checked, "accepted_edges": len(edges),
               "groups": len({r["group_id"] for r in ledger}),
               "non_singleton_records": sum(r["group_size"] > 1 for r in ledger),
               "component_record_size_distribution": dict(Counter(r["group_size"] for r in ledger)),
               "omitted_common_sketch_postings": omitted, "known_three_edges_reproduced": reproduced,
               "near_recall": "unknown; sketch retrieval not exhaustive; known-dependent grouping only",
               "automatic_exclusions": 0, "runtime_seconds": round(time.monotonic()-started, 3),
               "fingerprint_bytes": sum(a.nbytes for a in arrays)}
    save(OUT / "source_group_summary.json", summary)
    enrich_summary()
    print(json.dumps(summary, indent=2), flush=True)
    if historical_checked != 2658 or not reproduced:
        raise ValueError("Historical replication failed; do not seal")


if __name__ == "__main__":
    run()
