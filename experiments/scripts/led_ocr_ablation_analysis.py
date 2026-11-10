"""Phase 4 of the LED OCR ablation: one analysis pass, one label for D minus A.

Reads the text-free receipts only. Thresholds, seed and label order come from the hashed decision_rules.json; the
script refuses to run if that file no longer matches the frozen hash. A pair is comparable when both arms are valid
cells with a ROUGE-L @350 and a MiniCheck (transcript + OCR evidence) score. Every video stays in the denominator of 40.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

import numpy as np

PROTOCOL_ID = "led-ocr-ablation-261110-v1"
PRIMARY, GUARD = "rougeL_f1_at_350", "minicheck_evidence_full"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_frozen(protocol_dir: Path) -> dict:
    """Return the decision rules after verifying every frozen file against hashes.json."""
    manifest = json.loads((protocol_dir / "hashes.json").read_text(encoding="utf-8"))["sha256"]
    for name, expected in manifest.items():
        if sha256_bytes((protocol_dir / name).read_bytes()) != expected:
            raise ValueError(f"{name} no longer matches its frozen hash")
    return json.loads((protocol_dir / "decision_rules.json").read_text(encoding="utf-8"))


def metric_value(row: dict, metric: str) -> float | None:
    value = row.get(metric)
    if isinstance(value, dict):
        value = value.get("mean_prob")
    return value if isinstance(value, (int, float)) and math.isfinite(value) else None


def build_pairs(cohort_ids: dict[str, str], scores: list[dict], cells: list[dict]) -> list[dict]:
    """One entry per cohort video, in id order, with comparable=False plus a reason when a pair cannot be used."""
    by_cell = {(r["id"], r["arm"]): r for r in scores}
    cell_status = {(r["id"], r["arm"]): r for r in cells}
    pairs = []
    for vid in sorted(cohort_ids):
        pair = {"id": vid, "stratum": cohort_ids[vid], "comparable": False}
        a, d = by_cell.get((vid, "A")), by_cell.get((vid, "D"))
        if not a or not d:
            missing = [arm for arm in ("A", "D") if (vid, arm) not in by_cell]
            states = {arm: (cell_status.get((vid, arm)) or {}).get("status", "absent") for arm in missing}
            pair["reason"] = f"not scored: {states}"
        else:
            values = {m: (metric_value(a, m), metric_value(d, m)) for m in (PRIMARY, GUARD)}
            if any(x is None or y is None for x, y in values.values()):
                pair["reason"] = "metric missing: " + ",".join(m for m, (x, y) in values.items() if x is None or y is None)
            else:
                pair.update(comparable=True, delta={m: values[m][1] - values[m][0] for m in values})
        pairs.append(pair)
    return pairs


def stratified_bootstrap(by_stratum: dict[str, list[float]], resamples: int, seed: int, level: float) -> dict:
    """Percentile bootstrap of the overall mean difference; videos resampled within each stratum, quotas fixed."""
    members = {s: np.asarray(v, dtype=float) for s, v in by_stratum.items() if v}
    total = sum(len(v) for v in members.values())
    if not total:
        return {"n": 0, "mean": None, "low": None, "high": None}
    rng = np.random.default_rng(seed)
    sums = np.zeros(resamples)
    for stratum in sorted(members):
        values = members[stratum]
        sums += values[rng.integers(0, len(values), size=(resamples, len(values)))].sum(axis=1)
    means = np.sort(sums / total)
    tail = (1.0 - level) / 2.0
    low = means[max(0, math.ceil(tail * resamples) - 1)]
    high = means[min(resamples - 1, math.ceil((1.0 - tail) * resamples) - 1)]
    mean = math.fsum(x for v in members.values() for x in v) / total
    return {"n": total, "mean": mean, "low": float(low), "high": float(high)}


def decide(primary: dict, guard: dict, comparable: int, rules: dict) -> dict:
    """Apply the frozen rule in its frozen order."""
    pm, gm = rules["primary"]["margin"], rules["guard"]["margin"]
    if comparable < rules["min_comparable_pairs"]:
        return {"label": "no_selection", "reason": f"{comparable} comparable pairs < {rules['min_comparable_pairs']}"}
    if (primary["high"] < 0 and primary["mean"] <= -pm) or (guard["high"] < 0 and guard["mean"] <= -gm):
        return {"label": "ocr_hurts_summary", "reason": "primary or guard interval below zero beyond its margin"}
    if primary["low"] > 0 and primary["mean"] >= pm and guard["mean"] >= -gm:
        return {"label": "ocr_helps_summary", "reason": "primary interval above zero, beyond margin, guard within margin"}
    return {"label": "no_difference", "reason": "neither the helps nor the hurts condition holds"}


def contrast(pairs: list[dict], metric: str, rules: dict) -> dict:
    by_stratum: dict[str, list[float]] = {}
    for pair in pairs:
        if pair["comparable"]:
            by_stratum.setdefault(pair["stratum"], []).append(pair["delta"][metric])
    iv = rules["interval"]
    return stratified_bootstrap(by_stratum, iv["resamples"], iv["seed"], iv["level"])


def mean_or_none(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def describe(scores: list[dict], cells: list[dict], extract: list[dict]) -> dict:
    """Descriptive only: never feeds the label."""
    out = {"by_arm": {}, "ocr_not_in_input_videos": None, "segmenter_content_videos": None, "by_stratum_delta": {}}
    for arm in ("A", "D"):
        mine = [r for r in scores if r["arm"] == arm]
        out["by_arm"][arm] = {
            "scored": len(mine),
            "bertscore_f1": mean_or_none([metric_value(r, "bertscore_f1") for r in mine]),
            "rougeL_f1_at_120": mean_or_none([metric_value(r, "rougeL_f1_at_120") for r in mine]),
            "word_count": mean_or_none([r["word_count"] for r in mine]),
            "minicheck_transcript_only": mean_or_none([metric_value(r, "minicheck_evidence_transcript") for r in mine]),
            "slide_term_coverage": mean_or_none([r.get("slide_term_coverage") for r in mine]),
            "generation_seconds": mean_or_none([c.get("generation_seconds") for c in cells if c["arm"] == arm and c.get("status") == "ok"]),
        }
    d_cells = [c for c in cells if c["arm"] == "D" and c.get("status") == "ok"]
    out["ocr_not_in_input_videos"] = sorted(c["id"] for c in d_cells if "OCR" not in str(c.get("model_used")))
    out["segmenter_content_videos"] = sorted(r["id"] for r in extract if r.get("segmenter") == "content")
    return out


def analyze(protocol_dir: Path, scores: list[dict], cells: list[dict], extract: list[dict]) -> dict:
    rules = check_frozen(protocol_dir)
    cohort = json.loads((protocol_dir / "cohort.json").read_text(encoding="utf-8"))
    ids = {v["id"]: v["stratum"] for v in cohort["videos"]}
    pairs = build_pairs(ids, scores, cells)
    comparable = sum(p["comparable"] for p in pairs)
    primary, guard = contrast(pairs, PRIMARY, rules), contrast(pairs, GUARD, rules)
    verdict = decide(primary, guard, comparable, rules) if comparable else {"label": "no_selection", "reason": "no comparable pair"}
    return {"protocol_id": PROTOCOL_ID, "label_kind": "confirmatory_single_pass", "cohort_size": len(ids),
            "comparable_pairs": comparable, "not_comparable": [{k: p[k] for k in ("id", "stratum", "reason")} for p in pairs if not p["comparable"]],
            "primary": {"metric": PRIMARY, **primary}, "guard": {"metric": GUARD, **guard},
            "decision": verdict, "descriptive_only": describe(scores, cells, extract),
            "decision_rules_sha256": json.loads((protocol_dir / "hashes.json").read_text(encoding="utf-8"))["sha256"]["decision_rules.json"]}


def read_rows(path: Path) -> list[dict]:
    from experiments.scripts.led_ocr_ablation_extract import read_rows as read

    return read(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--protocol-dir", required=True)
    parser.add_argument("--out-dir", required=True, help="private run folder holding the receipts")
    parser.add_argument("--result-dir", required=True, help="registry results folder for analysis.json")
    args = parser.parse_args(argv)
    out_dir, result_dir = Path(args.out_dir), Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    target = result_dir / "analysis.json"
    if target.exists():
        raise FileExistsError("analysis already run once; further analyses must be post-hoc files with their own names")
    result = analyze(Path(args.protocol_dir), read_rows(out_dir / "scores_receipt_cohort.jsonl"),
                     read_rows(out_dir / "cells_receipt_cohort.jsonl"), read_rows(out_dir / "extract_ledger_cohort.jsonl"))
    data = (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    target.write_bytes(data)
    (result_dir / "analysis.sha256").write_text(sha256_bytes(data) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "comparable_pairs": result["comparable_pairs"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
