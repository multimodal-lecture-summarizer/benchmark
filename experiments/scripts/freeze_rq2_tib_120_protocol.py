"""Write the immutable 120-record execution contract after cohort/code review."""

import json
from pathlib import Path

from experiments.scripts.rq2_tib_benchmark_results import SCORER
from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
from experiments.scripts.rq2_tib_frozen_runtime import code_identity
from experiments.scripts.rq2_tib_pilot_runtime import digest


def freeze():
    root = Path(__file__).resolve().parents[2]
    directory = root / "experiments/registry/datasets"
    manifest = json.loads((directory / "tib-rq2-rq4-120-cohort-261012.json").read_text(encoding="utf-8"))
    scorer = SemanticScorer().metadata
    protocol = {
        "format": "tib-rq2-rq4-120-protocol-v1", "status": "frozen",
        "decision_id": "TIB-RQ2-RQ4-120-20261010",
        "cohort_manifest_sha256": manifest["manifest_sha256"],
        "selection_sha256": manifest["selection_sha256"],
        "dataset_revision": manifest["dataset_revision"],
        "selected_count": 120, "strata_counts": {"short": 40, "medium": 40, "long": 40},
        "tokenizer": manifest["tokenizer"],
        "generation": {
            "model": "Qwen/Qwen2.5-1.5B-Instruct",
            "revision": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306",
            "precision": "float16", "device": "Tesla T4", "map_batch_size": 2,
            "chunk_tokens": 512, "map_output_tokens": 96,
            "final_output_tokens": 384, "seed": 42, "temperature": 0,
            "arms": ["S1", "S3"], "repetitions": 1,
            "output_budget": "same allocated map and final caps; actual token use separately measured",
            "reference_in_generation": False,
        },
        "scoring": {"primary": SCORER, "bertscore": scorer["bertscore"],
                    "sbertscore": scorer["sbertscore"]},
        "runtime": {"generation_soft_seconds": 36000,
                    "session_soft_seconds": 43200, "automatic_retries": 0},
        "analysis": {"estimand": "record-weighted paired S3-minus-S1 among successfully scored selected valid records",
                     "full_selected_denominator": 120,
                     "failed_quality": "missing_not_zero; list every missing ID and arm/metric status",
                     "group_fields": ["dependence_group", "author_group"],
                     "group_intervals": "exploratory component-resampled record-weighted sensitivity",
                     "bootstrap_samples": 5000, "seed": 20261009,
                     "population_superiority_claim": False,
                     "unseen_test_claim": False},
        "claim": "text-only creator-abstract agreement and measured same-record S1/S3 costs",
        "limitations": ["creator abstracts not verified factual summaries",
                        "cross-split relation audit not exhaustive within valid",
                        "series and author identity not authoritative",
                        "S3 structure changes boundaries and chunk count/length"],
        "code_sha256": code_identity(),
    }
    protocol["protocol_sha256"] = digest(protocol)
    target = directory / "tib-rq2-rq4-120-protocol-261012.json"
    if target.exists() and json.loads(target.read_text(encoding="utf-8")) != protocol:
        raise ValueError("Existing protocol differs; create a new version and run root")
    if not target.exists():
        target.write_text(json.dumps(protocol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, protocol["protocol_sha256"]


if __name__ == "__main__":
    print(freeze())
