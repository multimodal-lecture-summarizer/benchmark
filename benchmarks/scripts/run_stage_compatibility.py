"""Stage compatibility benchmark runner for notebook 08a (smoke/full).

Evaluates cross-stage compatibility of shortlisted components.
Manifest produces: integration.compatibility_matrix, integration.pipeline_shortlist
Manifest requires: selection.stage_shortlists, integration.error_propagation_metrics
"""

from __future__ import annotations

from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
    mean,
)

# Stage pairs: (upstream_label, downstream_label, output_artifact_id, quality_key, higher_better)
_STAGE_PAIRS: list[tuple[str, str, str, str, bool]] = [
    ("scene", "keyframe", "keyframe.aggregate", "required_scene_f1", True),
    ("keyframe", "caption", "caption.aggregate", "cider", True),
    ("asr+scene+ocr+caption", "chapter", "chapter.aggregate", "collar_f1_3s", True),
    ("chapter+asr+keyframe+caption+tracking", "summary", "summary.aggregate", "cider", True),
    ("summary", "retrieval", "retrieval.aggregate", "recall@5", True),
    ("retrieval", "qa", "qa.aggregate", "token_f1", True),
]

_STAGE_PAIRS_SMOKE: list[tuple[str, str, str, str, bool]] = [
    ("scene", "keyframe", "keyframe.aggregate", "required_scene_f1", True),
    ("summary", "retrieval", "retrieval.aggregate", "recall@5", True),
]


def _aggregate_quality(payload: dict, quality_key: str) -> float | None:
    values: list[float] = []
    for record in payload.get("records", []):
        m = record.get("metrics")
        if isinstance(m, dict) and quality_key in m:
            values.append(float(m[quality_key]))
    return mean(values) if values else None


def _compatibility_score(predicted: float | None, oracle: float | None) -> float:
    if oracle is None or oracle == 0.0:
        return 1.0 if predicted is not None else 0.0
    if predicted is None:
        return 0.0
    return min(1.0, predicted / oracle)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "08a_stage_compatibility", argv)
        units = load_eligible_units(context)

        # Read required upstream artifacts
        read_json_artifact(context, "selection.stage_shortlists")
        read_json_artifact(context, "integration.error_propagation_metrics")

        pairs = _STAGE_PAIRS_SMOKE if context.profile == "smoke" else _STAGE_PAIRS

        # Pre-load all downstream aggregate artifacts
        available: dict[str, dict] = {}
        for _, _, art_id, _, _ in pairs:
            try:
                available[art_id] = read_json_artifact(context, art_id)
            except Exception as exc:
                available[art_id] = {"_missing": True, "_error": str(exc), "records": []}

        matrix_records: list[dict[str, Any]] = []
        shortlist_records: list[dict[str, Any]] = []

        for upstream, downstream, art_id, quality_key, higher_better in pairs:
            payload = available.get(art_id, {"records": []})
            missing = payload.get("_missing", False)

            if missing:
                matrix_records.append(
                    {
                        "upstream_stage": upstream,
                        "downstream_stage": downstream,
                        "status": "missing_artifact",
                        "quality_metric": quality_key,
                        "predicted_quality": None,
                        "compatibility_score": None,
                    }
                )
                shortlist_records.append(
                    {
                        "downstream_stage": downstream,
                        "status": "missing_artifact",
                        "selected_upstream": upstream,
                        "compatibility_score": None,
                    }
                )
                continue

            predicted_quality = _aggregate_quality(payload, quality_key)
            # Oracle proxy: perfect score (1.0 for higher-better, 0.0 for lower-better)
            oracle_quality = 1.0 if higher_better else 0.0
            compat = _compatibility_score(predicted_quality, oracle_quality if higher_better else None)

            matrix_records.append(
                {
                    "upstream_stage": upstream,
                    "downstream_stage": downstream,
                    "status": "ok",
                    "quality_metric": quality_key,
                    "higher_is_better": higher_better,
                    "predicted_quality": predicted_quality,
                    "oracle_quality": oracle_quality,
                    "compatibility_score": compat,
                    "interpretation": (
                        "compatible" if compat >= 0.9
                        else "degraded" if compat >= 0.5
                        else "incompatible"
                    ),
                }
            )
            shortlist_records.append(
                {
                    "downstream_stage": downstream,
                    "status": "ok",
                    "selected_upstream": upstream,
                    "quality_metric": quality_key,
                    "compatibility_score": compat,
                }
            )

        if not matrix_records:
            raise RuntimeError("no stage pairs could be evaluated for compatibility")

        write_json_artifact(context, "integration.compatibility_matrix", matrix_records)
        write_json_artifact(context, "integration.pipeline_shortlist", shortlist_records)
        write_run_manifest(context)

        n_ok = sum(1 for r in matrix_records if r.get("status") == "ok")
        print(f"[OK] stage compatibility: {n_ok}/{len(pairs)} pairs evaluated")
        return 0
    except Exception as exc:
        print(f"[FAIL] stage compatibility: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
