import json
from pathlib import Path

import pytest

from experiments.scripts.tib_benchmark_adapter_budget import Budget, AdapterFailure, plan_windows
from experiments.scripts.tib_benchmark_checkpoint import commit, digest
from experiments.scripts.tib_benchmark_development_trials import build_trial_registry, resolve_trial, development_node_seed
from experiments.scripts.tib_benchmark_capacity_runtime import runtime_identity


def registry():
    root = Path(__file__).resolve().parents[1]
    proposals = json.loads((root/'experiments/registry/protocols/tib-model-benchmark-p4-261019-1802/candidate_profiles.json').read_text())
    original = json.dumps(proposals, sort_keys=True)
    result = build_trial_registry(proposals, {i:'a'*64 for i in ('valid:644','valid:341','valid:886')})
    assert json.dumps(proposals, sort_keys=True) == original
    return result


def test_bounded_trials_preserve_shared_cap_and_final_reserve():
    r = registry()
    assert len(r['trials']) == 8 and sum(t['enabled_by_default'] for t in r['trials']) == 7
    assert r['word_cap'] == 350 and r['selection_authorized'] is False
    assert all(t['profile']['final_max_new_tokens_including_EOS'] == 768 for t in r['trials'])
    assert [t['profile']['decode']['no_repeat_ngram_size'] for t in r['trials'] if t['candidate_id']=='led'] == [0,3,4]


def test_qwen_larger_reserve_repartitions_native_windows_with_wrappers():
    source = list(range(9000))
    wrapper = lambda ids, stage: [1]*60 + ids + [2]*20
    counts = []
    for reserve in (256,384,512):
        budget = Budget('causal',4096,reserve)
        windows = plan_windows(source,budget,wrapper)
        assert windows[0]['start'] == 0 and windows[-1]['end'] == len(source)
        assert all(a['end'] == b['start'] for a,b in zip(windows,windows[1:]))
        assert all(w['batch']['padded_length'] + reserve <=4096 for w in windows)
        counts.append(windows[0]['end'])
    assert counts == [3760,3632,3504]
    with pytest.raises(AdapterFailure):
        Budget('causal',4096,512).prepare(list(range(3840)),lambda ids,stage:ids,'map')


def test_deferred_trial_needs_explicit_flag_and_verified_capacity(tmp_path):
    r = registry()
    with pytest.raises(ValueError,match='explicit resource'):
        resolve_trial(r,'qwen-r512','qwen3',tmp_path)
    with pytest.raises(ValueError,match='verified384'):
        resolve_trial(r,'qwen-r512','qwen3',tmp_path,allow_deferred=True)
    commit(tmp_path/'qwen3/qwen-r384/capacity-test.json',{
        'trial_id':'qwen-r384','candidate_id':'qwen3','status':'completed','T4_feasibility_verified':True,
        'device_name':'Tesla T4', 'trial_registry_sha256':digest(r),
        'profile_sha256':next(t for t in r['trials'] if t['trial_id']=='qwen-r384')['profile_sha256'],
        'records':[{'record_id':i,'source_sha256':'a'*64,'status':'completed'} for i in r['source_ids']],
        'device_memory_bytes':16*1024**3,'cuda_peak_reserved_bytes':14*1024**3})
    assert resolve_trial(r,'qwen-r512','qwen3',tmp_path,allow_deferred=True)['deferred']


def test_trial_namespace_and_source_node_seed_are_stable(tmp_path):
    r = registry()
    with pytest.raises(ValueError,match='mismatched'):
        resolve_trial(r,'led-ngram3','bart',tmp_path)
    key = {'record_id':'valid:886','stage':'map','layer':0,'node':1,'profile_sha256':'one'}
    assert development_node_seed(key) == development_node_seed({**key,'profile_sha256':'two'})
    assert development_node_seed(key) != development_node_seed({**key,'node':2})


@pytest.mark.parametrize('field', ['runtime_dependencies','asset_sha256','actual_attention_backend','actual_device_map'])
def test_checkpoint_identity_changes_with_inference_environment(field):
    receipt = {k:'baseline' for k in ('device_name','packages','cuda_runtime','actual_parameter_dtype',
              'runtime_dependencies','actual_attention_backend','actual_device_map','asset_sha256',
              'tokenizer_class','device_memory_bytes')}
    assert runtime_identity(receipt) != runtime_identity({**receipt,field:'changed'})


def test_deferred_trial_rejects_other_profile_or_source_evidence(tmp_path):
    r = registry()
    receipt = {'trial_id':'qwen-r384','candidate_id':'qwen3','status':'completed',
        'T4_feasibility_verified':True,'device_name':'Tesla T4','trial_registry_sha256':digest(r),
        'profile_sha256':'wrong','records':[{'record_id':i,'source_sha256':'a'*64,'status':'completed'} for i in r['source_ids']],
        'device_memory_bytes':16*1024**3,'cuda_peak_reserved_bytes':14*1024**3}
    path=tmp_path/'qwen3/qwen-r384/capacity-bad.json'
    commit(path,receipt)
    with pytest.raises(ValueError,match='verified384'):
        resolve_trial(r,'qwen-r512','qwen3',tmp_path,allow_deferred=True)
    receipt['profile_sha256']=next(t for t in r['trials'] if t['trial_id']=='qwen-r384')['profile_sha256']
    receipt['records'][0]['source_sha256']='other-source'
    commit(path,receipt)
    with pytest.raises(ValueError,match='verified384'):
        resolve_trial(r,'qwen-r512','qwen3',tmp_path,allow_deferred=True)
