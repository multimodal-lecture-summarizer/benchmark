"""Whole-corpus IIIT-CVID frame and crop EDA before research splitting."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from PIL import Image


def _quantiles(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)
    return {str(q): float(ordered[round(q * (len(ordered) - 1))])
            for q in (0, .25, .5, .75, .95, 1)}


def _frame_row(image_path: Path) -> dict:
    xml_path = image_path.with_suffix(".xml")
    with Image.open(image_path) as image:
        width, height, mode = image.width, image.height, image.mode
    root = ET.parse(xml_path).getroot()
    try:
        xml_width = int(root.findtext("size/width"))
        xml_height = int(root.findtext("size/height"))
        xml_size_mismatch = (xml_width, xml_height) != (width, height)
    except (TypeError, ValueError):
        xml_size_mismatch = True
    names = []
    invalid_boxes = 0
    for obj in root.findall("object"):
        names.append((obj.findtext("name") or "").strip())
        box = obj.find("bndbox")
        if box is None:
            invalid_boxes += 1
            continue
        try:
            x1, y1, x2, y2 = [float(box.findtext(key)) for key in
                              ("xmin", "ymin", "xmax", "ymax")]
            if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
                invalid_boxes += 1
        except (TypeError, ValueError):
            invalid_boxes += 1
    return {
        "bytes": image_path.stat().st_size, "width": width, "height": height,
        "mode": mode, "lines": len(names), "blank_lines": sum(not x for x in names),
        "invalid_boxes": invalid_boxes, "label_characters": sum(len(x) for x in names),
        "label_words": sum(len(x.split()) for x in names),
        "xml_size_mismatch": xml_size_mismatch,
    }


def _crop_stats(base: Path, split: str) -> dict:
    labels = base / f"{split}.txt"
    n = 0
    missing = 0
    blank = 0
    paths = set()
    lengths = []
    sizes = []
    dimensions = Counter()
    label_counts = Counter()
    non_ascii_labels = 0
    numeric_labels = 0
    for raw in labels.open(encoding="utf-8", errors="replace"):
        name, separator, label = raw.rstrip("\r\n").partition(".png ")
        if not separator:
            raise ValueError(f"Invalid crop label row in {labels}: {raw[:100]}")
        rel = name + ".png"
        path = base / rel
        n += 1
        paths.add(rel.replace("//", "/"))
        blank += not label.strip()
        cleaned = label.strip()
        lengths.append(len(cleaned))
        label_counts[cleaned.casefold()] += 1
        non_ascii_labels += any(ord(char) > 127 for char in cleaned)
        numeric_labels += cleaned.isnumeric()
        if not path.is_file():
            missing += 1
            continue
        sizes.append(path.stat().st_size)
        # Read every crop header. Pixel content is not decoded for this inventory.
        with Image.open(path) as image:
            dimensions[(image.width, image.height)] += 1
    disk_files = sum(1 for _ in (base / "Crops" / split).rglob("*.png"))
    return {
        "source_split": split, "label_rows": n, "crop_files": disk_files,
        "unique_label_paths": len(paths), "missing_labeled_images": missing,
        "unlabeled_image_files": disk_files - (n - missing), "blank_labels": blank,
        "unique_label_strings": len(label_counts),
        "repeated_label_rows": sum(count for count in label_counts.values() if count > 1),
        "non_ascii_labels": non_ascii_labels, "numeric_labels": numeric_labels,
        "top_labels": [{"text": text, "n": count} for text, count in label_counts.most_common(15)],
        "label_length_quantiles": _quantiles(lengths),
        "file_size_quantiles_bytes": _quantiles(sizes),
        "top_image_dimensions": [
            {"width": w, "height": h, "n": count}
            for (w, h), count in dimensions.most_common(10)
        ],
    }


def analyze_visual(root: Path) -> dict:
    """Scan every IIIT-CVID frame/XML and crop label/header, across native splits."""
    base = root / "experiments/datasets/iiit_cvid/IIIT-CVid"
    frame_summaries = []
    crop_summaries = []
    split_courses = {}
    split_videos = {}
    for split in ("train", "val", "test"):
        images = sorted((base / "Frames" / split).rglob("*.png"))
        xml_count = sum(1 for _ in (base / "Frames" / split).rglob("*.xml"))
        courses = Counter()
        videos = Counter()
        widths, heights, sizes, lines_per_frame = [], [], [], []
        modes = Counter()
        total_lines = total_words = blank_lines = invalid_boxes = xml_size_mismatches = 0
        invalid_box_frames = []
        xml_size_mismatch_frames = []
        for path in images:
            rel = path.relative_to(base / "Frames" / split)
            course, video = rel.parts[:2]
            courses[course] += 1
            videos[f"{course}/{video}"] += 1
            if not path.with_suffix(".xml").is_file():
                raise ValueError(f"Frame has no XML: {path}")
            row = _frame_row(path)
            widths.append(row["width"])
            heights.append(row["height"])
            sizes.append(row["bytes"])
            lines_per_frame.append(row["lines"])
            modes[row["mode"]] += 1
            total_lines += row["lines"]
            total_words += row["label_words"]
            blank_lines += row["blank_lines"]
            invalid_boxes += row["invalid_boxes"]
            xml_size_mismatches += row["xml_size_mismatch"]
            if row["xml_size_mismatch"]:
                xml_size_mismatch_frames.append(str(rel))
            if row["invalid_boxes"]:
                invalid_box_frames.append({
                    "relative_path": str(rel), "invalid_boxes": row["invalid_boxes"]
                })
        split_courses[split] = set(courses)
        split_videos[split] = set(videos)
        frame_summaries.append({
            "source_split": split, "frames": len(images), "xml_files": xml_count,
            "courses": len(courses), "videos": len(videos),
            "frames_per_course": dict(sorted(courses.items())),
            "frames_per_video_quantiles": _quantiles(list(videos.values())),
            "width_quantiles": _quantiles(widths), "height_quantiles": _quantiles(heights),
            "size_quantiles_bytes": _quantiles(sizes),
            "image_modes": dict(modes), "text_lines": total_lines,
            "text_words": total_words, "blank_text_lines": blank_lines,
            "invalid_boxes": invalid_boxes,
            "invalid_box_frames": invalid_box_frames,
            "xml_size_mismatches": xml_size_mismatches,
            "xml_size_mismatch_examples": xml_size_mismatch_frames[:20],
            "lines_per_frame_quantiles": _quantiles(lines_per_frame),
        })
        crop_summaries.append(_crop_stats(base, split))

    overlaps = []
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlaps.append({"left": left, "right": right,
                         "same_courses": len(split_courses[left] & split_courses[right]),
                         "same_videos": len(split_videos[left] & split_videos[right])})
    repaired = (root / "experiments/outputs/phase12_repair_260926/20260926T094154516917Z"
                / "iiit_cvid/official/full/payloads")
    readiness = (root / "experiments/outputs/dataset_readiness_260926/20260926T101747121197Z"
                 / "bundle/iiit_cvid")
    freeze = json.loads((repaired / "dataset.frozen_manifest.json").read_text(encoding="utf-8"))["records"][0]
    screening = json.loads((readiness / "screening.json").read_text(encoding="utf-8"))
    selection = json.loads((readiness / "split-manifest.json").read_text(encoding="utf-8"))
    return {
        "dataset": "iiit_cvid", "scope": "all_source_splits_frame_xml_and_crop_labels_headers",
        "frames": frame_summaries, "crops": crop_summaries,
        "source_split_overlap": overlaps,
        "historical_d2_status": freeze["freeze_status"],
        "historical_d2_reason": freeze["reason"],
        "readiness_selected": screening["selected_count"],
        "readiness_retained": screening["retained_count"],
        "readiness_selection_eligible": selection["scientific_selection_eligible"],
        "input_paths": [str(base), str(repaired), str(readiness)],
        "limitations": [
            "All native test XML reference texts were included in aggregate EDA; this is not untouched label content.",
            "Crop headers were read for every image, but full pixel decode/checksum was not repeated for all crops.",
            "Near-duplicate visual similarity is not established by course/video IDs or XML labels.",
            "IIIT-CVID supports OCR, not scene-cut, keyframe, or caption ground truth.",
        ],
    }
