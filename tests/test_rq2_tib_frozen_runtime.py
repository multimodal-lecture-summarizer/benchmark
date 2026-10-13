"""Offline frozen runtime contracts; these fixtures produce no research scores."""
import copy
import json
import pytest
from experiments.scripts import rq2_tib_frozen_runtime as frozen
from experiments.scripts import rq2_tib_benchmark_bundle as bundles
from experiments.scripts import rq2_tib_benchmark_dataset as tib
from experiments.scripts.rq2_tib_frozen_analysis import grouped_interval, seal
from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
from test_rq2_tib_pilot_runtime import Backend as PilotBackend


class Backend(PilotBackend):
    map_batch_size=2


@pytest.fixture
def data():
    rows=[{'doi':str(i),'abstract':f'abstract {i}','transcript':'source end',
           'transcript_segments':{'text':['source','end'],'start':[0,2],'end':[1,3]}}
          for i in range(120)]
    prepared=tib.prepare_dataset({'train':[],'valid':rows,'test':[]},verify_counts=False)
    bundle=bundles.build_benchmark_bundle(prepared)
    bundles.add_token_counts(bundle,lambda s:s.split(),tokenizer_id=frozen.MODEL_ID,tokenizer_revision=frozen.MODEL_REVISION)
    selected=[]
    for i,item in enumerate(bundle['items']):
        item['source_tokens']=(100,5000,8000)[i//40]
        selected.append({'id':f'valid/{i}','source_sha256':item['source_sha256'],
            'reference_sha256':item['reference_sha256'],'source_tokens':item['source_tokens'],
            'length_stratum':('short','medium','long')[i//40],
            'dependence_group':str(i//2),'author_group':str(i//4),
            'arm_order':['S1','S3'] if i%2==0 else ['S3','S1']})
    manifest={'selected':selected,'selection_sha256':bundle['metadata']['selection_sha256']}
    manifest['manifest_sha256']=frozen.digest(manifest)
    metadata=SemanticScorer().metadata
    protocol={'format':'tib-rq2-rq4-120-protocol-v1','status':'frozen',
        'cohort_manifest_sha256':manifest['manifest_sha256'],'selected_count':120,
        'selection_sha256':manifest['selection_sha256'],'dataset_revision':tib.REVISION,
        'tokenizer':bundle['metadata']['tokenizer'],'strata_counts':{'short':40,'medium':40,'long':40},
        'generation':dict(model=frozen.MODEL_ID,revision=frozen.MODEL_REVISION,chunk_tokens=512,map_output_tokens=96,
                          final_output_tokens=384,seed=42,temperature=0,map_batch_size=2,precision='float16'),
        'runtime':dict(generation_soft_seconds=36000,session_soft_seconds=43200,automatic_retries=0),
        'scoring':{**{k:metadata[k] for k in ('bertscore','sbertscore')},'primary':frozen.SCORER},
        'analysis':dict(bootstrap_samples=100,seed=42,group_fields=['dependence_group','author_group']),
        'code_sha256':frozen.code_identity()}
    protocol['protocol_sha256']=frozen.digest(protocol)
    return bundle,manifest,protocol


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(frozen,'_profile',lambda backend,protocol:{'device':'offline_test'})
    monkeypatch.setattr(frozen,'_validate_backend_tokens',lambda backend,bundle:None)


def test_valid_and_changed_documents(data):
    bundle,manifest,protocol=data
    assert frozen.validate_frozen_inputs(*data) is bundle
    for obj,key in ((manifest,'selected'),(protocol,'code_sha256')):
        changed=copy.deepcopy(obj)
        changed[key]={} if key=='code_sha256' else []
        args=(bundle,changed,protocol) if obj is manifest else (bundle,manifest,changed)
        with pytest.raises(ValueError,match='hash'): frozen.validate_frozen_inputs(*args)


def test_runtime_failure_retained_no_retry_and_denominator(data,offline,tmp_path):
    backend=Backend(failure='ordinary offline failure')
    result=frozen.run_frozen(backend,*data,tmp_path)
    assert len(result['rows'])==120
    assert result['rows'][0]['status']=='failed'
    assert result['rows'][0]['arms']['S3']['status']=='completed'
    assert result['rows'][1]['arm_order']==['S3','S1']
    resumed=Backend()
    again=frozen.run_frozen(resumed,*data,tmp_path)
    assert not resumed.requests
    assert again['rows'][0]['status']=='failed'
    summary=frozen.summarize_frozen(again,data[1],data[2])
    assert summary['metrics']['rouge_l']['overall']['paired_scored']==119
    assert summary['dispatch_usage']['unknown_output_dispatches']==1
    assert summary['dispatch_usage']['total_output_tokens'] is None


def test_cuda_stops_dispatch_all120_retained(data,offline,tmp_path):
    backend=Backend(failure='CUDA device-side assert')
    result=frozen.run_frozen(backend,*data,tmp_path)
    assert len(backend.requests)==1
    assert len(result['rows'])==120
    assert sum(r['status']=='not_attempted' for r in result['rows'])==119


def test_empty_failure_no_zero_imputation(data,offline,tmp_path):
    result=frozen.run_frozen(Backend(empty=True),*data,tmp_path)
    assert all(r['status']=='failed' for r in result['rows'])
    summary=frozen.summarize_frozen(result,data[1],data[2])
    assert summary['metrics']['rouge_l']['overall']['S3_minus_S1'] is None


def test_receipt_tamper_rejected(data,offline,tmp_path):
    frozen.run_frozen(Backend(),*data,tmp_path,initialization_seconds=43200)
    path=tmp_path/'frozen-receipt.json'
    result=json.loads(path.read_text()); result['rows'][0]['id']='valid/999'
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError,match='checksum'): frozen.run_frozen(Backend(),*data,tmp_path)


def test_profile_rejected_without_offline_override(data):
    with pytest.raises(ValueError,match='profile'): frozen._profile(Backend(),data[2])


def test_semantic_failure_preserves_rouge_and_stops(data,offline,tmp_path):
    result=frozen.run_frozen(Backend(),*data,tmp_path)
    class Scorer:
        metadata=SemanticScorer().metadata
        calls=0
        def score_pair(self,*args):
            self.calls+=1
            raise RuntimeError('offline semantic failure')
    scorer=Scorer()
    evaluated=frozen.evaluate_frozen(result,data[0],scorer,tmp_path)
    assert scorer.calls==1
    assert evaluated['rows'][0]['scores']==result['rows'][0]['scores']
    assert evaluated['rows'][0]['status']=='evaluation_failed'
    frozen.evaluate_frozen(evaluated,data[0],scorer,tmp_path)
    assert scorer.calls==1
    summary=frozen.summarize_frozen(evaluated,data[1],data[2])
    assert summary['metrics']['rouge_l']['overall']['paired_scored']==120
    assert summary['metrics']['bertscore']['overall']['paired_scored']==0


def test_group_bootstrap_retains_component_multiplicity_and_record_weights():
    rows=[({'group':'a'},0)]*9+[({'group':'b'},10)]
    interval=grouped_interval(rows,'group',10000,42)
    assert interval['group_count']==2
    assert interval['ci95']==[0,10]
    # A single draw of both groups must equal record-weighted 1, not 5.
    import random
    seed=next(s for s in range(100) if len(set(random.Random(s).choices([0,1],k=2)))==2)
    assert grouped_interval(rows,'group',1,seed)['ci95']==[1,1]


def test_rehashed_code_revision_order_and_content_changes_rejected(data):
    bundle,manifest,protocol=data
    for field in ('code_sha256','dataset_revision'):
        changed=copy.deepcopy(protocol)
        changed[field]={} if field=='code_sha256' else 'other_revision'
        changed['protocol_sha256']=frozen.digest({k:v for k,v in changed.items() if k!='protocol_sha256'})
        with pytest.raises(ValueError): frozen.validate_frozen_inputs(bundle,manifest,changed)
    changed=copy.deepcopy(protocol); changed['generation']['revision']='unapproved'
    changed['protocol_sha256']=frozen.digest({k:v for k,v in changed.items() if k!='protocol_sha256'})
    with pytest.raises(ValueError,match='Qwen'): frozen.validate_frozen_inputs(bundle,manifest,changed)
    for field,value in (('arm_order',['S3','S1']),('source_sha256','0'*64),('length_stratum','long')):
        changed=copy.deepcopy(manifest); changed['selected'][0][field]=value
        changed['manifest_sha256']=frozen.digest({k:v for k,v in changed.items() if k!='manifest_sha256'})
        pinned=copy.deepcopy(protocol); pinned['cohort_manifest_sha256']=changed['manifest_sha256']
        pinned['protocol_sha256']=frozen.digest({k:v for k,v in pinned.items() if k!='protocol_sha256'})
        with pytest.raises(ValueError): frozen.validate_frozen_inputs(bundle,changed,pinned)


def test_dispatch_tamper_rejected_on_resume(data,offline,tmp_path):
    frozen.run_frozen(Backend(),*data,tmp_path,initialization_seconds=43200)
    (tmp_path/'dispatches.jsonl').write_text('{}\n')
    with pytest.raises(ValueError,match='Dispatch log'):
        frozen.run_frozen(Backend(),*data,tmp_path)


def test_interrupt_preserves_completed_arm_without_retry(data,offline,tmp_path):
    class Interrupted(Backend):
        def generate(self,prompt,**kwargs):
            if len(self.requests)>=2: raise KeyboardInterrupt('offline interruption')
            return super().generate(prompt,**kwargs)
    result=frozen.run_frozen(Interrupted(),*data,tmp_path)
    assert result['rows'][0]['status']=='interrupted'
    assert result['rows'][0]['arms']['S1']['status']=='completed'
    assert result['rows'][0]['arms']['S3']['status']=='failed'
    assert result['dispatches'][-1]['output_tokens'] is None
    resumed=Backend()
    again=frozen.run_frozen(resumed,*data,tmp_path,initialization_seconds=43200)
    assert not resumed.requests
    assert again['rows'][0]['arms']['S1']==result['rows'][0]['arms']['S1']


def test_injected_scorer_rejected_without_dispatch(data,offline,tmp_path):
    result=frozen.run_frozen(Backend(),*data,tmp_path,initialization_seconds=43200)
    scorer=SemanticScorer(bert_adapter=object())
    with pytest.raises(ValueError,match='test adapter'):
        frozen.evaluate_frozen(result,data[0],scorer,tmp_path)


def test_inflight_intent_is_sealed_before_first_dispatch_and_never_retried(data,offline,tmp_path):
    class AbruptProcessLoss(BaseException):
        pass
    class CrashBackend(Backend):
        def generate(self,prompt,**kwargs):
            saved=json.loads((tmp_path/'frozen-receipt.json').read_text())
            frozen.verify(saved)
            assert saved['rows'][0]['status']=='in_progress'
            assert saved['dispatches']==[]
            raise AbruptProcessLoss()
    # Simulate an uncatchable process loss with no dispatch finally receipt.
    def no_finally_dispatch(self,prompts,kwargs,batched):
        return self.backend.generate(prompts[0],**kwargs)
    from unittest.mock import patch
    with patch.object(frozen.TimedPilotBackend,'_dispatch',no_finally_dispatch):
        with pytest.raises(AbruptProcessLoss):
            frozen.run_frozen(CrashBackend(),*data,tmp_path)
    saved=json.loads((tmp_path/'frozen-receipt.json').read_text())
    assert saved['rows'][0]['status']=='in_progress'
    assert not (tmp_path/'dispatches.jsonl').exists()
    # Bound the resumed invocation; first row is finalized before deadline.
    resumed=Backend()
    result=frozen.run_frozen(resumed,*data,tmp_path,initialization_seconds=43200)
    assert result['rows'][0]['status']=='interrupted'
    assert len(result['rows'])==120
    assert not resumed.requests
    assert result['rows'][0]['possibly_attempted_unknown_usage'] is True
    assert result['dispatches']==[]
    summary=frozen.summarize_frozen(result,data[1],data[2])
    assert summary['dispatch_usage']['total_output_tokens'] is None
