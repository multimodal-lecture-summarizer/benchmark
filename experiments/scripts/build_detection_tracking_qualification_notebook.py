"""Build the Colab notebook for detection/tracking dataset qualification (plan phase 2).

Usage (from benchmark/): python experiments/scripts/build_detection_tracking_qualification_notebook.py
The notebook embeds experiments/scripts/detection_tracking_qualification.py so it needs no repo clone.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = "experiments/scripts/detection_tracking_qualification.py"
OUTPUT = ROOT / "experiments/notebooks/detection-tracking-dataset-qualification-colab.ipynb"


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.strip("\n").splitlines(True))
    if kind == "code":
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


INTRO = r'''
# Phase 2 — Dataset qualification cho Detection (03a) và Tracking (03b)

Notebook này thực hiện **toàn bộ phân tích dataset của phase 2** trên Colab: D0/D1 (tải thử, decode, kích thước), EDA, đối chiếu `raw = eligible + excluded + unresolved`, kiểm tra rò rỉ (leakage), đóng băng ID/split/checksum và quyết định keep/repair/restrict/reject. **Không chạy model nào, không chấm điểm.**

| Claim | Dataset | Nguồn | Vai trò |
|---|---|---|---|
| D-A | LVVO 1k four-class (1.000 ảnh) | Google Drive của tác giả, SHA-256 cố định | cohort đánh giá zero-shot |
| D-B | COCO val2017, tập con 10 lớp, ~2.000 ảnh, seed cố định | cocodataset.org | cohort đánh giá |
| T | DanceTrack val (eval) + train (tuning) | Hugging Face `noahcao/dancetrack` hoặc ZIP đặt tay | tracking general video |
| T | SportsMOT val (eval) + train (tuning) | **ZIP tải tay từ Codalab** (cần đăng ký, cấm phân phối lại) | tracking general video |

Quyết định đã đóng băng ở phase 1 (không đổi ở đây): taxonomy D-B 10 lớp, ngưỡng thực tế ΔmAP 0.02 / ΔHOTA 2.0, paired bootstrap 10.000 lần theo ảnh/video (D-A theo nhóm nguồn). MOT17 **không dùng** vì license chưa xác minh (quy tắc của plan).

## Cách chạy
1. Chạy các cell theo thứ tự (CPU là đủ, GPU không cần). Kết quả ghi vào Drive `MyDrive/DetTrack/<RUN_ID>`; đổi `RUN_ID` để chạy lại sạch, giữ nguyên để resume.
2. **SportsMOT:** đăng ký Codalab, tải ZIP, đặt vào `MyDrive/DetTrack/manual-downloads/` (tên chứa `sportsmot`). Nếu không có, SportsMOT được ghi `HOLD`, các phần còn lại vẫn chạy.
3. **License:** cell "License" in nguyên văn trang chính thức. Đọc rồi mới đặt `LICENSE_ACK[...] = True` trong cell cấu hình; mặc định `False` nên dataset đó chỉ được `HOLD`, không `KEEP`. DanceTrack/SportsMOT là non-commercial; SportsMOT cấm phân phối lại: chỉ lưu ID, checksum, metric, không đưa ảnh/video/GT vào repo.
4. Cuối notebook có `bundle.zip` (chỉ JSON/CSV/PNG, không ảnh gốc). Đưa các JSON registry vào `benchmark/experiments/registry/datasets/` và thư mục `dataset_eda/` vào `experiments/outputs/`.

Mọi con số trong notebook được tính khi chạy; chưa có kết quả nào được chạy trước.
'''

SETUP = r'''
from pathlib import Path
import os, sys, json, hashlib, subprocess, time, shutil, zipfile, re, platform, traceback
from datetime import datetime, timezone

IN_COLAB = Path('/content').exists()
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
OFFLINE = os.environ.get('DT_OFFLINE') == '1'   # chỉ dùng khi thử cục bộ

RUN_ID = 'det-track-qualification-261026-v3'   # đổi ID để chạy lại sạch; giữ để resume
WORK = Path('/content/dt-qual') if IN_COLAB else Path.cwd() / 'dt-qual-work'
PERSIST = Path('/content/drive/MyDrive/DetTrack') if IN_COLAB else WORK / 'persistent'
OUT = PERSIST / RUN_ID
MANUAL = PERSIST / 'manual-downloads'            # ZIP tải tay (SportsMOT...)
for p in (WORK, OUT, MANUAL, OUT / 'registry', OUT / 'license', OUT / 'dataset_eda'):
    p.mkdir(parents=True, exist_ok=True)

if not OFFLINE:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'huggingface_hub', 'gdown', 'requests'], check=True)
print('Persistent results:', OUT)
'''

EMBED = r'''
# Mã nguồn đã kiểm thử, nhúng sẵn: không cần clone repo.
SOURCES = {sources!r}
for relative, source in SOURCES.items():
    path = WORK / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')
    (path.parent / '__init__.py').touch()
(WORK / 'experiments' / '__init__.py').touch()
sys.path.insert(0, str(WORK))
SOURCE_DIGESTS = {{name: hashlib.sha256(src.encode()).hexdigest() for name, src in SOURCES.items()}}
binding = OUT / 'source-code-identity.json'
if binding.exists() and json.loads(binding.read_text()) != SOURCE_DIGESTS:
    raise ValueError('Mã nguồn thay đổi: dùng RUN_ID mới')
binding.write_text(json.dumps(SOURCE_DIGESTS, indent=2))

import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from collections import Counter
from experiments.scripts import detection_tracking_qualification as q
'''

CONFIG = r'''
# ----- Đóng băng từ phase 1 (không sửa) -----
SEED = 20261026
N_COCO_IMAGES = 2000          # giả định ngân sách trong research report; chốt tại đây khi freeze
FROZEN = dict(taxonomy_coco={str(k): v for k, v in q.COCO_TAXONOMY.items()},
              practical_thresholds=q.PRACTICAL_THRESHOLDS, bootstrap=q.BOOTSTRAP,
              phase1_report='plans/reports/protocol-decision-261026-1745-detection-tracking-claim-freeze-report.md')

# ----- Việc của bạn: đọc license ở cell kế tiếp rồi đặt True -----
LICENSE_ACK = {'lvvo': True,        # CC BY 4.0 trong LICENSE.txt của tác giả (đã đọc ở phiên trước)
               'coco': False, 'dancetrack': False, 'sportsmot': False}
# Nếu trang chính thức không tải được tự động nhưng bạn đã tự đọc và xác nhận, đặt True (ghi vào receipt là "manual").
LICENSE_VERIFIED_MANUAL = {'coco': False, 'dancetrack': False, 'sportsmot': False, 'lvvo': False}

INCLUDE_TRAIN = True          # tải/quét split train (tuning) của tracking; False = chỉ val
MAX_DT_ZIP_GB = 20            # bỏ qua ZIP HF lớn hơn mức này (an toàn đĩa Colab)

# ----- Ánh xạ nhãn open-vocab -> taxonomy (ĐỀ XUẤT, đóng băng khi bạn chấp nhận) -----
# Chuẩn hóa: lowercase, bỏ mạo từ a/an/the. Nhãn không khớp -> unknown_concept (không tính TP).
TAXONOMY_MAP_COCO = {
    'person': ['person', 'people', 'man', 'woman', 'student', 'teacher', 'human', 'child', 'boy', 'girl'],
    'chair': ['chair'], 'tv': ['tv', 'television', 'monitor', 'computer monitor', 'screen', 'display'],
    'laptop': ['laptop', 'laptop computer', 'notebook computer'], 'mouse': ['computer mouse', 'mouse'],
    'keyboard': ['keyboard', 'computer keyboard'], 'cell phone': ['cell phone', 'mobile phone', 'smartphone', 'phone'],
    'book': ['book', 'textbook'], 'clock': ['clock', 'wall clock'], 'bottle': ['bottle', 'water bottle']}
# Prompt zero-shot cho D-A (4 lớp LVVO). 'diagram' xếp vào illustration (đề xuất).
PROMPTS_LVVO = {'Table': ['table', 'data table'], 'Chart-Graph': ['chart', 'graph', 'plot'],
                'Photographic-image': ['photo', 'photograph', 'picture'],
                'Visual-illustration': ['illustration', 'drawing', 'diagram', 'cartoon']}
'''

LICENSE = r'''
import requests

LICENSE_SOURCES = {
    'lvvo': ('https://raw.githubusercontent.com/dbiswas55/LVVO_dataset/d53418d8846c5c08abf9cfa7380da8a4f16626ce/LICENSE.txt',
             r'Creative Commons|CC BY'),
    'coco': ('https://cocodataset.org/dataset/termsofuse.htm', r'Creative Commons'),  # tab nạp bằng JS từ file này
    'dancetrack': ('https://raw.githubusercontent.com/DanceTrack/DanceTrack/main/README.md', r'non-commercial'),
    'sportsmot': ('https://raw.githubusercontent.com/MCG-NJU/SportsMOT/main/README.md', r'NonCommercial|non-commercial'),
}
LICENSE_EVIDENCE = {}
for key, (url, pattern) in LICENSE_SOURCES.items():
    record = dict(url=url, fetched_utc=datetime.now(timezone.utc).isoformat(), ok=False, matched=False, sha256=None, lines=[])
    try:
        if OFFLINE:
            raise ConnectionError('offline test mode')
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        text = r.text
        (OUT / 'license' / f'{key}.txt').write_text(text, encoding='utf-8')
        record.update(ok=True, sha256=hashlib.sha256(r.content).hexdigest(),
                      matched=bool(re.search(pattern, text, re.I)),
                      lines=[ln.strip()[:300] for ln in text.splitlines()
                             if re.search(r'licen|commercial|creative commons|distribut|terms', ln, re.I)][:12])
    except Exception as exc:
        record['error'] = repr(exc)
    record['verified'] = bool(record['matched'] or LICENSE_VERIFIED_MANUAL.get(key))
    record['verified_via'] = 'official_page' if record['matched'] else ('manual' if LICENSE_VERIFIED_MANUAL.get(key) else 'none')
    LICENSE_EVIDENCE[key] = record
    print(f"== {key}: fetched={record['ok']} keyword_found={record['matched']} verified={record['verified']} ack={LICENSE_ACK.get(key)}")
    print('   ', url)
    for ln in record['lines']:
        print('   |', ln)
(OUT / 'license' / 'license-evidence.json').write_text(json.dumps(LICENSE_EVIDENCE, indent=2), encoding='utf-8')
print('\nMOT17: không dùng (license chưa xác minh) -> REJECT theo quy tắc plan.')
'''

HELPERS = r'''
def download(url, dest, retries=3, timeout=60):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if OFFLINE:
        raise ConnectionError('offline test mode')
    last = None
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + '.part')
                with open(tmp, 'wb') as handle:
                    for chunk in r.iter_content(1 << 20):
                        handle.write(chunk)
            tmp.replace(dest)
            return dest
        except Exception as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise ConnectionError(f'{url}: {last!r}')


def eda_dir(dataset_id, revision):
    path = OUT / 'dataset_eda' / dataset_id / revision
    path.mkdir(parents=True, exist_ok=True)
    return path


def savefig(fig, folder, name):
    fig.tight_layout()
    fig.savefig(folder / name, dpi=110)
    plt.show()
    plt.close(fig)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding='utf-8')


def guarded(fn, *args):
    try:
        return fn(*args)
    except Exception as exc:
        traceback.print_exc()
        return dict(acquired=False, error=repr(exc), blocking_qa=0, exact_leakage=0, sha_set=set())


def now():
    return datetime.now(timezone.utc).isoformat()
'''

LVVO_MD = r'''
## D-A — LVVO four-class (1.000 ảnh)

Tải archive tác giả, **xác minh SHA-256 cố định** `f049217c…`, giải nén an toàn, chuyển sang COCO JSON với ID ổn định (sắp theo tên file), giữ ảnh không box làm negative hợp lệ, ghi box lỗi vào danh sách loại (không bỏ im lặng). EDA: tần suất lớp, box/ảnh, diện tích, tỉ lệ khung, phân bố theo nhóm nguồn (instructor/course/video). Kiểm exact duplicate (SHA-256) và near-duplicate (dHash ≤ 4, chỉ là cờ xem xét). Cohort D-A là hữu hạn; ảnh trong cùng nhóm nguồn **không độc lập** nên bootstrap theo nhóm.
'''

LVVO = r'''
LVVO_FILE_ID = '1oVufdcjhs76uDmEGu63vywKUXy5ZQSVF'
LVVO_SHA256 = 'f049217c51c45d532f394d7082e69da95397dee106fede1d743ff3dee80bf7cf'
LVVO_FOLDER = 'https://drive.google.com/drive/folders/1RJjj71CAQHnRLqcWIYmJbWj_1zGmw2bO'


def run_lvvo():
    archive = WORK / 'lvvo' / 'LVVO_1k_withCategories.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    local = os.environ.get('DT_LVVO_ZIP')           # chỉ để thử cục bộ
    if local and not archive.exists():
        shutil.copyfile(local, archive)
    if not archive.exists():
        if OFFLINE:
            raise ConnectionError('offline test mode')
        import gdown
        if not gdown.download(id=LVVO_FILE_ID, output=str(archive), quiet=False):
            raise ConnectionError('Không tải được LVVO từ Drive của tác giả')
    sha = q.sha256_file(archive)
    if sha != LVVO_SHA256:
        raise ValueError(f'SHA-256 archive khác bản đã đóng băng: {sha}')
    q.safe_extract(archive, WORK / 'lvvo' / 'source')
    root = WORK / 'lvvo' / 'source' / 'LVVO_1k_withCategories'
    res = q.lvvo_to_coco(root)
    coco = res['coco']
    ledger = pd.DataFrame(res['ledger'])
    excluded = pd.DataFrame(res['excluded'])
    folder = eda_dir('lvvo-1k-four-class', LVVO_SHA256[:12])

    # ---- reconcile ----
    img_excl = [e for e in res['excluded'] if e['reason'] == 'missing_pair' or e['reason'].startswith('read_error')]
    box_excl = [e for e in res['excluded'] if e['reason'] == 'invalid_box_or_class']
    rec_images = q.reconcile(res['stems_total'], len(coco['images']), len(img_excl), 0)
    labels_dir = root / 'labels'
    raw_boxes = sum(len(json.loads((labels_dir / f"{s}.json").read_text(encoding='utf-8')).get('objects', []))
                    for s in ledger.stem)
    rec_boxes = q.reconcile(raw_boxes, len(coco['annotations']), len(box_excl), 0)
    print('images:', rec_images, '| boxes:', rec_boxes)

    # ---- EDA ----
    names = res['class_names']
    ann = pd.DataFrame(coco['annotations'])
    ann['class_name'] = ann.category_id.map(names)
    ann = ann.merge(ledger[['image_id', 'width', 'height', 'group']], on='image_id')
    ann['area_frac'] = ann.area / (ann.width * ann.height)
    ann['aspect'] = ann.bbox.map(lambda b: b[2] / b[3])
    ann['stratum'] = ann.area.map(q.size_stratum)
    per_class = ann.groupby('class_name').agg(boxes=('id', 'size'), images=('image_id', 'nunique'),
                                              area_frac_median=('area_frac', 'median'))
    per_class['box_share'] = per_class.boxes / per_class.boxes.sum()
    strata = ann.pivot_table(index='class_name', columns='stratum', values='id', aggfunc='size', fill_value=0)
    display(per_class)
    display(strata)
    print('negative images (0 box):', int((ledger.n_boxes == 0).sum()))
    print('boxes/image:', ledger.n_boxes.describe().round(2).to_dict())
    print('image sizes:', ledger.groupby(['width', 'height']).size().sort_values(ascending=False).head(5).to_dict())
    groups = ledger.group.value_counts()
    print(f'source groups: {len(groups)} (nhật ký trước: 139) | frames/group median={groups.median()} max={groups.max()}')
    fig, ax = plt.subplots(1, 4, figsize=(18, 3.6))
    per_class.boxes.sort_values().plot.barh(ax=ax[0], title='Boxes per class')
    ledger.n_boxes.plot.hist(bins=range(0, int(ledger.n_boxes.max()) + 2), ax=ax[1], title='Boxes per image')
    ann.area_frac.plot.hist(bins=30, ax=ax[2], title='Box area / image area')
    groups.plot.hist(bins=30, ax=ax[3], title='Images per source group')
    savefig(fig, folder, 'lvvo_eda.png')

    # ---- duplicates ----
    dup = ledger[ledger.sha256.duplicated(keep=False)]
    hashes = {r.stem: q.dhash64(root / 'images' / r.file_name) for r in ledger.itertuples()}
    pairs = pd.DataFrame(q.near_duplicate_pairs(hashes, dict(zip(ledger.stem, ledger.group)),
                                                dict(zip(ledger.stem, ledger.sha256))))
    dup_groups = int(dup.sha256.nunique())
    print(f'exact duplicate groups: {dup_groups} | near-dup pairs (dHash<=4): {len(pairs)}'
          f' | cross-group: {int((~pairs.same_group).sum()) if len(pairs) else 0}')

    # ---- freeze ----
    gt = dict(images=coco['images'], annotations=coco['annotations'],
              categories=coco['categories'])
    write_json(folder / 'lvvo_gt_coco.json', gt)
    ledger.to_csv(folder / 'image_ledger.csv', index=False)
    excluded.to_csv(folder / 'excluded_ledger.csv', index=False)
    pairs.to_csv(folder / 'near_duplicate_pairs_dhash4.csv', index=False)
    gt_sha = q.canonical_json_sha256(gt)
    registry = dict(
        dataset='lvvo-1k-four-class', claim='D-A', frozen_at=now(), source_repo='https://github.com/dbiswas55/LVVO_dataset',
        source_folder=LVVO_FOLDER, archive_sha256=sha, archive_bytes=archive.stat().st_size,
        author_repo_revision='d53418d8846c5c08abf9cfa7380da8a4f16626ce', license='CC BY 4.0 (author LICENSE.txt, pinned commit)',
        categories=coco['categories'], image_ids=[i['id'] for i in coco['images']],
        image_id_rule='1-based index over sorted file stems', gt_coco_canonical_sha256=gt_sha,
        counts=dict(images=rec_images, boxes=rec_boxes, negative_images=int((ledger.n_boxes == 0).sum()),
                    source_groups=int(len(groups)), exact_duplicate_groups=dup_groups,
                    near_duplicate_pairs=int(len(pairs))),
        sub_tracks=dict(zero_shot_open_vocab=dict(prompts=PROMPTS_LVVO),
                        closed_coco_models='no_corresponding_class (not ranked)',
                        fine_tuned_held_out='out of scope unless a separate claim is approved'),
        bootstrap=dict(unit='source group (instructor/course/video)', **q.BOOTSTRAP),
        practical_threshold=q.PRACTICAL_THRESHOLDS['delta_map_50_95'],
        scope_limits=['all labels were inspected in earlier EDA: no unseen-reference claim',
                      'near-duplicate and cross-group similarity unresolved: CI must reflect dependence',
                      'source video rights/alignment not verified: image-only scoring'],
        scorer_pin_pending='pycocotools version pinned in phase 3')
    write_json(OUT / 'registry' / 'lvvo-detection-protocol-261026.json', registry)
    return dict(acquired=True, blocking_qa=len(box_excl) + len(img_excl), exact_leakage=dup_groups,
                sha_set=set(ledger.sha256), registry='lvvo-detection-protocol-261026.json',
                summary=dict(images=len(coco['images']), boxes=len(coco['annotations']), groups=int(len(groups))))


LVVO_RESULT = guarded(run_lvvo)
print({k: v for k, v in LVVO_RESULT.items() if k != 'sha_set'})
'''

COCO_MD = r'''
## D-B — COCO val2017, tập con 10 lớp

Tải `annotations_trainval2017.zip` (~241 MB), chỉ lấy `instances_val2017.json`. Chọn tập con có **seed**, mỗi lớp có hạn ngạch ảnh, cân bằng small/medium/large (định nghĩa diện tích COCO), rồi bù ngẫu nhiên cho đủ `N_COCO_IMAGES`. Chỉ tải đúng các ảnh được chọn, decode từng ảnh, so kích thước với annotation, lưu SHA-256. Box thuộc lớp ngoài taxonomy trong các ảnh đã chọn bị bỏ khỏi GT và được đếm (detector sẽ bị lọc về 10 lớp khi chấm). Box `iscrowd` được giữ để pycocotools xử lý. COCO val2017 là held-out với detector COCO-pretrained (chỉ thấy train2017).
'''

COCO = r'''
COCO_ANN_URL = 'http://images.cocodataset.org/annotations/annotations_trainval2017.zip'
COCO_IMG_URL = 'http://images.cocodataset.org/val2017/{}'


def fetch_coco_image(item, folder):
    dest = folder / item['file_name']
    try:
        if dest.exists():
            try:
                with Image.open(dest) as im:
                    im.load()
            except Exception:
                dest.unlink()
        if not dest.exists():
            download(COCO_IMG_URL.format(item['file_name']), dest)
        with Image.open(dest) as im:
            im.load()
            size = im.size
        return dict(id=item['id'], ok=True, sha256=q.sha256_file(dest), size_match=size == (item['width'], item['height']))
    except Exception as exc:
        return dict(id=item['id'], ok=False, reason=repr(exc)[:200])


def run_coco():
    from concurrent.futures import ThreadPoolExecutor
    ann_zip = WORK / 'coco' / 'annotations_trainval2017.zip'
    instances = WORK / 'coco' / 'annotations' / 'instances_val2017.json'
    if not instances.exists():
        if not ann_zip.exists():
            download(COCO_ANN_URL, ann_zip)
        q.safe_extract(ann_zip, WORK / 'coco', keep=lambda n: n.endswith('instances_val2017.json'))
    ann_sha = q.sha256_file(ann_zip) if ann_zip.exists() else None
    full = json.loads(instances.read_text(encoding='utf-8'))
    sel = q.select_coco_subset(full, N_COCO_IMAGES, SEED)
    keep = set(sel['image_ids'])
    images = [i for i in full['images'] if i['id'] in keep]
    all_in_subset = [a for a in full['annotations'] if a['image_id'] in keep]
    dropped_other = sum(1 for a in all_in_subset if a['category_id'] not in q.COCO_TAXONOMY)
    licenses = {l['id']: l['name'] for l in full.get('licenses', [])}
    print(f"eligible images={sel['eligible_images']} selected={len(images)} quota/class={sel['quota_per_class']} "
          f"| boxes kept={len(sel['annotations'])} other-class boxes dropped={dropped_other}")

    folder_img = WORK / 'coco' / 'val2017_subset'
    folder_img.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda it: fetch_coco_image(it, folder_img), images))
    res = pd.DataFrame(results).set_index('id')
    ok = res[res.ok]
    failed = res[~res.ok]
    size_mismatch = int((~ok.size_match).sum())
    rec = q.reconcile(len(sel['image_ids']), len(ok), len(failed), 0)
    print('images reconcile:', rec, '| size mismatch:', size_mismatch)
    # ảnh lỗi bị loại khỏi GT cuối nhưng vẫn nằm trong ledger lỗi
    good_ids = set(ok.index)
    folder = eda_dir('coco-val2017-subset10', (ann_sha or 'annotations')[:12])

    # ---- EDA ----
    names = q.COCO_TAXONOMY
    ann = pd.DataFrame([a for a in sel['annotations'] if a['image_id'] in good_ids])
    ann['class_name'] = ann.category_id.map(names)
    ann['stratum'] = ann.area.map(q.size_stratum)
    per_class = ann.groupby('class_name').agg(boxes=('id', 'size'), images=('image_id', 'nunique'),
                                              crowd=('iscrowd', 'sum'))
    strata = ann.pivot_table(index='class_name', columns='stratum', values='id', aggfunc='size', fill_value=0)
    display(per_class.join(strata))
    lic = Counter(licenses.get(i['license'], i['license']) for i in images)
    print('image licenses in subset:', dict(lic))
    per_img = ann.groupby('image_id').size()
    print('boxes/image:', per_img.describe().round(2).to_dict())
    fig, ax = plt.subplots(1, 3, figsize=(15, 3.6))
    per_class.boxes.sort_values().plot.barh(ax=ax[0], title='Boxes per class (long tail)')
    strata.plot.bar(stacked=True, ax=ax[1], title='Box size strata per class')
    per_img.plot.hist(bins=30, ax=ax[2], title='Boxes per image')
    savefig(fig, folder, 'coco_subset_eda.png')

    # ---- freeze ----
    subset_images = [dict(id=i['id'], file_name=i['file_name'], width=i['width'], height=i['height'],
                          license=i['license']) for i in images if i['id'] in good_ids]
    gt = dict(images=subset_images, annotations=[a for a in sel['annotations'] if a['image_id'] in good_ids],
              categories=[dict(id=k, name=v) for k, v in q.COCO_TAXONOMY.items()])
    write_json(folder / 'coco_subset_gt.json', gt)
    ledger = pd.DataFrame([dict(image_id=i, **r) for i, r in res.iterrows()])
    ledger.to_csv(folder / 'image_ledger.csv', index=False)
    gt_sha = q.canonical_json_sha256(gt)
    registry = dict(
        dataset='coco-val2017-subset10', claim='D-B', frozen_at=now(), annotations_url=COCO_ANN_URL,
        annotations_zip_sha256=ann_sha, seed=SEED, n_requested=N_COCO_IMAGES, selection=dict(
            rule='per-class image quota, rarest class first, round-robin over small/medium/large, random fill',
            quota_per_class=sel['quota_per_class'], eligible_images=sel['eligible_images']),
        taxonomy={str(k): v for k, v in q.COCO_TAXONOMY.items()}, taxonomy_map_open_vocab=TAXONOMY_MAP_COCO,
        image_ids=sorted(good_ids), gt_coco_canonical_sha256=gt_sha,
        image_sha256={str(i): r.sha256 for i, r in ok.iterrows()},
        counts=dict(images=rec, boxes=len(gt['annotations']), other_class_boxes_dropped=int(dropped_other),
                    size_mismatch=size_mismatch, failed_downloads=int(len(failed))),
        license_note='annotations CC BY 4.0 and per-image Flickr licenses: confirm on cocodataset.org; images not redistributed',
        detector_leakage='COCO-pretrained detectors saw train2017 only; val2017 is held-out',
        bootstrap=dict(unit='image', **q.BOOTSTRAP), practical_threshold=q.PRACTICAL_THRESHOLDS['delta_map_50_95'],
        scope_limits=['general taxonomy, not lecture video', 'open-vocab scores depend on the frozen label map'])
    write_json(OUT / 'registry' / 'coco-subset-261026.json', registry)
    return dict(acquired=len(good_ids) > 0, blocking_qa=int(len(failed)) + size_mismatch, exact_leakage=0,
                sha_set=set(ok.sha256), registry='coco-subset-261026.json',
                summary=dict(images=len(good_ids), boxes=len(gt['annotations'])))


COCO_RESULT = guarded(run_coco)
# kiểm tra rò rỉ chéo: không ảnh nào của COCO trùng byte với LVVO
overlap = q.exact_overlap(LVVO_RESULT.get('sha_set', set()), COCO_RESULT.get('sha_set', set()))
COCO_RESULT['exact_leakage'] = len(overlap)
print({k: v for k, v in COCO_RESULT.items() if k != 'sha_set'}, '| exact overlap with LVVO:', len(overlap))
'''

MOT_MD = r'''
## T — DanceTrack và SportsMOT (val = đánh giá, train = tuning)

Test GT của cả hai bị ẩn nên **eval = val, tuning = train** của cùng dataset. Với mỗi sequence: đọc `seqinfo.ini` và `gt.txt` (định dạng MOT), kiểm tính toàn vẹn (trùng `(frame,id)`, box kích thước ≤ 0, frame ngoài khoảng, ID không dương), thống kê mật độ box/frame, độ dài track, số track có khoảng trống, tỉ lệ box bị che (proxy: IoU > 0.3 với box khác cùng frame), và ước lượng chuyển động camera (phase correlation giữa các cặp frame liên tiếp, proxy mô tả — **không phải nhãn**). Chỉ trích một số frame mẫu (đầu/cuối + các cặp liên tiếp) để decode-check và đo camera, không giải nén toàn bộ video. Kiểm rò rỉ: tên sequence, SHA-256 của `gt.txt` và của frame mẫu giữa train và val phải không trùng.

Detector sinh detections cố định ở phase 4 sẽ có dữ liệu train như sau (ghi vào registry để cảnh báo leakage): COCO-pretrained = chỉ COCO train2017 (không thấy dataset này); detections công bố YOLOX = **đã train trên chính dataset** (báo riêng, không so với nguồn (a)).
'''

MOT = r'''
class ZipSource:
    def __init__(self, path):
        self.path = Path(path)
        self.zf = zipfile.ZipFile(path)
        self.names = [i.filename for i in self.zf.infolist() if not i.is_dir()]
        stem = self.path.name.lower()
        # tên file như train1.zip / val.zip cho biết split khi thư mục trong ZIP không có
        self.default_split = next((s for s in ('train', 'val', 'test') if re.search(rf'(^|[^a-z]){s}', stem)), None)

    def read(self, name):
        return self.zf.read(name)


class HFSource:
    def __init__(self, repo, names):
        self.repo, self.names = repo, names
        self.default_split = None

    def read(self, name):
        from huggingface_hub import hf_hub_download
        return Path(hf_hub_download(self.repo, name, repo_type='dataset')).read_bytes()


def find_manual_archives(key):
    norm = lambda s: s.lower().replace('_', '').replace('-', '').replace(' ', '')
    return sorted(p for p in MANUAL.glob('*.zip') if key in norm(p.name))


def open_sources(key):
    """Trả về (danh sách nguồn, ghi chú). ZIP đặt tay được ưu tiên; DanceTrack tự thử Hugging Face."""
    manual = find_manual_archives(key)
    if manual:
        return [ZipSource(p) for p in manual], f'manual zips: {[p.name for p in manual]}'
    if key == 'dancetrack' and not OFFLINE:
        from huggingface_hub import list_repo_files, hf_hub_download
        files = list_repo_files('noahcao/dancetrack', repo_type='dataset')
        print('HF noahcao/dancetrack: %d files, e.g.' % len(files), files[:25])
        zips = [f for f in files if f.lower().endswith('.zip')]
        if zips:
            wanted = [f for f in zips if re.search('val', f, re.I) or (INCLUDE_TRAIN and re.search('train', f, re.I))]
            print('zip candidates:', wanted)
            local = []
            for f in wanted:
                local.append(Path(hf_hub_download('noahcao/dancetrack', f, repo_type='dataset')))
                size_gb = local[-1].stat().st_size / 1e9
                print(f'  {f}: {size_gb:.2f} GB')
                if size_gb > MAX_DT_ZIP_GB:
                    raise RuntimeError(f'{f} lớn hơn MAX_DT_ZIP_GB={MAX_DT_ZIP_GB}')
            if local:
                return [ZipSource(p) for p in local], f'hf zips: {wanted}'
        meta = [f for f in files if q.parse_mot_member(f)]
        if meta:
            return [HFSource('noahcao/dancetrack', meta)], 'hf files (no zip)'
    return [], 'no source found'


def run_tracking(key):
    sources, note = open_sources(key)
    print(f'[{key}] {note}')
    if not sources:
        raise FileNotFoundError(
            f'Không có dữ liệu {key}. Đặt ZIP vào {MANUAL} (tên chứa "{key}") rồi chạy lại cell này.')
    seqs = {}
    for source in sources:
        matched = 0
        for name in source.names:
            m = q.parse_mot_member(name, source.default_split)
            if not m:
                continue
            matched += 1
            entry = seqs.setdefault((m['split'], m['seq']), dict(source=source, frames={}, gt=None, info=None))
            if m['kind'] == 'seqinfo.ini':
                entry['info'] = name
            elif m['kind'] == 'gt/gt.txt':
                entry['gt'] = name
            else:
                entry['frames'][int(m['frame'])] = name
        label = getattr(source, 'path', None) or getattr(source, 'repo', '')
        print(f'  source {Path(str(label)).name}: {len(source.names)} members, {matched} recognised, '
              f'default_split={source.default_split}')
        if not matched:
            print('  !! không nhận diện được thành viên nào; 15 tên đầu:', source.names[:15])
    splits = Counter(s for s, _ in seqs)
    print('sequences per split:', dict(splits), '| test có GT:',
          sum(1 for (s, _), e in seqs.items() if s == 'test' and e['gt']))
    use = [k for k in sorted(seqs) if k[0] in ('val', 'train') and (INCLUDE_TRAIN or k[0] == 'val')]
    pairs_n = 6 if isinstance(sources[0], ZipSource) else 2
    root = WORK / 'mot' / key
    rows, shas = [], {}
    for split, seq in use:
        e = seqs[(split, seq)]
        if not e['info'] or not e['gt']:
            rows.append(dict(split=split, seq=seq, issue='missing_seqinfo_or_gt', blocking=1))
            continue
        info = q.parse_seqinfo(e['source'].read(e['info']).decode('utf-8', 'replace'))
        length, width, height = int(info['seqLength']), int(info['imWidth']), int(info['imHeight'])
        gt_bytes = e['source'].read(e['gt'])
        stats = q.mot_sequence_stats(q.parse_mot_gt(gt_bytes.decode('utf-8', 'replace')), length, width, height)
        gt_sha = hashlib.sha256(gt_bytes).hexdigest()
        # frame mẫu: giải nén, decode, sha, camera
        import cv2
        picks = [f for f in q.sample_frame_indices(length, pairs_n) if f in e['frames']]
        gray, decode_fail, size_bad, frame_sha = {}, 0, 0, {}
        for f in picks:
            dest = root / split / seq / 'img1' / Path(e['frames'][f]).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                dest.write_bytes(e['source'].read(e['frames'][f]))
            img = cv2.imread(str(dest), cv2.IMREAD_GRAYSCALE)
            if img is None:
                decode_fail += 1
                continue
            if img.shape != (height, width):
                size_bad += 1
            frame_sha[f] = q.sha256_file(dest)
            scale = 480 / img.shape[1]
            gray[f] = cv2.resize(img, (480, max(1, int(img.shape[0] * scale))))
        cam_pairs = [(gray[f], gray[f + 1]) for f in sorted(gray) if f + 1 in gray]
        cam = q.camera_motion_pixels(cam_pairs) if cam_pairs else float('nan')
        shas[(split, seq)] = dict(gt=gt_sha, frames=set(frame_sha.values()))
        frame_mismatch = int(len(e['frames']) != length)
        row = dict(split=split, seq=seq, fps=float(info.get('frameRate', 'nan')), width=width, height=height,
                   frames_listed=len(e['frames']), frame_count_mismatch=frame_mismatch,
                   decode_fail=decode_fail, size_mismatch=size_bad, gt_sha256=gt_sha,
                   camera_shift_px=cam, issue='',
                   blocking=q.mot_blocking_issues(stats) + decode_fail + size_bad + frame_mismatch)
        row.update({k: v for k, v in stats.items() if k != 'issues'})
        row['seq_length'] = length
        rows.append(row)
    df = pd.DataFrame(rows)
    folder = eda_dir(f'{key}-mot', hashlib.sha256(''.join(sorted(df.gt_sha256.dropna())).encode()).hexdigest()[:12])
    df.to_csv(folder / 'sequence_ledger.csv', index=False)
    num = df[df.get('issue', '') == '']
    summary = num.groupby('split').agg(sequences=('seq', 'size'), frames=('seq_length', 'sum'), boxes=('boxes', 'sum'),
                                       tracks=('tracks', 'sum'), boxes_per_frame=('boxes_per_frame_mean', 'mean'),
                                       occluded=('occluded_box_fraction', 'mean'), tracks_with_gaps=('tracks_with_gaps', 'sum'),
                                       cam_shift_median=('camera_shift_px', 'median'), blocking=('blocking', 'sum'))
    display(summary)
    reasons = ['duplicate_frame_id_rows', 'nonpositive_size_rows', 'frame_out_of_range_rows', 'decode_fail',
               'size_mismatch', 'frame_count_mismatch']
    reasons = [c for c in reasons if c in num]
    print('nguồn của lỗi chặn (tổng theo split):')
    display(num.groupby('split')[reasons].sum())
    flagged = num[num.blocking > 0]
    if len(flagged):
        print('sequence có lỗi chặn (tối đa 10):')
        display(flagged[['split', 'seq', 'seq_length', 'frames_listed'] + reasons].head(10))
    display(num.groupby('split')[['width', 'height', 'fps']].agg(lambda s: sorted(set(s.round(1)))[:4]))
    num = num.assign(camera=np.where(num.camera_shift_px > 1.0, 'moving(proxy)', 'static(proxy)'))
    print('camera proxy (>1 px median shift) per split:', num.groupby(['split', 'camera']).size().to_dict())
    val_frames = int(num[num.split == 'val'].seq_length.sum())
    print(f'val: {len(num[num.split == "val"])} sequences, {val_frames} frames' + (
        '  -> vượt 30.000 frame: cân nhắc subset đăng ký trước (ngân sách GPU)' if val_frames > 30000 else ''))
    fig, ax = plt.subplots(1, 4, figsize=(18, 3.6))
    for split, g in num.groupby('split'):
        ax[0].hist(g.boxes_per_frame_mean, alpha=.6, label=split)
        ax[1].hist(g.track_len_median, alpha=.6, label=split)
        ax[2].hist(g.occluded_box_fraction, alpha=.6, label=split)
        ax[3].hist(g.camera_shift_px.dropna(), alpha=.6, label=split)
    for a, t in zip(ax, ('Boxes/frame (mean)', 'Median track length', 'Occluded box fraction', 'Camera shift px')):
        a.set_title(t)
        a.legend()
    savefig(fig, folder, f'{key}_eda.png')

    # ---- leakage train vs val ----
    tr = [k for k in shas if k[0] == 'train']
    va = [k for k in shas if k[0] == 'val']
    name_overlap = q.exact_overlap([s for _, s in tr], [s for _, s in va])
    gt_overlap = q.exact_overlap([shas[k]['gt'] for k in tr], [shas[k]['gt'] for k in va])
    frame_overlap = q.exact_overlap([h for k in tr for h in shas[k]['frames']], [h for k in va for h in shas[k]['frames']])
    leakage = len(name_overlap) + len(gt_overlap) + len(frame_overlap)
    print(f'leakage exact: sequence names={len(name_overlap)} gt={len(gt_overlap)} sampled frames={len(frame_overlap)}')

    registry = dict(
        dataset=key, claim='T', frozen_at=now(), source_note=note, eval_split='val', tuning_split='train',
        license=LICENSE_EVIDENCE[key], license_ack=LICENSE_ACK[key],
        redistribution='forbidden or restricted: store IDs, checksums, metrics only',
        sequences={s: [dict(seq=r.seq, seq_length=int(r.seq_length), gt_sha256=r.gt_sha256, boxes=int(r.boxes),
                            tracks=int(r.tracks), camera_proxy=r.camera) for r in num[num.split == s].itertuples()]
                   for s in ('val', 'train')},
        sequence_ids_sha256=q.canonical_json_sha256(sorted(map(list, shas))),
        counts=summary.reset_index().to_dict('records'),
        leakage=dict(names=len(name_overlap), gt=len(gt_overlap), sampled_frames=len(frame_overlap)),
        detector_train_data=dict(coco_pretrained='COCO train2017 only (no exposure to this dataset)',
                                 published_yolox='trained on this dataset: report separately, not comparable to COCO-pretrained'),
        detection_sources=['frozen COCO-pretrained detector (phase 4)', 'dataset-published YOLOX detections (phase 4)'],
        bootstrap=dict(unit='video', **q.BOOTSTRAP), practical_threshold=q.PRACTICAL_THRESHOLDS['delta_hota'],
        scope_limits=['general video, no extrapolation to lecture video', 'few eval videos: wide CI, descriptive conclusions',
                      'camera static/moving is a phase-correlation proxy'])
    write_json(OUT / 'registry' / f'mot-{key}-261026.json', registry)
    blocking = int(num.blocking.sum()) + int((df.get('issue', '') != '').sum())
    return dict(acquired=bool(len(va)), blocking_qa=blocking, exact_leakage=leakage, sha_set=set(),
                registry=f'mot-{key}-261026.json',
                summary=dict(val_sequences=len(va), train_sequences=len(tr), val_frames=val_frames))


TRACK_RESULTS = {}
for key in ('dancetrack', 'sportsmot'):
    TRACK_RESULTS[key] = guarded(run_tracking, key)
    print(key, {k: v for k, v in TRACK_RESULTS[key].items() if k != 'sha_set'})
'''

DECIDE_MD = r'''
## Quyết định keep / repair / restrict / reject và gói kết quả

`qualification_decision` áp dụng các cổng theo thứ tự: chưa tải được → `HOLD`; license không xác minh được từ nguồn chính thức → `REJECT`; chưa tick `LICENSE_ACK` → `HOLD`; có trùng exact → `REPAIR`; có lỗi QA chặn → `REPAIR`; còn lại `KEEP` cho phạm vi đã khai báo. `KEEP` ở đây chỉ nghĩa là đủ điều kiện để dùng trong protocol đã nêu, không phải kết quả benchmark.
'''

DECIDE = r'''
RESULTS = dict(lvvo=LVVO_RESULT, coco=COCO_RESULT, **TRACK_RESULTS)
decisions = {}
for key, res in RESULTS.items():
    decisions[key] = q.qualification_decision(
        license_verified=LICENSE_EVIDENCE.get(key, {}).get('verified', False),
        license_ack=bool(LICENSE_ACK.get(key)), blocking_qa=int(res.get('blocking_qa', 0)),
        exact_leakage=int(res.get('exact_leakage', 0)), acquired=bool(res.get('acquired')))
decisions['mot17'] = dict(decision='REJECT', reason='license not verified; not used (plan rule)')
table = pd.DataFrame([dict(dataset=k, **v, error=RESULTS.get(k, {}).get('error', '')) for k, v in decisions.items()])
display(table)
if decisions['coco']['decision'] == 'REJECT':
    print('\nCOCO bị loại -> quay lại phase 1 chọn nguồn khác cho Detection B.')

import importlib.metadata as md
def ver(name):
    try:
        return md.version(name)
    except Exception:
        return None

receipt = dict(
    run_id=RUN_ID, finished_utc=now(), python=platform.python_version(), platform=platform.platform(),
    libraries={n: ver(n) for n in ('numpy', 'pandas', 'Pillow', 'opencv-python', 'opencv-python-headless', 'requests',
                                   'huggingface_hub', 'gdown', 'matplotlib')},
    seed=SEED, frozen=FROZEN, license_ack=LICENSE_ACK, license_evidence=LICENSE_EVIDENCE,
    decisions=decisions, results={k: {a: b for a, b in v.items() if a != 'sha_set'} for k, v in RESULTS.items()},
    model_inference_run=False, scoring_run=False,
    note='KEEP = eligible for the scoped protocol only; no benchmark result is implied.')
write_json(OUT / 'phase2-qualification-receipt.json', receipt)

bundle = OUT / 'bundle.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path != bundle and path.suffix in {'.json', '.csv', '.png', '.txt'}:
            zf.write(path, path.relative_to(OUT))
print('Bundle (không chứa ảnh/video gốc):', bundle, f'{bundle.stat().st_size / 1e6:.1f} MB')
print('Registry JSON để đưa vào benchmark/experiments/registry/datasets/:',
      sorted(p.name for p in (OUT / 'registry').glob('*.json')))
'''


def build():
    source = (ROOT / MODULE).read_text(encoding="utf-8")
    cells = [
        cell("markdown", INTRO),
        cell("code", SETUP),
        cell("code", EMBED.replace("{{", "{").replace("}}", "}").replace("{sources!r}", repr({MODULE: source}))),
        cell("code", CONFIG),
        cell("markdown", "## License\n\nIn nguyên văn các dòng liên quan từ trang chính thức. **Đọc trước khi đặt `LICENSE_ACK`.** Trang không tải được hoặc không có từ khóa mong đợi thì dataset không được coi là đã xác minh (COCO bị `REJECT` theo quy tắc plan trừ khi bạn đặt `LICENSE_VERIFIED_MANUAL` sau khi tự đọc trang chính thức)."),
        cell("code", LICENSE),
        cell("code", HELPERS),
        cell("markdown", LVVO_MD),
        cell("code", LVVO),
        cell("markdown", COCO_MD),
        cell("code", COCO),
        cell("markdown", MOT_MD),
        cell("code", MOT),
        cell("markdown", DECIDE_MD),
        cell("code", DECIDE),
    ]
    notebook = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python"), colab=dict(provenance=[])))
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
