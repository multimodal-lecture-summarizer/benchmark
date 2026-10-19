"""Bind manually authored sampled observations; never infer or repair native GT."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / 'benchmark/experiments/registry/datasets'
OUTPUT = ROOT / 'benchmark/experiments/outputs/mlpdataset_targeted_review_executed_261019'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def verify_observation(observation, receipt_sha256, expected_receipt_sha256, result_keys, results):
    """Fail closed before applying a human observation to a saved frame sequence."""
    if receipt_sha256 != expected_receipt_sha256:
        raise ValueError('Reviewed receipt SHA256 changed')
    key = observation['case_key']
    if result_keys[observation['case_number']-1] != key:
        raise ValueError('Reviewed case order changed')
    result = results[key]
    binding = result['binding']['case']
    signature = [(f['source_pts_ticks'], f['sha256']) for f in result['frames']]
    fingerprint = hashlib.sha256(json.dumps(signature, separators=(',', ':')).encode()).hexdigest()
    if (binding['source_sha256'] != observation['source_sha256'] or
            binding['annotation_s'] != observation['annotation_s'] or
            fingerprint != observation['sampled_sequence_sha256']):
        raise ValueError('Reviewed source, mark or frame sequence changed')
    return key


def build():
    queue_path = REGISTRY / 'mlpdataset-targeted-review-queue-v1.json'
    protocol_path = REGISTRY / 'mlpdataset-slide-transition-protocol-v1.json'
    observation_path = REGISTRY / 'mlpdataset-sampled-observations-v1.json'
    receipt_path = OUTPUT / 'review-receipt.json'
    queue, receipt, manual = [json.loads(p.read_text(encoding='utf-8')) for p in
                              (queue_path, receipt_path, observation_path)]
    assert receipt['queue_sha256'] == digest(queue_path)
    assert receipt['protocol_sha256'] == digest(protocol_path)
    if manual['receipt_sha256'] != digest(receipt_path):
        raise ValueError('Manual observations reference a different receipt')
    cases = {f"{c['video_id']}:{c['annotation_index']}": c for c in queue['cases']}
    results = receipt['results']
    signatures = defaultdict(list)
    for key, result in results.items():
        signatures[tuple((f['source_pts_ticks'], f['sha256']) for f in result['frames'])].append(key)
    reviewed = {o['case_number']: o for o in manual['observations']}
    rows, events, requests, repeats = {}, {}, [], []
    result_keys = list(results)
    for number, observation in reviewed.items():
        key = verify_observation(observation, digest(receipt_path), manual['receipt_sha256'], result_keys, results)
        result, case = results[key], cases[key]
        signature = tuple((f['source_pts_ticks'], f['sha256']) for f in result['frames'])
        original_keys = signatures.pop(signature)
        evidence = [dict(path=receipt_path.relative_to(ROOT).as_posix(), sha256=digest(receipt_path)),
                    dict(path=(OUTPUT / f'case-{number:02d}.jpg').relative_to(ROOT).as_posix(),
                         sha256=digest(OUTPUT / f'case-{number:02d}.jpg'), presentation_only=True)]
        if len(original_keys) > 1:
            primary = [case['video_id']+'/'+x['event_id'] for x in observation['changes'] if x['primary_candidate']]
            repeats.append(dict(original_keys=original_keys, event_ids=primary,
                mapping_proposal='multiple_events_unresolved' if len(primary)>1 else
                    'shared_single_primary_event' if primary else 'auxiliary_only_no_primary_event',
                mapping_status='proposal_only_no_original_row_deleted'))
        for change in observation['changes']:
            frames = result['frames']
            old, different, stable = [frames[change[k]] for k in ('last_old_sample_index',
                                       'first_different_sample_index', 'first_stable_new_sample_index')]
            assert old['source_elapsed_s'] < different['source_elapsed_s'] <= stable['source_elapsed_s']
            event_id = case['video_id'] + '/' + change['event_id']
            event = events.setdefault(event_id, dict(event_id=event_id, video_id=case['video_id'],
                label=change['label'], event_class=change['event_class'], primary_candidate=change['primary_candidate'],
                original_keys=[], observations=[], native_endpoint_s=None, effect_onset_s=None,
                effect_end_s=None, disposition='hold', native_evidence_status='pending'))
            event['original_keys'] = sorted(set(event['original_keys'] + original_keys))
            event['observations'].append(dict(case_key=key, last_old_sample=old,
                first_different_sample=different, first_stable_new_sample=stable, evidence=evidence))
        for original in original_keys:
            c = cases[original]
            rows[original] = dict(key=original, video_id=c['video_id'], original_row_index=c['annotation_index'],
                released_time_sec=c['annotation_s'], annotation_sha256=c['annotation_sha256'],
                source_sha256=c['source_sha256'], event_class=observation['observation_type'],
                reason=observation['summary'], semantic_review_status='sampled_window_reviewed',
                proposed_disposition='excluded_non_target' if number == 47 else
                    'hold' if not observation['changes'] else 'included_after_native_and_mapping_qualification',
                disposition='hold', native_endpoint_s=None,
                candidate_event_ids=[c['video_id']+'/'+x['event_id'] for x in observation['changes']],
                mapping_status='proposed_not_frozen', evidence=evidence)
        if not observation['changes']:
            anchor = min(case['annotation_s'], case['duration_s'])
            requests.append(dict(case=case, start_s=max(0, anchor-.4), end_s=min(case['duration_s'], anchor+.4),
                reason=observation['observation_type'], event_ids=[], original_keys=original_keys, evidence=evidence))
    assert not signatures, 'Every distinct sequence must have an explicit manual observation'
    for event in events.values():
        old = max(o['last_old_sample']['source_elapsed_s'] for o in event['observations'])
        different = min(o['first_different_sample']['source_elapsed_s'] for o in event['observations'])
        stable = min(o['first_stable_new_sample']['source_elapsed_s'] for o in event['observations'])
        assert old < different <= stable
        event['sampled_onset_bracket_s'] = [old, different]
        event['sampled_stable_new_upper_s'] = stable
        case = cases[event['original_keys'][0]]
        requests.append(dict(case=case, start_s=max(0, old-.3), end_s=min(case['duration_s'], stable+.3),
            reason=event['event_class'], event_ids=[event['event_id']], original_keys=event['original_keys'],
            evidence=[e for o in event['observations'] for e in o['evidence']]))
    for key, case in cases.items():
        if key in rows:
            continue
        historical = case.get('historical_evidence')
        label = historical['event_observation'] if historical else case['review_action']
        target = bool(historical and label.startswith('instructional_slide') and 'end_card' not in label)
        blank = label == 'content_to_blank_unresolved'
        evidence = [dict(path=queue_path.relative_to(ROOT).as_posix(), sha256=digest(queue_path))]
        if historical:
            evidence.append(dict(path=historical['clip_local_path'], sha256=historical['clip_sha256']))
        rows[key] = dict(key=key, video_id=case['video_id'], original_row_index=case['annotation_index'],
            released_time_sec=case['annotation_s'], annotation_sha256=case['annotation_sha256'],
            source_sha256=case['source_sha256'], event_class=label,
            semantic_review_status='historical_coarse_only' if historical else 'policy_context_pending',
            proposed_disposition='included_after_native_and_mapping_qualification' if target else 'hold' if
                (blank or not historical or label=='source_end_context_no_new_slide') else 'excluded_non_target',
            disposition='hold', native_endpoint_s=None, candidate_event_ids=[],
            mapping_status='not_frozen', reason='Retained context; no native endpoint certification', evidence=evidence)
        if target or blank:
            w = historical['measured_window']
            requests.append(dict(case=case, start_s=w['effective_start_s'],
                end_s=min(case['duration_s'], w['effective_end_s']+(7 if blank else 0)),
                reason='historical_unresolved_blank_extension' if blank else 'historical_native_endpoint',
                event_ids=[], original_keys=[key], evidence=evidence))
        elif not historical:
            anchor = min(case['annotation_s'], case['duration_s'])
            requests.append(dict(case=case, start_s=max(0,anchor-.8), end_s=min(case['duration_s'],anchor+.8),
                reason='source_edge_policy_context_not_edition_equivalence', event_ids=[], original_keys=[key], evidence=evidence))
    ledger = dict(schema_version=1, ledger_id='mlpdataset-sampled-adjudication-v1',
        reviewed_at=manual['reviewed_at'], reviewer='Codex visual diagnostic review',
        protocol_id=queue['protocol_id'],
        protocol_sha256=digest(protocol_path), original_queue_sha256=digest(queue_path),
        observations_sha256=digest(observation_path), receipt_sha256=digest(receipt_path),
        predecessor_sha256=None, gt_status='pending', cohort_status='pending', evaluation_ready=False,
        annotation_repairs_applied=0, native_certified_events=0, events=list(events.values()),
        repeated_sequence_groups=repeats, rows=[rows[k] for k in cases],
        summary=dict(original_rows=len(rows), sampled_rows=len(results), distinct_sequences=len(reviewed),
                     sampled_events=len(events), primary_candidate_events=sum(e['primary_candidate'] for e in events.values()),
                     repeated_groups=len(repeats), repeated_mapping_proposals=dict(Counter(g['mapping_proposal'] for g in repeats)),
                     proposed_dispositions=dict(Counter(x['proposed_disposition'] for x in rows.values()))))
    for key,row in rows.items():
        row['original_source_line']=cases[key]['original_source_line']
        row['confidence']='diagnostic_only_not_native_adjudication'
        row['pts_time_base_and_origin']=results[key]['timing'] if key in results else None
        row['effect_fields']=dict(last_old_frame=None,effect_onset=None,effect_end=None,first_stable_new_frame=None)
    ledger_path = REGISTRY / 'mlpdataset-sampled-adjudication-v1.json'
    save(ledger_path, ledger)
    # Merge only overlapping decode windows within one source; never merge event identities.
    jobs = []
    for req in sorted(requests, key=lambda x:(x['case']['video_id'], x['start_s'])):
        if jobs and jobs[-1]['video_id']==req['case']['video_id'] and req['start_s']<=jobs[-1]['end_s']:
            j=jobs[-1]; j['end_s']=max(j['end_s'],req['end_s'])
            for k in ('event_ids','original_keys'): j[k]=sorted(set(j[k]+req[k]))
            j['evidence'].extend(req['evidence']); j['reason']+=';'+req['reason']
        else:
            c=req['case']; jobs.append(dict(**{k:c[k] for k in ('video_id','source_sha256','source_relative_path','duration_s')},
                **{k:req[k] for k in ('start_s','end_s','reason','event_ids','original_keys','evidence')}))
    for i,j in enumerate(jobs,1):
        j['job_id']=f'native-{i:03d}'
        j['source_bindings']=[{k:cases[key][k] for k in ('annotation_index','annotation_s','annotation_sha256','original_source_line')} for key in j['original_keys']]
        assert 0 <= j['start_s'] < j['end_s'] <= j['duration_s']
    native = dict(schema_version=1, queue_id='mlpdataset-native-review-v1', drive_run_name=queue['drive_run_name'],
        protocol_id=queue['protocol_id'], protocol_sha256=digest(protocol_path), review_ledger_sha256=digest(ledger_path),
        original_queue_sha256=digest(queue_path), original_queue=queue, jobs=jobs,
        evaluation_ready=False, native_certified_events=0,
        summary=dict(jobs=len(jobs), videos=len({j['video_id'] for j in jobs}),
                     requested_decoded_seconds=sum(j['end_s']-j['start_s'] for j in jobs), original_rows=82))
    save(REGISTRY/'mlpdataset-native-review-queue-v1.json',native)
    print(json.dumps(dict(ledger=ledger['summary'],native=native['summary']),indent=2))


if __name__ == '__main__':
    build()
