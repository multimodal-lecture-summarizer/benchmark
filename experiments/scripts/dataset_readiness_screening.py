"""Conservative, versioned similarity screening; no semantic-uniqueness claim."""
from __future__ import annotations

import hashlib
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

from experiments.evaluation.asr_selection_scoring import normalize_english_asr
from experiments.scripts.benchmark_artifacts import sha256_file


def default_protocol() -> dict:
    return {
        "version": "dataset-readiness-v1", "selection_salt": "dataset-readiness-v1",
        "ted_validation_units": 30, "ted_test_units": 20,
        "minimum_retained": {"tedlium3": {"validation": 20, "final_test": 15},
                             "iiit_cvid": {"validation": 30, "final_test": 30}},
        "minimum_groups_per_split": 2,
        "image_dhash_size": 8, "image_dhash_max_distance": 6,
        "audio_fingerprint_samples": 4096, "audio_correlation_min": 0.995,
        "audio_relative_duration_tolerance": 0.01,
        "transcript_similarity_min": 0.95, "transcript_min_words": 8,
        "conflict_policy": "exclude_validation_for_cross_split; exclude_new_for_history; retain_within_split",
        "failure_policy": "exclude_no_replacement; block_if_insufficient_or_unresolved",
        "histogram_bytes_edges": [0, 10000, 50000, 100000, 250000, 500000, 1000000, 5000000, 50000000],
        "histogram_duration_edges": [0, 1, 2, 5, 10, 20, 30, 60, 120, 600],
        "scope": "preparation evidence screened under protocol; no model inference",
        "limitations": ["dHash is not semantic image matching",
                        "waveform correlation and text similarity do not exhaust audio transformations",
                        "screening test metadata/content for integrity does not establish untouched evaluation results"],
    }


def fingerprint(row: dict, protocol: dict) -> dict:
    """Verify bytes, then derive measured features from a full decode."""
    path = Path(row["media_path"])
    if sha256_file(path) != row["sha256"] or path.stat().st_size != row["bytes"]:
        raise ValueError(f"media identity changed: {row['unit_id']}")
    if row["dataset_id"] == "iiit_cvid":
        from PIL import Image
        with Image.open(path) as image:
            image.load()
            rgb = image.convert("RGB")
            canonical = str(rgb.size).encode() + rgb.tobytes()
            size = protocol["image_dhash_size"]
            pixels = np.asarray(rgb.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS))
            bits = (pixels[:, 1:] > pixels[:, :-1]).ravel()
            dhash = sum(int(bit) << index for index, bit in enumerate(bits))
        return {"decoded_sha256": hashlib.sha256(canonical).hexdigest(), "dhash": dhash}
    import soundfile as sf
    with sf.SoundFile(path) as audio:
        values = audio.read(dtype="float32", always_2d=True)
        if len(values) != audio.frames or not len(values) or not np.isfinite(values).all():
            raise ValueError("incomplete or non-finite audio")
        rate = audio.samplerate
    mono = values.mean(axis=1).astype(np.float64)
    sample = np.interp(np.linspace(0, len(mono) - 1, protocol["audio_fingerprint_samples"]),
                       np.arange(len(mono)), mono)
    sample -= sample.mean()
    norm = np.linalg.norm(sample)
    waveform = sample / norm if norm > 1e-12 else None
    canonical = str((rate, values.shape)).encode() + values.tobytes()
    return {"decoded_sha256": hashlib.sha256(canonical).hexdigest(),
            "waveform": waveform, "duration": len(values) / rate,
            "text": normalize_english_asr(row.get("reference_text", ""))}


def pair_match(left: dict, right: dict, a: dict, b: dict, protocol: dict) -> dict | None:
    if left["sha256"] == right["sha256"] or a["decoded_sha256"] == b["decoded_sha256"]:
        return {"kind": "exact", "method": "file_or_decoded_sha256", "score": 1, "threshold": 1}
    if "dhash" in a:
        distance = (a["dhash"] ^ b["dhash"]).bit_count()
        if distance <= protocol["image_dhash_max_distance"]:
            return {"kind": "near", "method": "dhash_hamming", "score": distance,
                    "threshold": protocol["image_dhash_max_distance"]}
        return None
    close_duration = abs(a["duration"] - b["duration"]) / max(a["duration"], b["duration"]) <= protocol["audio_relative_duration_tolerance"]
    if close_duration and a["waveform"] is not None and b["waveform"] is not None:
        score = float(abs(np.dot(a["waveform"], b["waveform"])))
        if score >= protocol["audio_correlation_min"]:
            return {"kind": "near", "method": "waveform_correlation", "score": score,
                    "threshold": protocol["audio_correlation_min"]}
    if min(len(a["text"].split()), len(b["text"].split())) >= protocol["transcript_min_words"]:
        score = SequenceMatcher(None, a["text"].split(), b["text"].split(), autojunk=False).ratio()
        if score >= protocol["transcript_similarity_min"]:
            return {"kind": "near", "method": "normalized_transcript_sequence", "score": score,
                    "threshold": protocol["transcript_similarity_min"]}
    return None


def screen_dataset(dataset_id: str, selected: list[dict], historical: list[dict], protocol: dict) -> tuple[list[dict], dict]:
    """Record every hit; deterministically exclude conflicts without replenishment."""
    records = [dict(r, decision="keep", reasons=[]) for r in selected]
    all_rows = records + [dict(r, split="historical") for r in historical]
    ids = [r["unit_id"] for r in all_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate unit IDs in selected/historical cohort")
    features, failures, pairs = {}, [], []
    for row in all_rows:
        invalid_reference = (row.get("ground_truth_error")
                             or not row.get("reference_text", "").strip()
                             or row.get("reference_text", "").strip() == "ignore_time_segment_in_scoring")
        if invalid_reference:
            failures.append({"unit_id": row["unit_id"], "split": row["split"],
                             "error": "released reference invalid or excluded from scoring"})
            if row["split"] != "historical":
                row["decision"] = "exclude"
                row["reasons"].append("released_reference_not_scorable")
        try:
            if not row.get("decoded"):
                raise ValueError("media decode failed")
            # Reference eligibility and content similarity are separate measurements:
            # fully decoded ignored units still participate in media comparisons.
            features[row["unit_id"]] = fingerprint(row, protocol)
            if invalid_reference and "text" in features[row["unit_id"]]:
                features[row["unit_id"]]["text"] = ""
        except Exception as exc:
            failures.append({"unit_id": row["unit_id"], "split": row["split"], "error": str(exc)})
            if row["split"] != "historical":
                row["decision"] = "exclude"
                row["reasons"].append("decode_reference_or_identity_failure")
    cohort_counts = dict(Counter(r["split"] for r in all_rows))
    splits = sorted(cohort_counts)
    coverage = {}
    for i, left_split in enumerate(splits):
        for right_split in splits[i:]:
            n, m = cohort_counts[left_split], cohort_counts[right_split]
            expected = n * (n - 1) // 2 if left_split == right_split else n * m
            if left_split == right_split == "historical":
                expected = 0
            coverage[left_split, right_split] = {"left_split": left_split, "right_split": right_split,
                                                "expected_pairs": expected, "completed_pairs": 0}
    comparisons = 0
    for index, left in enumerate(all_rows):
        for right in all_rows[index + 1:]:
            if left["split"] == right["split"] == "historical":
                continue
            if left["unit_id"] not in features or right["unit_id"] not in features:
                continue
            comparisons += 1
            coverage[tuple(sorted((left["split"], right["split"])))]["completed_pairs"] += 1
            hit = pair_match(left, right, features[left["unit_id"]], features[right["unit_id"]], protocol)
            if hit is None:
                continue
            loser = (left if right["split"] == "historical" else right if left["split"] == "historical"
                     else left if left["split"] == "validation" and right["split"] == "final_test"
                     else right if right["split"] == "validation" and left["split"] == "final_test" else None)
            if loser is not None:
                loser["decision"] = "exclude"
                loser["reasons"].append(f"{hit['method']}:{right['unit_id'] if loser is left else left['unit_id']}")
            pairs.append(dict(hit, left=left["unit_id"], right=right["unit_id"], left_split=left["split"],
                              right_split=right["split"], decision="exclude" if loser else "retain_within_split",
                              excluded_unit_id=loser["unit_id"] if loser else None,
                              reason="predeclared conservative conflict rule" if loser else "within-split similarity; dependence remains"))
    retained = [r for r in records if r["decision"] == "keep"]
    blockers = []
    for split, minimum in protocol["minimum_retained"][dataset_id].items():
        subset = [r for r in retained if r["split"] == split]
        if len(subset) < minimum:
            blockers.append(f"{split}: retained {len(subset)} below minimum {minimum}")
        if len({r.get("speaker_id") for r in subset if r.get("speaker_id")}) < protocol["minimum_groups_per_split"]:
            blockers.append(f"{split}: insufficient independent speaker/course groups")
    for field in ("speaker_id", "talk_id"):
        val = {r[field] for r in retained if r["split"] == "validation" and r.get(field)}
        test = {r[field] for r in retained if r["split"] == "final_test" and r.get(field)}
        if val & test:
            blockers.append(f"retained cross-split {field} overlap")
        if any(not r.get(field) for r in retained):
            blockers.append(f"retained {field} missing")
    if any(f["split"] == "historical" for f in failures):
        blockers.append("historical comparison incomplete")
    kept_ids = {r["unit_id"] for r in retained}
    remaining = [p for p in pairs if p["left_split"] != p["right_split"] and
                 p["left"] in kept_ids and p["right"] in kept_ids]
    historical_hits = [p for p in pairs if
                       (p["left_split"] == "historical" and p["right"] in kept_ids) or
                       (p["right_split"] == "historical" and p["left"] in kept_ids)]
    if remaining:
        blockers.append("retained cross-split similarity conflicts")
    if historical_hits:
        blockers.append("retained historical similarity conflicts")
    return records, {"dataset_id": dataset_id, "status": "blocked" if blockers else "screened_under_protocol",
                     "pairs": pairs, "failures": failures, "comparisons": comparisons,
                     "selected_count": len(records), "retained_count": len(retained),
                     "historical_count": len(historical), "retained_cross_split_hits": len(remaining),
                     "retained_historical_hits": len(historical_hits),
                     "cohort_counts": cohort_counts, "pair_coverage": list(coverage.values()),
                     "blockers": blockers, "limitations": protocol["limitations"]}
