"""Build standalone evaluation-only recovery without editing frozen generation."""

import ast
import base64
import gzip
import hashlib
import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]


def cell(kind, source, hidden=False):
    result = dict(cell_type=kind, metadata={'cellView': 'form'} if hidden else {},
                  source=source.splitlines(True))
    if kind == 'code':
        ast.parse(source)
        result.update(execution_count=None, outputs=[])
    return result


def build():
    registry = ROOT / 'experiments/registry/datasets'
    protocol = json.loads((registry / 'tib-rq2-rq4-120-protocol-261012.json').read_text())
    manifest = json.loads((registry / 'tib-rq2-rq4-120-cohort-261012.json').read_text())
    new_names = ['rq2_tib_semantic_v2', 'rq2_tib_rescore_runtime', 'rq2_tib_rescore_visualization']
    sources = {name: (ROOT / 'experiments/scripts' / f'{name}.py').read_bytes().decode('utf-8')
               for name in [*protocol['code_sha256'], *new_names]}
    for name, expected in protocol['code_sha256'].items():
        if hashlib.sha256(sources[name].encode()).hexdigest() != expected:
            raise ValueError(f'Frozen generation source changed: {name}')
    hashes = {name: hashlib.sha256(src.encode()).hexdigest() for name, src in sources.items()}
    packed = base64.b64encode(gzip.compress(json.dumps(sources).encode(), mtime=0)).decode()
    payload = '\n'.join(repr(line) for line in textwrap.wrap(packed, 110))
    old = json.loads((ROOT / 'experiments/notebooks/rq2-tib-120-evaluation-colab.ipynb').read_text(encoding='utf-8'))
    validation = ''.join(old['cells'][1]['source'])
    validation += f"\nassert MANIFEST['manifest_sha256']=={manifest['manifest_sha256']!r}\n"
    validation += f"assert PROTOCOL['protocol_sha256']=={protocol['protocol_sha256']!r}\n"
    validation += '''ORIGIN_DIR = RUN
OUT = ROOT/'semantic-rescore-v2'  # separate from original formal-run-v1
DEVICE = 'cuda'  # change to 'cpu' if no GPU; different device needs a NEW OUT folder
BATCH_SIZE = 16  # CPU: optionally 4; changed scorer/batch identity needs a NEW OUT
RETRY_FAILED = False  # explicit opt-in only after inspecting saved errors
assert OUT.resolve()!=ORIGIN_DIR.resolve()
if not (ORIGIN_DIR/'frozen-receipt.json').exists():
    raise FileNotFoundError('Original frozen-receipt.json missing; copy the full original run folder to Drive first.')
if not (ORIGIN_DIR/'dispatches.jsonl').exists():
    raise FileNotFoundError('Original dispatches.jsonl missing; keep the original call ledger.')
bundle={'metadata':metadata, 'items':items}
print('Read-only original run:',ORIGIN_DIR)
print('New semantic results:',OUT,'| device:',DEVICE)
'''
    cells = [cell('markdown', '''# RQ2 TIB 120: semantic-only rescore v2

**Không chạy Qwen, không sinh lại tóm tắt.** Notebook đọc 240 prediction và ROUGE-L đã lưu, chấm lại toàn bộ BERTScore + source SBERTScore bằng scorer v2. Lỗi retokenized window được sửa bằng cách chia trực tiếp token IDs, không cắt bỏ token. Hai encoder/revision và công thức chính giữ như protocol gốc; implementation mới được ghi thành scoring amendment, không giả định khớp identity v1.

Chuẩn bị Drive: giữ `MyDrive/RQ2_TIB_120_20261012/data` và toàn bộ `formal-run-v1` gồm `frozen-receipt.json` + `dispatches.jsonl`. Dừng phiên cũ; nên dùng phiên T4 mới để tránh giữ model cũ trong GPU. Chọn CPU bằng DEVICE nếu cần. Kết quả mới ở `semantic-rescore-v2`; không sửa/xóa thư mục gốc. Chạy theo thứ tự. 28 semantic scores v1 không được dùng lại; cả 120 mẫu được chấm theo cùng scorer mới.

Thời gian/resource generation cũ và chi phí rescore được báo riêng. Creator abstracts không phải factual-summary GT đã xác minh. Kết quả vẫn chỉ mô tả cohort; grouped intervals là exploratory, không chứng minh superiority trong quần thể.
'''), cell('code', validation)]
    cells.append(cell('code', '''# Install only missing/incompatible evaluation packages. Keep native NumPy stack intact.
import importlib.metadata, subprocess, sys
from packaging.requirements import Requirement
requirements=['transformers>=4.45,<5', 'sentence-transformers>=3,<6',
              'bert-score==0.3.13', 'sentencepiece>=0.2,<1', 'huggingface_hub>=0.25,<1']
missing=[]
for text in requirements:
    requirement=Requirement(text)
    try:
        installed=importlib.metadata.version(requirement.name)
        if installed not in requirement.specifier: missing.append(text)
    except importlib.metadata.PackageNotFoundError:
        missing.append(text)
if missing:
    subprocess.run([sys.executable,'-m','pip','install',*requirements],check=True)
    raise RuntimeError('Evaluation dependencies installed. Restart session, then rerun from the first cell to avoid stale binary modules. Files on Drive remain unchanged.')
import numpy as np, pandas as pd, matplotlib.pyplot as plt
import torch
if DEVICE=='cuda' and not torch.cuda.is_available():
    raise RuntimeError('No CUDA GPU available: enable T4 or set DEVICE=cpu before loading scorers.')
print('Evaluation device:',torch.cuda.get_device_name(0) if DEVICE=='cuda' else 'CPU')
'''))
    cells.append(cell('code', '''#@title Load verified bundled scoring code (no editing needed)
import base64, gzip
PAYLOAD = (
''' + payload + '''
)
SOURCES=json.loads(gzip.decompress(base64.b64decode(PAYLOAD)))
EXPECTED_HASHES = ''' + repr(hashes) + '''
CODE=pathlib.Path('/content/rq2_semantic_rescore_v2_code')
for name, source in SOURCES.items():
    actual=hashlib.sha256(source.encode()).hexdigest()
    assert actual==EXPECTED_HASHES[name]
    if name in PROTOCOL['code_sha256']: assert actual==PROTOCOL['code_sha256'][name]
for name, module in list(sys.modules.items()):
    if name.startswith('experiments') and getattr(module,'__file__',None):
        if not pathlib.Path(module.__file__).resolve().is_relative_to(CODE.resolve()):
            raise RuntimeError('Other benchmark modules are loaded. Restart session and rerun this notebook to use the verified scoring code.')
for folder in (CODE/'experiments', CODE/'experiments/scripts'):
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'__init__.py').write_text('')
for name,source in SOURCES.items():
    (CODE/'experiments/scripts'/f'{name}.py').write_text(source,encoding='utf-8')
sys.path.insert(0,str(CODE))
from experiments.scripts.rq2_tib_rescore_runtime import validate_origin,run_rescore,summarize_rescore
from experiments.scripts.rq2_tib_semantic_v2 import SemanticScorerV2
from experiments.scripts.rq2_tib_benchmark_metrics import sentences
origin=validate_origin(ORIGIN_DIR,bundle,MANIFEST,PROTOCOL)
OUT.mkdir(parents=True,exist_ok=True)
print('Verified original 120 records, both generated arms, source/reference identities and dispatch ledger.')
''', hidden=True))
    cells.append(cell('markdown', '''## Load encoders and verify repaired windowing

Chỉ nạp hai semantic encoders. Kiểm câu ngắn so với SentenceTransformer.encode và kiểm dữ liệu thật `valid/208` trước vòng chấm lại. Không dùng điểm hay nhãn để loại mẫu. Nếu kiểm tra thất bại, dừng để xem lỗi, không bật truncation hoặc bỏ mẫu.
'''))
    cells.append(cell('code', '''last_log=[0.0]
def show_progress(event):
    now=time.monotonic()
    important=event.get('status') in ('failed','completed','interrupted') and event.get('stage') not in ('source_embedding','sentence_windows')
    if important or now-last_log[0]>=5:
        print(event,flush=True);last_log[0]=now
metric_started=time.monotonic()
scorer=SemanticScorerV2(device=DEVICE,batch_size=BATCH_SIZE,on_event=show_progress).load()
samples=['Hello world.','Một câu tiếng Việt.','中文句子。']
direct=scorer._sentence_vectors(samples)
expected=scorer._sentence.encode(samples,batch_size=BATCH_SIZE,
    convert_to_numpy=True,normalize_embeddings=True,show_progress_bar=False)
assert np.allclose(direct,expected,atol=1e-5,rtol=1e-4), 'Short-input embedding equivalence failed'
old_by_id={r['id']:r for r in origin['rows']}
case=by_id['valid/208']
for label,text in [('source',case['source_text']),
                   ('S1',old_by_id['valid/208']['arms']['S1']['summary']),
                   ('S3',old_by_id['valid/208']['arms']['S3']['summary'])]:
    vectors=scorer._sentence_vectors(sentences(text),input_kind='regression_'+label)
    assert np.isfinite(vectors).all()
    print('valid/208 window preflight:',label,'sentences',len(vectors))
metric_initialization_seconds=time.monotonic()-metric_started
import platform
environment={'device':DEVICE,'gpu_name':torch.cuda.get_device_name(0) if DEVICE=='cuda' else None,
    'platform':platform.platform(),'cpu':platform.processor(),'torch':torch.__version__,
    'cpu_threads':torch.get_num_threads(),'scorer':scorer.metadata,
    'initialization_and_preflight_seconds':metric_initialization_seconds}
environment_path=OUT/f'scoring-environment-{time.time_ns()}.json'
environment_path.write_text(json.dumps(environment,indent=2),encoding='utf-8')
print('This scoring session environment:',environment_path)
print('Scorer v2 preflight passed; initialization+preflight seconds:',metric_initialization_seconds)
'''))
    cells.append(cell('markdown', '''## Rescore all 120 pairs

Checkpoint sau từng mẫu; resume cùng identity sẽ dùng lại điểm v2 đã hoàn tất. Mẫu lỗi được ghi, vòng chạy tiếp tục các mẫu sau. RETRY_FAILED mặc định False; chỉ bật khi chủ động thử lại lỗi đã xem. Không có automatic generation retry. Không chạy đồng thời hai phiên cùng OUT. Nếu tiến trình bị kill và còn `.rescore.lock`, xác nhận phiên cũ đã dừng rồi mới xóa riêng lock đó; không xóa receipt.
'''))
    cells.append(cell('code', '''receipt=run_rescore(ORIGIN_DIR,bundle,scorer,OUT,device=DEVICE,
    metric_initialization_seconds=metric_initialization_seconds,
    retry_failed=RETRY_FAILED,on_event=show_progress)
summary=summarize_rescore(receipt)
print('Rescore coverage:',summary['counts'])
for metric,report in summary['metrics'].items():
    print(metric,report['overall']['paired_scored'],'/ 120')
'''))
    cells.append(cell('markdown', '''## Aggregate, full tables and figures

Các bảng gồm đầy đủ 120 ID, failure/pending ledger, per-stratum paired means, grouped intervals và toàn bộ reference/S1/S3 có thể mở từng mẫu. PNG/CSV ghi vào thư mục rescore mới. Điểm thiếu giữ null, không gán 0. Không gộp thời gian rescore vào generation costs lịch sử.
'''))
    cells.append(cell('code', '''from experiments.scripts.rq2_tib_rescore_visualization import render_rescore
(OUT/'aggregate-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
render_rescore(receipt,summary,origin,bundle,OUT)
print('Aggregate:',OUT/'aggregate-report.json')
print('Original run preserved:',ORIGIN_DIR)
'''))
    cells.append(cell('markdown', '''## Completion and handoff

Hoàn tất semantic khi cả BERTScore và source SBERTScore có **120/120 paired scored**, không có failure/pending/interrupted. Nếu thiếu điểm, notebook vẫn xuất coverage và ledger, không tuyên bố hoàn tất. Giữ `aggregate-report.json`, receipt rescore, bảng CSV, PNG và notebook có outputs để nhận xét. Lần chuẩn bị này chỉ kiểm code/tests; chưa chạy pretrained encoders trên Colab hay chấm lại 120 mẫu.
'''))
    notebook=dict(cells=cells,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3'),
                  language_info=dict(name='python'),colab=dict(name='rq2-tib-120-semantic-rescore-colab.ipynb')),
                  nbformat=4,nbformat_minor=5)
    for i,entry in enumerate(cells):entry['id']=f'rescore-{i:02d}'
    path=ROOT/'experiments/notebooks/rq2-tib-120-semantic-rescore-colab.ipynb'
    path.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print(path)


if __name__=='__main__':build()
