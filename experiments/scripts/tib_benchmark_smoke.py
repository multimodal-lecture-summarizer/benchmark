"""Three sealed pilot sources: tokenizer planning and CPU controls only."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import time

from experiments.scripts.tib_benchmark_adapter_cpu import lead3, lexrank
from experiments.scripts.tib_benchmark_adapter_transformers import plan_profile_source
from experiments.scripts.tib_benchmark_output_evidence import validate_tokenizers


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smoke(qualification, registry, profiles_path, tokenizers_root, output):
    import psutil
    from transformers import AutoTokenizer
    if output.exists():
        raise ValueError("Smoke evidence exists; use a new version")
    cohort_path = registry / 'development_cohort.json'
    cohort = json.loads(cohort_path.read_text())
    if sha(registry / 'qualification_policy.json') != cohort['policy_sha256']:
        raise ValueError("Development policy hash mismatch")
    ids = cohort['staged_pilot_ids']
    if len(ids) != 3 or not set(ids).issubset(cohort['selected_ids']['pilot']):
        raise ValueError("Only the three sealed staged pilot sources are allowed")
    metadata = {row['record_id']: row for row in (json.loads(line) for line in
                (qualification / 'qualified_cohort/qualification_ledger.jsonl').read_text(encoding='utf-8').splitlines())}
    receipts = json.loads((qualification / 'eda/receipt.json').read_text())
    canonical = qualification / 'eda/canonical_records.jsonl.gz'
    if sha(canonical) != receipts['files']['canonical_records.jsonl.gz']:
        raise ValueError("Canonical bytes changed")
    sources = {}
    with gzip.open(canonical, 'rt', encoding='utf-8') as handle:
        for line in handle:
            row = json.loads(line)
            if row['record_id'] in ids:
                source = row['source_normalized']
                if hashlib.sha256(source.encode()).hexdigest() != metadata[row['record_id']]['source_normalized_sha256']:
                    raise ValueError("Canonical source hash mismatch")
                sources[row['record_id']] = source
    if set(sources) != set(ids):
        raise ValueError("Incomplete staged pilot source frame")
    tokenizer_receipt = json.loads((tokenizers_root / 'receipt.json').read_text())
    validate_tokenizers(tokenizers_root, tokenizer_receipt)
    profiles = {p['candidate_id']: p for p in json.loads(profiles_path.read_text())['pipelines']}
    tokenizers = {name: AutoTokenizer.from_pretrained(tokenizers_root / name, local_files_only=True)
                  for name in ('bart','led','qwen3')}
    results, native, full_outputs = [], [], []
    for identifier in ids:
        source = sources[identifier]
        for name, function in (('lead3',lead3),('lexrank',lexrank)):
            started = time.perf_counter()
            cpu_start = time.process_time()
            try:
                result = function(source, word_cap=350)
                status, failure = 'pass', None
                full_outputs.append({'record_id':identifier,**result})
                delivery = result['delivery']
            except Exception as exc:
                result, delivery = {}, {}
                status, failure = 'failed', f'{type(exc).__name__}: {exc}'
            results.append({'record_id':identifier,'candidate_id':name,'status':status,'failure':failure,
                            'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu_start,
                            'process_rss_after_bytes':psutil.Process().memory_info().rss,
                            'rss_is_peak':False, 'source_words':len(source.split()),
                            'sentence_count':result.get('sentence_count'),
                            'graph_sentence_count':result.get('graph_sentence_count'),
                            'delivery':{k:v for k,v in delivery.items() if k!='text'},
                            'generation_gpu_memory':None})
        for name, tokenizer in tokenizers.items():
            started = time.perf_counter()
            plan = plan_profile_source(source, tokenizer, profiles[name])
            if not plan['full_source_token_coverage']:
                raise ValueError("Native map planning did not cover full source")
            native.append({'record_id':identifier,**plan,'planning_wall_seconds':time.perf_counter()-started})
    summary = {'state':'staged_CPU_control_smoke_and_tokenizer_planning_only', 'ids':ids,
               'generation_scope':'six CPU extractive control attempts; no pretrained generator loaded or run',
               'model_generation_T4_verified':False,'formal_benchmark':False,'final_test_sealed':False,
               'word_cap':350,'reference_input_used':False,'cpu_results':results,'native_plans':native,
               'status_counts':dict(Counter(r['status'] for r in results)),
               'capping_by_candidate':{name:{'attempted':3,'completed':sum(r['status']=='pass' for r in results if r['candidate_id']==name),
                   'capped':sum(r['delivery'].get('capped',False) for r in results if r['candidate_id']==name),
                   'forced_word_boundary':sum(r['delivery'].get('forced_word_boundary',False) for r in results if r['candidate_id']==name)} for name in ('lead3','lexrank')},
               'code_sha256':{p.name:sha(p) for p in Path(__file__).parent.glob('tib_benchmark_adapter*.py')},
               'cohort_sha256':sha(cohort_path),'candidate_profiles_sha256':sha(profiles_path),
               'tokenizer_receipt_sha256':sha(tokenizers_root/'receipt.json'),
               'limitations':['Three-source technical smoke is not pilot40 or T4 capacity evidence',
                              'Map counts are plans; reduce calls need actual neural outputs',
                              'RSS after operation is not a measured peak; no CPU/RAM admission granted']}
    output.mkdir(parents=True)
    (output/'cpu_outputs.json').write_text(json.dumps(full_outputs,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'receipt.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification',type=Path,required=True)
    parser.add_argument('--registry',type=Path,required=True)
    parser.add_argument('--profiles',type=Path,required=True)
    parser.add_argument('--tokenizers',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = smoke(args.qualification,args.registry,args.profiles,args.tokenizers,args.output)
    print(json.dumps({'status_counts':result['status_counts'],'capping':result['capping_by_candidate'],
                      'native_plans':[{k:p[k] for k in ('record_id','candidate_id','source_tokens','planned_map_calls','full_source_token_coverage')} for p in result['native_plans']]},indent=2))
