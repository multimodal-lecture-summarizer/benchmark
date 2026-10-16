"""Six scientific selections with independent acquisition and runtime gates."""
import json
from pathlib import Path
import urllib.request
import zipfile

from experiments.scripts.spotting_colab_artifacts import acquire, digest, extract, sha, verify_files
from experiments.scripts.spotting_colab_environments import prepare_environment, provision_tesseract

REGISTRY = Path(__file__).resolve().parents[1]/'registry/datasets/iiit-cvid-spotting-colab-t4-candidates-261015.json'


def load_registry(path=None):
    value = json.loads(Path(path or REGISTRY).read_text(encoding='utf-8'))
    if len({c['candidate_id'] for c in value['candidates']}) != len(value['candidates']):
        raise ValueError('duplicate candidate IDs')
    for candidate in value['candidates']:
        if digest(candidate['configuration']) != candidate['configuration_sha256']:
            raise ValueError('candidate configuration digest mismatch')
    return value


def _checkpoint_member(spec, root):
    """The original Easy recognition archive is mutable, its selected bytes are locked."""
    path = root/spec['path']
    if path.exists():
        if sha(path) != spec['sha256']:
            raise ValueError('recognizer digest mismatch')
        return
    archive = root/'english_g2-download.zip'
    urllib.request.urlretrieve(spec['url'], archive)
    with zipfile.ZipFile(archive) as bundle:
        data = bundle.read(spec['zip_member'])
    import hashlib
    if hashlib.sha256(data).hexdigest() != spec['sha256']:
        raise ValueError('recognizer member digest mismatch')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)


def prepare_candidate(candidate, work_root):
    if not candidate['locked']:
        raise ValueError(candidate['blocking_reason'])
    if digest(candidate['configuration']) != candidate['configuration_sha256']:
        raise ValueError('candidate configuration altered')
    root = Path(work_root).resolve()/'candidates'/candidate['candidate_id']
    root.mkdir(parents=True,exist_ok=True)
    for artifact in candidate['artifacts']:
        if artifact.get('zip_member'):
            _checkpoint_member(artifact,root)
        else:
            path = acquire(artifact,root)
            if artifact['path'] in candidate.get('archives',{}):
                extract(path,root/candidate['archives'][artifact['path']])
    verify_files(root/'models',candidate['model_sha256'])
    python, environment = prepare_environment(candidate,work_root)
    prepared = dict(candidate_id=candidate['candidate_id'],python=python,models=str(root/'models'),
                    candidate_sha256=digest(candidate), environment=environment,
                    model_sha256=candidate['model_sha256'])
    prepared['library_paths'] = [str(p) for p in sorted((Path(python).parent.parent/'lib').glob('python*/site-packages/nvidia/*/lib'))]
    if candidate['adapter'] == 'tesseract':
        prepared['tesseract'],prepared['binary_identity'] = provision_tesseract()
    if candidate['adapter'] == 'testr':
        prepared['testr_source'] = str(Path(work_root).resolve()/'environments'/candidate['candidate_id']/'testr')
    return prepared


def verify_prepared(candidate, prepared):
    if prepared['candidate_sha256'] != digest(candidate):
        raise ValueError('prepared candidate registry binding mismatch')
    verify_files(prepared['models'],candidate['model_sha256'])
    from experiments.scripts.spotting_colab_environments import environment_snapshot
    if digest(environment_snapshot(prepared['python'])) != prepared['environment']['installed_digest']:
        raise ValueError('installed environment no longer matches prepare seal')
    for name, source in prepared['environment'].get('sources',{}).items():
        checkout = Path(prepared['python']).parent.parent.parent/name
        verify_files(checkout,source['files'])
    if candidate['adapter'] == 'tesseract':
        if sha(prepared['tesseract']) != prepared['binary_identity']['binary_sha256']:
            raise ValueError('Tesseract binary changed')
        for path, expected in prepared['binary_identity']['libraries'].items():
            if sha(path) != expected:
                raise ValueError('Tesseract linked library changed')


def lock_testr_checkpoint(checkpoint, output_registry, provenance_url):
    """Create a NEW reviewed registry for recovered author bytes; old registry is immutable.

    Provenance cannot be inferred from an arbitrary file hash. Caller must identify the
    recovered author checkpoint explicitly; a later genuine model/build gate is mandatory.
    """
    registry = load_registry()
    candidate = next(c for c in registry['candidates'] if c['adapter']=='testr')
    if provenance_url != candidate['checkpoint_url']:
        raise ValueError('TESTR provenance must identify the declared author checkpoint')
    path = Path(checkpoint).resolve()
    if not path.is_file():
        raise ValueError('recovered checkpoint missing')
    candidate['model_sha256'] = {'testr/model.pth':sha(path)}
    candidate['artifacts'] = [dict(path='models/testr/model.pth',url=path.as_uri(),sha256=sha(path))]
    candidate.update(locked=True,blocking_reason=None,
                     provenance_note='Recovered author bytes identified by caller; acquisition provenance not independently authenticated')
    output = Path(output_registry)
    if output.exists():
        raise ValueError('new registry path required')
    output.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return output
