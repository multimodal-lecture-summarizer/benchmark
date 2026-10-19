import hashlib
import json

import pytest

from experiments.scripts.tib_benchmark_budget_receipts import verify_gate_files


def test_all_four_gate_files_are_read_and_mutations_block(tmp_path):
    (tmp_path/'scorer.py').write_bytes(b'original source')
    config = {'development_trials': [{'stage':'test_fixture_only'}], 'admitted_candidate_ids':['lead3','bart'],
              'final_profile_ids':['lead3-p1','bart-p1']}
    records = {'scorer':{'scorer_ready':True,'scorer_code_sha256':{'scorer.py':hashlib.sha256(b'original source').hexdigest()}},
               'store':{'write_readback_verified':True,'restore_verified':True,'remote_source_use_authorized':True},
               'trial_registry':{'development_trials':config['development_trials']},
               'admission':{'admitted_candidate_ids':config['admitted_candidate_ids'],'final_profile_ids':config['final_profile_ids']}}
    for name, record in records.items():
        raw = json.dumps(record).encode()
        (tmp_path / (name+'.json')).write_bytes(raw)
        config[name+'_receipt_path'] = name+'.json'
        config[name+'_receipt_sha256'] = hashlib.sha256(raw).hexdigest()
    verify_gate_files(config,tmp_path)
    (tmp_path/'scorer.py').write_bytes(b'changed source')
    with pytest.raises(ValueError,match='hash mismatch'):
        verify_gate_files(config,tmp_path)
    (tmp_path/'scorer.py').write_bytes(b'original source')
    (tmp_path/'store.json').write_text('{}')
    with pytest.raises(ValueError,match='hash mismatch'):
        verify_gate_files(config,tmp_path)


def test_missing_gate_and_escape_are_not_verified(tmp_path):
    with pytest.raises(ValueError,match='Missing'):
        verify_gate_files({},tmp_path)
    with pytest.raises(ValueError,match='outside'):
        verify_gate_files({'scorer_receipt_path':'../outside.json'},tmp_path)
