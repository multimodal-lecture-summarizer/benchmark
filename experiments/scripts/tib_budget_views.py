"""Budget views: sentence prefixes of one stored raw output, reference-free."""
from __future__ import annotations

from experiments.scripts.tib_benchmark_output import select_delivered

# Ratified 2026-10-22; the contract cap stays the absolute maximum.
PRIMARY_BUDGETS = {"S": 60, "M": 120, "L": 240}
CONTRACT_CAP = 350


def build_views(raw_text: str, budgets: dict[str, int] | None = None,
                contract_cap: int = CONTRACT_CAP) -> dict[str, dict]:
    """Return the delivered text for each budget plus the contract-cap view.

    Every view reuses the common delivery selector, so a view is always a
    complete-sentence prefix of the raw output (or a flagged word cut). The
    views are nested by construction; they measure the first N words, not the
    ability to write an N-word summary.
    """
    budgets = dict(PRIMARY_BUDGETS if budgets is None else budgets)
    if not budgets or any(type(v) is not int or v < 1 for v in budgets.values()):
        raise ValueError("budgets must be positive integers")
    if max(budgets.values()) > contract_cap:
        raise ValueError("a budget exceeds the contract cap")
    if sorted(budgets.values()) != list(budgets.values()):
        raise ValueError("budgets must be listed in increasing order")
    views = {name: select_delivered(raw_text, cap) for name, cap in budgets.items()}
    views["contract"] = select_delivered(raw_text, contract_cap)
    return views
