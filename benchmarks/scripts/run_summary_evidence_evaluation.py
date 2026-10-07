"""Summary evidence evaluation runner for notebook 05b (smoke/full).

Audits claim support, evidence coverage and human label alignment
without generating new summaries.
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
    grounded_claim_f1,
    load_eligible_units,
    mean,
    simple_cider,
)


# ---------------------------------------------------------------------------
# Claim support helpers
# ---------------------------------------------------------------------------


def _claim_support_score(summary_text: str, claims: list[str]) -> float:
    """Fraction of claims that have at least one supporting token in the summary."""
    if not claims:
        return 1.0
    from experiments.evaluation.metrics import tokenize_words

    hyp_tokens = set(tokenize_words(summary_text))
    supported = 0
    for claim in claims:
        claim_tokens = set(tokenize_words(claim))
        if not claim_tokens:
            continue
        if hyp_tokens & claim_tokens:
            supported += 1
    return supported / len(claims)


def _evidence_coverage(summary_text: str, source_transcript: str) -> float:
    """Fraction of source content types present in summary (unigram overlap)."""
    if not source_transcript.strip():
        return 0.0
    from experiments.evaluation.metrics import tokenize_words

    src = set(tokenize_words(source_transcript))
    hyp = set(tokenize_words(summary_text))
    if not src:
        return 0.0
    return len(hyp & src) / len(src)


def _human_label_precision(summary_text: str, human_labels: list[str]) -> float:
    """Overlap between summary tokens and available human key-phrase labels."""
    if not human_labels:
        return 1.0  # no labels → not_eligible sentinel, pass through
    from experiments.evaluation.metrics import tokenize_words

    hyp = set(tokenize_words(summary_text))
    label_tokens = set()
    for label in human_labels:
        label_tokens.update(tokenize_words(label))
    if not label_tokens:
        return 1.0
    return len(hyp & label_tokens) / len(label_tokens)


# ---------------------------------------------------------------------------
# Factuality gate logic
# ---------------------------------------------------------------------------

_MIN_CLAIM_SUPPORT = 0.25   # at least 25% of claims supported
_MIN_EVIDENCE_COV = 0.05    # at least 5% unigram overlap with source


def _gate_passes(support: float, coverage: float) -> bool:
    return support >= _MIN_CLAIM_SUPPORT and coverage >= _MIN_EVIDENCE_COV


def main(argv: Sequence[str] | None = None) -> int:
    try:
        context = parse_context(__doc__ or "", "05b_summary_factuality_and_human_eval", argv)
        units = load_eligible_units(context)
        multimodal_pkg = read_json_artifact(context, "summary.multimodal_package")

        # Build unit_id → package record lookup
        pkg_by_unit: dict[str, dict] = {
            str(r["unit_id"]): r
            for r in multimodal_pkg.get("records", [])
        }

        evidence_metrics_records: list[dict[str, Any]] = []
        gate_records: list[dict[str, Any]] = []
        human_audit_records: list[dict[str, Any]] = []

        unit_gates: list[bool] = []

        for unit in units:
            uid = str(unit["unit_id"])
            pkg = pkg_by_unit.get(uid, {})
            summary_text = str(pkg.get("text_summary_10pct") or "")
            if not summary_text.strip():
                raise RuntimeError(
                    f"unit {uid!r} has no text_summary_10pct in summary.multimodal_package"
                )

            source_transcript = str(
                unit.get("reference_text") or unit.get("transcript") or ""
            )
            grounded_claims = [str(c) for c in (unit.get("grounded_claims") or []) if str(c).strip()]
            human_labels = [str(l) for l in (unit.get("human_labels") or []) if str(l).strip()]
            references = [str(r) for r in (unit.get("summary_references") or []) if str(r).strip()]
            if not references and source_transcript:
                references = [source_transcript]

            support = _claim_support_score(summary_text, grounded_claims)
            coverage = _evidence_coverage(summary_text, source_transcript)
            cider = simple_cider(summary_text, references) if references else 0.0
            claim_f1 = grounded_claim_f1(summary_text, grounded_claims) if grounded_claims else 1.0
            human_prec = _human_label_precision(summary_text, human_labels)
            passes = _gate_passes(support, coverage)
            unit_gates.append(passes)

            evidence_metrics_records.append(
                {
                    "unit_id": uid,
                    "dataset_id": unit.get("dataset_id"),
                    "claim_support_rate": support,
                    "evidence_coverage": coverage,
                    "cider": cider,
                    "grounded_claim_f1": claim_f1,
                    "n_claims": len(grounded_claims),
                    "gate_passes": passes,
                }
            )
            gate_records.append(
                {
                    "unit_id": uid,
                    "factuality_gate": "pass" if passes else "fail",
                    "claim_support_rate": support,
                    "evidence_coverage": coverage,
                    "min_claim_support_threshold": _MIN_CLAIM_SUPPORT,
                    "min_evidence_coverage_threshold": _MIN_EVIDENCE_COV,
                }
            )
            human_audit_records.append(
                {
                    "unit_id": uid,
                    "human_label_precision": human_prec,
                    "n_human_labels": len(human_labels),
                    "human_labels_available": len(human_labels) > 0,
                    "summary_word_count": len(summary_text.split()),
                }
            )

        write_json_artifact(context, "summary.evidence_metrics", evidence_metrics_records)
        write_json_artifact(context, "summary.factuality_gate", gate_records)
        write_json_artifact(context, "summary.human_label_audit", human_audit_records)
        write_run_manifest(context)

        n_pass = sum(unit_gates)
        print(
            f"[OK] summary evidence evaluation: {len(units)} unit(s), "
            f"gate pass {n_pass}/{len(units)}"
        )
        return 0
    except Exception as exc:
        print(f"[FAIL] summary evidence evaluation: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
