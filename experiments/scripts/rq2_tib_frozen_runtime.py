"""Frozen TIB 120 execution with immutable identities and failure retention."""
import copy
import hashlib
import json
import math
import time
from pathlib import Path
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig, _save_result
from experiments.scripts.rq2_tib_benchmark_bundle import generation_input, validate_bundle
from experiments.scripts.rq2_tib_benchmark_dataset import REVISION
from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
from experiments.scripts.rq2_tib_benchmark_pair import run_source_pair
from experiments.scripts.rq2_tib_benchmark_results import SCORER, score_pair, validate_semantic_scores
from experiments.scripts.rq2_tib_pilot_runtime import digest, hardware_profile, TimedPilotBackend
from experiments.scripts.rq2_tib_frozen_analysis import seal, verify, summarize_frozen

CODE_MODULES=('rq2_tib_frozen_runtime','rq2_tib_frozen_analysis','rq2_tib_benchmark',
    'rq2_tib_benchmark_pair','rq2_controlled_validation','rq2_local_hf_backend',
    'rq2_tib_benchmark_bundle','rq2_tib_benchmark_dataset','rq2_tib_benchmark_metrics',
    'rq2_tib_benchmark_results','rq2_tib_pilot_runtime')
MODEL_ID='Qwen/Qwen2.5-1.5B-Instruct'
MODEL_REVISION='989aa7980e4cf806f80c7fef2b1adb7bc71aa306'


def code_identity():
    return {n:hashlib.sha256((Path(__file__).parent/(n+'.py')).read_bytes()).hexdigest() for n in CODE_MODULES}


def validate_frozen_inputs(bundle,manifest,protocol):
    validate_bundle(bundle)
    if protocol.get('format')!='tib-rq2-rq4-120-protocol-v1' or protocol.get('status')!='frozen':
        raise ValueError('Protocol is not frozen')
    for value,key in ((protocol,'protocol_sha256'),(manifest,'manifest_sha256')):
        if value.get(key)!=digest({k:v for k,v in value.items() if k!=key}):
            raise ValueError('Frozen document hash mismatch')
    selected=manifest['selected']
    if (protocol['cohort_manifest_sha256']!=manifest['manifest_sha256'] or len(selected)!=120
            or len({r['id'] for r in selected})!=120 or protocol['selected_count']!=120
            or protocol['selection_sha256']!=manifest['selection_sha256']):
        raise ValueError('Frozen count/selection identity mismatch')
    if protocol['dataset_revision']!=REVISION or protocol['tokenizer']!=bundle['metadata']['tokenizer']:
        raise ValueError('Dataset/tokenizer revision mismatch')
    if (protocol['tokenizer']!=dict(id=MODEL_ID,revision=MODEL_REVISION,
                                  add_special_tokens=False,truncation=False)
            or protocol['generation'].get('model')!=MODEL_ID
            or protocol['generation'].get('revision')!=MODEL_REVISION):
        raise ValueError('Approved Qwen model/tokenizer revision mismatch')
    if protocol['code_sha256']!=code_identity():
        raise ValueError('Frozen implementation code mismatch')
    items={f"{r['split']}/{r['source_index']}":r for r in bundle['items']}
    if len(items)!=120 or set(items)!={r['id'] for r in selected}:
        raise ValueError('Frozen bundle must contain exactly the selected 120 IDs')
    counts={'short':0,'medium':0,'long':0}
    for i,row in enumerate(selected):
        item=items.get(row['id'])
        if not item or item['split']!='valid': raise ValueError('Selected IDs must belong to valid')
        if any(row[k]!=item[k] for k in ('source_sha256','reference_sha256','source_tokens')):
            raise ValueError('Frozen content/token mismatch')
        n=row['source_tokens']; stratum='short' if n<=4271 else 'medium' if n<=7142 else 'long'
        if (row['length_stratum']!=stratum or not row['dependence_group'] or not row['author_group']
                or row['arm_order']!=(['S1','S3'] if i%2==0 else ['S3','S1'])):
            raise ValueError('Frozen stratum/group/order mismatch')
        counts[stratum]+=1
    if counts!={'short':40,'medium':40,'long':40} or protocol['strata_counts']!=counts:
        raise ValueError('Frozen stratum count mismatch')
    required=dict(chunk_tokens=512,map_output_tokens=96,final_output_tokens=384,seed=42,
                  temperature=0,map_batch_size=2,precision='float16')
    if any(protocol['generation'].get(k)!=v for k,v in required.items()):
        raise ValueError('Frozen generation settings mismatch')
    if protocol['runtime']!=dict(generation_soft_seconds=36000,session_soft_seconds=43200,automatic_retries=0):
        raise ValueError('Frozen deadline/retry policy mismatch')
    expected=SemanticScorer().metadata
    if protocol['scoring']!={**{k:expected[k] for k in ('bertscore','sbertscore')},'primary':SCORER}:
        raise ValueError('Frozen scorer mismatch')
    analysis=protocol['analysis']
    if (analysis['group_fields']!=['dependence_group','author_group']
            or type(analysis['bootstrap_samples']) is not int or analysis['bootstrap_samples']<1):
        raise ValueError('Frozen grouped analysis policy mismatch')
    return bundle


def _profile(backend,protocol):
    profile=hardware_profile(backend); gen=protocol['generation']; tok=protocol['tokenizer']
    if (profile['model']!=gen['model']+'@'+gen['revision']
            or profile['tokenizer']!=tok['id']+'@'+tok['revision'] or profile['map_batch_size']!=2
            or not profile['device'].startswith('cuda') or 'T4' not in profile.get('gpu_name','')
            or str(getattr(getattr(backend,'model',None),'dtype',None))!='torch.float16'):
        raise ValueError('Frozen model/tokenizer/FP16/T4/batch2 profile mismatch')
    return profile


def _validate_backend_tokens(backend,bundle):
    if any(backend.count_tokens(r['source_text'])!=r['source_tokens'] for r in bundle['items']):
        raise ValueError('Frozen tokenizer count changed before dispatch')


def _write(receipt,directory):
    log=directory/'dispatches.jsonl'
    receipt['dispatches']=[json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    receipt['counts']={'selected':len(receipt['rows']),
        'generated':sum(bool(r.get('scores')) for r in receipt['rows']),
        'completed':sum(r['status']=='completed' for r in receipt['rows']),
        'failed':sum(r['status'] in ('failed','interrupted','evaluation_failed') for r in receipt['rows']),
        'not_attempted':sum(r['status']=='not_attempted' for r in receipt['rows'])}
    receipt=seal(receipt); _save_result(receipt,directory/'frozen-receipt.json'); return receipt


def _validate_receipt(receipt,bundle):
    verify(receipt); validate_frozen_inputs(bundle,receipt['manifest'],receipt['protocol'])
    if receipt['identity']['protocol_sha256']!=receipt['protocol']['protocol_sha256']:
        raise ValueError('Receipt protocol identity mismatch')
    if [r['id'] for r in receipt['rows']]!=[r['id'] for r in receipt['manifest']['selected']]:
        raise ValueError('Receipt denominator/order mismatch')
    for row,selected in zip(receipt['rows'],receipt['manifest']['selected']):
        if any(row[k]!=v for k,v in selected.items()): raise ValueError('Receipt selected identity mismatch')


def run_frozen(backend,bundle,manifest,protocol,output_dir,initialization_seconds=0,on_event=None):
    if not math.isfinite(initialization_seconds) or initialization_seconds<0:
        raise ValueError('Initialization duration must be finite and nonnegative')
    validate_frozen_inputs(bundle,manifest,protocol); profile=_profile(backend,protocol)
    _validate_backend_tokens(backend,bundle)
    directory=Path(output_dir); directory.mkdir(parents=True,exist_ok=True)
    identity={'protocol_sha256':protocol['protocol_sha256'],'profile':profile}
    path=directory/'frozen-receipt.json'
    receipt=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {
        'identity':identity,'manifest':manifest,'protocol':protocol,
        'rows':[{**r,'status':'not_attempted','arms':{}} for r in manifest['selected']],
        'sessions':[],'dispatches':[],'purpose':'finite_frozen_creator_abstract_agreement'}
    if path.exists():
        _validate_receipt(receipt,bundle)
        if receipt['identity']!=identity: raise ValueError('Frozen profile changed; use a NEW output directory')
        log=directory/'dispatches.jsonl'
        dispatches=[json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
        if receipt['dispatches']!=dispatches:
            raise ValueError('Dispatch log differs from sealed receipt; preserve evidence in a NEW output root')
    session={'initialization_seconds':initialization_seconds,'generation_seconds':None,'stop_reason':None}
    receipt['sessions'].append(session); started=time.monotonic()
    wrapped=TimedPilotBackend(backend,directory/'dispatches.jsonl',
        wall_limit_seconds=max(0,min(36000,43200-initialization_seconds)))
    items={f"{r['split']}/{r['source_index']}":r for r in bundle['items']}
    _write(receipt,directory)
    for row in receipt['rows']:
        if row['status']=='in_progress':
            # A process disappeared without a final failure receipt. Do not
            # redispatch any possibly attempted work after an unknown failure.
            row.update(status='interrupted',error='unclean_interruption_no_automatic_retry')
            # No finally log is guaranteed after process termination. Preserve
            # an explicit unknown-usage marker rather than invent zero output.
            row['possibly_attempted_unknown_usage']=True
        if row['status'] in ('generated','completed','failed','evaluation_failed','interrupted'): continue
        if wrapped.blocked_reason or time.monotonic()>=wrapped.deadline:
            session['stop_reason']=wrapped.blocked_reason or 'soft_generation_deadline'; break
        wrapped.item_id=row['id']
        def emit(event):
            wrapped.arm=event.get('arm',wrapped.arm)
            if on_event: on_event({**event,'id':row['id']})
        def checkpoint(pair):
            row.update({k:v for k,v in pair.items() if k!='source_tokens'}); _write(receipt,directory)
        try:
            row['status']='in_progress'
            # Persist intent before entering segmentation or any model call.
            # An abrupt process loss must never look like untouched work.
            _write(receipt,directory)
            pair=run_source_pair(generation_input(items[row['id']]),wrapped,BenchmarkConfig(),
                completed_arms=row['arms'],on_progress=checkpoint,on_event=emit,
                arm_order=row['arm_order'],continue_on_arm_failure=True,reject_empty=True)
            row.update({k:v for k,v in pair.items() if k!='source_tokens'})
            row['status']='generated' if all(a['status']=='completed' for a in row['arms'].values()) else 'failed'
            if row['status']=='generated': row['scores']=score_pair(row['arms'],items[row['id']]['reference_text'])
        except (Exception,KeyboardInterrupt) as exc:
            row.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc))
            if wrapped.arm and wrapped.arm not in row['arms']:
                row['arms'][wrapped.arm]={'status':'failed','error':str(exc),'usage_complete':False,
                    'prompt_tokens':None,'output_tokens':None}
            session['stop_reason']=type(exc).__name__
            if isinstance(exc,KeyboardInterrupt): _write(receipt,directory); break
        _write(receipt,directory)
    session['generation_seconds']=time.monotonic()-started
    log=directory/'dispatches.jsonl'
    receipt['dispatches']=[json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    return _write(receipt,directory)


def evaluate_frozen(receipt,bundle,scorer,output_dir,metric_initialization_seconds=0,on_event=None):
    if not math.isfinite(metric_initialization_seconds) or metric_initialization_seconds<0:
        raise ValueError('Metric initialization duration must be finite and nonnegative')
    receipt=copy.deepcopy(receipt); _validate_receipt(receipt,bundle)
    directory=Path(output_dir); directory.mkdir(parents=True,exist_ok=True)
    path=directory/'frozen-receipt.json'
    if path.exists():
        saved=json.loads(path.read_text(encoding='utf-8')); _validate_receipt(saved,bundle)
        if saved['identity']!=receipt['identity']: raise ValueError('Evaluation output identity mismatch')
        receipt=saved
    log=directory/'dispatches.jsonl'
    dispatches=[json.loads(x) for x in log.read_text(encoding='utf-8').splitlines()] if log.exists() else []
    if receipt['dispatches']!=dispatches: raise ValueError('Evaluation dispatch log checksum mismatch')
    metadata=scorer.metadata; expected=receipt['protocol']['scoring']
    if (metadata.get('test_adapters') is not False or metadata.get('version')!='tib_semantic_v1'
            or any(metadata.get(k)!=expected[k] for k in ('bertscore','sbertscore'))):
        raise ValueError('Semantic scorer identity mismatch or test adapter')
    if receipt.get('semantic_identity',metadata)!=metadata: raise ValueError('Semantic scorer changed on resume')
    receipt['semantic_identity']=metadata
    receipt.setdefault('metric_sessions',[]).append({'initialization_seconds':metric_initialization_seconds})
    prior=receipt['sessions'][-1] if receipt['sessions'] else {}
    remaining=43200-metric_initialization_seconds-prior.get('generation_seconds',0)-prior.get('initialization_seconds',0)
    deadline=time.monotonic()+max(0,remaining)
    items={f"{r['split']}/{r['source_index']}":r for r in bundle['items']}
    if any(r['status']=='evaluation_failed' for r in receipt['rows']): return _write(receipt,directory)
    for row in receipt['rows']:
        if row['status']!='generated': continue
        if time.monotonic()>=deadline: break
        item=items[row['id']]; started=time.perf_counter()
        try:
            row['semantic_scores']=validate_semantic_scores(scorer.score_pair(row['arms'],item['reference_text'],item['source_text']))
            row['status']='completed'
        except (Exception,KeyboardInterrupt) as exc:
            row.update(status='evaluation_failed',evaluation_error=f'{type(exc).__name__}: {exc}')
        row['semantic_seconds']=time.perf_counter()-started
        if on_event: on_event({'stage':'evaluation','id':row['id'],'status':row['status']})
        _write(receipt,directory)
        if row['status']=='evaluation_failed': break
    return _write(receipt,directory)
