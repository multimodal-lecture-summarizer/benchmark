"""Freeze a bounded TIB execution cohort from the integrated benchmark bundle.

This selects execution units only. It does not change the 8,769 mechanically
eligible candidates, preprocess the source again, or certify creator abstracts.
"""

import copy
import hashlib
import json
from pathlib import Path

from experiments.scripts import rq2_tib_benchmark_bundle as bundles

QUOTAS = ((0, 15, 1, 1), (15, 30, 2, 2), (30, 60, 2, 2), (60, float("inf"), 1, 1))
SEED = "tib-valid-bounded-20261010-v1"
MIN_SOURCE_WORDS = 500
MAX_SOURCE_WORDS = 7000
LINKED_CLUSTER_VALID_ID = 433


def freeze(full_path, limited_path, manifest_path):
    full = bundles.load_benchmark_bundle(full_path)
    if full["metadata"]["source_count"] != 9103 or len(full["items"]) != 8769:
        raise ValueError("Unexpected source or candidate pool")
    chosen = []
    authors = set()
    for lower, upper, computer_count, other_count in QUOTAS:
        for is_computer_science, count in ((True, computer_count), (False, other_count)):
            eligible = [item for item in full["items"]
                        if item["split"] == "valid"
                        and item["source_index"] != LINKED_CLUSTER_VALID_ID
                        and item["duration_minutes"] is not None
                        and lower <= item["duration_minutes"] < upper
                        and MIN_SOURCE_WORDS <= item["source_words"] <= MAX_SOURCE_WORDS
                        and ("Computer Science" in item["subject"]) == is_computer_science]
            eligible.sort(key=lambda item: hashlib.sha256(
                f"{SEED}|valid/{item['source_index']}".encode()).hexdigest())
            selected_here = 0
            for item in eligible:
                author = " ".join(item["author"].casefold().split())
                if author and author in authors:
                    continue
                chosen.append(item)
                if author:
                    authors.add(author)
                selected_here += 1
                if selected_here == count:
                    break
            if selected_here != count:
                raise ValueError(f"Insufficient independent authors in {lower}:{upper}")
    chosen.sort(key=lambda item: item["source_index"])
    metadata = copy.deepcopy(full["metadata"])
    metadata["selected_count"] = len(chosen)
    metadata["selection_sha256"] = hashlib.sha256(
        bundles._json(bundles._identity(chosen)).encode("utf-8")).hexdigest()
    metadata["execution_cohort"] = {
        "scope": "bounded_valid_split_creator_abstract_agreement",
        "parent_selection_sha256": full["metadata"]["selection_sha256"],
        "seed": SEED, "source_words_inclusive": [MIN_SOURCE_WORDS, MAX_SOURCE_WORDS],
        "duration_quotas": [list(row) for row in QUOTAS[:-1]] + [[60, None, 1, 1]],
        "linked_source_cluster_held_out_from_execution": ["train/2341", "valid/433", "test/782"],
        "creator_test_used_for_model_evaluation": False,
        "unseen_reference_claim": False,
        "sampling_claim": "purposive_length_and_subject_coverage_not_population_representative",
    }
    limited = {"metadata": metadata, "items": chosen}
    receipt = bundles.save_benchmark_bundle(limited, limited_path)
    manifest = {
        "full_bundle": str(Path(full_path).resolve()),
        "full_selection_sha256": full["metadata"]["selection_sha256"],
        "limited_bundle": receipt,
        "execution_cohort": metadata["execution_cohort"],
        "selected": [{key: item[key] for key in
                      ("split", "source_index", "doi", "title", "author", "genre", "subject",
                       "source_words", "duration_minutes", "source_sha256", "reference_sha256",
                       "audit_flags")} for item in chosen],
    }
    Path(manifest_path).parent.mkdir(parents=True, exist_ok=True)
    Path(manifest_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    root = Path("experiments/outputs/rq2_tib_benchmark")
    result = freeze(root / "tib-benchmark-data.jsonl.gz",
                    root / "limited/tib-benchmark-data.jsonl.gz",
                    Path("plans/reports/tib-bounded-valid-cohort-261010-manifest.json"))
    print({"selected": len(result["selected"]),
           "bundle_payload_sha256": result["limited_bundle"]["payload_sha256"]})
