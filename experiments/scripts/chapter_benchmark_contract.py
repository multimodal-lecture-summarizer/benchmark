"""Shared RQ1 chaptering contract for the 04a/04b runners.

Single source of truth for:

* evaluation mode -> admitted split (selection = validation only);
* independent chapter GT validation for chapter scoring;
* the hash-bound ``chapter.input_features`` record per lecture unit;
* the frozen RQ1 scorer: primary collar F1 at +/-3 s, secondary +/-5/10 s,
  Pk and WindowDiff;
* learned-checkpoint identity checks (C5/C6 are ``not_run`` without a
  train-only provenance manifest).

Nothing here substitutes scene cuts, clip joins, predictions or duration
midpoints for chapter GT, and empty predictions are scored as empty.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.metrics.chapter_metrics import (
    boundaries_to_binary_sequence,
    collar_f1,
    pk_metric,
    window_diff,
)

CHAPTER_CONTRACT_VERSION = "rq1-chapter-contract/1"
PRIMARY_COLLAR_SEC = 3.0
SECONDARY_COLLARS_SEC = (5.0, 10.0)
PK_WD_STEP_SEC = 1.0
EMPTY_PREDICTION_POLICY = "score_as_zero_boundaries"

EVALUATION_MODE_SPLITS: dict[str, frozenset[str]] = {
    "selection": frozenset({"validation"}),
    "final_test": frozenset({"final_test"}),
}

MODALITIES = ("transcript", "ocr", "scene", "visual", "acoustic")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LEARNED_CHECKPOINTS: dict[str, Path] = {
    "C5_cross_attention": PROJECT_ROOT / "checkpoints" / "c5_real.pt",
    "C6_late_fusion": PROJECT_ROOT / "checkpoints" / "c6_real.pt",
}
CHECKPOINT_PROVENANCE_FIELDS = (
    "candidate", "architecture", "code_sha256", "seed", "train_dataset_id",
    "train_unit_ids", "train_course_ids", "train_data_sha256", "checkpoint_sha256",
)


class ChapterContractError(RuntimeError):
    """Raised when a chaptering run cannot satisfy the RQ1 contract."""


CHAPTER_GT_REQUIRED_FIELDS = (
    "source", "revision", "annotation_origin", "timestamp_convention",
)
CHAPTER_GT_ALLOWED_ORIGINS = frozenset({
    "author_released_segments", "publisher_timed_toc", "creator_chapters",
    "expert_annotation_released",
})
CHAPTER_GT_FORBIDDEN_ORIGINS = frozenset({
    "scene_detection", "scene_boundaries", "shot_boundaries", "prediction",
    "model_output", "pseudo_label", "duration_midpoint", "fixed_window",
    "clip_join_cut", "project_annotation",
})


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evaluation mode
# ---------------------------------------------------------------------------


def admitted_splits(evaluation_mode: str | None) -> frozenset[str]:
    """Return the split allowlist for an explicit evaluation mode (fail closed)."""
    if evaluation_mode not in EVALUATION_MODE_SPLITS:
        raise ChapterContractError(
            f"chaptering runners require --evaluation-mode in "
            f"{sorted(EVALUATION_MODE_SPLITS)}, got {evaluation_mode!r}"
        )
    if evaluation_mode == "final_test":
        # Final-test evaluation is a separate, once-only frozen evaluation.  It is
        # intentionally not reachable from the 04a/04b selection nodes; it needs a
        # frozen chapter configuration, a sealed-evaluation decision record and a
        # dedicated output namespace, none of which exist yet.
        raise ChapterContractError(
            "final_test evaluation is sealed: selection nodes 04a/04b admit only "
            "validation units; run frozen final-test evaluation separately after "
            "chapter.frozen_configuration is approved"
        )
    return EVALUATION_MODE_SPLITS[evaluation_mode]


def assert_units_in_splits(units: Sequence[Mapping[str, Any]], allowed: frozenset[str]) -> None:
    leaked = sorted(str(u.get("unit_id")) for u in units if u.get("split") not in allowed)
    if leaked:
        raise ChapterContractError(f"units outside admitted splits {sorted(allowed)}: {leaked[:3]}")


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------


def validate_chapter_ground_truth(unit: Mapping[str, Any]) -> list[float]:
    """Validated independent chapter GT for one unit; never a fallback."""
    label = f"unit[{unit.get('dataset_id')}/{unit.get('unit_id')}]"

    def blocked(reason: str) -> None:
        raise ChapterContractError(f"blocked_gt: {label}: {reason}")

    if "chapter_boundaries_sec" not in unit:
        blocked("missing chapter_boundaries_sec")
    provenance = unit.get("chapter_gt")
    if not isinstance(provenance, Mapping):
        blocked("missing chapter_gt provenance")
    missing = [
        key for key in CHAPTER_GT_REQUIRED_FIELDS
        if not isinstance(provenance.get(key), str) or not provenance[key].strip()
    ]
    if missing:
        blocked(f"chapter_gt missing fields {missing}")
    origin = provenance["annotation_origin"]
    if origin in CHAPTER_GT_FORBIDDEN_ORIGINS:
        blocked(f"chapter_gt origin {origin!r} is not independent GT")
    if origin not in CHAPTER_GT_ALLOWED_ORIGINS:
        blocked(f"chapter_gt origin {origin!r} is not allowed")
    duration = unit.get("duration_sec")
    if (isinstance(duration, bool) or not isinstance(duration, (int, float))
            or not math.isfinite(float(duration)) or duration <= 0):
        blocked("chapter GT requires positive duration_sec")
    raw = unit["chapter_boundaries_sec"]
    if not isinstance(raw, list):
        blocked("chapter_boundaries_sec must be a list")
    boundaries: list[float] = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            blocked(f"non-numeric chapter boundary {value!r}")
        number = float(value)
        if not math.isfinite(number):
            blocked("non-finite chapter boundary")
        if not 0.0 < number < float(duration):
            blocked(f"chapter boundary {number} outside (0, {float(duration)})")
        boundaries.append(number)
    if any(first >= second for first, second in zip(boundaries, boundaries[1:])):
        blocked("chapter boundaries must be strictly increasing")
    return boundaries


def reference_boundaries(unit: Mapping[str, Any]) -> list[float]:
    """Return chapter GT through the chapter-specific validator."""
    return validate_chapter_ground_truth(unit)


def reject_course_split_leakage(units: Sequence[Mapping[str, Any]], dataset_id: str) -> None:
    """Reject a course identity shared by train, validation, and final-test splits."""
    by_course: dict[str, set[str]] = defaultdict(set)
    for unit in units:
        course, split = unit.get("course_id"), unit.get("split")
        if course in (None, "", "unknown") or split in (None, "", "unknown"):
            continue
        by_course[str(course)].add(str(split))
    overlaps = sorted(course for course, splits in by_course.items() if len(splits) > 1)
    if overlaps:
        raise ChapterContractError(
            f"dataset[{dataset_id}]: course_id occurs in multiple splits: {overlaps[:3]}"
        )


def reject_chapter_speaker_split_leakage(
    units: Sequence[Mapping[str, Any]], dataset_id: str
) -> None:
    """Require a known speaker and keep each speaker in one RQ1 split."""
    by_speaker: dict[str, set[str]] = defaultdict(set)
    for unit in units:
        speaker = unit.get("speaker_id")
        if not isinstance(speaker, str) or not speaker.strip() or speaker.strip().casefold() == "unknown":
            raise ChapterContractError(
                f"unit[{dataset_id}/{unit.get('unit_id')}]: chapter split requires speaker_id"
            )
        by_speaker[speaker.strip().casefold()].add(str(unit["split"]))
    overlaps = sorted(speaker for speaker, splits in by_speaker.items() if len(splits) > 1)
    if overlaps:
        raise ChapterContractError(
            f"dataset[{dataset_id}]: speaker_id occurs in multiple chapter splits: {overlaps[:3]}"
        )


# ---------------------------------------------------------------------------
# Input features
# ---------------------------------------------------------------------------


def _transcript(unit: Mapping[str, Any]) -> str | None:
    value = unit.get("transcript")
    if value is None:
        value = unit.get("reference_text")
    text = str(value) if value is not None else ""
    return text if text.strip() else None


def predictor_input(unit: Mapping[str, Any]) -> dict[str, str]:
    """Allow only source text into 04a/04b predictors, never annotation fields."""
    return {"transcript": _transcript(unit) or ""}


def _video_modalities(unit: Mapping[str, Any], duration: float, source_sha256: str) -> dict[str, dict[str, Any]]:
    """Admit only nonempty, timestamped features extracted from this media file."""
    video = unit.get("rq1_video_features")
    if video is None:
        return {
            name: {"available": False, "reason": "no source-backed video extraction for unit"}
            for name in ("scene", "ocr", "visual", "acoustic")
        }
    if not isinstance(video, Mapping) or video.get("source_sha256") != source_sha256:
        raise ChapterContractError(f"unit {unit.get('unit_id')!r}: video feature source_sha256 mismatch")

    result: dict[str, dict[str, Any]] = {}
    for name, content_key in (("scene", "boundaries_sec"), ("ocr", "observations"),
                              ("visual", "observations"), ("acoustic", "observations")):
        raw = video.get(name)
        if not isinstance(raw, Mapping):
            result[name] = {"available": False, "reason": "video extraction missing"}
            continue
        if raw.get("available") is not True:
            result[name] = {"available": False, "reason": str(raw.get("reason") or "video extraction unavailable")}
            continue
        content = raw.get(content_key)
        digest = raw.get("sha256")
        if not isinstance(content, list) or not content:
            raise ChapterContractError(f"unit {unit.get('unit_id')!r}: {name} marked available without content")
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ChapterContractError(f"unit {unit.get('unit_id')!r}: invalid {name} feature sha256")
        if not isinstance(raw.get("extractor"), str) or not raw["extractor"] or not isinstance(raw.get("config"), Mapping):
            raise ChapterContractError(f"unit {unit.get('unit_id')!r}: missing {name} extraction provenance")
        previous = -1.0
        nonblank_ocr = False
        for item in content:
            if name == "scene":
                stamp = item
            else:
                if not isinstance(item, Mapping):
                    raise ChapterContractError(f"unit {unit.get('unit_id')!r}: invalid {name} observation")
                if name == "ocr":
                    if not isinstance(item.get("text"), str):
                        raise ChapterContractError(f"unit {unit.get('unit_id')!r}: invalid OCR observation")
                    nonblank_ocr |= bool(item["text"].strip())
                else:
                    score = item.get("change_score")
                    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                        raise ChapterContractError(f"unit {unit.get('unit_id')!r}: invalid {name} change_score")
                stamp = item.get("time_sec")
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
                raise ChapterContractError(f"unit {unit.get('unit_id')!r}: invalid {name} timestamp")
            if stamp <= previous or stamp < 0 or stamp >= duration or (name == "scene" and stamp == 0):
                raise ChapterContractError(f"unit {unit.get('unit_id')!r}: {name} timestamps outside media or not increasing")
            previous = float(stamp)
        if name == "ocr" and not nonblank_ocr:
            raise ChapterContractError(f"unit {unit.get('unit_id')!r}: OCR marked available without text")
        expected_digest = hashlib.sha256(json.dumps(
            {"content": content, "extractor": raw["extractor"], "config": raw["config"]},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        if digest != expected_digest:
            raise ChapterContractError(f"unit {unit.get('unit_id')!r}: {name} feature sha256 mismatch")
        result[name] = {
            "available": True, "sha256": digest, content_key: content,
            "extractor": raw["extractor"], "config": dict(raw["config"]),
        }
    return result


def build_input_feature_record(
    unit: Mapping[str, Any],
    *,
    evaluation_mode: str,
    code_sha256: str,
) -> dict[str, Any]:
    """Build the hash-bound ``chapter.input_features`` record for one unit.

    Modalities are taken only from source-backed fields of this unit.  A modality
    that was not extracted is recorded as unavailable with a reason; it is never
    borrowed from another unit or another dataset's stage benchmark.
    """
    unit_id = str(unit.get("unit_id") or "")
    source_sha256 = unit.get("sha256")
    if not isinstance(source_sha256, str) or len(source_sha256) != 64:
        raise ChapterContractError(f"unit {unit_id!r}: missing source media sha256")
    for key in ("dataset_id", "split", "course_id"):
        if not isinstance(unit.get(key), str) or not unit[key]:
            raise ChapterContractError(f"unit {unit_id!r}: missing {key}")
    duration = float(unit["duration_sec"])

    modalities: dict[str, dict[str, Any]] = {}
    transcript = _transcript(unit)
    if transcript is not None:
        declared = unit.get("transcript_sha256")
        actual = _sha256_text(transcript)
        if declared and declared != actual:
            raise ChapterContractError(f"unit {unit_id!r}: transcript hash mismatch")
        modalities["transcript"] = {
            "available": True,
            "sha256": actual,
            "token_count": len(transcript.split()),
            "time_alignment": "uniform_token_rate_over_duration",
        }
    else:
        modalities["transcript"] = {"available": False, "reason": "no source transcript"}

    modalities.update(_video_modalities(unit, duration, source_sha256))

    extraction_config = {
        "contract": CHAPTER_CONTRACT_VERSION,
        "transcript_field_order": ["transcript", "reference_text"],
        "video_feature_field": "rq1_video_features",
    }
    cache_key = _sha256_json({
        "dataset_id": unit["dataset_id"],
        "unit_id": unit_id,
        "split": unit["split"],
        "evaluation_mode": evaluation_mode,
        "source_sha256": source_sha256,
        "modalities": {k: v.get("sha256") for k, v in modalities.items()},
        "extraction_config": extraction_config,
        "code_sha256": code_sha256,
    })
    return {
        "dataset_id": unit["dataset_id"],
        "unit_id": unit_id,
        "split": unit["split"],
        "course_id": unit["course_id"],
        "source_sha256": source_sha256,
        "duration_sec": duration,
        "evaluation_mode": evaluation_mode,
        "modalities": modalities,
        "extraction_config": extraction_config,
        "cache_key": cache_key,
    }


def verify_feature_matches_unit(
    feature: Mapping[str, Any], unit: Mapping[str, Any], evaluation_mode: str
) -> None:
    """Reject a feature record that does not belong to exactly this unit/mode."""
    for key, expected in (
        ("dataset_id", unit.get("dataset_id")),
        ("unit_id", str(unit.get("unit_id"))),
        ("split", unit.get("split")),
        ("source_sha256", unit.get("sha256")),
        ("evaluation_mode", evaluation_mode),
    ):
        if feature.get(key) != expected:
            raise ChapterContractError(
                f"chapter.input_features mismatch for unit {unit.get('unit_id')!r}: "
                f"{key}={feature.get(key)!r} expected {expected!r}"
            )


def index_features(
    records: Sequence[Mapping[str, Any]], units: Sequence[Mapping[str, Any]], evaluation_mode: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Index feature records and require an exact one-to-one match with units."""
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        key = (str(record.get("dataset_id")), str(record.get("unit_id")))
        if key in index:
            raise ChapterContractError(f"duplicate chapter.input_features record {key}")
        index[key] = record
    unit_keys = {(str(u.get("dataset_id")), str(u.get("unit_id"))) for u in units}
    if set(index) != unit_keys:
        extra = sorted(set(index) - unit_keys)[:3]
        missing = sorted(unit_keys - set(index))[:3]
        raise ChapterContractError(
            f"chapter.input_features do not match eligible units (extra={extra}, missing={missing})"
        )
    for unit in units:
        verify_feature_matches_unit(
            index[(str(unit.get("dataset_id")), str(unit.get("unit_id")))], unit, evaluation_mode
        )
    return index


def require_modalities(feature: Mapping[str, Any], needed: Sequence[str]) -> list[str]:
    """Return missing modalities for a candidate (empty list = runnable)."""
    modalities = feature.get("modalities") or {}
    return [m for m in needed if not (modalities.get(m) or {}).get("available")]


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


def score_chapters(
    predicted_sec: Sequence[float], reference_sec: Sequence[float], duration_sec: float
) -> dict[str, float]:
    """Frozen RQ1 scorer.  Empty predictions are scored as zero boundaries."""
    if not (isinstance(duration_sec, (int, float)) and math.isfinite(duration_sec)
            and duration_sec > 0):
        raise ChapterContractError("scorer requires positive duration_sec")
    pred = sorted(float(p) for p in predicted_sec)
    ref = sorted(float(r) for r in reference_sec)
    primary = collar_f1(ref, pred, tolerance_sec=PRIMARY_COLLAR_SEC)
    metrics: dict[str, float] = {
        "collar_f1_3s": primary.f1,
        "collar_precision_3s": primary.precision,
        "collar_recall_3s": primary.recall,
    }
    for tol in SECONDARY_COLLARS_SEC:
        secondary = collar_f1(ref, pred, tolerance_sec=tol)
        metrics[f"collar_f1_{int(tol)}s"] = secondary.f1
    ref_bin = boundaries_to_binary_sequence(ref, duration_sec, step_sec=PK_WD_STEP_SEC)
    hyp_bin = boundaries_to_binary_sequence(pred, duration_sec, step_sec=PK_WD_STEP_SEC)
    metrics["pk"] = pk_metric(ref_bin, hyp_bin)
    metrics["window_diff"] = window_diff(ref_bin, hyp_bin)
    metrics["predicted_boundary_count"] = float(len(pred))
    metrics["reference_boundary_count"] = float(len(ref))
    return metrics


SCORER_DESCRIPTION = {
    "contract": CHAPTER_CONTRACT_VERSION,
    "primary_metric": "collar_f1_3s",
    "primary_collar_sec": PRIMARY_COLLAR_SEC,
    "secondary_collars_sec": list(SECONDARY_COLLARS_SEC),
    "secondary_metrics": ["collar_f1_5s", "collar_f1_10s", "pk", "window_diff"],
    "pk_wd_step_sec": PK_WD_STEP_SEC,
    "matching": "one-to-one greedy nearest within collar",
    "empty_prediction_policy": EMPTY_PREDICTION_POLICY,
}


# ---------------------------------------------------------------------------
# Learned checkpoints (C5/C6)
# ---------------------------------------------------------------------------


def learned_candidate_status(
    candidate: str,
    eval_units: Sequence[Mapping[str, Any]],
    *,
    checkpoints: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Decide whether a learned chapterer may run; never relabel a heuristic.

    A checkpoint is admissible only with a sibling ``.provenance.json`` that
    binds architecture, code, seed and train-only data, whose SHA-256 matches the
    checkpoint bytes, and whose train units/courses are disjoint from the
    evaluated units.  Even then, inference needs the learned per-unit feature
    tensors, which ``chapter.input_features`` does not yet provide.
    """
    paths = checkpoints if checkpoints is not None else LEARNED_CHECKPOINTS
    path = paths.get(candidate)
    status: dict[str, Any] = {"candidate": candidate, "status": "not_run",
                              "checkpoint_path": str(path) if path else None}
    if path is None or not path.is_file():
        status["reason"] = "checkpoint_missing"
        return status
    provenance_path = path.with_suffix(".provenance.json")
    if not provenance_path.is_file():
        status["reason"] = (
            "checkpoint_provenance_missing: no train-only data/code/seed manifest; "
            "existing checkpoint cannot be attributed to frozen train units"
        )
        return status
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        status["reason"] = f"checkpoint_provenance_unreadable: {exc}"
        return status
    missing = [f for f in CHECKPOINT_PROVENANCE_FIELDS if f not in provenance]
    if missing:
        status["reason"] = f"checkpoint_provenance_incomplete: {missing}"
        return status
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if provenance["checkpoint_sha256"] != digest:
        status["reason"] = "checkpoint_sha256_mismatch"
        return status
    if provenance["candidate"] != candidate:
        status["reason"] = "checkpoint_candidate_mismatch"
        return status
    train_units = {str(u) for u in provenance["train_unit_ids"]}
    train_courses = {str(c) for c in provenance["train_course_ids"]}
    eval_unit_ids = {str(u.get("unit_id")) for u in eval_units}
    eval_courses = {str(u.get("course_id")) for u in eval_units}
    if train_units & eval_unit_ids or train_courses & eval_courses:
        status["reason"] = "train_eval_leakage: checkpoint trained on evaluated units/courses"
        return status
    status["reason"] = (
        "blocked_compute: learned feature tensors are not part of chapter.input_features yet"
    )
    status["checkpoint_sha256"] = digest
    return status
