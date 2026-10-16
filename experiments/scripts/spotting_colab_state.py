"""Portable immutable receipts and candidate-bound frame checkpoints."""
import hashlib
import json
import os
from pathlib import Path
import uuid


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_once(path, value):
    write_bytes_once(path, encode(value))


def write_bytes_once(path, data):
    """Publish complete bytes without replacing previous scientific evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'immutable artifact differs: ' + str(path))
        return
    temporary = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # CLI holds an exclusive run lock; rename publishes complete bytes on
        # Drive FUSE as well as local storage without exposing a partial JSON.
        require(not path.exists(), 'concurrent immutable publish')
        os.rename(temporary, path)
    except FileExistsError:
        require(path.read_bytes() == data, 'concurrent immutable artifact differs')
    finally:
        temporary.unlink(missing_ok=True)


def checkpoint_path(output, candidate_id, frame_id):
    relative = Path(frame_id + '.json')
    require(not relative.is_absolute() and '..' not in relative.parts and
            frame_id.startswith('Frames/test/'), 'unsafe frame ID')
    require(Path(candidate_id).name == candidate_id, 'unsafe candidate ID')
    return Path(output) / candidate_id / 'records' / relative


def validate_record(record, frame_id):
    require(record.get('frame_id') == frame_id, 'prediction frame mismatch')
    require(record.get('status') in ('ok', 'error') and isinstance(record.get('predictions'), list),
            'invalid prediction schema')
    if record['status'] == 'error':
        require(not record['predictions'] and isinstance(record.get('error'), str) and
                bool(record['error'].strip()), 'failure needs reason and zero retained predictions')
    else:
        require(record.get('error') is None, 'successful frame carries error')
    for item in record['predictions']:
        require(isinstance(item, dict) and isinstance(item.get('text'), str), 'malformed prediction text')
    encode(record)  # Non-finite JSON values are never persisted.


def load_records(output, candidate_id, binding, frames):
    """Reject foreign, duplicate, path-mismatched or altered checkpoints."""
    known = {frame['frame_id']: frame for frame in frames}
    records = {}
    folder = Path(output) / candidate_id / 'records'
    for path in sorted(folder.rglob('*.json')) if folder.exists() else []:
        item = read(path)
        record = item['record']
        ident = record['frame_id']
        require(ident in known and ident not in records, 'extra or duplicate checkpoint')
        require(path.resolve() == checkpoint_path(output, candidate_id, ident).resolve(), 'checkpoint path mismatch')
        require(item['binding'] == binding and item['image_sha256'] == known[ident]['image_sha256'],
                'checkpoint identity mismatch')
        require(item['record_sha256'] == digest(record), 'checkpoint payload digest mismatch')
        validate_record(record, ident)
        records[ident] = record
    return records


def commit_record(output, candidate_id, binding, frame, record):
    validate_record(record, frame['frame_id'])
    write_once(checkpoint_path(output, candidate_id, frame['frame_id']),
               dict(binding=binding, image_sha256=frame['image_sha256'],
                    record_sha256=digest(record), record=record))
