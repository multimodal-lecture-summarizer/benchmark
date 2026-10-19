"""Bounded local-use evidence decisions; source and reference gates stay separate."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

POLICY_VERSION = "tib-local-private-noncommercial-v1-261019-1703"
SCOPE = {"local_only": True, "private_only": True, "noncommercial_only": True,
         "retain_attribution": True, "public_text_redistribution": False,
         "external_api_text_transfer": False}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_license_uri(uri):
    """Normalize transport/deed spelling only; never substitute license versions."""
    parsed = urlsplit(uri)
    if (parsed.scheme not in ("http", "https") or parsed.netloc != "creativecommons.org"
            or parsed.query or parsed.fragment):
        return None
    parts = parsed.path.strip("/").split("/")
    if parts[-1].startswith(("deed.", "legalcode")):
        parts.pop()
    return "https://creativecommons.org/" + "/".join(parts) + "/"


def validate_policy(policy):
    if policy.get("policy_version") != POLICY_VERSION or policy.get("schema_version") != 1:
        raise ValueError("Unsupported rights policy version")
    if policy.get("scope") != SCOPE or any(
            type(policy["scope"][key]) is not bool for key in SCOPE):
        raise ValueError("Scope requires exact boolean local/private/noncommercial constraints")
    routes = policy.get("license_routes")
    if not isinstance(routes, dict) or not routes:
        raise ValueError("License routes must be a nonempty mapping")
    for uri, route in routes.items():
        if (not isinstance(uri, str) or canonical_license_uri(uri) != uri
                or not isinstance(route, dict)
                or route.get("decision") not in ("conditional", "hold")):
            raise ValueError("Invalid license route or decision; permitted decisions: conditional, hold")


def decide_record(row, raw, policy):
    """Conditional true means all recorded constraints hold for this use only."""
    validate_policy(policy)
    raw_license = raw.get("released_license_raw")
    digest = hashlib.sha256((raw_license or "").encode("utf-8")).hexdigest()
    if digest != row["released_license_raw_sha256"]:
        raise ValueError(f"Raw license hash mismatch: {row['record_id']}")
    uris = row.get("current_source_license_uris", [])
    canonical = [canonical_license_uri(uri) for uri in uris]
    routes = policy["license_routes"]
    known = [routes.get(uri) for uri in canonical]
    flags = []
    if row.get("doi_matches_export") is False:
        flags.append("doi_difference_not_automatic_wrong_record")
    if ("non-commercial" in (raw_license or "").lower()
            and any(uri and "/by-sa/" in uri for uri in canonical)):
        flags.append("released_prose_noncommercial_conflicts_with_authoritative_uri")
    checks = {**SCOPE, "attribution_complete": all(bool(row.get(key)) for key in
              ("author", "title", "source_url")), "license_uri_retained": bool(uris),
              "raw_license_retained": True, "modification_notice_retained": True}
    reason = "verified_source_cc_private_adaptation_conditions_satisfied"
    status = "conditional"
    if row.get("opendata_record_found") is not True or not uris:
        reason = "missing_per_record_current_grant_no_label_extrapolation"
    elif not all(known):
        reason = "unmapped_or_nonopen_current_uri"
    elif any(route["decision"] != "conditional" for route in known):
        reason = "older_nd_pending_version_specific_adaptation_analysis"
    elif not checks["attribution_complete"]:
        reason = "incomplete_attribution_evidence"
    elif row.get("source_nonempty") is not True:
        reason = "empty_source_text"
    else:
        reason = None
    if reason:
        status = "hold"
    source_ok = status in ("allow", "conditional")
    reference_ok = (row.get("reference_nonempty") is True
                    and row.get("abstract_use_status") == "SUPPORTED_CC0_FIELD_MATCH"
                    and row.get("reference_cc0_match") in
                    ("raw_exact", "technical_normalization_exact"))
    return {**row, "released_license_raw": raw_license,
            "policy_version": POLICY_VERSION, "source_use_status": status,
            "allowed_for_current_local_use": source_ok,
            "source_use_reason": reason or "verified_source_cc_private_adaptation_conditions_satisfied",
            "reference_use_status": "allow" if reference_ok else "hold",
            "reference_allowed_for_current_local_use": reference_ok,
            "allowed_for_reference_scoring": source_ok and reference_ok,
            "license_uri_canonical": canonical, "conditions_recorded": checks,
            "flags": flags, "public_text_redistribution_allowed": False,
            "modification_notice": "Author-release Whisper-small ASR; technical normalization; local analysis/summary adaptations only.",
            "sharealike_handling": "No sharing; any future sharing requires new version-specific review.",
            "rights_decision_scope": "Internal evidence decision, limited to source licensor rights; not third-party/legal certification."}


def build_ledger(policy_path, field_path, raw_path, output):
    """Check frozen inputs before writing; reject duplicate/misaligned full ledgers."""
    policy_path, field_path, raw_path, output = map(Path, (policy_path, field_path, raw_path, output))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    validate_policy(policy)
    benchmark = Path(__file__).resolve().parents[2]
    for relative, digest in policy["input_sha256"].items():
        if sha256(benchmark / relative) != digest:
            raise ValueError(f"Frozen input changed: {relative}")
    for path in (field_path, raw_path):
        relative = path.resolve().relative_to(benchmark).as_posix()
        if policy["input_sha256"].get(relative) != sha256(path):
            raise ValueError(f"Unbound input: {path}")
    raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))["records"]
    raw_index = {row["source_url"]: row for row in raw_rows}
    if len(raw_index) != len(raw_rows):
        raise ValueError("Duplicate raw source URL")
    fields = [json.loads(line) for line in field_path.read_text(encoding="utf-8").splitlines()]
    if (len(fields) != len(raw_rows) or len({r["record_id"] for r in fields}) != len(fields)
            or Counter(r["split"] for r in fields) != policy["expected_counts_by_split"]):
        raise ValueError("Incomplete, duplicate, or split-misaligned input ledger")
    decisions = []
    for row in fields:
        raw = raw_index[row["source_url"]]
        if raw["split"] != row["split"] or raw["doi"] != row["doi"]:
            raise ValueError(f"Raw record mismatch: {row['record_id']}")
        decisions.append(decide_record(row, raw, policy))
    output.mkdir(parents=True, exist_ok=True)
    ledger = output / "source_use_ledger.jsonl"
    summary_path = output / "rights_summary.json"
    if ledger.exists() or summary_path.exists():
        raise FileExistsError("Qualification evidence is immutable; choose a new output directory")
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in decisions), encoding="utf-8")
    counts = {}
    for split in ("train", "valid", "test"):
        rows = [r for r in decisions if r["split"] == split]
        counts[split] = {"total": len(rows), "source_status": dict(Counter(r["source_use_status"] for r in rows)),
                         "source_allowed": sum(r["allowed_for_current_local_use"] for r in rows),
                         "reference_allowed": sum(r["reference_allowed_for_current_local_use"] for r in rows),
                         "source_and_reference_allowed": sum(r["allowed_for_reference_scoring"] for r in rows)}
    summary = {"schema_version": 1, "state": "rights_qualified_not_cohort_sealed",
               "policy_version": POLICY_VERSION, "policy_sha256": sha256(policy_path),
               "input_sha256": policy["input_sha256"], "tool_sha256": sha256(__file__),
               "ledger_sha256": sha256(ledger), "counts_by_split": counts,
               "source_reasons": dict(Counter(r["source_use_reason"] for r in decisions)),
               "flag_counts": dict(Counter(flag for r in decisions for flag in r["flags"])),
               "source_allowed": sum(r["allowed_for_current_local_use"] for r in decisions),
               "reference_allowed": sum(r["reference_allowed_for_current_local_use"] for r in decisions),
               "source_and_reference_allowed": sum(r["allowed_for_reference_scoring"] for r in decisions),
               "selected_ids": [], "model_outputs_consulted": False}
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("policy", "fields", "raw-rights", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_ledger(args.policy, args.fields, args.raw_rights, args.output), indent=2))
