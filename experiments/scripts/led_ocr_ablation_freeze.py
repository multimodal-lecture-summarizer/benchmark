"""Freeze the LED OCR ablation protocol, cohort and decision rules before any output exists.

Question: does interleaving slide OCR into the LED input change the English summary, compared with
the transcript alone? Two arms (A `led`, D `led_ocr`) share one extracted input per video; the only
change is the LED_INCLUDE_OCR flag. Thresholds were approved by the user on 2026-11-10.

Run once: `python -m experiments.scripts.led_ocr_ablation_freeze` from the benchmark folder. A second
run with identical content is a no-op; any difference stops (create a new version instead).
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path

PROTOCOL_ID = "led-ocr-ablation-261110-v1"
DECIDED_ON = "2026-11-10"
SHORTLIST = "plans/reports/dataset-shortlist-261108-1703-tib-ccc-niche-candidates.csv"
REVIEW = "plans/reports/phd-review-261108-1703-benchmark-niche-dataset-report.md"
FROZEN_PARAMS = "benchmark/experiments/registry/datasets/slide-segmentation-frozen-params-261109.json"
SEGMENTER_SOURCE = "multimodal-lecture-summarizer/ai_workers/modules/visual_v2/slide_segmenter.py"
EXPECTED_STRATA = {"S1_cs_talk_scored": 18, "S2_cs_talk_unscored": 8, "S3_lecture_genre": 5, "S4_stem_formula_talk": 9}
EXPECTED_COHORT = 40
SMOKE_COUNT = 3
SEED = 20261110
RESAMPLES = 10000

# Thresholds approved by the user on 2026-11-10 (plan.md, validated decision 1).
DECISION_RULES = {
    "format": "led-ocr-ablation-decision-rules-v1",
    "approved_on": DECIDED_ON,
    "primary": {"metric": "rougeL_f1_at_350", "contrast": "D_minus_A", "margin": 0.01},
    "guard": {"metric": "minicheck_mean_prob_transcript_plus_ocr", "contrast": "D_minus_A", "margin": 0.03},
    "min_comparable_pairs": 32,
    "denominator": EXPECTED_COHORT,
    "interval": {"level": 0.95, "method": "stratified_percentile_bootstrap_by_stratum",
                 "resamples": RESAMPLES, "seed": SEED},
    "labels": {
        "ocr_helps_summary": "primary CI low > 0 and primary mean >= +0.01 and guard mean >= -0.03",
        "ocr_hurts_summary": ("(primary CI high < 0 and primary mean <= -0.01) or "
                              "(guard CI high < 0 and guard mean <= -0.03)"),
        "no_selection": "fewer than 32 comparable pairs",
        "no_difference": "everything else",
    },
    "label_order": ["no_selection", "ocr_hurts_summary", "ocr_helps_summary", "no_difference"],
    "post_hoc": "any analysis outside this file is labelled post_hoc and never changes the label",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


def read_shortlist(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _video(row: dict) -> dict:
    return {
        "id": row["id"], "stratum": row["stratum"], "split": row["split_or_conf"],
        "page_url": row["page_url"], "media_url": row["media_url"], "title": row["title"],
        "license": row["license"], "duration_s": int(float(row["duration_s"])),
        "size_mb": float(row["size_mb"]), "width": int(row["width"]), "height": int(row["height"]),
        "visual_class": row["visual_class"], "core_ready": row["core_ready"] == "True",
        "screening_label_source": [SHORTLIST, REVIEW],
    }


def build_cohort(rows: list[dict]) -> dict:
    """40 TIB `core_ready` videos plus 3 smoke videos outside the cohort. Labels taken as given."""
    tib = [r for r in rows if r["source"] == "TIB"]
    main = sorted((r for r in tib if r["core_ready"] == "True"), key=lambda r: r["id"])
    counts: dict[str, int] = {}
    for row in main:
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    if len(main) != EXPECTED_COHORT or counts != EXPECTED_STRATA:
        raise ValueError(f"cohort mismatch: {len(main)} videos, strata {counts}")
    # Smoke: the first not-core_ready TIB video of each stratum with readable-slide or screen visuals,
    # in id order, so the choice is mechanical. Smoke videos are never scored.
    others = sorted((r for r in tib if r["core_ready"] != "True" and r["probe_status"] == "ok"), key=lambda r: r["id"])
    smoke: list[dict] = []
    seen_strata: set[str] = set()
    for row in others:
        if row["stratum"] not in seen_strata:
            seen_strata.add(row["stratum"])
            smoke.append(row)
        if len(smoke) == SMOKE_COUNT:
            break
    if len(smoke) != SMOKE_COUNT:
        raise ValueError("not enough smoke videos outside the cohort")
    split_counts: dict[str, int] = {}
    for row in main:
        split_counts[row["split_or_conf"]] = split_counts.get(row["split_or_conf"], 0) + 1
    return {
        "format": "led-ocr-ablation-cohort-v1", "protocol_id": PROTOCOL_ID,
        "count": len(main), "strata_counts": counts, "split_counts": split_counts,
        "total_duration_hours": round(sum(float(r["duration_s"]) for r in main) / 3600, 2),
        "total_size_mb": round(sum(float(r["size_mb"]) for r in main), 1),
        "screening_label": "core_ready taken as given from the shortlist; it selects videos, it never enters a score",
        "videos": [_video(r) for r in main],
        "smoke_videos": [_video(r) for r in smoke],
        "smoke_note": "outside the cohort; used only for the phase 2 and 3 dry runs; never scored",
        "negative_control": "none (dropped by the user on 2026-11-10)",
    }


def git_state(repo: Path, subpath: str) -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()

    return {"commit": run("rev-parse", "HEAD"),
            "uncommitted_paths_under_subpath": [line for line in run("status", "--porcelain", "--", subpath).splitlines()]}


def segmenter_defaults_match(frozen: dict, source: str) -> dict:
    """Each frozen parameter must appear as a dataclass default in the app's segmenter module."""
    import re

    found = {}
    for name, value in frozen["params"].items():
        match = re.search(rf"^\s+{name}:\s*\w+\s*=\s*([0-9.]+)", source, re.MULTILINE)
        found[name] = float(match.group(1)) if match else None
    mismatched = {k: (found[k], v) for k, v in frozen["params"].items() if found[k] != float(v)}
    if mismatched:
        raise ValueError(f"segmenter defaults differ from frozen params: {mismatched}")
    return found


def build_protocol(cohort_sha: str, rules_sha: str, shortlist_sha: str, app: dict, code_sha: dict) -> dict:
    return {
        "format": "led-ocr-ablation-protocol-v1", "protocol_id": PROTOCOL_ID, "status": "frozen",
        "decided_on": DECIDED_ON,
        "decision_source": "user, 2026-11-10: LED only, two arms, no RAG, no slide-selection evaluation; "
                           "thresholds, screening-label handling and download scope approved in plan validation",
        "question": "does interleaving slide OCR into the LED input change the English summary versus transcript only",
        "supersedes": "summary part of plan 261108-1746-ocr-ablation-english-summary (paused, not cancelled)",
        "cohort_sha256": cohort_sha, "decision_rules_sha256": rules_sha, "shortlist_sha256": shortlist_sha,
        "app": app, "code_sha256": code_sha,
        "arms": {
            "A": {"id": "led", "LED_INCLUDE_OCR": False, "input": "transcript",
                  "valid_cell": "summary_method == 'led' and 'OCR' not in model_used"},
            "D": {"id": "led_ocr", "LED_INCLUDE_OCR": True, "input": "transcript with 'Slide: ...' blocks",
                  "valid_cell": "summary_method == 'led'"},
        },
        "single_changed_factor": "LED_INCLUDE_OCR; both arms read the same hashed input file per video",
        "extraction": {
            "SCENE_SEGMENTER": "slide", "ENABLE_FLORENCE_CAPTIONING": "false", "ENABLE_OBJECT_TRACKING": "false",
            "HF_TOKEN": "", "ASR_ENGLISH_BACKEND": "qwen3", "source_language": "en", "output_language": "en",
            "summary_length": "detailed", "word_cap": 350,
            "segmenter_params": "frozen 2026-11-09, see segmenter_params_check",
            "full_environment_capture": "phase 2 records every worker_settings value used, per run",
        },
        "segmenter_params_file": FROZEN_PARAMS,
        "exposure": ("19 cohort videos are in the TIB test split and S1 references were exposed through final523; "
                     "17 are train and 4 are valid. The cohort is not an unseen set."),
        "reference": {"dataset": "gigant/tib", "revision": "e6ab9fd7c6acd164f3284b8c4b17eb9d94681eee",
                      "join": "dataset field `doi` == cohort id; reference = field `abstract`",
                      "note": "ASR transcript here is Qwen3-ASR pipeline output, not the TIB transcript used in final523"},
        "metrics": {
            "primary": "ROUGE-L F1 @350 words, D minus A (rouge-score 0.1.2, stemmer on)",
            "guard": "MiniCheck mean sentence probability, D minus A, evidence = transcript + cleaned OCR for both arms",
            "descriptive": ["BERTScore F1", "ROUGE-L @120", "word count",
                            "MiniCheck with transcript-only evidence", "slide-term coverage",
                            "generation time, LED calls, OCR words, slides used"],
            "slide_term_coverage": ("T = content words (>=3 letters, lowercase, stopwords removed) in the cleaned OCR and not in "
                                    "the transcript; coverage = |T ∩ summary words| / |T|; videos with empty T dropped; descriptive only"),
        },
        "special_cells": {
            "ocr_not_in_input": "D equals A; still a valid pair (intention-to-treat); report the count",
            "segmenter_fell_back_to_content": "kept in cohort, flagged, reported separately",
            "error_cell": "recorded, pair not comparable, never rerun to change a result",
        },
        "run_rules": {"generations_per_cell": 1, "automatic_retries": 0, "order": "A then D within each video",
                      "download_failure": "recorded, no substitute video"},
        "analysis": {"unit": "video", "stratify_by": "stratum", "seed": SEED, "resamples": RESAMPLES, "level": 0.95,
                     "label_set": ["ocr_helps_summary", "ocr_hurts_summary", "no_difference", "no_selection"],
                     "one_pass": True, "default_change": "never automatic; presented to the user"},
        "limitations": [
            "TIB abstracts mostly summarize speech, so ROUGE-L understates any OCR benefit; no_difference is a valid outcome",
            "screening labels were not re-reviewed; mislabelled videos dilute the OCR effect toward no_difference",
            "slide mode has diagnostic-level evidence only; result applies to this configuration (slide, PaddleOCR, 576p)",
            "no 360p, whiteboard or content-mode generalisation",
        ],
    }


def freeze(repo_root: Path | None = None) -> dict:
    repo = repo_root or Path(__file__).resolve().parents[3]
    shortlist = repo / SHORTLIST
    frozen_params = json.loads((repo / FROZEN_PARAMS).read_text(encoding="utf-8"))
    params_check = segmenter_defaults_match(frozen_params, (repo / SEGMENTER_SOURCE).read_text(encoding="utf-8"))
    cohort = build_cohort(read_shortlist(shortlist))
    cohort_sha, rules_sha = sha256_bytes(canonical(cohort)), sha256_bytes(canonical(DECISION_RULES))
    app = git_state(repo / "multimodal-lecture-summarizer", "ai_workers")
    app["segmenter_params_check"] = params_check
    scripts = Path(__file__).resolve().parent
    code_sha = {name: sha256_file(scripts / f"{name}.py") for name in ("led_ocr_ablation_freeze",)}
    protocol = build_protocol(cohort_sha, rules_sha, sha256_file(shortlist), app, code_sha)
    out = repo / "benchmark/experiments/registry/protocols" / PROTOCOL_ID
    files = {"cohort.json": cohort, "decision_rules.json": DECISION_RULES, "protocol.json": protocol}
    hashes = {name: sha256_bytes(canonical(doc)) for name, doc in files.items()}
    manifest = {"protocol_id": PROTOCOL_ID, "frozen_on": DECIDED_ON, "sha256": hashes}
    out.mkdir(parents=True, exist_ok=True)
    for name, doc in {**files, "hashes.json": manifest}.items():
        target = out / name
        data = canonical(doc)
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"{name} already frozen with different content; create a new protocol version")
        if not target.exists():
            target.write_bytes(data)
    return manifest


if __name__ == "__main__":
    print(json.dumps(freeze(), indent=2))
