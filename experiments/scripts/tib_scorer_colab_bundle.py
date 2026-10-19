"""Package only stored development summaries and frozen scorer code for private Colab use."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "experiments/registry/protocols/tib-model-benchmark-p4-261019-1802"
REGISTRY = ROOT / "experiments/registry/protocols/tib-scorer-colab-runtime-261020-v1"
LOCAL = ROOT / "research-data/tib-scorer-colab-runtime-261020-v1"
IDS = {"valid:341", "valid:644", "valid:886"}
PINS = {"rouge-score": "0.1.2", "bert-score": "0.3.13", "sentence-transformers": "5.7.0",
        "transformers": "4.57.6", "torch": "2.11.0+cu130", "numpy": "2.1.3", "nltk": "3.9.4"}
SUPPORT = {"huggingface-hub": "0.36.2", "tokenizers": "0.22.2", "safetensors": "0.8.0",
           "psutil": "5.9.5", "requests": "2.32.4", "sentencepiece": "0.2.1"}
SCRIPTS = ["tib_benchmark_scorer", "tib_benchmark_scorer_probe", "tib_benchmark_scorer_assets",
           "rq2_tib_benchmark_metrics", "rq2_tib_semantic_v2", "tib_scorer_colab_backend",
           "tib_scorer_colab_checkpoint", "tib_scorer_colab_resources", "tib_scorer_colab_runner"]


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def development_rows():
    """Verify the existing acceptance view and export the same 21 delivered outputs."""
    qualification = ROOT / "research-data/tib-qualification-261019-1703"
    returned = ROOT / "research-data/tib-p41-261019-2122/returned-evidence-20261019T151425Z"
    view_path = PROTOCOL / "development-decision-261019-2341/derived_p41_acceptance_view_v1.json"
    view = json.loads(view_path.read_text(encoding="utf-8"))
    def selected(path):
        with path.open(encoding="utf-8") as handle:
            return {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in IDS}
    rights = selected(qualification / "source_use_ledger.jsonl")
    eligible = selected(qualification / "qualified_cohort/qualification_ledger.jsonl")
    with gzip.open(qualification / "eda/canonical_records.jsonl.gz", "rt", encoding="utf-8") as handle:
        canonical = {r["record_id"]: r for r in map(json.loads, handle) if r["record_id"] in IDS}
    staged = selected(returned / "run_bundle/staged_sources.jsonl")
    if any(set(group) != IDS for group in (rights, eligible, canonical, staged)):
        raise ValueError("Incomplete three-record identity/rights evidence")
    rows = []
    for item in view["records"]:
        record_id = item["record_id"]
        if record_id not in IDS:
            raise ValueError("Unexpected development ID")
        record, license_row = canonical[record_id], rights[record_id]
        if not (eligible[record_id]["role_eligible"] and license_row["allowed_for_current_local_use"]
                and license_row["allowed_for_reference_scoring"]):
            raise ValueError("Development rights/eligibility contract changed")
        source, reference = record["source_normalized"], record["reference_normalized"]
        if (text_hash(source) != staged[record_id]["source_normalized_sha256"]
                or text_hash(source) != eligible[record_id]["source_normalized_sha256"]
                or text_hash(reference) != eligible[record_id]["reference_normalized_sha256"]):
            raise ValueError("Canonical/staged/qualified identity mismatch")
        path = returned / item["raw_artifact"]
        if file_hash(path) != item["raw_artifact_sha256"]:
            raise ValueError("Historical output artifact changed")
        envelope = json.loads(path.read_text(encoding="utf-8"))
        payload = envelope["payload"]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != envelope["sha256"]:
            raise ValueError("Historical output envelope changed")
        delivered = payload["delivered_final"]
        if text_hash(delivered) != payload["delivery"]["delivered_sha256"]:
            raise ValueError("Delivered summary hash mismatch")
        decision = item["derived_acceptance"]
        if decision["status"] not in {"completed", "completed_with_warning"}:
            raise ValueError("No outcome-dependent exclusion permitted")
        profile = item["trial_id"]
        candidate = "qwen3" if profile.startswith("qwen") else profile.split("-")[0]
        rows.append({"sample_id": profile + "__" + record_id.replace(":", "-"),
                     "record_id": record_id, "candidate_id": candidate, "profile_id": profile,
                     "source": source, "reference": reference, "delivered_summary": delivered,
                     "source_sha256": text_hash(source), "reference_sha256": text_hash(reference),
                     "delivered_sha256": text_hash(delivered), "source_receipt_sha256": file_hash(path),
                     "generation_status": decision["status"], "warnings": decision["warnings"],
                     "reference_label": eligible[record_id]["reference_label"],
                     "attribution": staged[record_id]["attribution"],
                     "rights": license_row})
    if len(rows) != 21 or len({r["sample_id"] for r in rows}) != 21:
        raise ValueError("Stored development matrix must retain all 21 rows")
    return sorted(rows, key=lambda row: row["sample_id"]), view_path


def build():
    bundle = LOCAL / "bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    rows, view_path = development_rows()
    scripts = bundle / "experiments/scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        shutil.copyfile(ROOT / "experiments/scripts" / (name + ".py"), scripts / (name + ".py"))
    for relative in ("experiments/__init__.py", "experiments/scripts/__init__.py"):
        (bundle / relative).write_text("", encoding="utf-8")
    shutil.copyfile(PROTOCOL / "scorer_spec_v2.json", bundle / "frozen_scorer_spec.json")
    shutil.copyfile(PROTOCOL / "scorer_ready_receipt.json", bundle / "cpu_ready_receipt.json")
    shutil.copyfile(view_path, bundle / "derived_acceptance_view.json")
    spec = json.loads((bundle / "frozen_scorer_spec.json").read_text(encoding="utf-8"))
    for relative, expected in spec["code_sha256"].items():
        if file_hash(ROOT / relative) != expected:
            raise ValueError("Frozen scorer implementation changed: " + relative)
        destination = bundle / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    amendment = {"schema_version": 1, "amendment_id": "tib-scorer-colab-runtime-261020-v1",
        "state": "PREPARED_HOLD_ACTUAL_COLAB_EXECUTION_REQUIRED", "runtime_pins": PINS,
        "support_package_pins": SUPPORT, "frozen_spec_sha256": file_hash(bundle / "frozen_scorer_spec.json"),
        "cpu_ready_receipt_sha256": file_hash(bundle / "cpu_ready_receipt.json"),
        "acceptance_view_sha256": file_hash(view_path), "required_record_ids": sorted(IDS),
        "expected_output_count": 21, "expected_profile_ids": sorted({r["profile_id"] for r in rows}),
        "changes_from_cpu": {"torch": ["2.6.0+cu124", PINS["torch"]], "numpy": ["2.4.6", PINS["numpy"]],
                             "device": ["cpu", "cuda:0/Tesla T4"]},
        "preserved": {"metric_ids": list(spec["rouge"]["metrics"]) + ["bertscore_f1", "source_sentence_similarity_v1"],
                      "idf": False, "idf_fit_ids": [], "batch_size": 1, "dtype": "float32",
                      "bert_native_tokens": 512, "sentence_native_tokens": 128,
                      "tokenizers_windows_models_formulas": "unchanged frozen implementation/spec",
                      "delivered_word_cap": 350, "warning_outputs_scoreable": True},
        "scope": "scorer-only 21 stored development outputs / 3 existing pilot IDs; no quality ranking or admission",
        "evidence_required": ["actual Colab T4", "native/long/identity/null fixtures", "all21 E2E",
                              "hash-bound checkpoint readback", "measured CPU/RAM/GPU/VRAM/throughput"],
        "selection_start_authorized": False, "generation_allowed": False,
        "dependency_lock_scope": "direct runtime/support pins; full actual transitive package versions captured in receipt",
        "official_package_metadata": ["https://pypi.org/pypi/sentence-transformers/5.7.0/json",
                                      "https://pypi.org/pypi/torch/2.11.0/json"]}
    write_json(bundle / "runtime_amendment.json", amendment)
    (bundle / "development_outputs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    requirements = "--extra-index-url https://download.pytorch.org/whl/cu130\n" + "".join(f"{k}=={v}\n" for k, v in {**PINS, **SUPPORT}.items())
    (bundle / "requirements-colab-t4.txt").write_text(requirements, encoding="utf-8")
    manifest = {"schema_version": 1, "files": {p.relative_to(bundle).as_posix(): file_hash(p)
                for p in sorted(bundle.rglob("*")) if p.is_file() and p.name != "package_manifest.json" and "__pycache__" not in p.parts}}
    write_json(bundle / "package_manifest.json", manifest)
    REGISTRY.mkdir(parents=True, exist_ok=True)
    for name in ("runtime_amendment.json", "requirements-colab-t4.txt", "package_manifest.json"):
        shutil.copyfile(bundle / name, REGISTRY / name)
    archive = LOCAL / "tib-scorer-colab-runtime-261020-v1.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for relative in manifest["files"]:
            output.write(bundle / relative, relative)
        output.write(bundle / "package_manifest.json", "package_manifest.json")
    receipt = {"schema_version": 1, "status": "HOLD", "scorer_ready": False,
               "actual_colab_execution": False, "T4_verified": False,
               "reason": "Prepared only; actual Colab execution evidence required",
               "archive_local_path": str(archive), "archive_bytes": archive.stat().st_size,
               "archive_sha256": file_hash(archive), "manifest_sha256": file_hash(bundle / "package_manifest.json"),
               "development_output_count": 21, "unique_source_count": 3, "quality_ranking_performed": False,
               "generation_executed": False, "selection_start_authorized": False}
    write_json(REGISTRY / "scorer_ready_receipt.json", receipt)
    return receipt


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(build(), indent=2))
