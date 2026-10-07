"""Render measured candidate-readiness EDA; these artifacts do not confer D2 eligibility."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.scripts.dataset_readiness_plot_helpers import plot_tables


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _matrix(ax, values, labels, title, *, percent=False):
    import numpy as np
    from matplotlib import colormaps

    matrix = np.array([[float("nan") if v is None else v for v in row] for row in values])
    cmap = colormaps["Blues"].copy()
    cmap.set_bad("#eeeeee")
    ax.imshow(np.ma.masked_invalid(matrix), cmap=cmap, vmin=0,
              vmax=100 if percent else max(1, float(np.nanmax(matrix))) if np.isfinite(matrix).any() else 1,
              aspect="auto")
    ax.set_xticks(range(len(labels[0])), labels[0], rotation=25, ha="right")
    ax.set_yticks(range(len(labels[1])), labels[1])
    for row in range(matrix.shape[0]):
        for col in range(matrix.shape[1]):
            value = matrix[row, col]
            label = "N/A" if not np.isfinite(value) else f"{value:.0f}%" if percent else str(int(value))
            ax.text(col, row, label, ha="center", va="center", fontsize=9,
                    bbox={"facecolor": "white", "alpha": .72, "edgecolor": "none", "pad": 1})
    ax.set_title(title)


def _distribution(fig, data, title):
    import numpy as np

    if data.get("applicability") == "not_applicable":
        ax = fig.subplots()
        ax.axis("off")
        ax.text(.5, .6, "NOT APPLICABLE", fontsize=19, ha="center", transform=ax.transAxes)
        ax.text(.5, .43, data["reason"], fontsize=12, ha="center", transform=ax.transAxes)
        ax.text(.5, .28, f"Applicable n=0; N/A n={data['not_applicable_n']}; no zero durations imputed",
                fontsize=10, ha="center", transform=ax.transAxes)
        return
    axes = fig.subplots(1, 2)
    values, edges = data["values"], data["bins"]
    if not values:
        for ax in axes:
            ax.axis("off")
            ax.text(.5, .5, f"UNAVAILABLE: no measured {data['unit']}\nMissing n={data['missing_n']}",
                    ha="center", transform=ax.transAxes)
        return
    counts, _ = np.histogram(values, bins=edges)
    # Categorical fixed bins avoid silently clipping large values or tuning bins on test.
    axes[0].bar(range(len(counts)), counts, color="#315b7d")
    axes[0].set_xticks(range(len(counts)), [f"{a:g}–{b:g}" for a, b in zip(edges, edges[1:])],
                      rotation=65, ha="right", fontsize=7)
    axes[0].set(xlabel=f"Predeclared intervals ({data['unit']})", ylabel="Units", title=f"{title}: histogram")
    axes[1].step(values, np.arange(1, len(values) + 1) / len(values), where="post", color="#315b7d")
    axes[1].set(xlabel=data["unit"], ylabel="Cumulative fraction", ylim=(0, 1.03), title="Measured ECDF")
    axes[1].grid(alpha=.2)
    axes[1].text(.03, .93, f"Observed n={len(values)}; missing n={data['missing_n']}", transform=axes[1].transAxes)


def _draw(fig, figure_id, data):
    if figure_id in {"duration_distribution", "file_size_distribution"}:
        _distribution(fig, data, figure_id.replace("_", " "))
    elif figure_id == "missingness_gt_coverage":
        ax = fig.subplots()
        _matrix(ax, data["observed_percent"], (data["fields"], data["splits"]),
                "Nonempty reference / successful decode / observed metadata", percent=True)
        ax.set_ylabel("Split; denominator = all selected units within split")
    elif figure_id in {"source_overlap", "duplicate_matrix"}:
        axes = fig.subplots(1, 2)
        names = data.get("labels", ["Exact identity hits", "Near-screening hits"])
        for ax, (key, matrix), label in zip(axes, data["matrices"].items(), names):
            _matrix(ax, matrix, (data["splits"], data["splits"]), label)
        if figure_id == "duplicate_matrix":
            fig.text(.5, .17, f"Compared {data['completed_pairs']}/{data['expected_pairs']} expected pairs; {data['pair_count']} hits; audit={data['audit_status']}.",
                     ha="center", fontsize=9)
            fig.text(.5, .135, "N/A = incomplete or no comparisons. Off-diagonal mirrored; incomplete hit lower bounds retained in sidecar.",
                     ha="center", fontsize=9)
        else:
            missing = data["missing_group_metadata_n"]
            fig.text(.5, .17, f"Kept units: diagonal=distinct, off-diagonal=shared. Missing labels: speaker/course={missing['speaker_id']}, talk/video={missing['talk_id']}.", ha="center", fontsize=9)
    else:
        ax = fig.subplots()
        if figure_id == "scale_bytes":
            observed = [(i, value) for i, value in enumerate(data["bytes"]) if value is not None]
            ax.bar([i for i, _ in observed], [value for _, value in observed], color="#315b7d")
            ax.set_xticks(range(len(data["splits"])),
                          [f"{s}\nmeasured n={n}, missing n={m}" for s, n, m in
                           zip(data["splits"], data["measured_n"], data["missing_n_by_split"])])
            ax.set_xlim(-.5, len(data["splits"]) - .5)
            for i, value in enumerate(data["bytes"]):
                if value is None:
                    ax.text(i, .5, "N/A", ha="center", transform=ax.get_xaxis_transform())
            ax.set(ylabel="Observed bytes only", title=f"Sum of measured sizes only; missing size n={data['missing_n']}")
            ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        elif figure_id == "split_comparison":
            positions = list(range(len(data["splits"])))
            ax.bar([x - .2 for x in positions], data["selected"], width=.4, label="Selected", color="#9eafbe")
            ax.bar([x + .2 for x in positions], data["kept"], width=.4, label="Kept", color="#315b7d")
            ax.set_xticks(positions, data["splits"])
            ax.set(ylabel="Units", title="Selected and retained split composition")
            ax.legend()
        else:
            # Separate decoded subtotal from final decision reconciliation, not an additive total.
            names = ["Selected", "Decoded", "Kept", "Excluded"]
            heights = [data[k] for k in ("selected", "decoded", "kept", "excluded")]
            bottoms = [0, 0, 0, data["kept"]]
            ax.bar(names, heights, bottom=bottoms, color=["#9eafbe", "#67869d", "#315b7d", "#bf7356"])
            for i, (height, bottom) in enumerate(zip(heights, bottoms)):
                ax.text(i, bottom + height, str(height), ha="center", va="bottom")
            ax.set(ylabel="Units", title="Attrition: selected = kept + excluded; decoded is a subtotal")
        ax.grid(axis="y", alpha=.15)


def render_readiness_figures(run_root: Path, dataset_id: str, records: list[dict],
                             audit: dict, protocol: dict) -> list[dict]:
    """Write eight PNGs plus exact input sidecars; return a portable manifest.

    Paths are relative to run_root. Hashes cover exact on-disk bytes, including
    the protocol's canonical JSON newline. All plots use original denominators;
    the source-overlap matrix explicitly shows retained units only.
    """
    if not dataset_id or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in dataset_id):
        raise ValueError("unsafe dataset_id")
    tables = plot_tables(dataset_id, records, audit, protocol)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root = Path(run_root).resolve()
    folder = root / "figures" / dataset_id
    folder.mkdir(parents=True, exist_ok=True)
    code_paths = [Path(__file__), Path(__file__).with_name("dataset_readiness_plot_helpers.py")]
    code_revision = hashlib.sha256(b"".join(p.name.encode() + b"\0" + p.read_bytes() for p in code_paths)).hexdigest()
    protocol_hash = hashlib.sha256(_json_bytes(protocol)).hexdigest()
    # Store potentially large pair lists once, not once per figure. Sidecars bind
    # these complete inputs plus the exact small table consumed by each plot.
    input_files = {}
    for name, value in (("records", records), ("audit", audit), ("protocol", protocol)):
        input_path = folder / f"{name}.inputs.json"
        input_path.write_bytes(_json_bytes(value))
        input_files[name] = {"path": input_path.relative_to(root).as_posix(),
                             "sha256": hashlib.sha256(input_path.read_bytes()).hexdigest()}
    retained = sum(r["decision"] == "keep" for r in records)
    manifests = []
    for figure_id, data in tables.items():
        source = {"dataset_id": dataset_id, "figure_id": figure_id,
                  "inputs": input_files, "plot_data": data}
        source_path = folder / f"{figure_id}.source_table.json"
        source_path.write_bytes(_json_bytes(source))
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        output = folder / f"{figure_id}.png"
        fig = plt.figure(figsize=(12, 6.5), dpi=120)
        try:
            _draw(fig, figure_id, data)
            fig.suptitle(f"{dataset_id} — {figure_id.replace('_', ' ')}", fontsize=15)
            fig.text(.02, .07, f"CANDIDATE READINESS · selected n={len(records)} · kept n={retained} · no official D2 claim",
                     fontsize=9)
            fig.text(.02, .035, f"Protocol {protocol_hash[:12]} · source {source_hash[:12]} · code {code_revision[:12]}", fontsize=8)
            fig.tight_layout(rect=(0, .19, 1, .92))
            fig.savefig(output, metadata={"Software": "dataset-readiness-figures-v1"})
        finally:
            plt.close(fig)
        manifests.append({"dataset_id": dataset_id, "figure_id": figure_id,
                          "path": output.relative_to(root).as_posix(),
                          "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                          "source_table_path": source_path.relative_to(root).as_posix(),
                          "source_table_sha256": source_hash, "protocol_sha256": protocol_hash,
                          "code_revision": code_revision, "n": len(records), "kept_n": retained,
                          "scope": "candidate_readiness_all_selected", "official_d2": False,
                          "render_status": "not_applicable" if data.get("applicability") == "not_applicable" else "rendered",
                          "exclusion_policy": "recorded keep/exclude decisions; no refill",
                          "unit": "seconds" if figure_id == "duration_distribution" else "bytes" if figure_id in {"scale_bytes", "file_size_distribution"} else "percent" if figure_id == "missingness_gt_coverage" else "count"})
    return manifests
