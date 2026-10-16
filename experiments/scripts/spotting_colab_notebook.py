"""Notebook displays and portable evidence export; no model imports in the kernel."""
from __future__ import annotations

import hashlib
import json
import csv
import html
import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def render_figures(output_root):
    """Render measured CSV outputs inside the pinned scoring/orchestrator environment."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = Path(output_root)
    summary_path = root / "analysis-summary.json"
    summary_sha = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for entry in summary["artifacts"].values():
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("analysis export changed before visualization")
    receipt_path = root / "visualization-receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["analysis_sha256"] != summary_sha:
            raise ValueError("analysis changed since visualization seal")
        for entry in receipt["artifacts"]:
            if hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("visualization artifact changed")
        return receipt
    def rows(name):
        with (root / name).open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    metrics = rows("metrics.csv")
    groups = rows("group-metrics.csv")
    bootstrap = rows("bootstrap.csv")
    candidates = summary["candidate_order"]
    directory = root / "figures"
    directory.mkdir(exist_ok=True)
    figures = []
    def save(fig, name):
        fig.tight_layout()
        path = directory / (name + ".png")
        stream = io.BytesIO()
        fig.savefig(stream, format="png", dpi=150, metadata={"Software": "CVID spotting frozen visualization"})
        content = stream.getvalue()
        if path.exists() and path.read_bytes() != content:
            raise ValueError("existing figure differs; inspect interrupted visualization before retry")
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(content)
        plt.close(fig)
        figures.append({"path": path.relative_to(root).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    primary = {(r["candidate_id"], r["metric"]): r for r in metrics if r["variant"] == "primary"}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, metric in zip(axes, ("spotting", "detection")):
        ax.barh(candidates, [float(primary[c, metric]["hmean"]) for c in candidates])
        ax.set(xlim=(0, 1), xlabel="Pooled Hmean", title=metric + " — primary released-label agreement")
    save(fig, "01-primary-hmean")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, field in zip(axes, ("precision", "recall", "hmean")):
        ax.barh(candidates, [float(primary[c, "detection"][field]) for c in candidates])
        ax.set(xlim=(0, 1), title="Detection " + field)
    save(fig, "02-detection-prf")
    variants = list(dict.fromkeys(r["variant"] for r in metrics))
    fig, ax = plt.subplots(figsize=(13, 7))
    for cid in candidates:
        values = {r["variant"]: float(r["hmean"]) for r in metrics if r["candidate_id"] == cid and r["metric"] == "spotting"}
        ax.plot(variants, [values[v] for v in variants], marker="o", label=cid)
    ax.set(ylabel="Pooled spotting Hmean", title="Fixed sensitivity variants; same predictions")
    ax.legend(fontsize=8)
    save(fig, "03-fixed-sensitivity")
    fig, ax = plt.subplots(figsize=(13, 7))
    for cid in candidates:
        course = [r for r in groups if r["candidate_id"] == cid and r["variant"] == "primary" and r["metric"] == "spotting" and r["group_type"] == "course"]
        ax.plot([r["group"] for r in course], [float(r["hmean"]) for r in course], marker="o", label=cid)
    ax.set(xlabel="Course proxy", ylabel="Pooled within-course Hmean", title="Seven-course heterogeneity")
    ax.legend(fontsize=8)
    save(fig, "04-course-breakdown")
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.barh(candidates, [int(primary[c, "spotting"]["failed_frames"]) for c in candidates])
    ax.set(xlabel="Failed frames (remain in GT denominator)", title="Complete-cohort inference failures")
    save(fig, "05-failure-coverage")
    selected = [r for r in bootstrap if r["variant"] == "primary"]
    fig, ax = plt.subplots(figsize=(14, max(5, len(selected) * .45)))
    for index, row in enumerate(selected):
        ax.plot([float(row["low"]), float(row["high"])], [index, index], color="tab:blue")
        ax.plot(float(row["delta"]), index, "o", color="tab:blue")
    ax.set_yticks(range(len(selected)), [r["candidate_id"] + " / " + r["group_key"] for r in selected])
    ax.axvline(0, color="black", linewidth=1)
    ax.set(xlabel="Spotting Hmean difference from fixed Paddle anchor", title="Exploratory paired cluster bootstrap; unadjusted 95% intervals")
    save(fig, "06-paired-uncertainty")
    receipt = {"analysis_sha256": summary_sha, "artifacts": figures,
               "matplotlib": matplotlib.__version__, "purpose": "measured comparison visualization; no selection"}
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
    return receipt


def display_results(output_root):
    from IPython.display import HTML, Image, display
    root = Path(output_root)
    summary = root / "analysis-summary.json"
    if not summary.exists():
        raise FileNotFoundError("No completed comparison receipt; run analyze after inference.")
    print(summary.read_text(encoding="utf-8"))
    for path in sorted(root.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        print(path.name, f"({max(0, len(rows)-1)} rows; full CSV retained)")
        # Full exports stay downloadable; large per-frame tables have scroll containers.
        display(HTML('<div style="max-height:550px;overflow:auto">' +
                     '<table>' + ''.join('<tr>' + ''.join('<td>' + html.escape(value) +
                     '</td>' for value in row) + '</tr>' for row in rows) + '</table></div>'))
    for path in sorted(root.rglob("*.png")):
        print(path.relative_to(root))
        display(Image(filename=str(path)))


def export_evidence(output_root, destination=None):
    """Export every output file, including checkpoints, failures and package seals."""
    root = Path(output_root).resolve()
    destination = Path(destination or root.parent / (root.name + "-evidence.zip")).resolve()
    if destination.is_relative_to(root):
        raise ValueError("export archive must be outside output root")
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink())
    entries = []
    with ZipFile(destination, "w", ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in files:
            content = path.read_bytes()
            relative = path.relative_to(root).as_posix()
            entries.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(),
                            "bytes": len(content)})
            archive.writestr(relative, content)
        archive.writestr("export-manifest.json", json.dumps({"files": entries}, indent=2))
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {"path": str(destination), "sha256": digest, "files": len(entries),
            "completed_comparison": (root / "analysis-summary.json").exists()}
