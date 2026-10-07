"""Error propagation benchmark runner for notebook 07b (smoke/full).

Re-runs downstream stages under controlled upstream perturbations.
Produces integration.perturbed_inputs and integration.error_propagation_metrics.
"""

from __future__ import annotations

import copy
import math
import random
from typing import Any, Sequence

from experiments.scripts.benchmark_artifacts import (
    parse_context,
    read_json_artifact,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.stage_benchmark_helpers import (
    collar_boundary_f1,
    load_eligible_units,
    mean,
)


# ---------------------------------------------------------------------------
# Perturbation functions — each takes a list of prediction records and
# returns a perturbed copy without mutating the originals.
# ---------------------------------------------------------------------------


def _perturb_none(records: list[dict]) -> list[dict]:
    """Identity perturbation — baseline, no changes."""
    return copy.deepcopy(records)


def _perturb_drop_fraction(records: list[dict], fraction: float = 0.5) -> list[dict]:
    """Drop a fraction of prediction records uniformly at random."""
    rng = random.Random(42)
    keep_n = max(1, int(len(records) * (1 - fraction)))
    subset = rng.sample(records, min(keep_n, len(records)))
    return copy.deepcopy(subset)


def _perturb_shift_boundaries(records: list[dict], jitter_sec: float = 5.0) -> list[dict]:
    """Add Gaussian jitter to boundary timestamps."""
    rng = random.Random(42)
    perturbed: list[dict] = []
    for rec in records:
        r = copy.deepcopy(rec)
        preds = r.get("predictions") or {}
        for key in ("boundaries_sec", "chapter_boundaries_sec"):
            if key in preds:
                preds[key] = [
                    max(0.0, b + rng.gauss(0, jitter_sec))
                    for b in preds[key]
                ]
        perturbed.append(r)
    return perturbed


def _perturb_corrupt_text(records: list[dict], drop_rate: float = 0.3) -> list[dict]:
    """Drop words from hypothesis text to simulate ASR errors."""
    rng = random.Random(42)
    perturbed: list[dict] = []
    for rec in records:
        r = copy.deepcopy(rec)
        preds = r.get("predictions") or {}
        for key in ("hypothesis",):
            if key in preds:
                words = str(preds[key]).split()
                kept = [w for w in words if rng.random() > drop_rate]
                preds[key] = " ".join(kept)
        perturbed.append(r)
    return perturbed


_PERTURBATIONS = {
    "baseline": _perturb_none,
    "drop_50pct": lambda recs: _perturb_drop_fraction(recs, 0.5),
    "boundary_jitter_5s": lambda recs: _perturb_shift_boundaries(recs, 5.0),
    "text_corrupt_30pct": lambda recs: _perturb_corrupt_text(recs, 0.3),
}

_PERTURBATIONS_SMOKE = {
    "baseline": _perturb_none,
    "drop_50pct": lambda recs: _perturb_drop_fraction(recs, 0.5),
}


# ---------------------------------------------------------------------------
# Downstream impact measurement
# ---------------------------------------------------------------------------


def _measure_scene_impact(
    original_records: list[dict],
    perturbed_records: list[dict],
    units: list[dict[str, Any]],
) -> dict[str, float]:
    """Compare F1 of perturbed vs original scene boundaries."""
    orig_by_unit = {
        str(r.get("unit_id")): [
            float(b)
            for b in r.get("predictions", {}).get("boundaries_sec", [])
        ]
        for r in original_records
    }
    pert_by_unit = {
        str(r.get("unit_id")): [
            float(b)
            for b in r.get("predictions", {}).get("boundaries_sec", [])
        ]
        for r in perturbed_records
    }
    f1_deltas: list[float] = []
    for unit in units:
        uid = str(unit["unit_id"])
        ref = [float(b) for b in (unit.get("scene_boundaries_sec") or [])]
        if not ref:
            ref = orig_by_unit.get(uid, [0.0])
        orig_f1 = collar_boundary_f1(orig_by_unit.get(uid, []), ref, collar_sec=2.0)["boundary_f1"]
        pert_f1 = collar_boundary_f1(pert_by_unit.get(uid, []), ref, collar_sec=2.0)["boundary_f1"]
        f1_deltas.append(pert_f1 - orig_f1)
    return {
        "mean_f1_delta": mean(f1_deltas) if f1_deltas else 0.0,
        "n_units": float(len(f1_deltas)),
    }


def _measure_asr_impact(
    original_records: list[dict],
    perturbed_records: list[dict],
) -> dict[str, float]:
    """Measure word-count ratio after text corruption."""
    orig_lengths: list[float] = []
    pert_lengths: list[float] = []
    for r in original_records:
        hyp = str(r.get("predictions", {}).get("hypothesis") or "")
        orig_lengths.append(float(len(hyp.split())))
    for r in perturbed_records:
        hyp = str(r.get("predictions", {}).get("hypothesis") or "")
        pert_lengths.append(float(len(hyp.split())))
    orig_mean = mean(orig_lengths) if orig_lengths else 0.0
    pert_mean = mean(pert_lengths) if pert_lengths else 0.0
    return {
        "mean_word_retention": pert_mean / orig_mean if orig_mean > 0 else 0.0,
        "n_records_original": float(len(orig_lengths)),
        "n_records_perturbed": float(len(pert_lengths)),
    }


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "07b_error_propagation", argv)
        units = load_eligible_units(context)

        # Read required upstream artifacts
        read_json_artifact(context, "selection.stage_shortlists")
        asr_payload = read_json_artifact(context, "asr.raw_predictions")
        scene_payload = read_json_artifact(context, "scene.raw_predictions")
        read_json_artifact(context, "ocr.raw_predictions")
        read_json_artifact(context, "detection.raw_predictions")
        read_json_artifact(context, "tracking.raw_predictions")

        perturbations = (
            _PERTURBATIONS_SMOKE if context.profile == "smoke" else _PERTURBATIONS
        )

        perturbed_input_records: list[dict[str, Any]] = []
        propagation_metric_records: list[dict[str, Any]] = []

        asr_original = list(asr_payload.get("records", []))
        scene_original = list(scene_payload.get("records", []))

        for pert_name, pert_fn in perturbations.items():
            asr_perturbed = pert_fn(asr_original)
            scene_perturbed = pert_fn(scene_original)

            perturbed_input_records.append(
                {
                    "perturbation": pert_name,
                    "stage": "asr",
                    "n_original": len(asr_original),
                    "n_perturbed": len(asr_perturbed),
                    "sample_perturbed": asr_perturbed[:1],
                }
            )
            perturbed_input_records.append(
                {
                    "perturbation": pert_name,
                    "stage": "scene",
                    "n_original": len(scene_original),
                    "n_perturbed": len(scene_perturbed),
                    "sample_perturbed": scene_perturbed[:1],
                }
            )

            scene_impact = _measure_scene_impact(scene_original, scene_perturbed, units)
            asr_impact = _measure_asr_impact(asr_original, asr_perturbed)

            propagation_metric_records.append(
                {
                    "perturbation": pert_name,
                    "downstream_stage": "scene_boundary",
                    "metrics": scene_impact,
                }
            )
            propagation_metric_records.append(
                {
                    "perturbation": pert_name,
                    "downstream_stage": "asr_text",
                    "metrics": asr_impact,
                }
            )

        write_json_artifact(context, "integration.perturbed_inputs", perturbed_input_records)
        write_json_artifact(
            context, "integration.error_propagation_metrics", propagation_metric_records
        )
        write_run_manifest(context)
        print(
            f"[OK] error propagation: {len(units)} unit(s), "
            f"{len(perturbations)} perturbation(s)"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] error propagation: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
