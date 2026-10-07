"""End-to-end system evaluation runner for notebook 08b (smoke/full).

Manifest requires: dataset.frozen_manifest, integration.pipeline_shortlist
Manifest produces: system.per_video_results, system.telemetry,
                   system.aggregate, system.final_selection
"""

from __future__ import annotations

import time
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
    simple_cider,
)


def _get_asr_text(context, unit_id: str) -> str:
    try:
        payload = read_json_artifact(context, "asr.raw_predictions")
        for record in payload.get("records", []):
            if str(record.get("unit_id")) == str(unit_id):
                return str(record.get("predictions", {}).get("hypothesis") or "")
    except Exception:
        pass
    return ""


def _get_summary_text(context, unit_id: str) -> str:
    try:
        pkg = read_json_artifact(context, "summary.multimodal_package")
        for record in pkg.get("records", []):
            if str(record.get("unit_id")) == str(unit_id):
                return str(record.get("text_summary_10pct") or "")
    except Exception:
        pass
    return ""


def _get_qa_f1(context, unit_id: str) -> float | None:
    try:
        payload = read_json_artifact(context, "qa.raw_predictions")
        f1s: list[float] = []
        for record in payload.get("records", []):
            if str(record.get("unit_id")) == str(unit_id):
                m = record.get("metrics") or {}
                if "token_f1" in m:
                    f1s.append(float(m["token_f1"]))
        return mean(f1s) if f1s else None
    except Exception:
        return None


def _system_quality(
    asr_text: str,
    summary_text: str,
    qa_f1: float | None,
    unit: dict[str, Any],
) -> dict[str, float]:
    reference_text = str(unit.get("reference_text") or unit.get("transcript") or "")
    references = [reference_text] if reference_text.strip() else []
    summary_cider = simple_cider(summary_text, references) if references and summary_text else 0.0

    asr_completeness = 0.0
    if reference_text.strip() and asr_text.strip():
        ref_words = set(reference_text.lower().split())
        hyp_words = set(asr_text.lower().split())
        asr_completeness = len(hyp_words & ref_words) / len(ref_words) if ref_words else 0.0

    return {
        "summary_cider": summary_cider,
        "qa_token_f1": qa_f1 if qa_f1 is not None else 0.0,
        "asr_completeness": asr_completeness,
        "pipeline_success": float(bool(summary_text and asr_text)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "08b_end_to_end_system", argv)
        units = load_eligible_units(context)

        # Required upstream artifacts per manifest
        read_json_artifact(context, "integration.pipeline_shortlist")

        per_video_results: list[dict[str, Any]] = []
        telemetry_records: list[dict[str, Any]] = []
        all_quality: list[dict[str, float]] = []

        for unit in units:
            uid = str(unit["unit_id"])
            t0 = time.perf_counter()

            asr_text = _get_asr_text(context, uid)
            summary_text = _get_summary_text(context, uid)
            qa_f1 = _get_qa_f1(context, uid)
            quality = _system_quality(asr_text, summary_text, qa_f1, unit)
            wall = time.perf_counter() - t0

            per_video_results.append(
                {
                    "unit_id": uid,
                    "dataset_id": unit.get("dataset_id"),
                    "pipeline_composition": "frozen_phase1",
                    "quality_metrics": quality,
                    "execution_mode": "real",
                }
            )
            telemetry_records.append(
                {
                    "unit_id": uid,
                    "assembly_wall_sec": wall,
                    "timing_source": "assembly_only_smoke",
                    "asr_available": bool(asr_text),
                    "summary_available": bool(summary_text),
                }
            )
            all_quality.append(quality)

        if not all_quality:
            raise RuntimeError("no units produced E2E results")

        agg_metrics = {
            metric: mean(row[metric] for row in all_quality)
            for metric in all_quality[0]
        }
        aggregate_records = [
            {
                "pipeline_composition": "frozen_phase1",
                "n_units": len(units),
                "aggregate_quality": agg_metrics,
            }
        ]

        # Final selection: frozen_phase1 always selected in Phase 1
        final_selection_records = [
            {
                "pipeline_composition": "frozen_phase1",
                "selected": True,
                "summary_cider": agg_metrics.get("summary_cider", 0.0),
                "qa_token_f1": agg_metrics.get("qa_token_f1", 0.0),
                "asr_completeness": agg_metrics.get("asr_completeness", 0.0),
            }
        ]

        write_json_artifact(context, "system.per_video_results", per_video_results)
        write_json_artifact(context, "system.telemetry", telemetry_records)
        write_json_artifact(context, "system.aggregate", aggregate_records)
        write_json_artifact(context, "system.final_selection", final_selection_records)
        write_run_manifest(context)
        print(
            f"[OK] end-to-end system: {len(units)} unit(s), "
            f"summary_cider={agg_metrics.get('summary_cider', 0.0):.3f}"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] end-to-end system: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
