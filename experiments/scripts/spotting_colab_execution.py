"""Worker-side train gate, sealed runtime identity and resumable test inference."""
from datetime import datetime, timezone
from pathlib import Path
import time
import sys

from experiments.scripts.spotting_colab_state import (
    commit_record, digest, encode, load_records, read, require, sha, validate_record, write_bytes_once, write_once,
)
from experiments.scripts.spotting_colab_train_gate import observe_train, require_matching_runtime


def native_libraries():
    """Hash mapped native bytes without process addresses or timestamps."""
    if sys.platform != 'linux':
        return {}
    paths = set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/') and '.so' in fields[5]:
            path = Path(fields[5])
            require(path.is_file(), 'mapped native library is missing or deleted: ' + str(path))
            paths.add(path.resolve())
    return {str(path): sha(path) for path in sorted(paths)}


def execute_worker_job(job, predictor, runtime):
    """Called only after the isolated worker genuinely loads its candidate."""
    candidate = job['candidate']['candidate_id']
    output = Path(job['output_root'])
    target = output / candidate
    def make_binding():
        runtime['loaded_native_sha256'] = native_libraries()
        return dict(candidate_id=candidate, run_binding=job['run_binding'],
                    runtime_sha256=digest(runtime), configuration_sha256=digest(job['candidate']),
                    prepared_sha256=digest(job['prepared']))
    if job['mode'] == 'preflight':
        observations = observe_train(job['inputs'], predictor, job.get('preflight_geometry_policy'))
        binding = make_binding()
        receipt = dict(schema='cvid_colab_preflight_v1', status='passed', binding=binding,
                       runtime=runtime, train_observations=observations,
                       no_test_inference=True, accuracy_not_evaluated=True)
        # A passed seal cannot be replaced with a different execution.
        existing = target / 'preflight.json'
        if existing.exists():
            old = read(existing)
            require_matching_runtime(target, 'preflight', old, binding, runtime,
                                     'preflight runtime identity changed; use a new output root')
            return old
        write_once(existing, receipt)
        return receipt
    require(job['mode'] in ('infer', 'verify'), 'unknown worker mode')
    gate = read(target / 'preflight.json')
    # Replay identical train inputs so lazy CUDA/native loads are part of the seal
    # before reading test pixels; no test outcomes influence this warm-up.
    train = job.get('train_inputs', [])
    require([(r['frame_id'], r['image_sha256']) for r in train] ==
            [(r['frame_id'], r['image_sha256']) for r in gate['train_observations']],
            'inference must replay the exact sealed train preflight')
    observe_train(train, predictor, job.get('preflight_geometry_policy'))
    binding = make_binding()
    require_matching_runtime(target, job['mode'], gate, binding, runtime,
                             'runtime/config differs from successful train preflight')
    if job['mode'] == 'verify':
        receipt = dict(schema='cvid_train_replay_v1', status='passed', binding=binding,
                       runtime=runtime, train_frames=len(train), no_test_inference=True)
        write_once(target/'train-replay.json', receipt)
        return receipt
    require(all(row['frame_id'].startswith('Frames/test/') for row in job['inputs']), 'test input split changed')
    write_once(target / 'run-identity.json', dict(binding=binding, runtime=runtime))
    frames = job['inputs']
    records = load_records(output, candidate, binding, frames)
    for index, frame in enumerate(frames, 1):
        require(sha(frame['path']) == frame['image_sha256'], 'test input changed')
        if frame['frame_id'] in records:
            continue
        start = time.perf_counter()
        try:
            predictions = predictor(Path(frame['path']))
            record = dict(frame_id=frame['frame_id'], status='ok', error=None, predictions=predictions)
            validate_record(record, frame['frame_id'])
        except Exception as exc:
            record = dict(frame_id=frame['frame_id'], status='error',
                          error=f'{type(exc).__name__}: {exc}', predictions=[])
        record.update(wall_seconds=time.perf_counter() - start,
                      completed_at_utc=datetime.now(timezone.utc).isoformat())
        commit_record(output, candidate, binding, frame, record)
        records[frame['frame_id']] = record
        if index % 25 == 0:
            print(f'{candidate}: {index}/{len(frames)} committed', flush=True)
    records = load_records(output, candidate, binding, frames)
    require(len(records) == len(frames), 'candidate coverage incomplete')
    aggregate = b''.join(encode(records[row['frame_id']]) for row in frames)
    prediction_path = target / 'predictions.jsonl'
    write_bytes_once(prediction_path, aggregate)
    receipt = dict(schema='cvid_colab_candidate_complete_v1', status='complete', binding=binding,
                   frames=len(records), successful_frames=sum(r['status'] == 'ok' for r in records.values()),
                   failed_frames=sum(r['status'] == 'error' for r in records.values()),
                   prediction_sha256=sha(prediction_path), frame_inference_executed=True)
    write_once(target / 'candidate-complete.json', receipt)
    return receipt
