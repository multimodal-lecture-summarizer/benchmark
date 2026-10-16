"""Verify frozen spotting inputs before importing model runtimes."""
import hashlib
from importlib import metadata, util
import json
import os
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT/'experiments/registry/datasets/iiit-cvid-spotting-candidates-261014.json'
ARTIFACTS = ROOT/'research-data/spotting-candidates-261014'
RUNTIME_LOCK = Path(__file__).with_name('requirements-spotting-candidates.lock.txt')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def load_registry(path=REGISTRY):
    registry = json.loads(Path(path).read_text(encoding='utf-8'))
    for candidate in registry['candidates']:
        if canonical_sha(candidate['configuration']) != candidate['configuration_sha256']:
            raise ValueError('candidate configuration hash mismatch')
    return registry


def verify_files(items, base):
    """Paths are bounded to their declared artifact root; missing files fail closed."""
    base = Path(base).resolve()
    for relative, expected in items.items():
        target = (base/relative).resolve()
        if not target.is_relative_to(base) or not target.is_file() or sha(target) != expected:
            raise ValueError(f'file identity mismatch: {relative}')


def configure_environment(registry):
    env = registry['cpu_environment']
    # Imported engines must not have captured conflicting thread/CUDA settings.
    if any(n in sys.modules for n in ('torch','paddle')) and any(os.environ.get(k)!=v for k,v in env.items()):
        raise RuntimeError('configure thread environment before importing engines')
    os.environ.update(env)


def verify_candidate(candidate, registry, artifacts=ARTIFACTS, installed=False):
    if canonical_sha(candidate['configuration']) != candidate['configuration_sha256']:
        raise ValueError('candidate configuration hash mismatch')
    verify_files(registry['cohort_binding'], ROOT)
    verify_files(candidate['model_sha256'], Path(artifacts)/'models')
    verify_files(candidate['package']['file_sha256'], Path(artifacts)/'sources')
    verify_files({candidate['package']['wheel_filename']:candidate['package']['wheel_sha256']},artifacts)
    if installed:
        if sys.version_info[:2] != (3,11) or unicodedata.unidata_version!='14.0.0':
            raise ValueError('requires Python 3.11 / Unicode 14.0.0')
        for package, expected in registry['runtime_packages'].items():
            if metadata.version(package) != expected:
                raise ValueError(f'runtime version mismatch: {package}')
        for line in RUNTIME_LOCK.read_text(encoding='utf-8').splitlines():
            if not line or line.startswith(('#','--')):
                continue
            package, expected = line.split('==',1)
            if metadata.version(package) != expected:
                raise ValueError(f'locked runtime dependency mismatch: {package}')
        pkg = candidate['package']['name']
        package_root = Path(util.find_spec(pkg).origin).parent
        verify_files({n.removeprefix(pkg+'/'):h for n,h in candidate['package']['file_sha256'].items()},package_root)
    return dict(candidate_id=candidate['candidate_id'],configuration_sha256=candidate['configuration_sha256'],
                model_sha256=candidate['model_sha256'],cohort_binding=registry['cohort_binding'])


def bind_run_identity(path, identity, predictions_exist=False):
    """Never attach new metadata to existing predictions or mix resumed settings."""
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != identity:
            raise ValueError('resume identity mismatch; use a new run')
    else:
        if predictions_exist:
            raise ValueError('existing predictions have no bound identity')
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as f:
            json.dump(identity,f,sort_keys=True,indent=2)
            f.write('\n')
