"""Package exact code and fixed train-only pixels for remote T4 qualification."""
import json
from pathlib import Path
import zipfile

from experiments.scripts.spotting_colab_state import read, sha

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = 'experiments/registry/datasets/iiit-cvid-spotting-colab-t4-candidates-261015-v2.json'


def build():
    data = read(ROOT / 'experiments/outputs/colab-data-validation/receipts/prepared-data.json')
    train_root = ROOT / 'experiments/outputs/colab-data-validation/work/inputs'
    files = {p.relative_to(ROOT).as_posix(): p for p in (ROOT / 'experiments/scripts').glob('*.py')}
    files[REGISTRY] = ROOT / REGISTRY
    for row in data['train_preflight']:
        path = train_root / row['frame_id']
        if not row['frame_id'].startswith('Frames/train/') or sha(path) != row['image_sha256']:
            raise ValueError('fixed train preflight pixels changed')
        files[row['frame_id']] = path
    manifest = dict(schema='joint_spotting_train_qualification_v1', registry=REGISTRY,
                    train_inputs=data['train_preflight'], test_inputs=0,
                    train_selection=data['train_selection'], files={n: sha(p) for n, p in sorted(files.items())})
    output = ROOT / 'experiments/outputs/joint-spotting-t4-qualification-261015.zip'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, name)
        archive.writestr('qualification-manifest.json', json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(dict(path=str(output), sha256=sha(output), bytes=output.stat().st_size,
                          train_frames=len(data['train_preflight']), test_frames=0), indent=2))
    return output


if __name__ == '__main__':
    build()
