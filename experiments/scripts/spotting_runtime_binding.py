"""Test-bound identities and fail-closed runtime prerequisites; no engine import."""
from importlib import metadata
import json
from pathlib import Path
import site
import sys

from experiments.scripts.spotting_candidate_contract import (
    ARTIFACTS, ROOT, REGISTRY, RUNTIME_LOCK, canonical_sha, load_registry, sha, verify_files,
)

TEST = ROOT/'experiments/registry/datasets'
NAME = 'iiit-cvid-spotting-test-261014'
FREEZE_SHA = '9504e34f69b16f4b63893184e5decf2e3d88d7251833b0efbb85f2eb883438dd'
BINDING_SHA = '3c8101c36e6fef4b06d5a4efb0a1307757bed3aac742720ecefd034411b55d22'
LOCK_SHA = '56706330c3d94a16793999083bb8d796551a4032fa48e095deedb4a8c382cd0d'
EVIDENCE_SHA = {'-verified':'327911a737c49bddf5d66340522e645fb42b7bc7408d0548d8c4579488200a6a',
                '-replay-verified':'8ce621c6d06fcd7891837c4b5ea41c51927bac95d6d9365d4b136354906f2b5b'}
VENV = ARTIFACTS/'venv'
IMPLEMENTATION = ['spotting_runtime_binding.py','spotting_runtime_inspect.py','spotting_runtime_worker.py',
    'spotting_runtime_guard.py','spotting_runtime_fingerprint.py','verify_spotting_test_runtime.py',
    'spotting_candidate_contract.py','spotting_candidate_adapters.py']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def test_binding():
    freeze_path, binding_path = (TEST/(NAME+s+'.json') for s in ('-freeze','-candidate-binding'))
    require(sha(freeze_path)==FREEZE_SHA and sha(binding_path)==BINDING_SHA, 'frozen test anchor mismatch')
    freeze,binding = read_json(freeze_path),read_json(binding_path)
    registry = load_registry()
    require(sha(REGISTRY)==binding['candidate_registry']['sha256'], 'candidate registry/test binding mismatch')
    for suffix in ('-verified','-replay-verified'):
        path=TEST/(NAME+suffix+'.json')
        require(sha(path)==EVIDENCE_SHA[suffix] and read_json(path)['freeze_receipt_sha256']==FREEZE_SHA, 'test verification anchor mismatch')
    expected = {c['candidate_id']:{k:c[k] for k in ('configuration_sha256','model_sha256')} for c in registry['candidates']}
    observed = {c['candidate_id']:{k:c[k] for k in ('configuration_sha256','model_sha256')} for c in binding['candidates']}
    require(len(expected)==len(observed)==len(registry['candidates'])==len(binding['candidates'])==2 and expected==observed,
            'test candidate membership/configuration/weights mismatch')
    require(registry['cohort_binding']==binding['validation_cohort_binding_preserved'], 'validation binding changed')
    require(sha(RUNTIME_LOCK)==LOCK_SHA, 'runtime lock anchor mismatch')
    snapshot = {str((TEST/(NAME+s+'.json')).relative_to(ROOT)):sha(TEST/(NAME+s+'.json'))
                for s in ('-freeze','-candidate-binding','-verified','-replay-verified')}
    for item in freeze['artifacts']+binding['test_inputs']+freeze['prerequisites']:
        snapshot[item['path']] = item['sha256']
    snapshot.update(freeze['preserved_sha256'])
    snapshot[REGISTRY.relative_to(ROOT).as_posix()] = binding['candidate_registry']['sha256']
    snapshot[RUNTIME_LOCK.relative_to(ROOT).as_posix()] = LOCK_SHA
    snapshot['research-data/iiit-cvid-source/IIIT-CVid.zip'] = freeze['source_zip_sha256']
    snapshot.update({'experiments/scripts/'+n:sha(Path(__file__).with_name(n)) for n in IMPLEMENTATION})
    for c in registry['candidates']:
        base = ARTIFACTS.relative_to(ROOT).as_posix()+'/'
        snapshot.update({base+'models/'+p:h for p,h in c['model_sha256'].items()})
        snapshot.update({base+'sources/'+p:h for p,h in c['package']['file_sha256'].items()})
        snapshot[base+c['package']['wheel_filename']] = c['package']['wheel_sha256']
    verify_files(snapshot,ROOT)
    require(freeze['selected_frames']==1754 and freeze['selected_objects']==40063, 'test denominator changed')
    return registry,binding,snapshot


def isolated_runtime():
    require(Path(sys.prefix).resolve()==VENV.resolve() and sys.prefix!=sys.base_prefix, 'use pinned isolated spotting venv')
    require(site.ENABLE_USER_SITE is False, 'user site must be disabled')
    packages = {}
    for line in RUNTIME_LOCK.read_text(encoding='utf-8').splitlines():
        if line and not line.startswith(('#','--')):
            name,version=line.split('==',1)
            require(metadata.version(name)==version, 'locked runtime dependency mismatch: '+name)
            packages[name]=version
    return packages


def assert_native_origins(candidate, modules):
    """Paddle uses unqualified aliases; verify actual loaded origins, not spec alone."""
    package=candidate['package']['name']
    prefix=VENV/'Lib/site-packages'/package
    observed={}
    for name,module in sorted(modules.items()):
        relevant=name==package or name.startswith(package+'.')
        if package=='paddleocr':
            relevant=relevant or name in ('tools','ppocr') or name.startswith(('tools.','ppocr.'))
        if not relevant or not getattr(module,'__file__',None):
            continue
        path=Path(module.__file__).resolve()
        require(path.is_relative_to(prefix.resolve()), 'unexpected native module origin: '+name)
        relative=package+'/'+path.relative_to(prefix.resolve()).as_posix()
        expected=candidate['package']['file_sha256'].get(relative)
        require(expected is not None and sha(path)==expected, 'loaded native source mismatch: '+name)
        observed[name]=dict(path=str(path),sha256=expected)
    require(observed, 'no loaded native sources observed')
    return observed
