"""Evaluation-only amended semantic scoring; original generation evidence is read-only."""
import copy
import hashlib
import json
import math
import time
from pathlib import Path

from experiments.scripts.rq2_tib_benchmark import _save_result
from experiments.scripts.rq2_tib_benchmark_results import score_pair, validate_semantic_scores
from experiments.scripts.rq2_tib_frozen_analysis import seal, verify, summarize_frozen
from experiments.scripts.rq2_tib_frozen_runtime import _validate_receipt
from experiments.scripts.rq2_tib_pilot_runtime import digest


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_origin(origin_dir, bundle, manifest=None, protocol=None):
    """Require all 240 summaries and independently recompute unchanged ROUGE."""
    origin = Path(origin_dir)
    receipt = json.loads((origin / 'frozen-receipt.json').read_text(encoding='utf-8'))
    _validate_receipt(receipt, bundle)
    for expected, name in ((manifest, 'manifest'), (protocol, 'protocol')):
        if expected is not None and expected != receipt[name]:
            raise ValueError(f'Original {name} differs from supplied frozen document')
    log = origin / 'dispatches.jsonl'
    if not log.is_file():
        raise ValueError('Original dispatch ledger missing')
    dispatches = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    if dispatches != receipt['dispatches'] or not dispatches:
        raise ValueError('Original dispatch ledger mismatch or empty')
    items = {f"{r['split']}/{r['source_index']}": r for r in bundle['items']}
    attempted = {(d['id'], d['arm']) for d in dispatches}
    if any(d['id'] not in items or d['arm'] not in ('S1', 'S3') for d in dispatches):
        raise ValueError('Unknown dispatch identity')
    for row in receipt['rows']:
        item = items[row['id']]
        expected_source = hashlib.sha256(' '.join(item['source_text'].split()).encode()).hexdigest()
        if row.get('generation_source_sha256') != expected_source:
            raise ValueError('Original generation source checksum mismatch')
        if set(row['arms']) != {'S1', 'S3'}:
            raise ValueError('Original generation must contain both arms')
        for arm in ('S1', 'S3'):
            value = row['arms'][arm]
            if (value.get('status') != 'completed' or not isinstance(value.get('summary'), str)
                    or not value['summary'].strip() or (row['id'], arm) not in attempted):
                raise ValueError('All 240 original summaries must be completed and dispatched')
            ledger = [d for d in dispatches if (d['id'], d['arm']) == (row['id'], arm)]
            if any(d.get('output_tokens') is None or d.get('status') != 'returned' for d in ledger):
                raise ValueError('Original dispatch usage incomplete')
            for field in ('prompt_tokens', 'output_tokens'):
                if sum(sum(d[field]) for d in ledger) != value.get(field):
                    raise ValueError('Original arm and dispatch usage mismatch')
        scores = score_pair(row['arms'], item['reference_text'])
        if row.get('scores') != scores:
            raise ValueError('Original ROUGE consistency mismatch')
    return receipt


def _code_identity():
    folder = Path(__file__).parent
    return {name: _sha(folder / (name + '.py')) for name in
            ('rq2_tib_rescore_runtime', 'rq2_tib_semantic_v2')}


def _identity(origin_dir, origin, bundle, scorer, device):
    metadata = scorer.metadata
    if metadata.get('test_adapters') is not False or metadata.get('version') != 'tib_semantic_v2':
        raise ValueError('Amended semantic scorer required; test adapters forbidden')
    from experiments.scripts.rq2_tib_semantic_v2 import SemanticScorerV2
    if metadata != SemanticScorerV2(device=device, batch_size=metadata.get('batch_size', 16)).metadata:
        raise ValueError('Amended semantic model/scoring identity mismatch')
    if device not in ('cpu', 'cuda', 'cuda:0'):
        raise ValueError('Declare CPU or CUDA scoring device')
    return {'origin_file_sha256': _sha(Path(origin_dir) / 'frozen-receipt.json'),
            'origin_receipt_sha256': origin['receipt_sha256'],
            'origin_dispatch_sha256': _sha(Path(origin_dir) / 'dispatches.jsonl'),
            'bundle_sha256': digest(bundle), 'generation_protocol_sha256': origin['protocol']['protocol_sha256'],
            'scorer': metadata, 'device': device, 'code_sha256': _code_identity(),
            'amendment': 'token_id_windows_v2_all120_semantic_recomputed_original_generation_unchanged'}


def _write(receipt, directory):
    receipt['counts'] = {'selected': len(receipt['rows']), **{
        name: sum(row['status'] == name for row in receipt['rows'])
        for name in ('completed', 'evaluation_failed', 'interrupted', 'not_attempted', 'in_progress')}}
    sealed = seal(receipt)
    _save_result(sealed, directory / 'rescore-receipt.json')
    return sealed


def run_rescore(origin_dir, bundle, scorer, output_dir, *, device,
                metric_initialization_seconds=0, retry_failed=False, on_event=None):
    """Resume only this amended scorer, retaining each failed/interrupted attempt."""
    if not math.isfinite(metric_initialization_seconds) or metric_initialization_seconds < 0:
        raise ValueError('Initialization seconds must be finite and nonnegative')
    if type(retry_failed) is not bool:
        raise ValueError('retry_failed must be explicit boolean')
    directory, origin_path = Path(output_dir).resolve(), Path(origin_dir).resolve()
    if directory == origin_path or directory in origin_path.parents or origin_path in directory.parents:
        raise ValueError('Rescore output must be separate from original run')
    origin = validate_origin(origin_path, bundle)
    identity = _identity(origin_path, origin, bundle, scorer, device)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.rescore.lock'
    # An abrupt kernel loss leaves this marker intentionally. Recovery requires
    # confirming the old process stopped before manually removing the marker.
    with lock.open('x', encoding='utf-8') as stream:
        stream.write('Exclusive evaluation-only session; remove only after old process stops.\n')
    original_event = getattr(scorer, 'on_event', None)
    try:
        path = directory / 'rescore-receipt.json'
        receipt = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
            'format': 'rq2-tib-semantic-rescore-v2', 'identity': identity,
            'origin': copy.deepcopy(origin), 'rows': [
                {'id': r['id'], 'status': 'not_attempted', 'attempts': []} for r in origin['rows']],
            'sessions': []}
        if path.exists():
            verify(receipt)
            if receipt['identity'] != identity or receipt['origin'] != origin:
                raise ValueError('Rescore identity changed; use a NEW output directory')
            if [r['id'] for r in receipt['rows']] != [r['id'] for r in origin['rows']]:
                raise ValueError('Rescore denominator/order mismatch')
            for row in receipt['rows']:
                if row['status'] not in ('completed', 'evaluation_failed', 'interrupted', 'not_attempted', 'in_progress'):
                    raise ValueError('Unknown rescore status')
                if row['status'] == 'completed':
                    validate_semantic_scores(row['semantic_scores'])
                if row['status'] != 'not_attempted' and not row.get('attempts'):
                    raise ValueError('Rescore attempt history missing')
        session = {'initialization_seconds': metric_initialization_seconds,
                   'retry_failed': retry_failed, 'device': device, 'scoring_seconds': None}
        receipt['sessions'].append(session)
        items = {f"{r['split']}/{r['source_index']}": r for r in bundle['items']}
        originals = {r['id']: r for r in origin['rows']}
        started = time.perf_counter()
        _write(receipt, directory)
        for row in receipt['rows']:
            if row['status'] == 'in_progress':
                row['attempts'][-1].update(status='interrupted', error='unclean_process_interruption', seconds=None)
                row['status'] = 'interrupted'
            if row['status'] == 'completed' or (row['status'] == 'evaluation_failed' and not retry_failed):
                continue
            row.pop('semantic_scores', None)
            row.pop('error', None)
            attempt = {'status': 'in_progress', 'seconds': None, 'session_index': len(receipt['sessions']) - 1}
            row['attempts'].append(attempt)
            row['status'] = 'in_progress'
            _write(receipt, directory)
            item, tick = items[row['id']], time.perf_counter()
            interrupted = False
            try:
                if hasattr(scorer, 'on_event'):
                    scorer.on_event = (lambda event, item_id=row['id']: on_event({**event, 'id': item_id})) if on_event else None
                row['semantic_scores'] = validate_semantic_scores(scorer.score_pair(
                    copy.deepcopy(originals[row['id']]['arms']), item['reference_text'], item['source_text']))
                row['status'] = 'completed'
            except (Exception, KeyboardInterrupt) as exc:
                interrupted = isinstance(exc, KeyboardInterrupt)
                row['status'] = 'interrupted' if interrupted else 'evaluation_failed'
                attempt['error'] = f'{type(exc).__name__}: {exc}'
                row['error'] = attempt['error']
            attempt.update(status=row['status'], seconds=time.perf_counter() - tick)
            _write(receipt, directory)
            if on_event:
                on_event({'stage': 'rescore', 'id': row['id'], 'status': row['status']})
            if interrupted:
                break
        session['scoring_seconds'] = time.perf_counter() - started
        # Detect concurrent external edits to origin before publishing completion.
        if _sha(origin_path / 'frozen-receipt.json') != identity['origin_file_sha256']:
            raise ValueError('Original receipt changed during rescore')
        if _sha(origin_path / 'dispatches.jsonl') != identity['origin_dispatch_sha256']:
            raise ValueError('Original dispatch ledger changed during rescore')
        return _write(receipt, directory)
    finally:
        if hasattr(scorer, 'on_event'):
            scorer.on_event = original_event
        lock.unlink(missing_ok=True)


def summarize_rescore(receipt):
    """Reuse descriptive aggregation on an explicitly labelled amended projection."""
    verify(receipt)
    origin = receipt['origin']
    verify(origin)
    projection = copy.deepcopy(origin)
    if len(projection['rows']) != len(receipt['rows']):
        raise ValueError('Rescore analysis denominator mismatch')
    for row, amended in zip(projection['rows'], receipt['rows']):
        if row['id'] != amended['id']:
            raise ValueError('Rescore analysis denominator/order mismatch')
        row.pop('semantic_scores', None)
        row['status'] = amended['status']
        if amended['status'] == 'completed':
            row['semantic_scores'] = validate_semantic_scores(amended['semantic_scores'])
    projection['counts'] = receipt['counts']
    summary = summarize_frozen(seal(projection), origin['manifest'], origin['protocol'])
    summary['scoring_amendment'] = receipt['identity']
    summary['semantic_protocol_status'] = 'amended_v2_not_original_frozen_semantic_implementation'
    summary['original_generation_sessions'] = origin['sessions']
    summary['rescore_sessions'] = receipt['sessions']
    attempts = [a for row in receipt['rows'] for a in row['attempts']]
    summary['rescore_resources'] = {'attempts': len(attempts),
        'known_scoring_seconds': sum(a['seconds'] for a in attempts if a['seconds'] is not None),
        'unknown_duration_attempts': sum(a['seconds'] is None for a in attempts)}
    summary['rescore_cost'] = summary['rescore_resources']
    summary['rescore_receipt_sha256'] = receipt['receipt_sha256']
    return summary
