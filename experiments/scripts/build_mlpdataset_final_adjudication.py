"""Assemble an immutable targeted review ledger from manually reviewed evidence.

Run from workspace root. Requires saved local executed-output audit artifacts.
Does not modify annotations, notebooks, extraction caches, or earlier ledgers.
"""
import copy
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from mlpdataset_final_visual_decisions import (
    EFFECT_NOTES, HARD_CUTS, MULTI_EVENT_KEYS, UNRESOLVED_WINDOWS,
)

ROOT = Path(__file__).resolve().parents[3]
REG = ROOT / 'benchmark/experiments/registry/datasets'
OUT = ROOT / 'benchmark/experiments/outputs/mlpdataset_native_executed_review_261019'
NAME = 'mlpdataset-targeted-adjudication-v2'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def binding(path):
    return {'path': path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    prior = read(REG / 'mlpdataset-sampled-adjudication-v1.json')
    queue = read(REG / 'mlpdataset-native-review-queue-v1.json')
    frames = read(OUT / 'frame-ledger.json')
    lookup = {(f['job_id'], f['frame_index']): f for f in frames}
    jobs = {j['job_id']: j for j in queue['jobs']}
    audits = {j['job_id']: j for j in read(OUT / 'job-audit.json')}
    history = read(OUT / 'historical-native-adjudication.json')
    edges = read(OUT / 'source-edge-final-observations.json')

    def frame(job, index):
        return copy.deepcopy(lookup[(f'native-{job:03}', index)])

    def base_event(e, job_id):
        job = jobs[job_id]
        return {k: copy.deepcopy(e[k]) for k in (
            'event_id', 'video_id', 'label', 'event_class', 'primary_candidate', 'original_keys')
        } | {'job_id': job_id, 'source_sha256': job['source_sha256'],
             'source_bindings': job['source_bindings'],
             'source_timestamp_origin_s': audits[job_id]['origin_s'],
             'origin_mapping_tolerance_s': 1e-8, 'video_stream_identity': '0:0',
             'endpoint_point': None, 'endpoint_bracket': None, 'last_old_frame': None, 'effect_onset': None,
             'effect_end': None, 'last_effect_frame': None, 'first_stable_new_frame': None,
             'reviewer': 'Codex manual visual review', 'reviewed_at': '2026-10-19',
             'point_scope': 'local_scaled_lossy_native_cadence_presentation_only',
             'formal_scoring_eligible': False, 'native_raw_cache_certified': False,
             'mapped_original_keys': []}

    events = []
    for old in prior['events']:
        suffix = old['event_id'].split('/')[-1]
        job_id = next(j['job_id'] for j in queue['jobs'] if old['event_id'] in j['event_ids'])
        e = base_event(old, job_id)
        if suffix in HARD_CUTS:
            job, a, b = HARD_CUTS[suffix]
            e.update(last_old_frame=frame(job, a), effect_onset=frame(job, b),
                     effect_end=frame(job, b), first_stable_new_frame=frame(job, b), transition_type='hard_cut',
                     reason='Adjacent native-cadence presentations show ' + old['label'] + '.')
            if e['primary_candidate']:
                e['endpoint_point'] = frame(job, a)
        elif suffix == 'newborn-wipe':
            e.update(last_old_frame=frame(49, 12), effect_onset=frame(49, 13),
                     last_effect_frame=frame(49, 35), effect_end=frame(49, 36),
                     first_stable_new_frame=frame(49, 36),
                     endpoint_point=frame(49, 12), transition_type='wipe', reason=EFFECT_NOTES[suffix])
        else:
            indices = {'colon-stool': (3, [6, 7, 8, 9, 21, 22]),
                       'references-presenter': (60, [10, 11, 21]),
                       'presenter-credits': (61, [12, 13, 22])}[suffix]
            e.update(transition_type='dissolve', reason=EFFECT_NOTES[suffix],
                     reviewed_presentations=[frame(indices[0], i) for i in indices[1]])
            if suffix == 'colon-stool':
                e.update(endpoint_bracket=[frame(3, 0), frame(3, 6)],
                         effect_onset_candidate_bracket=[frame(3, 0), frame(3, 6)],
                         effect_end_bracket=[frame(3, 22), frame(3, 35)],
                         last_fully_old_observed=frame(3, 0),
                         first_definitely_changed_observed=frame(3, 6),
                         stable_new_observed_by=frame(3, 35),
                         independent_reviewer='Codex final scientific reviewer',
                         supersedes_sampled_onset_bracket=True)
        e['timing_status'] = ('local_reviewed_point' if e['endpoint_point'] else
                              'not_required_auxiliary' if not e['primary_candidate'] else 'hold')
        e['confidence'] = {'semantic': 'high', 'timing': e['timing_status'],
                           'source_edition_equivalence': 'not_independently_certified'}
        events.append(e)

    for h in history['records']:
        old = {'event_id': h['video_id'] + '/historical-' + h['job_id'],
               'video_id': h['video_id'], 'label': h['event_class'],
               'event_class': h['event_class'], 'primary_candidate': True,
               'original_keys': h['original_keys']}
        e = base_event(old, h['job_id'])
        e.update(endpoint_point=h['endpoint_point'], last_old_frame=h['last_fully_old_observed'],
                 endpoint_bracket=h['endpoint_bracket'],
                 effect_onset=h['effect_onset'], effect_end=h['effect_end'],
                 first_stable_new_frame=h['first_stable_new'], confidence=h['confidence'],
                 reason=h['reason'], historical_native_review=h,
                 transition_type='hard_cut' if h['endpoint_point'] else 'effect_uncertain',
                 timing_status='local_reviewed_point' if h['endpoint_point'] else 'hold')
        events.append(e)

    policy = {k: e for e in edges['native_source_edge_records'] for k in e['original_keys']}
    policy.update({e['original_key']: e for e in edges['carried_historical_records']})
    rows = []
    for old in prior['rows']:
        r = {k: copy.deepcopy(old[k]) for k in ('key', 'video_id', 'original_row_index',
             'released_time_sec', 'annotation_sha256', 'source_sha256', 'original_source_line')}
        candidates = [e for e in events if r['key'] in e['original_keys']]
        primary = [e for e in candidates if e['primary_candidate']]
        r.update(disposition='hold', endpoint_point=None, mapped_event_id=None,
                 candidate_event_ids=[e['event_id'] for e in candidates],
                 targeted_review_complete=True, formal_scoring_eligible=False,
                 reviewer='Codex manual targeted adjudication', reviewed_at='2026-10-19')
        if r['key'] in policy:
            p = policy[r['key']]
            r.update(disposition=p['primary_disposition'], reason=p['reason'], policy_review=p,
                     event_class=p['event_class'], mapping_status='source_edge_or_historical_policy')
        elif r['key'] in UNRESOLVED_WINDOWS:
            job, reason = UNRESOLVED_WINDOWS[r['key']]
            r.update(reason=reason, job_id=f'native-{job:03}',
                     event_class=old['event_class'], mapping_status='no_primary_mapping_established')
        elif r['key'] in MULTI_EVENT_KEYS:
            r.update(reason='Multiple primary events in reviewed context; original-row assignment '
                     'is unresolved. Neither nearest timestamp nor row ordering proves a mapping.',
                     event_class='multiple_instructional_events', mapping_status='ambiguous_many_to_many')
        elif len(primary) == 1:
            e = primary[0]
            r.update(mapped_event_id=e['event_id'], reason=e['reason'],
                     event_class=e['event_class'], mapping_status='explicit_single_primary_event')
            e['mapped_original_keys'].append(r['key'])
            if e['endpoint_point']:
                r.update(disposition='included_local_review', endpoint_point=e['endpoint_point'])
        elif candidates and not primary:
            r.update(disposition='excluded_non_target', event_class='auxiliary_outro',
                     reason='Reviewed events are presenter/credits outro only; no primary replacement.',
                     mapping_status='auxiliary_only')
        else:
            raise ValueError('Unaccounted row: ' + r['key'])
        r['confidence'] = 'local_visual_decision' if r['disposition'] != 'hold' else 'unresolved'
        rows.append(r)

    supplements = [{'observation_id': 'ALRJCeVT0fQ/figure-change', 'original_key': 'ALRJCeVT0fQ:7',
                    'last_old_frame': frame(19, 81), 'first_changed_frame': frame(19, 82),
                    'semantic_status': 'figure_or_full_slide_unresolved'},
                   {'observation_id': 'ALRJCeVT0fQ/terminal-blank', 'original_key': 'ALRJCeVT0fQ:7',
                    'last_old_frame': frame(19, 129), 'first_changed_frame': frame(19, 130),
                    'semantic_status': 'terminal_blank_no_incoming_slide_observed'}]
    groups = copy.deepcopy(prior['repeated_sequence_groups'])
    for g in groups:
        g['mapping_status'] = ('resolved_many_rows_one_event_count_once'
            if g['mapping_proposal'] == 'shared_single_primary_event' else
            'resolved_auxiliary_exclusion' if not g['event_ids'] else 'hold_multiple_events')
    bindings = [binding(p) for p in [REG / 'mlpdataset-sampled-adjudication-v1.json',
        REG / 'mlpdataset-targeted-review-queue-v1.json', REG / 'mlpdataset-native-review-queue-v1.json',
        REG / 'mlpdataset-slide-transition-protocol-v1.json', OUT / 'bound-bundle.json',
        OUT / 'frame-ledger.json', OUT / 'job-audit.json', OUT / 'historical-native-adjudication.json',
        OUT / 'source-edge-final-observations.json', Path(__file__),
        Path(__file__).with_name('mlpdataset_final_visual_decisions.py'),
        ROOT / 'benchmark/experiments/notebooks/diagnostics/mlpdataset_native_review_colab.ipynb']]
    summary = {'original_rows': len(rows), 'row_dispositions': dict(Counter(r['disposition'] for r in rows)),
               'canonical_events': len(events), 'primary_events': sum(e['primary_candidate'] for e in events),
               'local_reviewed_primary_points': sum(bool(e['endpoint_point']) for e in events),
               'mapped_unique_primary_points': sum(bool(e['endpoint_point'] and e['mapped_original_keys']) for e in events)}
    sources = [{'video_id': video, 'formal_scoring_eligible': False,
                'targeted_hold_keys': [r['key'] for r in rows if r['video_id'] == video and r['disposition'] == 'hold'],
                'blocking_gates': ['whole_source_annotation_completeness_not_verified',
                                   'media_edition_and_raw_native_cache_not_independently_certified',
                                   'dependence_rights_cohort_split_freeze_pending']}
               for video in sorted({r['video_id'] for r in rows})]
    ledger = {'schema_version': 2, 'ledger_id': NAME, 'reviewed_at': '2026-10-19',
              'targeted_review_status': 'complete_with_explicit_holds', 'gt_status': 'not_frozen',
              'cohort_status': 'not_frozen', 'evaluation_ready': False, 'annotation_repairs_applied': False,
              'native_raw_cache_certified': False, 'source_wide_completeness_verified': False,
              'evidence_scope': 'Runtime-bound native cadence, scaled lossy JPEG presentations and saved logs; '
              'raw source/PNG/independent probe JSON not independently rehashed locally. Included means local '
              'targeted decision only, never formal evaluation eligibility. Seven historical cases remain coarse.',
              'bindings': bindings, 'saved_log_file_bindings': [binding(OUT / (jid + '.log')) for jid in jobs],
              'log_text_hash_rule': 'job-audit hashes original UTF-8 notebook log text; local Windows '
              'files translate LF to CRLF. Restore CRLF to LF while preserving standalone progress CR.',
              'events': events, 'rows': rows, 'source_decisions': sources,
              'repeated_sequence_groups': groups,
              'supplemental_observations_not_gt': supplements, 'summary': summary}
    (REG / (NAME + '.json')).write_text(json.dumps(ledger, indent=2) + '\n', encoding='utf-8')
    fields = ['key', 'video_id', 'original_row_index', 'released_time_sec', 'disposition',
              'mapped_event_id', 'reviewed_point_s', 'candidate_event_ids', 'reason']
    with (REG / (NAME + '.csv')).open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            flat = {k: r[k] for k in fields if k not in ('reviewed_point_s', 'candidate_event_ids')}
            flat.update(reviewed_point_s=r['endpoint_point']['source_elapsed_s'] if r['endpoint_point'] else '',
                        candidate_event_ids=';'.join(r['candidate_event_ids']))
            writer.writerow(flat)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    build()
