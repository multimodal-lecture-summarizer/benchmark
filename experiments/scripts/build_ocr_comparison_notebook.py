"""Build a self-contained validation OCR comparison notebook for Colab."""

import ast
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAMES = ('ocr_validation_recognition', 'summarize_ocr_validation',
         'ocr_comparison_runtime', 'ocr_comparison_visualization')


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.splitlines(True))
    if kind == 'code':
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


def build():
    sources = {f'experiments/scripts/{name}.py':
               (ROOT / f'experiments/scripts/{name}.py').read_text(encoding='utf-8')
               for name in NAMES}
    review = ROOT / 'experiments/outputs/ocr_validation_261009/eda_dhash_different_label_review.csv'
    with review.open(encoding='utf-8') as handle:
        flagged = sorted({r[k] for r in csv.DictReader(handle) for k in ('left', 'right')})
    assert len(flagged) == 537
    cells = [cell('markdown', '''# IIIT-CVID: EDA và so sánh OCR recognition

So sánh **EasyOCR 1.7.2 CPU** và **PaddleOCR 2.8.1 / PaddlePaddle 2.6.2 CPU**, trên cùng **15.379 word crops validation**. Đây là nhận dạng chữ trên crop có sẵn; không đo phát hiện chữ trên frame, RAG hoặc chất lượng tóm tắt. Nhãn nguồn giữ nguyên. Validation đã được xem trong EDA và đánh giá trước đó; không gọi đây là unseen test.

Chạy các cell theo thứ tự trên Colab CPU. Notebook giữ nguyên NumPy/Pandas/Matplotlib/Pillow của kernel Colab (kể cả Python 3.13), kiểm tra import trước khi tải dữ liệu. NumPy 1.26 chỉ được cài trong môi trường inference Python 3.11 riêng ở /content. Notebook tự tải ZIP nguồn (~2,43 GB), xác minh SHA-256 và chỉ giải nén validation. Kết quả ghi trực tiếp vào Drive. Chọn RUN_ID mới nếu đổi môi trường/trọng số; giữ nguyên RUN_ID để resume. Không mở hai phiên ghi cùng thư mục. Cài đặt/tải trọng số cần mạng; inference dùng model đã xác minh.

CER chính = tổng Levenshtein / tổng ký tự tham chiếu, sau NFKC + casefold + gộp whitespace; giữ dấu câu và chữ số. Lỗi inference được ghi và chấm như dự đoán rỗng. So sánh đầy đủ chỉ xuất khi cả hai hệ thống phủ toàn bộ cohort. Notebook chưa được chạy inference trên Colab trong lần chuẩn bị này.
''')]
    cells.append(cell('code', '''from pathlib import Path
import os, sys, subprocess, json, hashlib, zipfile
IN_COLAB = Path('/content').exists()
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
RUN_ID = 'ocr-validation-261013-v1'  # đổi ID khi đổi môi trường; giữ để resume
WORK = Path('/content/ocr-comparison') if IN_COLAB else Path.cwd() / 'ocr-comparison-work'
PERSIST = Path('/content/drive/MyDrive/OCR') if IN_COLAB else WORK / 'persistent'
OUT = PERSIST / RUN_ID
MODEL = WORK / 'models'
ARCHIVE = WORK / 'IIIT-CVid.zip'  # có thể trỏ tới ZIP đã tải; vẫn kiểm hash
DATA = WORK / 'IIIT-CVid'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
# Do not mutate the live kernel's binary scientific stack. Colab preloads it.
# Check a fresh process first, then the live kernel, to catch stale loaded modules.
probe = """import sys, json, io
import numpy as np, numpy.random, pandas as pd, matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from PIL import Image
import PIL
np.random.default_rng(0).integers(0, 10, 3)
pd.DataFrame({'x': [1, 2]}).sum()
Figure().savefig(io.BytesIO(), format='png')
Image.new('RGB', (2, 2)).save(io.BytesIO(), format='PNG')
print(json.dumps({'numpy': np.__version__, 'pandas': pd.__version__,
                  'matplotlib': matplotlib.__version__, 'Pillow': PIL.__version__,
                  'python': sys.version.split()[0]}))
"""
checked = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True)
if checked.returncode:
    print(checked.stderr)
    raise RuntimeError('Kernel scientific stack is incompatible. Use the ABI recovery instructions at the end of this notebook; then restart session and rerun.')
try:
    import numpy as np, numpy.random, pandas as pd, matplotlib, PIL
    np.random.default_rng(0).integers(0, 10, 3)
except (ImportError, ValueError, AttributeError) as exc:
    raise RuntimeError('Live kernel has stale/incompatible binary modules. Restart session after ABI recovery, then rerun.') from exc
analysis_env = json.loads(checked.stdout.strip().splitlines()[-1])
loaded = {'numpy': np.__version__, 'pandas': pd.__version__,
          'matplotlib': matplotlib.__version__, 'Pillow': PIL.__version__}
if any(analysis_env[k] != v for k, v in loaded.items()):
    raise RuntimeError('Loaded versions differ from installed versions; restart session and rerun.')
(OUT / 'kernel-analysis-environment.json').write_text(json.dumps(analysis_env, indent=2))
print('Kernel analysis preflight:', analysis_env)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q',
                'huggingface_hub==0.30.2', 'uv==0.6.17'], check=True)
print('Persistent results:', OUT)
'''))
    cells.append(cell('code', f'''# Embedded audited sources; no repository clone required.
SOURCES = {sources!r}
for relative, source in SOURCES.items():
    path = WORK / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')
sys.path.insert(0, str(WORK))
os.chdir(WORK)
SOURCE_DIGESTS = {{name: hashlib.sha256(src.encode()).hexdigest() for name, src in SOURCES.items()}}
binding = OUT / 'source-code-identity.json'
if binding.exists() and json.loads(binding.read_text()) != SOURCE_DIGESTS:
    raise ValueError('Runner changed: use a new RUN_ID')
binding.write_text(json.dumps(SOURCE_DIGESTS, indent=2))
'''))
    cells.append(cell('code', '''from huggingface_hub import hf_hub_download, list_repo_files
from experiments.scripts.summarize_ocr_validation import verify_archive, verify_extraction
from experiments.scripts.ocr_validation_recognition import load_cohort, normalize, SOURCE_SHA256
REPO = 'staghado/IIIT-CVid'
REVISION = '8159222f11460bff70bec7990ade19c468755fe4'
if not ARCHIVE.exists():
    choices = [p for p in list_repo_files(REPO, repo_type='dataset', revision=REVISION)
               if p.endswith('.zip')]
    assert len(choices) == 1, choices
    cached = hf_hub_download(REPO, choices[0], repo_type='dataset', revision=REVISION)
    import shutil
    shutil.copyfile(cached, ARCHIVE)
verify_archive(ARCHIVE)
with zipfile.ZipFile(ARCHIVE) as archive:
    selected = [m for m in archive.infolist() if not m.is_dir() and
                m.filename.startswith(('IIIT-CVid/Crops/val/', 'IIIT-CVid/Frames/val/'))]
    for member in selected:
        destination = (WORK / member.filename).resolve()
        if not destination.is_relative_to(WORK.resolve()):
            raise ValueError('Unsafe ZIP member')
        if not destination.exists():
            archive.extract(member, WORK)
verified = verify_extraction(ARCHIVE, DATA)
cohort = load_cohort(DATA)
assert len(cohort) == 15379
(OUT / 'dataset-receipt.json').write_text(json.dumps(dict(
    repo=REPO, revision=REVISION, source_sha256=SOURCE_SHA256,
    crops=len(cohort), verified_crop_and_label_files=verified,
    scope='released validation crops only; original labels; exposed validation'), indent=2))
print('Verified crops:', len(cohort), '| files:', verified)
'''))
    cells.append(cell('markdown', '''## EDA trước inference

Decode mọi crop, kiểm nhãn và biểu đồ phân bố theo course/video, độ dài, kích thước, tương phản. Độ lệch chuẩn cường độ chỉ là proxy mô tả, không phải nhãn chất lượng ảnh. 537 ID dưới đây là cờ xem xét từ dHash lịch sử (khác nhãn), không chứng minh annotation sai; screening không đầy đủ. Không loại chúng khỏi kết quả chính.
'''))
    cells.append(cell('code', f'''import numpy as np, pandas as pd, matplotlib.pyplot as plt
from PIL import Image
FLAGGED_IDS = {flagged!r}
rows = []
for crop_id, path, label in cohort:
    with Image.open(path) as image:
        gray = np.asarray(image.convert('L'))
        width, height = image.size
    parts = crop_id.split('/')
    rows.append(dict(crop_id=crop_id, course=parts[2], video='/'.join(parts[2:4]),
                     label=label, chars=len(normalize(label)), width=width, height=height,
                     contrast=float(gray.std()), has_digit=any(c.isdigit() for c in label),
                     punctuation=any(not c.isalnum() and not c.isspace() for c in label),
                     review_flag=crop_id in FLAGGED_IDS))
features = pd.DataFrame(rows)
assert features.crop_id.is_unique and features.review_flag.sum() == 537
assert (features[['width', 'height', 'chars']] > 0).all().all()
features.to_csv(OUT / 'cohort-features.csv', index=False)
display(features.groupby('course').agg(crops=('crop_id','size'), videos=('video','nunique')))
display(features[['chars','width','height','contrast']].describe())
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
features.groupby('course').size().plot.bar(ax=axes[0,0], title='Crops/course')
features.groupby('video').size().plot.hist(ax=axes[0,1], bins=30, title='Crops/video')
for ax, name in zip([axes[0,2], *axes[1]], ['chars','width','height','contrast']):
    ax.hist(features[name], bins=35); ax.set_title(name)
fig.tight_layout(); fig.savefig(OUT / 'eda-distributions.png'); plt.show()
sample = pd.concat([group.sort_values(['contrast','crop_id']).iloc[
    [int((len(group)-1)*q) for q in (0.1,0.5,0.9)]]
    for _, group in features.groupby('course')])
fig, axes = plt.subplots(5,3,figsize=(13,10))
for ax, (idx,row) in zip(axes.flat, sample.iterrows()):
    ax.imshow(Image.open(DATA/row.crop_id)); ax.set_title(row.label); ax.axis('off')
fig.tight_layout(); fig.savefig(OUT/'eda-crop-gallery.png'); plt.show()
'''))
    cells.append(cell('markdown', '''## Môi trường CPU riêng và trọng số

Chạy tuần tự, mỗi thư viện 1 CPU thread. Cấu hình batch của mỗi engine giữ theo runner lịch sử (EasyOCR 1, PaddleOCR 32). Notebook ghi thời gian phiên để vận hành, không dùng nó để kết luận tốc độ engine; resume và môi trường Colab có thể thay đổi tài nguyên. Không tự lấy model thay thế nếu hash sai.
'''))
    cells.append(cell('code', '''ENV = WORK / 'ocr-py311'
subprocess.run([sys.executable, '-m', 'uv', 'venv', '--python', '3.11',
                '--python-preference', 'only-managed', str(ENV), '--allow-existing'], check=True)
PY = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
subprocess.run([sys.executable, '-m', 'uv', 'pip', 'install', '--python', str(PY),
    'torch==2.5.1', 'torchvision==0.20.1', '--index-url',
    'https://download.pytorch.org/whl/cpu'], check=True)
subprocess.run([sys.executable, '-m', 'uv', 'pip', 'install', '--python', str(PY),
    'setuptools==75.8.0', 'numpy==1.26.4', 'paddlepaddle==2.6.2', 'paddleocr==2.8.1',
    'easyocr==1.7.2', 'opencv-python==4.6.0.66',
    'opencv-contrib-python==4.6.0.66', 'opencv-python-headless==4.6.0.66'], check=True)
CHILD_ENV = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                 OPENBLAS_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='')
setup = ''' + repr('''from pathlib import Path
print('Preflight stage: importing OCR libraries', flush=True)
import easyocr, paddleocr, paddle, torch, sys
root = Path(sys.argv[1])
torch.set_num_threads(1)
print('Preflight stage: loading EasyOCR recognition weights', flush=True)
easyocr.Reader(['en'], gpu=False, detector=False, recognizer=True,
               model_storage_directory=str(root/'easyocr'), download_enabled=True, verbose=False)
print('Preflight stage: loading PaddleOCR recognition weights', flush=True)
paddleocr.PaddleOCR(use_angle_cls=False, lang='en', det=False, rec=True, use_gpu=False,
                   show_log=False, cpu_threads=1, ocr_version='PP-OCRv4',
                   rec_model_dir=str(root/'paddleocr/en_PP-OCRv4_rec_infer'))
print('Installed engines:', easyocr.__version__, paddleocr.__version__, flush=True)
assert easyocr.__version__ == '1.7.2' and paddleocr.__version__ == '2.8.1'
print('Preflight:', sys.version, paddle.__version__, torch.__version__)
import numpy as np
from PIL import Image
from experiments.scripts.ocr_comparison_runtime import verify_models, load_engine
from experiments.scripts.ocr_validation_recognition import load_cohort
cohort = load_cohort(Path(sys.argv[2]))
with Image.open(cohort[0][1]) as image:
    pixels = np.asarray(image.convert('RGB'))
for engine in ('easyocr_cpu','paddleocr'):
    print('Preflight stage: model hash and one-crop inference:', engine, flush=True)
    verify_models(engine, root)
    predictor, engine_version, batch = load_engine(engine, root)
    output = predictor([pixels])
    assert len(output) == 1 and isinstance(output[0], str), (engine, output)
    print('Inference preflight passed:', engine, engine_version)
''') + '''
lock = subprocess.check_output([sys.executable, '-m', 'uv', 'pip', 'freeze',
                               '--python', str(PY)], text=True)
(OUT/'installed-packages.txt').write_text(lock)

def run_logged(command, log_path, cwd, env):
    # Merge stderr into stdout so the real child traceback is visible and persisted.
    with log_path.open('w', encoding='utf-8') as log:
        with subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                              errors='replace', bufsize=1) as process:
            try:
                for line in process.stdout:
                    print(line, end='', flush=True)
                    log.write(line); log.flush()
                returncode = process.wait()
            except BaseException:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
                raise
    if returncode:
        raise RuntimeError(f'OCR preflight failed (exit {returncode}). The original error is printed above and saved in {log_path}.')

import time
PREFLIGHT_LOG = OUT / f'ocr-preflight-{time.time_ns()}.log'
run_logged([str(PY), '-u', '-c', setup, str(MODEL), str(DATA)],
           PREFLIGHT_LOG, WORK, CHILD_ENV)
print('Preflight log:', PREFLIGHT_LOG)
'''))
    for name in ('easyocr_cpu', 'paddleocr'):
        cells.append(cell('code', f'''# Rerun this cell after interruption; committed rows are checked and reused.
subprocess.run([str(PY), '-m', 'experiments.scripts.ocr_comparison_runtime',
    '--engine', {name!r}, '--dataset-root', str(DATA),
    '--output-root', str(OUT), '--model-root', str(MODEL)],
    cwd=WORK, env=CHILD_ENV, check=True)
'''))
    cells.append(cell('code', '''# Refuses partial, duplicate, mixed-source or mismatched reference rows.
subprocess.run([str(PY), '-m', 'experiments.scripts.summarize_ocr_validation',
    '--dataset-root', str(DATA), '--source-archive', str(ARCHIVE),
    '--output-root', str(OUT)], cwd=WORK, env=CHILD_ENV, check=True)
summary = json.loads((OUT/'paired_full.summary.json').read_text())
display(pd.DataFrame({k:summary[k] for k in ['easyocr','paddleocr']}).T)
print('Paddle - Easy CER:', summary['paddle_minus_easy_micro_cer'])
print('95% paired video-cluster bootstrap:', summary['paired_video_bootstrap_95_interval'])
per_course = pd.DataFrame({k:{m:v[m]['micro_cer'] for m in ['easyocr','paddleocr']}
                          for k,v in summary['by_course'].items()}).T
per_course.plot.bar(figsize=(9,4), ylabel='Micro CER', title='CER by course')
plt.tight_layout(); plt.savefig(OUT/'cer-by-course.png'); plt.show()
'''))
    cells.append(cell('code', '''from experiments.scripts.summarize_ocr_validation import load, score
refs = {key:label for key, _, label in cohort}
easy = load('easyocr_cpu', OUT, refs); paddle = load('paddleocr', OUT, refs)
paired = features.set_index('crop_id').copy()
for name, records in [('easy', easy), ('paddle', paddle)]:
    paired[name+'_edits'] = pd.Series({k:v['edit_distance'] for k,v in records.items()})
paired['refchars'] = pd.Series({k:v['reference_chars'] for k,v in easy.items()})
paired['length_bin'] = pd.cut(paired.chars, [0,2,5,10,float('inf')])
paired['width_bin'] = pd.cut(paired.width, [0,32,64,128,float('inf')])
paired['contrast_bin'] = pd.cut(paired.contrast, [0,20,40,60,128], include_lowest=True)
for feature in ['length_bin','width_bin','contrast_bin','has_digit','punctuation','review_flag']:
    grouped = paired.groupby(feature, observed=True).agg(
        crops=('refchars','size'), refchars=('refchars','sum'),
        easy_edits=('easy_edits','sum'), paddle_edits=('paddle_edits','sum'))
    grouped['easy_cer'] = grouped.easy_edits/grouped.refchars
    grouped['paddle_cer'] = grouped.paddle_edits/grouped.refchars
    display(grouped)
    grouped.to_csv(OUT/f'error-by-{feature}.csv')
retained = [k for k in easy if k not in FLAGGED_IDS]
display(pd.DataFrame({'easy':score([easy[k] for k in retained]),
                      'paddle':score([paddle[k] for k in retained])}).T)
print('Sensitivity ONLY, not cleaned GT: excludes historical review flags; primary keeps all crops.')
failures = [{**row, 'engine':name} for name,records in [('easy',easy),('paddle',paddle)]
            for row in records.values() if row['error'] is not None]
(OUT/'failure-ledger.json').write_text(json.dumps(failures, ensure_ascii=False, indent=2))
paired.to_csv(OUT/'paired-errors.csv')
'''))
    cells.append(cell('code', '''# Deterministic examples: largest edit gaps, not random cherry-picked successes.
paired['gap'] = paired.paddle_edits-paired.easy_edits
examples = pd.concat([paired.sort_values(['gap'], kind='stable').head(6),
                      paired.sort_values(['gap'], ascending=False, kind='stable').head(6)])
fig, axes = plt.subplots(4,3,figsize=(14,10))
for ax,(key,row) in zip(axes.flat, examples.iterrows()):
    ax.imshow(Image.open(DATA/key)); ax.axis('off')
    ax.set_title(f"GT: {row.label}\\nEasy: {easy[key]['prediction']} | Paddle: {paddle[key]['prediction']}", fontsize=9)
fig.tight_layout(); fig.savefig(OUT/'paired-error-gallery.png'); plt.show()
print('Complete outputs:', OUT)
print('Interpretation: compare overall and course-level CER, interval, failures and label-flag sensitivity.')
print('Scope stays exposed validation crop recognition; no frame detection or unseen-test claim.')
'''))
    cells.append(cell('markdown', '''## Bảng và đồ thị phân tích đầy đủ

Hiển thị kết quả tổng thể, bảng đầy đủ 140 video, phân bố CER theo video, paired scatter/delta, 7 nhóm đặc điểm crop, số crop thắng/thua, exact-word agreement, độ nhạy với cờ nhãn và khoảng tin cậy bootstrap. Các bảng xuất CSV và hình xuất PNG vào Drive. Nhóm đặc điểm chỉ mô tả, không xác lập quan hệ nhân quả; nhãn nguồn và cohort chính giữ nguyên.
'''))
    cells.append(cell('code', '''from experiments.scripts.ocr_comparison_visualization import render_comparison
render_comparison(paired, easy, paddle, summary, OUT)
print('Full tables and figures saved to:', OUT)
'''))
    cells.append(cell('markdown', '''## Gửi kết quả để nhận xét

Sau khi hoàn thành, giữ notebook có output và thư mục RUN_ID gồm `paired_full.summary.json`, hai JSONL, identity receipts, cohort features, bảng lỗi và PNG. Nếu Colab ngắt: dừng phiên cũ, reconnect, chạy lại từ đầu với RUN_ID cũ; checkpoint không khớp sẽ dừng và yêu cầu RUN_ID mới. Nếu còn file `<engine>.lock` sau khi tiến trình bị kill, xác nhận phiên cũ đã dừng rồi xóa riêng file lock đó trước khi resume. JSONL hỏng ở dòng cuối do ngắt ghi sẽ bị từ chối, không tự bỏ dữ liệu. Không chỉnh nhãn hoặc chọn mẫu sau khi xem điểm.

Nguồn: [IIIT-CVID mirror, pinned revision](https://huggingface.co/datasets/staghado/IIIT-CVid/tree/8159222f11460bff70bec7990ade19c468755fe4), [EasyOCR 1.7.2](https://pypi.org/project/easyocr/1.7.2/), [PaddleOCR 2.8.1](https://pypi.org/project/paddleocr/2.8.1/).
'''))
    cells.append(cell('markdown', '''## Phục hồi lỗi NumPy ABI từ bản notebook cũ (chỉ khi đã gặp lỗi)

Nếu kernel Python 3.13 hiện lỗi `numpy.dtype size changed`, bản cũ đã có ràng buộc NumPy <2 không phù hợp kernel. Không chạy lại cell cài đặt cũ. Chạy cell phục hồi dưới đây sau khi đổi `REPAIR_NATIVE_KERNEL` thành True, sau đó chọn **Runtime → Restart session** và chạy notebook đã cập nhật từ đầu. Restart session giữ file trong /content; không chọn Delete runtime nếu muốn giữ ZIP đã tải. Cell này không thay đổi môi trường OCR Python 3.11 hoặc file dữ liệu/nhãn. Chỉ dùng gói wheel, không build NumPy từ source. Mặc định cell không thực hiện thay đổi.
'''))
    cells.append(cell('code', '''REPAIR_NATIVE_KERNEL = False  # chỉ bật nếu kernel hiện bị lỗi ABI
if REPAIR_NATIVE_KERNEL:
    if sys.version_info[:2] not in ((3, 10), (3, 11), (3, 12), (3, 13)):
        raise RuntimeError('Recovery pins support Python 3.10–3.13; inspect this runtime first.')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade',
        '--force-reinstall', '--no-cache-dir', '--only-binary=:all:',
        'numpy==2.2.6', 'pandas==2.2.3', 'matplotlib==3.10.6', 'Pillow==11.3.0'], check=True)
    raise RuntimeError('Recovery installed. Select Runtime → Restart session now, then rerun from the first cell. Do not keep using this loaded kernel.')
else:
    print('Optional ABI recovery skipped; nothing changed.')
'''))
    notebook = dict(cells=cells, metadata=dict(kernelspec=dict(display_name='Python 3', language='python', name='python3'),
                    language_info=dict(name='python'), colab=dict(name='iiit_cvid_ocr_comparison_colab.ipynb')),
                    nbformat=4, nbformat_minor=5)
    for i, entry in enumerate(cells):
        entry['id'] = f'ocr-{i:02d}'
    target = ROOT/'experiments/notebooks/iiit_cvid_ocr_comparison_colab.ipynb'
    target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    build()
