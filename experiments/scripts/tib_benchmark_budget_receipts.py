"""Bind projection inputs to actual bounded receipt files, never just SHA shapes."""
import hashlib
import json
from pathlib import Path


def read_bound(root, name, expected, *, parse=True):
    root = Path(root).resolve()
    if not isinstance(name, str) or not name:
        raise ValueError("Missing gate receipt path")
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Receipt missing or outside evidence root")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Receipt hash mismatch")
    return json.loads(raw) if parse else raw


def verify_gate_files(config, root):
    receipts = {name: read_bound(root, config.get(name + '_receipt_path'), config.get(name + '_receipt_sha256'))
                for name in ('scorer','store','trial_registry','admission')}
    scorer, store = receipts['scorer'], receipts['store']
    if scorer.get('scorer_ready') is not True:
        raise ValueError("Scorer receipt is not ready")
    for name, expected in scorer.get('bindings_sha256', {}).items():
        read_bound(root, name, expected)
    for name, expected in scorer.get('scorer_code_sha256', {}).items():
        read_bound(root, name, expected, parse=False)
    for flag in ('write_readback_verified','restore_verified','remote_source_use_authorized'):
        if store.get(flag) is not True:
            raise ValueError(f"Store evidence missing: {flag}")
    if receipts['trial_registry'].get('development_trials') != config.get('development_trials'):
        raise ValueError("Trial registry accounting mismatch")
    admission = receipts['admission']
    if (admission.get('admitted_candidate_ids') != config.get('admitted_candidate_ids')
            or admission.get('final_profile_ids') != config.get('final_profile_ids')):
        raise ValueError("Admission decision mismatch")


def verify_measurement_files(profiles, root):
    for profile in profiles:
        measured = read_bound(root, profile.get('measurement_receipt_path'), profile.get('measurement_receipt_sha256'))
        for key, value in profile.items():
            if key not in ('measurement_receipt_sha256','measurement_receipt_path') and measured.get(key) != value:
                raise ValueError(f"Measurement identity/statistic mismatch: {key}")
