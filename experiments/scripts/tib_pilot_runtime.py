"""Five frozen candidates on the sealed40-ID technical pilot; no scores/search."""
import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
from types import SimpleNamespace

from . import tib_benchmark_checkpoint as checkpoint
from . import tib_benchmark_capacity_runtime as runtime
from . import tib_benchmark_adapter_generation as generation
from . import tib_benchmark_adapter_transformers as bindings
from . import tib_benchmark_output as delivery
from . import tib_benchmark_reduction_diagnostics as diagnostics
from . import tib_benchmark_generation_telemetry as telemetry
from .tib_benchmark_adapter_cpu import lead3, lexrank
from .tib_benchmark_development_trials import development_node_seed
from .tib_p4_generation_recovery import replay_record, verify_store, sha
from .tib_pilot_resources import PilotBudget, ResourceSample, allocated, atomic_json, require, runtime_environment, admit_assets
from .tib_pilot_validation import CANDIDATES, PREFERRED, validate_bundle, validate_cpu, validate_neural


def original_api(bundle):
    """The pilot ships byte-identical frozen modules; verify before old-key replay."""
    modules = dict(checkpoint=checkpoint, runtime=runtime, generation=generation, bindings=bindings,
                   output=delivery, diagnostics=diagnostics, telemetry=telemetry)
    manifest = json.loads((bundle/'bundle_manifest.json').read_text(encoding='utf-8'))
    for module in modules.values():
        name = 'experiments/scripts/' + Path(module.__file__).name
        require(sha(module.__file__) == manifest['files'][name], 'Frozen adapter differs from original: ' + name)
    return SimpleNamespace(**modules)


def import_historical(bundle, store, row, profile, environment, tokenizer, deadline):
    original = bundle/'original_generation'
    api = original_api(original)
    root = store/profile['candidate_id']/profile['profile_id']
    capacities = list(root.glob('capacity-*.json'))
    require(len(capacities) == 1, 'Unique historical capacity required')
    old = checkpoint.restore(capacities[0])
    registry = json.loads((original/'development_trials.json').read_text(encoding='utf-8'))
    trial = next(t for t in registry['trials'] if t['trial_id'] == profile['profile_id'])
    require(old['status'] == 'completed' and old['T4_feasibility_verified'] and old['fresh_generation_only'] and
            old['profile'] == profile['profile'] and old['profile_sha256'] == profile['profile_sha256'] and
            old['trial_registry_sha256'] == checkpoint.digest(registry), 'Historical capacity/profile binding')
    require(runtime.runtime_identity(environment) == runtime.runtime_identity(old), 'Historical runtime identity mismatch')
    for key in ('resolved_model_config', 'resolved_generation_config'):
        require(json.loads(json.dumps(environment[key], allow_nan=False)) == old[key], 'Historical persisted config mismatch')
    record = next(r for r in old['records'] if r['record_id'] == row['record_id'])
    replay = replay_record(api, trial, old, record, row, original, root, tokenizer, deadline,
                           {'denied_generation_attempts': 0})
    artifact = checkpoint.restore(root/PurePosixPath(record['artifact_path']).name)
    return artifact, replay['events'], {'original_record_wall_seconds': record['wall_seconds'],
        'original_node_generation_wall_seconds': replay['original_generation_wall_seconds'],
        'original_profile_load_seconds': old['load_seconds'], 'replay_wall_seconds': replay['replay_wall_seconds']}


def summary(records, ids):
    counts = Counter(records.get(i, {}).get('status', 'pending') for i in ids)
    return {'denominator': len(ids), 'status_counts': dict(counts),
            'successful': counts['completed'] + counts['completed_with_warning'],
            'failed_or_interrupted': counts['failed'] + counts['started'], 'pending': counts['pending'],
            'imported': sum(r.get('origin') == 'historical_import' for r in records.values()),
            'fresh': sum(r.get('origin') == 'fresh' and r['status'] in ('completed', 'completed_with_warning')
                         for r in records.values()), 'NULL_quality_for_failures': True}


def run(bundle, output, historical_store, candidate, *, resume=False, wall_hours=11.5, allocation, dependencies=None):
    bundle, output, historical_store = map(Path, (bundle, output, historical_store))
    require(candidate in CANDIDATES, 'Unknown pilot candidate')
    for protected in (bundle, historical_store):
        require(not output.resolve().is_relative_to(protected.resolve()) and
                not protected.resolve().is_relative_to(output.resolve()), 'Pilot output overlaps immutable inputs')
    require(not (output.parent/'resource_ledger.json').resolve().is_relative_to(historical_store.resolve()), 'Ledger overlaps history')
    receipt = {'status': 'HOLD', 'scope': 'technical_pilot40_only', 'candidate_id': candidate,
        'test_only': dependencies is not None, 'formal_benchmark': False, 'selection_authorized': False,
        'new_metric_calls': 0, 'records': {}, 'new_generation_calls': 0, 'new_generation_wall_seconds': 0,
        'automatic_retries': 0,
        'quality_evaluation': None, 'fresh_latency_excludes_imported': True}
    started, budget, model, tokenizer, history_hashes = time.monotonic(), None, None, None, None
    original_commit = checkpoint.commit
    try:
        allocated(allocation, wall_hours)
        contract, sources, bundle_sha = (dependencies.validate_bundle(bundle) if dependencies else validate_bundle(bundle))
        if dependencies is None:
            original_api(bundle/'original_generation')
        budget = PilotBudget(output, allocation, candidate, wall_hours,
                             dependencies=dependencies.resources if dependencies else None)
        require(budget.ledger.get('bundle_sha256') == bundle_sha, 'Pilot bundle/ledger identity mismatch')
        budget.guard()
        profile = next(p for p in contract['profiles'] if p['candidate_id'] == candidate)
        binding = {'pilot_bundle_sha256': bundle_sha, 'profile_sha256': profile['profile_sha256'],
            'profile_id': profile['profile_id'], 'acceptance_policy_sha256': contract['acceptance_policy_sha256'],
            'allocation_sha256': checkpoint.digest(allocation), 'candidate_id': candidate}
        if output.exists():
            require(resume, 'Existing output requires explicit resume')
            require(checkpoint.restore(output/'run_identity.json') == binding, 'Pilot resume identity mismatch')
        else:
            require(not resume, 'Resume output missing')
            output.mkdir(parents=True)
            checkpoint.commit(output/'run_identity.json', binding)
        def measured_commit(path, payload):
            require(Path(path).resolve().is_relative_to(output.resolve()), 'Pilot checkpoint write outside candidate output')
            size_before = Path(path).stat().st_size if Path(path).exists() else 0
            t = time.perf_counter()
            value = original_commit(path, payload)
            budget.flush(bytes_added=max(0, Path(path).stat().st_size-size_before), flush_seconds=time.perf_counter()-t)
            return value
        checkpoint.commit = measured_commit
        if not resume:
            receipt['store_probe'] = checkpoint.probe_store(output/'probe')
        for row in sources:
            saved = output/'records'/(row['record_id'].replace(':', '-')+'.json')
            if saved.exists():
                existing = checkpoint.restore(saved)
                require(existing['binding'] == binding and existing['source_sha256'] == row['source_normalized_sha256'],
                        'Saved pilot record identity mismatch')
                require(existing['status'] in ('started', 'failed', 'completed', 'completed_with_warning'), 'Invalid saved record status')
                receipt['records'][row['record_id']] = existing
        # Validate every envelope on resume; no corrupt or orphan attempt is repaired.
        if resume:
            for path in output.rglob('*.json'):
                if path.name != 'candidate_receipt.json':
                    checkpoint.restore(path)
        if resume and len(receipt['records']) == 40 and all(r['status'] in (
                'completed', 'completed_with_warning', 'failed') for r in receipt['records'].values()):
            runtime_ids = {r['runtime_sha256'] for r in receipt['records'].values()}
            require(len(runtime_ids) == 1, 'Cached candidate has inconsistent runtime identities')
            for row in sources:
                saved = receipt['records'][row['record_id']]
                require(saved['quality'] is None, 'Pilot quality must remain NULL')
                if saved['status'] != 'failed':
                    result = saved['result']
                    require(saved['validation']['acceptance']['status'] == saved['status'] and
                            result['delivery'] == delivery.select_delivered(result['raw_final'], 350) and
                            result['delivered_final'] == result['delivery']['text'], 'Cached acceptance/delivery mismatch')
                    for node in result.get('nodes', []):
                        require(node['canonical_source_sha256'] == row['source_normalized_sha256'] and
                                hashlib.sha256(node['output_text'].encode()).hexdigest() == node['output_sha256'],
                                'Cached node/source/output hash mismatch')
            receipt.update(runtime_sha256=next(iter(runtime_ids)), execution_mode='cached_candidate_resume',
                           runtime_verification='prior bound runtime; no current model reload or fresh latency claim',
                           model_load_wall_seconds=0, cached_reused_records=40, fresh_new_outputs=0)
            receipt['summary'] = summary(receipt['records'], contract['pilot_ids'])
            receipt['status'] = 'COMPLETED_WITH_FAILURES' if receipt['summary']['failed_or_interrupted'] else 'PASS'
            if dependencies:
                receipt['status'] = 'HOLD'
            return receipt
        attempted_keys = {checkpoint.digest(checkpoint.restore(p)['key'])
                          for p in (output/'nodes'/'attempts').glob('*.json')}
        neural = candidate in PREFERRED
        environment = dependencies.environment(candidate) if dependencies else runtime_environment(candidate)
        receipt['environment'] = environment
        if neural:
            history_hashes = json.loads((bundle/'expected_generation.json').read_text(encoding='utf-8'))['files']
            verify_store(historical_store, history_hashes)
            old_paths = list((historical_store/candidate/profile['profile_id']).glob('capacity-*.json'))
            require(len(old_paths) == 1, 'Historical cost receipt required for node admission')
            old_cost = checkpoint.restore(old_paths[0])
            stage_forecast = {}
            for old_record in old_cost['records']:
                for event in old_record['attempts']:
                    node = checkpoint.restore(historical_store/candidate/profile['profile_id']/'nodes'/(event['key_sha256']+'.json'))
                    stage = node['key']['stage']
                    stage_forecast[stage] = max(stage_forecast.get(stage, 0), event['new_attempt_wall_seconds']*1.5)
            require(all(v > 0 for v in stage_forecast.values()), 'Missing historical node cost forecasts')
            receipt['node_admission_forecast'] = {'stage_seconds': stage_forecast,
                'rule': '1.5x maximum observed historical same-model/stage node; operational guard, not statistical bound'}
            budget.guard(forecast_seconds=old_cost['load_seconds']*1.5)
            receipt['asset_admission'] = (dependencies.admit_assets(profile['profile'], budget) if dependencies else
                                           admit_assets(profile['profile'], budget))
            load_started = time.perf_counter()
            load_sample = dependencies.sample(True) if dependencies else ResourceSample(True)
            with load_sample as init_resources:
                receipt['model_load_resources'] = init_resources
                model, tokenizer = (dependencies.load_assets(profile['profile'], environment) if dependencies else
                                    runtime.load_runtime_assets(profile['profile'], environment))
            receipt['model_load_wall_seconds'] = time.perf_counter()-load_started
            runtime_sha = runtime.runtime_identity(environment)
        else:
            runtime_sha = checkpoint.digest(environment)
            receipt['model_load_wall_seconds'] = 0
        for existing in receipt['records'].values():
            require(existing['runtime_sha256'] == runtime_sha, 'Saved pilot runtime mismatch; no forced reuse')
        receipt['runtime_sha256'] = runtime_sha
        for row in sources:
            identifier = row['record_id']
            if identifier in receipt['records']:
                continue  # Includes started/failed: never retry an attempted record.
            budget.guard()
            path = output/'records'/(identifier.replace(':', '-')+'.json')
            record = {'record_id': identifier, 'source_sha256': row['source_normalized_sha256'],
                'source_stratum': row['source_stratum'], 'binding': binding, 'runtime_sha256': runtime_sha,
                'status': 'started', 'origin': 'historical_import' if neural and identifier in contract['staged_ids'] else 'fresh',
                'quality': None, 'retain_in_denominator': True, 'automatic_retry': False}
            receipt['records'][identifier] = record
            checkpoint.commit(path, record)
            generator = None
            result, events, resources, stage_resources = None, [], {}, []
            try:
                sample = dependencies.sample(neural) if dependencies else ResourceSample(neural)
                with sample as resources:
                    if record['origin'] == 'historical_import':
                        result, events, old_cost = (dependencies.import_historical(bundle, historical_store, row, profile, environment,
                            tokenizer, budget.deadline) if dependencies else import_historical(bundle, historical_store, row,
                            profile, environment, tokenizer, budget.deadline))
                        record['original_costs'] = old_cost
                        record['new_generation_wall_seconds'] = 0
                    elif neural:
                        backend = bindings.LoadedGenerator(model, tokenizer, architecture=profile['profile']['architecture'],
                            device='cuda:0', decode_parameters=profile['profile']['decode'], led_global_attention=candidate == 'led')
                        class Backend:
                            last_receipt = None
                            def __call__(self, batch, maximum, stage):
                                require(stage in stage_forecast, 'Unknown stage capacity: HOLD before generation')
                                budget.guard(forecast_seconds=stage_forecast[stage])
                                t, cpu = time.perf_counter(), time.process_time()
                                receipt['new_generation_calls'] += 1
                                try:
                                    return backend(batch, maximum, stage)
                                finally:
                                    self.last_receipt = backend.last_receipt
                                    elapsed = time.perf_counter()-t
                                    receipt['new_generation_wall_seconds'] += elapsed
                                    stage_resources.append({'stage': stage, 'wall_seconds': elapsed,
                                                            'cpu_seconds': time.process_time()-cpu})
                                    stage_forecast[stage] = max(stage_forecast[stage], (time.perf_counter()-t)*1.5)
                                    budget.flush()
                        def before_call(key):
                            budget.guard(checkpoint_reserve_bytes=4*1024*1024)
                            key_hash = checkpoint.digest(key)
                            require(key_hash not in attempted_keys, 'Node already attempted; automatic retry forbidden')
                            attempted_keys.add(key_hash)
                            import torch
                            seed = development_node_seed(key)
                            torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
                        generator = checkpoint.NodeCheckpointGenerator(Backend(), output/'nodes',
                            {**binding, 'record_id': identifier, 'source_sha256': row['source_normalized_sha256'],
                             'runtime_sha256': runtime_sha}, budget.deadline, before_call=before_call)
                        result = generation.summarize_source(row['source_normalized'],
                            **bindings.native_bindings(tokenizer, profile['profile']), generate=generator,
                            selector=delivery.select_delivered, word_cap=350)
                        events = generator.events
                        record.update(stage_resources=stage_resources,
                                      new_generation_wall_seconds=sum(e['new_attempt_wall_seconds'] for e in events))
                    else:
                        cpu_fn = {'lead3': lead3, 'lexrank': lexrank}[candidate]
                        result = cpu_fn(row['source_normalized'], word_cap=350)
                        events = []
                    record['result'] = result
                    validated = (validate_neural(row['source_normalized'], result, events, tokenizer,
                        profile['profile'], environment['resolved_generation_config']) if neural else
                        validate_cpu(row['source_normalized'], result, candidate))
                    record.update(status=validated['acceptance']['status'], validation=validated,
                                  result=result, events=events, calls=dict(Counter(n['stage'] for n in result.get('nodes', []))),
                                  native_tokens=sum(e['backend_receipt']['generated_native_tokens'] for e in events),
                                  maximum_layer=max((n['layer'] for n in result.get('nodes', [])), default=0),
                                  delivered_words=len(result['delivered_final'].split()),
                                  delivery=result['delivery'])
                record['resources'] = resources
            except Exception as error:
                record.update(status='failed', quality=None, error=f'{type(error).__name__}: {error}')
                if generator is not None:
                    record['events'] = generator.events
            finally:
                record['resources'] = resources
                record['stage_resources'] = stage_resources
                if generator is not None:
                    record['events'] = generator.events
                record['new_generation_wall_seconds'] = sum(s['wall_seconds'] for s in stage_resources)
                record['checkpoint_reused_original_wall_seconds'] = sum(
                    e.get('original_wall_seconds') or 0 for e in record.get('events', events))
                record['new_generation_calls'] = len(stage_resources)
                if result is not None:
                    record['result'] = result
            checkpoint.commit(path, record)
            print(json.dumps({'candidate_id': candidate, 'record_id': identifier, 'status': record['status']},
                             allow_nan=False), flush=True)
            budget.guard()
        receipt['summary'] = summary(receipt['records'], contract['pilot_ids'])
        if receipt['summary']['pending'] == receipt['summary']['status_counts'].get('started', 0) == 0:
            receipt['status'] = 'COMPLETED_WITH_FAILURES' if receipt['summary']['failed_or_interrupted'] else 'PASS'
        if dependencies:
            receipt['status'] = 'HOLD'
    except Exception as error:
        receipt.update(status='HOLD', error=f'{type(error).__name__}: {error}')
    finally:
        checkpoint.commit = original_commit
        if history_hashes is not None:
            try:
                verify_store(historical_store, history_hashes)
                receipt['historical_store_unchanged_verified'] = True
            except Exception as error:
                receipt.update(status='HOLD', historical_store_unchanged_verified=False, integrity_error=str(error))
        if 'contract' in locals():
            receipt['summary'] = summary(receipt['records'], contract['pilot_ids'])
        receipt.update(total_wall_seconds=time.monotonic()-started)
        if budget:
            try:
                budget.flush(final=True)
                receipt['resource_ledger'] = budget.ledger
            except Exception as error:
                receipt.update(status='HOLD', resource_ledger_error=str(error))
        if output.exists():
            atomic_json(output/'candidate_receipt.json', receipt)
        if model is not None:
            model = tokenizer = None
            gc.collect()
            if not dependencies:
                import torch
                torch.cuda.empty_cache()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('bundle', 'output', 'historical-store', 'allocation'):
        parser.add_argument('--'+option, required=True, type=Path)
    parser.add_argument('--candidate', required=True, choices=CANDIDATES)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--wall-hours', type=float, default=11.5)
    args = parser.parse_args()
    result = run(args.bundle, args.output, args.historical_store, args.candidate, resume=args.resume,
                 wall_hours=args.wall_hours, allocation=json.loads(args.allocation.read_text(encoding='utf-8')))
    print(json.dumps({'status': result['status'], 'summary': result.get('summary'), 'error': result.get('error')}, allow_nan=False), flush=True)
    return 0 if result['status'] in ('PASS', 'COMPLETED_WITH_FAILURES') else 1


if __name__ == '__main__':
    raise SystemExit(main())
