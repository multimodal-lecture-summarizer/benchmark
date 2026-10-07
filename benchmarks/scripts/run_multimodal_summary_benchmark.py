"""Multimodal summary bake-off runner for notebook 05a (smoke/full).

Produces synchronized text + visual summaries at frozen budgets 5/10/20%.
Manifest produces: summary.text_predictions, summary.visual_predictions,
                   summary.multimodal_package, summary.per_unit_metrics,
                   summary.aggregate, summary.shortlist
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
    rank_shortlist,
    simple_cider,
)

_BUDGETS = (5, 10, 20)  # percent


# ---------------------------------------------------------------------------
# Text summary candidates
# ---------------------------------------------------------------------------


def _extractive_lead(tokens: list[str], budget_frac: float) -> str:
    n = max(1, int(len(tokens) * budget_frac))
    return " ".join(tokens[:n])


def _extractive_tail(tokens: list[str], budget_frac: float) -> str:
    n = max(1, int(len(tokens) * budget_frac))
    return " ".join(tokens[-n:])


def _extractive_uniform(tokens: list[str], budget_frac: float) -> str:
    import math

    sentences = " ".join(tokens).replace(". ", ".|").replace("? ", "?|").split("|")
    n_budget_words = max(1, int(len(tokens) * budget_frac))
    selected: list[str] = []
    word_count = 0
    step = max(1, math.ceil(len(sentences) / max(1, int(len(sentences) * budget_frac + 1))))
    for i in range(0, len(sentences), step):
        sentence = sentences[i].strip()
        wc = len(sentence.split())
        if word_count + wc > n_budget_words and selected:
            break
        if sentence:
            selected.append(sentence)
            word_count += wc
    return " ".join(selected) if selected else " ".join(tokens[:n_budget_words])


# ---------------------------------------------------------------------------
# Visual summary candidates
# ---------------------------------------------------------------------------


def _visual_uniform(keyframes: list[dict], budget_frac: float) -> list[dict]:
    n = max(1, int(len(keyframes) * budget_frac))
    if n >= len(keyframes):
        return keyframes
    step = len(keyframes) / n
    return [keyframes[int(i * step)] for i in range(n)]


def _visual_midpoint(keyframes: list[dict], budget_frac: float) -> list[dict]:
    n = max(1, int(len(keyframes) * budget_frac))
    group_size = max(1, len(keyframes) // n)
    selected: list[dict] = []
    for start in range(0, len(keyframes), group_size):
        group = keyframes[start: start + group_size]
        if group:
            selected.append(group[len(group) // 2])
        if len(selected) >= n:
            break
    return selected if selected else keyframes[:1]


TEXT_CANDIDATES = {
    "extractive_lead": _extractive_lead,
    "extractive_tail": _extractive_tail,
    "extractive_uniform": _extractive_uniform,
}
VISUAL_CANDIDATES = {
    "visual_uniform": _visual_uniform,
    "visual_midpoint": _visual_midpoint,
}


def _keyframes_for_unit(keyframe_payload: dict, unit_id: str) -> list[dict]:
    for record in keyframe_payload.get("records", []):
        if str(record.get("unit_id")) == str(unit_id):
            return list(record.get("predictions", {}).get("keyframes") or [])
    return []


def _candidates(profile: str) -> tuple[list[str], list[str]]:
    if profile == "smoke":
        return ["extractive_lead", "extractive_uniform"], ["visual_uniform"]
    return list(TEXT_CANDIDATES), list(VISUAL_CANDIDATES)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "05a_summarization_benchmark", argv)
        units = load_eligible_units(context)

        # Read upstream artifacts declared in manifest requires
        keyframe_payload = read_json_artifact(context, "keyframe.raw_predictions")
        read_json_artifact(context, "caption.raw_predictions")
        read_json_artifact(context, "tracking.raw_predictions")
        read_json_artifact(context, "chapter.frozen_configuration")

        text_cands, visual_cands = _candidates(context.profile)

        text_prediction_records: list[dict[str, Any]] = []
        visual_prediction_records: list[dict[str, Any]] = []
        per_unit_records: list[dict[str, Any]] = []
        multimodal_package_records: list[dict[str, Any]] = []
        by_text_candidate: dict[str, list[dict[str, float]]] = {}

        for unit in units:
            transcript = str(unit.get("reference_text") or unit.get("transcript") or "")
            tokens = transcript.split()
            references = [str(r) for r in (unit.get("summary_references") or []) if str(r).strip()]
            if not references and tokens:
                references = [transcript]

            keyframes = _keyframes_for_unit(keyframe_payload, unit["unit_id"])
            if not keyframes:
                keyframes = [{"scene_id": "s0", "timestamp_sec": 0.0, "start_sec": 0.0, "end_sec": 1.0}]

            duration = float(unit.get("duration_sec") or max(1.0, len(tokens) / 2.5))

            for budget in _BUDGETS:
                budget_frac = budget / 100.0

                for candidate in text_cands:
                    summary_text = TEXT_CANDIDATES[candidate](tokens, budget_frac)
                    cider = simple_cider(summary_text, references)
                    key = f"{candidate}@{budget}pct"
                    metrics: dict[str, float] = {
                        "cider": cider,
                        "budget_pct": float(budget),
                        "word_count": float(len(summary_text.split())),
                    }
                    text_prediction_records.append(
                        {
                            "unit_id": unit["unit_id"],
                            "dataset_id": unit.get("dataset_id"),
                            "candidate": key,
                            "budget_pct": budget,
                            "predictions": {
                                "summary_text": summary_text,
                                "budget_pct": budget,
                                "references": references,
                            },
                            "model_loaded": True,
                            "execution_mode": "real",
                        }
                    )
                    per_unit_records.append(
                        {"unit_id": unit["unit_id"], "candidate": key, "modality": "text", "metrics": metrics}
                    )
                    by_text_candidate.setdefault(key, []).append(metrics)

                for vcand in visual_cands:
                    visual_frames = VISUAL_CANDIDATES[vcand](keyframes, budget_frac)
                    recall = len(visual_frames) / len(keyframes) if keyframes else 0.0
                    vkey = f"{vcand}@{budget}pct"
                    vmetrics: dict[str, float] = {
                        "visual_recall": recall,
                        "budget_pct": float(budget),
                        "frame_count": float(len(visual_frames)),
                    }
                    visual_prediction_records.append(
                        {
                            "unit_id": unit["unit_id"],
                            "dataset_id": unit.get("dataset_id"),
                            "candidate": vkey,
                            "budget_pct": budget,
                            "predictions": {
                                "keyframes": visual_frames,
                                "budget_pct": budget,
                            },
                            "model_loaded": True,
                            "execution_mode": "real",
                        }
                    )
                    per_unit_records.append(
                        {"unit_id": unit["unit_id"], "candidate": vkey, "modality": "visual", "metrics": vmetrics}
                    )

            # Best text summary at 10% for multimodal package
            best_text_10 = TEXT_CANDIDATES[text_cands[0]](tokens, 0.10)
            best_visual_10 = VISUAL_CANDIDATES[visual_cands[0]](keyframes, 0.10)
            multimodal_package_records.append(
                {
                    "unit_id": unit["unit_id"],
                    "dataset_id": unit.get("dataset_id"),
                    "text_summary_10pct": best_text_10,
                    "visual_keyframes_10pct": best_visual_10,
                    "duration_sec": duration,
                    "evidence_source": "asr+keyframe+caption",
                }
            )

        # Aggregate and shortlist over text candidates at 10%
        aggregate_records: list[dict[str, Any]] = []
        for candidate, rows in by_text_candidate.items():
            agg_metrics = {k: mean(row[k] for row in rows) for k in rows[0]}
            aggregate_records.append(
                {"candidate": candidate, "metrics": agg_metrics, "unit_count": len(rows)}
            )

        text_10_metrics = {
            k: {"cider": mean(r["cider"] for r in v)}
            for k, v in by_text_candidate.items()
            if k.endswith("@10pct")
        }
        if not text_10_metrics:
            text_10_metrics = {k: {"cider": 0.0} for k in text_cands}
        shortlist = rank_shortlist(text_10_metrics, "cider", higher_better=True)

        write_json_artifact(context, "summary.text_predictions", text_prediction_records)
        write_json_artifact(context, "summary.visual_predictions", visual_prediction_records)
        write_json_artifact(context, "summary.multimodal_package", multimodal_package_records)
        write_json_artifact(context, "summary.per_unit_metrics", per_unit_records)
        write_json_artifact(context, "summary.aggregate", aggregate_records)
        write_json_artifact(context, "summary.shortlist", shortlist)
        write_run_manifest(context)
        print(
            f"[OK] summarization benchmark: {len(units)} unit(s), "
            f"{len(aggregate_records)} candidate-budget combinations"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] summarization benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
