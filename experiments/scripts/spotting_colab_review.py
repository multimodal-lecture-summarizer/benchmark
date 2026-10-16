"""Measured result tables and explicit all-candidate admission for the T4 notebook."""
import csv
import gzip
import hashlib
import html
import json
from pathlib import Path

from experiments.scripts.spotting_colab_state import digest, read, require


def table(rows, title, columns=None):
    from IPython.display import HTML, display
    columns = columns or list(dict.fromkeys(k for row in rows for k in row))
    body = '<h3>' + html.escape(title) + '</h3><div style="max-height:550px;overflow:auto"><table border="1" cellpadding="5">'
    body += '<tr>' + ''.join('<th>' + html.escape(str(k)) + '</th>' for k in columns) + '</tr>'
    body += ''.join('<tr>' + ''.join('<td style="white-space:pre-wrap">' + html.escape(str(row.get(k, ''))) + '</td>' for k in columns) + '</tr>' for row in rows)
    display(HTML(body + '</table></div>'))
    if not rows:
        print('Zero rows; no entries omitted.')


def status_rows(output, registry):
    output = Path(output)
    rows = []
    for candidate in registry['candidates']:
        target = output / candidate['candidate_id']
        gate = read(target/'preflight.json') if (target/'preflight.json').is_file() else {}
        complete = read(target/'candidate-complete.json') if (target/'candidate-complete.json').is_file() else {}
        replay = read(target/'train-replay.json') if (target/'train-replay.json').is_file() else {}
        failures = sorted((target/'failures').glob('*.json'), key=lambda p:p.stat().st_mtime)
        last = read(failures[-1]) if failures else {}
        rows.append(dict(candidate_id=candidate['candidate_id'], required=not candidate.get('conditional',False),
                         prepared=(target/'prepared.json').is_file(), preflight=gate.get('status','pending'),
                         train_replay=replay.get('status','pending'),
                         device=gate.get('runtime',{}).get('device',''), train_frames=len(gate.get('train_observations',[])),
                         committed_frames=len(list((target/'records').rglob('*.json'))),
                         complete=complete.get('status','pending'), successful_frames=complete.get('successful_frames',''),
                         failed_frames=complete.get('failed_frames',''), latest_failure=last.get('error','')))
    return rows


def require_preflights(output, registry):
    """Do not start any test candidate until every required train gate is bound."""
    output = Path(output)
    data = read(output/'prepared-data.json')
    expected = [(r['frame_id'],r['image_sha256']) for r in data['train_preflight']]
    for candidate in registry['candidates']:
        if candidate.get('conditional',False):
            continue
        target = output/candidate['candidate_id']
        require((target/'preflight.json').is_file(), 'missing required preflight: '+candidate['candidate_id'])
        gate = read(target/'preflight.json')
        require(gate.get('status')=='passed' and gate.get('no_test_inference') is True, 'preflight not passed')
        binding = gate['binding']
        require(binding['configuration_sha256']==digest(candidate), 'preflight candidate changed')
        require(binding['runtime_sha256']==digest(gate['runtime']), 'preflight runtime changed')
        require(binding['prepared_sha256']==digest(read(target/'prepared.json')), 'prepared seal changed')
        require(binding['run_binding']==dict(data_sha256=digest(data),registry_sha256=digest(registry),bundle_sha256=data['bundle_sha256']),
                'preflight belongs to another run/cohort; qualification receipt cannot be imported')
        require([(r['frame_id'],r['image_sha256']) for r in gate['train_observations']]==expected,
                'preflight train IDs changed')
    return True


def require_train_replays(output, registry):
    """Separate-process train replay is required before the notebook's test phase."""
    require_preflights(output, registry)
    for candidate in registry['candidates']:
        if candidate.get('conditional', False):
            continue
        target = Path(output)/candidate['candidate_id']
        path = target/'train-replay.json'
        require(path.is_file(), 'missing required train replay: '+candidate['candidate_id'])
        replay, gate = read(path), read(target/'preflight.json')
        require(replay.get('status') == 'passed' and replay.get('no_test_inference') is True,
                'train replay not passed')
        require(replay['binding'] == gate['binding'] and
                digest(replay['runtime']) == replay['binding']['runtime_sha256'] and
                replay['train_frames'] == len(gate['train_observations']),
                'train replay identity changed')
    return True


def verified_exports(output):
    root = Path(output).resolve()
    summary = read(root/'analysis-summary.json')
    for entry in summary['artifacts'].values():
        path = (root/entry['path']).resolve()
        require(path.is_relative_to(root) and path.is_file(), 'unsafe/missing analysis export')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'], 'analysis export altered: '+path.name)
    return summary


def csv_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8',newline='') as stream:
        return list(csv.DictReader(stream))


def display_full_results(output):
    """All summary/stratum/failure tables, all primary frame IDs, measured plots."""
    from IPython.display import Image, display
    root = Path(output)
    summary = verified_exports(root)
    print('COMPLETE ANALYSIS:',summary['selected_frames'],'frames;',summary['selected_objects'],'GT;',len(summary['candidate_order']),'candidates')
    print('Selection:',summary['selection'],'—',summary['limits'])
    names = ['metrics.csv','macro-course-means.csv','group-metrics.csv','bootstrap.csv','failure-ledger.csv']
    for name in names:
        rows = csv_rows(root/name)
        table(rows,name+' — ALL '+str(len(rows))+' rows')
    frames = csv_rows(root/'frame-scores.csv.gz')
    primary = [r for r in frames if r['variant']=='primary']
    accounting = []
    for cid in summary['candidate_order']:
        selected = [r for r in primary if r['candidate_id']==cid]
        times = []
        require(hashlib.sha256((root/cid/'predictions.jsonl').read_bytes()).hexdigest()==summary['binding']['candidates'][cid]['predictions_sha256'],
                'native predictions no longer match analysis')
        with (root/cid/'predictions.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                record = json.loads(line)
                times.append(record['wall_seconds'])
        accounting.append(dict(candidate_id=cid,frames=len(selected),
                               invalid_predictions=sum(int(r['invalid_predictions']) for r in selected),
                               empty_transcriptions=sum(int(r['empty_transcriptions']) for r in selected),
                               frame_call_wall_seconds=sum(times),mean_frame_call_seconds=sum(times)/len(times)))
    table(accounting,'Failure/geometry/text accounting and recorded frame-call costs')
    print('Recorded call times include failures and may include warm-up; CPU/GPU costs are diagnostic, not a standardized latency benchmark. No GPU peak-memory measurement is claimed.')
    table(primary,'All primary per-frame scores / failures — '+str(len(primary))+' rows')
    print('All sensitivity frame rows:',len(frames),'retained in frame-scores.csv.gz; no frame IDs truncated in primary table.')
    texts = csv_rows(root/'all-prediction-text.csv.gz')
    counts = {cid:sum(r['candidate_id']==cid for r in texts) for cid in summary['candidate_order']}
    require(all(n==summary['selected_frames'] for n in counts.values()), 'transcription export coverage incomplete')
    table([dict(candidate_id=cid,frames=n) for cid,n in counts.items()], 'Full native transcription export coverage')
    print('Full texts/polygons:',root/'all-prediction-text.csv.gz','— inspect ANY frame in the following viewer or download this file; no text shortened.')
    table([dict(file=k,**entry) for k,entry in summary['artifacts'].items()],'Analysis export hashes and rows')
    receipt = read(root/'visualization-receipt.json')
    require(receipt['analysis_sha256']==hashlib.sha256((root/'analysis-summary.json').read_bytes()).hexdigest(), 'figure analysis identity changed')
    for entry in receipt['artifacts']:
        path = root/entry['path']
        require(hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256'], 'figure changed')
        print(entry['path'])
        display(Image(filename=str(path)))
