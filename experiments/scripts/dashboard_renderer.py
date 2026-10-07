"""dashboard_renderer.py — Plotly HTML dashboard generator.

Render 3 dashboard HTML files:
  1. Per-task leaderboard (1 file per task): bar chart + radar + table
  2. Cross-task comparison: heatmap tất cả tasks × candidates
  3. Ablation heatmap: 2^k toggle grid per task

Style: editorial (warm paper #faf7f2, ink #0a0a0a, accent red #b8232c).
Self-contained HTML với plotly.js bundled (offline-capable).

Usage:
    from experiments.scripts.dashboard_renderer import (
        render_per_task_leaderboard,
        render_cross_task_comparison,
        render_ablation_heatmap,
    )
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import plotly.graph_objects as go
import plotly.io as pio

from experiments.scripts.registry_loader import TaskID  # noqa: E402
from experiments.scripts.leaderboard_builder import TaskLeaderboard, CandidateScore  # noqa: E402


# Editorial color palette
PAPER_BG = "#faf7f2"
INK = "#0a0a0a"
MUTED = "#6b6258"
ACCENT_RED = "#b8232c"

pio.templates.default = "plotly_white"


# ---------------------------------------------------------------------------
# HTML wrapper (editorial style)
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    background: {paper_bg};
    color: {ink};
    margin: 0;
    padding: 0;
    line-line-height:1.5;
  }}
  .container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 2em 3em;
  }}
  .header {{
    border-bottom: 2px solid {ink};
    padding-bottom: 1em;
    margin-bottom: 2em;
  }}
  .eyebrow {{
    font-family: 'Courier New', monospace;
    font-size: 0.75em;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: {muted};
    margin-bottom: 0.25em;
  }}
  h1 {{
    font-size: 2.5em;
    margin: 0 0 0.25em;
    font-weight: 700;
  }}
  h2 {{
    font-size: 1.5em;
    margin-top: 2em;
    border-left: 3px solid {accent_red};
    padding-left: 0.5em;
  }}
  .winner {{
    font-size: 2em;
    font-style: italic;
    color: {accent_red};
    margin-top: 0.5em;
  }}
  .winner-meta {{
    font-family: 'Courier New', monospace;
    font-size: 0.9em;
    color: {muted};
    margin-top: 0.25em;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.95em;
  }}
  th, td {{
    text-align: left;
    padding: 0.5em 0.75em;
    border-bottom: 1px solid {muted};
  }}
  th {{
    font-family: 'Courier New', monospace;
    text-transform: uppercase;
    font-size: 0.75em;
    letter-spacing: 0.1em;
    color: {muted};
    border-bottom: 2px solid {ink};
  }}
  tr.winner-row td {{
    font-weight: 700;
    color: {accent_red};
    background: rgba(184, 35, 44, 0.05);
  }}
  .plot-div {{
    margin: 1.5em 0;
  }}
  .footer {{
    margin-top: 3em;
    padding-top: 1em;
    border-top: 1px solid {muted};
    font-size: 0.85em;
    color: {muted};
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="eyebrow">{eyebrow}</div>
    <h1>{heading}</h1>
    {winner_html}
  </div>
  <main>
    {content}
  </main>
  <div class="footer">
    Generated {timestamp} • Multimodal Lecture Summarizer Comparison Framework
  </div>
</div>
</body>
</html>
"""


def _wrap_html(
    title: str,
    heading: str,
    eyebrow: str,
    winner_html: str,
    content: str,
    timestamp: str,
) -> str:
    return HTML_TEMPLATE.format(
        title=title,
        heading=heading,
        eyebrow=eyebrow,
        winner_html=winner_html,
        content=content,
        paper_bg=PAPER_BG,
        ink=INK,
        muted=MUTED,
        accent_red=ACCENT_RED,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Per-task leaderboard HTML
# ---------------------------------------------------------------------------

def render_per_task_leaderboard(
    leaderboard: TaskLeaderboard,
    output_path: Path,
) -> Path:
    """
    Render per-task leaderboard HTML.
    Includes: bar chart of composite scores + radar of normalized metrics + table.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Bar chart — FIRST chart includes plotly.js from CDN
    fig_bar = go.Figure()
    cands = leaderboard.candidates
    colors_bar = [ACCENT_RED if c.is_winner else INK for c in cands]
    fig_bar.add_trace(go.Bar(
        x=[c.candidate_id for c in cands],
        y=[c.composite_score for c in cands],
        marker_color=colors_bar,
        text=[f"{c.composite_score:.3f}" for c in cands],
        textposition="outside",
    ))
    fig_bar.update_layout(
        title=f"Composite Scores — {leaderboard.task.value}",
        yaxis=dict(title="Composite Score", range=[0, 1]),
        xaxis=dict(title="Candidate (combo_id)", tickangle=-45),
        plot_bgcolor=PAPER_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(family="Georgia, serif", color=INK),
        height=450,
    )
    bar_html = fig_bar.to_html(full_html=False, include_plotlyjs="cdn")

    # Radar chart for top-5 candidates — NO plotly.js include (reuses first)
    top5 = cands[:5]
    if top5:
        metrics = leaderboard.metric_set
        fig_radar = go.Figure()
        for cand in top5:
            values = [cand.normalized_metrics.get(m, 0) for m in metrics]
            values.append(values[0])  # close polygon
            fig_radar.add_trace(go.Scatterpolar(
                r=values,
                theta=metrics + [metrics[0]],
                name=cand.candidate_id,
                line=dict(color=ACCENT_RED if cand.is_winner else MUTED, width=2),
            ))
        fig_radar.update_layout(
            title="Normalized Metrics — Top 5",
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            plot_bgcolor=PAPER_BG,
            paper_bgcolor=PAPER_BG,
            font=dict(family="Georgia, serif", color=INK),
            height=450,
        )
        radar_html = fig_radar.to_html(full_html=False, include_plotlyjs=False)
    else:
        radar_html = ""

    # Table
    table_rows = []
    for c in cands:
        is_winner_cls = " class=\"winner-row\"" if c.is_winner else ""
        marker = " <- WINNER" if c.is_winner else (" [Pareto]" if c.is_pareto_optimal else "")
        raw_cells = "".join(
            f"<td>{c.raw_metrics.get(m, 0):.4f}</td>"
            for m in leaderboard.metric_set
        )
        table_rows.append(
            f"<tr{is_winner_cls}><td>{c.rank}</td><td>{c.candidate_id}</td>"
            f"<td>{c.composite_score:.4f}{marker}</td>{raw_cells}</tr>"
        )
    header_cells = "".join(f"<th>{m}</th>" for m in leaderboard.metric_set)
    table_html = f"""
    <h2>Full Leaderboard</h2>
    <table>
      <thead>
        <tr><th>Rank</th><th>Candidate</th><th>Composite</th>{header_cells}</tr>
      </thead>
      <tbody>{''.join(table_rows)}</tbody>
    </table>
    """

    # Winner section
    winner_html = f"""
    <div class="winner">Winner: {leaderboard.winner_id}</div>
    <div class="winner-meta">
      Composite: {leaderboard.winner_composite:.4f} •
      95% CI: [{leaderboard.ci_95[0]:.4f}, {leaderboard.ci_95[1]:.4f}] •
      {leaderboard.n_candidates} candidates evaluated
    </div>
    """

    content = f"""
    <h2>Composite Scores</h2>
    <div class="plot-div">{bar_html}</div>
    <h2>Normalized Metrics — Top 5</h2>
    <div class="plot-div">{radar_html}</div>
    {table_html}
    """

    html = _wrap_html(
        title=f"Leaderboard — {leaderboard.task.value}",
        heading=f"{leaderboard.task.value} Leaderboard",
        eyebrow=f"MULTIMODAL LECTURE SUMMARIZER / {leaderboard.task.value}",
        winner_html=winner_html,
        content=content,
        timestamp=leaderboard.exported_at or "",
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Cross-task comparison HTML
# ---------------------------------------------------------------------------

def render_cross_task_comparison(
    leaderboards: Dict[str, TaskLeaderboard],
    output_path: Path,
) -> Path:
    """
    Render cross-task comparison: heatmap of winner per task + composite matrix.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tasks = sorted(leaderboards.keys())
    # Top 3 candidates per task
    all_top_candidates = set()
    for lb in leaderboards.values():
        for c in lb.candidates[:3]:
            all_top_candidates.add(c.candidate_id)
    top_candidates = sorted(all_top_candidates)

    # Build matrix: rows=top_candidates, cols=tasks
    matrix = []
    for cand_id in top_candidates:
        row = []
        for task in tasks:
            lb = leaderboards[task]
            cand = next((c for c in lb.candidates if c.candidate_id == cand_id), None)
            row.append(cand.composite_score if cand else None)
        matrix.append(row)

    fig_heat = go.Figure(data=go.Heatmap(
        z=matrix,
        x=tasks,
        y=top_candidates,
        colorscale=[[0, MUTED], [0.5, "#f5d76e"], [1, ACCENT_RED]],
        text=[[f"{v:.3f}" if v is not None else "—" for v in row] for row in matrix],
        texttemplate="%{text}",
        textfont=dict(size=10, color=INK),
        hovertemplate="Candidate: %{y}<br>Task: %{x}<br>Score: %{z:.3f}<extra></extra>",
    ))
    fig_heat.update_layout(
        title="Composite Score Matrix (Top 3 candidates per task)",
        plot_bgcolor=PAPER_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(family="Georgia, serif", color=INK),
        height=max(400, len(top_candidates) * 30 + 100),
        yaxis=dict(autorange="reversed"),
    )
    heatmap_html = fig_heat.to_html(full_html=False, include_plotlyjs="cdn")

    # Winner table per task
    winner_rows = []
    for task in tasks:
        lb = leaderboards[task]
        winner_rows.append(
            f"<tr><td>{task}</td><td>{lb.winner_id}</td>"
            f"<td>{lb.winner_composite:.4f}</td>"
            f"<td>[{lb.ci_95[0]:.4f}, {lb.ci_95[1]:.4f}]</td></tr>"
        )

    content = f"""
    <h2>Winners per Task</h2>
    <table>
      <thead>
        <tr><th>Task</th><th>Winner</th><th>Composite</th><th>95% CI</th></tr>
      </thead>
      <tbody>{''.join(winner_rows)}</tbody>
    </table>
    <h2>Composite Matrix — Top 3 Candidates × All Tasks</h2>
    <div class="plot-div">{heatmap_html}</div>
    """

    # Find overall winner (most frequent across tasks)
    from collections import Counter
    winner_counter = Counter(lb.winner_id for lb in leaderboards.values())
    most_common = winner_counter.most_common(1)[0] if winner_counter else ("none", 0)

    winner_html = f"""
    <div class="winner">Overall Top: {most_common[0]}</div>
    <div class="winner-meta">
      Won {most_common[1]} / {len(leaderboards)} tasks • {len(leaderboards)} tasks evaluated
    </div>
    """

    html = _wrap_html(
        title="Cross-task Leaderboard",
        heading="Cross-task Leaderboard",
        eyebrow="MULTIMODAL LECTURE SUMMARIZER / CROSS-TASK",
        winner_html=winner_html,
        content=content,
        timestamp="",
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Ablation heatmap
# ---------------------------------------------------------------------------

def render_ablation_heatmap(
    task: str,
    results_csv: Path,
    output_path: Path,
    metric_name: Optional[str] = None,
) -> Path:
    """
    Render ablation grid heatmap for 1 task từ ablation_audit.csv.
    Rows = base candidates, columns = toggle combinations, color = primary metric.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not results_csv.exists():
        raise FileNotFoundError(f"Results CSV not found: {results_csv}")

    # Group by base_id x toggle combo
    import csv as csv_mod
    base_to_combos: Dict[str, Dict[str, float]] = {}
    metric_used = metric_name

    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv_mod.DictReader(f)
        for row in reader:
            if row.get("status") != "OK":
                continue
            base = row["base_id"]
            toggle_json = row["toggle_values_json"]
            primary_value = float(row["primary_metric_value"]) if row["primary_metric_value"] else 0.0
            if not metric_used:
                metric_used = row["primary_metric_name"] or "metric"

            # Filter by task from combo_id (best effort)
            if not base.startswith(task):
                continue
            base_to_combos.setdefault(base, {})
            base_to_combos[base][toggle_json] = primary_value

    if not base_to_combos:
        # Empty: emit a placeholder
        html = _wrap_html(
            title=f"Ablation Heatmap — {task}",
            heading=f"Ablation Heatmap — {task}",
            eyebrow=f"MULTIMODAL LECTURE SUMMARIZER / {task} / ABLATION",
            winner_html="",
            content=f"<p>No ablation results found for task {task} in {results_csv}</p>",
            timestamp="",
        )
        output_path.write_text(html, encoding="utf-8")
        return output_path

    # Get all toggle combinations (union across bases)
    all_combos = set()
    for combos in base_to_combos.values():
        all_combos.update(combos.keys())
    sorted_combos = sorted(all_combos)

    bases = sorted(base_to_combos.keys())

    # Build matrix
    z_matrix = []
    for base in bases:
        row = [base_to_combos[base].get(combo, None) for combo in sorted_combos]
        z_matrix.append(row)

    # Truncate combo strings for display
    display_combos = [c[:50] + "..." if len(c) > 50 else c for c in sorted_combos]

    fig = go.Figure(data=go.Heatmap(
        z=z_matrix,
        x=display_combos,
        y=bases,
        colorscale=[[0, MUTED], [0.5, "#f5d76e"], [1, ACCENT_RED]],
        text=[[f"{v:.3f}" if v is not None else "—" for v in row] for row in z_matrix],
        texttemplate="%{text}",
        textfont=dict(size=9, color=INK),
        hovertemplate="Base: %{y}<br>Combo: %{x}<br>Metric: %{z:.4f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Ablation Heatmap — {task} ({metric_used})",
        plot_bgcolor=PAPER_BG,
        paper_bgcolor=PAPER_BG,
        font=dict(family="Georgia, serif", color=INK),
        height=max(400, len(bases) * 80 + 100),
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )
    plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    content = f"""
    <p>2^k ablation grid for task <strong>{task}</strong>. Color intensity shows
    primary metric value ({metric_used}).</p>
    <div class="plot-div">{plot_html}</div>
    <h2>How to Interpret</h2>
    <ul>
      <li><strong>Rows</strong>: Base candidates</li>
      <li><strong>Columns</strong>: Toggle value combinations (capped at 8 per base, sampled reproducibly)</li>
      <li><strong>Color</strong>: Primary metric value (brighter = higher; direction varies per metric)</li>
    </ul>
    """

    html = _wrap_html(
        title=f"Ablation Heatmap — {task}",
        heading=f"Ablation Heatmap — {task}",
        eyebrow=f"MULTIMODAL LECTURE SUMMARIZER / {task} / ABLATION",
        winner_html="",
        content=content,
        timestamp="",
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=str, default=None,
                        help="Task ID for per-task leaderboard")
    parser.add_argument("--leaderboards-dir", type=Path,
                        default=Path("experiments/scratch/leaderboards"),
                        help="Directory containing <task>.json leaderboards")
    parser.add_argument("--audit-csv", type=Path,
                        default=Path("experiments/scratch/ablation_audit.csv"),
                        help="Ablation audit CSV (for ablation heatmap)")
    parser.add_argument("--out-dir", type=Path,
                        default=Path("experiments/dashboards"),
                        help="Output directory for HTML files")
    parser.add_argument("--cross-task", action="store_true",
                        help="Generate cross-task comparison (all leaderboards)")
    parser.add_argument("--ablation", action="store_true",
                        help="Generate ablation heatmap")
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Per-task leaderboard
    if args.task:
        leaderboard_path = args.leaderboards_dir / f"{args.task}.json"
        if not leaderboard_path.exists():
            print(f"[FAIL] Leaderboard not found: {leaderboard_path}")
            return 1
        data = json.loads(leaderboard_path.read_text(encoding="utf-8"))
        # Reconstruct TaskLeaderboard from dict
        from experiments.scripts.leaderboard_builder import CandidateScore, TaskLeaderboard
        cands = [
            CandidateScore(
                candidate_id=c["candidate_id"],
                task=TaskID(args.task),
                raw_metrics=c["raw_metrics"],
                normalized_metrics=c["normalized_metrics"],
                composite_score=c["composite_score"],
                rank=c["rank"],
                is_pareto_optimal=c["is_pareto_optimal"],
                is_winner=c.get("is_winner", False),
                notes=c.get("notes", ""),
            )
            for c in data["candidates"]
        ]
        lb = TaskLeaderboard(
            task=TaskID(args.task),
            n_candidates=data["n_candidates"],
            metric_set=data["metric_set"],
            weights=data["weights"],
            candidates=cands,
            winner_id=data["winner"]["candidate_id"],
            winner_composite=data["winner"]["composite_score"],
            ci_95=tuple(data["winner"]["ci_95"]),
            exported_at=data.get("exported_at", ""),
        )
        out = args.out_dir / f"leaderboard_{args.task}.html"
        render_per_task_leaderboard(lb, out)
        print(f"[OK] Per-task dashboard: {out}")

    # Cross-task
    if args.cross_task:
        leaderboards: Dict[str, TaskLeaderboard] = {}
        for path in args.leaderboards_dir.glob("*.json"):
            if path.stem in {t.value for t in TaskID}:
                data = json.loads(path.read_text(encoding="utf-8"))
                cands = [
                    CandidateScore(
                        candidate_id=c["candidate_id"],
                        task=TaskID(path.stem),
                        raw_metrics=c["raw_metrics"],
                        normalized_metrics=c["normalized_metrics"],
                        composite_score=c["composite_score"],
                        rank=c["rank"],
                        is_pareto_optimal=c["is_pareto_optimal"],
                        is_winner=c.get("is_winner", False),
                    )
                    for c in data["candidates"]
                ]
                leaderboards[path.stem] = TaskLeaderboard(
                    task=TaskID(path.stem),
                    n_candidates=data["n_candidates"],
                    metric_set=data["metric_set"],
                    weights=data["weights"],
                    candidates=cands,
                    winner_id=data["winner"]["candidate_id"],
                    winner_composite=data["winner"]["composite_score"],
                    ci_95=tuple(data["winner"]["ci_95"]),
                )
        if not leaderboards:
            print("[FAIL] No leaderboards found")
            return 1
        out = args.out_dir / "cross_task.html"
        render_cross_task_comparison(leaderboards, out)
        print(f"[OK] Cross-task dashboard: {out}")

    # Ablation
    if args.ablation:
        if not args.task:
            print("[FAIL] --ablation requires --task")
            return 1
        out = args.out_dir / f"ablation_{args.task}.html"
        try:
            render_ablation_heatmap(args.task, args.audit_csv, out)
            print(f"[OK] Ablation heatmap: {out}")
        except FileNotFoundError as e:
            print(f"[FAIL] {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())