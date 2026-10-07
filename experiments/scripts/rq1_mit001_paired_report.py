"""Summarize paired RQ1 chapter scores from one local diagnostic artifact root.

This reads completed 04a/04b payloads and prints Markdown. It never modifies the
input artifacts or presents a single-course diagnostic as an official evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from experiments.scripts.benchmark_artifacts import RunnerContext, read_json_artifact, validated_payload_path


EXPECTED_UNITS = 35
METRIC = "collar_f1_3s"
BENCHMARK_CANDIDATES = (
    "fixed_window_300s",
    "lexical_texttiling",
    "multimodal_scene_aligned",
)
ABLATION_VARIANTS = ("transcript", "transcript+ocr", "transcript+scene")
NEW_ABLATION_VARIANTS = ("transcript+visual", "transcript+acoustic", "all_modalities")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _scores(payload: dict[str, Any], category: str, wanted: tuple[str, ...]) -> dict[str, dict[str, float]]:
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Missing records for {category}")
    scores: dict[str, dict[str, float]] = {name: {} for name in wanted}
    for row in records:
        if not isinstance(row, dict):
            raise ValueError(f"Invalid {category} record")
        name = row.get(category)
        if name not in scores:
            continue
        unit_id = row.get("unit_id")
        metric = row.get("metrics")
        value = metric.get(METRIC) if isinstance(metric, dict) else None
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError(f"Missing unit_id for {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid {METRIC} for {unit_id}/{name}")
        if unit_id in scores[name]:
            raise ValueError(f"Duplicate score for {unit_id}/{name}")
        scores[name][unit_id] = float(value)
    return scores


def _validate_cohort(scores: dict[str, dict[str, float]], expected_count: int) -> list[str]:
    cohorts = [set(by_unit) for by_unit in scores.values()]
    if not cohorts or any(cohort != cohorts[0] for cohort in cohorts[1:]):
        raise ValueError("04a/04b candidates do not share the same lecture IDs")
    if len(cohorts[0]) != expected_count:
        raise ValueError(f"Expected {expected_count} matching lecture IDs, got {len(cohorts[0])}")
    return sorted(cohorts[0])


def _verify_source_run(root: Path, summary: dict[str, Any], variants: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind the compared rows to one completed source, feature, and run identity."""
    source_hash = summary.get("code_sha256")
    if not isinstance(source_hash, str) or len(source_hash) != 64:
        raise ValueError("Missing diagnostic code_sha256")
    receipt_dir = root / "diagnostic" / "full"
    anchor = _read_json(receipt_dir / "chapter.input_features.receipt.json")
    config_hash = anchor.get("config_sha256")
    dependency_hash = anchor.get("dependency_state_sha256")
    context = RunnerContext(
        profile="full", run_namespace="diagnostic", status="partial", artifact_root=root,
        notebook_id="paired_report", run_id="00000000-0000-0000-0000-000000000000",
        source_sha256=source_hash, config_sha256=config_hash,
        dependency_state_sha256=dependency_hash, evaluation_mode="selection",
    )
    producers = {
        "dataset.frozen_manifest": "00c_dataset_eda_and_freeze",
        "chapter.input_features": "04a_chaptering_benchmark",
        "chapter.per_unit_metrics": "04a_chaptering_benchmark",
        "chapter.raw_predictions": "04a_chaptering_benchmark",
        "chapter.ablation_metrics": "04b_chaptering_modality_ablation",
        "chapter.ablation_predictions": "04b_chaptering_modality_ablation",
        "chapter.ablation_status": "04b_chaptering_modality_ablation",
    }
    payloads: dict[str, dict[str, Any]] = {}
    for artifact_id, producer in producers.items():
        _, receipt = validated_payload_path(context, artifact_id)
        if (receipt.get("producer_notebook_id") != producer or receipt.get("source_sha256") != source_hash
                or receipt.get("config_sha256") != config_hash
                or receipt.get("dependency_state_sha256") != dependency_hash
                or receipt.get("status") != "partial"
                or receipt.get("evaluation_mode") != (None if producer.startswith("00c") else "selection")):
            raise ValueError(f"{artifact_id}: mixed or incomplete run identity")
        payloads[artifact_id] = read_json_artifact(context, artifact_id)

    frozen = payloads["dataset.frozen_manifest"]["records"]
    if len(frozen) != 1:
        raise ValueError("Expected one frozen diagnostic cohort")
    units = frozen[0].get("unit_records")
    if not isinstance(units, list) or len(units) != EXPECTED_UNITS:
        raise ValueError("Frozen diagnostic cohort does not contain 35 units")
    source_by_id = {u["unit_id"]: u["sha256"] for u in units}
    if len(source_by_id) != EXPECTED_UNITS or set(source_by_id) != set(frozen[0].get("unit_ids", [])):
        raise ValueError("Frozen diagnostic cohort has duplicate or mismatched IDs")
    feature_rows = payloads["chapter.input_features"]["records"]
    feature_by_id = {f["unit_id"]: f for f in feature_rows}
    if len(feature_by_id) != EXPECTED_UNITS or set(feature_by_id) != set(source_by_id):
        raise ValueError("Feature cohort does not match frozen lecture IDs")
    for uid, feature in feature_by_id.items():
        if (feature.get("source_sha256") != source_by_id[uid]
                or feature.get("dataset_id") != summary["dataset_id"]
                or feature.get("split") != "validation"
                or feature.get("evaluation_mode") != "selection"):
            raise ValueError(f"{uid}: feature source/split mismatch")
    for artifact_id, name_field in (("chapter.raw_predictions", "candidate"),
                                    ("chapter.ablation_predictions", "ablation_variant")):
        rows = payloads[artifact_id]["records"]
        pairs = set()
        for row in rows:
            uid = row.get("unit_id")
            pair = (uid, row.get(name_field))
            if (uid not in feature_by_id or row.get("dataset_id") != summary["dataset_id"]
                    or row.get("split") != "validation"
                    or row.get("feature_cache_key") != feature_by_id[uid].get("cache_key")
                    or pair in pairs):
                raise ValueError(f"{artifact_id}: prediction feature key or cohort mismatch")
            pairs.add(pair)
        metric_artifact = "chapter.per_unit_metrics" if name_field == "candidate" else "chapter.ablation_metrics"
        metric_pairs = {(row.get("unit_id"), row.get(name_field)) for row in payloads[metric_artifact]["records"]}
        if pairs != metric_pairs:
            raise ValueError(f"{artifact_id}: predictions and metrics differ")
    statuses = {row.get("ablation"): row.get("status") for row in payloads["chapter.ablation_status"]["records"]}
    if any(statuses.get(name) != "run" for name in variants):
        raise ValueError("Requested ablation was not run")
    return payloads["chapter.per_unit_metrics"], payloads["chapter.ablation_metrics"]


def build_report(root: Path) -> str:
    summary = _read_json(root / "pilot_summary.json")
    if summary.get("diagnostic_only") is not True:
        raise ValueError("Only diagnostic runs are accepted")
    if summary.get("dataset_id") != "avlectures_mit001_local_diagnostic":
        raise ValueError("Unexpected diagnostic dataset")
    if summary.get("unit_count") != EXPECTED_UNITS or summary.get("exit_codes") != {"04a": 0, "04b": 0}:
        raise ValueError("Expected a completed 35-lecture 04a/04b run")

    expected_ablations = ABLATION_VARIANTS + (
        NEW_ABLATION_VARIANTS if summary.get("video_features_requested") is True else ()
    )
    payload_dir = root / "diagnostic" / "full" / "payloads"
    benchmark_payload, ablation_payload = (
        _verify_source_run(root, summary, expected_ablations)
        if summary.get("video_features_requested") is True else (
            _read_json(payload_dir / "chapter.per_unit_metrics.json"),
            _read_json(payload_dir / "chapter.ablation_metrics.json"),
        )
    )
    benchmark = _scores(
        benchmark_payload,
        "candidate", BENCHMARK_CANDIDATES,
    )
    ablation = _scores(
        ablation_payload,
        "ablation_variant", expected_ablations,
    )
    all_scores = {**benchmark, **ablation}
    unit_ids = _validate_cohort(all_scores, EXPECTED_UNITS)
    baseline = all_scores["transcript"]

    lines = [
        "# RQ1 MIT001: paired chaptering diagnostic",
        "",
        f"Artifact: `{root.resolve()}`",
        f"Dataset: `{summary['dataset_id']}`; {len(unit_ids)} matched lectures from one course.",
        f"Metric: macro mean of per-lecture `{METRIC}` (3-second boundary collar).",
        "Paired deltas and win/tie/loss compare each lecture with the 04b `transcript` variant.",
        "",
        "| Variant | Macro F1@3s | Mean paired delta | Wins / ties / losses |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name in (*BENCHMARK_CANDIDATES, *expected_ablations):
        values = all_scores[name]
        diffs = [values[unit] - baseline[unit] for unit in unit_ids]
        wins = sum(delta > 1e-12 for delta in diffs)
        losses = sum(delta < -1e-12 for delta in diffs)
        ties = len(diffs) - wins - losses
        lines.append(
            f"| `{name}` | {mean(values.values()):.4f} | {mean(diffs):+.4f} | {wins} / {ties} / {losses} |"
        )

    limitation = summary.get("limitation")
    lines.extend(["", "## Scope and limitations", "", "- Local diagnostic only; these are descriptive scores, not an official or held-out result."])
    if isinstance(limitation, str) and limitation.strip():
        lines.append(f"- {limitation.strip()}")
    lines.extend([
        "- All 35 videos are from MIT18.01JF07; this run cannot measure transfer to another course.",
        "- OCR and scene features are sampled/extracted from local media; this report makes no claim about unsampled visual content.",
        "- Visual means sparse source-frame change and acoustic means source-audio energy change; neither is a learned visual-caption or prosody model." if summary.get("video_features_requested") is True else "- Visual, acoustic, and full-modality ablations are outside the compared variants here.",
        "- The full-modality row is a fixed heuristic fusion, not a C5/C6 learned checkpoint." if summary.get("video_features_requested") is True else "- Learned C5/C6 variants were not evaluated.",
        "- No statistical significance or population-level conclusion is inferred from these paired descriptions.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_root", type=Path, help="Completed local RQ1 diagnostic run directory")
    args = parser.parse_args()
    print(build_report(args.artifact_root), end="")


if __name__ == "__main__":
    main()
