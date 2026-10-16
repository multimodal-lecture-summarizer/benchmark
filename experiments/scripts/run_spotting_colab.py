"""Colab CLI: isolated environments, train preflight, resumed test and analysis."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from experiments.scripts.spotting_colab_data import input_rows, prepare_data, verify_bundle
from experiments.scripts.spotting_colab_environments import worker_library_path
from experiments.scripts.spotting_colab_state import digest, read, require, write_once


@contextmanager
def exclusive_run(output):
    """Prevent concurrent writers; interrupted locks require explicit inspection."""
    output.mkdir(parents=True, exist_ok=True)
    path = output / '.execution.lock'
    try:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(dict(pid=os.getpid(), command=sys.argv, created_at=datetime.now(timezone.utc).isoformat()), stream)
    except FileExistsError as exc:
        raise RuntimeError('Run is locked. Inspect .execution.lock and running workers; remove only after confirming none remain.') from exc
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def invoke(root, python, module, args, log, extra_env=None):
    env = dict(os.environ, PYTHONNOUSERSITE='1', PYTHONPATH=str(root),
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    env.update(extra_env or {})
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as stream:
        result = subprocess.run([str(python), '-s', '-m', module, *map(str, args)], cwd=root,
                                env=env, stdout=stream, stderr=subprocess.STDOUT)
    require(result.returncode == 0, 'isolated process failed; inspect ' + str(log))


def worker_job(args, candidate, mode, data, registry):
    target = args.output_root / candidate['candidate_id']
    prepared = read(target / 'prepared.json')
    require(verify_bundle(args.bundle_root) == data['bundle_sha256'], 'bundle changed since data preparation')
    job = dict(mode=mode, candidate=candidate, prepared=prepared,
               preflight_geometry_policy=registry.get('preflight_geometry_policy', 'strict_valid_geometry'),
               inputs=input_rows(data, args.work_root, train=mode in ('preflight', 'verify')),
               train_inputs=input_rows(data, args.work_root, train=True),
               output_root=str(args.output_root.resolve()),
               run_binding=dict(data_sha256=digest(data), registry_sha256=digest(registry),
                                bundle_sha256=data['bundle_sha256']))
    attempt = uuid.uuid4().hex
    path = args.work_root / 'jobs' / (candidate['candidate_id'] + '-' + attempt + '.json')
    write_once(path, job)
    invoke(args.bundle_root, prepared['python'], 'experiments.scripts.spotting_colab_worker',
           ['--job', path], target / 'logs' / (mode + '-' + attempt + '.log'),
           extra_env={'LD_LIBRARY_PATH': worker_library_path(prepared)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--source-zip', type=Path)
    parser.add_argument('--candidate-registry', type=Path, help='Explicit versioned registry; old default preserved')
    parser.add_argument('command', choices=['prepare', 'preflight', 'verify', 'run', 'analyze', 'status'])
    parser.add_argument('--candidate')
    parser.add_argument('--score-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    from experiments.scripts.spotting_colab_candidates import load_registry
    registry_path = args.candidate_registry or args.bundle_root / 'experiments/registry/datasets/iiit-cvid-spotting-colab-t4-candidates-261015.json'
    registry = load_registry(registry_path)
    candidates = [c for c in registry['candidates'] if not args.candidate or c['candidate_id'] == args.candidate]
    require(candidates, 'unknown candidate')
    if args.command == 'status':
        rows = []
        for candidate in candidates:
            target = args.output_root / candidate['candidate_id']
            rows.append(dict(candidate_id=candidate['candidate_id'], prepared=(target / 'prepared.json').exists(),
                             preflight_passed=(target / 'preflight.json').exists(),
                             complete=(target / 'candidate-complete.json').exists(),
                             committed_frames=len(list((target / 'records').rglob('*.json')))))
        print(json.dumps(rows, indent=2))
        return rows
    # Internal scoring is already inside the parent process's exclusive lock.
    if args.score_worker:
        require(args.command == 'analyze', 'internal score worker requires analyze')
        from experiments.scripts.spotting_colab_analysis import score_completed
        return score_completed(args.bundle_root, args.output_root, registry)
    with exclusive_run(args.output_root):
        if args.command == 'prepare':
            source = args.source_zip or args.work_root / 'IIIT-CVid.zip'
            prepare_data(args.bundle_root, source, args.work_root, args.output_root)
            from experiments.scripts.spotting_colab_candidates import prepare_candidate
            from experiments.scripts.spotting_colab_environments import prepare_scoring_environment
            scoring = prepare_scoring_environment(args.work_root)
            write_once(args.output_root / 'scoring-environment.json', dict(python=str(scoring)))
            for candidate in candidates:
                try:
                    prepared = prepare_candidate(candidate, args.work_root)
                    write_once(args.output_root / candidate['candidate_id'] / 'prepared.json', prepared)
                except Exception as exc:
                    record_failure(args, candidate, 'prepare', exc)
                    if args.candidate:
                        raise
            return
        data = read(args.output_root / 'prepared-data.json')
        if args.command in ('preflight', 'verify', 'run'):
            failures = []
            for candidate in candidates:
                target = args.output_root / candidate['candidate_id']
                if args.command in ('verify', 'run') and not (target / 'preflight.json').exists():
                    if not candidate.get('conditional', False):
                        failures.append(candidate['candidate_id'])
                    print(candidate['candidate_id'] + ': blocked; no passed preflight', flush=True)
                    continue
                try:
                    mode = 'infer' if args.command == 'run' else args.command
                    worker_job(args, candidate, mode, data, registry)
                except Exception as exc:
                    record_failure(args, candidate, args.command, exc)
                    if not candidate.get('conditional', False):
                        failures.append(candidate['candidate_id'])
            require(not failures, 'candidate gates incomplete: ' + ', '.join(failures))
        elif args.command == 'analyze':
            scoring = read(args.output_root / 'scoring-environment.json')['python']
            arguments = ['--bundle-root', args.bundle_root, '--work-root', args.work_root,
                         '--output-root', args.output_root, '--candidate-registry', registry_path, 'analyze', '--score-worker']
            invoke(args.bundle_root, scoring, 'experiments.scripts.run_spotting_colab', arguments,
                   args.output_root / ('analysis-' + uuid.uuid4().hex + '.log'))


def record_failure(args, candidate, phase, error):
    target = args.output_root / candidate['candidate_id']
    receipt = dict(status='failed', phase=phase, candidate_id=candidate['candidate_id'],
                   error=f'{type(error).__name__}: {error}', test_eligible=False,
                   timestamp_utc=datetime.now(timezone.utc).isoformat())
    write_once(target / 'failures' / (phase + '-' + uuid.uuid4().hex + '.json'), receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
