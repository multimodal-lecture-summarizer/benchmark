"""Full-frame exact and perceptual duplicate screen for IIIT-CVID."""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageOps


def _dhash(image: Image.Image) -> int:
    pixels = list(ImageOps.grayscale(image).resize((9, 8)).getdata())
    result = 0
    for y in range(8):
        for x in range(8):
            result = (result << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return result


def screen_visual_duplicates(root: Path, threshold: int = 6) -> dict:
    """Read all 5,475 frames; similarities are candidate pairs, not GT exclusions."""
    base = root / "experiments/datasets/iiit_cvid/IIIT-CVid/Frames"
    rows = []
    for split in ("train", "val", "test"):
        for path in sorted((base / split).rglob("*.png")):
            raw = path.read_bytes()
            with Image.open(io.BytesIO(raw)) as image:
                visual_hash = _dhash(image)
            annotation = ET.parse(path.with_suffix(".xml")).getroot()
            reference = " ".join((item.findtext("name") or "") for item in annotation.findall("object"))
            tokens = set(re.findall(r"[a-z0-9]+", reference.casefold()))
            rows.append({
                "split": split, "relative_path": str(path.relative_to(base)),
                "sha256": hashlib.sha256(raw).hexdigest(), "dhash": visual_hash,
                "reference_tokens": tokens,
            })
    by_hash = defaultdict(list)
    for row in rows:
        by_hash[row["sha256"]].append(row)
    exact_groups = [group for group in by_hash.values() if len(group) > 1]
    exact_cross = [group for group in exact_groups if len({row["split"] for row in group}) > 1]

    near_cross_pairs = 0
    near_within_pairs = 0
    near_cross_high_text_overlap = 0
    cross_units = set()
    examples = []
    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            distance = (left["dhash"] ^ right["dhash"]).bit_count()
            if distance > threshold or left["sha256"] == right["sha256"]:
                continue
            if left["split"] == right["split"]:
                near_within_pairs += 1
            else:
                near_cross_pairs += 1
                cross_units.update((left["relative_path"], right["relative_path"]))
                union = left["reference_tokens"] | right["reference_tokens"]
                intersection = left["reference_tokens"] & right["reference_tokens"]
                text_jaccard = len(intersection) / len(union) if union else 0.0
                near_cross_high_text_overlap += len(union) >= 5 and text_jaccard >= .8
                if len(examples) < 20:
                    examples.append({
                        "left": left["relative_path"], "right": right["relative_path"],
                        "hamming": distance, "text_jaccard": round(text_jaccard, 4),
                    })
    return {
        "frames_scanned": len(rows), "method": "64_bit_dhash_hamming_at_most_6",
        "threshold": threshold,
        "exact_duplicate_groups": len(exact_groups),
        "exact_cross_split_groups": len(exact_cross),
        "exact_cross_split_examples": [
            [row["relative_path"] for row in group[:4]] for group in exact_cross[:10]
        ],
        "near_cross_split_pairs": near_cross_pairs,
        "near_cross_split_pairs_high_text_overlap": near_cross_high_text_overlap,
        "near_within_split_pairs": near_within_pairs,
        "near_cross_split_affected_frames": len(cross_units),
        "near_cross_split_examples": examples,
        "interpretation": "A dHash match is a review candidate; it does not prove two frames carry the same text or lecture content.",
    }
