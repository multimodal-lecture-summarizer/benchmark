"""RQ1 diagnostic pilot: run 04a/04b runners on real OCW timed-TOC lectures.

DIAGNOSTIC ONLY.  This is not an official D2 freeze and never writes to the
``official`` namespace.  Receipts are written with evidence status ``partial``.

Inputs come from the Phase-1 candidate ledger:
* units: OCW lectures whose remote media header was decoded and whose published
  clip offsets passed every ledger check (no exclusion reason);
* chapter GT: the published clip offsets exactly as recorded in the ledger;
* duration: ffprobe container duration of the archive.org lecture media;
* transcript: the OCW caption file (WebVTT) of the same lecture video.

The unit ``sha256`` is the SHA-256 of the caption file, because the video was
not downloaded (``source_kind: caption_vtt``).  All units are ``validation``:
the cohort comes from one course, so no course-disjoint final_test exists and
results are baseline-only diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Sequence

from benchmarks.scripts import run_chaptering_benchmark as run04a
from benchmarks.scripts import run_chaptering_modality_ablation as run04b
from experiments.scripts.benchmark_artifacts import (
    RunnerContext,
    write_json_artifact,
    write_run_manifest,
)
from experiments.scripts.rq1_candidate_ledger import Prober

DATASET_ID = "ocw_1801_timed_toc"
OCW_BASE = "https://ocw.mit.edu"
RUN_NAMESPACE = "diagnostic"
EVIDENCE_STATUS = "partial"
PROFILE = "full"

_CUE_TIME_RE = re.compile(r"^\d\d:\d\d(:\d\d)?\.\d{3}\s+-->")


def vtt_to_text(vtt: str) -> str:
    """Concatenate WebVTT cue text (drops header, cue ids, timings and tags)."""
    lines: list[str] = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or _CUE_TIME_RE.match(line) or line.isdigit():
            continue
        if line.startswith(("NOTE", "Kind:", "Language:")):
            continue
        lines.append(re.sub(r"<[^>]+>", "", line))
    return " ".join(lines)


def _code_sha256() -> str:
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for rel in (
        "experiments/scripts/rq1_diagnostic_pilot.py",
        "experiments/scripts/chapter_benchmark_contract.py",
        "benchmarks/scripts/run_chaptering_benchmark.py",
        "benchmarks/scripts/run_chaptering_modality_ablation.py",
        "experiments/scripts/stage_benchmark_helpers.py",
        "experiments/evaluation/dataset_contracts.py",
    ):
        digest.update(rel.encode())
        digest.update((root / rel).read_bytes())
    return digest.hexdigest()


def build_units(ledger: dict[str, Any], prober: Prober) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    attrition: list[dict[str, Any]] = []
    for record in ledger["records"]:
        if record["source_id"] != "mit_ocw_timed_toc":
            continue
        evidence = record["evidence"]
        if not evidence.get("media_probe_sample"):
            attrition.append({"lecture_id": record["lecture_id"], "reason": "not_in_media_probe_sample"})
            continue
        if record["exclusion_reason"]:
            attrition.append({"lecture_id": record["lecture_id"], "reason": record["exclusion_reason"]})
            continue
        duration = evidence["media_probe"].get("duration_sec")
        vtts = evidence.get("caption_vtt") or []
        if not vtts:
            attrition.append({"lecture_id": record["lecture_id"], "reason": "caption_missing"})
            continue
        # Every clip page links a caption file; accept only when all of them are
        # byte-identical (i.e. one full-lecture caption track).
        responses = [prober.get(OCW_BASE + v) for v in vtts]
        if any(r.status != 200 or not r.body for r in responses):
            attrition.append({"lecture_id": record["lecture_id"], "reason": "caption_unavailable"})
            continue
        if len({r.sha256 for r in responses}) != 1:
            attrition.append({"lecture_id": record["lecture_id"], "reason": "caption_not_unique"})
            continue
        response = responses[0]
        transcript = vtt_to_text(response.text())
        if not transcript.strip():
            attrition.append({"lecture_id": record["lecture_id"], "reason": "caption_empty"})
            continue
        units.append({
            "unit_id": record["lecture_id"],
            "dataset_id": DATASET_ID,
            "split": "validation",
            "course_id": record["course_id"],
            "lecture_id": record["lecture_id"],
            "duration_sec": float(duration),
            "sha256": response.sha256,
            "source_kind": "caption_vtt",
            "source_url": OCW_BASE + vtts[0],
            "media_url": record["video_url"],
            "rights": record["rights_status"],
            "transcript": transcript,
            "chapter_boundaries_sec": list(evidence["chapter_boundaries_sec"]),
            "chapter_gt": {
                "source": "MIT OCW 18.01SC clip pages (published youtube start offsets)",
                "revision": ledger["ocw_course_summaries"][0]["sitemap_sha256"][:16],
                "annotation_origin": "publisher_timed_toc",
                "timestamp_convention": "seconds from start of the full lecture video",
                "gt_url": record["gt_url"][0],
            },
        })
    units.sort(key=lambda u: u["unit_id"])
    return units, attrition


def _context(root: Path, notebook_id: str, code_sha: str, mode: str | None) -> RunnerContext:
    return RunnerContext(
        profile=PROFILE, run_namespace=RUN_NAMESPACE, status=EVIDENCE_STATUS,
        artifact_root=root, notebook_id=notebook_id, run_id=str(uuid.uuid4()),
        source_sha256=code_sha, config_sha256=hashlib.sha256(b"rq1-diagnostic-pilot/1").hexdigest(),
        dependency_state_sha256=hashlib.sha256(code_sha.encode()).hexdigest(),
        evaluation_mode=mode,
    )


def seed_namespace(root: Path, units: list[dict[str, Any]], code_sha: str) -> None:
    """Write diagnostic 00c-equivalent artifacts.  Never official."""
    ctx = _context(root, "00c_dataset_eda_and_freeze", code_sha, None)
    reason = ("DIAGNOSTIC PILOT ONLY - not an official D2 freeze; single source course; "
              "caption-only source hash; baseline diagnostics only")
    write_json_artifact(ctx, "dataset.frozen_manifest", [{
        "dataset_id": DATASET_ID, "freeze_status": "eligible",
        "scientific_selection_eligible": True,
        "unit_ids": [u["unit_id"] for u in units], "unit_records": units,
        "reason": reason, "profile": PROFILE,
    }])
    write_json_artifact(ctx, "dataset.registry", [{
        "dataset_id": DATASET_ID, "revision": units[0]["chapter_gt"]["revision"],
        "acquisition_level": "diagnostic_pilot", "rights": units[0]["rights"],
        "access_status": "media_url_published", "ground_truth_status": "publisher_timed_toc",
    }])
    write_json_artifact(ctx, "dataset.endpoint_matrix", [{
        "dataset_id": DATASET_ID, "endpoint": "chapter", "eligibility": "diagnostic_pilot",
        "scientific_selection_eligible": True, "reason": reason,
    }])
    write_run_manifest(ctx)


def _runner_argv(root: Path, notebook_id: str, code_sha: str) -> list[str]:
    return [
        "--profile", PROFILE, "--run-namespace", RUN_NAMESPACE,
        "--evidence-status", EVIDENCE_STATUS, "--artifact-root", str(root),
        "--notebook-id", notebook_id, "--run-id", str(uuid.uuid4()),
        "--source-sha256", code_sha,
        "--config-sha256", hashlib.sha256(b"rq1-diagnostic-pilot/1").hexdigest(),
        "--dependency-state-sha256", hashlib.sha256(code_sha.encode()).hexdigest(),
        "--evaluation-mode", "selection",
    ]


def run_pilot(ledger_path: Path, artifact_root: Path, cache_dir: Path) -> dict[str, Any]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    prober = Prober(output_dir=cache_dir)
    units, attrition = build_units(ledger, prober)
    if not units:
        raise RuntimeError("no pilot units passed the ledger gates")
    code_sha = _code_sha256()
    seed_namespace(artifact_root, units, code_sha)
    exit_04a = run04a.main(_runner_argv(artifact_root, run04a.NOTEBOOK_ID, code_sha))
    exit_04b = run04b.main(_runner_argv(artifact_root, run04b.NOTEBOOK_ID, code_sha)) \
        if exit_04a == 0 else None
    summary = {
        "diagnostic_only": True,
        "artifact_root": str(artifact_root),
        "namespace": f"{RUN_NAMESPACE}/{PROFILE}",
        "evidence_status": EVIDENCE_STATUS,
        "code_sha256": code_sha,
        "unit_ids": [u["unit_id"] for u in units],
        "splits": sorted({u["split"] for u in units}),
        "attrition": attrition,
        "exit_codes": {"04a": exit_04a, "04b": exit_04b},
    }
    (artifact_root / "pilot_summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                                      encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path("experiments/outputs/diagnostic")
    parser.add_argument("--ledger", type=Path, default=base / "rq1_qualification/candidate_ledger.json")
    parser.add_argument("--artifact-root", type=Path, default=base / "rq1_pilot")
    parser.add_argument("--cache-dir", type=Path, default=base / "rq1_qualification")
    args = parser.parse_args(argv)
    summary = run_pilot(args.ledger, args.artifact_root, args.cache_dir)
    print(json.dumps(summary, indent=2))
    return 0 if summary["exit_codes"] == {"04a": 0, "04b": 0} else 1


if __name__ == "__main__":
    raise SystemExit(main())
