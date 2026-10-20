"""Read-only P4.1 checkpoint replay using the unchanged original generation bundle.

Standalone deployment: copy this file to tools/, put only the ORIGINAL bundle on
PYTHONPATH. No generation, checkpoint repair, scoring or model selection occurs.
"""
import argparse
from collections import Counter
import gc
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import sys
import threading
import time
from types import SimpleNamespace


ORIGINAL_BUNDLE_SHA256 = '5c7e3c967aa7550ab78224c0699f312499943c1b8e491094d6880056fe176eaf'
PACKAGES = {'torch': '2.11.0+cu130', 'numpy': '2.1.3', 'transformers': '4.57.6',
            'huggingface-hub': '0.36.2', 'accelerate': '1.15.0',
            'tokenizers': '0.22.2', 'safetensors': '0.8.0', 'psutil': '5.9.5'}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_file(root, relative):
    name = PurePosixPath(relative)
    require(not name.is_absolute() and '..' not in name.parts and '\\' not in relative,
            'Unsafe relative path: ' + relative)
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file() and not (root / relative).is_symlink(),
            'Missing or unsafe file: ' + relative)
    return path


def verify_store(store, expected):
    require(bool(expected), 'Empty expected checkpoint inventory')
    actual = {p.relative_to(store).as_posix(): sha(safe_file(store, p.relative_to(store).as_posix()))
              for p in store.rglob('*') if p.is_file()}
    require(actual == expected, 'Checkpoint inventory/hash mismatch')
    return actual


def original_api(bundle):
    """Reject accidentally importing the current working tree's generation code."""
    names = {'checkpoint': 'tib_benchmark_checkpoint', 'runtime': 'tib_benchmark_capacity_runtime',
             'generation': 'tib_benchmark_adapter_generation', 'bindings': 'tib_benchmark_adapter_transformers',
             'output': 'tib_benchmark_output', 'diagnostics': 'tib_benchmark_reduction_diagnostics',
             'telemetry': 'tib_benchmark_generation_telemetry'}
    modules = {}
    for key, name in names.items():
        module = importlib.import_module('experiments.scripts.' + name)
        require(Path(module.__file__).resolve().is_relative_to(bundle.resolve()),
                'Generation imports must come from original bundle: ' + name)
        modules[key] = module
    return SimpleNamespace(**modules)


def readonly_generator(api, root, identity, deadline, counter):
    """Precheck before original __call__; never let it enter its write path."""
    def deny(*args, **kwargs):
        counter['denied_generation_attempts'] += 1
        raise RuntimeError('HOLD: generation forbidden during recovery')

    class ReadOnly(api.checkpoint.NodeCheckpointGenerator):
        def __call__(self, batch, maximum, stage):
            require(time.monotonic() < self.deadline, 'Recovery wall deadline reached')
            require(self.context is not None, 'Missing original node context')
            key = {**self.identity, **self.context, 'stage': stage, 'max_new_tokens': maximum,
                   'wrapped_input_sha256': api.checkpoint.digest(batch['input_ids'])}
            path = self.root / (api.checkpoint.digest(key) + '.json')
            require(path.is_file(), 'Missing node checkpoint; generation forbidden')
            require(api.checkpoint.restore(path)['key'] == key, 'Node identity mismatch')
            return super().__call__(batch, maximum, stage)

    return ReadOnly(deny, root, identity, deadline, before_call=deny)


def _untimed(nodes):
    return [{k: v for k, v in node.items() if k != 'wall_seconds'} for node in nodes]


def replay_record(api, trial, capacity, record, source, bundle, root, tokenizer, deadline, counter):
    digest, restore = api.checkpoint.digest, api.checkpoint.restore
    require(record['status'] == 'completed' and record['source_sha256'] == source['source_normalized_sha256'],
            'Original source/record binding mismatch')
    artifact = restore(safe_file(root, PurePosixPath(record['artifact_path']).name))
    identity = {'record_id': record['record_id'], 'source_sha256': record['source_sha256'],
                'profile_sha256': digest(trial['profile']), 'bundle_sha256': sha(bundle / 'bundle_manifest.json'),
                'trial_id': trial['trial_id'], 'trial_registry_sha256': capacity['trial_registry_sha256'],
                'runtime_sha256': api.runtime.runtime_identity(capacity)}
    generator = readonly_generator(api, root / 'nodes', identity, deadline, counter)
    started, cpu = time.perf_counter(), time.process_time()
    result = api.generation.summarize_source(source['source_normalized'],
            **api.bindings.native_bindings(tokenizer, trial['profile']), generate=generator,
            selector=api.output.select_delivered, word_cap=350)
    require(_untimed(result['nodes']) == _untimed(artifact['nodes']), 'Native window/node/lineage mismatch')
    require(_untimed(record['nodes']) == _untimed([{k: v for k, v in n.items() if k != 'output_text'}
                                                 for n in artifact['nodes']]), 'Capacity node lineage mismatch')
    require({k: result[k] for k in result if k != 'nodes'} ==
            {k: artifact[k] for k in result if k != 'nodes'}, 'Delivered/raw output mismatch')
    require(record['calls'] == dict(Counter(n['stage'] for n in result['nodes'])) and
            record['source_tokens'] == result['source_token_count'] and
            record['delivery'] == {k: v for k, v in result['delivery'].items() if k != 'text'},
            'Original record summary mismatch')
    require(artifact['reduction_diagnostic'] == api.diagnostics.reduction_diagnostic(artifact),
            'Original reduction diagnostic mismatch')
    require(artifact['generation_diagnostics'] == record['generation_diagnostics'], 'Diagnostic mismatch')
    require(len(generator.events) == len(record['attempts']) == len(result['nodes']), 'Node count mismatch')
    for event, old, node in zip(generator.events, record['attempts'], result['nodes']):
        require(event['status'] == 'reused' and event['new_attempt_wall_seconds'] == 0 and
                old['status'] == 'completed' and event['key_sha256'] == old['key_sha256'] and
                event['backend_receipt'] == old['backend_receipt'] and
                event['original_wall_seconds'] == old['new_attempt_wall_seconds'], 'Node reuse invariant mismatch')
        native = event['backend_receipt']
        ids = native['generated_ids']
        require(native['stage'] == node['stage'] and native['device'] == 'cuda:0' and
                0 < len(ids) == native['generated_native_tokens'], 'Native IDs/length mismatch')
        require(tokenizer.decode(ids, skip_special_tokens=True, clean_up_tokenization_spaces=False) ==
                node['output_text'], 'Native generated ID decoding mismatch')
        checkpoint = restore(root / 'nodes' / (event['key_sha256'] + '.json'))
        require(checkpoint['output'] == node['output_text'] and checkpoint['backend_receipt'] == native,
                'Original node output/telemetry mismatch')
        telemetry = api.telemetry.generation_receipt(
            SimpleNamespace(generation_config=capacity['resolved_generation_config']), tokenizer,
            trial['profile']['decode'], ids, checkpoint['key']['max_new_tokens'], node['output_text'])
        require(all(native.get(k) == v for k, v in telemetry.items()), 'Original effective decode telemetry mismatch')
    return {'record_id': record['record_id'], 'trial_id': trial['trial_id'], 'status': 'reused',
            'node_count': len(generator.events), 'events': generator.events,
            'original_generation_wall_seconds': sum(e['original_wall_seconds'] for e in generator.events),
            'new_generation_wall_seconds': 0, 'replay_wall_seconds': time.perf_counter() - started,
            'replay_cpu_seconds': time.process_time() - cpu,
            'raw_final_sha256': hashlib.sha256(result['raw_final'].encode()).hexdigest(),
            'delivered_final_sha256': hashlib.sha256(result['delivered_final'].encode()).hexdigest()}


def recover_generation(bundle, store, output, expected, wall_hours=11.5, *, dependencies=None, session_context=None):
    """Write a NEW receipt; injected dependencies can never establish actual PASS."""
    bundle, store, output, expected = map(Path, (bundle, store, output, expected))
    require(not output.exists(), 'Recovery output must be a new folder')
    require(not output.resolve().is_relative_to(store.resolve()) and
            not output.resolve().is_relative_to(bundle.resolve()), 'Output overlaps immutable inputs')
    require(0 < wall_hours <= 11.5, 'Recovery wall limit must be <=11.5 hours')
    stage_context = None
    if dependencies is None:
        require(session_context is not None, 'Actual recovery requires parent session context')
        # Validate every protected store before even creating an output folder.
        # The sibling helper lives outside the unchanged generation namespace.
        context_api = importlib.import_module('tib_p4_session_recovery')
        stage_context = context_api.validate_stage_context(session_context, output, 'generation')
    output.mkdir(parents=True)
    started, cpu = time.monotonic(), time.process_time()
    deadline = started + wall_hours * 3600
    receipt = {'status': 'HOLD', 'stage': 'cached_generation_recovery', 'fresh_generation': False,
               'cross_session_survival_verified': False, 'formal_benchmark': False,
               'selection_authorized': False, 'new_generation_calls': 0, 'new_generation_wall_seconds': 0,
               'denied_generation_attempts': 0, 'test_only': dependencies is not None,
               'source_runtime_compatible': False,
               'records': [], 'model_loads': [], 'original_profile_costs': [], 'wall_hours_limit': wall_hours}
    if stage_context is not None:
        receipt['stage_session_context'] = stage_context
    stop, thread, process, torch, model, tokenizer = threading.Event(), None, None, None, None, None
    inventory = None
    log = (output / 'recovery.log').open('w', encoding='utf-8')

    def progress(message):
        log.write(message + '\n'); log.flush()
        print(message, flush=True)

    try:
        expected_data = json.loads(expected.read_text(encoding='utf-8'))
        inventory = expected_data['files']
        verify_store(store, inventory)
        require(sha(bundle / 'bundle_manifest.json') == ORIGINAL_BUNDLE_SHA256, 'Original bundle identity mismatch')
        manifest = json.loads((bundle / 'bundle_manifest.json').read_text())
        for name, value in manifest['files'].items():
            require(sha(safe_file(bundle, name)) == value, 'Original bundle hash mismatch: ' + name)
        if 'bundle_files' in expected_data:
            for name, value in expected_data['bundle_files'].items():
                require(sha(safe_file(bundle, name)) == value, 'Expected bundle file mismatch: ' + name)
        receipt['original_bundle_manifest_sha256'] = sha(bundle / 'bundle_manifest.json')
        progress('Original store and generation bundle hashes verified')
        api = dependencies.api if dependencies else original_api(bundle)
        if dependencies:
            torch, psutil = dependencies.torch, dependencies.psutil
        else:
            import torch
            import psutil
        process = psutil.Process()
        peak = [process.memory_info().rss]
        def monitor():
            while not stop.wait(.1):
                peak[0] = max(peak[0], process.memory_info().rss)
        thread = threading.Thread(target=monitor, daemon=True); thread.start()
        packages = dependencies.packages if dependencies else {p: importlib.metadata.version(p) for p in PACKAGES}
        require(packages == PACKAGES, 'Exact original generation packages required')
        require(torch.cuda.is_available(), 'Actual CUDA required')
        device = torch.cuda.get_device_name(0)
        require(device in ('Tesla T4', 'NVIDIA T4', 'NVIDIA Tesla T4'), 'Actual T4 required')
        require(Path('/content').is_dir() and 'google.colab' in sys.modules or dependencies is not None,
                'Actual Colab session required')
        torch.cuda.reset_peak_memory_stats()
        receipt.update(device_name=device, packages=packages, cuda_runtime=torch.version.cuda)
        registry = json.loads((bundle / 'development_trials.json').read_text())
        require(api.checkpoint.digest(registry) == manifest['registry_sha256'], 'Registry identity mismatch')
        trials = [t for t in registry['trials'] if t['enabled_by_default'] and not t['deferred']]
        require(len(trials) == 7 and len({t['candidate_id'] for t in trials}) == 3, 'Expected seven profiles/three models')
        sources = [json.loads(line) for line in (bundle / 'staged_sources.jsonl').read_text().splitlines()]
        require([s['record_id'] for s in sources] == registry['source_ids'] == manifest['staged_pilot_ids'] and
                len(sources) == 3, 'Original three-source order mismatch')
        for source in sources:
            require(hashlib.sha256(source['source_normalized'].encode()).hexdigest() ==
                    source['source_normalized_sha256'] == registry['source_sha256'][source['record_id']],
                    'Source SHA mismatch')
            require(not any('reference' in k or 'abstract' in k for k in source), 'Reference entered generation')
        for candidate in dict.fromkeys(t['candidate_id'] for t in trials):
            group = [t for t in trials if t['candidate_id'] == candidate]
            current = {'device_name': device, 'packages': {p: packages[p] for p in
                       ('torch', 'transformers', 'huggingface-hub', 'numpy')},
                       'cuda_runtime': torch.version.cuda,
                       'device_memory_bytes': torch.cuda.get_device_properties(0).total_memory}
            progress('Loading original pinned assets: ' + candidate)
            require(time.monotonic() < deadline, 'Recovery wall deadline reached')
            load_started = time.perf_counter()
            model, tokenizer = api.runtime.load_runtime_assets(group[0]['profile'], current)
            def deny_model(*args, **kwargs):
                receipt['denied_generation_attempts'] += 1
                raise RuntimeError('HOLD: model.generate is forbidden')
            model.generate = deny_model
            receipt['model_loads'].append({'candidate_id': candidate, 'wall_seconds': time.perf_counter()-load_started,
                                         'runtime_sha256': api.runtime.runtime_identity(current),
                                         'runtime': current})
            for trial in group:
                root = store / candidate / trial['trial_id']
                paths = list(root.glob('capacity-*.json'))
                require(len(paths) == 1, 'Expected one original capacity receipt per profile')
                capacity = api.checkpoint.restore(paths[0])
                require(capacity['status'] == 'completed' and capacity['fresh_generation_only'] and
                        capacity['T4_feasibility_verified'] and capacity['candidate_id'] == candidate and
                        capacity['trial_id'] == trial['trial_id'] and capacity['profile'] == trial['profile'] and
                        capacity['profile_sha256'] == trial['profile_sha256'] == api.checkpoint.digest(trial['profile']) and
                        capacity['trial_registry_sha256'] == api.checkpoint.digest(registry), 'Original capacity binding mismatch')
                require(api.runtime.runtime_identity(current) == api.runtime.runtime_identity(capacity),
                        'Independently loaded runtime differs from original capacity fingerprint')
                for field in ('resolved_model_config', 'resolved_generation_config'):
                    # Compare the complete persisted JSON representation: live HF
                    # configs can have integer keys that JSON stores as strings.
                    # Preserve every field and never alter checkpoint identities.
                    loaded_config = json.loads(json.dumps(current[field], allow_nan=False))
                    saved_config = json.loads(json.dumps(capacity[field], allow_nan=False))
                    require(loaded_config == saved_config, 'Original loaded configuration differs: ' + field)
                require([r['record_id'] for r in capacity['records']] == registry['source_ids'], 'Capacity record order mismatch')
                receipt['original_profile_costs'].append({
                    'trial_id': trial['trial_id'], 'original_load_seconds': capacity['load_seconds'],
                    'original_total_wall_seconds': capacity['total_wall_seconds'],
                    'original_record_wall_seconds_sum': sum(r['wall_seconds'] for r in capacity['records']),
                    'original_node_generation_wall_seconds': sum(
                        a['new_attempt_wall_seconds'] for r in capacity['records'] for a in r['attempts'])})
                for record, source in zip(capacity['records'], sources):
                    receipt['records'].append(replay_record(api, trial, capacity, record, source, bundle,
                                                           root, tokenizer, deadline, receipt))
                    progress('Reused ' + trial['trial_id'] + ' / ' + record['record_id'])
            model = tokenizer = None
            gc.collect(); torch.cuda.empty_cache()
        receipt.update(reused_outputs=len(receipt['records']),
                       reused_nodes=sum(r['node_count'] for r in receipt['records']),
                       original_generation_wall_seconds=sum(r['original_generation_wall_seconds'] for r in receipt['records']))
        require(receipt['reused_outputs'] == 21 and receipt['reused_nodes'] == 123 and
                receipt['denied_generation_attempts'] == 0, 'Expected21outputs/123nodes/zero generation attempts')
        require(time.monotonic() < deadline, 'Recovery wall deadline reached')
        receipt['generation_replay_verified'] = True
        receipt['source_runtime_compatible'] = True
        if dependencies is None:
            receipt['status'] = 'PASS'
    except Exception as error:
        receipt.update(status='HOLD', error=f'{type(error).__name__}: {error}')
        progress(receipt['error'])
    finally:
        stop.set()
        if thread:
            thread.join()
            receipt['sampled_peak_process_rss_bytes'] = peak[0]
        if torch is not None and torch.cuda.is_available():
            receipt.update(cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                           cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
            model = tokenizer = None
            gc.collect(); torch.cuda.empty_cache()
        try:
            if inventory is not None:
                verify_store(store, inventory)
                receipt['store_unchanged_verified'] = True
        except Exception as error:
            receipt.update(status='HOLD', store_unchanged_verified=False, integrity_error=str(error))
        receipt.update(total_wall_seconds=time.monotonic()-started, cpu_seconds=time.process_time()-cpu,
                       overhead_includes='hashing/model load/tokenization/native replay/resource monitoring')
        (output / 'recovery_receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding='utf-8')
        progress('Recovery status: ' + receipt['status'])
        log.close()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'store', 'output', 'expected'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--wall-hours', type=float, default=11.5)
    parser.add_argument('--session-context', type=Path)
    args = parser.parse_args()
    receipt = recover_generation(args.bundle, args.store, args.output, args.expected, args.wall_hours,
                                 session_context=args.session_context)
    return 0 if receipt['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
