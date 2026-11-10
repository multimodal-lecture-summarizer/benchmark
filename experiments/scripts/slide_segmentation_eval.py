"""Diagnostic evaluation of scene segmenters on the MLPDataset slide-transition cohort.

Runs the app's own ``SceneDetector.detect_scenes`` per video, then scores the predicted
boundaries against the released marks with ``mlpdataset_transition_scoring.score_videos``
(``formal=False``, ``label_track="raw_released"``). Results are diagnostic only: MLPDataset is
not eligible for formal scoring, so never report them as a confirmed benchmark.

Does not download anything. Put ``<video_id>.mp4`` files in ``--video-dir`` (outside git).

Examples:
    python slide_segmentation_eval.py --role tuning --segmenter slide --video-dir D:/media \
        --out out/tuning-slide.json
    python slide_segmentation_eval.py --role report --segmenter content --video-dir D:/media \
        --out out/report-content.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
APP_ROOT = REPO_ROOT / "multimodal-lecture-summarizer"
DEFAULT_COHORT = HERE.parent / "registry" / "datasets" / "slide-segmentation-eval-cohort.json"
COLLARS = (0.5, 1.0, 2.0)
ROLES = ("tuning", "report", "speaker_layout")

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(APP_ROOT))

from mlpdataset_transition_scoring import score_videos  # noqa: E402


def run_one(video_path: Path, segmenter: str, funnel: bool) -> dict:
    """Detect scenes for one video. Failures are returned, never turned into an empty list."""
    from ai_workers.modules.visual_v2.scene_detector import SceneDetector

    started = time.perf_counter()
    try:
        detector = SceneDetector({"segmenter": segmenter})
        scenes = detector.detect_scenes(str(video_path))
        if not scenes or scenes[-1]["end_seconds"] <= 0:
            raise ValueError("no usable duration (truncated or unreadable media?)")
        record = {
            "status": "ok",
            "segmenter_used": detector.segmenter_used,
            "runtime_sec": round(time.perf_counter() - started, 2),
            "scene_count": len(scenes),
            "duration_sec": scenes[-1]["end_seconds"] if scenes else 0.0,
            "predicted_sec": [s["start_seconds"] for s in scenes[1:]],
            "longest_scene_share": longest_share(scenes),
        }
        if funnel:
            record["funnel"] = measure_funnel(detector, video_path, scenes)
        return record
    except Exception as err:  # recorded in the ledger by the caller
        return {
            "status": "error",
            "error": f"{type(err).__name__}: {err}",
            "runtime_sec": round(time.perf_counter() - started, 2),
        }


def longest_share(scenes: list[dict]) -> float | None:
    if not scenes:
        return None
    total = scenes[-1]["end_seconds"] - scenes[0]["start_seconds"]
    if total <= 0:
        return None
    return round(max(s["end_seconds"] - s["start_seconds"] for s in scenes) / total, 4)


def measure_funnel(detector, video_path: Path, scenes: list[dict]) -> dict:
    """Scene counts after detection and after the CLIP-stage filter (needs the models)."""
    import tempfile

    from ai_workers.modules.visual_v2.semantic import SemanticAnalyzer

    with tempfile.TemporaryDirectory() as tmp:
        strategy = "last_stable" if detector.segmenter_used == "slide" else "sharpest"
        detector.extract_keyframes(str(video_path), scenes, tmp, strategy=strategy)
        semantic = SemanticAnalyzer()
        if detector.segmenter_used == "slide":
            kept = semantic.filter_slide_segments(scenes)
        else:
            kept = semantic.filter_scenes_clip(scenes)
        return {"detected": len(scenes), "after_clip_filter": len(kept)}


def build_sources(cohort_entries: list[dict], runs: dict[str, dict]) -> tuple[dict, dict, dict]:
    """Scorer inputs. Reference marks at or after the video end are dropped and counted."""
    sources, truth, predictions = {}, {}, {}
    for entry in cohort_entries:
        run = runs.get(entry["video_id"])
        if not entry["labelled"] or not run or run["status"] != "ok":
            continue
        duration = float(run["duration_sec"])
        marks = [t for t in entry["released_times_sec"] if 0 <= t < duration]
        sources[entry["video_id"]] = {
            "duration_sec": duration,
            "group": entry["group"],
            "eligible": True,
            "fully_annotated_scope": True,
            "hold_intervals": [],
            "ignored_event_count": len(entry["released_times_sec"]) - len(marks),
        }
        truth[entry["video_id"]] = marks
        predictions[entry["video_id"]] = [t for t in run["predicted_sec"] if 0 <= t < duration]
    return sources, truth, predictions


def summarize(scores: dict) -> dict:
    return {
        "pooled": scores["pooled"],
        "macro_group": scores["macro_group"],
        "per_group": scores["per_group"],
        "per_video": {
            k: {m: v[m] for m in ("tp", "fp", "fn", "precision", "recall", "f1", "group")}
            for k, v in scores["per_video"].items()
        },
        "ignored_event_count": scores["ignored_event_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--segmenter", choices=("content", "slide"), required=True)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--funnel", action="store_true", help="also measure the CLIP-stage funnel (loads models)")
    args = parser.parse_args()

    cohort = json.loads(args.cohort.read_text(encoding="utf-8"))
    entries = cohort[args.role]
    runs: dict[str, dict] = {}
    ledger: list[dict] = []
    for entry in entries:
        video_id = entry["video_id"]
        path = args.video_dir / f"{video_id}.mp4"
        if not path.is_file():
            runs[video_id] = {"status": "error", "error": f"missing media file: {path.name}"}
        else:
            runs[video_id] = run_one(path, args.segmenter, args.funnel)
        if runs[video_id]["status"] != "ok":
            ledger.append({"video_id": video_id, "error": runs[video_id]["error"]})
        print(f"{video_id}: {runs[video_id]['status']}", flush=True)

    result = {
        "status": "diagnostic_only",
        "formal_scoring_eligible": False,
        "role": args.role,
        "segmenter": args.segmenter,
        "cohort": cohort["cohort_id"],
        "label_track": cohort["label_track"],
        "runs": runs,
        "failure_ledger": ledger,
    }
    sources, truth, predictions = build_sources(entries, runs)
    if sources:
        result["scores"] = {
            str(collar): summarize(
                score_videos(truth, predictions, sources, label_track=cohort["label_track"],
                             collar=collar, formal=False)
            )
            for collar in COLLARS
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {args.out}; failures: {len(ledger)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
