"""Chaptering bake-off runner for notebook 04a (RQ1, validation-only selection).

Contract (``experiments.scripts.chapter_benchmark_contract``):

* consumes one frozen, rights-cleared lecture cohort (``dataset.frozen_manifest``);
  no ASR/scene/OCR/caption stage-benchmark predictions from other datasets;
* admits only ``validation`` units (``--evaluation-mode selection``), filtered in
  the shared loader before any smoke truncation;
* every unit must carry independent, provenance-bound ``chapter_boundaries_sec``;
  there is no scene, clip-join or duration-midpoint fallback;
* writes the hash-bound ``chapter.input_features`` consumed by 04b;
* scores with the frozen RQ1 scorer (primary collar F1 at +/-3 s);
* empty predictions stay empty and are scored as zero boundaries;
* candidates whose modalities or checkpoints are unavailable are reported as
  ``not_run`` in ``chapter.candidate_status`` instead of being relabelled.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Sequence

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.chapter_benchmark_contract import (
    SCORER_DESCRIPTION,
    ChapterContractError,
    admitted_splits,
    assert_units_in_splits,
    build_input_feature_record,
    learned_candidate_status,
    predictor_input,
    reference_boundaries,
    require_modalities,
)
from experiments.scripts.rq1_official_scorer import score_official_unit
from experiments.scripts.stage_benchmark_helpers import (
    load_eligible_units,
    mean,
    rank_shortlist,
    write_stage_quartet,
)

NOTEBOOK_ID = "04a_chaptering_benchmark"
FIXED_WINDOW_SEC = 300.0          # frozen a priori; not tuned on validation
TEXTTILING_BLOCK_TOKENS = 20
TEXTTILING_THRESHOLD = 0.20
MULTIMODAL_ALIGNMENT_WINDOW_SEC = 45.0  # declared before reading validation GT

# ---------------------------------------------------------------------------
# Chapter boundary algorithms (all return seconds)
# ---------------------------------------------------------------------------


def fixed_window_boundaries(duration_sec: float, window_sec: float = FIXED_WINDOW_SEC) -> list[float]:
    """Duration-only baseline: a boundary every ``window_sec`` seconds."""
    boundaries: list[float] = []
    t = window_sec
    while t < duration_sec:
        boundaries.append(round(t, 3))
        t += window_sec
    return boundaries


def lexical_texttiling_tokens(
    tokens: list[str],
    block_size: int = TEXTTILING_BLOCK_TOKENS,
    threshold: float = TEXTTILING_THRESHOLD,
) -> list[int]:
    """Lightweight TextTiling-style lexical segmenter over token indices."""
    if len(tokens) < block_size * 2:
        return []

    def block_vocab(chunk: list[str]) -> set[str]:
        return {t.lower() for t in chunk if re.match(r"\w+", t)}

    boundaries: list[int] = []
    step = max(1, block_size // 2)
    for i in range(step, len(tokens) - step, step):
        left = block_vocab(tokens[max(0, i - block_size): i])
        right = block_vocab(tokens[i: i + block_size])
        denom = len(left | right)
        score = len(left & right) / denom if denom else 1.0
        if score < threshold:
            boundaries.append(i)
    deduped: list[int] = []
    for b in sorted(boundaries):
        if not deduped or b - deduped[-1] > block_size:
            deduped.append(b)
    return deduped


def lexical_texttiling_boundaries(transcript: str, duration_sec: float) -> list[float]:
    """Transcript-only baseline mapped to time with a uniform token rate.

    The uniform-rate mapping is a declared limitation (no word timestamps); it is
    recorded in ``chapter.input_features`` as ``time_alignment``.
    """
    tokens = transcript.split()
    if not tokens:
        return []
    rate = len(tokens) / duration_sec
    return [round(idx / rate, 3) for idx in lexical_texttiling_tokens(tokens)]


def align_transcript_to_events(
    transcript: str, duration_sec: float, event_times: Sequence[float],
) -> list[float]:
    """Retain lexical changes corroborated by a nearby visual event.

    A lexical boundary without an event is omitted, so an empty event stream
    cannot silently become a transcript-only prediction.
    """
    if not event_times:
        return []
    aligned: set[float] = set()
    for boundary in lexical_texttiling_boundaries(transcript, duration_sec):
        nearest = min(event_times, key=lambda event: (abs(event - boundary), event))
        if abs(nearest - boundary) <= MULTIMODAL_ALIGNMENT_WINDOW_SEC:
            aligned.add(round(float(nearest), 3))
    return sorted(aligned)


def transcript_scene_boundaries(unit: dict[str, Any], feature: dict[str, Any]) -> list[float]:
    scene = feature["modalities"]["scene"]
    return align_transcript_to_events(
        _transcript_of(unit), feature["duration_sec"], scene["boundaries_sec"],
    )


# name -> (required modalities, predictor(unit, feature) -> boundaries)
Predictor = Callable[[dict[str, Any], dict[str, Any]], list[float]]


def _transcript_of(unit: dict[str, Any]) -> str:
    return str(unit.get("transcript") or unit.get("reference_text") or "")


HEURISTIC_CANDIDATES: dict[str, tuple[tuple[str, ...], Predictor]] = {
    "fixed_window_300s": ((), lambda unit, feat: fixed_window_boundaries(feat["duration_sec"])),
    "lexical_texttiling": (
        ("transcript",),
        lambda unit, feat: lexical_texttiling_boundaries(_transcript_of(unit), feat["duration_sec"]),
    ),
    "multimodal_scene_aligned": (("transcript", "scene"), transcript_scene_boundaries),
}
LEARNED_CANDIDATES = ("C5_cross_attention", "C6_late_fusion")
SMOKE_CANDIDATES = ("fixed_window_300s", "lexical_texttiling")


def run(context) -> dict[str, Any]:
    splits = admitted_splits(context.evaluation_mode)
    units = load_eligible_units(context, allowed_splits=splits)
    assert_units_in_splits(units, splits)

    # Validate GT and build same-unit features for every unit before inference.
    references: dict[str, list[float]] = {}
    features: list[dict[str, Any]] = []
    for unit in units:
        references[str(unit["unit_id"])] = reference_boundaries(unit)
        features.append(build_input_feature_record(
            unit, evaluation_mode=context.evaluation_mode, code_sha256=context.source_sha256,
        ))
    feature_by_unit = {f["unit_id"]: f for f in features}

    names = SMOKE_CANDIDATES if context.profile == "smoke" else tuple(HEURISTIC_CANDIDATES)
    candidate_status: list[dict[str, Any]] = []
    runnable: list[str] = []
    for name in names:
        needed, _ = HEURISTIC_CANDIDATES[name]
        missing_units = {
            f["unit_id"]: require_modalities(f, needed) for f in features
            if require_modalities(f, needed)
        }
        if missing_units:
            candidate_status.append({
                "candidate": name, "status": "not_run", "family": "heuristic",
                "reason": "missing_modality", "required_modalities": list(needed),
                "units_missing": len(missing_units), "unit_count": len(units),
            })
        else:
            runnable.append(name)
            candidate_status.append({
                "candidate": name, "status": "run", "family": "heuristic",
                "required_modalities": list(needed), "unit_count": len(units),
            })
    if context.profile != "smoke":
        for name in LEARNED_CANDIDATES:
            status = learned_candidate_status(name, units)
            status["family"] = "learned"
            candidate_status.append(status)
            if status["status"] == "run":  # pragma: no cover - not reachable yet
                runnable.append(name)
    if not runnable:
        raise ChapterContractError("no runnable chaptering candidate for this cohort")

    predictions: list[dict[str, Any]] = []
    per_unit: list[dict[str, Any]] = []
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        uid = str(unit["unit_id"])
        feature = feature_by_unit[uid]
        reference = references[uid]
        for name in runnable:
            _, predictor = HEURISTIC_CANDIDATES[name]
            # Runtime/model errors abort the run. Only an emitted invalid payload
            # is a candidate/unit scoring failure under the frozen policy.
            raw_prediction = predictor(predictor_input(unit), feature)
            scored = score_official_unit(
                unit_id=uid, candidate=name, predicted_sec=raw_prediction,
                reference_sec=reference, duration_sec=feature["duration_sec"],
            )
            predicted = scored["normalized_prediction_sec"]
            metrics = scored["metrics"]
            predictions.append({
                "unit_id": uid,
                "dataset_id": unit.get("dataset_id"),
                "split": unit.get("split"),
                "candidate": name,
                "feature_cache_key": feature["cache_key"],
                "predictions": {
                    "chapter_boundaries_sec": predicted,
                    "reference_boundaries_sec": reference,
                    "empty_prediction": predicted == [],
                },
                "score_status": scored["status"],
                "failure_reason": scored["failure_reason"],
                "model_loaded": True,
                "execution_mode": "real",
            })
            per_unit.append({"unit_id": uid, "candidate": name, "metrics": metrics,
                             "score_status": scored["status"],
                             "failure_reason": scored["failure_reason"],
                             "secondary_status": scored["secondary_status"],
                             "pk_wd_k_bins": scored["pk_wd_k_bins"]})
            by_candidate.setdefault(name, []).append(scored)

    aggregate_metrics = {
        name: {
            key: (mean(row["metrics"][key] for row in rows)
                  if all(row["metrics"][key] is not None for row in rows) else None)
            for key in ("collar_f1_3s", "collar_f1_5s", "collar_f1_10s", "pk", "window_diff")
        }
        for name, rows in by_candidate.items()
    }
    aggregate = [
        {
            "candidate": name,
            "metrics": metrics,
            "unit_count": len(by_candidate[name]),
            "empty_prediction_count": sum(1 for row in by_candidate[name]
                                          if row["predicted_boundary_count"] == 0),
            "failure_count": sum(row["status"] == "candidate_unit_failure"
                                 for row in by_candidate[name]),
            "secondary_scored_count": sum(row["secondary_status"] == "scored"
                                          for row in by_candidate[name]),
        }
        for name, metrics in aggregate_metrics.items()
    ]
    shortlist = rank_shortlist(aggregate_metrics, "collar_f1_3s", higher_better=True)
    metadata = {
        "evaluation_mode": context.evaluation_mode,
        "admitted_splits": sorted(splits),
        "unit_ids": sorted(references),
        "scorer": SCORER_DESCRIPTION,
        "diagnostic_only": context.run_namespace != "official",
    }
    write_json_artifact(context, "chapter.input_features", features, metadata=metadata)
    write_json_artifact(context, "chapter.candidate_status", candidate_status, metadata=metadata)
    write_stage_quartet(
        context, "chapter",
        predictions=predictions, per_unit_metrics=per_unit,
        aggregate=aggregate, shortlist=shortlist,
    )
    write_run_manifest(context)
    return {"units": len(units), "runnable": runnable, "status": candidate_status}


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", NOTEBOOK_ID, argv)
        summary = run(context)
        print(
            f"[OK] chaptering benchmark: {summary['units']} validation unit(s), "
            f"{len(summary['runnable'])} runnable candidate(s); "
            + ", ".join(f"{s['candidate']}={s['status']}" for s in summary["status"])
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] chaptering benchmark: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
