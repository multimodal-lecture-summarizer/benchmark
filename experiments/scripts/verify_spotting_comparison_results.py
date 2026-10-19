"""Independent bookkeeping and receipt checks on completed real spotting evidence."""
import csv
import gzip
import json
import math
from pathlib import Path

import nbformat

from experiments.scripts.spotting_candidate_contract import ROOT, canonical_sha, sha, verify_files
from experiments.scripts.spotting_comparison_io_v2 import OUT, RUNTIME, load_checkpoints, write_once
from experiments.scripts.spotting_runtime_binding import read_json, require


def rows(name):
    path=OUT/name
    opener=gzip.open if name.endswith('.gz') else open
    with opener(path,'rt',encoding='utf-8',newline='') as stream: return list(csv.DictReader(stream))


def close(a,b):
    require(math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12),'numeric evidence mismatch')


def verify():
    execution=read_json(OUT/'execution-receipt.json')
    identity=read_json(OUT/'run-identity.json');verify_files(identity['snapshot'],ROOT)
    complete=read_json(OUT/'inference-complete.json')
    require(complete['run_id']==identity['run_id'] and complete['committed_records']==3508,'incomplete inference')
    frames=read_json(OUT/'input-manifest.json');ids={r['frame_id'] for r in frames}
    require(len(frames)==len(ids)==1754,'wrong unique cohort')
    raw={}
    for candidate in identity['candidate_order']:
        raw[candidate]=load_checkpoints(identity,frames,candidate)
        require(raw[candidate].keys()==ids,'missing committed inference record')
        for r in raw[candidate].values():
            require(r['origin'] in ('predictor_attempt','supervisor_timeout') and r['attempt_count']==1,
                    'unexplained forward origin or retry')
    analysis=read_json(OUT/'analysis-summary.json')
    for artifact in analysis['artifacts'].values():
        require(sha(ROOT/artifact['path'])==artifact['sha256'],'analysis export digest mismatch')
    metrics=rows('metrics.csv');scores=rows('frame-scores.csv.gz')
    require(len(metrics)==16 and len(scores)==14026,'incomplete metric exports')
    bymetric={(r['variant'],r['candidate_id'],r['metric']):r for r in metrics}
    for key,aggregate in bymetric.items():
        variant,candidate,metric=key
        subset=[r for r in scores if (r['variant'],r['candidate_id'])==(variant,candidate)]
        require(len(subset)==int(aggregate['selected_frames']),'frame score count mismatch')
        require(len(subset)==len({r['frame_id'] for r in subset}),'duplicate scored frame')
        for count in ('tp','fp','fn'):
            require(sum(int(r[metric+'_'+count]) for r in subset)==int(aggregate[count]),'pooled count mismatch')
        tp,fp,fn=(int(aggregate[k]) for k in ('tp','fp','fn'))
        close(aggregate['precision'],tp/(tp+fp) if tp+fp else 0)
        close(aggregate['recall'],tp/(tp+fn) if tp+fn else 0)
        close(aggregate['hmean'],2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
        expected=(1751,40023) if variant=='observed_flag_frame_influence' else (1754,40063)
        require((len(subset),tp+fn)==expected,'wrong variant denominator')
    for r in scores:
        require(int(r['spotting_tp'])<=int(r['detection_tp']),'text match exceeds geometric matching')
        if r['status']=='error':
            require(int(r['predictions_count'])==int(r['spotting_tp'])==int(r['detection_tp'])==0,
                    'failure retains partial predictions')
            require(int(r['spotting_fn'])==int(r['detection_fn'])==int(r['gt_objects']),'failure denominator lost')
    for candidate in identity['candidate_order']:
        for metric in ('spotting','detection'):
            base=bymetric['primary',candidate,metric]
            for variant in ('iou_075','case_sensitive'):
                row=bymetric[variant,candidate,metric]
                require(int(row['tp'])<=int(base['tp']),'stricter rule increased match count')
            close(bymetric['case_sensitive',candidate,'detection']['hmean'],bymetric['primary',candidate,'detection']['hmean'])
    bootstrap=rows('bootstrap.csv');require(len(bootstrap)==8,'missing uncertainty rows')
    for r in bootstrap:
        a,b=(bymetric[r['variant'],cid,'spotting'] for cid in identity['candidate_order'])
        close(r['observed'],float(b['hmean'])-float(a['hmean']))
        require(int(r['draws'])==2000 and int(r['seed'])==20261014,'bootstrap changed')
    texts=rows('all-frame-text.csv.gz');require(len(texts)==1754 and {r['frame_id'] for r in texts}==ids,'full text coverage lost')
    gtpath=ROOT/'experiments/outputs/iiit-cvid-spotting-test-261014/ground-truth.jsonl'
    refs={r['frame_id']:r for r in map(json.loads,gtpath.read_text(encoding='utf-8').splitlines())}
    for r in texts:
        require(json.loads(r['gt_texts'])==[o['text'] for o in refs[r['frame_id']]['objects']] and
                json.loads(r['gt_object_ids'])==[o['object_id'] for o in refs[r['frame_id']]['objects']],
                'GT text/ordinal truncated or changed')
        for prefix,candidate in zip(('easyocr','paddleocr'),identity['candidate_order']):
            require(json.loads(r[prefix+'_texts'])==[p['text'] for p in raw[candidate][r['frame_id']]['predictions']],
                    'raw prediction text truncated or changed')
    failures=rows('failure-ledger.csv')
    require(len(failures)==sum(r['status']=='error' for arm in raw.values() for r in arm.values()),'failure ledger mismatch')
    display=read_json(OUT/'display-receipt.json')
    for key in ('attempt_evidence','gallery_decisions','analysis_summary'):
        artifact=display[key]
        require(sha(ROOT/artifact['path'])==artifact['sha256'],'display reference digest mismatch')
    for artifact in display['artifacts']:
        require(sha(ROOT/artifact['path'])==artifact['sha256'],'display artifact changed')
    attempt=read_json(ROOT/display['attempt_evidence']['path'])
    for artifact in attempt['artifacts']:
        require(sha(ROOT/artifact['path'])==artifact['sha256'],'attempt evidence changed')
    actual={p.relative_to(ROOT).as_posix() for cid in identity['candidate_order']
            for p in (OUT/cid/'attempts').rglob('*') if p.is_file()}
    require(actual=={a['path'] for a in attempt['artifacts']},'attempt manifest omits evidence')
    sealed={c['candidate_id']:c['identity_sha256'] for c in read_json(RUNTIME)['candidates']}
    for candidate in complete['candidates']:
        worker=read_json(ROOT/candidate['worker_completion'])
        require(worker['candidate_id']==candidate['candidate_id'] and worker['run_id']==identity['run_id'] and
                worker['runtime_identity_sha256']==sealed[candidate['candidate_id']],'worker/runtime identity mismatch')
        for field in ('selected_frames','committed_frames','successful_frames','failed_frames'):
            require(worker[field]==candidate[field],'worker completion count mismatch')
        for path in (OUT/candidate['candidate_id']/'attempts').glob('*/loaded-runtime.json'):
            loaded=read_json(path)
            require(loaded['runtime_identity_sha256']==canonical_sha(loaded['identity'])==sealed[candidate['candidate_id']],
                    'actual loading identity differs from sealed runtime')
    for key in ('notebook','html','inference','analysis','display'):
        artifact=execution[key];require(sha(ROOT/artifact['path'])==artifact['sha256'],'execution binding mismatch')
    require(read_json(ROOT/'experiments/registry/datasets/iiit-cvid-test-spotting-comparison-261014-v2.json')==execution,
            'registry and local execution receipts differ')
    notebook=nbformat.read(ROOT/execution['notebook']['path'],as_version=4);nbformat.validate(notebook)
    cells=[c for c in notebook.cells if c.cell_type=='code']
    require([c.execution_count for c in cells]==list(range(1,len(cells)+1)),'nonsequential/incomplete execution')
    outputs=[o for c in cells for o in c.get('outputs',[])]
    require(not any(o.output_type=='error' for o in outputs),'notebook contains errors')
    require(sum('image/png' in o.get('data',{}) for o in outputs)==8,'missing embedded scientific figures')
    require(sum('image/jpeg' in o.get('data',{}) for o in outputs)==display['gallery_count'],'missing embedded gallery')
    html=(ROOT/execution['html']['path']).read_text(encoding='utf-8')
    require(all(ident in html for ident in ids),'HTML omits cohort IDs')
    result=dict(schema='cvid_spotting_completed_evidence_verification_v1',run_id=identity['run_id'],
        verified_inference_records=3508,verified_frame_scores=14026,verified_full_text_frames=1754,
        metrics_rows=16,bootstrap_rows=8,notebook_code_cells=len(cells),saved_errors=0,
        execution_receipt_sha256=sha(OUT/'execution-receipt.json'),verification_code_sha256=sha(Path(__file__)))
    write_once(OUT/'final-verification.json',result)
    return result


if __name__=='__main__': print(json.dumps(verify(),indent=2))
