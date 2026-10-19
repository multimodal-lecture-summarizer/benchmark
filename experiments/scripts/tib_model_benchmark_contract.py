"""Offline development contracts; importing this module never loads a model."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "registry/models/tib-summarization-pipelines-v1.json"
EXPECTED_IDS = frozenset({"lead3", "lexrank", "bart", "led", "qwen3"})


def load_registry(path: Path = REGISTRY) -> dict:
    """Reject drift between the five pipelines and their model/control roles."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    candidates = registry["pipelines"]
    ids = [row["candidate_id"] for row in candidates]
    if len(ids) != len(set(ids)) or set(ids) != EXPECTED_IDS:
        raise ValueError("Registry must contain five distinct declared pipeline IDs")
    by_id = {row["candidate_id"]: row for row in candidates}
    control = by_id["lead3"]
    if (control["role"], control["generation_device"], control["config_search"]) != (
        "fixed_control", "cpu", False
    ):
        raise ValueError("Lead-3 must remain a fixed CPU control without config search")
    if any(by_id[key]["role"] != "model_family" for key in EXPECTED_IDS - {"lead3"}):
        raise ValueError("Only the other four IDs belong to model-family selection")
    if by_id["lexrank"]["generation_device"] != "cpu":
        raise ValueError("LexRank generation is CPU")
    if any(by_id[key]["generation_device"] != "cuda" for key in ("bart", "led", "qwen3")):
        raise ValueError("Neural generator resource devices must be explicit")
    if (registry["canonical_input"] != "transcript"
            or registry["segments_role"] != "audit_sidecar"
            or registry["prompt_timestamps"] is not False):
        raise ValueError("Primary input contract changed")
    cap = registry["global_output_word_cap"]
    if cap is not None and (type(cap) is not int or cap <= 0):
        raise ValueError("Global word cap is UNSET or a positive integer")
    return registry


def comparison_contract(registry: dict) -> dict:
    """A common source for later masks, pair ledgers and resource reporting."""
    rows = registry["pipelines"]
    ids = sorted(row["candidate_id"] for row in rows)
    models = sorted(row["candidate_id"] for row in rows if row["role"] == "model_family")
    return {
        "candidate_ids": ids,
        "config_selection_family_ids": models,
        "between_family_candidate_ids": ids,
        "recommendation_ids": models,
        "paired_contrasts": [list(pair) for pair in combinations(ids, 2)],
        "generation_devices": {row["candidate_id"]: row["generation_device"] for row in rows},
        "state": "development_unsealed",
    }


def reference_disposition(reference: str, *, label: str = "B", evidence: str = "",
                          rights_pass: bool = False, structure_pass: bool = False) -> dict:
    """Apply proposed semantics, not automatic semantic annotation or cohort seal.

    Unreviewed nonempty abstracts remain B, including short/reused abstracts.
    Callers supply only pre-outcome evidence; model scores are not inputs.
    """
    if not isinstance(reference, str) or label not in {"A", "B", "C"}:
        raise ValueError("String reference and A/B/C label required")
    if type(rights_pass) is not bool or type(structure_pass) is not bool:
        raise ValueError("Rights and structure gates require explicit booleans")
    if not reference.strip():
        label, evidence = "C", "empty_reference"
    elif label in {"A", "C"} and not evidence.strip():
        raise ValueError("Nonempty A/C decisions require pre-outcome review evidence")
    scorable = label in {"A", "B"}
    if not rights_pass or not structure_pass:
        status = "HOLD"
    elif not scorable:
        status = "excluded"
    else:
        status = "flagged" if label == "B" else "eligible"
    return {
        "reference_usability": label,
        "reference_reason": evidence or "unreviewed_uncertain",
        "reference_policy_state": "proposed_uncalibrated",
        "reference_based_scoring_allowed": scorable,
        "primary_eligible": scorable and rights_pass and structure_pass,
        "eligibility_status": status,
    }
