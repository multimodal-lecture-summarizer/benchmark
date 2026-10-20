"""Pilot source-only bindings and prospective technical checks; no metric inputs."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from .tib_benchmark_acceptance import ACCEPTANCE_POLICY, node_acceptance, record_acceptance
from . import tib_benchmark_acceptance as classifier_module
from . import tib_benchmark_generation_telemetry as diagnostic_module
from .tib_benchmark_checkpoint import digest
from .tib_benchmark_adapter_generation import summarize_source
from .tib_benchmark_adapter_transformers import native_bindings
from .tib_benchmark_generation_telemetry import generation_receipt
from .tib_benchmark_output import select_delivered, sentence_spans
from .tib_p4_generation_recovery import sha, safe_file
from .tib_pilot_resources import require

CANDIDATES = ['lead3', 'lexrank', 'bart', 'led', 'qwen3']
PREFERRED = {'bart': 'bart-control', 'led': 'led-ngram3', 'qwen3': 'qwen-r384'}


def source_only(value):
    if isinstance(value, dict):
        require(not any('reference' in str(k).lower() or 'abstract' in str(k).lower() for k in value),
                'Reference/abstract field forbidden')
        for item in value.values():
            source_only(item)
    elif isinstance(value, list):
        for item in value:
            source_only(item)


def validate_bundle(bundle):
    bundle = Path(bundle)
    manifest = json.loads((bundle/'pilot_manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        require(sha(safe_file(bundle, name)) == expected, 'Pilot bundle hash mismatch: ' + name)
    mandatory = {'pilot_contract.json', 'pilot_sources.jsonl', 'acceptance_policy.json',
                 'actual_recovery_receipt.json', 'actual_scorer_ready_receipt.json', 'expected_generation.json'}
    require(mandatory <= set(manifest['files']), 'Missing bound pilot dependency')
    contract = json.loads((bundle/'pilot_contract.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line in (bundle/'pilot_sources.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(contract['pilot_ids']) == len(set(contract['pilot_ids'])) == len(rows) == 40 and
            [r['record_id'] for r in rows] == contract['pilot_ids'], 'Exactly40sealed ordered pilot sources required')
    require(contract['candidate_order'] == CANDIDATES and contract['word_cap'] == 350 and
            [p['candidate_id'] for p in contract['profiles']] == CANDIDATES, 'Exactly five fixed pilot profiles/cap350')
    require(contract['staged_ids'] == ['valid:644', 'valid:341', 'valid:886'] and
            set(contract['staged_ids']) <= set(contract['pilot_ids']), 'Historical three IDs mismatch')
    for row in rows:
        source_only(row)
        required = {'record_id', 'source_normalized', 'source_normalized_sha256', 'source_stratum', 'attribution'}
        require(required <= set(row) <= required | {'source_words'},
                'Unexpected source schema')
        if 'source_words' in row:
            require(type(row['source_words']) is int and row['source_words'] == len(row['source_normalized'].split()),
                    'Source word count mismatch')
        require(row['source_normalized'] and hashlib.sha256(row['source_normalized'].encode()).hexdigest() ==
                row['source_normalized_sha256'] and contract['source_strata'][row['record_id']] == row['source_stratum'],
                'Source/stratum binding mismatch')
        require(not row['record_id'].startswith('test:'), 'Final-test ID forbidden')
    policy = json.loads((bundle/'acceptance_policy.json').read_text(encoding='utf-8'))
    require(all(policy.get(k) == v for k, v in ACCEPTANCE_POLICY.items()) and
            sha(bundle/'acceptance_policy.json') == contract['acceptance_policy_sha256'],
            'Frozen acceptance policy mismatch')
    for prefix in ('classifier', 'diagnostic_rules'):
        name, expected = policy[prefix+'_path'], policy[prefix+'_sha256']
        require(name in manifest['files'] and sha(safe_file(bundle, name)) == expected,
                'Frozen acceptance classifier/diagnostic hash mismatch')
        loaded = classifier_module if prefix == 'classifier' else diagnostic_module
        require(sha(loaded.__file__) == expected, 'Loaded acceptance classifier/diagnostic differs')
    original = bundle/'original_generation'
    require(sha(original/'bundle_manifest.json') == contract['original_bundle_manifest_sha256'], 'Historical bundle identity')
    old_manifest = json.loads((original/'bundle_manifest.json').read_text(encoding='utf-8'))
    for name, expected in old_manifest['files'].items():
        require(sha(safe_file(original, name)) == expected, 'Historical generation bytes mismatch')
    registry = json.loads((original/'development_trials.json').read_text(encoding='utf-8'))
    originals_cpu = {p['candidate_id']: p for p in json.loads((original/'candidate_profiles.json').read_text(encoding='utf-8'))['pipelines']}
    originals = {r['record_id']: r for r in map(json.loads, (original/'staged_sources.jsonl').read_text(encoding='utf-8').splitlines())}
    for row in rows:
        if row['record_id'] in contract['staged_ids']:
            require(row['source_normalized_sha256'] == originals[row['record_id']]['source_normalized_sha256'], 'Historical source changed')
    for profile in contract['profiles']:
        require(digest(profile['profile']) == profile['profile_sha256'], 'Pilot profile digest mismatch')
        if profile['candidate_id'] in PREFERRED:
            trial = next(t for t in registry['trials'] if t['trial_id'] == PREFERRED[profile['candidate_id']])
            require(profile['profile_id'] == trial['trial_id'] and profile['profile'] == trial['profile'], 'Historical profile changed')
        else:
            require(profile['profile'] == originals_cpu[profile['candidate_id']], 'Frozen CPU profile changed')
    recovered = json.loads((bundle/'actual_recovery_receipt.json').read_text(encoding='utf-8'))
    scorer = json.loads((bundle/'actual_scorer_ready_receipt.json').read_text(encoding='utf-8'))
    require(recovered.get('status') == 'PASS' and recovered.get('cross_session_recovery_verified') is True and
            recovered.get('new_generation_calls') == recovered.get('new_metric_calls') == 0, 'Actual recovery gate missing')
    require(scorer.get('status') == 'PASS' and not scorer.get('test_only', False), 'Actual scorer-ready gate missing')
    return contract, rows, sha(bundle/'pilot_manifest.json')


def validate_cpu(source, result, candidate):
    spans = sentence_spans(source)
    indices = result['selected_sentence_indices']
    require(indices == sorted(set(indices)) and indices and all(type(i) is int and 0 <= i < len(spans) for i in indices),
            'CPU selected sentence indices invalid')
    require(result['selected_source_spans'] == [list(spans[i]) for i in indices], 'CPU source spans mismatch')
    if candidate == 'lead3':
        require(indices == list(range(min(3, len(spans)))), 'Lead3 selection changed')
    raw = ' '.join(source[a:b] for a, b in result['selected_source_spans'])
    require(result['raw_final'] == raw and result['delivery'] == select_delivered(raw, 350) and
            result['delivered_final'] == result['delivery']['text'], 'CPU output/selector mismatch')
    decision = {'policy_version': ACCEPTANCE_POLICY['version'], 'status': 'completed', 'technical_errors': [],
                'warnings': [], 'usable_output': True, 'retain_in_denominator': True, 'automatic_retry': False,
                'factuality_verified': False, 'native_eos_applicable': False}
    return {'node_decisions': [decision], 'acceptance': record_acceptance([decision], result['delivered_final']),
            'technical_valid': True, 'source_spans_sha256': digest(result['selected_source_spans']),
            'canonical_source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'native_eos_applicable': False}


def validate_neural(source, result, events, tokenizer, profile, configuration):
    require(len(result['nodes']) == len(events) and bool(events), 'Missing native node events')
    decisions, evidence = [], []
    class Replay:
        def set_node_context(self, context):
            self.context = context

        def __call__(self, batch, maximum, stage):
            i = len(decisions)
            require(i < len(events), 'Unexpected replay node')
            node, native = result['nodes'][i], events[i]['backend_receipt']
            require(node['stage'] == stage and all(node[k] == self.context[k] for k in self.context), 'Native node context mismatch')
            require(node['wrapped_input_ids_sha256'] == digest(batch['input_ids']) and
                    node['padded_input_tokens'] == batch['padded_length'], 'Native wrapped IDs/padding mismatch')
            ids = native['generated_ids']
            require(native['generated_native_tokens'] == len(ids) and native['stage'] == stage and
                    native['device'] == 'cuda:0', 'Native count/stage/device mismatch')
            require(tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False) ==
                    node['output_text'], 'Native ID decoding mismatch')
            expected = generation_receipt(SimpleNamespace(generation_config=configuration), tokenizer,
                                          profile['decode'], ids, maximum, node['output_text'])
            require(all(native.get(k) == v for k, v in expected.items()), 'Native effective configuration/telemetry mismatch')
            proof = {'technical_valid': True, 'native_ids_sha256': digest(ids),
                     'wrapped_input_sha256': digest(batch['input_ids']), 'node_context': self.context}
            decisions.append(node_acceptance(node['output_text'], native, technical_valid=proof['technical_valid']))
            evidence.append(proof)
            return node['output_text']
    replay = summarize_source(source, **native_bindings(tokenizer, profile), generate=Replay(),
                              selector=select_delivered, word_cap=350)
    untimed = lambda nodes: [{k: v for k, v in n.items() if k != 'wall_seconds'} for n in nodes]
    require(untimed(replay['nodes']) == untimed(result['nodes']) and len(decisions) == len(events), 'Native lineage/hash mismatch')
    require(all(replay[k] == result[k] for k in replay if k != 'nodes'), 'Native delivery/source binding mismatch')
    return {'technical_valid': True, 'node_evidence': evidence, 'node_decisions': decisions,
            'acceptance': record_acceptance(decisions, result['delivered_final'], technical_valid=True)}
