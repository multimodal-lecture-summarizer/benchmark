"""Build the Colab notebook for benchmark 03b (multi-object tracking on DanceTrack): dry / smoke / full.

Usage (from benchmark/): python experiments/scripts/build_tracking_benchmark_notebook.py
Frozen inputs (embedded, status must be `approved`): mot-dancetrack-261026, stratification-dancetrack-261027,
tracker-search-space-dancetrack-261027. The notebook embeds the code it runs and records its digests.
"""

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ["experiments/scripts/detection_tracking_qualification.py",
           "experiments/scripts/detection_tracking_eda.py",
           "experiments/scripts/detection_scoring.py",
           "experiments/scripts/detection_runner.py",
           "experiments/scripts/paired_bootstrap.py",
           "experiments/scripts/tracking_scoring.py",
           "experiments/scripts/tracking_runner.py",
           "experiments/scripts/yolox_checkpoint_smoke.py"]
REGISTRIES = {"mot": "experiments/registry/datasets/mot-dancetrack-261026.json",
              "strat": "experiments/registry/datasets/stratification-dancetrack-261027.json",
              "space": "experiments/registry/datasets/tracker-search-space-dancetrack-261027.json"}
DET_03A = ROOT / "experiments/registry/results/det-03a-261026-v1/tables/full_results.json"
OUTPUT = ROOT / "experiments/notebooks/03b-multi-object-tracking-benchmark-colab.ipynb"


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.strip("\n").splitlines(True))
    if kind == "code":
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


def pinned_trackeval_commit():
    text = (ROOT / "experiments/scripts/tracking_scoring.py").read_text(encoding="utf-8")
    return re.search(r'PINNED_TRACKEVAL_COMMIT = "([0-9a-f]{40})"', text).group(1)


def source_a_evidence():
    """Detector for source (a), chosen from 03a (COCO) results only: person AP among COCO-train2017-only candidates."""
    results = json.loads(DET_03A.read_text(encoding="utf-8"))
    table = {}
    for key, r in results.items():
        if key.endswith("|D-B"):
            table[r["candidate"]] = dict(person_ap=round(r["per_class_ap"]["person"], 4),
                                         median_ms=r["latency"].get("median_ms"), vocabulary=r["vocabulary"])
    coco_only = {k: v for k, v in table.items() if k in ("yolov8n", "yolo11n", "rtdetr_r18")}
    chosen = max(coco_only, key=lambda k: coco_only[k]["person_ap"])
    return dict(rule="highest person AP on the 03a D-B track among detectors trained on COCO train2017 only "
                     "(frozen registry detection_sources[0]); open-vocabulary models use larger pretraining and are excluded",
                person_ap_D_B=table, chosen=chosen)


INTRO = r'''
# 03b — Multi-object tracking benchmark (DanceTrack, SORT / ByteTrack / OC-SORT / BoT-SORT)

Notebook có 3 chế độ, đổi `MODE` ở cell cấu hình:

| MODE | Dữ liệu | Chạy ở đâu | Dùng để |
|---|---|---|---|
| `dry` | tổng hợp, tạo tại chỗ | CPU, offline | kiểm tra toàn bộ notebook; **không bao giờ công bố** |
| `smoke` | 3 sequence val ngắn nhất + 1 sequence dev ngắn nhất, 3 cấu hình/tracker | Colab GPU | đo FPS, thời gian CMC, ước ngân sách; **không công bố điểm** |
| `full` | 25 val + 8 dev, mặc định + 20 cấu hình ngẫu nhiên/tracker | Colab GPU + CPU | kết quả chính thức (cần smoke hợp lệ trong cùng `RUN_ID`) |

**Hai tầng.** Tầng A sinh detections cố định một lần (GPU) cho hai nguồn: **(a)** RT-DETR-R18vd chỉ train COCO (chọn từ AP lớp `person` của 03a trên COCO, không nhìn DanceTrack), **(b)** checkpoint YOLOX công bố cho DanceTrack, tiền xử lý `imagenet_rgb` đã kiểm bằng smoke (precision 0.864 / recall 0.986 so với GT). Tầng B chạy 4 tracker trên các detections đó (CPU) rồi chấm bằng TrackEval đã ghim.

**Quy tắc đã đóng băng (registry, status = approved).** Tuning chỉ trên 8 sequence dev của train; chọn cấu hình dev-HOTA cao nhất, hòa thì chỉ số nhỏ hơn; cấu hình 0 = mặc định công bố, báo riêng. Val chạy đúng 2 cấu hình/tracker (mặc định, tuned). Bootstrap theo video 10.000 lần, cùng lần lấy mẫu cho mọi hệ thống, kết luận chỉ khi CI cặp loại trừ 0 **và** |ΔHOTA| ≥ 2.0. Không có điểm tổng hợp; hai nguồn detections không bao giờ nằm chung một bảng xếp hạng.

**Giới hạn phải nhớ.** (1) Nguồn (b) mang cờ `DETECTOR_TRAIN_DATA_UNVERIFIED`: registry ghi nó được train trên DanceTrack nhưng chưa xác minh val có nằm trong dữ liệu train hay không, nên không gọi là held-out. (2) BoT-SORT trong thư viện này **không có ReID** (IoU + bù chuyển động camera). (3) Chỉ 3 sequence val có camera di chuyển: kết quả theo camera chỉ mô tả. (4) DanceTrack là video nhảy, không ngoại suy sang video bài giảng. (5) FPS = chỉ thời gian `update` (không gồm detector và decode ảnh).

**Giấy phép.** `trackers` Apache-2.0, `supervision` MIT, RT-DETR-R18vd Apache-2.0. DanceTrack: annotation CC BY 4.0, dữ liệu chỉ cho nghiên cứu phi thương mại; không phát hành lại ảnh. Bundle chỉ chứa JSON/CSV/PNG; track thô ở Drive.
'''

SETUP = r'''
from pathlib import Path
import os, sys, json, hashlib, subprocess, time, shutil, zipfile, re, platform, traceback, pickle
from datetime import datetime, timezone

# ============================ CẤU HÌNH ============================
MODE = 'dry'              # 'dry' (tổng hợp, CPU) | 'smoke' (3 val + 1 dev, không công bố) | 'full'
RUN_ID = 'track-03b-261027-v1'
LICENSE_ACK = False       # smoke/full: đặt True sau khi đọc điều khoản DanceTrack (in ở cell dữ liệu)
GPU_BUDGET_HOURS = 12.0   # tầng A (detections), phần còn lại sau 03a
TIER_B_MAX_HOURS = 10.0   # trần thời gian tường tầng B (CPU)
ALLOW_OVER_BUDGET = False # chỉ đặt True sau khi người duyệt ngân sách đồng ý
# ===================================================================
assert MODE in ('dry', 'smoke', 'full')

IN_COLAB = Path('/content').exists()
if IN_COLAB and MODE != 'dry':
    from google.colab import drive
    drive.mount('/content/drive')
WORK = Path('/content/track03b') if IN_COLAB else Path.cwd() / 'track03b-work'
PERSIST = Path('/content/drive/MyDrive/DetTrack') if (IN_COLAB and MODE != 'dry') else WORK / 'persistent'
OUT = PERSIST / (RUN_ID + ('-dry' if MODE == 'dry' else ''))
for p in (WORK, OUT, OUT / 'figures', OUT / 'tables', OUT / 'dets', OUT / 'runs', OUT / 'scores'):
    p.mkdir(parents=True, exist_ok=True)
if MODE != 'dry' and not LICENSE_ACK:
    print('Đặt LICENSE_ACK = True sau khi đọc điều khoản DanceTrack (xem cell dữ liệu); notebook sẽ dừng ở đó.')
if os.environ.get('DT_SKIP_PIP') != '1':
    pkgs = ['trackers==2.6.1', 'supervision==0.31.2', 'scipy', 'opencv-python-headless', 'requests', 'huggingface_hub']
    if MODE != 'dry':
        pkgs += ['transformers==4.57.6', 'timm', 'safetensors', 'loguru', 'thop', 'tabulate']
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', *pkgs], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps',
                    'https://github.com/JonathonLuiten/TrackEval/archive/{trackeval_commit}.zip'], check=True)
try:
    import torch
    GPU = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
except ImportError:
    torch, GPU = None, None
print('MODE:', MODE, '| GPU:', GPU)
if MODE != 'dry' and GPU is None:
    print('CẢNH BÁO: không có GPU. Tầng A sẽ rất chậm và smoke-budget-gate sẽ KHÔNG hợp lệ (full bị từ chối).')
'''

EMBED = r'''
SOURCES = {sources!r}
REGISTRIES = {registries!r}
for relative, source in SOURCES.items():
    path = WORK / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')
    (path.parent / '__init__.py').touch()
(WORK / 'experiments' / '__init__.py').touch()
for name, text in REGISTRIES.items():
    (WORK / 'registry').mkdir(exist_ok=True)
    (WORK / 'registry' / name).write_text(text, encoding='utf-8')
sys.path.insert(0, str(WORK))
DIGESTS = {{n: hashlib.sha256(s.encode()).hexdigest() for n, s in {{**SOURCES, **{{'registry/' + k: v for k, v in REGISTRIES.items()}}}}.items()}}
binding = OUT / 'source-code-identity.json'
if binding.exists() and json.loads(binding.read_text()) != DIGESTS:
    raise ValueError('Mã nguồn hoặc registry thay đổi: dùng RUN_ID mới')
binding.write_text(json.dumps(DIGESTS, indent=2))

import numpy as np, pandas as pd, matplotlib, requests
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from experiments.scripts import detection_tracking_qualification as q
from experiments.scripts import detection_tracking_eda as eda
from experiments.scripts import detection_runner as dr
from experiments.scripts import paired_bootstrap as pb
from experiments.scripts import tracking_scoring as ts
from experiments.scripts import tracking_runner as tr
from experiments.scripts import yolox_checkpoint_smoke as smoke
plt.rcParams.update({{'figure.dpi': 100, 'axes.grid': True, 'grid.alpha': .25, 'axes.spines.top': False, 'axes.spines.right': False}})
try:
    display
except NameError:
    display = print
SEED = 20261027
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


BANNER = {'dry': '*** DRY: dữ liệu tổng hợp, chỉ kiểm tra notebook, KHÔNG phải kết quả ***',
          'smoke': '*** SMOKE: kiểm tra pipeline và đo chi phí, KHÔNG công bố hay so sánh các điểm này ***',
          'full': 'DanceTrack val: 4 tracker × {mặc định, tuned}, hai nguồn detections báo riêng'}[MODE]
print(BANNER)
'''

FROZEN = r'''
REG = {k: json.loads((WORK / 'registry' / Path(p).name).read_text(encoding='utf-8')) for k, p in REGISTRY_PATHS.items()}
MOT, STRAT, SPACE = REG['mot'], REG['strat'], REG['space']
assert STRAT['status'] == 'approved' and SPACE['status'] == 'approved', 'stratification / search space chưa được duyệt'
assert STRAT['binds_registry_sequence_ids_sha256'] == MOT['sequence_ids_sha256'], 'phân tầng gắn với cohort khác'
SPECS = tr.load_specs(WORK / 'registry' / Path(REGISTRY_PATHS['space']).name)        # refuses an unapproved file
N_RANDOM, SEED_CFG = SPACE['protocol']['n_configs_excluding_default'], SPACE['protocol']['seed']
CONFIGS = {fam: tr.sample_configs(spec, N_RANDOM, SEED_CFG) for fam, spec in SPECS.items()}
CFG_IDX = list(range(N_RANDOM + 1)) if MODE == 'full' else [0, 1, 2]
N_BOOT = 10000 if MODE == 'full' else 200
STRATA = {r['seq']: r for r in STRAT['sequences']}
FULL_LEN = {d['seq']: d['seq_length'] for s in ('train', 'val') for d in MOT['sequences'][s]}
FULL_VAL = [d['seq'] for d in MOT['sequences']['val']]
FULL_DEV = list(STRAT['dev']['sequences'])
print('trackers:', {k: s.cls for k, s in SPECS.items()}, '| configs per tracker:', len(CFG_IDX), '| bootstrap:', N_BOOT)
print('license:', *MOT['license']['lines'], sep='\n  ')
'''

SOURCES_CELL = r'''
SOURCE_A = {source_a!r}
DATASET_SOURCES = {
    'a': dict(label='a: RT-DETR-R18vd (COCO only)', flags=[], detector='rtdetr_r18'),
    'b': dict(label='b: YOLOX published for DanceTrack', flags=['DETECTOR_TRAIN_DATA_UNVERIFIED'], detector='yolox_x_dancetrack'),
}
SRC = ['dry'] if MODE == 'dry' else ['a', 'b']
if MODE == 'dry':
    DATASET_SOURCES['dry'] = dict(label='dry: synthetic detections', flags=['SYNTHETIC'], detector='none')
print('source (a) rule:', SOURCE_A['rule'], '| chosen:', SOURCE_A['chosen'])
display(pd.DataFrame(SOURCE_A['person_ap_D_B']).T)
'''

DATA = r'''
DT_BASE = 'https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/{}.zip'
SEQ = {}       # name -> dict(length, fps, gt (MOT array), frame (callable t -> BGR image), split)


def synthetic_sequence(name, n_ids, length=60, size=(270, 480), seed=0):
    """Linear-motion dancers on a textured background that pans (so camera-motion compensation has something to do)."""
    rng = np.random.default_rng([SEED, seed])
    h, w = size
    base = (rng.random((h, w * 2, 3)) * 255).astype(np.uint8)
    pos = rng.uniform([20, 20], [w - 60, h - 100], size=(n_ids, 2))
    vel = rng.uniform(-3, 3, size=(n_ids, 2))
    hi = np.array([w - 40, h - 80], float)
    rows = []
    for t in range(1, length + 1):
        for i in range(n_ids):
            m = np.mod(pos[i] + vel[i] * t, 2 * hi)
            p = np.where(m > hi, 2 * hi - m, m)            # triangle wave: bounce inside the image
            rows.append((t, i + 1, p[0], p[1], 40, 80, 1, 1, 1))
    frame = lambda t, base=base, w=w: np.ascontiguousarray(np.roll(base, 2 * t, axis=1)[:, :w])
    return dict(length=length, fps=20.0, gt=np.array(rows, float), frame=frame)


def synthetic_detections(gt, length, seed):
    """GT boxes with jitter, 10% misses and one low-score false positive per frame (all synthetic)."""
    rng = np.random.default_rng([SEED, seed, 1])
    out = []
    for r in gt:
        if rng.random() < .1:
            continue
        out.append([r[0], -1, *(r[2:6] + rng.normal(0, 2, 4)), rng.uniform(.5, .95)])
    for t in range(1, length + 1):
        out.append([t, -1, rng.uniform(0, 400), rng.uniform(0, 190), 40, 80, rng.uniform(.15, .4)])
    return np.array(out, float)


def member_index():
    zips = {n: zipfile.ZipFile(eda.HttpRangeFile(DT_BASE.format(n))) for n in ('train1', 'train2', 'val')}
    seqs = {}
    for name, zf in zips.items():
        default = 'val' if name == 'val' else 'train'
        for n in (i.filename for i in zf.infolist() if not i.is_dir()):
            m = q.parse_mot_member(n, default)
            if not m:
                continue
            e = seqs.setdefault(m['seq'], dict(zf=zf, frames={}, gt=None, info=None, split=m['split']))
            if m['kind'] == 'seqinfo.ini':
                e['info'] = n
            elif m['kind'] == 'gt/gt.txt':
                e['gt'] = n
            else:
                e['frames'][int(m['frame'])] = n
    return seqs


def fetch_sequence(name, entry):
    """Copy one sequence from the remote archive to local disk (resumable) and verify the frozen GT checksum."""
    import cv2
    folder = WORK / 'dancetrack' / name
    (folder / 'img1').mkdir(parents=True, exist_ok=True)
    zf = entry['zf']
    gt_bytes = zf.read(entry['gt'])
    frozen = next(d['gt_sha256'] for s in ('train', 'val') for d in MOT['sequences'][s] if d['seq'] == name)
    assert hashlib.sha256(gt_bytes).hexdigest() == frozen, f'{name}: GT khác bản đã đóng băng'
    (folder / 'gt.txt').write_bytes(gt_bytes)
    info = q.parse_seqinfo(zf.read(entry['info']).decode())
    length = int(info['seqLength'])
    assert length == FULL_LEN[name] and len(entry['frames']) == length, f'{name}: số khung khác registry'
    for t in range(1, length + 1):
        p = folder / 'img1' / f'{t:08d}.jpg'
        if not p.exists():
            p.write_bytes(zf.read(entry['frames'][t]))
    gt = np.loadtxt(folder / 'gt.txt', delimiter=',', ndmin=2)
    frame = lambda t, folder=folder: cv2.imread(str(folder / 'img1' / f'{t:08d}.jpg'))
    return dict(length=length, fps=float(info.get('frameRate', 20)), gt=gt, frame=frame, split=entry['split'])


if MODE == 'dry':
    VAL = [f'dry-val-{i}' for i in range(1, 4)]
    DEV = [f'dry-dev-{i}' for i in range(1, 3)]
    for i, name in enumerate(VAL + DEV):
        SEQ[name] = {**synthetic_sequence(name, n_ids=3 + i, seed=i), 'split': 'val' if name in VAL else 'train'}
        STRATA[name] = dict(seq=name, tier_density=['low', 'mid', 'high'][i % 3], tier_id_gaps=['mid', 'high', 'low'][i % 3],
                            tier_speed=['high', 'low', 'mid'][i % 3], camera='moving' if i == 0 else 'static', role='dry')
else:
    if not LICENSE_ACK:
        raise RuntimeError('Đọc điều khoản DanceTrack ở trên rồi đặt LICENSE_ACK = True.')
    if MODE == 'smoke':
        VAL = sorted(FULL_VAL, key=lambda s: FULL_LEN[s])[:3]
        DEV = sorted(FULL_DEV, key=lambda s: FULL_LEN[s])[:1]
    else:
        VAL, DEV = list(FULL_VAL), list(FULL_DEV)
    INDEX = member_index()
    for name in VAL + DEV:
        t0 = time.time()
        SEQ[name] = fetch_sequence(name, INDEX[name])
        print(f'  {name}: {SEQ[name]["length"]} khung, {SEQ[name]["fps"]:.0f} fps ({time.time() - t0:.0f}s)', flush=True)
print('val:', VAL, '| dev:', DEV, '| frames:', sum(SEQ[s]['length'] for s in VAL + DEV))
'''

TIER_A = r'''
def det_paths(source, seq):
    return OUT / 'dets' / source / f'{seq}.txt', OUT / 'dets' / source / f'{seq}.json'


def tier_a_sequence(detect_frame, source, seq):
    """Run `detect_frame(bgr) -> (rows_xywh_conf, seconds)` over a sequence; write MOT dets + a meta file (resumable)."""
    path, meta_path = det_paths(source, seq)
    if path.exists() and meta_path.exists():
        return
    rows, secs = [], 0.0
    for t in range(1, SEQ[seq]['length'] + 1):
        found, dt = detect_frame(SEQ[seq]['frame'](t))
        secs += dt
        rows.append(tr.det_rows(t, found[:, :4], found[:, 4]) if len(found) else np.zeros((0, 7)))
    rows = np.vstack(rows) if rows else np.zeros((0, 7))
    rows = tr.write_mot_dets(path, rows)                 # checksum of the stored values, not of the unrounded input
    write_json(meta_path, dict(source=source, seq=seq, n_frames=SEQ[seq]['length'], n_boxes=int(len(rows)), seconds=secs,
                               seconds_per_frame=secs / SEQ[seq]['length'], dets_sha256=tr.dets_checksum(rows),
                               device='cuda' if GPU else 'cpu', score_floor=tr.DET_SCORE_FLOOR))


def sync():
    if torch is not None and torch.cuda.is_available():
        torch.cuda.synchronize()


def make_detector_a():
    c = next(c for c in dr.CANDIDATES if c.id == SOURCE_A['chosen'])
    adapter = dr.build_adapter(c, 'cuda' if GPU else 'cpu')
    adapter.load()

    def detect(bgr):
        sync(); t0 = time.perf_counter()
        dets = adapter.predict(np.ascontiguousarray(bgr[:, :, ::-1]))
        sync(); dt = time.perf_counter() - t0
        keep = [d for d in dets if d['label'] == 'person' and d['score'] >= tr.DET_SCORE_FLOOR]
        return np.array([[*d['bbox'], d['score']] for d in keep], float).reshape(-1, 5), dt
    return detect, adapter.close


def make_detector_b():
    from huggingface_hub import hf_hub_download
    yolox_dir = WORK / 'YOLOX'
    if not yolox_dir.exists():
        subprocess.run(['git', 'clone', '--depth', '1', '--branch', '0.3.0', 'https://github.com/Megvii-BaseDetection/YOLOX.git',
                        str(yolox_dir)], check=True)
    sys.path.insert(0, str(yolox_dir))
    from yolox.utils import postprocess
    path = hf_hub_download(smoke.REPO, smoke.FILE)
    CHECKPOINT_SHA = smoke.sha256(path)
    assert os.path.getsize(path) == smoke.EXPECTED_BYTES, 'checkpoint khác bản đã kiểm ở smoke'
    ckpt = torch.load(path, map_location='cpu', weights_only=False)
    model, ncls = smoke.build_model(ckpt['model'])
    dev = next(model.parameters()).device
    SOURCE_B_INFO.update(checkpoint_sha256=CHECKPOINT_SHA, bytes=os.path.getsize(path))

    def detect(bgr):
        x, scale = tr.yolox_letterbox(bgr)
        sync(); t0 = time.perf_counter()
        with torch.no_grad():
            out = postprocess(model(torch.from_numpy(x).to(dev)), ncls, tr.DET_SCORE_FLOOR, tr.YOLOX_NMS)[0]
        sync(); dt = time.perf_counter() - t0
        rows = tr.yolox_outputs_to_rows(None if out is None else out.cpu().numpy(), scale, 0)
        return rows[:, 2:7], dt                 # x, y, w, h, conf
    return detect, lambda: None


SOURCE_B_INFO = {}
if MODE == 'dry':
    for seq in VAL + DEV:
        path, meta_path = det_paths('dry', seq)
        if not path.exists():
            rows = synthetic_detections(SEQ[seq]['gt'], SEQ[seq]['length'], seed=100 + (VAL + DEV).index(seq))
            rows = tr.write_mot_dets(path, rows)
            write_json(meta_path, dict(source='dry', seq=seq, n_frames=SEQ[seq]['length'], seconds_per_frame=0.0,
                                       dets_sha256=tr.dets_checksum(rows), device='none'))
else:
    for source, factory in (('a', make_detector_a), ('b', make_detector_b)):
        todo = [s for s in VAL + DEV if not all(p.exists() for p in det_paths(source, s))]
        if not todo:
            continue
        detect, close = factory()
        for seq in todo:
            t0 = time.time()
            tier_a_sequence(detect, source, seq)
            print(f'  tier A {source}/{seq}: {time.time() - t0:.0f}s', flush=True)
        close()
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
DETS = {s: {seq: tr.read_mot_dets(det_paths(s, seq)[0]) for seq in VAL + DEV} for s in SRC}
DET_META = {s: {seq: json.loads(det_paths(s, seq)[1].read_text()) for seq in VAL + DEV} for s in SRC}
for s in SRC:
    for seq in VAL + DEV:
        assert tr.dets_checksum(DETS[s][seq]) == DET_META[s][seq]['dets_sha256'], f'{s}/{seq}: detections đổi sau khi đóng băng'
print({s: {seq: int(len(d)) for seq, d in DETS[s].items()} for s in SRC})
'''


DIAG = r'''
# ---- detection diagnostics: how good are the fixed detections themselves? (IoU 0.5 against GT, by score threshold) ----
THRESHOLDS = (0.1, 0.3, 0.5, 0.7)
DIAG_ROWS = []
SCORE_SPLIT = {s: dict(matched=[], unmatched=[]) for s in SRC}
for source in SRC:
    for seq in VAL + DEV:
        length = SEQ[seq]['length']
        gt = SEQ[seq]['gt']
        gt = gt[gt[:, 6] != 0] if gt.shape[1] > 6 else gt
        gt_f, det_f = ts._split_by_frame(gt, length), tr.dets_by_frame(DETS[source][seq], length)
        acc = {thr: [0, 0, 0] for thr in THRESHOLDS}                 # detections kept, of which matched to GT, GT matched
        for g, d in zip(gt_f, det_f):
            iou = ts.box_iou_xywh(d[:, 2:6], g[:, 2:6])
            best = iou.max(1) if iou.size else np.zeros(len(d))
            if seq in VAL:
                SCORE_SPLIT[source]['matched'] += d[best >= .5, 6].tolist()
                SCORE_SPLIT[source]['unmatched'] += d[best < .5, 6].tolist()
            for thr in THRESHOLDS:
                keep = d[:, 6] >= thr
                acc[thr][0] += int(keep.sum())
                acc[thr][1] += int((best[keep] >= .5).sum())
                acc[thr][2] += int((iou[keep].max(0) >= .5).sum()) if keep.any() and len(g) else 0
        for thr, (n_det, tp_det, tp_gt) in acc.items():
            DIAG_ROWS.append(dict(source=source, seq=seq, split='val' if seq in VAL else 'dev', camera=STRATA[seq]['camera'],
                                  gt_per_frame=len(gt) / length, thr=thr, dets_per_frame=n_det / length,
                                  precision=tp_det / max(n_det, 1), recall=tp_gt / max(len(gt), 1)))
DIAG_DF = pd.DataFrame(DIAG_ROWS)
DIAG_DF.to_csv(OUT / 'tables' / f'{MODE}_det_diagnostics.csv', index=False)
for thr in (0.5,):
    view = DIAG_DF[DIAG_DF.thr == thr].pivot_table(index=['seq', 'split', 'camera', 'gt_per_frame'], columns='source',
                                                   values=['dets_per_frame', 'precision', 'recall'])
    print(f'\nDetections vs GT at score >= {thr} (IoU 0.5), per video:')
    display(view.round(3))
weak = DIAG_DF[(DIAG_DF.thr == 0.5) & (DIAG_DF.recall < 0.5)]
if len(weak):
    print('DETECTOR_WEAK_ON_VIDEO (recall < 0.5 at score >= 0.5):', weak[['source', 'seq', 'recall']].round(3).to_dict('records'))
fig, ax = plt.subplots(1, len(SRC), figsize=(6.5 * len(SRC), 3.8), squeeze=False)
for a, source in zip(ax[0], SRC):
    bins = np.linspace(0.1, 1, 28)
    a.hist(SCORE_SPLIT[source]['unmatched'], bins=bins, alpha=.6, label='no GT at IoU>=0.5', color='#d62728')
    a.hist(SCORE_SPLIT[source]['matched'], bins=bins, alpha=.6, label='matches a GT box', color='#2ca02c')
    a.set_yscale('log'); a.set_xlabel('detection score'); a.set_ylabel('boxes (val videos)'); a.set_title(DATASET_SOURCES[source]['label']); a.legend(fontsize=8)
fig.suptitle('Detection score vs correctness: where do the default tracker thresholds (0.25 - 0.7) cut?')
savefig(fig, 'det_score_calibration.png')
'''

TIER_B = r'''
STORE = OUT / 'runs'
SCORES = OUT / 'scores'


def run_one(source, fam, ci, seq):
    spec, params = SPECS[fam], CONFIGS[fam][ci]

    def go():
        t0 = time.perf_counter()
        tracker = tr.build_tracker(spec, params, SEQ[seq]['fps'])
        res = tr.run_sequence(tracker, DETS[source][seq], SEQ[seq]['length'], frames=SEQ[seq]['frame'], needs_frame=spec.needs_frame)
        res['wall_seconds'] = time.perf_counter() - t0          # update + frame decode + conversion (the cost the budget needs)
        return res
    return tr.run_or_load(STORE / source, fam, ci, seq, params, DETS[source][seq], go)


def scored(source, fam, ci, seq):
    """(score, run meta) for one (source, tracker, config, sequence); the TrackEval result is cached next to the run."""
    run = run_one(source, fam, ci, seq)
    key = (run.get('params_sha256'), run.get('dets_sha256'))
    cache = SCORES / source / fam / f'cfg{ci:02d}' / f'{seq}.pkl'
    if cache.exists():
        blob = pickle.loads(cache.read_bytes())
        if blob['key'] == key:
            return blob['score'], {**run, 'score_seconds': blob.get('score_seconds')}
    t0 = time.perf_counter()
    score = tr.score_run(SEQ[seq]['gt'], run, SEQ[seq]['length'])
    score_seconds = time.perf_counter() - t0
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(dict(key=key, score=score, score_seconds=score_seconds)))
    return score, {**run, 'score_seconds': score_seconds}


def seq_hota(score):
    return ts.summarize(ts.combine([score['result']]))['HOTA']


# ---- tuning on the dev sequences (train split only; val is never touched here) ----
TUNING, CHOSEN = {}, {}
t_b = time.time()
for source in SRC:
    for fam in SPECS:
        means = {}
        for ci in CFG_IDX:
            per_seq = [scored(source, fam, ci, seq)[0] for seq in DEV]
            means[ci] = float(np.mean([seq_hota(s) for s in per_seq])) if all(s['ok'] for s in per_seq) else float('nan')
            print(f'  tune {source}/{fam} cfg{ci:02d}: dev HOTA {means[ci]:.2f}', end='\r', flush=True)
        valid = {ci: v for ci, v in means.items() if not np.isnan(v)}
        best = min(valid, key=lambda ci: (-valid[ci], ci)) if valid else None      # ties -> lower index
        TUNING[(source, fam)], CHOSEN[(source, fam)] = means, best
        print(f'{source}/{fam}: dev HOTA default {means[0]:.2f} | best cfg {best} = {means.get(best, float("nan")):.2f}')
write_json(OUT / 'tables' / f'{MODE}_tuning.json', {f'{s}|{f}': dict(dev_hota=v, chosen=CHOSEN[(s, f)], params=CONFIGS[f][CHOSEN[(s, f)]] if CHOSEN[(s, f)] is not None else None)
                                                    for (s, f), v in TUNING.items()})
print(f'tuning wall time {(time.time() - t_b) / 60:.1f} min')
'''

EVAL = r'''
# ---- evaluation on val: published default (cfg 0) and the dev-tuned config, per tracker and detection source ----
SYSTEMS, FPS = {}, {}
for source in SRC:
    for fam in SPECS:
        for variant, ci in (('default', 0), ('tuned', CHOSEN[(source, fam)])):
            if ci is None:
                continue
            pairs = {seq: scored(source, fam, ci, seq) for seq in VAL}
            SYSTEMS[(source, fam, variant)] = dict(ci=ci, scores={seq: p[0] for seq, p in pairs.items()})
            fps = [p[1].get('fps') for p in pairs.values() if p[1].get('fps')]
            FPS[(source, fam, variant)] = float(np.median(fps)) if fps else float('nan')


def summary_table(source):
    rows = []
    for (s, fam, variant), sysd in SYSTEMS.items():
        if s != source:
            continue
        agg = tr.score_config(sysd['scores'])
        base = dict(tracker=fam, variant=variant, cfg=sysd['ci'], fps=FPS[(s, fam, variant)])
        if agg['score'] is None:
            rows.append({**base, 'failed': json.dumps(agg['failed'])})
        else:
            sc = agg['score']
            rows.append({**base, **{k: sc[k] for k in ('HOTA', 'DetA', 'AssA', 'LocA', 'IDF1', 'MOTA', 'IDSW', 'Frag', 'MT', 'ML')}})
    return pd.DataFrame(rows)


TABLES = {}
for source in SRC:
    t = summary_table(source)
    TABLES[source] = t
    print(f'\n=== {DATASET_SOURCES[source]["label"]} {DATASET_SOURCES[source]["flags"]} {"(" + MODE.upper() + ", không công bố)" if MODE != "full" else ""} ===')
    display(t.round(3))
    t.to_csv(OUT / 'tables' / f'{MODE}_summary_{source}.csv', index=False)
    if len(t) and 'failed' in t and t['failed'].notna().any():
        print('CÓ SEQUENCE LỖI: hệ thống tương ứng không có điểm (không tính là 0).')
'''

BOOT = r'''
# ---- paired video bootstrap: same resamples for every system; each system resampled once and reused ----
MULT = pb.cluster_multiplicities(len(VAL), None, N_BOOT, SEED)
DECISIONS, CI = {}, {}
for source in SRC:
    series = {}
    for key, sysd in SYSTEMS.items():
        if key[0] != source or any(not s['ok'] for s in sysd['scores'].values()):
            continue
        per_seq = [sysd['scores'][seq]['result'] for seq in VAL]
        series[key] = pb.metric_series(ts.metric_on_resample(per_seq, 'HOTA'), MULT)
        CI[key] = (float(np.nanquantile(series[key][1], .025)), float(np.nanquantile(series[key][1], .975)))
    pairs = []
    fams = list(SPECS)
    for variant in ('default', 'tuned'):
        for i in range(len(fams)):
            for j in range(i + 1, len(fams)):
                pairs.append((f'{variant}: {fams[i]} vs {fams[j]}', (source, fams[i], variant), (source, fams[j], variant)))
    for fam in fams:
        pairs.append((f'{fam}: tuned vs default', (source, fam, 'tuned'), (source, fam, 'default')))
    out = []
    for name, ka, kb in pairs:
        if ka not in series or kb not in series or SYSTEMS[ka]['ci'] == SYSTEMS[kb]['ci'] and ka[1] == kb[1]:
            continue
        res = pb.paired_from_series(series[ka], series[kb])
        out.append(dict(comparison=name, HOTA_a=res['a'], HOTA_b=res['b'], delta=res['delta'], ci_lo=res['delta_lo'], ci_hi=res['delta_hi'],
                        verdict=pb.decide_difference(res, tr.PRACTICAL_HOTA_THRESHOLD)))
    df = pd.DataFrame(out)
    DECISIONS[source] = df.to_dict('records')
    print(f'\n=== paired comparison, {DATASET_SOURCES[source]["label"]} (unit: video, {N_BOOT} resamples, threshold {tr.PRACTICAL_HOTA_THRESHOLD} HOTA) ===')
    display(df.round(3))
    df.to_csv(OUT / 'tables' / f'{MODE}_pairs_{source}.csv', index=False)
write_json(OUT / 'tables' / f'{MODE}_decisions.json', DECISIONS)
'''

STRATIFIED = r'''
# ---- descriptive breakdown by the frozen strata (tuned configs, pooled over the val videos in each group) ----
STRAT_ROWS = []
for source in SRC:
    for fam in SPECS:
        sysd = SYSTEMS.get((source, fam, 'tuned'))
        if sysd is None or any(not s['ok'] for s in sysd['scores'].values()):
            continue
        for axis in ('tier_density', 'tier_id_gaps', 'tier_speed', 'camera'):
            for level in sorted({STRATA[s][axis] for s in VAL}):
                members = [s for s in VAL if STRATA[s][axis] == level]
                sc = ts.score_sequences([sysd['scores'][s]['result'] for s in members])
                STRAT_ROWS.append(dict(source=source, tracker=fam, axis=axis, level=level, n_videos=len(members),
                                       HOTA=sc['HOTA'], DetA=sc['DetA'], AssA=sc['AssA'], IDSW=sc['IDSW'],
                                       note='CAMERA_DESCRIPTIVE_ONLY' if axis == 'camera' else ('n<3: very wide' if len(members) < 3 else '')))
STRAT_DF = pd.DataFrame(STRAT_ROWS)
if len(STRAT_DF):
    display(STRAT_DF[STRAT_DF.source == SRC[0]].round(2))
    STRAT_DF.to_csv(OUT / 'tables' / f'{MODE}_strata.csv', index=False)
print('Mô tả, không kiểm định: mỗi nhóm chỉ vài video.')
'''

VIZ = r'''
COLORS = dict(sort='#1f77b4', bytetrack='#d62728', ocsort='#2ca02c', botsort='#9467bd')
for source in SRC:
    t = TABLES[source]
    if 'HOTA' not in t or t.HOTA.isna().all():
        continue
    # 1. HOTA with video-bootstrap CI, default vs tuned
    fig, ax = plt.subplots(1, 3, figsize=(18, 4.6))
    fams = list(SPECS)
    x = np.arange(len(fams)); w = .38
    for k, variant in enumerate(('default', 'tuned')):
        vals = [t[(t.tracker == f) & (t.variant == variant)].HOTA.iloc[0] if len(t[(t.tracker == f) & (t.variant == variant)]) else np.nan for f in fams]
        err = np.array([[v - CI[(source, f, variant)][0], CI[(source, f, variant)][1] - v] if (source, f, variant) in CI and not np.isnan(v) else [0, 0]
                        for f, v in zip(fams, vals)]).T
        ax[0].bar(x + (k - .5) * w, vals, w, yerr=err, capsize=3, label=variant, alpha=.85)
    ax[0].set_xticks(x, fams); ax[0].set_ylabel('HOTA'); ax[0].legend(); ax[0].set_title('HOTA ± 95% video-bootstrap CI (CI of the pooled score, not of differences)')
    # 2. AssA vs DetA
    for _, r in t.dropna(subset=['HOTA']).iterrows():
        ax[1].scatter(r.DetA, r.AssA, color=COLORS[r.tracker], marker='o' if r.variant == 'tuned' else 's', s=70)
        ax[1].annotate(f'{r.tracker}/{r.variant[:3]}', (r.DetA, r.AssA), fontsize=7)
    ax[1].set_xlabel('DetA'); ax[1].set_ylabel('AssA'); ax[1].set_title('Detection vs association quality (square = default)')
    # 3. FPS vs HOTA
    for _, r in t.dropna(subset=['HOTA']).iterrows():
        ax[2].scatter(r.fps, r.HOTA, color=COLORS[r.tracker], marker='o' if r.variant == 'tuned' else 's', s=70)
        ax[2].annotate(f'{r.tracker}/{r.variant[:3]}', (r.fps, r.HOTA), fontsize=7)
    ax[2].set_xscale('log'); ax[2].set_xlabel('tracker-only FPS (update() only)'); ax[2].set_ylabel('HOTA'); ax[2].set_title('Accuracy vs tracker speed')
    fig.suptitle(f'{DATASET_SOURCES[source]["label"]}  {DATASET_SOURCES[source]["flags"]}  {BANNER if MODE != "full" else ""}')
    savefig(fig, f'headline_{source}.png')
    # 4. per-video HOTA heatmap (tuned)
    mat = pd.DataFrame({f: {s: seq_hota(SYSTEMS[(source, f, 'tuned')]['scores'][s]) if SYSTEMS[(source, f, 'tuned')]['scores'][s]['ok'] else np.nan for s in VAL}
                        for f in fams if (source, f, 'tuned') in SYSTEMS})
    fig, ax = plt.subplots(figsize=(1.1 * len(mat.columns) + 4, 0.38 * len(mat) + 2))
    im = ax.imshow(mat.values, aspect='auto', cmap='viridis')
    ax.set_xticks(range(mat.shape[1]), mat.columns); ax.set_yticks(range(mat.shape[0]), [s + (' *' if STRATA[s]['camera'] == 'moving' else '') for s in mat.index]); ax.grid(False)
    fig.colorbar(im); ax.set_title('HOTA per val video, tuned config (* = moving camera proxy)')
    savefig(fig, f'heatmap_{source}.png')
'''

CMC = r'''
# ---- BoT-SORT: how much of its update time is camera-motion compensation? (one val video, first 200 frames) ----
seq = VAL[0]
n = min(200, SEQ[seq]['length'])
sub = DETS[SRC[0]][seq]
sub = sub[sub[:, 0] <= n]
cmc = {}
for label, over in (('cmc_on', {}), ('cmc_off', {'enable_cmc': False})):
    params = {**CONFIGS['botsort'][0], **over}
    res = tr.run_sequence(tr.build_tracker(SPECS['botsort'], params, SEQ[seq]['fps']), sub, n, frames=SEQ[seq]['frame'], needs_frame=True)
    cmc[label] = res['median_update_ms']
cmc['cmc_ms_per_frame'] = cmc['cmc_on'] - cmc['cmc_off']
print('BoT-SORT median update ms:', cmc)
'''

BUDGET = r'''
# ---- budget gate: extrapolate measured costs to the full cohorts ----
smoke_update_ms, smoke_ms = {}, {}
for fam in SPECS:
    runs = [scored(source, fam, 0, seq)[1] for source in SRC for seq in VAL]
    smoke_update_ms[fam] = float(np.median([r['median_update_ms'] for r in runs if r.get('median_update_ms')] or [np.nan]))
    # cost per frame of one (config, sequence) job: tracker update + frame decode + TrackEval scoring
    per_frame = [(r['wall_seconds'] + r['score_seconds']) / r['n_frames'] * 1000 for r in runs
                 if r.get('wall_seconds') is not None and r.get('score_seconds') is not None]
    smoke_ms[fam] = float(np.median(per_frame)) if per_frame else float('nan')
dev_frames = sum(FULL_LEN[s] for s in FULL_DEV)
val_frames = sum(FULL_LEN[s] for s in FULL_VAL)
cfgs_full = {f: N_RANDOM + 1 for f in SPECS}
b_dev = tr.estimate_budget(smoke_ms, dev_frames, cfgs_full)
b_val = tr.estimate_budget(smoke_ms, val_frames, {f: 2 for f in SPECS})
tier_b_hours = 2 * (b_dev['total_hours'] + b_val['total_hours'])
spf = {s: float(np.mean([m['seconds_per_frame'] for m in DET_META[s].values()])) for s in SRC}
tier_a_hours = sum(spf[s] * (dev_frames + val_frames) * tr.BUDGET_OVERHEAD / 3600 for s in SRC if s != 'dry')
print(pd.DataFrame(dict(update_ms=smoke_update_ms, job_ms_per_frame=smoke_ms)).round(3))
print(f'Ước tính full: tầng A {tier_a_hours:.2f} GPU-giờ (trần {GPU_BUDGET_HOURS}) | tầng B {tier_b_hours:.2f} giờ CPU (trần {TIER_B_MAX_HOURS})')
gate = dict(tier_a_gpu_hours=tier_a_hours, tier_b_cpu_hours=tier_b_hours, update_ms=smoke_update_ms, job_ms_per_frame=smoke_ms, seconds_per_frame_tier_a=spf, bot_sort_cmc=cmc,
            gpu=GPU, tier_a_on_gpu=(GPU is not None and MODE != 'dry'), mode=MODE,
            over_budget=bool(tier_a_hours > GPU_BUDGET_HOURS or tier_b_hours > TIER_B_MAX_HOURS),
            valid=bool(MODE == 'smoke' and GPU is not None), finished_utc=datetime.now(timezone.utc).isoformat())
if MODE in ('dry', 'smoke'):
    write_json(OUT / ('smoke-budget-gate.json' if MODE == 'smoke' else 'dry-budget-gate.json'), gate)
    if MODE == 'dry':
        print('Gate của dry không bao giờ hợp lệ cho full.')
    elif GPU is None:
        print('Ước tính KHÔNG hợp lệ: smoke chạy không có GPU. Chạy lại smoke trên Colab GPU trước khi chạy full.')
    elif gate['over_budget']:
        print('DỪNG: ước tính vượt trần. Báo kết quả này cho người duyệt ngân sách; không tự cắt phạm vi.')
    else:
        print('Trong ngân sách. Có thể đặt MODE = "full" và chạy lại từ đầu notebook.')
'''

FULL_GUARD = r'''
if MODE == 'full':
    gate_path = OUT / 'smoke-budget-gate.json'
    if not gate_path.exists():
        raise RuntimeError('Chưa có smoke trong RUN_ID này (smoke-budget-gate.json). Chạy MODE = "smoke" trước, cùng RUN_ID.')
    _gate = json.loads(gate_path.read_text())
    if not _gate.get('valid') or not _gate.get('tier_a_on_gpu'):
        raise RuntimeError('Smoke trong RUN_ID này không chạy tầng A trên GPU nên ước tính ngân sách không hợp lệ.')
    if _gate['over_budget'] and not ALLOW_OVER_BUDGET:
        raise RuntimeError(f"Smoke ước tính tầng A {_gate['tier_a_gpu_hours']:.1f} GPU-giờ / tầng B {_gate['tier_b_cpu_hours']:.1f} giờ, vượt trần; cần người duyệt đặt ALLOW_OVER_BUDGET = True.")
    print('Budget gate passed:', {k: _gate[k] for k in ('tier_a_gpu_hours', 'tier_b_cpu_hours', 'gpu')})
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
    libraries={n: ver(n) for n in ('trackers', 'supervision', 'numpy', 'scipy', 'opencv-python-headless', 'torch', 'transformers', 'TrackEval')},
    trackeval_commit=ts.PINNED_TRACKEVAL_COMMIT, source_digests=DIGESTS,
    frozen=dict(sequence_ids_sha256=MOT['sequence_ids_sha256'], stratification_status=STRAT['status'], search_space_status=SPACE['status'],
                dev_sequences=DEV, val_sequences=VAL, configs_per_tracker=len(CFG_IDX), seed_configs=SEED_CFG),
    detection_sources={s: dict(**DATASET_SOURCES[s], meta={q_: v for q_, v in DET_META[s].items()}) for s in SRC},
    source_a_choice=SOURCE_A, source_b_info=SOURCE_B_INFO,
    chosen_configs={f'{s}|{f}': dict(cfg=c, params=CONFIGS[f][c] if c is not None else None) for (s, f), c in CHOSEN.items()},
    botsort_cmc=cmc, decisions=DECISIONS,
    sequence_frame_rates={s_: SEQ[s_]['fps'] for s_ in VAL + DEV},     # frame_rate actually passed to every tracker (the config files show the library default 30)
    detection_diagnostics=f'tables/{MODE}_det_diagnostics.csv',
    weak_detector_videos=weak[['source', 'seq', 'recall']].round(4).to_dict('records'),     # recall < 0.5 at score >= 0.5: tracker gaps there are detection-limited
    reportable=(MODE == 'full'),
    note={'dry': 'synthetic data: validates the notebook only', 'smoke': 'smoke results validate the pipeline and costs only',
          'full': 'frozen protocol; source (b) results carry DETECTOR_TRAIN_DATA_UNVERIFIED'}[MODE])
write_json(OUT / f'{MODE}_manifest.json', manifest)
bundle = OUT / f'bundle_{MODE}.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.suffix in {'.json', '.csv', '.png'} and not path.name.startswith('bundle_') and 'runs' not in path.parts and 'scores' not in path.parts and 'dets' not in path.parts:
            zf.write(path, path.relative_to(OUT))
print('Bundle:', bundle, f'{bundle.stat().st_size / 1e6:.2f} MB (chỉ JSON/CSV/PNG; track thô và detections ở', OUT, ')')
'''


def build():
    sources = {m: (ROOT / m).read_text(encoding="utf-8") for m in MODULES}
    registries = {Path(p).name: (ROOT / p).read_text(encoding="utf-8") for p in REGISTRIES.values()}
    embed = (EMBED.replace("{{", "{").replace("}}", "}").replace("{sources!r}", repr(sources))
             .replace("{registries!r}", repr(registries)))
    paths = "REGISTRY_PATHS = " + repr(REGISTRIES) + "\n"
    setup = SETUP.replace("{trackeval_commit}", pinned_trackeval_commit())
    sources_cell = SOURCES_CELL.replace("{source_a!r}", repr(source_a_evidence()))
    cells = [
        cell("markdown", INTRO), cell("code", setup), cell("code", embed), cell("code", HELPERS + "\n" + paths),
        cell("markdown", "## 1. Đầu vào đã đóng băng\nPhân tầng, tập dev và không gian tham số phải ở trạng thái `approved`; cấu hình lấy mẫu có seed, cấu hình 0 là mặc định công bố."),
        cell("code", FROZEN), cell("code", FULL_GUARD),
        cell("markdown", "## 2. Nguồn detections\nNguồn (a) được chọn từ 03a bằng quy tắc ghi sẵn; nguồn (b) mang cờ chưa xác minh dữ liệu train."),
        cell("code", sources_cell),
        cell("markdown", "## 3. Dữ liệu\n`dry`: tổng hợp. `smoke`/`full`: DanceTrack qua HTTP range, kiểm SHA-256 GT theo registry; ảnh chỉ để chạy detector và BoT-SORT, không đưa vào bundle."),
        cell("code", DATA),
        cell("markdown", "## 4. Tầng A — detections cố định\nMỗi (nguồn, sequence) ghi một tệp MOT det + checksum; chạy lại cell để tiếp tục nếu runtime bị ngắt. Chỉ person, điểm ≥ 0.1."),
        cell("code", TIER_A),
        cell("markdown", "## 4b. Chẩn đoán detections\nChất lượng của chính detections cố định so với GT theo từng video (precision/recall ở IoU 0.5 theo ngưỡng điểm) và nơi các ngưỡng mặc định của tracker cắt phân phối điểm. Cần đọc trước khi giải thích khác biệt giữa các tracker."),
        cell("code", DIAG),
        cell("markdown", "## 5. Tầng B — tuning trên dev\nMỗi (tracker, cấu hình, sequence) lưu track thô và điểm TrackEval (resumable). Chọn cấu hình dev-HOTA trung bình cao nhất; hòa thì chỉ số nhỏ hơn. Val không được đụng tới ở bước này."),
        cell("code", TIER_B),
        cell("markdown", "## 6. Đánh giá trên val\nMặc định và tuned, mỗi nguồn detections một bảng. Sequence lỗi làm hệ thống đó không có điểm (không tính là 0)."),
        cell("code", EVAL),
        cell("markdown", "## 7. So sánh cặp\nBootstrap theo video; kết luận chỉ khi CI cặp loại trừ 0 và |ΔHOTA| ≥ 2.0, ngược lại là *indistinguishable*."),
        cell("code", BOOT),
        cell("markdown", "## 8. Phân tầng (mô tả)\nTheo mật độ, gián đoạn ID, tốc độ và camera (ngưỡng đã đóng băng trên train)."),
        cell("code", STRATIFIED),
        cell("markdown", "## 9. Trực quan hóa"),
        cell("code", VIZ),
        cell("markdown", "## 10. Chi phí và cổng ngân sách\nThời gian CMC của BoT-SORT; ước tính full từ chi phí đo được. `full` từ chối chạy nếu thiếu cổng hợp lệ."),
        cell("code", CMC), cell("code", BUDGET),
        cell("markdown", "## 11. Lưu kết quả"),
        cell("code", SAVE),
    ]
    notebook = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python"), colab=dict(provenance=[], gpuType="T4"), accelerator="GPU"))
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
