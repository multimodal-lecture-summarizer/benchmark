"""Build a standalone Colab development pilot from the current audited sources."""
import ast
import json
from pathlib import Path


def build():
    root = Path(__file__).resolve().parents[2]
    names = ['rq2_tib_benchmark', 'rq2_tib_benchmark_dataset', 'rq2_tib_benchmark_bundle',
             'rq2_tib_benchmark_pair', 'rq2_tib_benchmark_results', 'rq2_tib_benchmark_metrics',
             'rq2_controlled_validation', 'rq2_local_hf_backend', 'rq2_tib_pilot',
             'rq2_tib_pilot_runtime', 'rq2_tib_pilot_cohort', 'rq2_tib_pilot_forecast', 'rq2_tib_pilot_data',
             'rq2_tib_pilot_display']
    sources = {name:(root/'experiments/scripts'/f'{name}.py').read_text(encoding='utf-8') for name in names}
    cells = []
    def md(source):
        cells.append(dict(cell_type='markdown', metadata={}, source=source.splitlines(True)))
    def code(source):
        ast.parse(source)
        cells.append(dict(cell_type='code', metadata={}, source=source.splitlines(True), execution_count=None, outputs=[]))
    md('''# TIB RQ2/RQ4 — development technical pilot
Run on **Colab GPU**, with a fresh Drive root. Nine train records selected by source length,
both S1/S3, no quality-based selection. This notebook does not launch the full benchmark or freeze a cohort.
S3 changes boundary-constrained chunking; both arms use the same flattened map/reduce prompts.
Equal allocated intermediate/final output caps do not imply equal actual total tokens.
Text-only results measure creator-abstract agreement, not video factuality or multimodal benefit.

Upload the supplied `data` folder to `MyDrive/RQ2_TIB_PILOT_20261010/data` first, if available.
Otherwise this notebook reuses the existing full TIB cache, or fetches the pinned source through
the existing integrated preparation entry point. No source truncation. Previously inspected references are not unseen.
The two-hour generation limit is a soft stop between calls. Colab disconnection/idle expiry can interrupt a run;
Drive checkpoints preserve predictions, but resumed timings cannot justify a uniform runtime forecast.
All review information is rendered in notebook output: coverage, per-record timings/tokens/VRAM,
paired metrics, failures and the runtime forecast. Save this notebook with outputs or copy the final report;
you do not need to inspect/export individual JSON files. JSON checkpoints remain internal resume evidence.
''')
    code('''import time, subprocess, sys
SESSION_START = time.perf_counter()
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'transformers>=4.45,<5', 'datasets', 'huggingface_hub', 'sentence-transformers',
    'bert-score', 'sentencepiece', 'pandas'])
''')
    code('''from pathlib import Path
import json, gc, hashlib
from google.colab import drive
drive.mount('/content/drive')
ROOT = Path('/content/drive/MyDrive/RQ2_TIB_PILOT_20261010')
ROOT.mkdir(parents=True, exist_ok=True)
DATA = ROOT/'data'; DATA.mkdir(exist_ok=True)
RUN = ROOT/'pilot-run-v1'
CODE = Path('/content/rq2_tib_pilot_code')
''')
    code('SOURCES = '+repr(sources)+'''
for folder in (CODE/'experiments', CODE/'experiments/scripts'):
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'__init__.py').write_text('', encoding='utf-8')
for name, source in SOURCES.items():
    (CODE/'experiments/scripts'/f'{name}.py').write_text(source, encoding='utf-8')
sys.path.insert(0, str(CODE))
from experiments.scripts.rq2_tib_pilot_data import prepare_pilot_data, MODEL_ID, MODEL_REVISION
from experiments.scripts.rq2_tib_benchmark_bundle import load_benchmark_bundle, generation_input
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig
from experiments.scripts.rq2_tib_pilot import run_pilot, evaluate_pilot, forecast_receipt
from experiments.scripts.rq2_tib_pilot_runtime import code_identity
from experiments.scripts.rq2_tib_pilot_display import show_pilot_report
print('Code identity:', code_identity()['sha256'])
''')
    code('''from transformers import AutoTokenizer
from huggingface_hub import snapshot_download
PILOT_FILE = DATA/'tib-development-pilot.jsonl.gz'
if PILOT_FILE.exists() and (DATA/'pilot-design.json').exists():
    bundle = load_benchmark_bundle(PILOT_FILE)
    design = json.loads((DATA/'pilot-design.json').read_text())
else:
    tokenizer_path = snapshot_download(MODEL_ID, revision=MODEL_REVISION,
        allow_patterns=['tokenizer*', 'vocab.json', 'merges.txt', 'config.json', 'special_tokens_map.json'])
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    full_cache = Path('/content/drive/MyDrive/RQ2_TIB_BENCHMARK/tib-benchmark-data.jsonl.gz')
    bundle, design, PILOT_FILE = prepare_pilot_data(full_cache, DATA, tokenizer,
        on_progress=lambda n,total: print('Token lengths:', n, '/', total))
import pandas as pd
display(pd.DataFrame(design['selected']))
print('Full-pool strata:', design['population_by_stratum'])
print('Target longer than dev maximum:', design['full_pool_exceeds_pilot_length_range'])
assert len(bundle['items']) == 9 and all(r['split']=='train' for r in bundle['items'])
assert not design['evaluation_cohort_frozen']
''')
    md('''## Generate once; retain every selected ID
Fixed pilot profile: Qwen2.5-1.5B pinned revision, FP16, greedy, map batch 2,
512 source tokens/chunk, 96 × max(chunk count) common map output cap, final cap 384.
Context preflight is source-only and does not drop long records. If it fails, stop and revise
the declared configuration in a **new root**, retaining this failed preflight. No automatic fallback or retry.
''')
    code('''import torch
assert torch.cuda.is_available(), 'Select a Colab GPU runtime. Do not run this pilot on local GPU.'
from experiments.scripts.rq2_local_hf_backend import LocalHfUsageBackend
model_path = snapshot_download(MODEL_ID, revision=MODEL_REVISION,
    allow_patterns=['*.json', '*.safetensors', '*.txt'])
backend = LocalHfUsageBackend(Path(model_path), model_id=MODEL_ID,
    revision=MODEL_REVISION, device='cuda')
backend.map_batch_size = 2
config = BenchmarkConfig()
from experiments.scripts.rq2_controlled_validation import _fixed_chunks, _hierarchy_chunks, predict_source_boundaries
checks = []
for item in bundle['items']:
    seg = generation_input(item)['transcript_segments']
    source = ' '.join(item['source_text'].split())
    fixed = _fixed_chunks(source, backend, config.chunk_tokens)
    structured = _hierarchy_chunks(seg['text'], seg['start'],
        predict_source_boundaries(seg['text'], seg['start']), backend, config.chunk_tokens)
    cap = max(len(fixed), len(structured))*config.map_output_tokens
    # Planning screen with 4x retokenization allowance, not a proof about generated text.
    # The backend checks each actual reduce prompt plus its output cap before dispatch.
    checks.append({'id':f"train/{item['source_index']}", 'S1_chunks':len(fixed),
        'S3_chunks':len(structured), 'map_cap':cap,
        'reduce_context_headroom_screen':4*cap+config.final_output_tokens+2048 < backend.context_limit})
    assert all(' '.join(chunks)==source for chunks in (fixed, structured)), 'Source coverage changed'
(ROOT/'context-preflight.json').write_text(json.dumps(checks, indent=2))
display(pd.DataFrame(checks))
assert all(r['reduce_context_headroom_screen'] for r in checks), 'STOP: revise context/budget policy before generation'
initialization_seconds = time.perf_counter()-SESSION_START
last_log = [0.0]
def progress(event):
    now = time.monotonic()
    if event.get('status')=='failed' or now-last_log[0]>10:
        print({k:v for k,v in event.items() if k in ('id','index','total','stage','status','arm','step','chunk_index','chunk_total')})
        last_log[0] = now
receipt = run_pilot(backend, bundle, design, output_dir=RUN,
    initialization_seconds=initialization_seconds, config=config,
    wall_limit_seconds=7200, on_event=progress)
display(pd.DataFrame([{'id':r['id'], 'stratum':r['length_stratum'], 'status':r['status'],
    **{a+'_seconds':r.get('arms',{}).get(a,{}).get('wall_seconds') for a in ('S1','S3')}} for r in receipt['rows']]))
_ = show_pilot_report(receipt, forecast=forecast_receipt(receipt), dispatch_path=RUN/'dispatches.jsonl')
''')
    md('''## Score saved predictions after releasing the generator
CUDA failure: restart the runtime before further GPU work. Keep all receipts. Do not silently lower batch size.
This stage can reopen `pilot-receipt.json` without regenerating summaries. Failed IDs stay in coverage denominators.
Primary score is Unicode word LCS ROUGE-L F1, casefolded, no stemming, per-record macro.
Secondary scores are BERTScore and source SBERTScore; the latter is not a factuality percentage.
Pilot scores are diagnostics, not model selection, population claims, or a confirmatory confidence interval.
''')
    code('''if 'backend' in globals():
    del backend
gc.collect(); torch.cuda.empty_cache()
receipt = json.loads((RUN/'pilot-receipt.json').read_text())
if any(any(word in str(r).lower() for word in ('cuda', 'out of memory', 'fresh_runtime'))
       for r in receipt['rows'] if r['status'] in ('failed','not_attempted','interrupted')):
    raise RuntimeError('Restart runtime after CUDA failure; preserve failed pilot and do not forecast it')
from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
metric_started = time.perf_counter()
try:
    scorer = SemanticScorer(device='cuda', batch_size=16).load()
except Exception as exc:
    print('Semantic scorer initialization failed:', type(exc).__name__, str(exc))
    show_pilot_report(receipt, forecast=forecast_receipt(receipt), dispatch_path=RUN/'dispatches.jsonl')
    raise
metric_initialization_seconds = time.perf_counter()-metric_started
receipt = evaluate_pilot(receipt, bundle, scorer, output_dir=RUN,
    metric_initialization_seconds=metric_initialization_seconds)
print(receipt['counts'])
''')
    code('''# This output cell can reopen saved evidence without regenerating summaries.
receipt = json.loads((RUN/'pilot-receipt.json').read_text())
forecast = forecast_receipt(receipt)
(RUN/'runtime-forecast.json').write_text(json.dumps(forecast, indent=2))
report = show_pilot_report(receipt, forecast=forecast, dispatch_path=RUN/'dispatches.jsonl')
print('Save this notebook with outputs, or copy the report above into chat. No separate JSON export needed.')
''')
    md('''## Next decision after receipts
Compare measured costs across short/medium/long, including initialization, both arms, semantic scoring,
shared preparation and checkpoints. Forecast requires complete fresh profiles for all three strata;
failures, resumed costs, or target lengths outside the pilot range block a credible forecast.
The observed min/max scenario range is not a statistical confidence interval; 30% planning margin is an assumption.
Any extra model/configuration/repetition requires separate measured cost. Reduce extensions first if over 12 hours.
Choose evaluation IDs without seeing comparative scores, review dependence groups, then freeze IDs and protocol.
Future paired uncertainty uses video/dependence groups, never chunks as independent samples.
The printed report is the review handoff; checkpoints stay on Drive for resume/provenance.
''')
    target = root/'experiments/notebooks/rq2-tib-technical-pilot-colab.ipynb'
    notebook = dict(cells=cells, metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python'}, 'colab':{'name':target.name}, 'accelerator':'GPU'}, nbformat=4, nbformat_minor=5)
    for index, cell in enumerate(cells):
        cell['id'] = f'pilot-{index:02d}'
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding='utf-8')
    return target


if __name__ == '__main__':
    print(build())
