"""Build the Colab notebook for benchmark 03a (object detection): smoke test and full run.

Usage (from benchmark/): python experiments/scripts/build_detection_benchmark_notebook.py
Inputs are the frozen artifacts of the qualification run (hash-verified in the notebook).
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
MODULES = ["experiments/scripts/detection_tracking_qualification.py",
           "experiments/scripts/detection_scoring.py",
           "experiments/scripts/paired_bootstrap.py",
           "experiments/scripts/detection_runner.py"]
VENDOR_DIR = REPO / "multimodal-lecture-summarizer/ai_workers/modules/visual_v2/florence2_vendor"
VENDOR_CODE = ["configuration_florence2.py", "modeling_florence2.py", "processing_florence2.py"]
OUTPUT = ROOT / "experiments/notebooks/03a-object-detection-benchmark-colab.ipynb"


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.strip("\n").splitlines(True))
    if kind == "code":
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


INTRO = r'''
# 03a — Object detection benchmark (D-A LVVO, D-B COCO subset)

Notebook chạy **cả smoke test và full run** cho 03a. Đổi `MODE` ở cell cấu hình: `'smoke'` (20 ảnh mỗi track, kiểm tra pipeline, đo latency/VRAM, **không công bố điểm**) hoặc `'full'` (toàn bộ cohort đã đóng băng).

| Track | Cohort (đã đóng băng) | Ứng viên |
|---|---|---|
| D-B closed | COCO val2017 subset, 2.000 ảnh, 10 lớp | YOLOv8n, YOLO11n, RT-DETR-R18vd |
| D-B open | cùng cohort | Florence-2-base `<OD>` (score-less), GroundingDINO-base |
| D-A open (zero-shot) | LVVO 1.000 ảnh, 4 lớp | Florence-2-base `<OD>`, Florence-2-base `<OPEN_VOCABULARY_DETECTION>` *(bổ sung, cần duyệt)*, GroundingDINO-base |

Mô hình COCO-pretrained **không có lớp table/chart/photo/illustration** nên không chấm trên D-A (`no_corresponding_class`, không ép ánh xạ). D-A và D-B, closed và open luôn báo riêng, không gộp xếp hạng.

**Quy tắc đã đóng băng:** metric = COCO mAP@[.50:.95] (pycocotools 2.0.11); conf = 0.001 cho mAP (0.25 chỉ cho P/R chẩn đoán); NMS IoU 0.7; max 100 box/ảnh; batch 1; ngưỡng thực tế ΔmAP = 0.02; bootstrap theo ảnh (D-B) hoặc nhóm nguồn (D-A), 10.000 lần, cùng lần lấy mẫu cho mọi hệ thống; ảnh lỗi (decode, OOM, timeout, sai kích thước) được **đếm riêng** và chấm như không có dự đoán. Florence-2 **không có score** (mọi box = 1.0): mAP của nó bị chặn trên, chỉ là baseline, không xếp hạng tuyệt đối với mô hình có score.

**Ngân sách:** trần ~15 GPU-giờ cho 03a+03b. Sau smoke, notebook ước tính GPU-giờ của full run từ latency đo thật; nếu vượt trần, **dừng và hỏi** (không tự cắt phạm vi). Full run từ chối chạy nếu chưa có smoke trong cùng `RUN_ID`.

**Giấy phép phần mềm/mô hình (nghiên cứu):** Ultralytics (code + trọng số YOLO) là AGPL-3.0; RT-DETR-R18vd, GroundingDINO: Apache-2.0; Florence-2: MIT. Dữ liệu: COCO ảnh theo điều khoản Flickr, LVVO CC BY 4.0. Không phát hành lại ảnh.

Kết quả ghi vào Drive `MyDrive/DetTrack/<RUN_ID>/`: dự đoán thô (`preds/*.jsonl`), manifest, bảng, hình, `bundle.zip`.
'''

SETUP = r'''
from pathlib import Path
import os, sys, json, hashlib, subprocess, time, shutil, zipfile, re, platform, traceback
from datetime import datetime, timezone

# ============================ CẤU HÌNH ============================
MODE = 'smoke'            # 'smoke' = 20 ảnh/track, không công bố; 'full' = toàn cohort (cần smoke trước)
N_SMOKE = 20
RUN_ID = 'det-03a-261026-v1'
GPU_BUDGET_HOURS = 15.0   # trần chung 03a + 03b; vượt thì dừng và hỏi
ALLOW_OVER_BUDGET = False # chỉ đặt True sau khi người duyệt ngân sách đồng ý
RUN_ABLATION = False      # imgsz 416 cho mô hình closed (tách khỏi xếp hạng chính), chỉ ở full
# ===================================================================

IN_COLAB = Path('/content').exists()
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
WORK = Path('/content/det03a') if IN_COLAB else Path.cwd() / 'det03a-work'
PERSIST = Path('/content/drive/MyDrive/DetTrack') if IN_COLAB else WORK / 'persistent'
PRIOR = Path(os.environ.get('DT_PRIOR', PERSIST / 'det-track-qualification-261026-v3'))
OUT = PERSIST / RUN_ID
for p in (WORK, OUT, OUT / 'preds', OUT / 'figures', OUT / 'tables'):
    p.mkdir(parents=True, exist_ok=True)
if not PRIOR.exists():
    raise FileNotFoundError(f'Thiếu {PRIOR}: cần kết quả qualification đã đóng băng.')
assert MODE in ('smoke', 'full')
if os.environ.get('DT_SKIP_PIP') != '1':
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'ultralytics==8.4.190', 'pycocotools==2.0.11',
                    'transformers==4.57.6', 'timm', 'einops', 'gdown', 'huggingface_hub', 'safetensors', 'scipy'], check=True)
import torch
GPU = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
print('MODE:', MODE, '| GPU:', GPU, '| torch', torch.__version__)
if GPU is None:
    print('CẢNH BÁO: không có GPU; latency/VRAM đo trên CPU không dùng được để ước tính ngân sách.')
'''

EMBED = r'''
SOURCES = {sources!r}
VENDOR_CODE = {vendor!r}
for relative, source in SOURCES.items():
    path = WORK / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')
    (path.parent / '__init__.py').touch()
(WORK / 'experiments' / '__init__.py').touch()
FLORENCE_DIR = WORK / 'florence2_vendor'
FLORENCE_DIR.mkdir(exist_ok=True)
for name, source in VENDOR_CODE.items():
    (FLORENCE_DIR / name).write_bytes(source.encode('utf-8'))
sys.path.insert(0, str(WORK))
DIGESTS = {{n: hashlib.sha256(s.encode()).hexdigest() for n, s in {{**SOURCES, **VENDOR_CODE}}.items()}}
binding = OUT / 'source-code-identity.json'
if binding.exists() and json.loads(binding.read_text()) != DIGESTS:
    raise ValueError('Mã nguồn thay đổi: dùng RUN_ID mới')
binding.write_text(json.dumps(DIGESTS, indent=2))

import numpy as np, pandas as pd, matplotlib, requests
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from collections import Counter
from experiments.scripts import detection_tracking_qualification as q
from experiments.scripts import detection_scoring as ds
from experiments.scripts import paired_bootstrap as pb
from experiments.scripts import detection_runner as dr
plt.rcParams.update({'figure.dpi': 100, 'axes.grid': True, 'grid.alpha': .25, 'axes.spines.top': False, 'axes.spines.right': False})
try:
    display
except NameError:
    display = print
SEED = 20261026
'''

HELPERS = r'''
def show_png(path):
    try:
        from IPython.display import display as _d, Image as _I
        _d(_I(filename=str(path)))
    except Exception:
        print('saved', path)


def savefig(fig, name):
    fig.tight_layout()
    path = OUT / 'figures' / f'{MODE}_{name}'
    fig.savefig(path, dpi=110)
    plt.close(fig)
    show_png(path)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=float), encoding='utf-8')


def download(url, dest, retries=3, timeout=60):
    dest = Path(dest); dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + '.part')
                with open(tmp, 'wb') as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(dest); return dest
        except Exception as exc:
            last = exc; time.sleep(2 ** attempt)
    raise ConnectionError(f'{url}: {last!r}')


BANNER = '*** SMOKE: kiểm tra pipeline trên %d ảnh/track, KHÔNG công bố hay so sánh các điểm này ***' % N_SMOKE
if MODE == 'smoke':
    print(BANNER)
'''

FROZEN = r'''
REG = {k: json.loads((PRIOR / 'registry' / f).read_text(encoding='utf-8')) for k, f in (
    ('lvvo', 'lvvo-detection-protocol-261026.json'), ('coco', 'coco-subset-261026.json'))}
GT = {}
for key, pattern, name in (('D-A', 'lvvo-1k-four-class', 'lvvo_gt_coco.json'), ('D-B', 'coco-val2017-subset10', 'coco_subset_gt.json')):
    GT[key] = json.loads(next((PRIOR / 'dataset_eda' / pattern).glob(f'*/{name}')).read_text(encoding='utf-8'))
assert q.canonical_json_sha256(GT['D-A']) == REG['lvvo']['gt_coco_canonical_sha256']
assert q.canonical_json_sha256(GT['D-B']) == REG['coco']['gt_coco_canonical_sha256']
print('Frozen GT hashes verified.')
ledger = pd.read_csv(next((PRIOR / 'dataset_eda' / 'lvvo-1k-four-class').glob('*/image_ledger.csv'))).set_index('image_id')
LVVO_GROUPS = ledger.group.to_dict()                       # image_id -> source group (bootstrap unit for D-A)
TAX = {'D-B': REG['coco']['taxonomy_map_open_vocab'],
       'D-A': REG['lvvo']['sub_tracks']['zero_shot_open_vocab']['prompts']}
PHRASES = {'D-B': list(TAX['D-B'].keys()),                   # canonical class names, one prompt
           'D-A': [p for ps in TAX['D-A'].values() for p in ps]}
PHRASES_OVD = {'D-A': [ps[0] for ps in TAX['D-A'].values()]}   # one phrase per class for Florence prompted detection
TRACK_N = {t: len(GT[t]['images']) for t in GT}
rng = np.random.default_rng(SEED)
SAMPLE = {t: sorted(int(i) for i in rng.choice([im['id'] for im in GT[t]['images']], N_SMOKE, replace=False)) for t in GT}
def track_ids(track):
    return SAMPLE[track] if MODE == 'smoke' else [im['id'] for im in GT[track]['images']]
print({t: len(track_ids(t)) for t in GT}, '| candidates:', [c.id for c in dr.CANDIDATES])
'''

DATA = r'''
LVVO_FILE_ID = '1oVufdcjhs76uDmEGu63vywKUXy5ZQSVF'
COCO_URL = 'http://images.cocodataset.org/val2017/{}'
IMG = {}


def prepare_lvvo():
    archive = WORK / 'lvvo' / 'LVVO_1k_withCategories.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get('DT_LVVO_ZIP') and not archive.exists():
        shutil.copyfile(os.environ['DT_LVVO_ZIP'], archive)
    if not archive.exists():
        import gdown
        if not gdown.download(id=LVVO_FILE_ID, output=str(archive), quiet=True):
            raise ConnectionError('Không tải được LVVO')
    assert q.sha256_file(archive) == REG['lvvo']['archive_sha256'], 'archive LVVO khác bản đã đóng băng'
    q.safe_extract(archive, WORK / 'lvvo' / 'source')
    root = WORK / 'lvvo' / 'source' / 'LVVO_1k_withCategories' / 'images'
    return {int(i): root / fn for i, fn in ledger.file_name.items()}


def prepare_coco(ids):
    from concurrent.futures import ThreadPoolExecutor
    folder = WORK / 'coco' / 'val2017_subset'
    folder.mkdir(parents=True, exist_ok=True)
    names = {im['id']: im['file_name'] for im in GT['D-B']['images']}
    def fetch(i):
        p = folder / names[i]
        if not p.exists():
            download(COCO_URL.format(names[i]), p)
        return i, p
    with ThreadPoolExecutor(16) as pool:
        return dict(pool.map(fetch, ids))


IMG['D-A'] = prepare_lvvo()
IMG['D-B'] = prepare_coco(track_ids('D-B'))
ITEMS = {t: [(i, IMG[t][i], (im['width'], im['height'])) for im in GT[t]['images'] for i in [im['id']]
             if i in set(track_ids(t))] for t in GT}
print({t: len(v) for t, v in ITEMS.items()}, 'images ready')
'''

FLORENCE = r'''
# Vendored Florence-2-base: code files are embedded (identical to the product checkout); weights/tokenizer come
# from the Hugging Face repo and every file is verified against the product's SHA-256 table.
FLORENCE_OK, FLORENCE_VERIFY = False, {}
try:
    from huggingface_hub import hf_hub_download
    for name in ('model.safetensors', 'config.json', 'preprocessor_config.json', 'tokenizer.json', 'tokenizer_config.json', 'vocab.json'):
        if not (FLORENCE_DIR / name).exists():
            shutil.copyfile(hf_hub_download('microsoft/Florence-2-base', name), FLORENCE_DIR / name)
    FLORENCE_VERIFY = dr.verify_florence_assets(FLORENCE_DIR)
    FLORENCE_OK = all(FLORENCE_VERIFY.values())
except Exception as exc:
    print('Florence assets could not be prepared:', repr(exc))
print('Florence-2 assets verified against the product checkout:', FLORENCE_OK, FLORENCE_VERIFY)
if not FLORENCE_OK:
    print('Florence-2 sẽ bị bỏ qua và ghi là "unavailable". Có thể đặt thư mục florence2_vendor của repo vào', FLORENCE_DIR)
'''

RUN = r'''
def applicable(c, track):
    if track not in c.tracks:
        return False
    if c.adapter == 'florence' and not FLORENCE_OK:
        return False
    return True


def phrases_for(c, track):
    return PHRASES_OVD[track] if c.params.get('task') == '<OPEN_VOCABULARY_DETECTION>' else PHRASES[track]


JOBS = [(c, t) for t in ('D-B', 'D-A') for c in dr.CANDIDATES if applicable(c, t)]
SKIPPED = [(c.id, t, 'no_corresponding_class' if c.vocabulary == 'closed' else ('florence_unavailable' if c.adapter == 'florence' and not FLORENCE_OK else 'track_not_registered'))
           for t in ('D-B', 'D-A') for c in dr.CANDIDATES if not applicable(c, t)]
print('jobs:', [(c.id, t) for c, t in JOBS]); print('not applicable:', SKIPPED)

RUN_INFO = {}
t_all = time.time()
for c, track in JOBS:
    path = OUT / 'preds' / f'{MODE}_{c.id}_{track}.jsonl'
    key = f'{c.id}|{track}'
    ad = dr.build_adapter(c, 'cuda' if GPU else 'cpu', florence_dir=FLORENCE_DIR, phrases=phrases_for(c, track))
    t0 = time.time()
    try:
        ad.load()
        load_s = time.time() - t0
        info = dr.run_track(ad, ITEMS[track], path, progress=lambda n, m, k=key: print(f'  {k}: {n}/{m}', end='\r'))
        info['load_s'] = round(load_s, 1)
    except Exception as exc:
        traceback.print_exc()
        info = dict(error=repr(exc))
    finally:
        ad.close()
    RUN_INFO[key] = info
    print(key, info)
print(f'inference wall time {(time.time() - t_all) / 60:.1f} min')
write_json(OUT / 'tables' / f'{MODE}_run_info.json', RUN_INFO)
'''

SCORE = r'''
RESULTS = {}
for c, track in JOBS:
    key = f'{c.id}|{track}'
    path = OUT / 'preds' / f'{MODE}_{c.id}_{track}.jsonl'
    if not path.exists():
        continue
    rows = dr.read_rows(path)
    sc = dr.score_track(GT[track], rows, c.vocabulary, TAX[track], image_ids=track_ids(track), score_less=c.score_less)
    sc['peak_vram_mb'] = RUN_INFO.get(key, {}).get('peak_vram_mb')
    sc['candidate'], sc['track'], sc['vocabulary'] = c.id, track, c.vocabulary
    RESULTS[key] = sc


def table(track, vocabulary):
    rows = []
    for key, r in RESULTS.items():
        if r['track'] != track or r['vocabulary'] != vocabulary:
            continue
        s = r['scored']
        rows.append(dict(candidate=r['candidate'], mAP=s['ap_50_95'], AP50=s['ap50'], AP75=s['ap75'], AP_s=s['ap_small'], AP_m=s['ap_medium'],
                         AP_l=s['ap_large'], AR100=s['ar_100'], failed=r['n_failed'] + r['n_not_attempted'], n_img=r['n_images'],
                         boxes=r['n_predictions'], map_cov=r['mapping']['coverage'] if vocabulary == 'open' else np.nan,
                         score_less=r['score_less'], P_at_025=r['diagnostic_at_conf']['precision'], R_at_025=r['diagnostic_at_conf']['recall'],
                         lat_med_ms=r['latency'].get('median_ms'), lat_p95_ms=r['latency'].get('p95_ms'), vram_mb=r['peak_vram_mb']))
    return pd.DataFrame(rows).set_index('candidate') if rows else pd.DataFrame()


for track in ('D-B', 'D-A'):
    for vocab in ('closed', 'open'):
        t = table(track, vocab)
        if len(t):
            print(f'\n=== {track} / {vocab} {"(SMOKE, không công bố)" if MODE == "smoke" else ""} ===')
            display(t.round(4))
            t.to_csv(OUT / 'tables' / f'{MODE}_{track}_{vocab}.csv')
if SKIPPED:
    print('\nKhông áp dụng:', SKIPPED)
write_json(OUT / 'tables' / f'{MODE}_results.json', RESULTS)
'''

VIZ = r'''
# ---- 1. mAP / AP50 by track (closed and open kept in separate panels) ----
fig, axes = plt.subplots(1, 4, figsize=(20, 4), squeeze=False)
for a, (track, vocab) in zip(axes[0], [('D-B', 'closed'), ('D-B', 'open'), ('D-A', 'open'), ('D-A', 'closed')]):
    t = table(track, vocab)
    if len(t) == 0:
        a.set_title(f'{track} {vocab}: không áp dụng'); a.axis('off'); continue
    x = np.arange(len(t)); w = .38
    a.bar(x - w / 2, t.mAP, w, label='mAP@[.5:.95]'); a.bar(x + w / 2, t.AP50, w, label='AP50')
    for i, sl in enumerate(t.score_less):
        if sl:
            a.text(i, max(t.AP50.iloc[i], t.mAP.iloc[i]) + .01, 'score-less', ha='center', fontsize=7, color='#b00')
    a.set_xticks(x, t.index, rotation=25, ha='right', fontsize=8); a.set_ylim(0, 1); a.set_title(f'{track} / {vocab}'); a.legend(fontsize=7)
fig.suptitle(BANNER if MODE == 'smoke' else 'Headline AP (no composite rank across tracks)')
savefig(fig, 'headline_ap.png')

# ---- 2. per-class AP heatmaps ----
for track in ('D-B', 'D-A'):
    keys = [k for k, r in RESULTS.items() if r['track'] == track]
    if not keys:
        continue
    classes = [c['name'] for c in GT[track]['categories']]
    mat = pd.DataFrame({RESULTS[k]['candidate']: pd.Series(RESULTS[k]['per_class_ap']) for k in keys}).reindex(classes)
    fig, ax = plt.subplots(figsize=(1.2 * len(keys) + 4, 0.5 * len(classes) + 2))
    im = ax.imshow(mat.values.astype(float), vmin=0, vmax=1, cmap='viridis', aspect='auto')
    ax.set_xticks(range(mat.shape[1]), mat.columns, rotation=30, ha='right'); ax.set_yticks(range(mat.shape[0]), mat.index); ax.grid(False)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            ax.text(j, i, '-' if pd.isna(v) else f'{v:.2f}', ha='center', va='center', color='w', fontsize=8)
    ax.set_title(f'{track}: per-class AP@[.5:.95]' + (' (SMOKE)' if MODE == 'smoke' else '')); fig.colorbar(im)
    savefig(fig, f'per_class_ap_{track}.png')

# ---- 3. accuracy vs latency (marker size = peak VRAM) ----
rows = [(r['candidate'], r['track'], r['scored']['ap_50_95'], r['latency'].get('median_ms'), r['peak_vram_mb'] or 100, r['score_less']) for r in RESULTS.values()]
if rows:
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
    for a, track in zip(ax, ('D-B', 'D-A')):
        for name, tr, m, lat, vram, sl in rows:
            if tr == track and lat:
                a.scatter(lat, m, s=max(vram, 30) / 4, alpha=.7, marker='s' if sl else 'o'); a.annotate(name, (lat, m), fontsize=7)
        a.set_xscale('log'); a.set_xlabel('median latency per image (ms), batch 1'); a.set_ylabel('mAP@[.5:.95]'); a.set_title(f'{track} (marker size ~ VRAM, square = score-less)')
    savefig(fig, 'accuracy_vs_latency.png')

# ---- 4. what do open-vocabulary models say? (diagnoses the label map) ----
for key, r in RESULTS.items():
    if r['vocabulary'] != 'open':
        continue
    rows_ = dr.read_rows(OUT / 'preds' / f"{MODE}_{r['candidate']}_{r['track']}.jsonl")
    labels = Counter(norm for row in rows_ if row['ok'] for d in row['dets'] for norm in [ds.normalise_label(d['label'])])
    lookup = {ds.normalise_label(s) for ss in TAX[r['track']].values() for s in ss} | {ds.normalise_label(k) for k in TAX[r['track']]}
    top = pd.DataFrame([dict(label=l, boxes=n, mapped=l in lookup) for l, n in labels.most_common(15)])
    print(f"\n{key}: coverage {r['mapping']['coverage']:.3f}; top predicted labels (mapped = recognised by the frozen label map)")
    display(top)

# ---- 5. GT vs predictions on the same images ----
def draw(im, boxes, color, width=3):
    d = ImageDraw.Draw(im)
    for x, y, w, h in boxes:
        d.rectangle((x, y, x + w, y + h), outline=color, width=width)
    return im

for track in ('D-B', 'D-A'):
    keys = [k for k, r in RESULTS.items() if r['track'] == track]
    if not keys:
        continue
    ids = track_ids(track)[:3]
    fig, axes = plt.subplots(len(ids), len(keys) + 1, figsize=(3.6 * (len(keys) + 1), 3.0 * len(ids)), squeeze=False)
    for r_i, iid in enumerate(ids):
        base = Image.open(IMG[track][iid]).convert('RGB'); base.thumbnail((640, 640)); scale = base.width / GT[track]['images'][[im['id'] for im in GT[track]['images']].index(iid)]['width']
        gt_boxes = [[v * scale for v in a['bbox']] for a in GT[track]['annotations'] if a['image_id'] == iid]
        axes[r_i, 0].imshow(draw(base.copy(), gt_boxes, '#00c853')); axes[r_i, 0].set_title(f'GT ({len(gt_boxes)})', fontsize=8); axes[r_i, 0].axis('off')
        for c_i, k in enumerate(keys, start=1):
            rows_ = {row['image_id']: row for row in dr.read_rows(OUT / 'preds' / f"{MODE}_{RESULTS[k]['candidate']}_{track}.jsonl")}
            dets = [d for d in rows_.get(iid, {}).get('dets', []) if d['score'] >= (0.25 if not RESULTS[k]['score_less'] else 0)]
            axes[r_i, c_i].imshow(draw(base.copy(), [[v * scale for v in d['bbox']] for d in dets], '#ff3b30'))
            axes[r_i, c_i].set_title(f"{RESULTS[k]['candidate']} ({len(dets)} boxes, conf>=0.25)", fontsize=8); axes[r_i, c_i].axis('off')
    fig.suptitle(f'{track}: ground truth (green) vs predictions (red), unfiltered by label'); savefig(fig, f'overlays_{track}.png')
'''

BUDGET = r'''
# Budget gate: extrapolate the measured smoke latency to the full cohorts.
full_n = {'D-B': len(GT['D-B']['images']), 'D-A': len(GT['D-A']['images'])}
med = {k: r['latency']['median_ms'] for k, r in RESULTS.items() if r['latency'].get('median_ms')}
est = dr.estimate_gpu_hours(med, full_n)
est_df = pd.Series(est['per_job_hours']).rename('gpu_hours').to_frame()
display(est_df.round(2))
print(f"Ước tính full run 03a: {est['total_hours']:.2f} GPU-giờ trên {GPU or 'CPU (không đáng tin)'} | trần chung 03a+03b = {GPU_BUDGET_HOURS} GPU-giờ")
if MODE == 'smoke':
    gate = dict(estimated_total_hours=est['total_hours'], per_job=est['per_job_hours'], gpu=GPU, budget=GPU_BUDGET_HOURS,
                over_budget=est['total_hours'] > GPU_BUDGET_HOURS, n_smoke=N_SMOKE, valid=GPU is not None,
                finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(OUT / 'smoke-budget-gate.json', gate)
    if not gate['valid']:
        print('Ước tính KHÔNG hợp lệ: smoke chạy trên CPU. Chạy lại smoke trên GPU (Colab T4) trước khi chạy full.')
    elif gate['over_budget']:
        print('DỪNG: ước tính vượt trần. Báo kết quả này cho người duyệt ngân sách; không tự cắt phạm vi.')
    else:
        print('Trong ngân sách (03b chưa tính). Có thể đặt MODE = "full" và chạy lại từ đầu notebook.')
'''

FULL_GUARD = r'''
if MODE == 'full':
    gate_path = OUT / 'smoke-budget-gate.json'
    if not gate_path.exists():
        raise RuntimeError('Chưa có smoke trong RUN_ID này (smoke-budget-gate.json). Chạy MODE = "smoke" trước.')
    gate = json.loads(gate_path.read_text())
    if not gate.get('valid'):
        raise RuntimeError('Smoke trong RUN_ID này chạy trên CPU nên ước tính ngân sách không hợp lệ: chạy lại smoke trên GPU.')
    if gate['over_budget'] and not ALLOW_OVER_BUDGET:
        raise RuntimeError(f"Smoke ước tính {gate['estimated_total_hours']:.1f} GPU-giờ > {GPU_BUDGET_HOURS}; cần người duyệt đặt ALLOW_OVER_BUDGET = True.")
    print('Budget gate passed:', {k: gate[k] for k in ('estimated_total_hours', 'gpu', 'budget')})
'''

BOOT = r'''
# Paired bootstrap (full run only): same resamples for every system, units = images (D-B) or source groups (D-A).
if MODE == 'full':
    DECISIONS = {}
    for track in ('D-B', 'D-A'):
        for vocab in ('closed', 'open'):
            keys = [k for k, r in RESULTS.items() if r['track'] == track and r['vocabulary'] == vocab]
            if len(keys) < 2:
                continue
            ids = track_ids(track)
            groups = None if track == 'D-B' else [LVVO_GROUPS[i] for i in ids]
            mult = pb.cluster_multiplicities(len(ids), groups, 10000, SEED)
            caches = {}
            for k in keys:
                c = next(c for c in dr.CANDIDATES if c.id == RESULTS[k]['candidate'])
                rows_ = dr.read_rows(OUT / 'preds' / f'full_{c.id}_{track}.jsonl')
                name_to_id = {x['name']: x['id'] for x in GT[track]['categories']}
                raw = [dict(image_id=r['image_id'], label=d['label'], bbox=d['bbox'], score=d['score']) for r in rows_ if r['ok'] for d in r['dets']]
                mapped = (ds.map_open_vocab(raw, TAX[track], name_to_id)['preds'] if vocab == 'open' else
                          [dict(image_id=p['image_id'], category_id=name_to_id[p['label']], bbox=p['bbox'], score=p['score']) for p in raw if p['label'] in name_to_id])
                failed = {r['image_id'] for r in rows_ if not r['ok']}
                caches[k] = ds.DetectionCache(GT[track], [p for p in mapped if p['image_id'] not in failed], ids)
            series = {}
            for k in keys:                                  # each system is resampled once and reused in every pair
                t0 = time.time()
                series[k] = pb.metric_series(caches[k].map_fn(), mult)
                print(f'  {track}/{vocab} {RESULTS[k]["candidate"]}: {len(mult)} resamples in {time.time() - t0:.0f}s', flush=True)
            out = []
            for a_i in range(len(keys)):
                for b_i in range(a_i + 1, len(keys)):
                    ka, kb = keys[a_i], keys[b_i]
                    res = pb.paired_from_series(series[ka], series[kb])
                    verdict = pb.decide_difference(res, 0.02)
                    out.append(dict(a=RESULTS[ka]['candidate'], b=RESULTS[kb]['candidate'], mAP_a=res['a'], mAP_b=res['b'], delta=res['delta'],
                                    ci_lo=res['delta_lo'], ci_hi=res['delta_hi'], verdict=verdict,
                                    note='score-less baseline: not ranked' if any(RESULTS[k]['score_less'] for k in (ka, kb)) else ''))
            df = pd.DataFrame(out)
            print(f'\n=== paired comparison {track}/{vocab} (unit: {"image" if track == "D-B" else "source group"}, 10,000 resamples, threshold 0.02) ===')
            display(df.round(4)); df.to_csv(OUT / 'tables' / f'full_pairs_{track}_{vocab}.csv', index=False)
            DECISIONS[f'{track}|{vocab}'] = df.to_dict('records')
    write_json(OUT / 'tables' / 'full_decisions.json', DECISIONS)
else:
    print('Paired bootstrap chỉ chạy ở MODE = "full".')
'''

SAVE = r'''
import importlib.metadata as md
def ver(n):
    try:
        return md.version(n)
    except Exception:
        return None
manifest = dict(
    run_id=RUN_ID, mode=MODE, finished_utc=datetime.now(timezone.utc).isoformat(), gpu=GPU, python=platform.python_version(),
    libraries={n: ver(n) for n in ('torch', 'torchvision', 'transformers', 'ultralytics', 'pycocotools', 'numpy', 'timm', 'einops', 'Pillow')},
    defaults=dr.DEFAULTS, candidates=[dict(id=c.id, family=c.family, vocabulary=c.vocabulary, params=c.params, score_less=c.score_less, tracks=c.tracks) for c in dr.CANDIDATES],
    skipped=SKIPPED, florence_assets_verified=FLORENCE_OK, florence_asset_checks=FLORENCE_VERIFY, source_digests=DIGESTS,
    frozen_gt_sha=dict(lvvo=REG['lvvo']['gt_coco_canonical_sha256'], coco=REG['coco']['gt_coco_canonical_sha256']),
    sample_ids=SAMPLE if MODE == 'smoke' else None,
    preds_sha256={p.name: q.sha256_file(p) for p in sorted((OUT / 'preds').glob(f'{MODE}_*.jsonl'))},
    reportable=(MODE == 'full'), note='smoke results validate the pipeline only' if MODE == 'smoke' else 'frozen protocol, all frozen images')
write_json(OUT / f'{MODE}_manifest.json', manifest)
bundle = OUT / f'bundle_{MODE}.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.csv', '.png', '.jsonl'} and not path.name.startswith('bundle_'):
            zf.write(path, path.relative_to(OUT))
print('Bundle:', bundle, f'{bundle.stat().st_size / 1e6:.1f} MB')
'''


def build():
    sources = {m: (ROOT / m).read_text(encoding="utf-8") for m in MODULES}
    vendor = {name: (VENDOR_DIR / name).read_bytes().decode("utf-8") for name in VENDOR_CODE}
    embed = EMBED.replace("{{", "{").replace("}}", "}").replace("{sources!r}", repr(sources)).replace("{vendor!r}", repr(vendor))
    cells = [
        cell("markdown", INTRO), cell("code", SETUP), cell("code", embed), cell("code", HELPERS),
        cell("markdown", "## 1. Cohort đã đóng băng\nGT được kiểm lại bằng hash; smoke dùng mẫu có seed cố định."),
        cell("code", FROZEN),
        cell("markdown", "## 2. Dữ liệu\nLVVO (hash archive cố định) và ảnh COCO của cohort. Smoke chỉ tải ảnh trong mẫu."),
        cell("code", DATA),
        cell("markdown", "## 3. Florence-2\nMã nhúng giống checkout của sản phẩm; mọi tệp được kiểm SHA-256 theo bảng của `florence_runtime.py`."),
        cell("code", FLORENCE),
        cell("markdown", "## 4. Suy luận (resumable, ảnh lỗi được ghi lý do)\n" + "Mỗi ảnh ghi một dòng JSON (dự đoán thô, latency, lý do lỗi). Chạy lại cell để tiếp tục nếu runtime bị ngắt."),
        cell("code", FULL_GUARD), cell("code", RUN),
        cell("markdown", "## 5. Chấm điểm\npycocotools 2.0.11; closed và open, D-A và D-B báo riêng. Ảnh lỗi chấm như không có dự đoán."),
        cell("code", SCORE),
        cell("markdown", "## 6. Trực quan hóa\nAP tổng quát, AP theo lớp, độ chính xác so với latency/VRAM, nhãn mà mô hình open-vocab thực sự trả về, và so sánh GT với dự đoán."),
        cell("code", VIZ),
        cell("markdown", "## 7. Cổng ngân sách\nƯớc tính GPU-giờ của full run từ latency smoke."),
        cell("code", BUDGET),
        cell("markdown", "## 8. So sánh cặp (chỉ full)\nBootstrap theo cụm 10.000 lần; kết luận chỉ khi CI cặp loại trừ 0 và |ΔmAP| ≥ 0.02."),
        cell("code", BOOT),
        cell("markdown", "## 9. Lưu kết quả"),
        cell("code", SAVE),
    ]
    notebook = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python"), colab=dict(provenance=[], gpuType="T4"), accelerator="GPU"))
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
