"""Actual isolated train-only joint-spotter qualification on a Colab T4."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import uuid

from experiments.scripts.spotting_colab_candidates import load_registry, prepare_candidate
from experiments.scripts.spotting_colab_environments import worker_library_path
from experiments.scripts.spotting_colab_state import digest, read, require, sha, write_once


def qualify(root, work, output):
    root, work, output = map(Path, (root, work, output))
    manifest = read(root / 'qualification-manifest.json')
    for name, wanted in manifest['files'].items():
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()) and sha(path) == wanted, 'qualification package altered: ' + name)
    inputs = []
    for row in manifest['train_inputs']:
        require(row['frame_id'].startswith('Frames/train/'), 'qualification must not include test inputs')
        path = root / row['frame_id']
        require(sha(path) == row['image_sha256'], 'qualification train image altered')
        inputs.append(dict(row, path=str(path.resolve())))
    registry = load_registry(root / manifest['registry'])
    candidate = next(c for c in registry['candidates'] if c['adapter'] == 'pgnet')
    output.mkdir(parents=True, exist_ok=True)
    prepared = prepare_candidate(candidate, work)
    write_once(output / candidate['candidate_id'] / 'prepared.json', prepared)
    job = dict(mode='preflight', candidate=candidate, prepared=prepared, inputs=inputs,
               preflight_geometry_policy=registry.get('preflight_geometry_policy', 'strict_valid_geometry'),
               output_root=str(output.resolve()), run_binding=dict(
                   qualification_manifest_sha256=sha(root / 'qualification-manifest.json'),
                   registry_sha256=digest(registry), purpose='train_only_T4_qualification_no_test_inference'))
    path = work / ('qualification-job-' + uuid.uuid4().hex + '.json')
    write_once(path, job)
    env = dict(os.environ, PYTHONPATH=str(root.resolve()), PYTHONNOUSERSITE='1',
               LD_LIBRARY_PATH=worker_library_path(prepared),
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    subprocess.run([prepared['python'], '-s', '-m', 'experiments.scripts.spotting_colab_worker',
                    '--job', str(path)], cwd=root, env=env, check=True)
    receipt = read(output / candidate['candidate_id'] / 'preflight.json')
    print('QUALIFICATION PASSED: ' + candidate['candidate_id'], flush=True)
    print('Train frames: ' + str(len(receipt['train_observations'])), flush=True)
    print('No test inference or GT-based accuracy selection.', flush=True)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    qualify(args.root, args.work, args.output)
