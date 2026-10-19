"""Verify frozen test identities and full-cohort scorer oracles, without OCR."""
from collections import Counter
import json
from pathlib import Path

from experiments.scripts.cvid_eda_common import ROOT, OUT, sha
from experiments.scripts.cvid_test_contract import NAME, REGISTRY
from experiments.scripts.cvid_test_scoring import paired_cluster_bootstrap, score_test_endpoints
from experiments.scripts.cvid_test_source import require
from experiments.scripts.freeze_cvid_test_spotting import verify_snapshot
from experiments.scripts.freeze_iiit_cvid_spotting import frozen_write, json_bytes


def load_json(suffix):
    return json.loads((REGISTRY/(NAME+suffix+'.json')).read_text(encoding='utf-8'))


def verify_data():
    receipt = load_json('-freeze')
    for item in receipt['artifacts']+receipt['prerequisites']:
        require(sha(ROOT/item['path']) == item['sha256'], 'frozen artifact hash mismatch: '+item['path'])
    verify_snapshot(receipt['preserved_sha256'])
    for name, expected in receipt['implementation_sha256'].items():
        require(sha(Path(__file__).with_name(name)) == expected, 'implementation changed: '+name)
    manifest, influence, protocol = (load_json(s) for s in ('-cohort','-influence','-protocol'))
    selected = [f for f in manifest['frames'] if f['selected']]
    held = [f for f in manifest['frames'] if not f['selected']]
    ids = (REGISTRY/(NAME+'-selected-frame-ids.txt')).read_text(encoding='utf-8').splitlines()
    require(len(set(ids)) == 1754 and ids == [r['frame_id'] for r in selected], 'selected ID coverage changed')
    require(len(manifest['frames']) == 1755 and len(held) == 1, 'source partition changed')
    require(Counter(f['decision'] for f in manifest['frames']) == {'KEEP':1657,'REPAIR_METADATA_DERIVED':97,'HOLD':1}, 'decisions changed')
    require(sum(f['object_count'] for f in held) == 40, 'held GT count changed')
    gt_path = ROOT/'experiments/outputs'/NAME/'ground-truth.jsonl'
    gt = [json.loads(line) for line in gt_path.read_text(encoding='utf-8').splitlines()]
    require([r['frame_id'] for r in gt] == ids, 'GT/selected IDs disagree')
    require(sum(len(r['objects']) for r in gt) == 40063, 'GT denominator changed')
    # Use the already hash-bound EDA ledger to independently compare every GT row.
    import pandas as pd
    objects = pd.read_csv(OUT/'objects.csv.gz',keep_default_na=False).set_index('object_id').to_dict('index')
    frame_map, seen = {f['frame_id']:f for f in selected}, set()
    for frame in gt:
        source = frame_map[frame['frame_id']]
        require([frame['width'],frame['height']] == [source['width'],source['height']], 'GT decoded dimensions changed')
        require(len(frame['objects']) == source['object_count'], 'GT object count changed')
        for obj in frame['objects']:
            require(obj['object_id'] not in seen and obj['object_id'] == 'Frames/'+obj['eda_object_id'], 'GT identity collision')
            seen.add(obj['object_id'])
            raw = objects[obj['eda_object_id']]
            require(raw['frame_id'] == source['eda_frame_id'] and obj['text'] == raw['text'], 'GT raw text/frame changed')
            require(obj['bbox_xyxy'] == [raw[k] for k in ('xmin','ymin','xmax','ymax')] and raw['geometry_valid'], 'GT geometry changed')
    excluded = influence['excluded_frame_ids']
    retained = [r for r in gt if r['frame_id'] not in excluded]
    require(len(retained) == 1751 and sum(len(r['objects']) for r in retained) == 40023, 'influence denominator changed')
    require(influence['selected_frame_ids'] == [r['frame_id'] for r in retained], 'influence selected IDs changed')
    require(protocol['metrics']['primary_uncertainty']['K'] == len(manifest['courses']) == 7, 'course contract changed')
    require(protocol['metrics']['secondary_uncertainty']['K'] == len(manifest['source_groups']) == 276, 'folder contract changed')
    return gt, excluded, receipt


def oracle_records(gt):
    records = []
    for frame in gt:
        predictions = []
        for obj in frame['objects']:
            a,b,c,d = obj['bbox_xyxy']
            predictions.append(dict(text=obj['text'],polygon=[[a,b],[c,b],[c,d],[a,d]]))
        records.append(dict(frame_id=frame['frame_id'],status='ok',predictions=predictions))
    return records


def main():
    gt, excluded, freeze = verify_data()
    print('Frozen identities verified; running full 40,063-object oracle (not model predictions)',flush=True)
    oracle = score_test_endpoints(gt,oracle_records(gt),excluded)
    missing = score_test_endpoints(gt,[],excluded)
    empty = score_test_endpoints(gt,[dict(frame_id=r['frame_id'],status='ok',predictions=[]) for r in gt],excluded)
    totals = {}
    for endpoint, frames, objects in [('primary',1754,40063),('observed_flag_frame_influence',1751,40023)]:
        perfect,failed,blank = oracle[endpoint],missing[endpoint],empty[endpoint]
        require(perfect['selected_frames'] == frames and perfect['failed_frames'] == 0, 'oracle coverage changed')
        for metric in ('detection','spotting'):
            require(perfect['overall'][metric]['tp'] == objects and perfect['overall'][metric]['hmean'] == 1., 'oracle mismatch')
            require(failed['overall'][metric]['fn'] == blank['overall'][metric]['fn'] == objects, 'missing/empty denominator changed')
            require(failed['overall'][metric]['hmean'] == blank['overall'][metric]['hmean'] == 0., 'missing/empty score mismatch')
        require(failed['failed_frames'] == frames and blank['failed_frames'] == 0, 'error/empty distinction changed')
        cluster = paired_cluster_bootstrap(perfect['frames'],perfect['frames'])
        require(cluster['observed'] == 0. and cluster['interval_95'] == [0.,0.] and len(cluster['groups']) == 7, 'paired identity oracle failed')
        totals[endpoint] = dict(frames=frames,objects=objects,oracle=perfect['overall'],
                               missing_all_frames=failed['failed_frames'],empty_success_frames=blank['successful_frames'],
                               missing_and_empty_fn=objects,paired_identity_bootstrap=cluster)
    verify_snapshot(freeze['preserved_sha256'])
    result = dict(schema='iiit_cvid_spotting_test_freeze_verification_v1',date='2026-10-14',
        freeze_receipt_sha256=sha(REGISTRY/(NAME+'-freeze.json')),
        verification_implementation_sha256=sha(Path(__file__)),artifact_hashes_verified=len(freeze['artifacts']),
        preserved_hashes_verified=len(freeze['preserved_sha256']),full_gt_rows_compared=40063,
        endpoints=totals,spotting_inference_executed=False,
        limits='Oracle uses released GT as synthetic predictions solely to test scorer contracts; no model accuracy result')
    frozen_write(REGISTRY/(NAME+'-verified.json'),json_bytes(result))
    print(json.dumps(dict(status='verified',selected_frames=1754,selected_objects=40063,
        influence_frames=1751,influence_objects=40023,spotting_inference_executed=False),indent=2))


if __name__ == '__main__':
    main()
