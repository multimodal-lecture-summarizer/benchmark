from contextlib import nullcontext
import json
from types import SimpleNamespace

import pytest

from experiments.scripts import tib_pilot_runtime as pilot
from experiments.scripts.tib_benchmark_checkpoint import commit, restore
from experiments.scripts.tib_p4_generation_recovery import sha
from test_tib_pilot_resources import allocation, ledger
from test_tib_pilot_validation import pilot_bundle


def dependencies():
    return SimpleNamespace(validate_bundle=pilot.validate_bundle,
        resources=SimpleNamespace(clock=lambda: 200, cpu_clock=lambda: 20, boot_id='boot'),
        environment=lambda candidate: {'device_name': 'cpu', 'cpu_packages': {'fixture': True}},
        sample=lambda neural: nullcontext({'wall_seconds': 0, 'cpu_seconds': 0,
                                           'cuda_peak_reserved_bytes': None}))


def setup(tmp_path):
    bundle = tmp_path/'bundle'; contract, _ = pilot_bundle(bundle)
    output = tmp_path/'pilot'; output.mkdir()
    a = allocation(); ledger(output, a, bundle_sha256=sha(bundle/'pilot_manifest.json'))
    return bundle, output, a, contract


def test_complete_cpu40_denominator_injected_never_actual_pass(tmp_path):
    bundle, output, a, _ = setup(tmp_path)
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, dependencies=dependencies())
    assert result['status'] == 'HOLD' and result['test_only']
    assert result['summary']['denominator'] == result['summary']['successful'] == 40
    assert result['summary']['fresh'] == 40 and result['summary']['imported'] == 0
    assert result['new_generation_calls'] == result['new_metric_calls'] == result['automatic_retries'] == 0
    assert all(r['validation']['technical_valid'] and r['resources']['cuda_peak_reserved_bytes'] is None
               for r in result['records'].values())


def test_unallocated_fails_before_gate_models_or_outputs(tmp_path):
    deps = SimpleNamespace(validate_bundle=lambda _: pytest.fail('Must not inspect/load without allocation'))
    a = allocation(); a['state'] = 'REQUIRED_NO_START'
    result = pilot.run(tmp_path/'bundle', tmp_path/'new', tmp_path/'history', 'bart', allocation=a, dependencies=deps)
    assert result['status'] == 'HOLD' and 'REQUIRED_NO_START' in result['error']
    assert not (tmp_path/'new').exists()


def test_exhausted_quota_prevents_environment_or_weights(tmp_path):
    bundle, output, a, _ = setup(tmp_path)
    ledger(output, a, cpu_seconds=23*3600, bundle_sha256=sha(bundle/'pilot_manifest.json'))
    deps = dependencies(); deps.environment = lambda _: pytest.fail('No environment/model loading after failed quota')
    result = pilot.run(bundle, output/'bart', tmp_path/'old-store', 'bart', allocation=a, dependencies=deps)
    assert 'Reserved scorer CPU' in result['error']
    assert result['summary']['denominator'] == result['summary']['pending'] == 40
    assert not (output/'bart').exists()


@pytest.mark.parametrize('status', ['started', 'failed'])
def test_resume_never_retries_started_or_failed_records(tmp_path, monkeypatch, status):
    bundle, output, a, contract = setup(tmp_path)
    first = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, dependencies=dependencies())
    identifier = contract['pilot_ids'][0]
    path = output/'lead3'/'records'/(identifier.replace(':', '-')+'.json')
    record = restore(path); record['status'] = status; record['quality'] = None; commit(path, record)
    monkeypatch.setattr(pilot, 'lead3', lambda *a, **kw: pytest.fail('Attempted record must never retry'))
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a,
                       resume=True, dependencies=dependencies())
    assert result['summary']['denominator'] == 40 and result['summary']['successful'] == 39
    assert result['summary']['failed_or_interrupted'] == 1 and result['records'][identifier]['quality'] is None
    assert restore(path)['status'] == status


def test_resume_identity_and_runtime_mismatch_fail_closed(tmp_path):
    bundle, output, a, _ = setup(tmp_path)
    pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, dependencies=dependencies())
    # Leave one pending record so a prospective resume must derive live runtime.
    path = next((output/'lead3'/'records').glob('*.json')); path.unlink()
    deps = dependencies(); deps.environment = lambda _: {'device_name': 'different'}
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, resume=True, dependencies=deps)
    assert 'Saved pilot runtime mismatch' in result['error']
    identity = restore(output/'lead3'/'run_identity.json'); identity['profile_id'] = 'changed'
    commit(output/'lead3'/'run_identity.json', identity)
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, resume=True, dependencies=dependencies())
    assert 'resume identity mismatch' in result['error']


def test_terminal_candidate_resume_skips_environment_assets_and_model(tmp_path):
    bundle, output, a, _ = setup(tmp_path)
    pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, dependencies=dependencies())
    deps = dependencies()
    deps.environment = lambda _: pytest.fail('Cached terminal candidate must skip environment/model loading')
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, resume=True, dependencies=deps)
    assert result['execution_mode'] == 'cached_candidate_resume' and result['model_load_wall_seconds'] == 0
    assert result['cached_reused_records'] == 40 and result['fresh_new_outputs'] == result['new_generation_calls'] == 0
    assert result['summary']['denominator'] == 40 and result['test_only']


def test_partial_failure_keeps_original40_and_null_quality(tmp_path, monkeypatch):
    bundle, output, a, _ = setup(tmp_path)
    monkeypatch.setattr(pilot, 'lead3', lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('technical failure')))
    result = pilot.run(bundle, output/'lead3', tmp_path/'old-store', 'lead3', allocation=a, dependencies=dependencies())
    assert result['summary']['denominator'] == result['summary']['failed_or_interrupted'] == 40
    assert all(r['status'] == 'failed' and r['quality'] is None for r in result['records'].values())


def test_output_history_overlap_creates_nothing(tmp_path):
    with pytest.raises(ValueError, match='overlaps'):
        pilot.run(tmp_path/'bundle', tmp_path/'history'/'bad', tmp_path/'history', 'bart', allocation=allocation())
    assert not (tmp_path/'history').exists()


def test_backend_failure_keeps_spent_cost_attempts_and40_denominator(tmp_path, monkeypatch):
    import sys
    from experiments.scripts.tib_benchmark_checkpoint import digest
    from experiments.scripts.tib_benchmark_adapter_generation import summarize_source
    bundle, output, a, contract = setup(tmp_path)
    rows = [json.loads(line) for line in (bundle/'pilot_sources.jsonl').read_text().splitlines()]
    profile = next(p for p in contract['profiles'] if p['candidate_id'] == 'bart')
    profile['profile'].update(architecture='encoder_decoder', decode={})
    profile['profile_sha256'] = digest(profile['profile'])
    history = tmp_path/'history'; root = history/'bart'/'bart-control'
    commit(root/'nodes'/'old-node.json', {'key': {'stage': 'final'}})
    commit(root/'capacity-old.json', {'load_seconds': 1, 'records': [{'attempts': [
        {'key_sha256': 'old-node', 'new_attempt_wall_seconds': 1}]}]})
    (bundle/'expected_generation.json').write_text(json.dumps({'files': {
        p.relative_to(history).as_posix(): sha(p) for p in history.rglob('*') if p.is_file()}}))
    environment = {'device_name': 'Tesla T4', 'packages': {}, 'cuda_runtime': '13',
        'actual_parameter_dtype': 'float16', 'runtime_dependencies': {}, 'actual_attention_backend': 'eager',
        'actual_device_map': {}, 'asset_sha256': {}, 'tokenizer_class': 'Fake', 'device_memory_bytes': 1,
        'resolved_generation_config': {}}
    deps = dependencies()
    deps.validate_bundle = lambda _: (contract, rows, sha(bundle/'pilot_manifest.json'))
    deps.environment = lambda _: environment
    deps.load_assets = lambda *a: (object(), object())
    deps.admit_assets = lambda *a: {'test_only': True}
    deps.import_historical = lambda *a: (_ for _ in ()).throw(RuntimeError('synthetic import failure'))
    deps.sample = lambda neural: nullcontext({'wall_seconds': .02, 'cpu_seconds': .01,
        'peak_rss_bytes': 100, 'cuda_peak_reserved_bytes': 80, 'cuda_peak_allocated_bytes': 50,
        'minimum_available_host_bytes': 1000, 'peak_gpu_utilization_percent': 25})
    class FailingBackend:
        last_receipt = None
        def __call__(self, *args):
            self.last_receipt = {'partial_native_telemetry': True}
            raise RuntimeError('synthetic backend failure')
    monkeypatch.setattr(pilot.bindings, 'LoadedGenerator', lambda *a, **kw: FailingBackend())
    class SyntheticPipeline:
        def __call__(self, source, *, generate, **kwargs):
            generate.set_node_context({'layer': 0, 'node': 0, 'source_intervals': [[0, 1]]})
            generate({'input_ids': [1]}, 4, 'final')
    monkeypatch.setattr(pilot.generation, 'summarize_source', SyntheticPipeline())
    monkeypatch.setattr(pilot.bindings, 'native_bindings', lambda *a: {})
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(manual_seed=lambda _: None,
                        cuda=SimpleNamespace(manual_seed_all=lambda _: None)))
    result = pilot.run(bundle, output/'bart', history, 'bart', allocation=a, dependencies=deps)
    assert result['summary']['denominator'] == result['summary']['failed_or_interrupted'] == 40
    assert result['new_generation_calls'] == 37 and result['historical_store_unchanged_verified']
    fresh = [r for r in result['records'].values() if r['origin'] == 'fresh']
    assert len(fresh) == 37
    assert result['new_generation_wall_seconds'] == sum(r['new_generation_wall_seconds'] for r in fresh)
    for record in fresh:
        assert record['quality'] is None and record['resources']['peak_rss_bytes'] == 100
        assert record['resources']['cuda_peak_reserved_bytes'] == 80
        assert record['new_generation_calls'] == len(record['stage_resources']) == 1
        assert record['new_generation_wall_seconds'] > 0 and record['events'][0]['status'] == 'failed'
    before = result['new_generation_calls']
    resumed = pilot.run(bundle, output/'bart', history, 'bart', allocation=a, dependencies=deps, resume=True)
    assert resumed['new_generation_calls'] == 0 and resumed['summary']['denominator'] == 40
