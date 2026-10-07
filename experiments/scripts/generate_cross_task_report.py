"""Cross-task report runner for notebook 09 (smoke/full).

Read-only aggregation of all eligible stage artifacts. Never executes models
or modifies upstream artifacts.

Manifest requires: dataset.figure_manifest, selection.stage_pareto,
                   integration.compatibility_matrix, system.aggregate,
                   system.final_selection
Manifest produces: report.cross_task_tables, report.cross_task_figures,
                   report.claim_evidence_index
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

# Stage-level artifacts to include in tables
_STAGE_ARTIFACTS: list[tuple[str, str, str, bool]] = [
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


def _read_optional(context, artifact_id: str) -> dict:
    try:
        return read_json_artifact(context, artifact_id)
    except Exception as exc:
        return {"_missing": True, "_error": str(exc), "records": []}


def _best_candidate(rows: list[dict], quality_key: str, higher_better: bool) -> dict | None:
    candidates = [r for r in rows if isinstance(r.get("metrics"), dict)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda r: (
            r["metrics"].get(quality_key, 0.0)
            if higher_better
            else -r["metrics"].get(quality_key, float("inf"))
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "09_cross_task_report", argv)

        # Required artifacts per manifest
        read_json_artifact(context, "dataset.figure_manifest")
        read_json_artifact(context, "selection.stage_pareto")
        read_json_artifact(context, "integration.compatibility_matrix")
        read_json_artifact(context, "system.aggregate")
        read_json_artifact(context, "system.final_selection")

        # Build cross-task tables
        table_rows: list[dict[str, Any]] = []
        for stage, artifact_id, quality_key, higher_better in _STAGE_ARTIFACTS:
            payload = _read_optional(context, artifact_id)
            if payload.get("_missing"):
                table_rows.append(
                    {
                        "stage": stage,
                        "status": "missing",
                        "artifact_id": artifact_id,
                        "error": payload.get("_error"),
                    }
                )
                continue

            rows = [r for r in payload.get("records", []) if isinstance(r, dict)]
            best = _best_candidate(rows, quality_key, higher_better)
            all_values = [
                r["metrics"][quality_key]
                for r in rows
                if isinstance(r.get("metrics"), dict) and quality_key in r["metrics"]
            ]
            table_rows.append(
                {
                    "stage": stage,
                    "status": "ok",
                    "artifact_id": artifact_id,
                    "n_candidates": len(rows),
                    "primary_metric": quality_key,
                    "higher_is_better": higher_better,
                    "best_candidate": best.get("candidate") if best else None,
                    "best_value": best["metrics"].get(quality_key) if best else None,
                    "mean_value": mean(all_values) if all_values else None,
                }
            )

        cross_task_tables = [
            {
                "table_id": "stage_leaderboard",
                "description": "Best candidate per stage ranked by primary metric",
                "rows": table_rows,
                "n_stages_ok": sum(1 for r in table_rows if r.get("status") == "ok"),
                "n_stages_total": len(table_rows),
            }
        ]

        # Figure manifest: reference placeholders for each stage
        figure_entries: list[dict[str, Any]] = [
            {
                "figure_id": f"fig_{row['stage']}_leaderboard",
                "stage": row["stage"],
                "status": row["status"],
                "primary_metric": row.get("primary_metric"),
                "best_candidate": row.get("best_candidate"),
                "source_table": "stage_leaderboard",
            }
            for row in table_rows
        ]
        cross_task_figures = [
            {
                "figure_manifest_type": "cross_task_report",
                "figures": figure_entries,
                "note": "Figures are reproduced from stage aggregate artifacts; no model is re-executed.",
            }
        ]

        # Claim-evidence index: map each stage best candidate to its source artifact
        claim_evidence_index = [
            {
                "stage": row["stage"],
                "claim": f"Best {row['stage']} candidate is {row.get('best_candidate')!r}",
                "evidence_artifact": row.get("artifact_id"),
                "evidence_value": row.get("best_value"),
                "metric": row.get("primary_metric"),
                "status": row.get("status"),
            }
            for row in table_rows
        ]

        write_json_artifact(context, "report.cross_task_tables", cross_task_tables)
        write_json_artifact(context, "report.cross_task_figures", cross_task_figures)
        write_json_artifact(context, "report.claim_evidence_index", claim_evidence_index)
        write_run_manifest(context)

        n_ok = sum(1 for r in table_rows if r.get("status") == "ok")
        print(
            f"[OK] cross-task report: {n_ok}/{len(table_rows)} stages with eligible artifacts"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] cross-task report: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
