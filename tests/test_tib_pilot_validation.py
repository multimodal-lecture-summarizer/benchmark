import copy
import json
from types import SimpleNamespace

import pytest

from experiments.scripts.tib_benchmark_acceptance import ACCEPTANCE_POLICY
from experiments.scripts.tib_benchmark_adapter_cpu import lead3
from experiments.scripts.tib_benchmark_adapter_generation import summarize_source
from experiments.scripts.tib_benchmark_adapter_transformers import native_bindings
from experiments.scripts.tib_benchmark_checkpoint import digest
from experiments.scripts.tib_benchmark_generation_telemetry import generation_receipt
from experiments.scripts.tib_benchmark_output import select_delivered
from experiments.scripts.tib_p4_generation_recovery import sha
from experiments.scripts.tib_pilot_validation import CANDIDATES, PREFERRED, validate_bundle, validate_cpu, validate_neural


def pilot_bundle(root):
    root.mkdir()
    staged = ['valid:644', 'valid:341', 'valid:886']
    ids = staged + [f'valid:{1000+i}' for i in range(37)]
    rows = [{'record_id': i, 'source_normalized': 'First sentence. Second sentence.',
             'source_normalized_sha256': __import__('hashlib').sha256(b'First sentence. Second sentence.').hexdigest(),
             'source_stratum': 'short', 'attribution': {'creator': 'fixture'}} for i in ids]
    original = root/'original_generation'; original.mkdir()
    cpu = [{'candidate_id': c} for c in CANDIDATES[:2]]
    trials = [{'candidate_id': c, 'trial_id': p, 'profile': {'candidate_id': c}}
              for c, p in PREFERRED.items()]
    (original/'candidate_profiles.json').write_text(json.dumps({'pipelines': cpu}))
    (original/'development_trials.json').write_text(json.dumps({'trials': trials}))
    (original/'staged_sources.jsonl').write_text('\n'.join(json.dumps(r) for r in rows[:3]))
    (original/'bundle_manifest.json').write_text(json.dumps({'files': {p.name: sha(p) for p in original.iterdir()}}))
    profiles = [{'candidate_id': c, 'profile_id': PREFERRED.get(c, c), 'profile': {'candidate_id': c},
                 'profile_sha256': digest({'candidate_id': c})} for c in CANDIDATES]
    policy = dict(ACCEPTANCE_POLICY)
    scripts = __import__('pathlib').Path(__file__).resolve().parents[1]/'experiments/scripts'
    for prefix, name in [('classifier', 'tib_benchmark_acceptance.py'),
                         ('diagnostic_rules', 'tib_benchmark_generation_telemetry.py')]:
        relative = 'experiments/scripts/'+name
        target = root/relative; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((scripts/name).read_bytes())
        policy.update({prefix+'_path': relative, prefix+'_sha256': sha(target)})
    policy['technical_contracts'] = ['All fields preserved in frozen enriched policy']
    (root/'acceptance_policy.json').write_text(json.dumps(policy))
    contract = {'pilot_ids': ids, 'staged_ids': staged, 'source_strata': dict.fromkeys(ids, 'short'),
        'candidate_order': CANDIDATES, 'word_cap': 350, 'profiles': profiles,
        'acceptance_policy_sha256': sha(root/'acceptance_policy.json'),
        'original_bundle_manifest_sha256': sha(original/'bundle_manifest.json')}
    (root/'pilot_contract.json').write_text(json.dumps(contract))
    (root/'pilot_sources.jsonl').write_text('\n'.join(map(json.dumps, rows)))
    (root/'expected_generation.json').write_text('{"files":{}}')
    (root/'actual_recovery_receipt.json').write_text(json.dumps({'status': 'PASS',
        'cross_session_recovery_verified': True, 'cross_session_survival_verified': False,
        'new_generation_calls': 0, 'new_metric_calls': 0}))
    (root/'actual_scorer_ready_receipt.json').write_text('{"status":"PASS","test_only":false}')
    refresh(root)
    return contract, rows


def refresh(root):
    (root/'pilot_manifest.json').write_text(json.dumps({'files': {p.relative_to(root).as_posix(): sha(p)
        for p in root.rglob('*') if p.is_file() and p.name != 'pilot_manifest.json'}}))


def test_source_only_exact40_and_five_bound_profiles(tmp_path):
    root = tmp_path/'bundle'; contract, rows = pilot_bundle(root)
    actual, sources, _ = validate_bundle(root)
    assert actual == contract and sources == rows


def test_actual_builder_contract_and_allocated_budget_shape_when_present():
    from pathlib import Path
    from experiments.scripts.tib_pilot_bundle import pilot_allocation
    from experiments.scripts.tib_pilot_resources import allocated
    assert allocated(pilot_allocation(), 11.5)['checkpoint_flush_seconds'] == 0
    root = Path(__file__).resolve().parents[1]/'research-data/tib-pilot40-261020-v1/package'
    if not root.exists():
        pytest.skip('Private source-only pilot package is local preparation evidence')
    contract, rows, _ = validate_bundle(root)
    assert len(rows) == 40 and contract['expected_matrix_cells'] == 200
    assert contract['expected_imported_neural_cells'] == 9


@pytest.mark.parametrize('change,match', [('reference', 'Reference'), ('duplicate', 'Exactly40'),
    ('stratum', 'stratum'), ('source_hash', 'Source/stratum'), ('profile', 'profile'), ('gate', 'recovery gate')])
def test_bundle_failures_even_when_file_manifest_recomputed(tmp_path, change, match):
    root = tmp_path/'bundle'; contract, rows = pilot_bundle(root)
    if change == 'reference': rows[0]['reference_summary'] = 'forbidden'
    if change == 'duplicate': rows[0] = rows[1]
    if change == 'stratum': rows[0]['source_stratum'] = 'long'
    if change == 'source_hash': rows[0]['source_normalized'] += ' changed'
    if change == 'profile': contract['profiles'][2]['profile']['changed'] = True
    if change == 'gate': (root/'actual_recovery_receipt.json').write_text('{"status":"HOLD"}')
    (root/'pilot_sources.jsonl').write_text('\n'.join(map(json.dumps, rows)))
    (root/'pilot_contract.json').write_text(json.dumps(contract)); refresh(root)
    with pytest.raises(ValueError, match=match): validate_bundle(root)


def test_cpu_lineage_spans_selector_and_eos_na():
    source = 'First sentence. Second sentence. Third sentence. Fourth sentence.'
    result = lead3(source, word_cap=350)
    actual = validate_cpu(source, result, 'lead3')
    assert actual['technical_valid'] and not actual['native_eos_applicable']
    result['selected_source_spans'][0][0] = 1
    with pytest.raises(ValueError, match='source spans'): validate_cpu(source, result, 'lead3')


@pytest.mark.parametrize('warning', [False, True])
def test_native_replay_context_lineage_and_warnings_retained(warning):
    source = 'abc'
    profile = {'candidate_id': 'bart', 'architecture': 'encoder_decoder', 'encoder_cap': 32, 'decoder_cap': 16,
        'padding_multiple': 1, 'decode': {}, **{s+'_max_new_tokens_including_EOS': 4 for s in ('map','reduce','final')}}
    tokenizer = SimpleNamespace(encode=lambda text, **kw: list(map(ord, text)),
        decode=lambda ids, **kw: ''.join(chr(i) for i in ids if i != 2),
        build_inputs_with_special_tokens=lambda ids: ids, eos_token_id=2)
    text = 'Z' if warning else 'Z.'
    ids = list(map(ord, text)) + ([] if warning else [2])
    configuration = {'eos_token_id': 2}
    native = generation_receipt(SimpleNamespace(generation_config=configuration), tokenizer, {}, ids, 4, text)
    native.update(generated_ids=ids, generated_native_tokens=len(ids), stage='final', device='cuda:0')
    result = summarize_source(source, **native_bindings(tokenizer, profile), generate=lambda *a: text,
                              selector=select_delivered, word_cap=350)
    actual = validate_neural(source, result, [{'backend_receipt': native}], tokenizer, profile, configuration)
    assert actual['technical_valid'] and actual['acceptance']['status'] == ('completed_with_warning' if warning else 'completed')
    assert actual['acceptance']['retain_in_denominator'] and not actual['acceptance']['automatic_retry']
    corrupt = copy.deepcopy(result); corrupt['nodes'][0]['source_intervals'] = [[0, 2]]
    with pytest.raises(ValueError, match='context mismatch'):
        validate_neural(source, corrupt, [{'backend_receipt': native}], tokenizer, profile, configuration)
    corrupt = copy.deepcopy(result); corrupt['nodes'][0]['output_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='lineage/hash'):
        validate_neural(source, corrupt, [{'backend_receipt': native}], tokenizer, profile, configuration)
