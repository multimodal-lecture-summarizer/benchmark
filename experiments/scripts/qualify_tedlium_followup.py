"""Trace retained TED-LIUM ignore rows without repeating waveform decoding."""
import json
from collections import Counter
from experiments.scripts.dataset_qualification_io import ROOT, OUT, sha, write_csv, receipt

def main():
    bundle = ROOT / 'experiments/outputs/dataset_readiness_260926/20260926T101159603902Z/bundle'
    hashes = {x['path']: x['sha256'] for x in json.loads((bundle/'bundle-receipt.json').read_text())['files']}
    units_path = bundle/'tedlium3/units.json'
    assert sha(units_path) == hashes['tedlium3/units.json']
    units = json.loads(units_path.read_text())
    rows = []
    for unit in units:
        media = bundle/'media/tedlium3'/path_name(unit['media_path'])
        assert sha(media) == unit['sha256'] == hashes['media/tedlium3/'+media.name]
        marker = unit['reference_text'].strip() == 'ignore_time_segment_in_scoring'
        gap = unit['upstream_id'].startswith('inter_segment_gap')
        valid = bool(unit['reference_text'].strip()) and not marker and not gap
        rows.append({'id': unit['unit_id'], 'split': unit['original_split'],
                     'source_group': unit['source_id'], 'reference_text': unit['reference_text'],
                     'arrow_coordinate': unit['annotation_source'], 'annotation_sha256': unit['annotation_sha256'],
                     'media_sha256': unit['sha256'], 'media_valid': True, 'label_valid': valid,
                     'decision': 'KEEP' if valid else 'EXCLUDE',
                     'reason': 'released_reference_for_bounded_ASR_diagnostic' if valid else
                               'source_ignore_marker_and_inter_segment_gap' if gap else 'source_ignore_marker',
                     'scientific_cohort_status': 'HOLD_source_snapshot_and_independent_holdout',
                     'evidence': 'retained_bundle_hash_verified; prior_50_WAV_decode_reused'})
    assert len(rows) == 50 and sum(x['label_valid'] for x in rows) == 42
    artifact = write_csv('tedlium3-id-ledger.csv', rows)
    probe_path = OUT/'tedlium-recovery-probes.json'
    probes = json.loads(probe_path.read_text())
    lium_api = next(p for p in probes if p['url'].endswith('/api/datasets/LIUM/tedlium'))
    overlap = sorted({r['source_group'] for r in rows if r['split']=='validation'} &
                     {r['source_group'] for r in rows if r['split']=='test'})
    value = receipt('tedlium3', {'selected':50,'observed':50,'label_valid':42,'media_valid':50,
                               'evaluated':0,'failed':0}, [artifact, {'path':str(probe_path.relative_to(ROOT)), 'sha256':sha(probe_path)}],
                    decisions=dict(Counter(x['decision'] for x in rows)), source_group_intersection=overlap,
                    invalid_trace={'ignore_marker':8,'validation_ignore':4,'test_gap_ignore':4},
                    source_recovery={'original_pin':'local Arrow fingerprint, not an upstream Git commit',
                                     'builder_probed_revision':'db6c0314dee6cc8e2770b34fda08f4a3bf1ebd59',
                                     'builder_preserves_ignore_marker':True,
                                     'LIUM_API_status':lium_api.get('status'),'original_Arrow_bytes_recovered':False},
                    media_scope='reuse prior 50-WAV decode, reverify immutable file hashes; no full-corpus decode',
                    status='bounded_42_item_diagnostic_candidate_only_no_scientific_freeze')
    print(json.dumps(value, ensure_ascii=True))

def path_name(value):
    return value.replace('\\','/').rsplit('/',1)[-1]

if __name__ == '__main__': main()
