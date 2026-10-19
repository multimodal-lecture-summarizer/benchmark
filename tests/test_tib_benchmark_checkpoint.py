import json
import time

import pytest

from experiments.scripts.tib_benchmark_checkpoint import NodeCheckpointGenerator, commit, restore, probe_store


def test_atomic_store_readback_and_hash_corruption(tmp_path):
    path = tmp_path/'node.json'
    assert commit(path,{'text':'notes'}) == {'text':'notes'}
    data = json.loads(path.read_text()); data['payload']['text']='corrupt'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='hash mismatch'): restore(path)
    assert probe_store(tmp_path)['cross_session_survival_verified'] is False


def test_resume_reuses_only_matching_identity_context_and_input(tmp_path):
    calls=[]
    def generate(batch,maximum,stage): calls.append(stage); return 'Notes.'
    generator=NodeCheckpointGenerator(generate,tmp_path,{'profile':'p1'},time.monotonic()+60)
    generator.set_node_context({'layer':0,'node':0})
    assert generator({'input_ids':[1]},4,'map') == 'Notes.'
    assert generator({'input_ids':[1]},4,'map') == 'Notes.'
    assert calls == ['map'] and generator.events[-1]['status']=='reused'
    generator({'input_ids':[2]},4,'map')
    generator.set_node_context({'layer':1,'node':0})
    generator({'input_ids':[2]},4,'map')
    assert len(calls)==3


def test_partial_file_is_not_resumed_and_deadline_blocks(tmp_path):
    (tmp_path/'anything.json.partial').write_text('partial')
    generator=NodeCheckpointGenerator(None,tmp_path,{},time.monotonic()-1)
    generator.set_node_context({'layer':0,'node':0})
    with pytest.raises(TimeoutError): generator({'input_ids':[1]},4,'map')
    assert generator.events[0]['status'] == 'deadline_before_call'
    assert generator.events[0]['new_attempt_wall_seconds'] == 0
    assert generator.events[0]['generation_started'] is False


@pytest.mark.parametrize('mode,status,error_type', [
    ('raise','failed',RuntimeError),
    ('deadline','deadline_hit',TimeoutError),
    ('empty','failed_empty_output',ValueError),
])
def test_failed_calls_preserve_spent_cost_and_telemetry(tmp_path, mode, status, error_type):
    class Backend:
        last_receipt = None
        calls = 0

        def __call__(self, batch, maximum, stage):
            self.calls += 1
            self.last_receipt = {'stage':stage,'diagnostic':'partial or complete backend evidence'}
            if mode == 'raise':
                raise RuntimeError('backend generation failed')
            if mode == 'deadline':
                generator.deadline = time.monotonic() - 1
            return '  ' if mode == 'empty' else 'Notes.'

    backend = Backend()
    generator = NodeCheckpointGenerator(backend,tmp_path,{'profile':'failure'},time.monotonic()+60)
    generator.set_node_context({'layer':0,'node':0})
    with pytest.raises(error_type):
        generator({'input_ids':[1]},4,'map')
    assert backend.calls == 1  # No automatic retries.
    event = generator.events[0]
    assert event['status'] == status
    assert event['new_attempt_wall_seconds'] >= 0
    assert event['generation_started'] is True
    assert event['backend_receipt'] == backend.last_receipt
    attempt = restore(next((tmp_path/'attempts').glob('attempt-*.json')))
    assert attempt['status'] == status
    assert event['new_attempt_wall_seconds'] == attempt['wall_seconds']
    assert attempt['backend_receipt'] == event['backend_receipt']
    assert not list(tmp_path.glob('*.json'))  # Failed output never becomes resumable.


def test_generation_integration_passes_layer_node_context_and_reuses(tmp_path):
    from experiments.scripts.tib_benchmark_adapter_generation import summarize_source
    from experiments.scripts.tib_benchmark_adapter_budget import Budget
    from experiments.scripts.tib_benchmark_output import select_delivered
    calls=[]
    def backend(batch,maximum,stage): calls.append(stage);return 'Notes.'
    wrapper=NodeCheckpointGenerator(backend,tmp_path,{'profile':'integration'},time.monotonic()+60)
    budget=Budget('encoder_decoder',100,20,decoder_cap=100)
    options=dict(encode=lambda text:list(text.encode()),decode=lambda ids:bytes(ids).decode(),
                 wrapper=lambda ids,stage:ids,generate=wrapper,budgets={s:budget for s in ('map','reduce','final')},
                 selector=select_delivered,word_cap=350)
    first=summarize_source('Lecture.',**options)
    second=summarize_source('Lecture.',**options)
    assert first['delivered_final']==second['delivered_final']=='Notes.'
    assert calls==['final'] and wrapper.events[-1]['status']=='reused'
