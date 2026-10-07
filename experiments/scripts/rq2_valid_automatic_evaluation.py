"""Validation-only automatic diagnostics for the paired RQ2 S1/S3 outputs.

ROUGE-L uses the noisy creator abstract; lexical support is word overlap with
the transcript prefix. Neither metric measures factual correctness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.evaluation.metrics import rouge_l_f1, tokenize_words
from experiments.scripts.rq2_valid_paired_diagnostic import (
    DATASET,
    OUTPUT_DIR,
    RECEIPT_PATH,
    REVISION,
    _aligned_prefix,
)

METRICS = ("rouge_l_abstract_proxy", "source_lexical_support_proxy")
REFERENCE_SCREEN_PATH = ROOT / "plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-reference-screen.json"


def lexical_support(source: str, summary: str) -> float | None:
    """Share of unique summary word types also present in the source prefix."""
    hypothesis = set(tokenize_words(summary))
    if not hypothesis:
        return None
    return len(hypothesis & set(tokenize_words(source))) / len(hypothesis)


def paired_interval(differences: list[float], *, seed: int = 20261002,
                    samples: int = 5000) -> dict:
    """Percentile paired bootstrap over records; descriptive for this cohort."""
    if not differences:
        return {"n": 0, "mean_s3_minus_s1": None, "ci95": None}
    rng = random.Random(seed)
    n = len(differences)
    means = sorted(
        sum(differences[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(samples)
    )
    return {
        "n": n,
        "mean_s3_minus_s1": statistics.mean(differences),
        "ci95": [means[int(0.025 * samples)], means[int(0.975 * samples)]],
        "ci_method": "paired_record_percentile_bootstrap",
        "bootstrap_samples": samples,
        "seed": seed,
    }


def _paired_metrics(rows: list[dict]) -> dict:
    return {
        metric: paired_interval([
            row["delta_s3_minus_s1"][metric]
            for row in rows if row["delta_s3_minus_s1"][metric] is not None
        ]) for metric in METRICS
    }


def _load_pair(entry: dict, selection_hash: str) -> dict:
    # Treat manifest paths as untrusted: all evidence must reside in this output directory.
    path = Path(entry["path"]).resolve()
    if path.parent != OUTPUT_DIR.resolve() or not path.is_file():
        raise ValueError(f"Paired output outside expected directory: {path}")
    pair = json.loads(path.read_text(encoding="utf-8"))
    if (pair.get("doi") != entry["doi"] or pair.get("split") != "valid"
            or pair.get("dataset") != DATASET or pair.get("revision") != REVISION
            or pair.get("selection_sha256") != selection_hash
            or pair.get("test_content_accessed") is not False):
        raise ValueError(f"Invalid paired provenance for {entry['doi']}")
    return pair


def evaluate_records(manifest: dict, receipt: dict, source_records: dict[str, dict],
                     reference_screen: dict) -> dict:
    if (manifest.get("status") != "development_diagnostic_only"
            or manifest.get("split") != "valid"
            or manifest.get("test_content_accessed") is not False
            or manifest.get("selection_sha256") != receipt.get("selected_doi_sha256")
            or manifest.get("failed") or manifest.get("missing")):
        raise ValueError("Incomplete or mismatched validation diagnostic")
    selected = {item["doi"]: item for item in receipt["selected"]}
    if (reference_screen.get("dataset") != DATASET or reference_screen.get("revision") != REVISION
            or reference_screen.get("split") != "valid"
            or reference_screen.get("test_content_accessed") is not False):
        raise ValueError("Reference screen provenance mismatch")
    screen_items = reference_screen.get("items") or {}
    doi_to_media = {}
    for doi in selected:
        match = re.fullmatch(r"10\.5446/(\d+) \(DOI\)", doi)
        if not match:
            raise ValueError(f"Unrecognized DOI for reference screen: {doi}")
        doi_to_media[doi] = match.group(1)
    if set(screen_items) != set(doi_to_media.values()):
        raise ValueError("Reference screen DOI set differs from selected validation cohort")
    completed = manifest["completed"]
    if len(completed) != len(selected) or {x["doi"] for x in completed} != set(selected):
        raise ValueError("Completed DOI set differs from declared validation cohort")

    rows = []
    for entry in completed:
        doi = entry["doi"]
        record = source_records[doi]
        pair = _load_pair(entry, receipt["selected_doi_sha256"])
        texts, _, _, truncated = _aligned_prefix(record)
        source = " ".join(texts)
        source_hash = hashlib.sha256("\n".join(texts).encode()).hexdigest()
        if pair["transcript_sha256"] != source_hash or pair["input"]["prefix_truncated"] != truncated:
            raise ValueError(f"Source prefix changed for {doi}")
        abstract = str(record.get("abstract") or "").strip()
        arms = {}
        for label, key in (("S1", "S1"), ("S3", "S3_lexical_cohesion")):
            arm = pair["arms"][key]
            summary = arm["summary"].strip()
            if not summary:
                raise ValueError(f"Empty summary for {doi}/{label}")
            arms[label] = {
                "summary_words": len(summary.split()),
                "rouge_l_abstract_proxy": rouge_l_f1(abstract, summary) if abstract else None,
                "source_lexical_support_proxy": lexical_support(source, summary),
                "cumulative_prompt_token_estimate": arm["cumulative_prompt_token_estimate"],
                "estimated_prompt_cap_exceeded": arm["estimated_prompt_cap_exceeded"],
                "call_count": arm["call_count"],
            }
        delta = {
            metric: (arms["S3"][metric] - arms["S1"][metric]
                     if arms["S3"][metric] is not None and arms["S1"][metric] is not None else None)
            for metric in METRICS
        }
        rows.append({
            "doi": doi,
            "subject": str(record.get("subject") or "").strip(),
            "abstract_words": len(abstract.split()),
            "abstract_short_under_30_words": len(abstract.split()) < 30,
            "reference_status": "unverified_creator_abstract",
            "reference_screen": screen_items[doi_to_media[doi]]["screen"],
            "source_prefix_truncated": truncated,
            "source_prefix_words": len(source.split()),
            "full_transcript_words": pair["input"]["full_transcript_words"],
            "arms": arms,
            "delta_s3_minus_s1": delta,
        })

    strata = {}
    for name, predicate in {
        "full_transcript": lambda r: not r["source_prefix_truncated"],
        "prefix_truncated": lambda r: r["source_prefix_truncated"],
        "abstract_under_30_words": lambda r: r["abstract_short_under_30_words"],
        "abstract_at_least_30_words": lambda r: not r["abstract_short_under_30_words"],
        "reference_candidate_unverified": lambda r: r["reference_screen"] == "candidate_unverified",
        "reference_unsuitable": lambda r: r["reference_screen"] == "unsuitable",
        "both_arms_within_estimated_prompt_cap": lambda r: not any(
            arm["estimated_prompt_cap_exceeded"] for arm in r["arms"].values()),
    }.items():
        part = [r for r in rows if predicate(r)]
        strata[name] = {"n": len(part), "paired": _paired_metrics(part)}

    return {
        "status": "validation_automatic_diagnostic_only",
        "dataset": DATASET,
        "revision": REVISION,
        "split": "valid",
        "test_content_accessed": False,
        "selection_sha256": receipt["selected_doi_sha256"],
        "n": len(rows),
        "metric_interpretation": {
            "rouge_l_abstract_proxy": "ROUGE-L F1 against unverified creator abstract; reference quality varies",
            "source_lexical_support_proxy": "Fraction of unique summary word types found in processed transcript prefix; not factuality",
            "ci95": "Descriptive paired bootstrap on selected validation records; no population inference",
        },
        "paired": _paired_metrics(rows),
        "strata": strata,
        "rows": rows,
        "limits": {
            "generator": "deterministic mostly extractive heuristic",
            "source_prefix_truncated_n": sum(r["source_prefix_truncated"] for r in rows),
            "either_arm_prompt_cap_exceeded_n": sum(any(
                a["estimated_prompt_cap_exceeded"] for a in r["arms"].values()) for r in rows),
            "abstract_short_under_30_words_n": sum(r["abstract_short_under_30_words"] for r in rows),
            "actual_equal_token_budget_verified": False,
            "factuality_measured": False,
            "reference_validity_verified": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "automatic_evaluation.json")
    args = parser.parse_args()
    from datasets import load_dataset

    manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    reference_screen = json.loads(REFERENCE_SCREEN_PATH.read_text(encoding="utf-8"))
    if (receipt.get("dataset") != DATASET or receipt.get("revision") != REVISION
            or receipt.get("split_read") != "valid" or receipt.get("test_content_accessed") is not False):
        raise ValueError("Invalid validation selection receipt")
    wanted = {item["doi"] for item in receipt["selected"]}
    records = {}
    for record in load_dataset(DATASET, split="valid", revision=REVISION, streaming=True):
        doi = str(record.get("doi") or "").strip()
        if doi in wanted:
            records[doi] = record
            if len(records) == len(wanted):
                break
    if set(records) != wanted:
        raise ValueError("Validation source records incomplete")
    result = evaluate_records(manifest, receipt, records, reference_screen)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "n": result["n"], "limits": result["limits"]}))


if __name__ == "__main__":
    main()
