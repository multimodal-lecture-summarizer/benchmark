"""Package the frozen TIB cohort and audited Python sources for Colab."""

import ast
import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "experiments/registry/datasets"
OUTPUT = ROOT / "experiments/outputs/rq2_tib_120_261012"
NAMES = (
    "rq2_tib_benchmark", "rq2_tib_benchmark_dataset", "rq2_tib_benchmark_bundle",
    "rq2_tib_benchmark_pair", "rq2_tib_benchmark_results", "rq2_tib_benchmark_metrics",
    "rq2_controlled_validation", "rq2_local_hf_backend", "rq2_tib_pilot_runtime",
    "rq2_tib_frozen_runtime", "rq2_tib_frozen_analysis",
)


def _cell(kind, source):
    result = {"cell_type": kind, "metadata": {}, "source": source.splitlines(True)}
    if kind == "code":
        ast.parse(source)
        result.update(execution_count=None, outputs=[])
    return result


def build():
    manifest_path = REGISTRY / "tib-rq2-rq4-120-cohort-261012.json"
    protocol_path = REGISTRY / "tib-rq2-rq4-120-protocol-261012.json"
    bundle_path = OUTPUT / "data/tib-evaluation-120.jsonl.gz"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if not all(path.exists() for path in (manifest_path, protocol_path, bundle_path)):
        raise FileNotFoundError("Frozen manifest, protocol or 120-record bundle missing")
    sources = {name: (ROOT / "experiments/scripts" / f"{name}.py").read_bytes().decode("utf-8")
               for name in NAMES}
    source_hashes = {name: hashlib.sha256(value.encode("utf-8")).hexdigest()
                     for name, value in sources.items()}
    if protocol["code_sha256"] != source_hashes:
        raise ValueError("Protocol code hashes differ from embedded sources")

    cells = [
        _cell("markdown", """# Frozen TIB RQ2/RQ4 120-record evaluation

The 120 creator `valid` records were selected before generation, 40 per pinned source-token length stratum. S1 and S3 summarize the same full transcript with the same Qwen checkpoint. Primary result: ROUGE-L agreement with creator abstracts and measured pipeline cost. These abstracts were already inspected in EDA; results cannot establish factual video quality or multimodal benefit. Grouped intervals are exploratory sensitivity, not population-superiority tests.

Upload the supplied `data` folder to `MyDrive/RQ2_TIB_120_20261012/data`, select a Tesla T4 GPU and run cells in order. Use a fresh run directory for any changed cohort, code, configuration or hardware. Checkpoints can be resumed only with matching identity. Keep the Colab tab/runtime active; Drive checkpoints survive disconnection but an in-flight model call may stop.
"""),
        _cell("code", """# Validate supplied identity and all 120 source/reference hashes before pip or model loading.
import gzip, hashlib, json, pathlib, time
from google.colab import drive
drive.mount('/content/drive')
ROOT = pathlib.Path('/content/drive/MyDrive/RQ2_TIB_120_20261012')
DATA = ROOT/'data'; RUN = ROOT/'formal-run-v1'
MANIFEST = json.loads((DATA/'tib-rq2-rq4-120-cohort-261012.json').read_text(encoding='utf8'))
PROTOCOL = json.loads((DATA/'tib-rq2-rq4-120-protocol-261012.json').read_text(encoding='utf8'))
def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
assert digest({k:v for k,v in MANIFEST.items() if k!='manifest_sha256'}) == MANIFEST['manifest_sha256']
assert digest({k:v for k,v in PROTOCOL.items() if k!='protocol_sha256'}) == PROTOCOL['protocol_sha256']
assert PROTOCOL['cohort_manifest_sha256']==MANIFEST['manifest_sha256']
assert PROTOCOL['selected_count']==120 and len(MANIFEST['selected'])==120
bundle_file = DATA/'tib-evaluation-120.jsonl.gz'
items=[]; payload=hashlib.sha256(); complete=False; metadata=None
with gzip.open(bundle_file,'rt',encoding='utf8',newline='') as stream:
    for line in stream:
        record=json.loads(line)
        if record.get('kind')=='checksum':
            assert record['sha256']==payload.hexdigest(); complete=True; continue
        assert not complete
        payload.update(line.encode('utf8'))
        if record['kind']=='metadata': metadata=record['value']
        elif record['kind']=='item': items.append(record['value'])
        else: raise ValueError('Unexpected bundle record')
assert complete and len(items)==120
assert payload.hexdigest()==MANIFEST['bundle']['payload_sha256']
by_id={f"{r['split']}/{r['source_index']}":r for r in items}
assert len(by_id)==120 and set(by_id)=={r['id'] for r in MANIFEST['selected']}
for entry in MANIFEST['selected']:
    item=by_id[entry['id']]
    for text_field, hash_field in [('source_text','source_sha256'),('reference_text','reference_sha256')]:
        assert hashlib.sha256(item[text_field].encode('utf8')).hexdigest()==entry[hash_field]==item[hash_field]
assert metadata['selection_sha256']==MANIFEST['selection_sha256']
print('Frozen inputs verified:', len(items), 'records; cohort', MANIFEST['manifest_sha256'])
SESSION_START=time.monotonic()
"""),
        _cell("code", """import subprocess, sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'transformers>=4.45,<5', 'datasets', 'huggingface_hub',
    'sentence-transformers', 'bert-score', 'sentencepiece', 'pandas'])
"""),
        _cell("code", """# Embedded source is fixed by the protocol; no remote code checkout.
SOURCES = """ + repr(sources) + """
for name, source in SOURCES.items():
    assert hashlib.sha256(source.encode('utf8')).hexdigest()==PROTOCOL['code_sha256'][name]
CODE = pathlib.Path('/content/rq2_tib_120_code')
for folder in [CODE/'experiments', CODE/'experiments/scripts']:
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'__init__.py').write_text('',encoding='utf8')
for name, source in SOURCES.items():
    (CODE/'experiments/scripts'/f'{name}.py').write_bytes(source.encode('utf8'))
sys.path.insert(0,str(CODE))
from experiments.scripts.rq2_tib_benchmark_bundle import load_benchmark_bundle
from experiments.scripts.rq2_tib_frozen_runtime import validate_frozen_inputs, run_frozen, evaluate_frozen, summarize_frozen
bundle=load_benchmark_bundle(bundle_file)
validate_frozen_inputs(bundle,MANIFEST,PROTOCOL)
RUN.mkdir(parents=True,exist_ok=True)
print('Code and bundle identity verified; run directory:', RUN)
"""),
        _cell("markdown", """## Generation

Two arms run on each selected record; failures and unattempted IDs stay in the 120 denominator. Deadline checks happen between dispatches and cannot interrupt a GPU kernel. Generated predictions are saved before secondary scoring.
"""),
        _cell("code", """import torch, gc
from huggingface_hub import snapshot_download
from experiments.scripts.rq2_local_hf_backend import LocalHfUsageBackend
assert torch.cuda.is_available(), 'Select Tesla T4 GPU runtime'
assert 'T4' in torch.cuda.get_device_name(0), 'Frozen cost profile requires Tesla T4; start a new protocol for another GPU'
MODEL_ID=PROTOCOL['generation']['model']; REVISION=PROTOCOL['generation']['revision']
model_path=snapshot_download(MODEL_ID,revision=REVISION,allow_patterns=['*.json','*.safetensors','*.txt'])
backend=LocalHfUsageBackend(pathlib.Path(model_path),model_id=MODEL_ID,revision=REVISION,device='cuda')
backend.map_batch_size=2
print('GPU:',torch.cuda.get_device_name(0),'batch:',backend.map_batch_size)
"""),
        _cell("code", """# Source-only context preflight; no output or reference is used to select/drop IDs.
from experiments.scripts.rq2_controlled_validation import _fixed_chunks, _hierarchy_chunks, predict_source_boundaries
from experiments.scripts.rq2_tib_benchmark_bundle import generation_input
from experiments.scripts.rq2_tib_benchmark import BenchmarkConfig
config=BenchmarkConfig()
for item in bundle['items']:
    seg=generation_input(item)['transcript_segments']
    fixed=_fixed_chunks(' '.join(item['source_text'].split()),backend,config.chunk_tokens)
    structured=_hierarchy_chunks(seg['text'],seg['start'],
        predict_source_boundaries(seg['text'],seg['start']),backend,config.chunk_tokens)
    source=' '.join(item['source_text'].split())
    assert all(' '.join(chunks)==source for chunks in (fixed,structured)), 'Full source coverage changed'
    map_budget=config.map_output_tokens*max(len(fixed),len(structured))
    # Planning screen, not a proof about generated text; backend checks actual reduce prompt.
    assert 4*map_budget+config.final_output_tokens+2048 < backend.context_limit
    for chunks in (fixed,structured):
        base,remainder=divmod(map_budget,len(chunks))
        for i,chunk in enumerate(chunks):
            prompt=f'Summarize lecture section {i+1} using only its source.\\nCONTENT:\\n{chunk}\\nSECTION SUMMARY:'
            assert backend.count_tokens(prompt)+base+(i<remainder)<=backend.context_limit
print('Source-only preflight complete:',len(bundle['items']))
"""),
        _cell("code", """last_log=[0.0]
def show_progress(event):
    now=time.monotonic()
    if event.get('status') in ('failed','not_attempted') or now-last_log[0]>=10:
        print({k:event.get(k) for k in ('id','stage','status','arm','step','chunk_index','chunk_total') if k in event})
        last_log[0]=now
receipt=run_frozen(backend,bundle,MANIFEST,PROTOCOL,output_dir=RUN,
    initialization_seconds=time.monotonic()-SESSION_START,on_event=show_progress)
print('Generation:',receipt['counts'])
"""),
        _cell("markdown", """## Secondary metrics and aggregate

Semantic scorers use saved predictions after releasing the generator. If semantic scoring fails, ROUGE and predictions remain. The report shows every selected record, paired counts per metric, per-arm resources and separate dependence-group sensitivity.
"""),
        _cell("code", """del backend
gc.collect(); torch.cuda.empty_cache()
from experiments.scripts.rq2_tib_benchmark_metrics import SemanticScorer
metric_started=time.monotonic()
try:
    scorer=SemanticScorer(device='cuda').load()
    receipt=evaluate_frozen(receipt,bundle,scorer,output_dir=RUN,
        metric_initialization_seconds=time.monotonic()-metric_started,on_event=show_progress)
except (Exception, KeyboardInterrupt) as exc:
    # The sealed receipt preserves generation and any completed scoring.
    receipt=json.loads((RUN/'frozen-receipt.json').read_text(encoding='utf8'))
    print('Secondary scoring stopped:',type(exc).__name__,str(exc))
    print('Missing scores remain unavailable, never zero.')
print('Evaluation:',receipt['counts'])
"""),
        _cell("code", """summary=summarize_frozen(receipt,MANIFEST,PROTOCOL)
from IPython.display import display
import pandas as pd
print('Claim:',summary['claim'])
print('Coverage:',summary['counts'])
print("Metric means use each metric's paired successful intersection; unavailable stays null.")
display(pd.DataFrame([{'metric':metric,**report['overall'],
    'balanced_strata_mean_delta':report['balanced_strata_mean_delta']}
    for metric,report in summary['metrics'].items()]))
display(pd.DataFrame(summary['arms']).T)
for metric, report in summary['metrics'].items():
    print(metric, 'paired:', report['overall']['paired_scored'], '/ 120')
    display(pd.DataFrame([{'stratum':name,**values} for name,values in report['strata'].items()]))
    print('Overall:',report['overall'],'group sensitivity:',report['exploratory_group_sensitivity'])
display(pd.DataFrame([{'metric':metric,'group':group,**interval}
    for metric,report in summary['metrics'].items()
    for group,interval in report['exploratory_group_sensitivity'].items()]))
display(pd.DataFrame(summary['resources_by_arm']).T)
display(pd.DataFrame([{'arm':arm,
    **{field:(max(values) if values else None)
       for field in ('peak_gpu_allocated_bytes','peak_gpu_reserved_bytes')
       for values in [[row['arms'][arm][field] for row in receipt['rows']
           if arm in row.get('arms',{}) and row['arms'][arm].get(field) is not None]]},
    'peak_semantics':'maximum measured attempt, not additive cost'} for arm in ('S1','S3')]))
display(pd.DataFrame([{'id':row['id'],'stratum':row['length_stratum'],
    'status':row['status'],'S1':row.get('arms',{}).get('S1',{}).get('status','not_attempted'),
    'S3':row.get('arms',{}).get('S3',{}).get('status','not_attempted'),
    'error':row.get('error'),'evaluation_error':row.get('evaluation_error'),
    'ROUGE':bool(row.get('scores')),'BERTScore':bool(row.get('semantic_scores',{}).get('bertscore')),
    'source SBERTScore':bool(row.get('semantic_scores',{}).get('sbertscore'))}
    for row in receipt['rows']]))
print('Unknown usage:',summary['dispatch_usage'])
(RUN/'aggregate-report.json').write_text(json.dumps(summary,ensure_ascii=False,
    indent=2,allow_nan=False),encoding='utf8')
print('Aggregate report:',RUN/'aggregate-report.json')
"""),
        _cell("markdown", """## Complete outputs and visual checks

The next cells use only the sealed receipt. All 120 IDs remain in the denominator. The CSV contains full predictions and references; expand any ID below to read them in the notebook. Empty cells mean unavailable data, never zero. Charts are descriptive; grouped intervals do not establish population superiority.
"""),
        _cell("code", """from html import escape
from IPython.display import HTML

item_by_id={f"{item['split']}/{item['source_index']}":item for item in bundle['items']}
metric_keys={'ROUGE-L':'scores','BERTScore':'bertscore','source SBERTScore':'sbertscore'}
records=[]
for row in receipt['rows']:
    item=item_by_id[row['id']]
    arms=row.get('arms',{})
    values={'id':row['id'],'stratum':row['length_stratum'],'title':item['title'],
        'status':row['status'],'S1_status':arms.get('S1',{}).get('status','not_attempted'),
        'S3_status':arms.get('S3',{}).get('status','not_attempted'),
        'reference':item['reference_text'],'S1_summary':arms.get('S1',{}).get('summary'),
        'S3_summary':arms.get('S3',{}).get('summary'),
        'error':row.get('error'),'evaluation_error':row.get('evaluation_error')}
    for arm in ('S1','S3'):
        for field in ('prompt_tokens','output_tokens','generation_seconds','segmentation_seconds',
                      'peak_gpu_allocated_bytes','peak_gpu_reserved_bytes'):
            values[f'{arm}_{field}']=arms.get(arm,{}).get(field)
    for label,key in metric_keys.items():
        score=row.get('scores') if key=='scores' else row.get('semantic_scores',{}).get(key)
        for part in ('S1','S3','S3_minus_S1'):
            values[f'{label}_{part}']=score.get(part) if score else None
    records.append(values)
results=pd.DataFrame(records)
assert len(results)==120 and results['id'].is_unique
results.to_csv(RUN/'per-item-results.csv',index=False,encoding='utf-8-sig')
print('Complete item export:',RUN/'per-item-results.csv')
print('Sealed receipt, all calls, failures and run identity:',RUN/'frozen-receipt.json')
overview=results[['id','stratum','title','status','S1_status','S3_status',
    'ROUGE-L_S1','ROUGE-L_S3','ROUGE-L_S3_minus_S1',
    'BERTScore_S3_minus_S1','source SBERTScore_S3_minus_S1']]
display(HTML('<div style="max-height:550px;overflow:auto">'+
    overview.to_html(index=False,escape=True,na_rep='—')+'</div>'))
details=[]
for record in records:
    texts=''.join('<h5>'+escape(label)+'</h5><pre style="white-space:pre-wrap">'+
        escape(str(value) if value is not None else '[unavailable]')+'</pre>'
        for label,value in [('Creator abstract',record['reference']),
            ('S1 summary',record['S1_summary']),('S3 summary',record['S3_summary'])])
    scores='; '.join(label+' Δ='+str(record[f'{label}_S3_minus_S1'])
        for label in metric_keys if record[f'{label}_S3_minus_S1'] is not None)
    details.append('<details><summary>'+escape(record['id'])+' · '+
        escape(str(record['title']))+' · '+escape(record['status'])+'</summary><p>'+
        escape(scores or 'No paired metric')+'</p>'+texts+'</details>')
display(HTML('<h4>Full text for all 120 selected IDs</h4>'+''.join(details)))
"""),
        _cell("code", """import matplotlib.pyplot as plt

order=['short','medium','long']
metric_reports={'ROUGE-L':'rouge_l','BERTScore':'bertscore',
                'source SBERTScore':'sbertscore'}
fig,axes=plt.subplots(1,3,figsize=(17,4.5))
for ax,(label,key) in zip(axes,metric_reports.items()):
    report=summary['metrics'][key]
    counts=[report['strata'][s]['paired_scored'] for s in order]
    ax.bar(order,counts,color='#237f83')
    ax.set(title=label+' paired coverage',ylabel='scored / 40',ylim=(0,42))
    for i,count in enumerate(counts): ax.text(i,count+0.6,f'{count}/40',ha='center')
fig.suptitle('Coverage on the frozen 120-ID denominator')
fig.tight_layout(); fig.savefig(RUN/'paired-coverage.png',dpi=150,bbox_inches='tight'); plt.show()

fig,axes=plt.subplots(1,3,figsize=(17,4.5))
for ax,(label,key) in zip(axes,metric_reports.items()):
    report=summary['metrics'][key]
    valid=[(s,report['strata'][s]['S3_minus_S1']) for s in order
           if report['strata'][s]['S3_minus_S1'] is not None]
    if valid:
        ax.bar([s for s,_ in valid],[v for _,v in valid],
            color=['#2876ad' if v>=0 else '#b45e52' for _,v in valid])
    ax.axhline(0,color='black',linewidth=.8)
    ax.set(title=label+' paired mean S3 − S1',ylabel='score difference')
    if not valid: ax.text(.5,.5,'No paired scores',transform=ax.transAxes,ha='center')
fig.suptitle('Successful pairs only; no zero imputation')
fig.tight_layout(); fig.savefig(RUN/'paired-stratum-deltas.png',dpi=150,bbox_inches='tight'); plt.show()

paired=results.dropna(subset=['ROUGE-L_S1','ROUGE-L_S3'])
fig,axes=plt.subplots(1,2,figsize=(11,4.5))
if len(paired):
    axes[0].scatter(paired['ROUGE-L_S1'],paired['ROUGE-L_S3'],alpha=.65)
    lower=min(paired[['ROUGE-L_S1','ROUGE-L_S3']].min())
    upper=max(paired[['ROUGE-L_S1','ROUGE-L_S3']].max())
    axes[0].plot([lower,upper],[lower,upper],color='black',linewidth=.8)
    axes[1].hist(paired['ROUGE-L_S3_minus_S1'],bins=min(15,max(1,len(paired))))
else:
    for ax in axes: ax.text(.5,.5,'No paired scores',transform=ax.transAxes,ha='center')
axes[0].set(title='Per-item ROUGE-L agreement',xlabel='S1',ylabel='S3')
axes[1].set(title='Per-item paired differences',xlabel='S3 − S1',ylabel='record count')
fig.suptitle(f'Primary endpoint distribution: {len(paired)}/120 scored pairs')
fig.tight_layout(); fig.savefig(RUN/'primary-paired-distribution.png',dpi=150,bbox_inches='tight'); plt.show()

fig,axes=plt.subplots(1,2,figsize=(12,4))
for ax,field,unit in ((axes[0],'generation_seconds','seconds'),
                      (axes[1],'output_tokens','tokens')):
    values=[summary['resources_by_arm'][arm][field] for arm in ('S1','S3')]
    for i,value in enumerate(values):
        if value is not None: ax.bar(i,value,color=['#2876ad','#237f83'][i])
    ax.set_xticks((0,1),('S1','S3'))
    ax.set_xlim(-.6,1.6)
    ax.set(title='Measured '+field.replace('_',' '),ylabel=unit)
    for i,value in enumerate(values):
        ax.text(i,0 if value is None else value,
            str(round(value,1)) if value is not None else 'unavailable',ha='center',va='bottom')
fig.suptitle('Observed attempts only; see incomplete usage below')
fig.tight_layout(); fig.savefig(RUN/'measured-arm-resources.png',dpi=150,bbox_inches='tight'); plt.show()
print('Saved figures:',*(RUN/name for name in ('paired-coverage.png',
    'paired-stratum-deltas.png','primary-paired-distribution.png','measured-arm-resources.png')))
display(pd.DataFrame(summary['resources_by_arm']).T)
print('Unknown usage:',summary['dispatch_usage'])
print('Failure and unattempted IDs:')
display(results.loc[(results['status']!='completed') | results['error'].notna() |
    results['evaluation_error'].notna(),['id','stratum','status','S1_status','S3_status',
    'error','evaluation_error']].reset_index(drop=True))
"""),
    ]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3",
               "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
    notebook_path = ROOT / "experiments/notebooks/rq2-tib-120-evaluation-colab.ipynb"
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    package = OUTPUT / "rq2-tib-120-colab.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(notebook_path, notebook_path.name)
        for path in (bundle_path, manifest_path, protocol_path):
            archive.write(path, "data/" + path.name)
    return notebook_path, package


if __name__ == "__main__":
    print(build())
