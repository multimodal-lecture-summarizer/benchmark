"""Whole-corpus TED-LIUM metadata and reference EDA before research splitting."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


TIMES = r"-(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)-<"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _quantiles(values) -> dict:
    values = values.dropna()
    return {str(q): float(values.quantile(q)) for q in (0, .25, .5, .75, .95, 1)}


def analyze_audio(root: Path) -> dict:
    """Scan every source split's text/identity metadata; do not decode 53 GB of audio."""
    from datasets import load_from_disk
    import pandas as pd

    source = root / "experiments/datasets/tedlium3"
    summaries = []
    tables = {}
    identities = {}
    for split in ("train", "validation", "test"):
        frame = load_from_disk(str(source / split)).select_columns(
            ["id", "text", "speaker_id", "gender", "file"]
        ).to_pandas()
        ids = frame["id"].fillna("").astype(str)
        text = frame["text"].fillna("").astype(str).str.strip()
        bounds = ids.str.extract(TIMES).astype(float)
        duration = bounds[1] - bounds[0]
        words = text.str.split().str.len()
        gap = ids.str.startswith("inter_segment_gap")
        ignored = text.eq("ignore_time_segment_in_scoring")
        valid = duration.gt(0) & text.ne("") & ~gap & ~ignored
        talks = frame["file"].fillna("").astype(str).str.rsplit("/", n=1).str[-1]
        norm = text.str.lower().str.replace(r"\s+", " ", regex=True)
        table = pd.DataFrame({
            "id": ids, "speaker": frame["speaker_id"], "talk": talks,
            "start": bounds[0], "end": bounds[1],
            "duration": duration, "words": words, "valid": valid, "gap": gap,
        })
        tables[split] = table
        identities[split] = {
            "ids": set(ids), "speakers": set(frame["speaker_id"].dropna().astype(str)),
            "talks": set(talks), "references": set(norm[valid]),
        }
        covered_seconds = 0.0
        adjacent_overlaps = 0
        for _, group in table.groupby("talk", sort=False):
            start, end = None, None
            ordered = group.sort_values("start")
            for left, right in zip(ordered["start"], ordered["end"]):
                if start is None:
                    start, end = left, right
                elif left <= end:
                    adjacent_overlaps += left < end
                    end = max(end, right)
                else:
                    covered_seconds += end - start
                    start, end = left, right
            if start is not None:
                covered_seconds += end - start
        summaries.append({
            "source_split": split, "rows": len(frame), "valid_asr_rows": int(valid.sum()),
            "gap_rows": int(gap.sum()), "ignore_marker_rows": int(ignored.sum()),
            "blank_reference_rows": int(text.eq("").sum()),
            "unique_ids": int(ids.nunique()), "unique_speakers": int(frame["speaker_id"].nunique()),
            "unique_source_files": int(talks.nunique()),
            "missing_speaker_rows": int(frame["speaker_id"].isna().sum()),
            "missing_source_file_rows": int(frame["file"].isna().sum()),
            "unparseable_or_nonpositive_timing_rows": int((~duration.gt(0)).sum()),
            "gender_code_counts": {str(k): int(v) for k, v in frame["gender"].value_counts(dropna=False).items()},
            "top_speakers": {str(k): int(v) for k, v in frame["speaker_id"].value_counts().head(10).items()},
            "segments_per_speaker_quantiles": _quantiles(frame["speaker_id"].value_counts()),
            "segment_duration_sum_seconds": float(duration.sum()),
            "merged_source_coverage_seconds": float(covered_seconds),
            "adjacent_interval_overlaps": int(adjacent_overlaps),
            "valid_asr_duration_sum_seconds": float(duration[valid].sum()),
            "duration_quantiles_seconds": _quantiles(duration),
            "duration_histogram_bins_seconds": [0, 1, 2, 5, 10, 20, 30, 60, 1e9],
            "duration_histogram": np.histogram(
                duration, bins=[0, 1, 2, 5, 10, 20, 30, 60, 1e9]
            )[0].astype(int).tolist(),
            "reference_word_quantiles": _quantiles(words[valid]),
            "reference_word_histogram_bins": [0, 5, 10, 20, 40, 80, 160, 1e9],
            "reference_word_histogram": np.histogram(
                words[valid], bins=[0, 5, 10, 20, 40, 80, 160, 1e9]
            )[0].astype(int).tolist(),
            "wps_quantiles": _quantiles(words[valid] / duration[valid]),
            "segments_per_source_quantiles": _quantiles(talks.value_counts()),
            "repeated_reference_groups": int((norm[valid].value_counts() > 1).sum()),
            "rows_in_repeated_reference_groups": int(norm[valid].duplicated(keep=False).sum()),
        })

    overlap = []
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        a, b = identities[left], identities[right]
        overlap.append({
            "left": left, "right": right,
            "same_ids": len(a["ids"] & b["ids"]),
            "same_speakers": len(a["speakers"] & b["speakers"]),
            "same_source_files": len(a["talks"] & b["talks"]),
            "same_reference_strings": len(a["references"] & b["references"]),
        })

    repaired = root / "experiments/outputs/phase12_repair_260926/20260926T094154516917Z"
    payloads = repaired / "tedlium3/official/full/payloads"
    readiness = (root / "experiments/outputs/dataset_readiness_260926/20260926T101747121197Z"
                 / "bundle/tedlium3")
    freeze = _read(payloads / "dataset.frozen_manifest.json")["records"][0]
    screening = _read(readiness / "screening.json")
    selection = _read(readiness / "split-manifest.json")
    retained_validation = {x.split(":", 1)[1] for x in selection["retained_unit_ids"]
                           if x.startswith("validation:")}
    if not retained_validation <= identities["validation"]["ids"]:
        raise ValueError("Readiness IDs disagree with local validation Arrow data")
    return {
        "dataset": "tedlium3", "scope": "all_source_splits_metadata_and_reference_statistics",
        "source_rows": summaries, "cross_split_overlap": overlap,
        "historical_d2_units": len(_read(payloads / "dataset.unit_profile.json")["records"]),
        "historical_freeze_status": freeze["freeze_status"],
        "historical_freeze_reason": freeze["reason"],
        "readiness_selected": screening["selected_count"],
        "readiness_retained": screening["retained_count"],
        "readiness_retained_validation": len(retained_validation),
        "readiness_selection_eligible": selection["scientific_selection_eligible"],
        "validation_speaker_counts": {str(k): int(v) for k, v in
                                      tables["validation"]["speaker"].value_counts().items()},
        "validation_duration_histogram": np.histogram(
            tables["validation"]["duration"], bins=[0, 2, 5, 10, 15, 20, 30, 60, 1e9]
        )[0].astype(int).tolist(),
        "input_paths": [str(source), str(payloads), str(readiness)],
        "limitations": [
            "All source-split reference texts were used in aggregate EDA; the original test split is not untouched.",
            "Segment-duration sums include overlaps and are not unique audio hours.",
            "Audio waveforms were not decoded for the 270k Arrow rows.",
            "Exact text repetition does not establish duplicate audio.",
            "The historical 20-unit ASR comparison used old final-test items for model selection.",
        ],
    }
