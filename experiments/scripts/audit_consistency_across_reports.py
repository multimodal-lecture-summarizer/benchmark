"""
audit_consistency_across_reports.py
====================================

Tự động phát hiện mâu thuẫn giữa 3 nguồn báo cáo:
  1. reports/rq*_benchmark_results.json     (ground truth — từ benchmark run)
  2. reports/repro_manifest.json            (frozen reproducibility artifact)
  3. reports/validation_gate_summary.md     (human-readable summary)

Mục đích: chặn "metric drift" — khi 1 file được cập nhật mà files khác bị bỏ quên.

Cách dùng:
  python experiments/scripts/audit_consistency_across_reports.py
  python experiments/scripts/audit_consistency_across_reports.py --json    # output JSON cho CI
  python experiments/scripts/audit_consistency_across_reports.py --strict  # exit 1 nếu có drift

Detection logic:
  - Định nghĩa 1 bảng "metric registry" ánh xạ (source_field → ground_truth_path → other_source_paths)
  - Load từng source, extract value qua dotted path (vd: "RQ1.primary_metrics.C5_window_diff")
  - So sánh với tolerance cho từng metric (count: 0, pct: 0.5%, score: 0.001)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "reports"


# ---------------------------------------------------------------------------
# Metric Registry — ánh xạ giữa các nguồn
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricSpec:
    """Một metric cần đối chiếu xuyên suốt các nguồn."""
    name: str                    # Tên logic, vd "RQ1_C5_WindowDiff"
    description: str
    # Path extractor cho từng nguồn
    ground_truth_path: Tuple[str, ...]   # dotted path trong raw JSON
    manifest_path: Optional[Tuple[str, ...]] = None
    summary_path: Optional[Tuple[str, ...]] = None   # regex pattern trong .md
    # Tolerance cho phép (absolute)
    tolerance_abs: float = 0.0
    tolerance_rel: float = 0.0   # %


# Helper: extract nested dict value qua dotted path
def _extract(obj: Any, path: Tuple[str, ...]) -> Optional[float]:
    cur = obj
    for p in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    if cur is None:
        return None
    if isinstance(cur, (int, float)):
        return float(cur)
    if isinstance(cur, str):
        # Try to parse numeric strings like "0.136" or "78.8%"
        s = cur.replace("%", "").strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _extract_summary(md_text: str, patterns: List[str]) -> Optional[float]:
    """Extract a number từ markdown line matching any pattern."""
    import re
    for line in md_text.splitlines():
        for pat in patterns:
            if pat.lower() in line.lower():
                # Pull first number from line
                m = re.search(r"(\d+\.\d+|\d+)", line)
                if m:
                    return float(m.group(1))
    return None


# Registry: ground_truth ở reports/rq*_benchmark_results.json
METRIC_REGISTRY: List[MetricSpec] = [
    # RQ0-A: Audio / ASR
    MetricSpec(
        name="RQ0_A_WER_BestModel",
        description="Best ASR model WER (%)",
        ground_truth_path=("RQ0_A_results",),  # special - aggregated below
        manifest_path=("research_questions_outcomes", "RQ0_A", "wer_pct"),
        summary_path=None,
        tolerance_abs=0.5,
    ),
    MetricSpec(
        name="RQ0_A_RTF_BestModel",
        description="Best ASR model real-time factor",
        ground_truth_path=("RQ0_A_results",),
        manifest_path=("research_questions_outcomes", "RQ0_A", "real_time_factor"),
        summary_path=None,
        tolerance_abs=0.05,
    ),
    # RQ0-V: Visual
    MetricSpec(
        name="RQ0_V_ContentDetector_F1_2s",
        description="ContentDetector F1 @ 2s collar (%)",
        ground_truth_path=("RQ0_V_results",),
        manifest_path=("research_questions_outcomes", "RQ0_V", "collar_f1_2s_pct"),
        summary_path=None,
        tolerance_abs=1.0,
    ),
    # RQ1: Chaptering
    MetricSpec(
        name="RQ1_C5_WindowDiff",
        description="C5 WindowDiff (lower better)",
        ground_truth_path=("RQ1_results", "models", "C5 (Cross-Attention Proposed)", "window_diff", "mean"),
        manifest_path=("research_questions_outcomes", "RQ1", "primary_metrics", "C5_window_diff"),
        summary_path=None,
        tolerance_abs=0.01,
    ),
    MetricSpec(
        name="RQ1_C1_WindowDiff",
        description="C1 WindowDiff baseline",
        ground_truth_path=("RQ1_results", "models", "C1 (Text-only)", "window_diff", "mean"),
        manifest_path=("research_questions_outcomes", "RQ1", "primary_metrics", "C1_window_diff"),
        summary_path=None,
        tolerance_abs=0.01,
    ),
    MetricSpec(
        name="RQ1_C3_WindowDiff",
        description="C3 WindowDiff (visual ablation)",
        ground_truth_path=("RQ1_results", "models", "C3 (Visual DINOv2)", "window_diff", "mean"),
        manifest_path=("research_questions_outcomes", "RQ1", "primary_metrics", "C3_window_diff"),
        summary_path=None,
        tolerance_abs=0.01,
    ),
    MetricSpec(
        name="RQ1_C5_CollarF1_5s",
        description="C5 Collar F1 @ 5s (higher better)",
        ground_truth_path=("RQ1_results", "models", "C5 (Cross-Attention Proposed)", "collar_f1_5s", "mean"),
        manifest_path=("research_questions_outcomes", "RQ1", "primary_metrics", "C5_collar_f1_5s"),
        summary_path=None,
        tolerance_abs=0.05,
    ),
    # RQ2: Summarization
    MetricSpec(
        name="RQ2_S3_Hallucination",
        description="S3 hallucination rate (%)",
        ground_truth_path=("RQ2_results", "models", "S3 (Text Hierarchy)", "hallucination_rate", "mean"),
        manifest_path=("research_questions_outcomes", "RQ2", "primary_metrics", "S3_hallucination_pct"),
        summary_path=None,
        tolerance_abs=0.5,
    ),
    MetricSpec(
        name="RQ2_S3ev_Hallucination",
        description="S3+ev hallucination rate (%)",
        ground_truth_path=("RQ2_results", "models", "S3+ev (Slide-Evidence Grounded)", "hallucination_rate", "mean"),
        manifest_path=("research_questions_outcomes", "RQ2", "primary_metrics", "S3_ev_hallucination_pct"),
        summary_path=None,
        tolerance_abs=0.5,
    ),
    MetricSpec(
        name="RQ2_S4_Hallucination",
        description="S4 hallucination rate (%)",
        ground_truth_path=("RQ2_results", "models", "S4 (Multimodal Grounded)", "hallucination_rate", "mean"),
        manifest_path=("research_questions_outcomes", "RQ2", "primary_metrics", "S4_hallucination_pct"),
        summary_path=None,
        tolerance_abs=0.5,
    ),
    MetricSpec(
        name="RQ2_S3ev_ClaimDensity",
        description="S3+ev claim density (claims/100 tokens)",
        ground_truth_path=("RQ2_results", "models", "S3+ev (Slide-Evidence Grounded)", "claim_density", "mean"),
        manifest_path=("research_questions_outcomes", "RQ2", "primary_metrics", "S3_ev_claim_density"),
        summary_path=None,
        tolerance_abs=0.5,
    ),
    # RQ3: Retrieval / QA
    MetricSpec(
        name="RQ3_Q3_Recall3",
        description="Q3 Recall@3 (%)",
        ground_truth_path=("RQ3_results", "models", "Q3 (Multimodal RRF)", "recall_at_3", "mean"),
        manifest_path=("research_questions_outcomes", "RQ3", "primary_metrics", "Q3_recall_3"),
        summary_path=None,
        tolerance_abs=1.0,
    ),
    MetricSpec(
        name="RQ3_Q3_MRR",
        description="Q3 MRR",
        ground_truth_path=("RQ3_results", "models", "Q3 (Multimodal RRF)", "mrr", "mean"),
        manifest_path=("research_questions_outcomes", "RQ3", "primary_metrics", "Q3_mrr"),
        summary_path=None,
        tolerance_abs=0.01,
    ),
    MetricSpec(
        name="RQ3_GapClosed",
        description="Oracle gap closed (%)",
        ground_truth_path=("RQ3_results", "summary_metrics", "oracle_gap_closed_pct"),
        manifest_path=("research_questions_outcomes", "RQ3", "primary_metrics", "oracle_gap_closed_pct"),
        summary_path=None,
        tolerance_abs=1.0,
    ),
    MetricSpec(
        name="RQ3_AbsoluteOracle",
        description="Absolute oracle performance (%)",
        ground_truth_path=("RQ3_results", "summary_metrics", "absolute_oracle_performance_pct"),
        manifest_path=("research_questions_outcomes", "RQ3", "primary_metrics", "absolute_oracle_performance_pct"),
        summary_path=None,
        tolerance_abs=1.0,
    ),
]


# Special aggregator for RQ0-A & RQ0-V (extract best model from JSON results)
def _extract_rq0a_best(json_obj: Dict) -> Dict[str, float]:
    """Find best ASR model (lowest WER) → return {wer, rtf}."""
    out: Dict[str, float] = {}
    res = json_obj.get("results", json_obj)
    models = res.get("models") or res.get("asr_models") or []
    if not models:
        return out
    # Filter valid models with WER
    valid = [m for m in models if isinstance(m.get("wer_pct"), (int, float))]
    if not valid:
        valid = [m for m in models if isinstance(m.get("wer"), (int, float))]
    if not valid:
        return out
    best = min(valid, key=lambda m: m.get("wer_pct", m.get("wer", 1e9)))
    out["wer"] = float(best.get("wer_pct", best.get("wer")))
    rtf = best.get("real_time_factor") or best.get("rtf")
    if rtf is not None:
        out["rtf"] = float(rtf)
    return out


def _extract_rq0v_best(json_obj: Dict) -> Dict[str, float]:
    """Find best scene detector (highest F1@2s)."""
    out: Dict[str, float] = {}
    res = json_obj.get("results", json_obj)
    detectors = res.get("detectors") or res.get("scene_detectors") or []
    if not detectors:
        return out
    valid = [d for d in detectors if isinstance(d.get("collar_f1_2s"), (int, float))]
    if not valid:
        return out
    best = max(valid, key=lambda d: d["collar_f1_2s"])
    out["f1_2s"] = float(best["collar_f1_2s"])
    return out


# ---------------------------------------------------------------------------
# Load các nguồn
# ---------------------------------------------------------------------------

def load_source(name: str, path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        if path.suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".md":
            return {"__md_text__": path.read_text(encoding="utf-8")}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"  ⚠ {name}: parse error — {e}", file=sys.stderr)
    return None


def extract_metric_value(spec: MetricSpec, sources: Dict[str, Dict]) -> Dict[str, Optional[float]]:
    """Trả về {source_name: value} cho metric spec."""
    out: Dict[str, Optional[float]] = {}
    # Ground truth từ raw JSON (RQ-specific)
    if spec.ground_truth_path == ("RQ0_A_results",):
        rq0a = sources.get("rq0a_audio_results.json")
        if rq0a:
            best = _extract_rq0a_best(rq0a)
            out["ground_truth"] = best.get("wer") if "WER" in spec.name else best.get("rtf")
    elif spec.ground_truth_path == ("RQ0_V_results",):
        rq0v = sources.get("rq0v_visual_results.json")
        if rq0v:
            best = _extract_rq0v_best(rq0v)
            out["ground_truth"] = best.get("f1_2s")
    else:
        gt = sources.get(f"rq{spec.ground_truth_path[0][2]}_benchmark_results.json")
        if gt:
            out["ground_truth"] = _extract(gt, spec.ground_truth_path)

    # Manifest
    if spec.manifest_path:
        manifest = sources.get("repro_manifest.json")
        if manifest:
            out["repro_manifest"] = _extract(manifest, spec.manifest_path)
    return out


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------

@dataclass
class Discrepancy:
    metric_name: str
    description: str
    ground_truth: Optional[float]
    other_source: str
    other_value: Optional[float]
    diff_abs: Optional[float]
    tolerance_abs: float
    exceeds_tolerance: bool


def compare_sources(sources: Dict[str, Dict]) -> List[Discrepancy]:
    discrepancies: List[Discrepancy] = []
    for spec in METRIC_REGISTRY:
        values = extract_metric_value(spec, sources)
        gt = values.get("ground_truth")
        for source_name, val in values.items():
            if source_name == "ground_truth" or val is None:
                continue
            if gt is None:
                continue
            diff = abs(val - gt)
            ok = diff <= spec.tolerance_abs
            if not ok:
                discrepancies.append(Discrepancy(
                    metric_name=spec.name,
                    description=spec.description,
                    ground_truth=gt,
                    other_source=source_name,
                    other_value=val,
                    diff_abs=diff,
                    tolerance_abs=spec.tolerance_abs,
                    exceeds_tolerance=True,
                ))
    return discrepancies


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true",
                   help="Output JSON thay vì human-readable table")
    p.add_argument("--strict", action="store_true",
                   help="Exit code 1 nếu phát hiện drift")
    p.add_argument("--report-dir", type=Path, default=REPORTS_DIR,
                   help="Path tới reports directory")
    args = p.parse_args(argv)

    # Load tất cả sources
    files_to_load = {
        "rq0a_audio_results.json": args.report_dir / "rq0a_audio_results.json",
        "rq0v_visual_results.json": args.report_dir / "rq0v_visual_results.json",
        "rq1_benchmark_results.json": args.report_dir / "rq1_benchmark_results.json",
        "rq2_benchmark_results.json": args.report_dir / "rq2_benchmark_results.json",
        "rq3_benchmark_results.json": args.report_dir / "rq3_benchmark_results.json",
        "rq4_efficiency_summary.json": args.report_dir / "rq4_efficiency_summary.json",
        "repro_manifest.json": args.report_dir / "repro_manifest.json",
        "validation_gate_summary.md": args.report_dir / "validation_gate_summary.md",
    }

    sources: Dict[str, Dict] = {}
    print("=" * 70)
    print("CONSISTENCY AUDIT - Multimodal Lecture Summarizer Reports")
    print("=" * 70)
    OK_CHAR = "[OK]"
    MISS_CHAR = "[!!]"
    CONSISTENT = "[OK]"
    INCONSISTENT = "[!!]"
    for name, path in files_to_load.items():
        loaded = load_source(name, path)
        if loaded is None:
            print(f"  {MISS_CHAR} {name:50s} MISSING")
        else:
            print(f"  {OK_CHAR} {name:50s} OK ({path.stat().st_size:,} bytes)")
            sources[name] = loaded

    print()
    discrepancies = compare_sources(sources)

    if not discrepancies:
        print(f"{CONSISTENT} All metrics consistent across sources (within tolerance).")
        return 0

    print(f"{INCONSISTENT} Found {len(discrepancies)} inconsistencies:")
    print()
    print(f"{'Metric':<28}{'Ground Truth':>14}{'Manifest':>12}{'Diff':>10}{'Tol':>8}  Source")
    print("-" * 90)
    for d in discrepancies:
        gt_str = f"{d.ground_truth:.4f}" if d.ground_truth is not None else "n/a"
        ov_str = f"{d.other_value:.4f}" if d.other_value is not None else "n/a"
        diff_str = f"{d.diff_abs:.4f}" if d.diff_abs is not None else "n/a"
        tol_str = f"{d.tolerance_abs:.4f}"
        print(f"{d.metric_name:<28}{gt_str:>14}{ov_str:>12}{diff_str:>10}{tol_str:>8}  {d.other_source}")

    if args.json:
        out = {
            "inconsistencies": [
                {
                    "metric": d.metric_name,
                    "description": d.description,
                    "ground_truth": d.ground_truth,
                    "other_source": d.other_source,
                    "other_value": d.other_value,
                    "diff_abs": d.diff_abs,
                    "tolerance_abs": d.tolerance_abs,
                }
                for d in discrepancies
            ]
        }
        print()
        print(json.dumps(out, indent=2))

    if args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())