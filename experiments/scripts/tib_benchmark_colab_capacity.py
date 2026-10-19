"""One neural candidate, three sealed pilot sources; never a formal benchmark."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import threading
import time

from experiments.scripts.tib_benchmark_adapter_generation import summarize_source
from experiments.scripts.tib_benchmark_adapter_transformers import LoadedGenerator, native_bindings
from experiments.scripts.tib_benchmark_checkpoint import NodeCheckpointGenerator, commit, digest, probe_store
from experiments.scripts.tib_benchmark_output import select_delivered
from experiments.scripts.tib_benchmark_development_trials import resolve_trial, development_node_seed
from experiments.scripts.tib_benchmark_reduction_diagnostics import reduction_diagnostic
from experiments.scripts.tib_benchmark_capacity_runtime import (
    checkpoint_download_patterns, stream_sha, load_runtime_assets, runtime_identity)


def capacity(bundle, store, candidate, wall_hours, *, trial_id=None, allow_deferred_trial=False):
    import psutil
    import torch
    if not 0 < wall_hours < 12:
        raise ValueError('Technical run limit must be strictly below12hours')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required; CPU run cannot establish GPU feasibility')
    started, deadline = time.monotonic(), time.monotonic()+wall_hours*3600
    manifest = json.loads((bundle/'bundle_manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path=(bundle/name).resolve()
        if not path.is_relative_to(bundle.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Bundle file hash mismatch: '+name)
    profiles=json.loads((bundle/'candidate_profiles.json').read_text())
    profile=next(p for p in profiles['pipelines'] if p['candidate_id']==candidate)
    trial_registry=None
    if trial_id is not None:
        trial_registry=json.loads((bundle/'development_trials.json').read_text())
        trial=resolve_trial(trial_registry,trial_id,candidate,store,allow_deferred=allow_deferred_trial)
        profile=trial['profile']
    records=[json.loads(line) for line in (bundle/'staged_sources.jsonl').read_text(encoding='utf-8').splitlines()]
    if [r['record_id'] for r in records]!=manifest['staged_pilot_ids'] or len(records)!=3:
        raise ValueError('Only three sealed staged pilot IDs are permitted')
    for row in records:
        if hashlib.sha256(row['source_normalized'].encode()).hexdigest()!=row['source_normalized_sha256']:
            raise ValueError('Source hash mismatch')
        if any('reference' in key or 'abstract' in key for key in row):
            raise ValueError('Reference fields must not enter generator bundle')
    store=store/candidate
    if trial_id is not None:
        store=store/trial_id
    store.mkdir(parents=True,exist_ok=True)
    store_check=probe_store(store)
    device=torch.cuda.get_device_name(0)
    t4=device in ('Tesla T4','NVIDIA T4','NVIDIA Tesla T4')
    process=psutil.Process()
    peak=[process.memory_info().rss]
    stop=threading.Event()
    def monitor():
        while not stop.wait(.1): peak[0]=max(peak[0],process.memory_info().rss)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    torch.cuda.reset_peak_memory_stats()
    receipt={'scope':'three-source technical capacity only','candidate_id':candidate,'device_name':device,
             'T4_device_observed':t4,'T4_feasibility_verified':False,'formal_benchmark':False,
             'final_test_sealed':False,'word_cap_frozen_for_selection':False,'word_cap':350,
             'profile':profile,'profile_sha256':digest(profile),'store_probe':store_check,'records':[],
             'wall_hours_limit':wall_hours,'packages':{p:importlib.metadata.version(p) for p in ('torch','transformers','huggingface-hub','numpy')},
             'status':'started','measurement_note':'sampled process RSS; CUDA peaks include model load; no throughput generalization from three records'}
    receipt.update(trial_id=trial_id,trial_registry_sha256=digest(trial_registry) if trial_registry else None,
                   intermediate_acceptance_policy='observe_continue_with_flags_technical_only',
                   formal_intermediate_acceptance_policy_frozen=False,
                   device_memory_bytes=torch.cuda.get_device_properties(0).total_memory,
                   host_memory_total_bytes=psutil.virtual_memory().total,
                   host_memory_available_before_load_bytes=psutil.virtual_memory().available,
                   cuda_runtime=torch.version.cuda)
    stamp=str(time.time_ns())
    output=store/('capacity-'+stamp+'.json')
    commit(output,receipt)
    try:
        model,tokenizer=load_runtime_assets(profile,receipt)
        bound=native_bindings(tokenizer,profile)
        for row in records:
            record={'record_id':row['record_id'],'source_words':len(row['source_normalized'].split()),
                    'source_sha256':row['source_normalized_sha256'],
                    'status':'attempted','stratum':row['source_stratum']}
            cpu_start,time_start=time.process_time(),time.perf_counter()
            backend=LoadedGenerator(model,tokenizer,architecture=profile['architecture'],device='cuda:0',
                        decode_parameters=profile['decode'],led_global_attention=candidate=='led')
            def seed_node(key):
                seed=development_node_seed(key) if trial_id is not None else int(digest(key)[:8],16)
                torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
            generator=NodeCheckpointGenerator(backend,store/'nodes',
                {'record_id':row['record_id'],'source_sha256':row['source_normalized_sha256'],
                 'profile_sha256':digest(profile),'bundle_sha256':stream_sha(bundle/'bundle_manifest.json'),
                 'trial_id':trial_id,'trial_registry_sha256':receipt['trial_registry_sha256'],
                 'runtime_sha256':runtime_identity(receipt)},deadline,seed_node)
            receipt['records'].append(record)
            commit(output,receipt)
            try:
                result=summarize_source(row['source_normalized'],**bound,generate=generator,
                         selector=select_delivered,word_cap=350)
                torch.cuda.synchronize()
                diagnostics=[]
                for event in generator.events:
                    native=event.get('backend_receipt')
                    if trial_id is not None and (not native or not native.get('generation_config_complete')
                                                 or not native.get('valid_eos_token_ids')):
                        raise ValueError('Development trial requires complete effective config/EOS telemetry')
                    diagnostics.append({'key_sha256':event['key_sha256'],'status':event['status'],
                                        'backend_receipt':native})
                result['generation_diagnostics']=diagnostics
                result['reduction_diagnostic']=reduction_diagnostic(result)
                artifact=store/(row['record_id'].replace(':','-')+'-'+stamp+'.json')
                commit(artifact,result)
                record.update(status='completed',delivery={k:v for k,v in result['delivery'].items() if k!='text'},
                              calls=dict(Counter(n['stage'] for n in result['nodes'])),
                              source_tokens=result['source_token_count'],artifact_path=str(artifact),
                              generation_diagnostics=diagnostics,
                              semantic_coverage_review='pending_manual_development_review',
                              nodes=[{k:v for k,v in n.items() if k!='output_text'} for n in result['nodes']])
            except Exception as error:
                record.update(status='failed',error=f'{type(error).__name__}: {error}')
            record.update(wall_seconds=time.perf_counter()-time_start,cpu_seconds=time.process_time()-cpu_start,
                          attempts=generator.events)
            commit(output,receipt)
            if time.monotonic()>=deadline: break
        receipt['status']='completed' if len(receipt['records'])==3 and all(r['status']=='completed' for r in receipt['records']) else 'partial_or_failed'
        receipt['fresh_generation_only']=all(r.get('attempts') and all(e['status']=='completed' for e in r['attempts']) for r in receipt['records'])
        receipt['T4_feasibility_verified']=t4 and receipt['status']=='completed' and receipt['fresh_generation_only']
    except Exception as error:
        receipt.update(status='failed',error=f'{type(error).__name__}: {error}')
    finally:
        stop.set();thread.join()
        receipt.update(total_wall_seconds=time.monotonic()-started,sampled_peak_process_rss_bytes=peak[0],
                       cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                       cuda_peak_reserved_bytes=torch.cuda.max_memory_reserved())
        commit(output,receipt)
    print(json.dumps({'receipt':str(output),'status':receipt['status'],'T4_verified':receipt['T4_feasibility_verified']}))
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--store',type=Path,required=True)
    parser.add_argument('--candidate',choices=['bart','led','qwen3'],required=True)
    parser.add_argument('--wall-hours',type=float,default=11)
    parser.add_argument('--trial-id')
    parser.add_argument('--allow-deferred-trial',action='store_true',help='Explicit resource review required;384 evidence and headroom still enforced')
    args=parser.parse_args()
    result=capacity(args.bundle,args.store,args.candidate,args.wall_hours,
                    trial_id=args.trial_id,allow_deferred_trial=args.allow_deferred_trial)
    if result['status']!='completed': raise SystemExit(1)
