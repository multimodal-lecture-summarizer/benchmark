"""Inventory all materialized research datasets without running any model."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
from collections import Counter
from pathlib import Path


VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".m4v", ".webm"}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _q(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)
    return {str(p): float(ordered[round(p * (len(ordered) - 1))])
            for p in (0, .25, .5, .75, .95, 1)}


def _files(root: Path) -> dict:
    count = total = 0
    extensions = Counter()
    for folder, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".cache", ".git", "__pycache__"}]
        for name in names:
            path = Path(folder) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            count += 1
            total += size
            extensions[path.suffix.lower() or "(none)"] += 1
    return {"files": count, "bytes": total, "extensions": dict(extensions)}


def _video_probe(root: Path) -> dict:
    files = sorted(path for path in root.rglob("*") if path.is_file()
                   and path.suffix.lower() in VIDEO_SUFFIXES)
    durations, widths, heights = [], [], []
    errors = []
    for path in files:
        command = ["ffprobe", "-v", "error", "-show_entries",
                   "format=duration:stream=codec_type,width,height",
                   "-of", "json", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            errors.append({"file": str(path), "error": result.stderr[:160]})
            continue
        info = json.loads(result.stdout)
        duration = float(info.get("format", {}).get("duration", 0) or 0)
        visual = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        durations.append(duration)
        widths.append(int(visual.get("width") or 0))
        heights.append(int(visual.get("height") or 0))
    return {"materialized_videos": len(files), "probed": len(durations),
            "probe_errors": errors, "duration_seconds": _q(durations),
            "total_duration_seconds": sum(durations),
            "width_pixels": _q(widths), "height_pixels": _q(heights)}


def _eduviqa(base: Path) -> dict:
    qa = _read(base / "q_and_a.json")
    chunks = _read(base / "hybrid_clip_ssim_chunking_meta_data.json")
    ids = [str(item["video_id"]) for item in qa]
    counts, blank_q, blank_a = [], 0, 0
    question_words, answer_words = [], []
    repeated_questions = 0
    for item in qa:
        mapping = item["Q&A"]
        questions = [value for key, value in mapping.items() if key.startswith("question ")]
        answers = [value for key, value in mapping.items() if key.startswith("answer ")]
        counts.append(len(questions))
        blank_q += sum(not str(v).strip() for v in questions)
        blank_a += sum(not str(v).strip() for v in answers)
        question_words.extend(len(str(value).split()) for value in questions)
        answer_words.extend(len(str(value).split()) for value in answers)
        normalized = [str(value).casefold().strip() for value in questions]
        repeated_questions += len(normalized) - len(set(normalized))
        if len(questions) != len(answers):
            raise ValueError("EduViQA question/answer count mismatch")
    transitions = [len(item["hybrid_clip_ssim_timestamps"]) for item in chunks]
    transcript_paths = list((base / "video_transcripts").rglob("transcript.txt"))
    transcript_words = [len(path.read_text(encoding="utf-8", errors="replace").split())
                        for path in transcript_paths]
    return {"videos_with_qa": len(qa), "unique_video_ids": len(set(ids)),
            "qa_pairs": sum(counts), "qa_per_video": _q(counts),
            "blank_questions": blank_q, "blank_answers": blank_a,
            "repeated_questions_within_video": repeated_questions,
            "question_words": _q(question_words), "answer_words": _q(answer_words),
            "transcript_files": len(transcript_paths),
            "transcript_words": _q(transcript_words),
            "blank_transcripts": sum(value == 0 for value in transcript_words),
            "algorithmic_transition_timestamps": sum(transitions),
            "transitions_per_video": _q(transitions),
            "media": _video_probe(base / "Videos"),
            "reference_status": "QA provenance and evidence linkage unresolved; transitions are algorithmic, not scene GT"}


def _slidevqa(base: Path) -> dict:
    rows = []
    decks = {}
    for split, filename in (("train", "train.json"), ("val", "val.json"), ("test", "test.json")):
        entries = _read(base / "annotations" / filename)
        names = {str(item.get("deck_name") or "") for item in entries}
        decks[split] = names
        rows.append({"split": split, "qa_pairs": len(entries), "decks": len(names),
                     "blank_questions": sum(not str(item.get("question") or "").strip() for item in entries),
                     "blank_answers": sum(not str(item.get("answer") or "").strip() for item in entries),
                     "no_evidence_pages": sum(not item.get("evidence_pages") for item in entries),
                     "question_words": _q([len(str(item.get("question") or "").split()) for item in entries]),
                     "answer_words": _q([len(str(item.get("answer") or "").split()) for item in entries])})
    return {"splits": rows, "deck_overlap": {
        "train_val": len(decks["train"] & decks["val"]),
        "train_test": len(decks["train"] & decks["test"]),
        "val_test": len(decks["val"] & decks["test"])},
        "slide_images_present": False, "reference_status": "annotation-only local snapshot"}


def _vidchapters(base: Path) -> dict:
    splits = {}
    for split in ("train", "val", "test"):
        ids = _read(base / f"{split}.json")
        splits[split] = set(ids)
    return {"annotation_id_counts": {key: len(value) for key, value in splits.items()},
            "cross_split_id_overlap": {
                "train_val": len(splits["train"] & splits["val"]),
                "train_test": len(splits["train"] & splits["test"]),
                "val_test": len(splits["val"] & splits["test"])},
            "media": _video_probe(base / "media"),
            "chapter_payload_bytes": (base / "chapters.pkl").stat().st_size,
            "chapter_payload_status": "not_deserialized_untrusted_pickle"}


def _ytseg(base: Path) -> dict:
    import pyarrow.parquet as pq

    shards = sorted(base.rglob("*.parquet"))
    n = 0
    chapters = []
    durations = []
    ids = set()
    missing = 0
    for shard in shards:
        parquet = pq.ParquetFile(shard)
        n += parquet.metadata.num_rows
        for batch in parquet.iter_batches(columns=["video_id", "duration", "chapter_timestamps"],
                                          batch_size=1024):
            data = batch.to_pydict()
            for video_id, duration, markers in zip(
                data["video_id"], data["duration"], data["chapter_timestamps"]
            ):
                ids.add(str(video_id))
                if duration is None:
                    missing += 1
                else:
                    durations.append(float(duration))
                chapters.append(len(markers or []))
    return {"parquet_shards": len(shards), "annotation_rows": n,
            "unique_annotation_video_ids": len(ids), "missing_durations": missing,
            "rows_without_chapters": sum(value == 0 for value in chapters),
            "duration_seconds": _q(durations), "chapters_per_video": _q(chapters),
            "media": _video_probe(base),
            "reference_status": "creator chapters support chaptering, not scene-cut GT"}


def analyze_catalog(root: Path) -> dict:
    base = root / "experiments/datasets"
    inventory = {path.name: _files(path) for path in sorted(base.iterdir()) if path.is_dir()}
    mit = _read(base / "avlectures_mit001/media_audit.json")
    yale = _read(base / "yale_rq1_qualification/qualification_download_receipt.json")
    return {
        "scope": "all_materialized_dataset_directories",
        "inventory_policy": "Recursive file inventory excludes .cache, .git and __pycache to avoid counting redundant caches.",
        "inventory": inventory,
        "eduviqa": _eduviqa(base / "eduviqa"),
        "slidevqa": _slidevqa(base / "slidevqa"),
        "vidchapters": _vidchapters(base / "vidchapters_qualification"),
        "ytseg": _ytseg(base / "ytseg_qualification"),
        "yale": {"qualification_only": bool(yale["qualification_only"]),
                 "receipt_files": len(yale["files"]), "receipt_failures": len(yale["failures"]),
                 "media": _video_probe(base / "yale_rq1_qualification")},
        "mit001": {"expected_videos": mit["expected_gt_video_count"],
                   "actual_videos": mit["actual_mp4_count"],
                   "status_counts": mit["status_counts"],
                   "gt_segments": sum(item["gt_segments"] for item in mit["records"]),
                   "duration_seconds": _q([item["duration_sec"] for item in mit["records"]])},
        "tvsum": {"materialized_files": inventory["tvsum_extracted"]["files"],
                  "status": "not_materialized"},
        "limitations": [
            "Video probes read container metadata only, not all frames or audio samples.",
            "VidChapters 2 GB pickle was not deserialized; chapter content remains unverified.",
            "SlideVQA slide images and TVSum media/labels are absent locally.",
            "Media/annotation counts do not prove released GT, rights, or endpoint eligibility.",
        ],
    }
