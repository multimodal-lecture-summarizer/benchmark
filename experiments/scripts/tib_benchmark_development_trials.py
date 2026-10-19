"""Bounded development profiles; never select models or authorize formal runs."""
from copy import deepcopy
from pathlib import Path

from experiments.scripts.tib_benchmark_checkpoint import digest, restore


def build_trial_registry(proposals, source_sha256=None):
    profiles = {p['candidate_id']: p for p in proposals['pipelines']}
    trials = []
    def add(identifier, candidate, *, reserve=None, ngram=None, concise=False, deferred=False):
        profile = deepcopy(profiles[candidate])
        if reserve is not None:
            profile['map_max_new_tokens_including_EOS'] = reserve
            profile['reduce_max_new_tokens_including_EOS'] = reserve
        if ngram is not None:
            profile['decode']['no_repeat_ngram_size'] = ngram
        if concise:
            profile['prompts']['map'] = (
                'Write compact English lecture notes. Preserve the main claims, definitions and key evidence. '
                'Use short factual bullets, avoid repetition, and finish each bullet. Return only notes.')
            profile['prompts']['reduce'] = (
                'Merge these English lecture notes into compact non-redundant factual bullets. '
                'Preserve distinct principal topics and claims from every input. Finish each bullet. Return only notes.')
        trials.append({'trial_id':identifier, 'candidate_id':candidate, 'profile':profile,
                       'profile_sha256':digest(profile), 'enabled_by_default':not deferred,
                       'deferred':deferred, 'repetitions':1})
    add('bart-control', 'bart')
    add('led-ngram0', 'led', ngram=0)
    add('led-ngram3', 'led', ngram=3)
    add('led-ngram4', 'led', ngram=4)
    add('qwen-r256', 'qwen3', reserve=256)
    add('qwen-r384', 'qwen3', reserve=384)
    add('qwen-concise-r256', 'qwen3', reserve=256, concise=True)
    add('qwen-r512', 'qwen3', reserve=512, deferred=True)
    return {'schema_version':1, 'scope':'three sealed staged development sources only',
            'word_cap':350, 'context_policy':'recompute native windows with wrappers/padding/output reserve',
            'maximum_trials':8, 'default_trials':7, 'maximum_neural_outputs':24,
            'default_neural_outputs':21, 'source_ids':['valid:644','valid:341','valid:886'],
            'source_sha256':dict(source_sha256 or {}),
            'node_seed_policy':'source_stage_layer_node_v1_seed1729',
            'intermediate_acceptance_policy':'observe_continue_with_flags_technical_only',
            'formal_intermediate_acceptance_policy_frozen':False,
            'quality_flags_cause_automatic_retries_or_exclusions':False,
            'deferred_512_policy':{'requires':'successful T4 qwen-r384 receipt for these three IDs',
                'minimum_measured_reserved_headroom_bytes':1073741824,
                'explicit_resource_review_flag_required':True,
                'headroom_is_operational_guard_not_capacity_guarantee':True},
            'selection_authorized':False, 'formal_benchmark':False, 'trials':trials}


def resolve_trial(registry, identifier, candidate, store, *, allow_deferred=False):
    matches = [t for t in registry['trials'] if t['trial_id'] == identifier]
    if len(matches) != 1 or matches[0]['candidate_id'] != candidate:
        raise ValueError('Unknown or mismatched development trial')
    trial = matches[0]
    if trial['profile_sha256'] != digest(trial['profile']):
        raise ValueError('Development profile hash mismatch')
    if trial['deferred']:
        if not allow_deferred:
            raise ValueError('Deferred trial requires explicit resource review flag')
        evidence = []
        prerequisite = next(t for t in registry['trials'] if t['trial_id'] == 'qwen-r384')
        for path in (Path(store)/'qwen3'/'qwen-r384').glob('capacity-*.json'):
            receipt = restore(path)
            if (receipt.get('trial_id') == 'qwen-r384' and receipt.get('T4_feasibility_verified') is True
                    and receipt.get('candidate_id') == 'qwen3'
                    and receipt.get('status') == 'completed'
                    and receipt.get('device_name') in ('Tesla T4','NVIDIA T4','NVIDIA Tesla T4')
                    and receipt.get('profile_sha256') == prerequisite['profile_sha256']
                    and receipt.get('trial_registry_sha256') == digest(registry)
                    and [r['record_id'] for r in receipt['records']] == registry['source_ids']
                    and bool(registry['source_sha256'])
                    and all(r.get('source_sha256') == registry['source_sha256'].get(r['record_id'])
                            for r in receipt['records'])
                    and all(r['status'] == 'completed' for r in receipt['records'])):
                total = receipt.get('device_memory_bytes')
                reserved = receipt.get('cuda_peak_reserved_bytes')
                if isinstance(total, int) and isinstance(reserved, int) and (
                    total-reserved >= registry['deferred_512_policy']['minimum_measured_reserved_headroom_bytes']):
                    evidence.append(path)
        if not evidence:
            raise ValueError('Deferred512 needs verified384 T4 capacity and measured memory headroom')
    return trial


def development_node_seed(key):
    # Same predeclared seed for corresponding source/stage/layer/node across trials;
    # windows can differ, so this is reproducibility, not a matched-content claim.
    identity = {field:key[field] for field in ('record_id','stage','layer','node')}
    return int(digest({'base_seed':1729, **identity})[:8], 16)
