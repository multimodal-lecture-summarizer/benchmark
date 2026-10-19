"""Offline reference qualification; canonical transcript, no model outcomes or scores."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

try:
    from .rq2_tib_benchmark_dataset import REVISION, prepare_record
except ImportError:  # Direct CLI execution from the script directory.
    from rq2_tib_benchmark_dataset import REVISION, prepare_record

VERSION = "tib-reference-usability-v1-261019-1703"
SPLITS = ("train", "valid", "test")


def normalize(text):
    return " ".join(unicodedata.normalize("NFC", str(text or "")).split())


def historical_normalize(text):
    return " ".join(str(text or "").strip().casefold().split())


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_records(data):
    import pyarrow.parquet as parquet

    for split in SPLITS:
        index = 0
        for path in sorted(data.glob(f"{split}-*.parquet")):
            for batch in parquet.ParquetFile(path).iter_batches(batch_size=64):
                for row in batch.to_pylist():
                    yield split, index, row
                    index += 1


def freeze_policy(data, destination):
    """Calibration precedes policy serialization and full-ledger processing."""
    if destination.exists():
        raise ValueError("Policy already frozen; use a new version for amendments")
    notes = [
        "Rod/bar manufacture and testing appear in opening; full coverage unreviewed.",
        "ROS evolution appears in opening; design/new-feature claims unreviewed.",
        "Custom pinball topic appears in opening; hardware/software coverage unreviewed.",
        "Differential privacy/census relation appears in opening; full coverage unreviewed.",
        "Course boilerplate plus specific organometallic title; opening related, full coverage uncertain.",
        "React Hooks/Volto integration appears in opening; transformation demonstration unreviewed.",
    ]
    calibration = []
    for split, index, row in iter_records(data):
        if split != "train" or index >= 6:
            break
        source, reference = row.get("transcript") or "", row.get("abstract") or ""
        calibration.append({"record_id": f"{split}:{index}", "source_raw_sha256": sha(source),
                            "reference_raw_sha256": sha(reference), "label": "B",
                            "review_scope": "entire abstract and first 1200 transcript characters",
                            "relation_note": notes[index], "uncertainty": "full presentation relation unreviewed"})
    policy = {
        "policy_version": VERSION, "revision": REVISION, "status": "frozen_before_full_ledger",
        "calibration": calibration, "calibration_version": "train-first-six-v1",
        "canonical_source": "transcript", "normalization": "Unicode NFC then whitespace collapse; case-sensitive",
        "historical_normalization": "legacy strip/casefold/whitespace collapse; no NFC",
        "A": "Reviewed reference content and presentation relation supported by explicit source spans; not factual gold.",
        "B": "Nonempty creator abstract with unresolved coverage/relation/quality uncertainty; retained in primary A+B.",
        "C": "Empty normalized reference, or explicit reviewed evidence of unusability/mismatch; no proxy cutoff.",
        "default_nonempty": "B", "empty": "C", "primary": ["A", "B"],
        "short_generic_reused": "diagnostic flags only; never automatic C",
        "nonempty_review_requirement": ["reviewer", "reference_hash", "source_hash", "source_spans", "relation_evidence", "uncertainty"],
        "calibration_decision": "Topic-related openings alone do not justify A; boilerplate/shortness alone do not justify C.",
        "rights_scope": "Reference labels grant no rights; permission/source/group eligibility is separate.",
        "forbidden_inputs": ["model predictions", "ROUGE", "BERTScore", "candidate outcomes", "test performance"],
        "amendment": "Version and requalify every split before related outcomes; preserve prior receipt.",
    }
    write_json(destination, policy)


def classify_reference(reference):
    return "B" if normalize(reference) else "C"


def qualify(data, policy_path, output, compact):
    protected = [output / name for name in ("reference_usability_ledger.jsonl", "historical_reuse_review.jsonl", "reference_summary.json")]
    protected.append(compact / "reference_summary.json")
    if any(path.exists() for path in protected):
        raise ValueError("Existing reference evidence cannot be overwritten; choose a new qualification directory")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy["policy_version"] != VERSION or policy["default_nonempty"] != "B":
        raise ValueError("Unknown frozen policy")
    policy_hash = sha(policy_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    rows, historical_groups, current_groups = [], defaultdict(list), defaultdict(list)
    for split, index, raw in iter_records(data):
        source, reference = raw.get("transcript") or "", raw.get("abstract") or ""
        normalized_reference = normalize(reference)
        legacy = prepare_record(split, index, raw)
        flags = []
        if normalized_reference and len(normalized_reference.split()) < 30:
            flags.append("short_under_30_words_diagnostic_only")
        if re.search(r"(part of (a|the) course|topics covered include|course of lectures)", reference, re.I):
            flags.append("possible_course_boilerplate_diagnostic_only")
        row = {"record_id": f"{split}:{index}", "split": split, "source_index": index,
               "reference_label": classify_reference(reference),
               "reference_primary_eligible": bool(normalized_reference),
               "reference_only_eligibility": "eligible_flagged" if normalized_reference else "excluded_empty",
               "reference_raw_sha256": sha(reference), "reference_normalized_sha256": sha(normalized_reference),
               "source_raw_sha256": sha(source), "source_normalized_sha256": sha(normalize(source)),
               "reference_words": len(normalized_reference.split()), "audit_flags": flags,
               "legacy_structural_eligible": legacy["text_usable"],
               "legacy_structural_reasons": legacy["structural_reasons"],
               "legacy_reused_reference_flag": False, "current_reused_reference_flag": False,
               "review_status": "unreviewed_uncertain_B" if normalized_reference else "mechanically_empty_C",
               "reviewer": None, "relation_evidence": None, "source_spans": [],
               "uncertainty": "presentation/reference relation not fully reviewed" if normalized_reference else None,
               "policy_version": VERSION, "policy_sha256": policy_hash}
        rows.append(row)
        if normalized_reference:
            current_groups[normalized_reference].append(row)
        key = historical_normalize(reference)
        if key and legacy["text_usable"]:
            historical_groups[key].append(row)
    reused = [(key, group) for key, group in historical_groups.items() if len(group) > 1]
    for _, group in reused:
        for row in group:
            row["legacy_reused_reference_flag"] = True
    for key, group in current_groups.items():
        if len(group) > 1:
            for row in group:
                row["current_reused_reference_flag"] = True
                row["current_reference_group_id"] = "reference:" + sha(key)
                row["review_status"] = "targeted_review_pending_keep_B"
                row["audit_flags"].append("reused_reference_diagnostic_only")
    reviews = []
    for key, group in reused:
        ids = [row["record_id"] for row in group]
        for row in group:
            reviews.append({**row, "historical_group_member_ids": ids,
                            "historical_group_id": "legacy-reference:" + sha(key),
                            "adjudication": "pending; B is uncertainty default, not blanket restoration or exclusion",
                            "rights_or_final_eligibility_decision": "not_granted_by_reference_policy"})
    for name, values in (("reference_usability_ledger.jsonl", rows), ("historical_reuse_review.jsonl", reviews)):
        with (output / name).open("w", encoding="utf-8") as handle:
            for row in values:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {"policy_version": VERSION, "policy_sha256": policy_hash, "revision": REVISION,
               "source_count": len(rows), "labels": dict(Counter(row["reference_label"] for row in rows)),
               "by_split": {split: dict(Counter(row["reference_label"] for row in rows if row["split"] == split)) for split in SPLITS},
               "legacy_structural_eligible": sum(row["legacy_structural_eligible"] for row in rows),
               "legacy_empty_after_structure": sum(row["legacy_structural_eligible"] and row["reference_label"] == "C" for row in rows),
               "legacy_reused_flags": len(reviews), "legacy_reused_groups": len(reused),
               "legacy_broad_pool": sum(row["legacy_structural_eligible"] and row["reference_label"] != "C" and not row["legacy_reused_reference_flag"] for row in rows),
               "current_case_sensitive_reused_flags": sum(row["current_reused_reference_flag"] for row in rows),
               "current_case_sensitive_reused_groups": sum(len(group) > 1 for group in current_groups.values()),
               "legacy_only_reused_ids": [row["record_id"] for row in rows if row["legacy_reused_reference_flag"] and not row["current_reused_reference_flag"]],
               "current_only_reused_ids": [row["record_id"] for row in rows if row["current_reused_reference_flag"] and not row["legacy_reused_reference_flag"]],
               "targeted_adjudication_complete": False, "A_only_sensitivity_available": False,
               "cohort_seal_ready": False, "rights_granted": False,
               "historical_reconciliation": "legacy structural pool + casefold reference groups; new flags use all rows + NFC case-sensitive references",
               "raw_text_storage": "pinned ignored Parquet only; no transcript/abstract text copied to registry"}
    summary["historical_expected_counts_match"] = (summary["legacy_structural_eligible"], summary["legacy_empty_after_structure"], len(reviews), summary["legacy_broad_pool"]) == (9002, 8, 225, 8769)
    write_json(output / "reference_summary.json", summary)
    write_json(compact / "reference_summary.json", summary)
    return summary


def verify_review_members(data, by_id, rows):
    """Verify actual pinned text and every raw-character excerpt before recording review."""
    ledger = {row["record_id"]: row for row in rows}
    if set(by_id) - set(ledger):
        raise ValueError("Review ID missing from reference ledger")
    found, span_count = set(), 0
    for split, index, raw in iter_records(data):
        rid = f"{split}:{index}"
        if rid not in by_id:
            continue
        found.add(rid)
        source, abstract = raw.get("transcript") or "", raw.get("abstract") or ""
        member = by_id[rid][1]
        actual = {"source_raw_sha256": sha(source), "reference_raw_sha256": sha(abstract),
                  "reference_normalized_sha256": sha(normalize(abstract))}
        if any(member[key] != value or ledger[rid][key] != value for key, value in actual.items()):
            raise ValueError("Review hashes differ from actual pinned text")
        if ledger[rid]["reference_label"] != "B":
            raise ValueError("Uncertainty B review requires a nonempty B reference")
        for span in member["source_spans"]:
            start, end = span.get("start"), span.get("end")
            if (type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(source)
                    or span.get("coordinate") != "raw Unicode character offsets; end exclusive"):
                raise ValueError("Invalid review source span bounds or coordinate")
            if span.get("sha256") != sha(source[start:end]):
                raise ValueError("Review excerpt hash differs from actual pinned source span")
            span_count += 1
    if found != set(by_id):
        raise ValueError("Review ID missing from pinned source")
    return span_count


def apply_reviews(output, compact, review_path, data, *, validate_only=False):
    """Attach explicit human/agent review evidence without changing the frozen rubric."""
    reviews = json.loads(review_path.read_text(encoding="utf-8"))
    by_id = {}
    for group in reviews["groups"]:
        if group["decision"] != "B" or not group["rationale"]:
            raise ValueError("This review receipt supports uncertainty B only")
        for member in group["members"]:
            rid = member["record_id"]
            if rid in by_id or not member["source_spans"]:
                raise ValueError("Duplicate review ID or missing inspected source span")
            by_id[rid] = (group, member)
    ledger_path = output / "reference_usability_ledger.jsonl"
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["record_id"] not in by_id:
            continue
        group, member = by_id[row["record_id"]]
        for key in ("source_raw_sha256", "reference_raw_sha256", "reference_normalized_sha256"):
            if member[key] != row[key]:
                raise ValueError("Review and pinned ledger hashes differ")
        row.update(review_status="reviewed_uncertain_B", reviewer=group["reviewer"],
                   relation_evidence=group["rationale"], source_spans=member["source_spans"],
                   review_packet_group=group["packet_group"], historical_group_id=group["historical_group_id"],
                   uncertainty="Course/topic relation inspected in limited spans; full presentation coverage not certified")
    span_count = verify_review_members(data, by_id, rows)
    legacy = [row for row in rows if row["legacy_reused_reference_flag"]]
    if validate_only:
        receipt = {"validation_version": "reference-review-source-span-validation-v2",
                   "policy_version": VERSION, "status": "pass", "reviewed_member_count": len(by_id),
                   "validated_source_span_count": span_count, "historical_reviewed_count": len(legacy),
                   "review_receipt_sha256": sha(review_path.read_text(encoding="utf-8")),
                   "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "preserved_files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                       for name in ("reference_usability_ledger.jsonl", "historical_reuse_review.jsonl", "reference_summary.json")}}
        destination = compact / "reference_review_validation_v2.json"
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, indent=2) + "\n")
        return receipt
    for name, values in (("reference_usability_ledger.jsonl", rows), ("historical_reuse_review.jsonl", legacy)):
        with (output / name).open("w", encoding="utf-8") as handle:
            for row in values:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = json.loads((output / "reference_summary.json").read_text(encoding="utf-8"))
    summary.update(targeted_adjudication_complete=all(row["review_status"] == "reviewed_uncertain_B" for row in legacy),
                   historical_reviewed_count=sum(row["review_status"] == "reviewed_uncertain_B" for row in legacy),
                   all_row_targeted_reviewed_count=len(by_id),
                   review_receipt_sha256=sha(review_path.read_text(encoding="utf-8")),
                   review_scope="All historical reuse members reviewed via entire abstract, title and one source context span; conservative B, not full-transcript/factuality review")
    write_json(output / "reference_summary.json", summary)
    write_json(compact / "reference_summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", type=Path)
    parser.add_argument("--freeze-policy", action="store_true")
    parser.add_argument("--apply-reviews", type=Path)
    parser.add_argument("--validate-reviews", type=Path)
    args = parser.parse_args()
    if args.freeze_policy:
        freeze_policy(args.data, args.policy)
    else:
        if args.output is None or args.compact is None:
            parser.error("--output and --compact are required for qualification")
        review = args.apply_reviews or args.validate_reviews
        if args.apply_reviews and args.validate_reviews:
            parser.error("Choose --apply-reviews or --validate-reviews")
        result = (apply_reviews(args.output, args.compact, review, args.data, validate_only=bool(args.validate_reviews)) if review
                  else qualify(args.data, args.policy, args.output, args.compact))
        print(json.dumps(result, indent=2))
