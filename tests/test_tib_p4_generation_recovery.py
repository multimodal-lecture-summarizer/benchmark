"""CPU-only fail-closed contracts; no weights, downloads or generation calls."""
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_benchmark_checkpoint as checkpoints
from experiments.scripts import tib_benchmark_adapter_generation as generation
from experiments.scripts import tib_p4_generation_recovery as recovery
from experiments.scripts.tib_benchmark_adapter_budget import Budget


def test_inventory_catches_mutation_addition_and_missing(tmp_path):
    path = tmp_path / 'original.json'
    path.write_text('old')
    expected = {'original.json': recovery.sha(path)}
    assert recovery.verify_store(tmp_path, expected) == expected
    path.write_text('changed')
    with pytest.raises(ValueError, match='inventory/hash'):
        recovery.verify_store(tmp_path, expected)
    path.write_text('old')
    (tmp_path / 'extra').write_text('x')
    with pytest.raises(ValueError, match='inventory/hash'):
        recovery.verify_store(tmp_path, expected)
    (tmp_path / 'extra').unlink()
    path.unlink()
    with pytest.raises(ValueError, match='inventory/hash'):
        recovery.verify_store(tmp_path, expected)


@pytest.mark.parametrize('name', ['../escape', '/absolute', r'a\b'])
def test_rejects_unsafe_inventory_paths(tmp_path, name):
    with pytest.raises(ValueError, match='Unsafe'):
        recovery.safe_file(tmp_path, name)


def test_missing_node_never_reaches_original_write_path(tmp_path, monkeypatch):
    writes = []
    monkeypatch.setattr(checkpoints, 'commit', lambda *args: writes.append(args))
    counter = {'denied_generation_attempts': 0}
    api = SimpleNamespace(checkpoint=checkpoints)
    generator = recovery.readonly_generator(api, tmp_path / 'nodes', {'record_id': 'x'},
                                           time.monotonic() + 10, counter)
    generator.set_node_context({'layer': 0, 'node': 0})
    with pytest.raises(ValueError, match='Missing node'):
        generator({'input_ids': [1]}, 4, 'final')
    assert writes == [] and not (tmp_path / 'nodes').exists()
    assert counter['denied_generation_attempts'] == 0


def test_original_node_key_and_reuse_event_are_unchanged(tmp_path):
    api = SimpleNamespace(checkpoint=checkpoints)
    identity = {'record_id': 'valid:1', 'profile_sha256': 'frozen'}
    context = {'layer': 0, 'node': 0, 'source_intervals': [[0, 2]]}
    key = {**identity, **context, 'stage': 'final', 'max_new_tokens': 4,
           'wrapped_input_sha256': checkpoints.digest([1, 2])}
    path = tmp_path / (checkpoints.digest(key) + '.json')
    checkpoints.commit(path, {'key': key, 'output': 'saved', 'wall_seconds': 12.5, 'backend_receipt': {'ids': [3]}})
    before = recovery.sha(path)
    generator = recovery.readonly_generator(api, tmp_path, identity, time.monotonic() + 10,
                                           {'denied_generation_attempts': 0})
    generator.set_node_context(context)
    assert generator({'input_ids': [1, 2]}, 4, 'final') == 'saved'
    assert generator.events == [{'status': 'reused', 'key_sha256': checkpoints.digest(key),
                                 'new_attempt_wall_seconds': 0, 'original_wall_seconds': 12.5,
                                 'backend_receipt': {'ids': [3]}}]
    assert recovery.sha(path) == before and len(list(tmp_path.iterdir())) == 1


def test_identity_collision_fails_before_original_call(tmp_path):
    key = {'record_id': 'a', 'layer': 0, 'node': 0, 'stage': 'final',
           'max_new_tokens': 4, 'wrapped_input_sha256': checkpoints.digest([1])}
    checkpoints.commit(tmp_path / (checkpoints.digest(key) + '.json'), {'key': {**key, 'record_id': 'b'}})
    generator = recovery.readonly_generator(SimpleNamespace(checkpoint=checkpoints), tmp_path,
                                           {'record_id': 'a'}, time.monotonic() + 10,
                                           {'denied_generation_attempts': 0})
    generator.set_node_context({'layer': 0, 'node': 0})
    with pytest.raises(ValueError, match='identity mismatch'):
        generator({'input_ids': [1]}, 4, 'final')


def test_corrupt_envelope_fails_before_call(tmp_path):
    key = {'layer': 0, 'node': 0, 'stage': 'final', 'max_new_tokens': 4,
           'wrapped_input_sha256': checkpoints.digest([1])}
    (tmp_path / (checkpoints.digest(key) + '.json')).write_text('{"payload":{},"sha256":"wrong"}')
    generator = recovery.readonly_generator(SimpleNamespace(checkpoint=checkpoints), tmp_path, {},
                                           time.monotonic() + 10, {'denied_generation_attempts': 0})
    generator.set_node_context({'layer': 0, 'node': 0})
    with pytest.raises(ValueError, match='hash mismatch'):
        generator({'input_ids': [1]}, 4, 'final')


def test_hold_receipt_preserves_partial_cost_and_original_store(tmp_path):
    store = tmp_path / 'store'; store.mkdir()
    original = store / 'old.json'; original.write_text('frozen')
    expected = tmp_path / 'expected.json'
    expected.write_text(json.dumps({'files': {'old.json': recovery.sha(original)}}))
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    (bundle / 'bundle_manifest.json').write_text('{}')
    output = tmp_path / 'new'
    receipt = recovery.recover_generation(bundle, store, output, expected, dependencies=object())
    assert receipt['status'] == 'HOLD' and receipt['test_only']
    assert receipt['total_wall_seconds'] >= 0 and receipt['cpu_seconds'] >= 0
    assert receipt['store_unchanged_verified'] and receipt['new_generation_calls'] == 0
    assert not receipt['fresh_generation'] and not receipt['cross_session_survival_verified']
    assert json.loads((output / 'recovery_receipt.json').read_text()) == receipt
    assert original.read_text() == 'frozen'


def test_new_folder_required_and_store_overlap_forbidden(tmp_path):
    store = tmp_path / 'store'; store.mkdir()
    with pytest.raises(ValueError, match='new folder'):
        recovery.recover_generation(tmp_path, store, store, tmp_path / 'expected')
    with pytest.raises(ValueError, match='overlaps'):
        recovery.recover_generation(tmp_path / 'bundle', store, store / 'new', tmp_path / 'expected')


def test_wall_deadline_prevents_node_restore(tmp_path):
    generator = recovery.readonly_generator(SimpleNamespace(checkpoint=checkpoints), tmp_path, {},
                                           time.monotonic()-1, {'denied_generation_attempts': 0})
    with pytest.raises(ValueError, match='deadline'):
        generator({'input_ids': [1]}, 4, 'final')


def test_actual_invalid_context_creates_no_output_or_log(tmp_path, monkeypatch):
    other_store = tmp_path/'scorer-store'; other_store.mkdir()
    output = other_store/'generation'
    called = []
    def reject(context, destination, stage):
        called.append((context, destination, stage))
        assert not destination.exists()
        raise ValueError('Protected scorer store overlap')
    helper = SimpleNamespace(validate_stage_context=reject)
    monkeypatch.setitem(__import__('sys').modules, 'tib_p4_session_recovery', helper)
    with pytest.raises(ValueError, match='scorer store overlap'):
        recovery.recover_generation(tmp_path/'bundle', tmp_path/'generation-store', output,
                                    tmp_path/'expected.json', session_context=tmp_path/'context.json')
    assert called == [(tmp_path/'context.json', output, 'generation')]
    assert not output.exists() and list(other_store.iterdir()) == []


def test_actual_missing_context_creates_no_output(tmp_path):
    output = tmp_path/'new'
    with pytest.raises(ValueError, match='requires parent session context'):
        recovery.recover_generation(tmp_path/'bundle', tmp_path/'store', output, tmp_path/'expected.json')
    assert not output.exists()


def test_replay_uses_original_pipeline_and_compares_native_lineage(tmp_path):
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    (bundle / 'bundle_manifest.json').write_text('original')
    source = {'source_normalized': 'abc', 'source_normalized_sha256': __import__('hashlib').sha256(b'abc').hexdigest()}
    profile = {'decode': {}}
    trial = {'profile': profile, 'trial_id': 'bart-control'}
    bound = {'encode': lambda text: [ord(c) for c in text], 'decode': lambda ids: ''.join(map(chr, ids)),
             'wrapper': lambda ids, stage: ids,
             'budgets': {s: Budget(architecture='encoder_decoder', input_cap=32, max_new_tokens=4,
                                  decoder_cap=8, decoder_prefix_tokens=1, padding_multiple=1)
                         for s in ('map', 'reduce', 'final')}}
    selector = lambda text, cap: {'text': text}
    # Build a synthetic saved result; this is a test fixture, never real evidence.
    result = generation.summarize_source('abc', **bound, generate=lambda *a: 'z', selector=selector, word_cap=350)
    native = {'generated_ids': [122], 'generated_native_tokens': 1, 'stage': 'final', 'device': 'cuda:0'}
    identity = {'record_id': 'valid:1', 'source_sha256': source['source_normalized_sha256'],
                'profile_sha256': checkpoints.digest(profile), 'bundle_sha256': recovery.sha(bundle/'bundle_manifest.json'),
                'trial_id': 'bart-control', 'trial_registry_sha256': 'registry', 'runtime_sha256': 'runtime'}
    key = {**identity, 'layer': 0, 'node': 0, 'source_intervals': [[0, 3]], 'stage': 'final',
           'max_new_tokens': 4, 'wrapped_input_sha256': checkpoints.digest([97, 98, 99])}
    key_sha = checkpoints.digest(key)
    checkpoints.commit(tmp_path/'nodes'/f'{key_sha}.json', {'key': key, 'output': 'z', 'wall_seconds': 7,
                                                          'backend_receipt': native})
    diag = [{'backend_receipt': native}]
    result.update(reduction_diagnostic={'test': True}, generation_diagnostics=diag)
    checkpoints.commit(tmp_path/'valid-1.json', result)
    record = {'status': 'completed', 'record_id': 'valid:1', 'source_sha256': source['source_normalized_sha256'],
              'artifact_path': '/old/drive/valid-1.json', 'calls': {'final': 1}, 'source_tokens': 3, 'delivery': {},
              'generation_diagnostics': diag, 'nodes': [{k: v for k, v in n.items() if k != 'output_text'} for n in result['nodes']],
              'attempts': [{'status': 'completed', 'key_sha256': key_sha,
                            'new_attempt_wall_seconds': 7, 'backend_receipt': native}]}
    api = SimpleNamespace(checkpoint=checkpoints, generation=generation,
        bindings=SimpleNamespace(native_bindings=lambda *a: bound), output=SimpleNamespace(select_delivered=selector),
        runtime=SimpleNamespace(runtime_identity=lambda _: 'runtime'),
        diagnostics=SimpleNamespace(reduction_diagnostic=lambda _: {'test': True}),
        telemetry=SimpleNamespace(generation_receipt=lambda *a: {'generated_ids': [122]}))
    capacity = {'trial_registry_sha256': 'registry', 'resolved_generation_config': {}}
    tokenizer = SimpleNamespace(decode=lambda *a, **kw: 'z')
    recovered = recovery.replay_record(api, trial, capacity, record, source, bundle, tmp_path, tokenizer,
                                       time.monotonic()+10, {'denied_generation_attempts': 0})
    assert recovered['node_count'] == 1 and recovered['original_generation_wall_seconds'] == 7
    result['nodes'][0]['ordered_child_output_sha256'] = ['tampered']
    checkpoints.commit(tmp_path/'valid-1.json', result)
    with pytest.raises(ValueError, match='lineage mismatch'):
        recovery.replay_record(api, trial, capacity, record, source, bundle, tmp_path, tokenizer,
                               time.monotonic()+10, {'denied_generation_attempts': 0})


@pytest.mark.parametrize('changed_config', [None, 'resolved_model_config', 'resolved_generation_config'])
def test_complete_injected_replay_loads_three_models_once_and_remains_hold(tmp_path, monkeypatch, changed_config):
    bundle, store = tmp_path/'bundle', tmp_path/'store'
    bundle.mkdir(); store.mkdir()
    sources = [{'record_id': f'valid:{i}', 'source_normalized': str(i),
                'source_normalized_sha256': __import__('hashlib').sha256(str(i).encode()).hexdigest()}
               for i in range(3)]
    trials = [{'trial_id': f'{candidate}-{i}', 'candidate_id': candidate, 'profile': {'candidate': candidate},
               'profile_sha256': checkpoints.digest({'candidate': candidate}),
               'enabled_by_default': True, 'deferred': False}
              for candidate, count in [('bart', 1), ('led', 3), ('qwen3', 3)] for i in range(count)]
    registry = {'trials': trials, 'source_ids': [s['record_id'] for s in sources],
                'source_sha256': {s['record_id']: s['source_normalized_sha256'] for s in sources}}
    (bundle/'development_trials.json').write_text(json.dumps(registry))
    (bundle/'staged_sources.jsonl').write_text('\n'.join(map(json.dumps, sources)))
    manifest = {'files': {p.name: recovery.sha(p) for p in bundle.iterdir()},
                'registry_sha256': checkpoints.digest(registry), 'staged_pilot_ids': registry['source_ids']}
    (bundle/'bundle_manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(recovery, 'ORIGINAL_BUNDLE_SHA256', recovery.sha(bundle/'bundle_manifest.json'))
    for trial in trials:
        cap = {'status': 'completed', 'fresh_generation_only': True, 'T4_feasibility_verified': True,
               'candidate_id': trial['candidate_id'], 'trial_id': trial['trial_id'], 'profile': trial['profile'],
               'profile_sha256': trial['profile_sha256'], 'trial_registry_sha256': checkpoints.digest(registry),
               'records': [{'record_id': s['record_id'], 'wall_seconds': 2,
                            'attempts': [{'new_attempt_wall_seconds': 1}]} for s in sources],
               'load_seconds': 4, 'total_wall_seconds': 11,
               'resolved_model_config': {'id2label': {0: 'LABEL_0'}, 'other_field': {'nested': True}},
               'resolved_generation_config': {'num_beams': 4, 'extra_field': ['preserved']}}
        checkpoints.commit(store/trial['candidate_id']/trial['trial_id']/'capacity-old.json', cap)
    expected = tmp_path/'expected.json'
    expected.write_text(json.dumps({'files': {p.relative_to(store).as_posix(): recovery.sha(p)
                                            for p in store.rglob('*') if p.is_file()}}))
    loads, calls, models = [], [], []
    def load(profile, receipt):
        loads.append(profile['candidate'])
        # Live model keys are ints; commit/restore makes saved keys strings.
        receipt.update(resolved_model_config={'id2label': {0: 'LABEL_0'}, 'other_field': {'nested': True}},
                       resolved_generation_config={'num_beams': 4, 'extra_field': ['preserved']})
        if changed_config == 'resolved_model_config':
            receipt['resolved_model_config']['other_field']['nested'] = False
        elif changed_config == 'resolved_generation_config':
            receipt['resolved_generation_config']['extra_field'] = ['changed']
        model = SimpleNamespace(generate=lambda: pytest.fail('Original model.generate was used'))
        models.append(model)
        return model, object()
    def replay(*args):
        calls.append(args[1]['trial_id'])
        return {'node_count': 3 if len(calls) == 21 else 6, 'original_generation_wall_seconds': 1}
    monkeypatch.setattr(recovery, 'replay_record', replay)
    cuda = SimpleNamespace(is_available=lambda: True, get_device_name=lambda _: 'Tesla T4',
        get_device_properties=lambda _: SimpleNamespace(total_memory=16_000_000_000),
        reset_peak_memory_stats=lambda: None, max_memory_allocated=lambda: 10,
        max_memory_reserved=lambda: 20, empty_cache=lambda: None)
    deps = SimpleNamespace(api=SimpleNamespace(checkpoint=checkpoints,
        runtime=SimpleNamespace(load_runtime_assets=load, runtime_identity=lambda _: 'runtime')),
        torch=SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda='13.0')),
        psutil=SimpleNamespace(Process=lambda: SimpleNamespace(memory_info=lambda: SimpleNamespace(rss=100))),
        packages=recovery.PACKAGES)
    receipt = recovery.recover_generation(bundle, store, tmp_path/'new', expected, dependencies=deps)
    assert receipt['status'] == 'HOLD' and receipt['test_only']
    if changed_config is not None:
        assert 'Original loaded configuration differs: ' + changed_config in receipt['error']
        assert not receipt['source_runtime_compatible']
        assert calls == [] and loads == ['bart']
        assert receipt['store_unchanged_verified'] and receipt['new_generation_calls'] == 0
        return
    assert receipt['generation_replay_verified'] and receipt['source_runtime_compatible']
    assert receipt['reused_outputs'] == 21 and receipt['reused_nodes'] == 123
    assert len(receipt['original_profile_costs']) == 7
    assert receipt['original_profile_costs'][0] == {'trial_id': 'bart-0', 'original_load_seconds': 4,
        'original_total_wall_seconds': 11, 'original_record_wall_seconds_sum': 6,
        'original_node_generation_wall_seconds': 3}
    assert loads == ['bart', 'led', 'qwen3'] and len(calls) == 21
    assert receipt['store_unchanged_verified'] and receipt['new_generation_calls'] == 0
    with pytest.raises(RuntimeError, match='forbidden'):
        models[0].generate()
