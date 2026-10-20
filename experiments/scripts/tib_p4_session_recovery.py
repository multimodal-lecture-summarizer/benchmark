"""Drive origin witness and fresh-VM proof; never modify generation/scorer stores."""
import hashlib
import json
import os
from pathlib import Path
import platform
import time


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                   ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def session_fingerprint():
    import google.colab
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if len(boot) != 36 or not Path('/content/drive/MyDrive').is_dir():
        raise ValueError('Actual mounted Colab Linux session required')
    return {'google_colab_imported': True, 'boot_id': boot, 'pid': os.getpid(),
            'observed_epoch_ns': time.time_ns(), 'python': platform.python_version(),
            'platform': platform.platform()}


def validate_package(package):
    package = Path(package).resolve()
    manifest = json.loads((package / 'recovery_manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = (package / name).resolve()
        if not path.is_relative_to(package) or not path.is_file() or sha(path) != expected:
            raise ValueError('Recovery package file/hash mismatch: ' + name)
    return manifest


def inventory(root, expected):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Original checkpoint store absent: ' + str(root))
    for name, expected_sha in expected.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha(path) != expected_sha:
            raise ValueError('Original Drive checkpoint missing/changed: ' + name)
    files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    if any(name.endswith(('.partial', '.tmp')) for name in files):
        raise ValueError('Incomplete checkpoint store; no automatic repair')
    return files


def source_stores(package, drive):
    package, drive = Path(package), Path(drive)
    layout = json.loads((package / 'drive_layout.json').read_text())
    result = {}
    for kind in ('generation', 'scorer'):
        relative = layout[kind]
        root = (drive / relative).resolve()
        if not root.is_relative_to(drive.resolve()):
            raise ValueError('Drive root escapes configured private Drive')
        expected = json.loads((package / ('expected_' + kind + '.json')).read_text())['files']
        result[kind] = {'drive_relative_root': relative, 'files': inventory(root, expected)}
    return result


def read_witness(path):
    envelope = json.loads(Path(path).read_text())
    if set(envelope) != {'payload', 'sha256'} or digest(envelope['payload']) != envelope['sha256']:
        raise ValueError('Origin witness hash mismatch')
    return envelope['payload']


def seal_origin(package, drive, witness):
    """Run in current session BEFORE deleting runtime; refuse witness replacement."""
    package, witness = Path(package), Path(witness)
    validate_package(package)
    _safe_output(package, drive, witness.parent)
    identity = session_fingerprint()
    stores = source_stores(package, drive)
    if witness.exists():
        prior = read_witness(witness)
        if (prior['origin_session']['boot_id'] == identity['boot_id'] and prior['stores'] == stores
                and prior['recovery_manifest_sha256'] == sha(package / 'recovery_manifest.json')):
            return prior
        raise ValueError('Origin witness exists; do not replace it. Use the fresh recovery notebook.')
    payload = {'schema_version': 1, 'state': 'ORIGIN_SEALED_NOT_RECOVERY_PASS',
               'origin_session': identity, 'stores': stores,
               'recovery_manifest_sha256': sha(package / 'recovery_manifest.json'),
               'created_epoch_ns': time.time_ns(), 'new_generation_calls': 0, 'new_metric_calls': 0}
    witness.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({'payload': payload, 'sha256': digest(payload)}, indent=2, allow_nan=False)
    with witness.open('x', encoding='utf-8') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if read_witness(witness) != payload:
        raise ValueError('Origin witness readback mismatch')
    return payload


def verify_fresh(package, drive, witness):
    validate_package(package)
    prior = read_witness(witness)
    current = session_fingerprint()
    if prior['recovery_manifest_sha256'] != sha(Path(package) / 'recovery_manifest.json'):
        raise ValueError('Origin witness belongs to another recovery package')
    if not prior['origin_session'].get('google_colab_imported'):
        raise ValueError('Origin was not recorded in Colab')
    if current['boot_id'] == prior['origin_session']['boot_id']:
        raise ValueError('Same VM/session: delete old Colab runtime before recovery')
    if current['observed_epoch_ns'] <= prior['created_epoch_ns']:
        raise ValueError('Recovery must follow the origin seal')
    if source_stores(package, drive) != prior['stores']:
        raise ValueError('Checkpoint directory changed since origin seal')
    return {'state': 'FRESH_VM_AND_DRIVE_HASHES_VERIFIED', 'origin_witness_sha256': sha(witness),
            'origin_session': prior['origin_session'], 'recovery_session': current,
            'different_vm_boot_id': True, 'source_stores_unchanged': True}


def _safe_output(package, drive, output):
    output, drive = Path(output).resolve(), Path(drive).resolve()
    layout = json.loads((Path(package) / 'drive_layout.json').read_text())
    if not output.is_relative_to(drive):
        raise ValueError('Recovery evidence must stay in configured private Drive')
    for relative in layout.values():
        root = (drive / relative).resolve()
        if output.is_relative_to(root) or root.is_relative_to(output):
            raise ValueError('Recovery output/witness cannot overlap original stores')


def validate_stage_context(context_path, output, stage):
    try:
        from tib_p4_recovery_context import validate_stage_context as validate
    except ModuleNotFoundError:
        from .tib_p4_recovery_context import validate_stage_context as validate
    return validate(context_path, output, stage)
