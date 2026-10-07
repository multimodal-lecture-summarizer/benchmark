"""Generate a paged diagrams.net map of the benchmark directory tree."""

from __future__ import annotations

import argparse
import html
import os
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class Folder:
    children: list[str] = field(default_factory=list)
    direct_files: int = 0
    total_folders: int = 1
    is_git_metadata: bool = False


def scan(root: Path) -> dict[str, Folder]:
    folders = {".": Folder()}

    def fail(error: OSError) -> None:
        raise error

    for current, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        rel = Path(current).relative_to(root).as_posix()
        key = "." if rel == "." else rel
        dirs[:] = sorted((name for name in dirs if name != ".git"), key=str.casefold)
        folders[key].direct_files = len(files)
        for name in dirs:
            child = name if key == "." else f"{key}/{name}"
            folders[child] = Folder()
            folders[key].children.append(child)

    if (root / ".git").is_dir():
        folders[".git"] = Folder(is_git_metadata=True)
        folders["."].children.insert(0, ".git")

    def count(key: str) -> int:
        folder = folders[key]
        folder.total_folders = 1 + sum(count(child) for child in folder.children)
        return folder.total_folders

    count(".")
    return folders


def visible_tree(
    root: str, folders: dict[str, Folder], limit: int
) -> tuple[set[str], set[str]]:
    children = folders[root].children
    visible_count = folders[root].total_folders
    portals: set[str] = set()
    for child in sorted(children, key=lambda key: folders[key].total_folders, reverse=True):
        if visible_count <= limit:
            break
        if folders[child].total_folders > 1:
            portals.add(child)
            visible_count -= folders[child].total_folders - 1

    visible: set[str] = set()

    def visit(key: str) -> None:
        visible.add(key)
        if key not in portals:
            for child in folders[key].children:
                visit(child)

    visit(root)
    if len(visible) > limit:
        raise ValueError(f"Page {root} has {len(visible)} nodes; raise --page-limit")
    return visible, portals


def color(key: str, portal: bool, git: bool) -> tuple[str, str]:
    if git:
        return "#eeeeee", "#999999"
    if portal:
        return "#fff2cc", "#d6b656"
    if key.startswith("experiments/datasets"):
        return "#fce5cd", "#d79b00"
    if "/outputs" in key or key.startswith("outputs"):
        return "#d5e8d4", "#82b366"
    if key.startswith(("docs", "plans", "reports")):
        return "#e1d5e7", "#9673a6"
    return "#dae8fc", "#6c8ebf"


def make_page(
    mxfile: ET.Element,
    page_number: int,
    page_root: str,
    folders: dict[str, Folder],
    visible: set[str],
    portals: set[str],
) -> None:
    title = "Tổng quan" if page_root == "." else page_root
    diagram = ET.SubElement(
        mxfile, "diagram", {"id": f"page-{page_number}", "name": f"{page_number:02d} {title}"}
    )
    graph = ET.SubElement(diagram, "mxGraphModel", {
        "dx": "1600", "dy": "900", "grid": "1", "gridSize": "10",
        "page": "1", "pageScale": "1", "pageWidth": "1600", "pageHeight": "1200",
        "math": "0", "shadow": "0",
    })
    cells = ET.SubElement(graph, "root")
    ET.SubElement(cells, "mxCell", {"id": "0"})
    ET.SubElement(cells, "mxCell", {"id": "1", "parent": "0"})

    positions: dict[str, tuple[int, float]] = {}
    cursor = 115.0

    def place(key: str, depth: int) -> float:
        nonlocal cursor
        kids = [child for child in folders[key].children if child in visible]
        if not kids:
            y = cursor
            cursor += 54
        else:
            child_ys = [place(child, depth + 1) for child in kids]
            y = (child_ys[0] + child_ys[-1]) / 2
        positions[key] = (40 + depth * 270, y)
        return y

    place(page_root, 0)
    max_depth = max((x - 40) // 270 for x, _ in positions.values())
    graph.set("pageWidth", str(max(1200, 350 + max_depth * 270)))
    graph.set("pageHeight", str(max(800, int(cursor + 80))))

    note = ET.SubElement(cells, "mxCell", {
        "id": "note", "value": (
            f"Cây thư mục benchmark — {html.escape(title)} | "
            f"{len(visible)} nút trên trang | Ô vàng: xem trang cùng tên. "
            "Số tệp là số nằm trực tiếp trong thư mục; .git được thu gọn."
        ),
        "style": "text;html=1;align=left;verticalAlign=middle;fontSize=16;fontStyle=1;",
        "vertex": "1", "parent": "1",
    })
    ET.SubElement(note, "mxGeometry", {
        "x": "40", "y": "20", "width": str(max(1050, 250 + max_depth * 270)),
        "height": "55", "as": "geometry",
    })

    ids = {key: f"folder-{index}" for index, key in enumerate(sorted(visible), 1)}
    for key in sorted(visible):
        parent = key.rsplit("/", 1)[0] if "/" in key else "."
        if key == page_root or parent not in visible:
            continue
        edge = ET.SubElement(cells, "mxCell", {
            "id": f"edge-{ids[key]}", "edge": "1", "parent": "1",
            "source": ids[parent], "target": ids[key],
            "style": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;"
            "endArrow=none;strokeColor=#9aa7b1;",
        })
        ET.SubElement(edge, "mxGeometry", {"relative": "1", "as": "geometry"})

    for key in sorted(visible):
        folder = folders[key]
        name = "benchmark" if key == "." else key.rsplit("/", 1)[-1]
        suffix = " ↗" if key in portals else ""
        details = f"{folder.total_folders - 1} thư mục con · {folder.direct_files} tệp"
        if folder.is_git_metadata:
            details = "Git metadata · không mở rộng"
        value = f"<b>{html.escape(name + suffix)}/</b><br/><font style='font-size:10px'>{details}</font>"
        fill, stroke = color(key, key in portals, folder.is_git_metadata)
        x, y = positions[key]
        cell = ET.SubElement(cells, "mxCell", {
            "id": ids[key], "value": value, "vertex": "1", "parent": "1",
            "style": "rounded=1;whiteSpace=wrap;html=1;align=center;verticalAlign=middle;"
            f"fillColor={fill};strokeColor={stroke};fontSize=12;"
            + ("dashed=1;" if key in portals else ""),
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": str(x), "y": str(round(y - 19, 1)),
            "width": "230", "height": "38", "as": "geometry",
        })


def generate(root: Path, output: Path, limit: int) -> tuple[int, int]:
    folders = scan(root)
    mxfile = ET.Element("mxfile", {
        "host": "app.diagrams.net", "agent": "Codex", "version": "24.7.17",
        "type": "device",
    })
    pending = ["."]
    seen: set[str] = set()
    while pending:
        key = pending.pop(0)
        if key in seen:
            continue
        seen.add(key)
        visible, portals = visible_tree(key, folders, limit)
        make_page(mxfile, len(seen), key, folders, visible, portals)
        pending.extend(sorted(portals))
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(mxfile, space="  ")
    ET.ElementTree(mxfile).write(output, encoding="utf-8", xml_declaration=True)
    return len(folders), len(seen)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--page-limit", type=int, default=450)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "docs" / "visuals" / "benchmark-directory-tree.drawio").resolve()
    if args.page_limit < 20:
        parser.error("--page-limit must be at least 20")
    folders, pages = generate(root, output, args.page_limit)
    print(f"Wrote {output} ({folders} folder nodes across {pages} pages)")


if __name__ == "__main__":
    main()
