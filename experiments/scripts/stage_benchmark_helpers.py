"""Shared helpers for Phase 1 stage smoke/full benchmark runners."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from experiments.evaluation.metrics import asr_wer_cer, boundary_prf, cer, normalize_text, tokenize_words
from experiments.scripts.benchmark_artifacts import RunnerContext, read_json_artifact, write_json_artifact


KNOWN_SPLITS = frozenset({"train", "validation", "final_test"})

_NOTEBOOK_TO_ENDPOINTS: dict[str, set[str]] = {
    "01a_asr_model_benchmark": {"asr_benchmark", "asr"},
    "01c_asr_architecture_benchmark": {"asr_benchmark", "asr"},
    "01b_asr_preprocessing_ablation": {"asr_benchmark", "asr", "asr_preprocessing_ablation"},
    "02a_scene_boundary_benchmark": {"scene_boundary_benchmark", "scene"},
    "02b_keyframe_selection_benchmark": {"keyframe_selection_benchmark", "keyframe"},
    "02c_ocr_benchmark": {"ocr_benchmark", "ocr"},
    "02d_visual_caption_benchmark": {"visual_caption_benchmark", "caption"},
    "03a_object_detection_benchmark": {"object_detection_benchmark", "detection"},
    "03b_multi_object_tracking_benchmark": {"multi_object_tracking_benchmark", "tracking"},
    "04a_chaptering_benchmark": {"chaptering_benchmark", "chapter"},
    "04b_chaptering_modality_ablation": {"chaptering_modality_ablation", "chapter"},
    "05a_summarization_benchmark": {"summarization_benchmark", "summary"},
    "05b_summary_factuality_and_human_eval": {"summary_evidence_evaluation", "summary"},
    "06a_retrieval_benchmark": {"retrieval_benchmark", "retrieval"},
    "06b_qa_generation_benchmark": {"qa_generation_benchmark", "qa"},
    "08b_end_to_end_system": {"end_to_end_system"},
}

_ASR_DIAGNOSTIC_NOTEBOOKS = frozenset({
    "01a_asr_model_benchmark", "01b_asr_preprocessing_ablation",
    "01c_asr_architecture_benchmark",
})

_COMPOSITE_REQUIRED_ENDPOINTS: dict[str, tuple[set[str], ...]] = {
    "07b_error_propagation": (
        {"asr_benchmark", "asr"},
        {"scene_boundary_benchmark", "scene"},
        {"ocr_benchmark", "ocr"},
        {"object_detection_benchmark", "detection"},
        {"multi_object_tracking_benchmark", "tracking"},
    ),
    "08a_stage_compatibility": (
        {"asr_benchmark", "asr"},
        {"scene_boundary_benchmark", "scene"},
        {"keyframe_selection_benchmark", "keyframe"},
        {"ocr_benchmark", "ocr"},
        {"visual_caption_benchmark", "caption"},
        {"object_detection_benchmark", "detection"},
        {"multi_object_tracking_benchmark", "tracking"},
        {"chaptering_benchmark", "chapter"},
        {"summarization_benchmark", "summary"},
        {"retrieval_benchmark", "retrieval"},
        {"qa_generation_benchmark", "qa"},
    ),
    "08b_end_to_end_system": (
        {"asr_benchmark", "asr"},
        {"scene_boundary_benchmark", "scene"},
        {"summarization_benchmark", "summary"},
        {"qa_generation_benchmark", "qa"},
    ),
}


def load_eligible_units(
    context: RunnerContext,
    endpoint: str | None = None,
    *,
    allow_fixture_without_matrix: bool = False,
    limit_smoke: bool = True,
    allowed_splits: frozenset[str] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return frozen units eligible for the requested run namespace.

    Enforces fail-closed endpoint eligibility:
    - Reads and verifies dataset.endpoint_matrix through the receipt/artifact system.
    - Requires endpoint matrix for official/full runs; missing or malformed matrix fails closed.
    - Intersects endpoint allowlist with frozen records marked eligible.
    - Only diagnostic runs may use an explicit diagnostic eligibility flag;
      official runs always require scientific eligibility.

    When ``allowed_splits`` is given, every frozen unit must declare a known
    split and only units in the allowlist are returned.  The split filter runs
    before smoke truncation, so manifest ordering can never expose a unit from a
    sealed split (e.g. ``final_test`` during selection).
    """
    if allowed_splits is not None:
        allowed_splits = frozenset(allowed_splits)
        unknown = allowed_splits - KNOWN_SPLITS
        if not allowed_splits or unknown:
            raise RuntimeError(f"invalid split allowlist {sorted(allowed_splits)}")
    frozen = read_json_artifact(context, "dataset.frozen_manifest")
    registry = read_json_artifact(context, "dataset.registry")
    approved_tedlium_screen_signatures: set[tuple[str, str]] = set()

    def metadata_screen_signature(record: dict[str, Any]) -> tuple[str, str] | None:
        if record.get("train_evaluation_media_audit_status") != "metadata_screened_audio_overlap_unverified":
            return None
        metadata_hash, media_hash = record.get("metadata_cohort_sha256"), record.get("media_cohort_sha256")
        if (not isinstance(metadata_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", metadata_hash)
                or not isinstance(media_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", media_hash)):
            return None
        return metadata_hash, media_hash

    def metadata_screen_signatures(records: Any) -> set[tuple[str, str]]:
        return {signature for record in records if isinstance(record, dict)
                if (signature := metadata_screen_signature(record)) is not None
                and record.get("dataset_id") == "tedlium3"}

    def selection_eligible(record: dict[str, Any]) -> bool:
        needs_tedlium_diagnostic_screen = (
            record.get("dataset_id") == "tedlium3"
            and context.notebook_id in _ASR_DIAGNOSTIC_NOTEBOOKS
        )
        if needs_tedlium_diagnostic_screen:
            return (
                context.run_namespace == "diagnostic"
                and record.get("scientific_selection_eligible") is False
                and record.get("diagnostic_selection_eligible") is True
                and metadata_screen_signature(record) in approved_tedlium_screen_signatures
            )
        if record.get("scientific_selection_eligible") is True:
            return True
        eligible = (
            context.run_namespace == "diagnostic"
            and record.get("diagnostic_selection_eligible") is True
        )
        return eligible

    target_endpoints: set[str]
    is_composite = False
    composite_endpoint_sets: tuple[set[str], ...] = ()

    if endpoint:
        target_endpoints = {endpoint}
    elif context.notebook_id in _COMPOSITE_REQUIRED_ENDPOINTS:
        is_composite = True
        composite_endpoint_sets = _COMPOSITE_REQUIRED_ENDPOINTS[context.notebook_id]
        target_endpoints = set().union(*composite_endpoint_sets)
    elif context.notebook_id in _NOTEBOOK_TO_ENDPOINTS:
        target_endpoints = _NOTEBOOK_TO_ENDPOINTS[context.notebook_id]
    else:
        target_endpoints = {context.notebook_id}

    ep_receipt_path = context.namespace_root / "dataset.endpoint_matrix.receipt.json"
    is_official_or_full = (context.run_namespace == "official" or context.profile == "full")

    allowed_dataset_ids: set[str]
    if not ep_receipt_path.is_file():
        if is_official_or_full:
            raise RuntimeError(
                f"missing required dataset.endpoint_matrix receipt at {ep_receipt_path} "
                f"for official/full run of {context.notebook_id}"
            )
        if not allow_fixture_without_matrix:
            raise RuntimeError(
                f"missing dataset.endpoint_matrix receipt at {ep_receipt_path}; "
                f"fail-closed: explicit endpoint matrix is required"
            )
        # Explicit opt-in fixture fallback only
        allowed_dataset_ids = {
            str(r.get("dataset_id"))
            for r in frozen.get("records", [])
            if r.get("freeze_status") == "eligible" and selection_eligible(r)
        }
    else:
        try:
            ep_payload = read_json_artifact(context, "dataset.endpoint_matrix")
        except Exception as exc:
            raise RuntimeError(
                f"failed to read or validate dataset.endpoint_matrix artifact: {exc}"
            ) from exc

        ep_records = ep_payload.get("records")
        if not isinstance(ep_records, list):
            raise RuntimeError("dataset.endpoint_matrix payload must contain a 'records' list")

        frozen_signatures = metadata_screen_signatures(frozen.get("records", []))
        registry_signatures = metadata_screen_signatures(registry.get("records", []))
        endpoint_signatures = metadata_screen_signatures(ep_records)
        approved_tedlium_screen_signatures.update(
            frozen_signatures & registry_signatures & endpoint_signatures)

        for idx, rec in enumerate(ep_records):
            if not isinstance(rec, dict):
                raise RuntimeError(f"dataset.endpoint_matrix record {idx} is not a dict")
            dataset_id = rec.get("dataset_id")
            endpoint_id = rec.get("endpoint")
            eligible = rec.get("scientific_selection_eligible")
            if not isinstance(dataset_id, str) or not dataset_id.strip():
                raise RuntimeError(
                    f"dataset.endpoint_matrix record {idx} requires a non-empty string dataset_id"
                )
            if not isinstance(endpoint_id, str) or not endpoint_id.strip():
                raise RuntimeError(
                    f"dataset.endpoint_matrix record {idx} requires a non-empty string endpoint"
                )
            if not isinstance(eligible, bool):
                raise RuntimeError(
                    f"dataset.endpoint_matrix record {idx} requires boolean scientific_selection_eligible"
                )
            diagnostic_eligible = rec.get("diagnostic_selection_eligible")
            if diagnostic_eligible is not None and not isinstance(diagnostic_eligible, bool):
                raise RuntimeError(
                    f"dataset.endpoint_matrix record {idx} requires boolean diagnostic_selection_eligible"
                )

        if is_composite:
            composite_allowed: set[str] | None = None
            for ep_set in composite_endpoint_sets:
                matching = {
                    str(r["dataset_id"])
                    for r in ep_records
                    if r.get("endpoint") in ep_set and selection_eligible(r)
                }
                if composite_allowed is None:
                    composite_allowed = matching
                else:
                    composite_allowed &= matching
            allowed_dataset_ids = composite_allowed if composite_allowed is not None else set()
        else:
            allowed_dataset_ids = {
                str(r["dataset_id"])
                for r in ep_records
                if r.get("endpoint") in target_endpoints and selection_eligible(r)
            }

    if context.notebook_id in _ASR_DIAGNOSTIC_NOTEBOOKS:
            screened_registry_ids = {
            str(record.get("dataset_id")) for record in registry.get("records", [])
            if isinstance(record, dict) and (record.get("dataset_id") != "tedlium3"
                or metadata_screen_signature(record) in approved_tedlium_screen_signatures)
        }
            allowed_dataset_ids.intersection_update(screened_registry_ids)

    units: list[dict[str, Any]] = []
    for record in frozen.get("records", []):
        if record.get("freeze_status") != "eligible":
            continue
        if not selection_eligible(record):
            continue
        dataset_id = str(record.get("dataset_id") or "unknown")
        if dataset_id not in allowed_dataset_ids:
            continue
        unit_ids = record.get("unit_ids") or []
        if not unit_ids:
            continue
        embedded = {
            str(item.get("unit_id")): item
            for item in (record.get("unit_records") or [])
            if isinstance(item, dict) and item.get("unit_id")
        }
        for unit_id in unit_ids:
            key = str(unit_id)
            spec = dict(embedded.get(key) or {"unit_id": key})
            spec.setdefault("unit_id", key)
            spec.setdefault("dataset_id", dataset_id)
            if allowed_splits is not None:
                split = spec.get("split")
                if split not in KNOWN_SPLITS:
                    raise RuntimeError(
                        f"unit {key!r} has no valid split ({split!r}); "
                        "split-scoped loading fails closed"
                    )
                if split not in allowed_splits:
                    continue
            units.append(spec)
    if not units:
        scope = f" in splits {sorted(allowed_splits)}" if allowed_splits is not None else ""
        raise RuntimeError(
            f"no {('diagnostically or scientifically' if context.run_namespace == 'diagnostic' else 'scientifically')} eligible frozen units for endpoint in "
            f"{sorted(target_endpoints)}{scope}"
        )
    if context.profile == "smoke" and limit_smoke:
        return units[:1]
    return units


def require_media(unit: dict[str, Any], *keys: str) -> Path:
    for key in keys:
        value = unit.get(key)
        if not value:
            continue
        path = Path(str(value))
        if path.is_file():
            return path.resolve()
    raise RuntimeError(
        f"unit {unit.get('unit_id')!r} is missing readable media "
        f"(tried {', '.join(keys)})"
    )


def write_stage_quartet(
    context: RunnerContext,
    stage: str,
    *,
    predictions: list[dict[str, Any]],
    per_unit_metrics: list[dict[str, Any]],
    aggregate: list[dict[str, Any]],
    shortlist: list[dict[str, Any]],
) -> None:
    write_json_artifact(context, f"{stage}.raw_predictions", predictions)
    write_json_artifact(context, f"{stage}.per_unit_metrics", per_unit_metrics)
    write_json_artifact(context, f"{stage}.aggregate", aggregate)
    write_json_artifact(context, f"{stage}.shortlist", shortlist)


def mean(values: Iterable[float]) -> float:
    items = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not items:
        raise ValueError("no finite values to average")
    return sum(items) / len(items)


def rank_shortlist(
    candidate_metrics: dict[str, dict[str, float]],
    primary: str,
    *,
    higher_better: bool,
) -> list[dict[str, Any]]:
    ordered = sorted(
        candidate_metrics.items(),
        key=lambda item: item[1][primary],
        reverse=higher_better,
    )
    if not ordered:
        raise ValueError("shortlist requires at least one candidate")
    rows: list[dict[str, Any]] = []
    for rank, (candidate, metrics) in enumerate(ordered, start=1):
        rows.append(
            {
                "rank": rank,
                "candidate": candidate,
                "metrics": metrics,
                "selected": rank == 1,
                "primary_metric": primary,
            }
        )
    return rows


def corpus_wer(pairs: Sequence[tuple[str, str]]) -> float:
    refs = " ".join(normalize_text(ref) for ref, _ in pairs)
    hyps = " ".join(normalize_text(hyp) for _, hyp in pairs)
    return float(asr_wer_cer(refs, hyps)["wer"])


def collar_boundary_f1(
    pred: Sequence[float],
    ref: Sequence[float],
    *,
    collar_sec: float = 2.0,
) -> dict[str, float]:
    scores = boundary_prf(pred, ref, tolerance_sec=collar_sec)
    return {
        "boundary_f1": float(scores["f1"]),
        "boundary_precision": float(scores["precision"]),
        "boundary_recall": float(scores["recall"]),
        "matched_mae": float(scores["mae"]) if math.isfinite(float(scores["mae"])) else 0.0,
        "collar_sec": collar_sec,
    }


def required_scene_f1(
    selected_scene_ids: Sequence[str],
    required_scene_ids: Sequence[str],
) -> dict[str, float]:
    selected = {str(item) for item in selected_scene_ids}
    required = {str(item) for item in required_scene_ids}
    if not required:
        raise ValueError("required_scene_ids cannot be empty for keyframe scoring")
    tp = len(selected & required)
    fp = len(selected - required)
    fn = len(required - selected)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "required_scene_f1": f1,
        "keyframe_precision": precision,
        "scene_coverage": recall,
    }


def detection_hmean(pred_boxes: Sequence[Sequence[float]], ref_boxes: Sequence[Sequence[float]]) -> float:
    """Greedy IoU@0.5 Hmean for axis-aligned boxes [x0,y0,x1,y1]."""
    preds = [tuple(map(float, box)) for box in pred_boxes]
    refs = [tuple(map(float, box)) for box in ref_boxes]
    if not preds and not refs:
        return 1.0
    if not preds or not refs:
        return 0.0

    def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
        x0 = max(a[0], b[0])
        y0 = max(a[1], b[1])
        x1 = min(a[2], b[2])
        y1 = min(a[3], b[3])
        inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
        if inter <= 0:
            return 0.0
        area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
        area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
        denom = area_a + area_b - inter
        return inter / denom if denom > 0 else 0.0

    used: set[int] = set()
    tp = 0
    for pred in preds:
        best_j = None
        best = 0.0
        for index, ref in enumerate(refs):
            if index in used:
                continue
            score = iou(pred, ref)
            if score >= 0.5 and score > best:
                best = score
                best_j = index
        if best_j is not None:
            used.add(best_j)
            tp += 1
    precision = tp / len(preds)
    recall = tp / len(refs)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def simple_cider(hypothesis: str, references: Sequence[str]) -> float:
    """Lightweight CIDEr-style TF-IDF cosine over 1-4 grams."""
    hyp_tokens = tokenize_words(hypothesis)
    ref_token_lists = [tokenize_words(ref) for ref in references if str(ref).strip()]
    if not hyp_tokens or not ref_token_lists:
        return 0.0

    def ngrams(tokens: Sequence[str], order: int) -> Counter[str]:
        return Counter(
            " ".join(tokens[i : i + order])
            for i in range(max(0, len(tokens) - order + 1))
        )

    scores: list[float] = []
    for order in (1, 2, 3, 4):
        hyp = ngrams(hyp_tokens, order)
        if not hyp:
            scores.append(0.0)
            continue
        ref_counters = [ngrams(tokens, order) for tokens in ref_token_lists]
        df = Counter()
        for counter in ref_counters:
            df.update(counter.keys())
        doc_count = len(ref_counters)

        def tfidf(counter: Counter[str]) -> dict[str, float]:
            total = sum(counter.values()) or 1
            return {
                gram: (count / total) * math.log((doc_count + 1) / (1 + df.get(gram, 0)))
                for gram, count in counter.items()
            }

        hyp_vec = tfidf(hyp)
        ref_vecs = [tfidf(counter) for counter in ref_counters]

        def cosine(a: dict[str, float], b: dict[str, float]) -> float:
            keys = set(a) | set(b)
            if not keys:
                return 0.0
            dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
            na = math.sqrt(sum(v * v for v in a.values()))
            nb = math.sqrt(sum(v * v for v in b.values()))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        scores.append(mean(cosine(hyp_vec, ref_vec) for ref_vec in ref_vecs))
    return mean(scores)


def grounded_claim_f1(hypothesis: str, claims: Sequence[str]) -> float:
    hyp = set(tokenize_words(hypothesis))
    claim_tokens = [set(tokenize_words(claim)) for claim in claims if str(claim).strip()]
    if not claim_tokens:
        return 0.0
    scores = []
    for tokens in claim_tokens:
        if not tokens:
            scores.append(0.0)
            continue
        tp = len(hyp & tokens)
        precision = tp / len(hyp) if hyp else 0.0
        recall = tp / len(tokens)
        scores.append(
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        )
    return mean(scores)


def recognition_cer(reference: str, hypothesis: str) -> float:
    return float(cer(reference, hypothesis))
