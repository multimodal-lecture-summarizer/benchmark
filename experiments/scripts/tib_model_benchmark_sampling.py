"""Source-only deterministic development allocation with whole-group role isolation."""
from collections import Counter
import hashlib

STRATA = ("short", "medium", "long")


def stratum(words, cuts):
    return STRATA[sum(words > cut for cut in cuts)]


def quotas(target, counts, minimum):
    if sum(counts.values()) < target or any(counts.get(s, 0) < minimum for s in STRATA):
        raise ValueError("Insufficient source-length strata for frozen floors")
    weights = {s: target * counts[s] / sum(counts.values()) for s in STRATA}
    result = {s: int(weights[s]) for s in STRATA}
    for s in sorted(STRATA, key=lambda x: (-(weights[x] - result[x]), STRATA.index(x)))[:target - sum(result.values())]:
        result[s] += 1
    for s in STRATA:
        while result[s] < minimum:
            donor = max(STRATA, key=lambda x: (result[x] - minimum, -STRATA.index(x)))
            if result[donor] <= minimum:
                raise ValueError("Cannot satisfy source-length floors")
            result[donor] -= 1
            result[s] += 1
    return result


def sample_rows(rows, target, cuts, seed, *, extremes=False, minimum=3):
    bins = {s: [r for r in rows if stratum(r["source_words"], cuts) == s] for s in STRATA}
    allocation = quotas(target, {s: len(v) for s, v in bins.items()}, minimum)
    selected = []
    for s in STRATA:
        candidates = bins[s]
        forced = []
        if extremes:
            ordered = sorted(candidates, key=lambda r: (r["source_words"], r["record_id"]))
            forced = [ordered[0], ordered[-1]] if len(ordered) > 1 else ordered
        forced_ids = {r["record_id"] for r in forced}
        ordered = sorted((r for r in candidates if r["record_id"] not in forced_ids), key=lambda r: hashlib.sha256(f"{seed}|{r['record_id']}".encode()).hexdigest())
        selected.extend(forced + ordered[:allocation[s] - len(forced)])
    if len(selected) != target:
        raise ValueError("Unable to allocate exact development size")
    return sorted(selected, key=lambda r: r["record_id"]), allocation


def select_development(validation, cuts, seed="tib-development-261019-v1"):
    if any(row["split"] != "valid" for row in validation):
        raise ValueError("Development allocation accepts native validation only")
    pilot, pilot_quotas = sample_rows(validation, 40, cuts, seed + "|pilot", extremes=True)
    pilot_groups = {r["group_id"] for r in pilot}
    remaining = [r for r in validation if r["group_id"] not in pilot_groups]
    selection_n = 300 if len(remaining) >= 300 else 200 if len(remaining) >= 200 else None
    if selection_n is None:
        raise ValueError("Below 200 group-safe validation records after pilot; no test borrowing")
    selection, selection_quotas = sample_rows(remaining, selection_n, cuts, seed + "|selection", minimum=25)
    if pilot_groups & {r["group_id"] for r in selection}:
        raise ValueError("Pilot/selection group leakage")
    staged = [min(pilot, key=lambda r: (r["source_words"], r["record_id"])),
              sorted(pilot, key=lambda r: (r["source_words"], r["record_id"]))[len(pilot) // 2],
              max(pilot, key=lambda r: (r["source_words"], r["record_id"]))]
    return {"pilot": pilot, "selection": selection, "pilot_quotas": pilot_quotas,
            "selection_quotas": selection_quotas,
            "availability_after_pilot_group_reservation": len(remaining),
            "selection_fallback": selection_n == 200,
            "fallback_reason": "availability_below_300_after_pilot_group_reservation" if selection_n == 200 else None,
            "staged_pilot_ids": [r["record_id"] for r in staged]}
