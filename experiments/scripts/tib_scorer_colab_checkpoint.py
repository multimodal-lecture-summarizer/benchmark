"""Hash-checked scorer-only checkpoints; corrupt/missing resume data is a HOLD."""
import hashlib
import json
import os
import re
from pathlib import Path


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    encoded = json.dumps({"payload": payload, "sha256": digest(payload)},
                         ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    with temporary.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    restored = read_checked(path)
    if restored != payload:
        raise ValueError("Checkpoint immediate readback differs")
    return restored


def read_checked(path):
    path = Path(path)
    if path.with_suffix(path.suffix + ".partial").exists():
        raise ValueError("Partial checkpoint requires explicit investigation: " + str(path))
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if set(envelope) != {"payload", "sha256"} or digest(envelope["payload"]) != envelope["sha256"]:
        raise ValueError("Checkpoint integrity mismatch: " + str(path))
    return envelope["payload"]


class ScoreCheckpoints:
    def __init__(self, root, binding, *, resume=False):
        self.root, self.binding, self.resume = Path(root), binding, resume
        self.root.mkdir(parents=True, exist_ok=True)
        if list(self.root.glob("*.partial")):
            raise ValueError("Partial scorer checkpoint exists; no automatic recovery")
        if not resume and any(self.root.iterdir()):
            raise ValueError("Scorer checkpoints exist; use --resume to validate/reuse")

    def key(self, row):
        return {"binding": self.binding, "sample_id": row["sample_id"], "input_sha256": digest(row)}

    def load(self, row):
        key = self.key(row)
        path = self.root / (digest(key) + ".json")
        if not path.is_file():
            raise ValueError("Required resume checkpoint missing: " + row["sample_id"])
        payload = read_checked(path)
        if payload["key"] != key:
            raise ValueError("Scorer checkpoint binding mismatch")
        return payload

    def save(self, row, result, scoring_wall_seconds):
        key = self.key(row)
        path = self.root / (digest(key) + ".json")
        if path.exists():
            raise ValueError("Scorer checkpoint overwrite forbidden")
        return atomic_write(path, {"key": key, "result": result,
                                  "original_scoring_wall_seconds": scoring_wall_seconds})


def validate_bundle(root):
    """Reject modified code, references or cohorts before scoring any output."""
    root = Path(root).resolve()
    manifest = json.loads((root / "package_manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
              and path.name != "package_manifest.json"
              and not ("__pycache__" in path.parts and path.suffix == ".pyc")}
    if not files or set(files) != actual:
        raise ValueError("Package manifest file set mismatch")
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or file_sha(path) != expected:
            raise ValueError("Package hash/path mismatch: " + name)
    spec = json.loads((root / "frozen_scorer_spec.json").read_text(encoding="utf-8"))
    amendment = json.loads((root / "runtime_amendment.json").read_text(encoding="utf-8"))
    for name, binding in (("frozen_scorer_spec", "frozen_spec_sha256"),
                          ("cpu_ready_receipt", "cpu_ready_receipt_sha256")):
        if amendment[binding] != file_sha(root / (name + ".json")):
            raise ValueError("Frozen scorer evidence binding mismatch: " + name)
    for name, expected in spec["code_sha256"].items():
        if files.get(name) != expected:
            raise ValueError("Frozen scorer code mismatch: " + name)
    rows = [json.loads(line) for line in (root / "development_outputs.jsonl").read_text(encoding="utf-8").splitlines()]
    acceptance = None
    if amendment.get("acceptance_view_sha256"):
        path = root / "derived_acceptance_view.json"
        if file_sha(path) != amendment["acceptance_view_sha256"]:
            raise ValueError("Derived acceptance view binding mismatch")
        view = json.loads(path.read_text(encoding="utf-8"))
        acceptance = {(item["record_id"], item["trial_id"]): item for item in view["records"]}
        if len(acceptance) != 21:
            raise ValueError("Incomplete derived acceptance view")
    if len(rows) != amendment["expected_output_count"] or len(rows) != 21:
        raise ValueError("Expected exactly21 stored development outputs")
    ids, profiles = set(amendment["required_record_ids"]), set(amendment["expected_profile_ids"])
    if ids != {"valid:341", "valid:644", "valid:886"} or len(profiles) != 7:
        raise ValueError("Wrong development cohort/profile universe")
    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate sample_id")
    grid, sources = set(), {}
    for row in rows:
        pair = row["record_id"], row["profile_id"]
        if pair in grid or pair[0] not in ids or pair[1] not in profiles:
            raise ValueError("Invalid or duplicate stored-output matrix entry")
        grid.add(pair)
        if acceptance is not None:
            prior = acceptance.get(pair, {})
            decision = prior.get("derived_acceptance", {})
            if (prior.get("raw_artifact_sha256") != row["source_receipt_sha256"]
                    or decision.get("status") != row["generation_status"]
                    or decision.get("warnings") != row["warnings"]):
                raise ValueError("Stored output/acceptance provenance mismatch")
        expected_candidate = "bart" if pair[1].startswith("bart-") else "led" if pair[1].startswith("led-") else "qwen3"
        if row["candidate_id"] != expected_candidate:
            raise ValueError("Candidate/profile mismatch")
        for text, hash_key in (("source", "source_sha256"), ("reference", "reference_sha256"),
                               ("delivered_summary", "delivered_sha256")):
            if (not isinstance(row[text], str) or not row[text].strip()
                    or hashlib.sha256(row[text].encode("utf-8")).hexdigest() != row[hash_key]):
                raise ValueError("Stored text/hash mismatch: " + text)
        if len(row["delivered_summary"].split()) > 350:
            raise ValueError("Delivered summary exceeds350-word maximum")
        if not re.fullmatch(r"[a-f0-9]{64}", row["source_receipt_sha256"]):
            raise ValueError("Missing generation receipt binding")
        if (row["generation_status"] not in {"completed", "completed_with_warning"}
                or not isinstance(row["warnings"], list)
                or not all(isinstance(reason, str) for reason in row["warnings"])):
            raise ValueError("Invalid stored generation status/warnings")
        source_key = row["source_sha256"], row["reference_sha256"]
        if sources.setdefault(pair[0], source_key) != source_key:
            raise ValueError("Different source/reference for the same record")
    if grid != {(record, profile) for record in ids for profile in profiles}:
        raise ValueError("Incomplete paired development matrix")
    return manifest, spec, amendment, rows
