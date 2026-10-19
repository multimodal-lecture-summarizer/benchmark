"""Atomic node records for technical capacity runs; actual store must be probed."""
import hashlib
import json
from pathlib import Path
import os
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def commit(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({'payload':payload,'sha256':digest(payload)},sort_keys=True).encode()
    temporary = path.with_suffix(path.suffix+'.partial')
    with temporary.open('wb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary,path)
    return restore(path)


def restore(path):
    envelope = json.loads(Path(path).read_text(encoding='utf-8'))
    if digest(envelope['payload']) != envelope['sha256']:
        raise ValueError('Checkpoint hash mismatch')
    return envelope['payload']


def probe_store(root):
    root = Path(root)
    path = root / ('store-probe-'+str(time.time_ns())+'.json')
    payload = {'nonce':str(time.time_ns()),'scope':'mounted path write/fsync/rename/readback; not cross-session survival'}
    assert commit(path,payload) == payload and restore(path) == payload
    return {'write_readback_verified':True,'restore_verified':True,'cross_session_survival_verified':False,
            'probe_file':str(path),'probe_payload_sha256':digest(payload)}


class NodeCheckpointGenerator:
    def __init__(self, backend, root, identity, deadline, before_call=None):
        self.backend, self.root = backend, Path(root)
        self.identity, self.deadline = identity, deadline
        self.before_call = before_call
        self.context = None
        self.events = []

    def set_node_context(self, context):
        self.context = context

    def __call__(self, batch, maximum, stage):
        if self.context is None:
            raise ValueError('Missing node layer/index context')
        key = {**self.identity,**self.context,'stage':stage,'max_new_tokens':maximum,
               'wrapped_input_sha256':digest(batch['input_ids'])}
        path = self.root / (digest(key)+'.json')
        if path.exists():
            payload = restore(path)
            if payload['key'] != key:
                raise ValueError('Checkpoint identity mismatch')
            self.events.append({'status':'reused','key_sha256':digest(key),'new_attempt_wall_seconds':0,
                                'original_wall_seconds':payload['wall_seconds'],
                                'backend_receipt':payload.get('backend_receipt')})
            return payload['output']
        if time.monotonic() >= self.deadline:
            self.events.append({'status':'deadline_before_call','key_sha256':digest(key),
                                'new_attempt_wall_seconds':0,'backend_receipt':None,
                                'generation_started':False})
            raise TimeoutError('Session deadline before node generation')
        if self.before_call:
            self.before_call(key)
        attempt_path=self.root/'attempts'/('attempt-'+str(time.time_ns())+'.json')
        attempt={'key':key,'status':'started','wall_seconds':None}
        commit(attempt_path,attempt)
        started = time.perf_counter()
        try:
            output = self.backend(batch,maximum,stage)
        except Exception as error:
            attempt.update(status='failed',wall_seconds=time.perf_counter()-started,
                           error=f'{type(error).__name__}: {error}',
                           backend_receipt=getattr(self.backend,'last_receipt',None))
            self._append_failed_event(key, attempt)
            commit(attempt_path,attempt)
            raise
        elapsed = time.perf_counter()-started
        if time.monotonic() >= self.deadline:
            attempt.update(status='deadline_hit',wall_seconds=elapsed,
                           backend_receipt=getattr(self.backend,'last_receipt',None))
            self._append_failed_event(key, attempt)
            commit(attempt_path,attempt)
            raise TimeoutError('Session deadline reached during node')
        if not output.strip():
            attempt.update(status='failed_empty_output',wall_seconds=elapsed,
                           backend_receipt=getattr(self.backend,'last_receipt',None))
            self._append_failed_event(key, attempt)
            commit(attempt_path,attempt)
            raise ValueError('Empty node output')
        native = getattr(self.backend,'last_receipt',None)
        payload = {'key':key,'output':output,'wall_seconds':elapsed,'backend_receipt':native}
        commit(path,payload)
        attempt.update(status='completed',wall_seconds=elapsed,checkpoint=str(path))
        commit(attempt_path,attempt)
        self.events.append({'status':'completed','key_sha256':digest(key),'new_attempt_wall_seconds':elapsed,
                            'backend_receipt':native})
        return output

    def _append_failed_event(self, key, attempt):
        """Keep spent failed-call time visible even when no output node commits."""
        event = {'status':attempt['status'],'key_sha256':digest(key),
                 'new_attempt_wall_seconds':attempt['wall_seconds'],
                 'backend_receipt':attempt.get('backend_receipt'),
                 'generation_started':True}
        if 'error' in attempt:
            event['error'] = attempt['error']
        self.events.append(event)
