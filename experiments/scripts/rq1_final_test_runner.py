"""Execute sealed RQ1 final-test scoring from prediction artifacts.

Prediction generation is a separate, locked candidate execution step. This
runner neither selects candidates nor reads training/validation predictions.
Synthetic fixture mode exercises the same contract without opening real test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scipy import stats

from experiments.scripts.rq1_cohort_split_guard import validate_rq1_cohort_split
from experiments.scripts.rq1_grouped_bootstrap import grouped_paired_bootstrap
from experiments.scripts.rq1_official_scorer import macro_primary_f1, score_official_unit


class FinalTestLockError(ValueError):
    """Sealed inputs, cohort or prediction coverage drifted."""


def _group_inference(comparisons: list[dict[str, Any]]) -> None:
    """Attach paired group t p-values and correction over locked contrasts."""
    raw: list[float] = []
    for row in comparisons:
        values = row["group_means"]
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        row["cohens_d_paired_group"] = (statistics.mean(values) / sd) if sd > 0 else None
        p = float(stats.ttest_1samp(values, 0).pvalue) if sd > 0 else 1.0
        raw.append(p if math.isfinite(p) else 1.0)
        row["paired_group_t_p_raw"] = raw[-1]
    order = sorted(range(len(raw)), key=lambda index: raw[index])
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, raw[index] * (len(raw) - rank)))
        comparisons[index]["holm_p_adjusted"] = running
        comparisons[index]["holm_family_size"] = len(raw)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_locked(base: Path, receipt: dict[str, Any], label: str) -> Any:
    item = receipt.get(label)
    if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
        raise FinalTestLockError(f"{label}: path and sha256 required")
    path = (base / item["path"]).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file() or _sha(path) != item["sha256"]:
        raise FinalTestLockError(f"{label}: missing file, path escape, or hash drift")
    return json.loads(path.read_text(encoding="utf-8"))


def run_sealed_scores(lock_path: Path, prediction_path: Path, output_dir: Path) -> dict[str, Any]:
    """Score exact locked test IDs once; never create a partial official report."""
    if output_dir.exists():
        raise FinalTestLockError("output directory already exists; sealed runs never overwrite")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    mode = lock.get("mode")
    if mode not in {"fixture", "official"} or lock.get("schema") != "rq1-final-test-lock/1":
        raise FinalTestLockError("unsupported lock schema/mode")
    if not isinstance(lock.get("run_id"), str) or not lock["run_id"].strip():
        raise FinalTestLockError("nonempty run_id required")
    if mode == "official" and lock.get("scale_decision") != "pretest_scope_and_precision_locked":
        raise FinalTestLockError("official scale/scope decision is not locked")
    base = lock_path.resolve().parent
    cohort = _read_locked(base, lock, "cohort")
    history = _read_locked(base, lock, "history")
    targets = _read_locked(base, lock, "targets")
    config = _read_locked(base, lock, "candidate_config")
    if not all(isinstance(x, list) for x in (cohort, history, targets)) or not isinstance(config, dict):
        raise FinalTestLockError("invalid locked input shape")
    groups = validate_rq1_cohort_split(cohort, history)
    test_ids = [row["video_id"] for row in cohort if row["split"] == "final_test"]
    if not test_ids:
        raise FinalTestLockError("no final_test cohort")
    test_set = set(test_ids)
    test_groups = [group for group in groups if set(group) <= test_set]
    if set(uid for group in test_groups for uid in group) != test_set:
        raise FinalTestLockError("test groups do not cover exact cohort")
    target_by_id = {row.get("video_id"): row for row in targets if isinstance(row, dict)}
    if len(target_by_id) != len(targets) or set(target_by_id) != test_set:
        raise FinalTestLockError("target IDs do not match exact test cohort")
    for uid, row in target_by_id.items():
        if not isinstance(row.get("annotation_sha256"), str) or len(row["annotation_sha256"]) != 64 or not isinstance(row.get("media_sha256"), str) or len(row["media_sha256"]) != 64:
            raise FinalTestLockError(f"{uid}: annotation/media receipt hashes required")
    candidates = config.get("candidates")
    contrasts = config.get("contrasts")
    if (not isinstance(candidates, list) or not candidates or len(set(candidates)) != len(candidates)
            or not all(isinstance(name, str) and name for name in candidates)
            or not isinstance(contrasts, list) or not contrasts):
        raise FinalTestLockError("candidates/contrasts must be predeclared")
    for contrast in contrasts:
        if not isinstance(contrast, dict) or contrast.get("candidate") not in candidates or contrast.get("baseline") not in candidates or contrast["candidate"] == contrast["baseline"]:
            raise FinalTestLockError("invalid predeclared contrast")
    contrast_pairs = [(contrast["candidate"], contrast["baseline"]) for contrast in contrasts]
    if len(set(contrast_pairs)) != len(contrast_pairs):
        raise FinalTestLockError("duplicate predeclared contrast")
    if mode == "official":
        _read_locked(base, lock, "protocol")
        receipts = config.get("candidate_execution_receipts")
        if not isinstance(receipts, dict) or set(receipts) != set(candidates):
            raise FinalTestLockError("official candidate execution receipts must cover exact candidates")
        for candidate, receipt in receipts.items():
            if not isinstance(receipt, dict) or not all(isinstance(receipt.get(key), str) and len(receipt[key]) == 64
                                                        for key in ("code_sha256", "input_features_sha256")):
                raise FinalTestLockError(f"{candidate}: code/input provenance hashes required")
    prediction_sha = _sha(prediction_path)
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    if (prediction.get("lock_sha256") != _sha(lock_path)
            or prediction.get("candidate_config_sha256") != lock["candidate_config"]["sha256"]
            or not isinstance(prediction.get("rows"), list)):
        raise FinalTestLockError("prediction artifact does not bind this lock/config")
    expected = {(uid, candidate) for uid in test_ids for candidate in candidates}
    actual = [(row.get("video_id"), row.get("candidate")) for row in prediction["rows"] if isinstance(row, dict)]
    if len(actual) != len(prediction["rows"]) or len(actual) != len(expected) or set(actual) != expected:
        raise FinalTestLockError("prediction artifact must contain one row per test video/candidate")
    by_pair = {(row["video_id"], row["candidate"]): row for row in prediction["rows"]}
    scores = []
    for uid in test_ids:
        target = target_by_id[uid]
        for candidate in candidates:
            pred = by_pair[(uid, candidate)]
            if pred.get("status") == "candidate_unit_failure":
                payload = None
            elif pred.get("status") == "run":
                payload = pred.get("predicted_sec")
            else:
                raise FinalTestLockError("prediction status must be run or candidate_unit_failure")
            scores.append(score_official_unit(unit_id=uid, candidate=candidate, predicted_sec=payload,
                                              reference_sec=target["reference_sec"], duration_sec=target["duration_sec"]))
    macro = {name: macro_primary_f1([row for row in scores if row["candidate"] == name],
                                     expected_candidate=name, expected_unit_ids=test_ids) for name in candidates}
    score_map = {uid: {row["candidate"]: row["metrics"]["collar_f1_3s"] for row in scores if row["unit_id"] == uid} for uid in test_ids}
    seed = config.get("bootstrap_seed")
    resamples = config.get("bootstrap_resamples")
    if isinstance(seed, bool) or not isinstance(seed, int) or isinstance(resamples, bool) or resamples != 10_000:
        raise FinalTestLockError("locked bootstrap seed and 10000 resamples required")
    comparisons = [grouped_paired_bootstrap(score_map, test_groups, candidate=c["candidate"],
                    baseline=c["baseline"], seed=seed + i, resamples=resamples) for i, c in enumerate(contrasts)]
    _group_inference(comparisons)
    report = {"schema": "rq1-final-test-report/1", "mode": mode,
              "status": "fixture_only" if mode == "fixture" else "official_scored",
              "run_id": lock.get("run_id"), "created_utc": datetime.now(timezone.utc).isoformat(),
              "lock_sha256": _sha(lock_path), "prediction_sha256": prediction_sha,
              "input_sha256": {key: lock[key]["sha256"] for key in ("cohort", "history", "targets", "candidate_config")},
              "runtime_code_sha256": {"runner": _sha(Path(__file__)),
                                      "scorer": _sha(Path(score_official_unit.__code__.co_filename)),
                                      "grouped_bootstrap": _sha(Path(grouped_paired_bootstrap.__code__.co_filename))},
              "test_video_ids": test_ids, "test_groups": test_groups, "candidate_macro": macro,
              "paired_grouped_comparisons": comparisons, "per_unit_scores": scores}
    output_dir.mkdir(parents=True)
    output = output_dir / "report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "report.sha256").write_text(_sha(output) + "  report.json\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run_sealed_scores(args.lock, args.predictions, args.output_dir)
    print(json.dumps({"status": result["status"], "report": str(args.output_dir / "report.json")}))


if __name__ == "__main__":
    main()
