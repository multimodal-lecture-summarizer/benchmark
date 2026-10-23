"""Package Pilot40 outputs (4 profiles, no Qwen3) and frozen scorer code for private Colab scoring.

Mirrors tib_scorer_colab_bundle (the 21-output scorer bundle) without modifying it.
Failed cells stay in the denominator as unscoreable rows; nothing is retried or dropped.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from experiments.scripts.tib_budget_views import build_views
from experiments.scripts.tib_scorer_colab_bundle import (
    PINS, SCRIPTS as P4B_SCRIPTS, SUPPORT, file_hash, text_hash, write_json,
)

ROOT = Path(__file__).resolve().parents[2]
QUALIFICATION = ROOT / "research-data/tib-qualification-261019-1703"
COHORT = ROOT / "experiments/registry/datasets/tib-text-model-benchmark-v1/qualification-261019-1703/development_cohort.json"
SPEC = ROOT / "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/scorer_spec_v2.json"
P4B_AMENDMENT = ROOT / "experiments/registry/protocols/tib-scorer-colab-runtime-261020-v1/runtime_amendment.json"
EVIDENCE_ZIP = ROOT / "research-data/tib-pilot40-261020-v1/results/tib-pilot40-evidence-20261023T074252Z.zip"
EVIDENCE_SHA256 = "39cc411bd3304041a478c1fb55b55b2417764538a62df69aa15472ab0980dbce"
REGISTRY = ROOT / "experiments/registry/protocols/tib-pilot40-scoring-261023-v1"
LOCAL = ROOT / "research-data/tib-pilot40-scoring-261023-v1"
AMENDMENT_ID = "tib-pilot40-scoring-261023-v1"

PROFILES = ("lead3", "lexrank", "bart", "led")
EXCLUDED = {"qwen3": "protocol decision 2026-10-23 18:42: dropped from selection300/final523; primary metric not scored"}
VIEW_BUDGETS = {"S": 60, "M": 120, "L": 240}
STATUSES = {"completed", "completed_with_warning", "failed"}
SCRIPTS = P4B_SCRIPTS + ["tib_pilot40_scorer_runner"]
EXPECTED_ROWS, EXPECTED_SCOREABLE = 160, 154


def _jsonl(lines):
    return [json.loads(line) for line in lines if line.strip()]


def pilot40_rows(evidence_zip=EVIDENCE_ZIP, qualification=QUALIFICATION, cohort_path=COHORT):
    """Return sorted rows for every (pilot ID, profile) cell; any identity drift raises."""
    qualification = Path(qualification)
    cohort = json.loads(Path(cohort_path).read_text(encoding="utf-8"))
    pilot_ids = set(cohort["selected_ids"]["pilot"])
    if pilot_ids & set(cohort["selected_ids"]["selection"]):
        raise ValueError("Pilot and selection cohorts overlap")

    def by_record(path):
        with Path(path).open(encoding="utf-8") as handle:
            return {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in pilot_ids}

    rights = by_record(qualification / "source_use_ledger.jsonl")
    eligible = by_record(qualification / "qualified_cohort/qualification_ledger.jsonl")
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "rt", encoding="utf-8") as handle:
        canonical = {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in pilot_ids}
    if any(set(group) != pilot_ids for group in (rights, eligible, canonical)):
        raise ValueError("Incomplete pilot identity/rights evidence")

    rows = []
    with zipfile.ZipFile(evidence_zip) as archive:
        sources = {item["record_id"]: item for item in
                   _jsonl(archive.read("package/pilot_sources.jsonl").decode("utf-8").splitlines())}
        if set(sources) != pilot_ids:
            raise ValueError("Evidence pilot sources differ from the sealed Pilot40 cohort")
        for profile in PROFILES:
            blob = archive.read(f"pilot/{profile}/candidate_receipt.json")
            receipt_sha = hashlib.sha256(blob).hexdigest()
            records = json.loads(blob)["records"]
            if set(records) != pilot_ids:
                raise ValueError(f"{profile}: receipt does not cover exactly the pilot IDs")
            for record_id in sorted(pilot_ids):
                record = records[record_id]
                canon, right, qual = canonical[record_id], rights[record_id], eligible[record_id]
                source, reference = canon["source_normalized"], canon["reference_normalized"]
                if not (qual["role_eligible"] and right["allowed_for_current_local_use"]
                        and right["allowed_for_reference_scoring"]):
                    raise ValueError("Rights/eligibility contract changed: " + record_id)
                if not (text_hash(source) == sources[record_id]["source_normalized_sha256"]
                        == qual["source_normalized_sha256"] == record["source_sha256"]
                        and text_hash(reference) == qual["reference_normalized_sha256"]):
                    raise ValueError("Source/reference identity mismatch: " + record_id)
                status = record["status"]
                if status not in STATUSES or not record.get("retain_in_denominator"):
                    raise ValueError(f"{profile}/{record_id}: unexpected status {status}")
                row = {"sample_id": f"{profile}__{record_id.replace(':', '-')}", "record_id": record_id,
                       "candidate_id": profile, "profile_id": profile,
                       "source_stratum": record["source_stratum"], "origin": record["origin"],
                       "source": source, "reference": reference,
                       "source_sha256": text_hash(source), "reference_sha256": text_hash(reference),
                       "source_receipt_sha256": receipt_sha, "generation_status": status,
                       "reference_label": qual["reference_label"], "rights": right,
                       "attribution": sources[record_id]["attribution"]}
                if status == "failed":
                    row.update(scoreable=False, failure_reason=record["error"], warnings=[],
                               delivered_summary=None, delivered_sha256=None, views=None)
                else:
                    result = record["result"]
                    delivered = result["delivered_final"]
                    if (text_hash(delivered) != result["delivery"]["delivered_sha256"]
                            or len(delivered.split()) > 350):
                        raise ValueError(f"{profile}/{record_id}: delivered summary hash/cap mismatch")
                    views = build_views(result["raw_final"], VIEW_BUDGETS)
                    row.update(scoreable=True, failure_reason=None,
                               warnings=record["validation"]["acceptance"]["warnings"],
                               delivered_summary=delivered, delivered_sha256=text_hash(delivered),
                               views={name: views[name]["text"] for name in VIEW_BUDGETS})
                rows.append(row)
    return sorted(rows, key=lambda r: (r["profile_id"], r["record_id"]))


def build():
    if file_hash(EVIDENCE_ZIP) != EVIDENCE_SHA256:
        raise ValueError("Pilot40 evidence ZIP hash changed")
    rows = pilot40_rows()
    scoreable = sum(r["scoreable"] for r in rows)
    if len(rows) != EXPECTED_ROWS or scoreable != EXPECTED_SCOREABLE:
        raise ValueError(f"Expected {EXPECTED_ROWS}/{EXPECTED_SCOREABLE} rows, got {len(rows)}/{scoreable}")
    bundle = LOCAL / "bundle"
    if bundle.exists():
        shutil.rmtree(bundle)
    scripts = bundle / "experiments/scripts"
    scripts.mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copyfile(ROOT / "experiments/scripts" / (name + ".py"), scripts / (name + ".py"))
    for relative in ("experiments/__init__.py", "experiments/scripts/__init__.py"):
        (bundle / relative).write_text("", encoding="utf-8")
    shutil.copyfile(SPEC, bundle / "frozen_scorer_spec.json")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    for relative, expected in spec["code_sha256"].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError("Frozen scorer implementation changed: " + relative)
        (bundle / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, bundle / relative)
    p4b = json.loads(P4B_AMENDMENT.read_text(encoding="utf-8"))
    if p4b["runtime_pins"] != PINS or p4b["support_package_pins"] != SUPPORT:
        raise ValueError("Runtime pins differ from the audited P4b amendment")
    amendment = {
        "schema_version": 1, "amendment_id": AMENDMENT_ID,
        "state": "PREPARED_HOLD_ACTUAL_COLAB_EXECUTION_REQUIRED",
        "runtime_pins": PINS, "support_package_pins": SUPPORT,
        "frozen_spec_sha256": file_hash(bundle / "frozen_scorer_spec.json"),
        "p4b_runtime_amendment_sha256": file_hash(P4B_AMENDMENT),
        "evidence_zip_sha256": EVIDENCE_SHA256,
        "expected_output_count": EXPECTED_ROWS, "expected_scoreable_count": EXPECTED_SCOREABLE,
        "profile_ids": list(PROFILES), "excluded_profiles": EXCLUDED,
        "views": {"budgets_words": VIEW_BUDGETS, "metrics": ["rouge1_f1", "rouge2_f1", "rougeL_f1", "bertscore_f1"],
                  "source_similarity": "not computed on views"},
        "preserved": "scorer v2 metrics, windows, IDF=false, FP32 and the 350-word cap are unchanged",
        "scope": "Pilot40 reference scoring for scoring-cost measurement; descriptive, no ranking or admission",
        "selection_start_authorized": False, "generation_allowed": False,
    }
    write_json(bundle / "runtime_amendment.json", amendment)
    (bundle / "pilot_outputs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (bundle / "requirements-colab-t4.txt").write_text(
        "--extra-index-url https://download.pytorch.org/whl/cu130\n"
        + "".join(f"{k}=={v}\n" for k, v in {**PINS, **SUPPORT}.items()), encoding="utf-8")
    manifest = {"schema_version": 1, "files": {
        p.relative_to(bundle).as_posix(): file_hash(p) for p in sorted(bundle.rglob("*"))
        if p.is_file() and p.name != "package_manifest.json" and "__pycache__" not in p.parts}}
    write_json(bundle / "package_manifest.json", manifest)
    REGISTRY.mkdir(parents=True, exist_ok=True)
    for name in ("runtime_amendment.json", "requirements-colab-t4.txt", "package_manifest.json"):
        shutil.copyfile(bundle / name, REGISTRY / name)
    archive = LOCAL / "tib-pilot40-scoring-261023-v1.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative in manifest["files"]:
            output.write(bundle / relative, relative)
        output.write(bundle / "package_manifest.json", "package_manifest.json")
    receipt = {"schema_version": 1, "status": "HOLD", "scorer_ready": False,
               "actual_colab_execution": False,
               "reason": "Prepared only; actual Colab execution evidence required",
               "archive_bytes": archive.stat().st_size, "archive_sha256": file_hash(archive),
               "manifest_sha256": file_hash(bundle / "package_manifest.json"),
               "rows": len(rows), "scoreable_rows": scoreable, "failed_rows": len(rows) - scoreable,
               "rows_by_profile": {p: sum(r["profile_id"] == p for r in rows) for p in PROFILES},
               "quality_ranking_performed": False, "generation_executed": False,
               "selection_start_authorized": False}
    write_json(REGISTRY / "preparation_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build(), indent=2))
