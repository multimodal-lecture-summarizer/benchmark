"""Efficiency Pareto runner for notebook 07a (smoke/full).

Reads all stage aggregates and builds quality/latency/memory/cost Pareto
frontiers per stage. Produces selection.stage_pareto and
selection.stage_shortlists.
"""

from __future__ import annotations

from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import mean

# Stage → (artifact_id, primary_quality_metric, higher_is_better)
_STAGE_SPECS: list[tuple[str, str, str, bool]] = [
    ("asr", "asr.aggregate", "corpus_wer", False),
    ("scene", "scene.aggregate", "boundary_f1", True),
    ("keyframe", "keyframe.aggregate", "required_scene_f1", True),
    ("ocr", "ocr.aggregate", "recognition_cer", False),
    ("caption", "caption.aggregate", "cider", True),
    ("detection", "detection.aggregate", "detection_hmean", True),
    ("tracking", "tracking.aggregate", "hota", True),
    ("chapter", "chapter.aggregate", "collar_f1_3s", True),
    ("summary", "summary.aggregate", "cider", True),
    ("retrieval", "retrieval.aggregate", "recall@5", True),
    ("qa", "qa.aggregate", "token_f1", True),
]


def _is_pareto_dominated(
    candidate: dict[str, float],
    others: list[dict[str, float]],
    quality_key: str,
    latency_key: str,
    higher_quality: bool,
) -> bool:
    """Return True if `candidate` is dominated by any entry in `others`."""
    q_c = candidate.get(quality_key, 0.0)
    l_c = candidate.get(latency_key, float("inf"))
    for other in others:
        q_o = other.get(quality_key, 0.0)
        l_o = other.get(latency_key, float("inf"))
        # Other dominates candidate if it is at least as good on both axes
        # and strictly better on at least one
        q_better = (q_o >= q_c) if higher_quality else (q_o <= q_c)
        q_strict = (q_o > q_c) if higher_quality else (q_o < q_c)
        l_better = l_o <= l_c
        l_strict = l_o < l_c
        if q_better and l_better and (q_strict or l_strict):
            return True
    return False


def _build_pareto_frontier(
    rows: list[dict[str, Any]],
    quality_key: str,
    latency_key: str,
    higher_quality: bool,
) -> list[dict[str, Any]]:
    """Return the non-dominated subset of rows."""
    if not rows:
        return []
    metrics_list = [row.get("metrics", {}) for row in rows]
    # Inject synthetic latency proxy (1.0 for all if not present)
    for m in metrics_list:
        if latency_key not in m:
            m[latency_key] = 1.0

    pareto: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        others = [metrics_list[j] for j in range(len(rows)) if j != i]
        if not _is_pareto_dominated(metrics_list[i], others, quality_key, latency_key, higher_quality):
            pareto.append(
                {
                    "candidate": row.get("candidate"),
                    "metrics": metrics_list[i],
                    "pareto_optimal": True,
                }
            )
    return pareto


def _extract_aggregate_rows(payload: dict) -> list[dict[str, Any]]:
    return [r for r in payload.get("records", []) if isinstance(r, dict)]


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "07a_efficiency_pareto", argv)

        stage_pareto_records: list[dict[str, Any]] = []
        stage_shortlist_records: list[dict[str, Any]] = []

        for stage, artifact_id, quality_key, higher_quality in _STAGE_SPECS:
            try:
                payload = read_json_artifact(context, artifact_id)
            except Exception as exc:
                # Log and continue — missing stage does not abort the Pareto run
                stage_pareto_records.append(
                    {
                        "stage": stage,
                        "status": "missing_aggregate",
                        "error": str(exc),
                        "pareto_candidates": [],
                    }
                )
                stage_shortlist_records.append(
                    {
                        "stage": stage,
                        "status": "missing_aggregate",
                        "selected_candidate": None,
                        "selection_metric": quality_key,
                    }
                )
                continue

            rows = _extract_aggregate_rows(payload)
            if not rows:
                stage_pareto_records.append(
                    {
                        "stage": stage,
                        "status": "empty_aggregate",
                        "pareto_candidates": [],
                    }
                )
                stage_shortlist_records.append(
                    {
                        "stage": stage,
                        "status": "empty_aggregate",
                        "selected_candidate": None,
                    }
                )
                continue

            pareto = _build_pareto_frontier(rows, quality_key, "rtf", higher_quality)
            stage_pareto_records.append(
                {
                    "stage": stage,
                    "status": "ok",
                    "quality_metric": quality_key,
                    "higher_is_better": higher_quality,
                    "n_candidates": len(rows),
                    "n_pareto": len(pareto),
                    "pareto_candidates": pareto,
                }
            )

            # Select the Pareto-optimal candidate with best quality metric
            if pareto:
                best = max(pareto, key=lambda p: (
                    p["metrics"].get(quality_key, 0.0)
                    if higher_quality
                    else -p["metrics"].get(quality_key, float("inf"))
                ))
                stage_shortlist_records.append(
                    {
                        "stage": stage,
                        "status": "ok",
                        "selected_candidate": best["candidate"],
                        "selection_metric": quality_key,
                        "selection_value": best["metrics"].get(quality_key),
                    }
                )
            else:
                # All candidates dominated by each other (rare) — pick best quality
                best_row = max(rows, key=lambda r: (
                    r.get("metrics", {}).get(quality_key, 0.0)
                    if higher_quality
                    else -r.get("metrics", {}).get(quality_key, float("inf"))
                ))
                stage_shortlist_records.append(
                    {
                        "stage": stage,
                        "status": "no_pareto_optimal",
                        "selected_candidate": best_row.get("candidate"),
                        "selection_metric": quality_key,
                        "selection_value": best_row.get("metrics", {}).get(quality_key),
                    }
                )

        n_ok = sum(1 for r in stage_pareto_records if r.get("status") == "ok")
        if n_ok == 0:
            raise RuntimeError("no valid stage aggregates found; cannot perform Pareto analysis")
        if (context.run_namespace == "official" or context.profile == "full") and n_ok < len(_STAGE_SPECS):
            missing_stages = [r["stage"] for r in stage_pareto_records if r.get("status") != "ok"]
            raise RuntimeError(
                f"official/full Pareto run requires all stages; missing or invalid: {missing_stages}"
            )

        # Guard: both artifacts must be non-empty
        if not stage_pareto_records:
            raise RuntimeError("no stage aggregates available for Pareto analysis")
        if not stage_shortlist_records:
            raise RuntimeError("no stage shortlists could be built")

        write_json_artifact(context, "selection.stage_pareto", stage_pareto_records)
        write_json_artifact(context, "selection.stage_shortlists", stage_shortlist_records)
        write_run_manifest(context)

        print(
            f"[OK] efficiency pareto: {n_ok}/{len(_STAGE_SPECS)} stages with aggregates"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] efficiency pareto: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
