"""Verify original test bindings and extract only hash-verified CVID images."""
import io
from pathlib import Path
import zipfile

from experiments.scripts.spotting_colab_state import digest, read, require, sha, write_bytes_once, write_once

NAME = 'iiit-cvid-spotting-test-261014'
REGISTRY = 'experiments/registry/datasets/'
GT = 'experiments/outputs/' + NAME + '/ground-truth.jsonl'
SOURCE_SHA = 'b5b562580e250ee3336462b7699bc79d0d1149d3b8cc82f1b221a0d0ce4fb489'
FROZEN = {
    REGISTRY + NAME + '-cohort.json': '116ccd271dfc95b3bdd1190e75635eac064b49c076ab030ea6f27cf3ea3d5e18',
    REGISTRY + NAME + '-protocol.json': '884aba8bb19a8e7e20734e2fa2f9dee851e78d96417462947b4b2e8c3bf6aa3a',
    REGISTRY + NAME + '-influence.json': 'bd80635a9a085277f2d3cb1a6d74c2325544ea6201b30b476e5cda56f6fb776b',
    REGISTRY + NAME + '-selected-frame-ids.txt': '3ad969d979c800fa1209458ce9552f7a703b5f291210bdbee5b200773aa6e6a0',
    GT: '6263377fe70da58049ffe8c09b57ccca75e674e7e17b0fc6f42281501dd06771',
    'experiments/scripts/spotting_metrics.py': '56ffdf7151ea441af4814a9f675d41146343c6c88e1973a01124a4e4c8122f40',
    'experiments/scripts/cvid_test_scoring.py': '295370be23e7955a528aaa9ee0d058b38a6c30065a0567211aaa7cbfc0174bac',
}


def verify_bundle(root):
    root = Path(root).resolve()
    for name, expected in FROZEN.items():
        require(sha(root / name) == expected, 'frozen binding changed: ' + name)
    manifest = root / 'bundle-manifest.json'
    if manifest.exists():
        value = read(manifest)
        entries = value.get('files', value)
        if isinstance(entries, list):
            entries = {row['path']: row['sha256'] for row in entries}
        for name, item in entries.items():
            target = (root / name).resolve()
            require(target.is_relative_to(root), 'unsafe bundle entry')
            expected = item['sha256'] if isinstance(item, dict) else item
            require(sha(target) == expected, 'bundle file changed: ' + name)
        return sha(manifest)
    # Development runs bind every relevant source, not only imported modules.
    files = {p.relative_to(root).as_posix(): sha(p) for p in
             sorted((root / 'experiments/scripts').glob('spotting_colab*.py'))}
    files['experiments/scripts/run_spotting_colab.py'] = sha(root / 'experiments/scripts/run_spotting_colab.py')
    return digest(files)


def prepare_data(root, archive_path, work, output):
    from PIL import Image
    root, work, output = map(Path, (root, work, output))
    code = verify_bundle(root)
    require(sha(archive_path) == SOURCE_SHA, 'CVID archive SHA mismatch')
    cohort = read(root / REGISTRY / (NAME + '-cohort.json'))
    frames = [row for row in cohort['frames'] if row['selected']]
    require(len(frames) == 1754 and sum(row['object_count'] for row in frames) == 40063,
            'frozen denominator mismatch')
    preflight = []
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'duplicate ZIP members')
        # Score-independent train-only coverage: first image at each decoded size.
        first_by_size = {}
        for member in sorted(n for n in names if n.startswith('IIIT-CVid/Frames/train/') and n.endswith('.png')):
            raw = archive.read(member)
            with Image.open(io.BytesIO(raw)) as image:
                size = image.size
            if size not in first_by_size:
                first_by_size[size] = member
        require(first_by_size, 'no train images for preflight')
        selected_train = sorted(set(first_by_size.values()))
        for member in selected_train:
            ident = member.removeprefix('IIIT-CVid/')
            raw = archive.read(member)
            path = work / 'inputs' / ident
            write_bytes_once(path, raw)
            preflight.append(dict(frame_id=ident, image_sha256=__import__('hashlib').sha256(raw).hexdigest(), path=str(path.resolve())))
        for frame in frames:
            raw = archive.read(frame['archive_image_member'])
            require(__import__('hashlib').sha256(raw).hexdigest() == frame['image_sha256'], 'test image SHA mismatch')
            path = work / 'inputs' / frame['frame_id']
            write_bytes_once(path, raw)
    # Persist logical identities without ephemeral Colab filesystem paths.
    binding = dict(schema='cvid_colab_data_v1', source_sha256=SOURCE_SHA,
                   bundle_sha256=code, frozen=FROZEN, frames=frames,
                   train_preflight=[{k: v for k, v in row.items() if k != 'path'} for row in preflight],
                   train_selection='lexicographic first train image per decoded image size; no model scores or GT labels')
    write_once(output / 'prepared-data.json', binding)
    return binding


def input_rows(data, work, train=False):
    work = Path(work)
    rows = data['train_preflight'] if train else data['frames']
    result = []
    for row in rows:
        path = work / 'inputs' / row['frame_id']
        require(sha(path) == row['image_sha256'], 'materialized image changed: ' + row['frame_id'])
        result.append(dict(frame_id=row['frame_id'], image_sha256=row['image_sha256'], path=str(path.resolve())))
    return result
