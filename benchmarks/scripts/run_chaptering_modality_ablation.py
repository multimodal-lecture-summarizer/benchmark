"""Chaptering modality ablation runner for notebook 04b (RQ1, validation-only).

Consumes ``chapter.input_features`` and ``chapter.shortlist`` from 04a on the
same frozen validation units (identity, split, source hash and evaluation mode
are verified per unit before inference).

Ablation variants declare the modalities they need.  A variant whose modality
was not extracted for these units is reported ``not_run`` in
``chapter.ablation_status``; it is never silently downgraded to text-only and
never labelled as the learned C5/C6 models.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Sequence

from benchmarks.scripts.run_chaptering_benchmark import (
    MULTIMODAL_ALIGNMENT_WINDOW_SEC,
    align_transcript_to_events,
    fixed_window_boundaries,
    lexical_texttiling_boundaries,
    transcript_scene_boundaries,
)
from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.chapter_benchmark_contract import (
    SCORER_DESCRIPTION,
    ChapterContractError,
    admitted_splits,
    assert_units_in_splits,
    index_features,
    predictor_input,
    reference_boundaries,
    require_modalities,
)
from experiments.scripts.rq1_official_scorer import score_official_unit
from experiments.scripts.stage_benchmark_helpers import load_eligible_units, mean

NOTEBOOK_ID = "04b_chaptering_modality_ablation"

Predictor = Callable[[dict[str, Any], dict[str, Any]], list[float]]


def _transcript_of(unit: dict[str, Any]) -> str:
    return str(unit.get("transcript") or unit.get("reference_text") or "")


OCR_NOVELTY_JACCARD_MAX = 0.5  # declared before reading validation GT


def transcript_ocr_boundaries(unit: dict[str, Any], feature: dict[str, Any]) -> list[float]:
    """Align lexical topic changes to OCR text changes on this video's timeline."""
    return align_transcript_to_events(
        _transcript_of(unit), feature["duration_sec"], _ocr_events(feature),
    )


def _ocr_events(feature: dict[str, Any]) -> list[float]:
    observations = feature["modalities"]["ocr"]["observations"]
    events: list[float] = []
    previous_tokens: set[str] | None = None
    for observation in observations:
        tokens = set(re.findall(r"\w+", observation["text"].lower()))
        if not tokens:
            continue
        if previous_tokens is not None:
            union = previous_tokens | tokens
            similarity = len(previous_tokens & tokens) / len(union) if union else 1.0
            if similarity <= OCR_NOVELTY_JACCARD_MAX:
                events.append(float(observation["time_sec"]))
        previous_tokens = tokens
    return events


def _change_events(feature: dict[str, Any], modality: str) -> list[float]:
    """Select the strongest quarter of positive changes within this lecture."""
    observations = feature["modalities"][modality]["observations"]
    positive = sorted(float(row["change_score"]) for row in observations if row["change_score"] > 0)
    if not positive:
        return []
    threshold = positive[(3 * (len(positive) - 1)) // 4]
    return [float(row["time_sec"]) for row in observations if row["change_score"] >= threshold]


def transcript_change_boundaries(unit: dict[str, Any], feature: dict[str, Any], modality: str) -> list[float]:
    return align_transcript_to_events(
        _transcript_of(unit), feature["duration_sec"], _change_events(feature, modality),
    )


def all_modality_boundaries(unit: dict[str, Any], feature: dict[str, Any]) -> list[float]:
    """Keep lexical changes corroborated by at least two source modalities."""
    events = (
        feature["modalities"]["scene"]["boundaries_sec"],
        _ocr_events(feature),
        _change_events(feature, "visual"),
        _change_events(feature, "acoustic"),
    )
    lexical = lexical_texttiling_boundaries(_transcript_of(unit), feature["duration_sec"])
    fused: set[float] = set()
    for boundary in lexical:
        nearby = []
        for modality_events in events:
            if modality_events:
                nearest = min(modality_events, key=lambda event: (abs(event - boundary), event))
                if abs(nearest - boundary) <= MULTIMODAL_ALIGNMENT_WINDOW_SEC:
                    nearby.append(float(nearest))
        if len(nearby) >= 2:
            fused.add(round(sorted(nearby)[len(nearby) // 2], 3))
    return sorted(fused)


# name -> (required modalities, predictor or None when no implementation exists)
ABLATIONS: dict[str, tuple[tuple[str, ...], Predictor | None]] = {
    "duration_only": ((), lambda unit, feat: fixed_window_boundaries(feat["duration_sec"])),
    "transcript": (
        ("transcript",),
        lambda unit, feat: lexical_texttiling_boundaries(_transcript_of(unit), feat["duration_sec"]),
    ),
    "transcript+ocr": (("transcript", "ocr"), transcript_ocr_boundaries),
    "transcript+scene": (("transcript", "scene"), transcript_scene_boundaries),
    "transcript+visual": (("transcript", "visual"), lambda unit, feat: transcript_change_boundaries(unit, feat, "visual")),
    "transcript+acoustic": (("transcript", "acoustic"), lambda unit, feat: transcript_change_boundaries(unit, feat, "acoustic")),
    "all_modalities": (("transcript", "ocr", "scene", "visual", "acoustic"), all_modality_boundaries),
}
SMOKE_ABLATIONS = ("duration_only", "transcript")


def _selected_algorithm(shortlist: dict[str, Any]) -> str:
    records = shortlist.get("records") or []
    selected = [r for r in records if r.get("selected") is True]
    if len(selected) != 1:
        raise ChapterContractError("chapter.shortlist must mark exactly one selected candidate")
    return str(selected[0]["candidate"])


def run(context) -> dict[str, Any]:
    splits = admitted_splits(context.evaluation_mode)
    units = load_eligible_units(context, allowed_splits=splits)
    assert_units_in_splits(units, splits)

    feature_payload = read_json_artifact(context, "chapter.input_features")
    features = index_features(feature_payload["records"], units, context.evaluation_mode)
    selected_04a_candidate = _selected_algorithm(read_json_artifact(context, "chapter.shortlist"))

    references = {str(u["unit_id"]): reference_boundaries(u) for u in units}
    names = SMOKE_ABLATIONS if context.profile == "smoke" else tuple(ABLATIONS)

    status: list[dict[str, Any]] = []
    runnable: list[str] = []
    for name in names:
        needed, predictor = ABLATIONS[name]
        missing = sum(1 for f in features.values() if require_modalities(f, needed))
        if missing:
            status.append({"ablation": name, "status": "not_run", "reason": "missing_modality",
                           "required_modalities": list(needed), "units_missing": missing})
        elif predictor is None:
            status.append({"ablation": name, "status": "not_run",
                           "reason": "not_implemented: no fusion method bound to this variant",
                           "required_modalities": list(needed)})
        else:
            status.append({"ablation": name, "status": "run", "required_modalities": list(needed)})
            runnable.append(name)
    if not runnable:
        raise ChapterContractError("no runnable ablation variant for this cohort")

    predictions: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        uid = str(unit["unit_id"])
        feature = features[(str(unit["dataset_id"]), uid)]
        for name in runnable:
            predictor = ABLATIONS[name][1]
            assert predictor is not None
            # Runtime/model errors abort the run. Invalid returned payloads are
            # retained as zero-primary-score unit failures by the scorer.
            raw_prediction = predictor(predictor_input(unit), dict(feature))
            scored = score_official_unit(
                unit_id=uid, candidate=name, predicted_sec=raw_prediction,
                reference_sec=references[uid], duration_sec=feature["duration_sec"],
            )
            predicted = scored["normalized_prediction_sec"]
            metrics = scored["metrics"]
            predictions.append({
                "unit_id": uid,
                "dataset_id": unit.get("dataset_id"),
                "split": unit.get("split"),
                "ablation_variant": name,
                "feature_cache_key": feature["cache_key"],
                "predictions": {
                    "chapter_boundaries_sec": predicted,
                    "reference_boundaries_sec": references[uid],
                    "empty_prediction": predicted == [],
                },
                "score_status": scored["status"],
                "failure_reason": scored["failure_reason"],
                "model_loaded": True,
                "execution_mode": "real",
            })
            metrics_rows.append({"unit_id": uid, "ablation_variant": name, "metrics": metrics,
                                 "score_status": scored["status"],
                                 "failure_reason": scored["failure_reason"],
                                 "secondary_status": scored["secondary_status"],
                                 "pk_wd_k_bins": scored["pk_wd_k_bins"]})
            by_variant.setdefault(name, []).append(scored)

    primary = {name: mean(r["metrics"]["collar_f1_3s"] for r in rows)
               for name, rows in by_variant.items()}
    best = max(sorted(primary), key=lambda k: primary[k])
    frozen_configuration = [{
        # Each ablation is a complete predictor. The 04a winner is retained as
        # context only; combining it with this winner was never evaluated.
        "configuration_scope": "ablation_predictor_only",
        "evaluated_predictor": best,
        "independent_04a_selected_candidate": selected_04a_candidate,
        "joint_04a_04b_configuration_evaluated": False,
        "frozen_modality_variant": best,
        # These predictors are source-bound heuristics, not C1-C6. An official
        # namespace alone cannot make this a frozen RQ1 model selection.
        "official_selection_eligible": False,
        "selection_scope": "heuristic_diagnostic",
        "selection_split": "validation",
        "selection_metric": "collar_f1_3s",
        "selection_collar_f1_3s": primary[best],
        "variant_table": [
            {"variant": k, "collar_f1_3s": v, "unit_count": len(by_variant[k]),
             "failure_count": sum(row["status"] == "candidate_unit_failure"
                                  for row in by_variant[k])}
            for k, v in sorted(primary.items())
        ],
        "selection_unit_ids": sorted(references),
        "final_test_evaluated": False,
    }]
    metadata = {
        "evaluation_mode": context.evaluation_mode,
        "admitted_splits": sorted(splits),
        "scorer": SCORER_DESCRIPTION,
        "diagnostic_only": True,
    }
    write_json_artifact(context, "chapter.ablation_status", status, metadata=metadata)
    write_json_artifact(context, "chapter.ablation_predictions", predictions, metadata=metadata)
    write_json_artifact(context, "chapter.ablation_metrics", metrics_rows, metadata=metadata)
    write_json_artifact(context, "chapter.frozen_configuration", frozen_configuration,
                        metadata=metadata)
    write_run_manifest(context)
    return {"units": len(units), "runnable": runnable, "best": best, "status": status}


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", NOTEBOOK_ID, argv)
        summary = run(context)
        print(
            f"[OK] chaptering modality ablation: {summary['units']} validation unit(s), "
            f"{len(summary['runnable'])} runnable variant(s), frozen={summary['best']}"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] chaptering modality ablation: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
