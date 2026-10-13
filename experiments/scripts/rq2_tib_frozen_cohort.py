"""Freeze score-independent TIB valid records for a bounded S1/S3 comparison."""

import copy
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts.rq2_tib_benchmark import _save_result
from experiments.scripts.rq2_tib_pilot_runtime import digest


SEED = "tib-valid-120-20261012-v1"
CUTS = (4271, 7142)
STRATA = ("short", "medium", "long")
MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"


def _id(row):
    return f"{row['split']}/{row['source_index']}"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _stratum(tokens):
    return STRATA[sum(tokens > cut for cut in CUTS)]


class _Components:
    def __init__(self, ids):
        self.parent = {name: name for name in ids}

    def root(self, name):
        self.parent.setdefault(name, name)
        if self.parent[name] != name:
            self.parent[name] = self.root(self.parent[name])
        return self.parent[name]

    def union(self, left, right):
        a, b = self.root(left), self.root(right)
        self.parent[max(a, b)] = min(a, b)


def _groups(items, audit_path, chosen):
    """Link evidence and conservative author cues over the full pool/CSV nodes."""
    ids = [_id(row) for row in items]
    evidence, author = _Components(ids), _Components(ids)
    seen = defaultdict(dict)
    for row in items:
        name = _id(row)
        for field in ("doi", "source_url", "source_sha256"):
            value = str(row.get(field) or "").strip().casefold()
            if not value:
                continue
            previous = seen[field].setdefault(value, name)
            if previous != name:
                evidence.union(name, previous)
                author.union(name, previous)
        value = " ".join(str(row.get("author") or "").casefold().split())
        if value:
            previous = seen["author"].setdefault(value, name)
            if previous != name:
                author.union(name, previous)
    classes = Counter()
    with Path(audit_path).open(encoding="utf-8", newline="") as stream:
        for pair in csv.DictReader(stream):
            left = f"{pair['left_split']}/{pair['left_index']}"
            right = f"{pair['right_split']}/{pair['right_index']}"
            relation = pair["review_class"]
            classes[relation] += 1
            if (relation in {"high_content_similarity_review", "possible_series_review"}
                    or any(pair.get(key) == "True" for key in
                           ("exact_doi", "exact_source_url", "exact_video_url", "exact_transcript_hash"))):
                evidence.union(left, right)
                author.union(left, right)
            if "author" in pair.get("shared_fields", "").split("|"):
                author.union(left, right)
    # The historical audit queued cross-split title/author pairs. Directly
    # screen every pair in this fixed 120-item cohort for within-valid reuse.
    shingles = {}
    for row in chosen:
        words = re.findall(r"\b\w+\b", row["source_text"].casefold())
        shingles[_id(row)] = set(zip(*(words[offset:] for offset in range(5))))
    selected_overlap_pairs = 0
    for index, left_row in enumerate(chosen):
        left = _id(left_row)
        for right_row in chosen[index + 1:]:
            right = _id(right_row)
            overlap = len(shingles[left] & shingles[right])
            smaller = min(len(shingles[left]), len(shingles[right]))
            union = len(shingles[left]) + len(shingles[right]) - overlap
            if union and smaller and (overlap / union >= .30 or overlap / smaller >= .80):
                evidence.union(left, right)
                author.union(left, right)
                selected_overlap_pairs += 1
    # An evidence link can join two author components via an off-pool CSV node.
    for name in list(evidence.parent):
        author.union(name, evidence.root(name))
    return evidence, author, dict(classes), selected_overlap_pairs


def freeze_cohort(full_path, token_path, pilot_design_path, pair_audit_path,
                  output_dir, manifest_path):
    """Save 120 checksum-verified records and a portable public ID manifest."""
    full = bundles.load_benchmark_bundle(full_path)
    rows = full["items"]
    if full["metadata"]["source_count"] != 9103 or len(rows) != 8769:
        raise ValueError("Pinned source/candidate counts changed")
    by_id = {_id(row): row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate source ID")
    token_cache = json.loads(Path(token_path).read_text(encoding="utf-8"))
    identity = token_cache["identity"]
    tokenizer = identity["tokenizer"]
    if (identity["full_selection"] != full["metadata"]["selection_sha256"]
            or tokenizer != {"id": MODEL, "revision": REVISION,
                             "add_special_tokens": False, "truncation": False}):
        raise ValueError("Unpinned or mismatched token ledger")
    tokens = {row["id"]: row for row in token_cache["rows"]}
    if len(tokens) != len(rows) or set(tokens) != set(by_id):
        raise ValueError("Incomplete or duplicate token ledger")
    for name, row in by_id.items():
        saved = tokens[name]
        if (saved["source_sha256"] != row["source_sha256"]
                or type(saved["source_tokens"]) is not int or saved["source_tokens"] <= 0):
            raise ValueError("Token ledger source changed: " + name)
        row["source_tokens"] = saved["source_tokens"]
    valid = [row for row in rows if row["split"] == "valid"]
    pool_counts = Counter(_stratum(row["source_tokens"]) for row in valid)
    if dict(pool_counts) != {"short": 296, "medium": 289, "long": 302}:
        raise ValueError("Valid length frame changed")
    pilot = json.loads(Path(pilot_design_path).read_text(encoding="utf-8"))
    pilot_ids = [row["id"] for row in pilot["selected"]]
    if (len(pilot_ids) != 9 or len(set(pilot_ids)) != 9
            or any(not name.startswith("train/") for name in pilot_ids)
            or pilot["numeric_cutpoints_inclusive"] != list(CUTS)
            or pilot["expected_full_pool_count"] != 8769):
        raise ValueError("Pilot identity/cutpoints changed")
    chosen = []
    for stratum in STRATA:
        candidates = [row for row in valid if _stratum(row["source_tokens"]) == stratum]
        candidates.sort(key=lambda row: (hashlib.sha256(
            f"{SEED}|{_id(row)}".encode()).hexdigest(), _id(row)))
        chosen.extend(candidates[:40])
    chosen.sort(key=lambda row: row["source_index"])
    evidence, author, classes, selected_overlap_pairs = _groups(rows, pair_audit_path, chosen)
    selected = []
    for index, row in enumerate(chosen):
        name = _id(row)
        selected.append({"id": name, "source_sha256": row["source_sha256"],
                         "reference_sha256": row["reference_sha256"],
                         "source_tokens": row["source_tokens"],
                         "length_stratum": _stratum(row["source_tokens"]),
                         "dependence_group": evidence.root(name),
                         "author_group": author.root(name),
                         "arm_order": ["S1", "S3"] if index % 2 == 0 else ["S3", "S1"],
                         "doi": row["doi"], "title": row["title"],
                         "audit_flags": row.get("audit_flags", [])})
    if (len(selected) != 120 or len({_id(row) for row in chosen}) != 120
            or set(pilot_ids).intersection(row["id"] for row in selected)):
        raise ValueError("Invalid selected cohort")
    selected_counts = Counter(row["length_stratum"] for row in selected)
    if any(selected_counts[name] != 40 for name in STRATA):
        raise ValueError("Length quotas changed")
    metadata = copy.deepcopy(full["metadata"])
    metadata.update(selected_count=120, tokenizer=tokenizer,
                    selection_sha256=hashlib.sha256(
                        bundles._json(bundles._identity(chosen)).encode()).hexdigest(),
                    status="frozen_not_evaluated",
                    execution_cohort={"id": "TIB-RQ2-RQ4-120-20261012",
                                      "split": "valid", "strata_counts": dict(selected_counts),
                                      "source_token_cutpoints_inclusive": list(CUTS), "seed": SEED})
    subset = {"metadata": metadata, "items": copy.deepcopy(chosen)}
    bundles.validate_bundle(subset)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / "tib-evaluation-120.jsonl.gz"
    if bundle_path.exists():
        prior = bundles.load_benchmark_bundle(bundle_path)
        if prior != subset:
            raise ValueError("Existing frozen bundle differs; choose a new run root")
        bundle_receipt = {"payload_sha256": _bundle_payload_sha(bundle_path),
                          "bytes": bundle_path.stat().st_size, "records": 120}
    else:
        bundle_receipt = bundles.save_benchmark_bundle(subset, bundle_path)
        bundle_receipt.pop("path", None)
    manifest = {
        "format": "tib-rq2-rq4-120-cohort-v1", "status": "frozen_not_evaluated",
        "dataset": full["metadata"]["dataset"], "dataset_revision": full["metadata"]["revision"],
        "parent_selection_sha256": full["metadata"]["selection_sha256"],
        "selection_sha256": metadata["selection_sha256"],
        "bundle": bundle_receipt,
        "inputs_sha256": {"token_ledger": _sha(token_path), "pilot_design": _sha(pilot_design_path),
                          "cross_split_pair_evidence": _sha(pair_audit_path)},
        "tokenizer": tokenizer, "seed": SEED, "split": "valid",
        "source_token_cutpoints_inclusive": list(CUTS),
        "frame_counts": dict(pool_counts), "strata_counts": dict(selected_counts),
        "selected_count": 120, "pilot_excluded_ids": pilot_ids,
        "audit_pair_classes": classes,
        "within_selected_high_overlap_pairs": selected_overlap_pairs,
        "group_policy": "exact DOI/URL/source hash plus reviewed content/series links; author union as sensitivity only",
        "group_limit": "All 120 selected pairs screened for high transcript overlap; off-cohort within-valid similarity and course identities unverified",
        "estimand": "finite balanced selected-cohort record-weighted paired delta conditional on scored intersection",
        "reference_status": "creator abstracts inspected in EDA; factuality unverified; test not unseen",
        "selected": selected,
    }
    manifest["manifest_sha256"] = digest(manifest)
    manifest_path = Path(manifest_path)
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        raise ValueError("Existing frozen manifest differs; choose a new version")
    if not manifest_path.exists():
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        _save_result(manifest, manifest_path)
    return manifest


def _bundle_payload_sha(path):
    with __import__("gzip").open(path, "rt", encoding="utf-8", newline="") as stream:
        result = None
        for line in stream:
            entry = json.loads(line)
            if entry.get("kind") == "checksum":
                result = entry["sha256"]
        if result is None:
            raise ValueError("Incomplete bundle")
        return result


if __name__ == "__main__":
    root = Path("experiments/outputs")
    result = freeze_cohort(
        root / "rq2_tib_benchmark/tib-benchmark-data.jsonl.gz",
        root / "rq2_tib_pilot_261010/data/source-token-lengths.json",
        root / "rq2_tib_pilot_261010/data/pilot-design.json",
        root / "rq2_tib_split_audit/cross_split_pair_evidence.csv",
        root / "rq2_tib_120_261012/data",
        Path("experiments/registry/datasets/tib-rq2-rq4-120-cohort-261012.json"),
    )
    print({"selected": len(result["selected"]),
           "selection_sha256": result["selection_sha256"],
           "manifest_sha256": result["manifest_sha256"]})
