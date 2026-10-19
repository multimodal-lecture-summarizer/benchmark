"""Verify targeted decisions against original identities and saved PTS evidence.

This checks integrity/consistency, never semantic correctness or full-source GT.
Run from workspace root after build_mlpdataset_final_adjudication.py.
"""
import csv
import hashlib
import json
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REG = ROOT / 'benchmark/experiments/registry/datasets'
OUT = ROOT / 'benchmark/experiments/outputs/mlpdataset_native_executed_review_261019'
NAME = 'mlpdataset-targeted-adjudication-v2'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify():
    ledger = read(REG / (NAME + '.json'))
    original = read(REG / 'mlpdataset-targeted-review-queue-v1.json')['cases']
    native = read(REG / 'mlpdataset-native-review-queue-v1.json')
    frames = read(OUT / 'frame-ledger.json')
    jobs = {j['job_id']: j for j in native['jobs']}
    audits = {j['job_id']: j for j in read(OUT / 'job-audit.json')}
    frame_lookup = {(f['job_id'], f['frame_index']): f for f in frames}
    hash_cache = {}

    def digest(path):
        if path not in hash_cache:
            hash_cache[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hash_cache[path]

    for b in ledger['bindings'] + ledger['saved_log_file_bindings']:
        assert digest(ROOT / b['path']) == b['sha256'], b['path']
    assert len(frames) == len(frame_lookup) == 3553
    for job_id, job in jobs.items():
        log_path = OUT / (job_id + '.log')
        # Preserve standalone CR progress characters; read_text() would change them.
        log = log_path.read_bytes().decode('utf-8').replace('\r\n', '\n')
        assert hashlib.sha256(log.encode('utf-8')).hexdigest() == audits[job_id]['log_sha256']
        assert 'Stream #0:0 -> #0:0' in log
        pts = [(int(i), int(t)) for i, t in re.findall(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)', log)]
        base = re.search(r'config in time_base:\s*(\d+/\d+)', log).group(1)
        sequence = [f for f in frames if f['job_id'] == job_id]
        assert len(sequence) == len(pts) == audits[job_id]['frames']
        previous = None
        for f, (index, ticks) in zip(sequence, pts):
            assert (f['frame_index'], f['source_pts_ticks'], f['source_time_base']) == (index, ticks, base)
            elapsed = ticks * Fraction(base) - audits[job_id]['origin_s']
            assert abs(float(elapsed) - f['source_elapsed_s']) < 1e-8
            assert job['start_s'] - 1e-8 <= float(elapsed) < job['end_s'] + 1e-8
            assert previous is None or ticks > previous
            previous = ticks
            assert digest(ROOT / f['presentation_jpeg_path']) == f['presentation_jpeg_sha256']

    def check_nested(obj):
        if isinstance(obj, dict):
            if 'presentation_jpeg_path' in obj:
                assert obj == frame_lookup[(obj['job_id'], obj['frame_index'])]
            for value in obj.values():
                check_nested(value)
        elif isinstance(obj, list):
            for value in obj:
                check_nested(value)

    check_nested(ledger)
    rows = ledger['rows']
    row_map = {r['key']: r for r in rows}
    assert len(rows) == len(row_map) == len(original) == 82
    for case in original:
        key = f"{case['video_id']}:{case['annotation_index']}"
        r = row_map[key]
        for dest, source in [('video_id', 'video_id'), ('original_row_index', 'annotation_index'),
                             ('released_time_sec', 'annotation_s'), ('annotation_sha256', 'annotation_sha256'),
                             ('source_sha256', 'source_sha256'), ('original_source_line', 'original_source_line')]:
            assert r[dest] == case[source], (key, dest)
        assert r['targeted_review_complete'] and not r['formal_scoring_eligible']
        assert r['reason'] and r['confidence'] and r['reviewer']
        if r['disposition'] == 'included_local_review':
            assert r['endpoint_point'] and r['mapped_event_id']
        else:
            assert r['endpoint_point'] is None
        if case['annotation_s'] > case['duration_s']:
            assert r['disposition'] == 'hold', key
        if case['annotation_s'] == 0:
            assert r['disposition'] == 'excluded_non_target', key
    assert sum(c['annotation_s'] > c['duration_s'] for c in original) == 18
    assert sum(c['annotation_s'] == 0 for c in original) == 4
    events = {e['event_id']: e for e in ledger['events']}
    assert len(events) == len(ledger['events']) == 43
    for e in events.values():
        job = jobs[e['job_id']]
        assert e['video_id'] == job['video_id'] and e['source_sha256'] == job['source_sha256']
        assert set(e['original_keys']) <= set(job['original_keys'])
        for key in e['original_keys']:
            assert e['event_id'] in row_map[key]['candidate_event_ids']
            assert row_map[key]['source_sha256'] == e['source_sha256']
        for key in e['mapped_original_keys']:
            assert row_map[key]['mapped_event_id'] == e['event_id']
        if e['endpoint_point']:
            assert e['primary_candidate'] and e['endpoint_point'] == e['last_old_frame']
            assert e['effect_onset']['frame_index'] == e['last_old_frame']['frame_index'] + 1
            assert e['effect_end'] == e['first_stable_new_frame']
            assert e['effect_onset']['source_pts_ticks'] <= e['effect_end']['source_pts_ticks']
    for r in rows:
        for eid in r['candidate_event_ids']:
            assert r['key'] in events[eid]['original_keys']
        if r['mapped_event_id']:
            e = events[r['mapped_event_id']]
            assert r['key'] in e['mapped_original_keys']
            assert r['endpoint_point'] == e['endpoint_point']
    assert Counter(r['disposition'] for r in rows) == {
        'included_local_review': 40, 'excluded_non_target': 11, 'hold': 31}
    assert len([e for e in events.values() if e['endpoint_point']]) == 35
    assert len([e for e in events.values() if e['endpoint_point'] and e['mapped_original_keys']]) == 28
    assert len(ledger['source_decisions']) == len({r['video_id'] for r in rows}) == 42
    assert all(not s['formal_scoring_eligible'] for s in ledger['source_decisions'])
    assert not any(ledger[k] for k in ('evaluation_ready', 'annotation_repairs_applied',
                                     'native_raw_cache_certified', 'source_wide_completeness_verified'))
    with (REG / (NAME + '.csv')).open(encoding='utf-8-sig', newline='') as handle:
        flat = list(csv.DictReader(handle))
    assert [r['key'] for r in flat] == [r['key'] for r in rows]
    for r, f in zip(rows, flat):
        assert f['disposition'] == r['disposition']
        assert f['reason'] == r['reason']
        assert f['mapped_event_id'] == (r['mapped_event_id'] or '')
        assert f['candidate_event_ids'].split(';') == r['candidate_event_ids'] or not f['candidate_event_ids']
    result = {'status': 'pass', 'scope': 'integrity_not_semantic_or_formal_GT_certification',
              'verified_rows': 82, 'verified_native_frames': len(frames), 'verified_logs': len(jobs),
              'unique_files_hashed': len(hash_cache), 'summary': ledger['summary'],
              'ledger_sha256': digest(REG / (NAME + '.json')),
              'csv_sha256': digest(REG / (NAME + '.csv'))}
    (OUT / 'final-adjudication-validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    verify()
