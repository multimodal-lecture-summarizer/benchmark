"""Inventory official IIIT frame splits without reading pixels or labels."""
from pathlib import Path
import xml.etree.ElementTree as ET


def _parse_frame_transcriptions(xml_path: Path) -> tuple[str, int]:
    """Read Pascal-VOC text lines in deterministic top-to-bottom order."""
    root = ET.parse(xml_path).getroot()
    lines: list[tuple[int, int, str]] = []
    for obj in root.findall("object"):
        text = (obj.findtext("name") or "").strip()
        if not text:
            continue
        box = obj.find("bndbox")
        ymin = int(box.findtext("ymin", default="0")) if box is not None else 0
        xmin = int(box.findtext("xmin", default="0")) if box is not None else 0
        lines.append((ymin, xmin, text))
    lines.sort(key=lambda row: (row[0], row[1], row[2]))
    return "\n".join(row[2] for row in lines), len(lines)


def select_iiit(root: Path) -> dict:
    frames = root / "experiments/datasets/iiit_cvid/IIIT-CVid/Frames"
    selected, issues, courses = [], [], {}
    for native, split in (("val", "validation"), ("test", "final_test")):
        directory = frames / native
        if not directory.is_dir():
            raise ValueError(f"missing official IIIT split: {directory}")
        images = sorted(directory.rglob("*.png"))
        annotations = set(directory.rglob("*.xml"))
        courses[split] = set()
        for path in images:
            parts = path.relative_to(directory).parts
            if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit():
                issues.append({"reason": "malformed_image_path", "path": str(path)})
                continue
            course, video, filename = parts
            courses[split].add(course)
            annotation = path.with_suffix(".xml")
            if annotation not in annotations:
                issues.append({"reason": "missing_annotation", "path": str(annotation)})
            selected.append({"dataset_id": "iiit_cvid", "unit_id": f"{split}:{course}:{video}:{path.stem}",
                             "split": split, "original_split": native, "speaker_id": f"course_{course}",
                             "talk_id": f"{course}_{video}", "source_id": f"{course}/{video}",
                             "input_media_path": path.relative_to(root).as_posix(),
                             "annotation_path": annotation.relative_to(root).as_posix()})
        for annotation in sorted(annotations):
            if not annotation.with_suffix(".png").is_file():
                issues.append({"reason": "orphan_annotation", "path": str(annotation)})
        if not images:
            issues.append({"reason": "empty_official_split", "split": split})
    if courses["validation"] & courses["final_test"]:
        raise ValueError("IIIT official validation/test course overlap")
    return {"selected": selected, "historical": [], "issues": issues,
            "counts": {split: {"selected": sum(r["split"] == split for r in selected),
                                "courses": sorted(values)} for split, values in courses.items()},
            "index_policy": "sorted_official_png_xml_pairs; orphan/malformed paths block readiness",
            "selection_status": "blocked" if issues else "selected"}
