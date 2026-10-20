"""Prepare a private recovery package without changing either original bundle."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / 'research-data/tib-p4-fresh-recovery-261020-v2'
REGISTRY = ROOT / 'experiments/registry/protocols/tib-p4-fresh-recovery-261020-v2'
GEN = ROOT / 'research-data/tib-p41-261019-2122'
SCORER = ROOT / 'experiments/registry/protocols/tib-scorer-colab-runtime-261020-v1'
TOOLS = ['tib_p4_session_recovery', 'tib_p4_recovery_context', 'tib_p4_generation_recovery', 'tib_p4_scorer_replay']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def extract_verified(archive, target):
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or source.testzip() is not None:
            raise ValueError('Invalid original ZIP')
        for name in names:
            path = (target / name).resolve()
            if not path.is_relative_to(target.resolve()):
                raise ValueError('Unsafe original ZIP path')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source.read(name))


def build():
    package = LOCAL / 'package'
    package.mkdir(parents=True, exist_ok=True)
    gen_archive = GEN / 'tib-p41-development-261019.zip'
    if sha(gen_archive) != '51593e37d868ba05d5fb1c2dfb2ef8eaa95467ca8b6ff1ddeac56b7dd3efefa8':
        raise ValueError('Original P4.1 generation bundle differs')
    extract_verified(gen_archive, package / 'generation_bundle')
    original_scorer_zip = json.loads((SCORER / 'scorer_ready_receipt.json').read_text())
    scorer_archive = Path(original_scorer_zip['archive_local_path'])
    if sha(scorer_archive) != original_scorer_zip['archive_sha256']:
        raise ValueError('Original scorer ZIP differs')
    extract_verified(scorer_archive, package / 'scorer_bundle')
    returned_gen_zip = GEN / 'returned-evidence-20261019T151425Z/tib-p41-evidence-20261019T151425Z.zip'
    returned_gen_sha = 'db97d6b9093af58572a79c403c06e2d5fcfe24bc59268930958759f5987193ed'
    if sha(returned_gen_zip) != returned_gen_sha:
        raise ValueError('Audited returned P4.1 archive differs')
    with zipfile.ZipFile(returned_gen_zip) as source:
        gen_files = {name.removeprefix('checkpoints/'): hashlib.sha256(source.read(name)).hexdigest()
                     for name in source.namelist() if name.startswith('checkpoints/') and not name.endswith('/')}
    if len(gen_files) != 288:
        raise ValueError('Expected original281JSON envelopes plus7logs')
    gen_bundle = package / 'generation_bundle'
    expected_gen = {'files': gen_files, 'bundle_sha256': sha(gen_bundle / 'bundle_manifest.json'),
                    'bundle_archive_sha256': sha(gen_archive), 'returned_archive_sha256': returned_gen_sha,
                    'bundle_files': {p.relative_to(gen_bundle).as_posix(): sha(p)
                                     for p in sorted(gen_bundle.rglob('*')) if p.is_file()}}
    actual_zip = ROOT / 'research-data/tib-scorer-colab-runtime-261020-v1/returned-20261020T010554Z/tib-scorer-evidence-20261020T010554Z.zip'
    if sha(actual_zip) != '116ecb2ccce3d47689fba85c35f4036f38b03ee2bab84423be2e0e11b4065ad7':
        raise ValueError('Actual scorer export differs')
    with zipfile.ZipFile(actual_zip) as source:
        ready = source.read('evidence/scorer_ready_receipt.json')
        write_ready = package / 'origin_scorer_ready.json'
        write_ready.write_bytes(ready)
        score_files = {name.removeprefix('evidence/checkpoints/'): hashlib.sha256(source.read(name)).hexdigest()
                       for name in source.namelist() if name.startswith('evidence/checkpoints/')}
        asset_sha = {}
        for key in ('bert', 'sentence'):
            raw = source.read('scorer-assets/' + key + '/asset_manifest.json')
            path = package / 'scorer_asset_manifests' / key / 'asset_manifest.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            asset_sha[key] = hashlib.sha256(raw).hexdigest()
    write(package / 'expected_generation.json', expected_gen)
    write(package / 'expected_scorer.json', {'files': score_files,
          'origin_ready_sha256': hashlib.sha256(ready).hexdigest(), 'asset_manifest_sha256': asset_sha})
    write(package / 'drive_layout.json', {
        'generation': 'TIB_P41_DEVELOPMENT_261019/checkpoints',
        'scorer': 'TIB_P4_SCORER_261020_V1/scorer-evidence/checkpoints'})
    requirements = (package / 'scorer_bundle/requirements-colab-t4.txt').read_text()
    (package / 'requirements-recovery.txt').write_text(requirements + 'accelerate==1.15.0\n', encoding='utf-8')
    tools = package / 'tools'
    tools.mkdir(exist_ok=True)
    for name in TOOLS:
        shutil.copyfile(ROOT / 'experiments/scripts' / (name + '.py'), tools / (name + '.py'))
    manifest = {'schema_version': 1, 'scope': 'Read-only fresh-session recovery; no pilot/selection/generation/scoring',
                'files': {p.relative_to(package).as_posix(): sha(p) for p in sorted(package.rglob('*'))
                          if p.is_file() and p.name != 'recovery_manifest.json' and '__pycache__' not in p.parts}}
    write(package / 'recovery_manifest.json', manifest)
    archive = LOCAL / 'tib-p4-fresh-recovery-261020-v2.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for name in manifest['files']:
            output.write(package / name, name)
        output.write(package / 'recovery_manifest.json', 'recovery_manifest.json')
    plan = {'schema_version': 1, 'state': 'PREPARED_HOLD_ACTUAL_FRESH_COLAB_REQUIRED',
            'scorer_ready_step': 'CLOSED_PASS_ACTUAL_T4', 'generation_profiles_replayed': 7,
            'expected_generation_outputs': 21, 'expected_generation_nodes': 123,
            'expected_scorer_checkpoints': 21, 'generation_store_files': len(gen_files),
            'scorer_store_files': len(score_files), 'origin_witness_required': True,
            'different_vm_boot_id_required': True, 'no_key_or_runtime_identity_rewrite': True,
            'forbidden_new_generation_calls': True, 'forbidden_new_metric_calls': True,
            'metric_definitions_and_original_bundles_unchanged': True,
            'cross_session_recovery_verified': False, 'pilot40_authorized': False,
            'selection_start_authorized': False, 'pilot_profiles': ['bart-control', 'led-ngram3', 'qwen-r384', 'lead3', 'lexrank'],
            'pilot_ids': 40, 'selection_ids': 300, 'final_target': 523, 'word_cap_maximum': 350,
            'full_study_budget_verified': False}
    write(REGISTRY / 'recovery_plan.json', plan)
    for name in ('recovery_manifest.json', 'expected_generation.json', 'expected_scorer.json', 'requirements-recovery.txt'):
        REGISTRY.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(package / name, REGISTRY / name)
    receipt = {'schema_version': 1, 'status': 'HOLD', 'actual_fresh_session_executed': False,
               'archive_local_path': str(archive), 'archive_bytes': archive.stat().st_size,
               'archive_sha256': sha(archive), 'manifest_sha256': sha(package / 'recovery_manifest.json'),
               'cross_session_recovery_verified': False, 'original_bundles_preserved': True}
    write(REGISTRY / 'preparation_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
