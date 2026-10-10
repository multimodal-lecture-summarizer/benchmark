"""Evidence-backed derived time metadata and bounded-source review, without GT replacement."""
import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import pandas as pd
from dataset_qualification_io import ROOT, OUT, write_csv, write_json, sha


def read_csv(name):
    with (OUT / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def update_receipt(dataset, artifacts, **details):
    path = OUT / (dataset + '-qualification-receipt.json')
    value = json.loads(path.read_text(encoding='utf-8'))
    names = {a['path'] for a in artifacts}
    value['artifacts'] = [a for a in value['artifacts'] if a['path'] not in names] + artifacts
    value.update(details)
    write_json(path.name, value)


def main():
    code_sources = json.loads((OUT / 'remaining-datasets-semantic-source-probes.json').read_text())
    assert all(p['status'] == 200 for p in code_sources)
    for dataset in ['accessmath', 'lecturemath']:
        keys = read_csv(dataset + '-keyframe-ledger.csv')
        for row in keys:
            row['abs_time_unit'] = 'milliseconds; author KeyFrameAnnotation + TimeHelper.stampToStr'
            row['derived_time_s'] = float(row['abs_time_raw']) / 1000
            row['derived_time_rule'] = 'AbsTime/1000; preserve raw label and frame index; media alignment still HOLD'
        artifact = write_csv(dataset + '-keyframe-ledger.csv', keys)
        update_receipt(dataset, [artifact], time_unit_review=dict(status='verified_from_author_code',
                       unit='milliseconds', sources=code_sources,
                       media_alignment='HOLD; author annotation clock is not proof of downloaded video clock'),
                       label_semantics_review='Released extractive keyframes, segments and handwritten-content annotations; not independently verified required board-state GT.')
    # Recover every displayed historical candidate without decoding the PNG archive again.
    notebook = ROOT / 'experiments/notebooks/diagnostics/lecturemath-keyframe-annotations-eda.ipynb'
    outputs = json.loads(notebook.read_text(encoding='utf-8'))['cells'][5]['outputs']
    html = next(''.join(o['data']['text/html']) for o in outputs if 'text/html' in o.get('data', {}))
    frame = pd.read_html(io.StringIO(html))[0]
    frame = frame.drop(columns=[c for c in frame if str(c).startswith('Unnamed')])
    pairs = frame.to_dict('records')
    for row in pairs:
        row.update(decision='HOLD', reason='historical dHash candidate only; visual source review unresolved')
    artifact = write_csv('lecturemath-historical-dhash-30-of-33.csv', pairs)
    update_receipt('lecturemath', [artifact], duplicate_review=dict(historical_candidate_count=33,
                   persisted_identified_pairs=len(pairs), unresolved_unretained_pairs=33-len(pairs),
                   decision='HOLD; original signature list not persisted; do not pretend 30 rows cover 33 pairs'))
    # Official release titles link both corpora, but concatenation/camera equivalence is not proven.
    db = ET.parse(ROOT / 'experiments/outputs/board_eda_downloads/lecturemath-db.xml').getroot()
    access = {r['id']: r for r in read_csv('accessmath-id-ledger.csv')}
    lecture = {r['id']: r for r in read_csv('lecturemath-id-ledger.csv')}
    bridges = []
    for item in db.findall('.//Lectures/Lecture'):
        title = item.findtext('.//MetaData/RawTitle') or ''
        match = re.fullmatch(r'AccessMath - (NM )?Lecture (\d+)', title)
        if not match:
            continue
        access_id = ('nm_' if match[1] else '') + 'lecture_' + match[2].zfill(2)
        if access_id not in access:
            continue
        lecture_id = item.findtext('Title')
        bridges.append(dict(accessmath_id=access_id, lecturemath_id=lecture_id,
                            accessmath_split=access[access_id]['split'], lecturemath_split=lecture[lecture_id]['split'],
                            source_url=item.findtext('.//MetaData/Link'), official_raw_title=title,
                            title_mapping_evidence='author metadata exact dataset/lecture title; original camera/multipart clock not checked',
                            decision='HOLD', reason='potential_cross_dataset_reuse;do_not_pool_as_independent_sources'))
    artifact = write_csv('accessmath-lecturemath-source-bridge-ledger.csv', bridges)
    for dataset in ['accessmath', 'lecturemath']:
        update_receipt(dataset, [artifact], cross_dataset_source_bridge_candidates=len(bridges),
                       cross_dataset_leakage='Potential author-title source reuse across datasets; no independent-source claim until media alignment.')
    # Test the HH:MM:SS hypothesis against actually observed metadata duration.
    probes = json.loads((OUT / 'remaining-datasets-source-probes.json').read_text(encoding='utf-8'))
    sample = next(p for p in probes if p['dataset'] == 'eduvidqa' and p.get('id'))
    timestamp_rows = []
    for row in read_csv('eduvidqa-id-ledger.csv'):
        if row['video_id'] != sample['id'] or row['timestamp_status'] != 'three_part_unresolved':
            continue
        a, b, c = map(int, row['timestamp_raw'].split(':'))
        timestamp_rows.append(dict(id=row['id'], video_id=row['video_id'], timestamp_raw=row['timestamp_raw'],
                                   observed_metadata_duration_s=sample['duration'],
                                   hh_mm_ss_candidate_s=a*3600+b*60+c,
                                   hh_mm_ss_within_duration=a*3600+b*60+c <= sample['duration'],
                                   mm_ss_fraction_candidate_s=a*60+b+c/100,
                                   mm_ss_fraction_within_duration=a*60+b+c/100 <= sample['duration'],
                                   decision='HOLD', reason='HH:MM:SS contradicted for sample; alternative within range is not confirmed timebase'))
    artifact = write_csv('eduvidqa-sampled-three-part-timebase-review.csv', timestamp_rows)
    update_receipt('eduvidqa', [artifact], timestamp_timebase_review=dict(
                   sampled_video=sample['id'], sampled_three_part_records=len(timestamp_rows),
                   hh_mm_ss_contradicted_records=sum(not r['hh_mm_ss_within_duration'] for r in timestamp_rows),
                   scope='metadata duration only; media clip acquisition HTTP403; no verified transcript/frame alignment',
                   author_repository_parser='Pinned release contains evaluation-only scripts; no released timestamp parser found',
                   decision='HOLD; preserve raw timestamps; do not globally convert to HH:MM:SS or MM:SS'))
    update_receipt('mlpdataset', [], media_probe_rule='first released video in sorted source ID order; metadata and 0-20s clip attempt',
                   json_issue_scope='Malformed dental conversation JSON does not invalidate independently parsed segments.txt; dialogue endpoint remains HOLD.')
    # Every artifact hash and row count must still match after additive review.
    for dataset in ['mlpdataset', 'accessmath', 'lecturemath', 'eduvidqa']:
        value = json.loads((OUT / (dataset + '-qualification-receipt.json')).read_text(encoding='utf-8'))
        for artifact in value['artifacts']:
            path = ROOT / artifact['path']
            assert sha(path) == artifact['sha256'], path
        print(dataset, 'artifact hashes verified', len(value['artifacts']))


if __name__ == '__main__':
    main()
