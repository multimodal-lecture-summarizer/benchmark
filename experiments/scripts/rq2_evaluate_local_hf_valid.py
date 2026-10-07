"""Score retained local-LLM RQ2 validation pairs against noisy TIB abstracts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiments.evaluation.metrics import rouge_l_f1
from experiments.scripts.rq2_controlled_validation import DATASET, REVISION, load_declared_cohort
from experiments.scripts.rq2_valid_automatic_evaluation import lexical_support, paired_interval

OUTPUT_DIR = ROOT / "experiments/outputs/diagnostic/rq2_valid_controlled_qwen"
SCREEN = ROOT / "plans/261002-0946-rq2-controlled-summarization/rq2-tib-valid-reference-screen.json"


def evaluate(manifest: dict, records: dict[str, dict], screen: dict) -> dict:
    cohort = load_declared_cohort()
    if (manifest.get("dataset") != DATASET or manifest.get("revision") != REVISION
            or manifest.get("split") != "valid" or manifest.get("test_content_accessed") is not False
            or manifest.get("selection_sha256") != cohort["selected_doi_sha256"]
            or manifest.get("requested_limit") != 20 or len(manifest.get("results", [])) != 20):
        raise ValueError("Incomplete or mismatched 20-item validation LLM run")
    if (screen.get("dataset") != DATASET or screen.get("revision") != REVISION
            or screen.get("split") != "valid" or screen.get("test_content_accessed") is not False):
        raise ValueError("Reference screen provenance mismatch")
    wanted = {item["doi"] for item in cohort["selected"]}
    if {item["doi"] for item in manifest["results"]} != wanted or set(records) != wanted:
        raise ValueError("Evaluation DOI set differs from frozen validation cohort")
    rows = []
    for item in manifest["results"]:
        doi = item["doi"]
        row = {"doi": doi, "generation_status": item["status"]}
        if item["status"] != "completed":
            row["reason"] = item.get("reason")
            rows.append(row)
            continue
        filename = re.sub(r"[^a-zA-Z0-9]+", "-", doi).strip("-") + ".json"
        pair = json.loads((OUTPUT_DIR / filename).read_text(encoding="utf-8"))
        if (pair.get("doi") != doi or pair.get("dataset") != DATASET
                or pair.get("revision") != REVISION or pair.get("split") != "valid"
                or pair.get("test_content_accessed") is not False
                or pair.get("selection_sha256") != cohort["selected_doi_sha256"]):
            raise ValueError(f"Invalid generation provenance: {doi}")
        abstract = str(records[doi].get("abstract") or "").strip()
        segments = records[doi].get("transcript_segments")
        source = (" ".join(str(text).strip() for text in segments["text"])
                  if segments is not None else None)
        media_id = re.fullmatch(r"10\.5446/(\d+) \(DOI\)", doi).group(1)
        arms = {}
        for label in ("S1", "S3"):
            arm = pair["arms"][label]
            summary = arm["summary"].strip()
            arms[label] = {"rouge_l_abstract_proxy": rouge_l_f1(abstract, summary) if abstract else None,
                           "source_lexical_overlap_proxy": lexical_support(source, summary) if source else None,
                           "summary_words": len(summary.split()),
                           "prompt_tokens": arm["prompt_tokens"],
                           "output_tokens": arm["output_tokens"],
                           "call_count": len(arm["calls"])}
        row.update({"generation_status": "completed", "abstract_words": len(abstract.split()),
                    "reference_screen": screen["items"][media_id]["screen"],
                    "source_tokens": pair["source_tokens"],
                    "prompt_imbalance_tokens": pair["prompt_imbalance_tokens"],
                    "arms": arms,
                    "delta_s3_minus_s1": {name: arms["S3"][name] - arms["S1"][name]
                        for name in ("rouge_l_abstract_proxy", "source_lexical_overlap_proxy")
                        if arms["S3"][name] is not None and arms["S1"][name] is not None}})
        rows.append(row)
    complete = [row for row in rows if row["generation_status"] == "completed"]
    return {"status": "validation_real_llm_diagnostic_only", "dataset": DATASET,
            "revision": REVISION, "split": "valid", "test_content_accessed": False,
            "model": manifest["model"], "n_declared": 20, "n_completed": len(complete),
            "primary_metric_proxy": "rouge_l_abstract_proxy",
            "paired_rouge": paired_interval([row["delta_s3_minus_s1"]["rouge_l_abstract_proxy"]
                for row in complete if "rouge_l_abstract_proxy" in row["delta_s3_minus_s1"]]),
            "rows": rows,
            "limits": {"reference_validity_verified": False, "factuality_measured": False,
                       "structure_predictor": "source_only_adjacent_window_lexical_cohesion_v1",
                       "formal_sealed_result": False}}


def main() -> None:
    from datasets import load_dataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=OUTPUT_DIR / "manifest.json")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "automatic_evaluation.json")
    parser.add_argument("--eda-cache", type=Path, help="Use pinned local abstract cache; source overlap N/A")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    screen = json.loads(SCREEN.read_text(encoding="utf-8"))
    wanted = {item["doi"] for item in load_declared_cohort()["selected"]}
    if args.eda_cache:
        cached = json.loads(args.eda_cache.read_text(encoding="utf-8"))
        if (cached.get("dataset") != DATASET or cached.get("revision") != REVISION
                or cached.get("split") != "valid" or cached.get("test_content_accessed") is not False
                or cached.get("selection_sha256") != load_declared_cohort()["selected_doi_sha256"]):
            raise ValueError("EDA abstract cache provenance mismatch")
        records = {item["doi"]: {"abstract": item["abstract_text"]}
                   for item in cached["items"]}
    else:
        records = {}
        for record in load_dataset(DATASET, split="valid", revision=REVISION, streaming=True):
            doi = str(record.get("doi") or "").strip()
            if doi in wanted:
                records[doi] = record
                if len(records) == len(wanted):
                    break
    result = evaluate(manifest, records, screen)
    target = args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target), "completed": result["n_completed"],
                      "paired_rouge": result["paired_rouge"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
