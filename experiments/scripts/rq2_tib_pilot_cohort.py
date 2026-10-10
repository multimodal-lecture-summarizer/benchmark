"""Source-only development timing pilot; this never freezes an evaluation cohort."""

import copy
import hashlib
from collections import Counter

from experiments.scripts import rq2_tib_benchmark_bundle as bundles

STRATA = ("short", "medium", "long")


def _id(row):
    return f"{row['split']}/{row['source_index']}"


def select_pilot(bundle, per_stratum=3):
    """Select min/middle/max train ranks within numeric token-length strata.

    Numeric cutpoints are the last token length in the first two train rank
    thirds. Ties stay in the lower stratum, including when assigning the full
    pool. Empty/small strata reject the design instead of relabelling tied
    lengths. Selection reads no quality score or reference content.
    """
    bundles.validate_bundle(bundle)
    if not isinstance(per_stratum, int) or isinstance(per_stratum, bool) or per_stratum < 2:
        raise ValueError("At least two ranks per stratum are required")
    tokenizer = bundle["metadata"].get("tokenizer", {})
    if not tokenizer.get("id") or not tokenizer.get("revision") or tokenizer.get("truncation") is not False:
        raise ValueError("Exact source_tokens require a declared pinned, untruncated tokenizer")
    items = bundle["items"]
    if any(not isinstance(r.get("source_tokens"), int) or isinstance(r.get("source_tokens"), bool)
           or r["source_tokens"] <= 0 for r in items):
        raise ValueError("Every full-pool item needs positive exact source_tokens")
    train = sorted((r for r in items if r["split"] == "train"),
                   key=lambda r: (r["source_tokens"], _id(r)))
    if len(train) < 3 * per_stratum:
        raise ValueError("Insufficient development items")
    cuts = [train[len(train) * k // 3 - 1]["source_tokens"] for k in (1, 2)]

    def stratum(row):
        return STRATA[sum(row["source_tokens"] > cut for cut in cuts)]

    selected = []
    for name in STRATA:
        candidates = [r for r in train if stratum(r) == name]
        if len(candidates) < per_stratum:
            raise ValueError(f"Insufficient distinct ranks in {name}; tied cutpoints may collapse strata")
        ranks = [i * (len(candidates) - 1) // (per_stratum - 1) for i in range(per_stratum)]
        selected.extend(candidates[i] for i in ranks)
    selected.sort(key=lambda r: r["source_index"])
    ledger = [{"id": _id(r), "length_stratum": stratum(r), "source_tokens": r["source_tokens"],
               "source_sha256": r["source_sha256"], "role": "development_timing_only"} for r in selected]
    source_identity = [{k: r[k] for k in ("id", "length_stratum", "source_tokens", "source_sha256")}
                       for r in ledger]
    source_hash = hashlib.sha256(bundles._json({"tokenizer": tokenizer, "cutpoints": cuts,
                                              "selected": source_identity}).encode()).hexdigest()
    population = {name: sum(stratum(r) == name for r in items) for name in STRATA}
    reserved = {split: dict(Counter(stratum(r) for r in items if r["split"] == split))
                for split in ("valid", "test")}
    train_max = max(r["source_tokens"] for r in train)
    full_max = max(r["source_tokens"] for r in items)
    design = {"status": "pilot_not_frozen", "selected": ledger,
              "selection_source_sha256": source_hash, "numeric_cutpoints_inclusive": cuts,
              "cutpoint_policy": "train_rank_thirds_ties_lower_then_even_rank_min_to_max",
              "population_by_stratum": population, "reserved_by_split": reserved,
              "expected_full_pool_count": len(items), "tokenizer": copy.deepcopy(tokenizer),
              "train_max_source_tokens": train_max, "full_max_source_tokens": full_max,
              "full_pool_exceeds_pilot_length_range": full_max > train_max,
              "evaluation_cohort_frozen": False, "quality_selection_allowed": False}
    metadata = copy.deepcopy(bundle["metadata"])
    metadata.update(selected_count=len(selected), status="pilot_not_frozen",
                    selection_sha256=hashlib.sha256(bundles._json(bundles._identity(selected)).encode()).hexdigest(),
                    technical_pilot=copy.deepcopy(design))
    subset = {"metadata": metadata, "items": copy.deepcopy(selected)}
    bundles.validate_bundle(subset)
    return subset, design
