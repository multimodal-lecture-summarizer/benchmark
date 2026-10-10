"""Reuse prepared TIB, cache token lengths only, save a nine-record dev bundle."""
import json
import time
from pathlib import Path
from experiments.scripts.rq2_tib_benchmark import load_or_prepare_data, _save_result
from experiments.scripts.rq2_tib_benchmark_bundle import save_benchmark_bundle
from experiments.scripts.rq2_tib_pilot_cohort import select_pilot

MODEL_ID = 'Qwen/Qwen2.5-1.5B-Instruct'
MODEL_REVISION = '989aa7980e4cf806f80c7fef2b1adb7bc71aa306'


def prepare_pilot_data(full_data_path, output_dir, tokenizer, *, on_progress=None):
    """No generation, no source truncation, no quality-based sample selection."""
    started = time.perf_counter()
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    bundle = load_or_prepare_data(full_data_path)
    tokenizer_identity = {'id':MODEL_ID, 'revision':MODEL_REVISION,
                          'add_special_tokens':False, 'truncation':False}
    identity = {'full_selection':bundle['metadata']['selection_sha256'], 'tokenizer':tokenizer_identity}
    counts_path = output_dir/'source-token-lengths.json'
    cache = json.loads(counts_path.read_text(encoding='utf-8')) if counts_path.exists() else None
    if cache and cache['identity']!=identity:
        raise ValueError('Token length cache identity differs; use a new pilot data directory')
    cached = {r['id']:r for r in cache['rows']} if cache else {}
    lengths = []
    for index, item in enumerate(bundle['items'], 1):
        ident = f"{item['split']}/{item['source_index']}"
        old = cached.get(ident)
        if old and old['source_sha256']!=item['source_sha256']:
            raise ValueError('Source changed in token-length cache: '+ident)
        count = old['source_tokens'] if old else len(tokenizer.encode(
            item['source_text'], add_special_tokens=False, truncation=False, verbose=False))
        item['source_tokens'] = count
        lengths.append({'id':ident, 'source_sha256':item['source_sha256'], 'source_tokens':count})
        if on_progress and (index%250==0 or index==len(bundle['items'])):
            on_progress(index, len(bundle['items']))
    bundle['metadata']['tokenizer'] = tokenizer_identity
    _save_result({'identity':identity, 'rows':lengths}, counts_path)
    subset, design = select_pilot(bundle)
    target = output_dir/'tib-development-pilot.jsonl.gz'
    if target.exists():
        from experiments.scripts.rq2_tib_benchmark_bundle import load_benchmark_bundle
        existing = load_benchmark_bundle(target)
        if existing['metadata']['selection_sha256']!=subset['metadata']['selection_sha256']:
            raise ValueError('Existing pilot IDs changed; use a new data directory')
    else:
        save_benchmark_bundle(subset, target)
    design['data_preparation_seconds'] = time.perf_counter()-started
    _save_result(design, output_dir/'pilot-design.json')
    return subset, design, target
