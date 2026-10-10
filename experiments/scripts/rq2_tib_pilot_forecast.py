"""Conservative runtime planning from complete paired development timings."""

import math
from statistics import mean

from experiments.scripts.rq2_tib_pilot_cohort import STRATA


def _seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def forecast_pilot(rows, *, initialization_seconds, population_by_stratum,
                   safety_factor=1.3, budget_hours=12, hardware_consistent=True,
                   length_range_covered=True, io_retry_seconds=0):
    """Forecast both arms plus scoring/preparation/checkpoints, without selection.

    Range uses observed per-stratum min/max, not a confidence interval. Callers
    must reject resumed, heterogeneous or unobserved-stage profiles. Additional
    I/O/retry allowance is explicit; the safety factor also covers uncertainty.
    """
    problems = []
    if not _seconds(initialization_seconds) or not _seconds(io_retry_seconds):
        problems.append("unknown_initialization_or_io_retry_cost")
    if not _seconds(safety_factor) or safety_factor < 1:
        raise ValueError("Safety factor must be finite and >= 1")
    if not _seconds(budget_hours) or budget_hours <= 0:
        raise ValueError("Budget must be finite and positive")
    if not hardware_consistent:
        problems.append("heterogeneous_hardware")
    if not length_range_covered:
        problems.append("target_length_outside_pilot_range")
    if set(population_by_stratum) != set(STRATA) or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in population_by_stratum.values()):
        problems.append("invalid_target_population")
    timings = {s: [] for s in STRATA}
    ids = set()
    for row in rows:
        ident, name = row.get("id"), row.get("length_stratum")
        if not ident or ident in ids:
            problems.append("missing_or_duplicate_profile_id")
        ids.add(ident)
        if row.get("resumed") or row.get("profile_resumed"):
            problems.append("resumed_profile")
        if row.get("status") != "completed" or name not in timings:
            problems.append("incomplete_profile_or_unknown_stratum")
            continue
        costs = []
        for arm in ("S1", "S3"):
            profile = row.get("arms", {}).get(arm, {})
            if profile.get("status") != "completed" or profile.get("resumed") or not _seconds(profile.get("wall_seconds")):
                problems.append("missing_failed_or_resumed_arm")
            costs.append(profile.get("wall_seconds"))
        costs.extend(row.get(key) for key in
                     ("scoring_seconds", "shared_preparation_seconds", "checkpoint_seconds"))
        if any(not _seconds(v) for v in costs):
            problems.append("unknown_stage_cost")
        else:
            timings[name].append(sum(costs))
    if any(not values for values in timings.values()):
        problems.append("incomplete_three_stratum_coverage")
    result = {"status": "evidence_not_frozen", "credible_forecast": not problems,
              "blockers": sorted(set(problems)), "evaluation_cohort_frozen": False,
              "automatic_cohort_selection": False, "safety_factor": safety_factor,
              "budget_seconds": budget_hours * 3600,
              "range_interpretation": "observed_min_max_scenarios_not_statistical_confidence_interval"}
    if problems:
        return result
    init = initialization_seconds + io_retry_seconds
    estimate = lambda fn: safety_factor * (init + sum(
        population_by_stratum[s] * fn(timings[s]) for s in STRATA))
    point = estimate(mean)
    result.update(predicted_seconds=point, observed_scenario_range_seconds=[estimate(min), estimate(max)],
                  within_budget=estimate(max) <= budget_hours * 3600,
                  planning_means_seconds={s: mean(timings[s]) for s in STRATA},
                  population_by_stratum=dict(population_by_stratum),
                  decision="review_protocol_and_cohort_manually_before_freezing")
    return result
