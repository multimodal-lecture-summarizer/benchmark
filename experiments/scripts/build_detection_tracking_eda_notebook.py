"""Build the Colab notebook for detailed detection/tracking EDA (plan phase 2, analysis part).

Usage (from benchmark/): python experiments/scripts/build_detection_tracking_eda_notebook.py
Input of the notebook = the frozen artifacts of the qualification run (hash-verified), so every
number is computed on exactly the cohorts that were frozen.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ["experiments/scripts/detection_tracking_qualification.py",
           "experiments/scripts/detection_tracking_eda.py"]
OUTPUT = ROOT / "experiments/notebooks/detection-tracking-eda-colab.ipynb"


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.strip("\n").splitlines(True))
    if kind == "code":
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


INTRO = r'''
# Phase 2 — EDA chi tiết: LVVO (D-A), COCO subset (D-B), DanceTrack (T)

Notebook này phân tích **đúng các cohort đã đóng băng** ở lần chạy `det-track-qualification-261026-v3` (hash GT được kiểm lại trước khi dùng). Không chạy model, không chấm điểm. Mục tiêu: hiểu dữ liệu đủ để thiết kế đánh giá ở phase 3/4 và biết trước các giới hạn thống kê.

**Nguyên tắc khoa học áp dụng**
- Đơn vị phụ thuộc được xử lý đúng: LVVO theo **nhóm nguồn** (và nhóm gộp qua cặp gần trùng), DanceTrack theo **sequence**. Báo *design effect* và *effective n*; khoảng tin cậy dùng bootstrap theo cụm.
- So sánh train/val của DanceTrack là kiểm định ở mức sequence (Mann–Whitney, KS) kèm **Cliff's δ**, hiệu chỉnh **Holm** cho nhiều đặc trưng; KS gộp chỉ để mô tả.
- Ảnh gần trùng (dHash) được đo lại bằng **slide Jaccard** (cắt viền đen, chỉ so vùng slide ở giữa, so mặt nạ nét vẽ). NCC thô và ink-overlap toàn khung bị loại vì các frame cùng bài giảng chia sẻ nền trắng, viền đen và cửa sổ giao diện nên điểm cao dù nội dung khác (đã thấy trên lưới ảnh hiệu chuẩn). Mọi độ đo tự động ở đây chỉ là **cờ sàng lọc**; kết luận trùng lặp cần người duyệt lưới ảnh. Không tự loại ảnh nào.
- Ngưỡng cờ ("ít hỗ trợ", "dịch chuyển phân phối", ...) là quy tắc heuristic được in rõ trong bảng quan sát, không phải kết luận suy diễn.
- Mô tả ≠ suy diễn: mọi so sánh với toàn bộ COCO val2017 là **kiểm tra tính đại diện có chủ đích** (tập con được phân tầng theo lớp/kích thước nên lệch có chủ ý).

**Cách chạy:** chạy tuần tự trên Colab (CPU đủ). Cần thư mục `MyDrive/DetTrack/det-track-qualification-261026-v3/` từ lần chạy trước. DanceTrack được đọc bằng HTTP range (chỉ GT và vài frame mẫu, không tải 11 GB). Kết quả: `MyDrive/DetTrack/<RUN_ID>/` (hình, bảng CSV, `eda-observations.json`, `bundle.zip`).
'''

SETUP = r'''
from pathlib import Path
import os, sys, json, hashlib, subprocess, time, shutil, zipfile, re, platform, traceback
from datetime import datetime, timezone

IN_COLAB = Path('/content').exists()
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
OFFLINE = os.environ.get('DT_OFFLINE') == '1'

RUN_ID = 'det-track-eda-261026-v2'
WORK = Path('/content/dt-eda') if IN_COLAB else Path.cwd() / 'dt-eda-work'
PERSIST = Path('/content/drive/MyDrive/DetTrack') if IN_COLAB else WORK / 'persistent'
PRIOR = Path(os.environ.get('DT_PRIOR', PERSIST / 'det-track-qualification-261026-v3'))
OUT = PERSIST / RUN_ID
for p in (WORK, OUT):
    p.mkdir(parents=True, exist_ok=True)
if not PRIOR.exists():
    raise FileNotFoundError(f'Thiếu {PRIOR}: chạy notebook qualification trước (hoặc đặt PRIOR).')
if not OFFLINE:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'huggingface_hub', 'gdown', 'requests', 'scipy'], check=True)
print('Frozen inputs:', PRIOR, '\nResults:', OUT)
'''

EMBED = r'''
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

import numpy as np, pandas as pd, matplotlib, requests
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from collections import Counter
from scipy import stats as sps
from experiments.scripts import detection_tracking_qualification as q
from experiments.scripts import detection_tracking_eda as eda
plt.rcParams.update({'figure.dpi': 100, 'axes.grid': True, 'grid.alpha': .25, 'axes.spines.top': False, 'axes.spines.right': False})
SEED = 20261026
try:
    display
except NameError:
    display = print
'''

HELPERS = r'''
RESULTS, OBS = {}, []     # OBS: danh sách quan sát định lượng + cờ heuristic


def savefig(fig, folder, name, show=True):
    fig.tight_layout()
    fig.savefig(folder / name, dpi=110)
    plt.close(fig)
    if show:   # backend is Agg (headless-safe), so render the saved PNG inline instead of plt.show()
        try:
            from IPython.display import display as _display, Image as _Image
            _display(_Image(filename=str(folder / name)))
        except Exception:
            print('saved', folder / name)


def save_table(df, folder, name, show=True):
    df.to_csv(folder / name)
    if show:
        display(df)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=float), encoding='utf-8')


def observe(dataset, key, value, flag=None, rule=None):
    OBS.append(dict(dataset=dataset, key=key, value=value, flag=flag, rule=rule))


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


def guarded(name, fn):
    try:
        RESULTS[name] = fn()
    except Exception:
        traceback.print_exc()
        RESULTS[name] = dict(error=True)
        observe(name, 'section_failed', True, flag='ERROR', rule='section raised an exception')


def load_frozen():
    reg = {k: json.loads((PRIOR / 'registry' / f).read_text(encoding='utf-8')) for k, f in (
        ('lvvo', 'lvvo-detection-protocol-261026.json'), ('coco', 'coco-subset-261026.json'),
        ('mot', 'mot-dancetrack-261026.json'))}
    gts = {}
    for key, pattern, name in (('lvvo', 'lvvo-1k-four-class', 'lvvo_gt_coco.json'), ('coco', 'coco-val2017-subset10', 'coco_subset_gt.json')):
        path = next((PRIOR / 'dataset_eda' / pattern).glob(f'*/{name}'))
        gts[key] = json.loads(path.read_text(encoding='utf-8'))
        want = reg[key]['gt_coco_canonical_sha256']
        assert q.canonical_json_sha256(gts[key]) == want, f'{key}: GT khác bản đã đóng băng'
    print('Frozen GT hashes verified (LVVO, COCO).')
    return reg, gts


REG, GT = load_frozen()
'''

LVVO_MD = r'''
## 1. LVVO (D-A) — phân bố lớp, hình học box, cấu trúc nhóm, gần trùng

Câu hỏi: (1) lớp nào ít hỗ trợ thống kê; (2) box có đặc trưng hình học nào đáng chú ý cho detector (kích thước, tỉ lệ khung, chồng lấn, chạm biên); (3) mức phụ thuộc giữa các ảnh do nhóm nguồn và ảnh gần trùng làm giảm cỡ mẫu hiệu dụng bao nhiêu; (4) các cặp gần trùng khác nhóm thực sự giống nhau đến đâu (NCC) — có lưới ảnh để duyệt tay.
'''

LVVO = r'''
LVVO_FILE_ID = '1oVufdcjhs76uDmEGu63vywKUXy5ZQSVF'
CLASS_COLORS = {'Table': '#d62728', 'Chart-Graph': '#1f77b4', 'Photographic-image': '#2ca02c', 'Visual-illustration': '#ff7f0e'}


JAC_THRESHOLD = 0.5   # screening cut only; the calibration figure shows how reliable (or not) it is


def thumb(path, width=480):
    with Image.open(path) as im:
        g = im.convert('L')
        return np.asarray(g.resize((width, max(1, round(g.height * width / g.width))), Image.Resampling.BILINEAR), dtype=np.uint8)


def eda_lvvo():
    folder = OUT / 'lvvo'
    folder.mkdir(exist_ok=True)
    archive = WORK / 'lvvo' / 'LVVO_1k_withCategories.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get('DT_LVVO_ZIP') and not archive.exists():
        shutil.copyfile(os.environ['DT_LVVO_ZIP'], archive)
    if not archive.exists():
        import gdown
        if OFFLINE or not gdown.download(id=LVVO_FILE_ID, output=str(archive), quiet=True):
            raise ConnectionError('Không tải được LVVO')
    assert q.sha256_file(archive) == REG['lvvo']['archive_sha256'], 'archive khác bản đã đóng băng'
    q.safe_extract(archive, WORK / 'lvvo' / 'source')
    root = WORK / 'lvvo' / 'source' / 'LVVO_1k_withCategories'

    gt = GT['lvvo']
    names = {c['id']: c['name'] for c in gt['categories']}
    ledger = pd.read_csv(next((PRIOR / 'dataset_eda' / 'lvvo-1k-four-class').glob('*/image_ledger.csv'))).set_index('image_id')
    img = pd.DataFrame(gt['images']).set_index('id').join(ledger[['stem', 'group']])
    ann = pd.DataFrame(gt['annotations'])
    ann['cls'] = ann.category_id.map(names)
    ann = ann.join(img[['width', 'height', 'group', 'stem']], on='image_id')
    ann[['x', 'y', 'w', 'h']] = pd.DataFrame(ann.bbox.tolist(), index=ann.index)
    ann['area_frac'] = ann.area / (ann.width * ann.height)
    ann['log2_aspect'] = np.log2(ann.w / ann.h)
    ann['cx'], ann['cy'] = (ann.x + ann.w / 2) / ann.width, (ann.y + ann.h / 2) / ann.height
    ann['touch'] = (ann.x <= 1) | (ann.y <= 1) | (ann.x + ann.w >= ann.width - 1) | (ann.y + ann.h >= ann.height - 1)
    ov = {i: eda.max_overlap_stats(g[['x', 'y', 'w', 'h']].to_numpy(float)) for i, g in ann.groupby('image_id')}
    ann['max_iou'] = 0.0
    ann['max_contain'] = 0.0
    for i, g in ann.groupby('image_id'):
        ann.loc[g.index, 'max_iou'] = ov[i]['max_iou']
        ann.loc[g.index, 'max_contain'] = ov[i]['max_containment']
    classes = sorted(names.values())

    # ---- 1.1 per-class summary (descriptive) ----
    per = ann.groupby('cls').agg(boxes=('id', 'size'), images=('image_id', 'nunique'),
                                 area_frac_p05=('area_frac', lambda s: s.quantile(.05)), area_frac_med=('area_frac', 'median'),
                                 area_frac_p95=('area_frac', lambda s: s.quantile(.95)),
                                 log2_aspect_med=('log2_aspect', 'median'), touch_border=('touch', 'mean'),
                                 overlap_iou_gt_0_3=('max_iou', lambda s: (s > .3).mean()),
                                 nested_contain_gt_0_9=('max_contain', lambda s: (s > .9).mean()))
    per['box_share'] = per.boxes / per.boxes.sum()
    per['boxes_per_positive_image'] = per.boxes / per.images
    cis = {}
    n_img = len(img)
    for c in classes:
        counts = ann[ann.cls == c].groupby('image_id').size().reindex(img.index, fill_value=0)
        cis[c] = eda.cluster_bootstrap_mean_ci(img.group.values, counts.values, seed=SEED)
    per['mean_boxes_per_image'] = [cis[c]['mean'] for c in per.index]
    per['mpi_ci_lo'] = [cis[c]['lo'] for c in per.index]
    per['mpi_ci_hi'] = [cis[c]['hi'] for c in per.index]
    save_table(per.round(4), folder, 'per_class_summary.csv')
    for c in classes:
        sup = int(per.loc[c, 'boxes'])
        observe('lvvo', f'boxes[{c}]', sup, flag='LOW_SUPPORT' if sup < 150 else None, rule='boxes < 150 (heuristic: per-class AP unstable)')

    fig, ax = plt.subplots(1, 3, figsize=(16, 4))
    per.boxes.sort_values().plot.barh(ax=ax[0], color=[CLASS_COLORS[c] for c in per.boxes.sort_values().index], title='Boxes per class')
    for c in classes:
        sub = ann[ann.cls == c]
        ax[1].hist(np.log10(sub.area_frac), bins=30, histtype='step', lw=2, density=True, label=c, color=CLASS_COLORS[c])
        ax[2].hist(sub.log2_aspect, bins=30, histtype='step', lw=2, density=True, label=c, color=CLASS_COLORS[c])
    ax[1].set(title='log10(box area / image area)', xlabel='log10 fraction')
    ax[2].set(title='log2(width/height): 0 = square', xlabel='log2 aspect')
    ax[1].legend(fontsize=7)
    savefig(fig, folder, 'class_geometry.png')

    # ---- 1.2 spatial prior, co-occurrence ----
    fig, ax = plt.subplots(1, 4, figsize=(16, 3.6))
    for a, c in zip(ax, classes):
        sub = ann[ann.cls == c]
        h, _, _ = np.histogram2d(sub.cy, sub.cx, bins=12, range=[[0, 1], [0, 1]])
        a.imshow(h / h.sum(), cmap='magma', origin='upper')
        a.set_title(f'{c}\ncentre density', fontsize=9)
        a.grid(False)
    savefig(fig, folder, 'center_density.png')
    pres = pd.DataFrame({c: img.index.isin(ann[ann.cls == c].image_id) for c in classes}, index=img.index)
    co = pd.DataFrame([[ (pres[a] & pres[b]).sum() / max((pres[a] | pres[b]).sum(), 1) for b in classes] for a in classes], index=classes, columns=classes)
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    im = ax.imshow(co.values, vmin=0, vmax=1, cmap='viridis')
    ax.set_xticks(range(4), classes, rotation=30, ha='right')
    ax.set_yticks(range(4), classes)
    for i in range(4):
        for j in range(4):
            ax.text(j, i, f'{co.values[i, j]:.2f}', ha='center', va='center', color='w')
    ax.set_title('Image-level co-occurrence (Jaccard)')
    ax.grid(False)
    fig.colorbar(im)
    savefig(fig, folder, 'cooccurrence.png')
    save_table(co.round(3), folder, 'cooccurrence_jaccard.csv', show=False)

    # ---- 1.3 groups, dependence, image size ----
    grp = img.group.value_counts()
    obs_groups = dict(groups=len(grp), median=float(grp.median()), max=int(grp.max()), top5_share=float(grp.head(5).sum() / n_img))
    print('groups:', obs_groups)
    observe('lvvo', 'groups', obs_groups)
    size = img.groupby(['width', 'height']).size().sort_values(ascending=False)
    print('top image sizes:', size.head(6).to_dict())
    mix = ann.pivot_table(index='group', columns='cls', values='id', aggfunc='size', fill_value=0).reindex(grp.index).fillna(0)
    top = mix.head(40)
    fig, ax = plt.subplots(1, 2, figsize=(15, 5))
    grp.plot.hist(bins=30, ax=ax[0], title=f'Images per source group (n groups={len(grp)})')
    ax[1].imshow((top.div(top.sum(axis=1), axis=0)).values, aspect='auto', cmap='viridis')
    ax[1].set_xticks(range(4), top.columns, rotation=30, ha='right')
    ax[1].set_title('Class mix of the 40 largest groups (row-normalised)')
    ax[1].grid(False)
    savefig(fig, folder, 'groups.png')

    dep_rows = []
    for c in classes:
        v = pres[c].astype(float).values
        d = eda.design_effect(img.group.values, v)
        dep_rows.append(dict(outcome=f'present[{c}]', **d))
    d = eda.design_effect(img.group.values, img.index.map(ann.groupby('image_id').size()).fillna(0).values)
    dep_rows.append(dict(outcome='boxes per image', **d))
    dep = pd.DataFrame(dep_rows).set_index('outcome')

    # ---- 1.4 near-duplicates: objective similarity + clusters ----
    pairs = pd.read_csv(next((PRIOR / 'dataset_eda' / 'lvvo-1k-four-class').glob('*/near_duplicate_pairs_dhash4.csv')))
    cache = {}

    def th(stem):
        if stem not in cache:
            cache[stem] = thumb(root / 'images' / f'{stem}.jpg')
        return cache[stem]

    # Raw-pixel NCC is kept only to show why it is unsuitable here: slides share a white page and black bars.
    pairs['ncc'] = [eda.ncc(eda._resize(eda.content_crop(th(a).astype(float)), 64), eda._resize(eda.content_crop(th(b).astype(float)), 64))
                    for a, b in zip(pairs.left, pairs.right)]
    pairs['jac'] = [eda.slide_jaccard(th(a), th(b)) for a, b in zip(pairs.left, pairs.right)]
    pairs['likely_duplicate'] = pairs.jac >= JAC_THRESHOLD
    pairs.sort_values('jac', ascending=False).to_csv(folder / 'near_duplicate_pairs_with_similarity.csv', index=False)
    fig, ax = plt.subplots(1, 3, figsize=(17, 3.8))
    for flag, g in pairs.groupby('same_group'):
        ax[0].hist(g.jac, bins=25, alpha=.6, label=f'same group={flag} (n={len(g)})')
    ax[0].axvline(JAC_THRESHOLD, color='k', ls='--')
    ax[0].set(title='Slide Jaccard of dHash<=4 pairs (central region)', xlabel='slide Jaccard')
    ax[0].legend()
    ax[1].scatter(pairs.jac, pairs.ncc, s=12, c=pairs.same_group.map({True: '#1f77b4', False: '#d62728'}))
    ax[1].set(xlabel='slide Jaccard', ylabel='raw NCC', title='NCC is high even for different slides (red = cross-group)')
    ax[2].scatter(pairs.distance, pairs.jac, s=12, c=pairs.same_group.map({True: '#1f77b4', False: '#d62728'}))
    ax[2].set(xlabel='dHash Hamming distance', ylabel='slide Jaccard', title='dHash vs slide Jaccard')
    savefig(fig, folder, 'near_duplicate_similarity.png')

    # calibration figure: examples from three similarity bands, so the threshold can be judged by eye
    rng_cal = np.random.default_rng(SEED)
    bands = [('jac >= 0.3', pairs[pairs.jac >= .3]), ('0.15 <= jac < 0.3', pairs[(pairs.jac >= .15) & (pairs.jac < .3)]), ('jac < 0.15', pairs[pairs.jac < .15])]
    fig, axes = plt.subplots(3, 8, figsize=(20, 7.5))
    for r, (label, band) in enumerate(bands):
        pick = band.iloc[rng_cal.permutation(len(band))[:4]] if len(band) else band
        for k in range(4):
            for side in range(2):
                a = axes[r, k * 2 + side]
                a.axis('off')
                if k < len(pick):
                    row = pick.iloc[k]
                    stem = (row.left, row.right)[side]
                    with Image.open(root / 'images' / f'{stem}.jpg') as im:
                        a.imshow(im.convert('RGB').resize((320, 180)))
                    a.set_title(f'{label} | jac={row.jac:.2f} ncc={row.ncc:.2f}' if side == 0 else f'{"same" if row.same_group else "cross"}-group', fontsize=7)
    fig.suptitle('Calibration: random dHash<=4 pairs per slide-Jaccard band (left | right of each pair): judge by eye whether high bands are really the same slide')
    savefig(fig, folder, 'near_duplicate_calibration.png')
    stem_group = dict(zip(img.stem, img.group))
    edges_all = list(zip(pairs.left, pairs.right))
    edges_hi = list(zip(pairs[pairs.likely_duplicate].left, pairs[pairs.likely_duplicate].right))
    comp_all = eda.connected_components(img.stem, edges_all)
    comp_hi = eda.connected_components(img.stem, edges_hi)
    sizes_all = pd.Series(comp_all).value_counts()
    sizes_hi = pd.Series(comp_hi).value_counts()
    summary_dup = dict(pairs=len(pairs), cross_group=int((~pairs.same_group).sum()), likely_duplicate=int(pairs.likely_duplicate.sum()),
                       likely_duplicate_cross_group=int((pairs.likely_duplicate & ~pairs.same_group).sum()),
                       images_in_any_pair=int((sizes_all[sizes_all > 1]).sum()), largest_component=int(sizes_all.max()),
                       images_in_likely_duplicate_pairs=int(sizes_hi[sizes_hi > 1].sum()))
    print('near-duplicate summary:', summary_dup)
    observe('lvvo', 'near_duplicates', summary_dup, flag='REVIEW' if summary_dup['likely_duplicate_cross_group'] else None,
            rule='cross-group pairs with slide Jaccard >= 0.5: screening flag only, inspect contact sheets')
    merged = eda.merged_group_labels(stem_group, edges_all)
    merged_hi = eda.merged_group_labels(stem_group, edges_hi)
    img['merged_group'] = img.stem.map(merged)
    img['merged_group_hi'] = img.stem.map(merged_hi)
    for label, col in (('merged by all dHash pairs (upper bound on dependence)', 'merged_group'), ('merged by slide Jaccard>=0.5 pairs', 'merged_group_hi')):
        for c in classes:
            dep_rows.append(dict(outcome=f'present[{c}] | {label}', **eda.design_effect(img[col].values, pres[c].astype(float).values)))
    dep = pd.DataFrame(dep_rows).set_index('outcome')
    save_table(dep.round(3), folder, 'design_effect.csv')
    cl = {name: img[col].nunique() for name, col in (('author groups', 'group'), ('merged (all dHash pairs)', 'merged_group'), ('merged (jac>=0.5)', 'merged_group_hi'))}
    print('independent clusters available for the bootstrap:', cl)
    observe('lvvo', 'independent_clusters', cl)
    own = dep[dep.index.str.startswith('present') & ~dep.index.str.contains(r'\|')]
    upper = dep[dep.index.str.contains('all dHash pairs')]
    observe('lvvo', 'max_design_effect_author_groups', float(own.deff.max()), flag='DEPENDENT' if own.deff.max() > 1.5 else None,
            rule='design effect > 1.5 with author groups: bootstrap must resample groups')
    observe('lvvo', 'max_design_effect_upper_bound_all_dhash_merge', float(upper.deff.max()),
            rule='upper bound if every dHash<=4 pair were a true duplicate (not supported by calibration figure)')
    observe('lvvo', 'min_effective_n_author_groups', float(own.n_eff.min()))

    # contact sheets for cross-group pairs (manual adjudication aid)
    cross = pairs[~pairs.same_group].sort_values('jac', ascending=False).reset_index(drop=True)
    per_page, pages = 12, int(np.ceil(len(cross) / 12))
    sheet_dir = folder / 'dup_review_sheets'
    sheet_dir.mkdir(exist_ok=True)
    for p in range(pages):
        chunk = cross.iloc[p * per_page:(p + 1) * per_page]
        fig, axes = plt.subplots(6, 4, figsize=(14, 17))
        for a in axes.ravel():
            a.axis('off')
        for k, r in enumerate(chunk.itertuples()):
            for side, stem in enumerate((r.left, r.right)):
                a = axes[k // 2, (k % 2) * 2 + side]
                with Image.open(root / 'images' / f'{stem}.jpg') as im:
                    a.imshow(im.convert('RGB').resize((320, 180)))
                a.set_title(f'{stem[:34]}\n{"jac %.2f ncc %.2f d=%d" % (r.jac, r.ncc, r.distance) if side == 0 else "group " + stem_group[stem][:20]}', fontsize=6)
        fig.suptitle(f'Cross-group dHash<=4 pairs, sorted by slide Jaccard (page {p + 1}/{pages}); ghi nhận xét vào cột reviewer của CSV', fontsize=9)
        savefig(fig, sheet_dir, f'page_{p + 1:02d}.png', show=p < 2)
    template = cross[['left', 'right', 'distance', 'jac', 'ncc']].assign(reviewer_decision='', note='')
    template.to_csv(folder / 'cross_group_pairs_review_template.csv', index=False)

    # ---- 1.5 overlays ----
    rng = np.random.default_rng(SEED)
    fig, axes = plt.subplots(4, 4, figsize=(16, 13))
    for r, c in enumerate(classes):
        ids = rng.choice(ann[ann.cls == c].image_id.unique(), 4, replace=False)
        for k, i in enumerate(ids):
            a = axes[r, k]
            im = Image.open(root / 'images' / (img.loc[i, 'stem'] + '.jpg')).convert('RGB')
            d = ImageDraw.Draw(im)
            for _, b in ann[ann.image_id == i].iterrows():
                d.rectangle((b.x, b.y, b.x + b.w, b.y + b.h), outline=CLASS_COLORS[b.cls], width=max(3, im.width // 300))
            a.imshow(im)
            a.set_title(f'{c} | {img.loc[i, "stem"][:30]}', fontsize=7)
            a.axis('off')
    fig.suptitle('GT overlays: one row per class (colour = class of each box)')
    savefig(fig, folder, 'overlays.png')
    return dict(per_class=per.boxes.to_dict(), images=n_img, groups=len(grp))


guarded('lvvo', eda_lvvo)
'''

COCO_MD = r'''
## 2. COCO subset (D-B) — hỗ trợ theo lớp, tính đại diện, hình học, chồng lấn

Câu hỏi: (1) hạn ngạch 200 ảnh/lớp có đạt không và lớp nào bị giới hạn bởi dữ liệu; (2) tập con lệch gì so với toàn bộ val2017 (lệch do phân tầng là có chủ đích, cần biết hướng và độ lớn); (3) hình học và mức chồng lấn/chạm biên theo lớp; (4) độ chính xác ước lượng được theo lớp (bootstrap theo ảnh).
'''

COCO = r'''
COCO_ANN_URL = 'http://images.cocodataset.org/annotations/annotations_trainval2017.zip'
COCO_IMG_URL = 'http://images.cocodataset.org/val2017/{}'


def eda_coco():
    from concurrent.futures import ThreadPoolExecutor
    folder = OUT / 'coco'
    folder.mkdir(exist_ok=True)
    cdir = WORK / 'coco'
    instances = cdir / 'annotations' / 'instances_val2017.json'
    if not instances.exists():
        zpath = cdir / 'annotations_trainval2017.zip'
        if not zpath.exists():
            download(COCO_ANN_URL, zpath)
        assert q.sha256_file(zpath) == REG['coco']['annotations_zip_sha256'], 'annotations khác bản đã đóng băng'
        q.safe_extract(zpath, cdir, keep=lambda n: n.endswith('instances_val2017.json'))
    full = json.loads(instances.read_text(encoding='utf-8'))
    tax = {int(k): v for k, v in REG['coco']['taxonomy'].items()}
    classes = list(tax.values())
    subset = GT['coco']
    ids = set(REG['coco']['image_ids'])
    img = pd.DataFrame(subset['images']).set_index('id')
    ann = pd.DataFrame(subset['annotations'])
    ann['cls'] = ann.category_id.map(tax)
    ann = ann.join(img[['width', 'height', 'file_name', 'license']], on='image_id')
    ann[['x', 'y', 'w', 'h']] = pd.DataFrame(ann.bbox.tolist(), index=ann.index)
    ann['area_frac'] = ann.area / (ann.width * ann.height)
    ann['log2_aspect'] = np.log2(ann.w.clip(lower=1) / ann.h.clip(lower=1))
    ann['stratum'] = ann.area.map(q.size_stratum)
    ann['cx'], ann['cy'] = (ann.x + ann.w / 2) / ann.width, (ann.y + ann.h / 2) / ann.height
    ann['touch'] = (ann.x <= 1) | (ann.y <= 1) | (ann.x + ann.w >= ann.width - 1) | (ann.y + ann.h >= ann.height - 1)
    ann['max_iou'] = 0.0
    ann['max_contain'] = 0.0
    for i, g in ann[ann.iscrowd == 0].groupby('image_id'):
        o = eda.max_overlap_stats(g[['x', 'y', 'w', 'h']].to_numpy(float))
        ann.loc[g.index, 'max_iou'] = o['max_iou']
        ann.loc[g.index, 'max_contain'] = o['max_containment']
    nc = ann[ann.iscrowd == 0]

    # ---- 2.1 quota vs availability ----
    fa = pd.DataFrame(full['annotations'])
    fa = fa[(fa.category_id.isin(tax)) & (fa.iscrowd == 0)]
    fa['cls'] = fa.category_id.map(tax)
    avail = fa.groupby('cls').image_id.nunique()
    got = nc.groupby('cls').image_id.nunique()
    quota = REG['coco']['selection']['quota_per_class']
    sup = pd.DataFrame({'eligible_images_full_val': avail, 'selected_images': got, 'quota': quota,
                        'selected_boxes': nc.groupby('cls').size(), 'full_val_boxes': fa.groupby('cls').size()}).loc[classes]
    sup['quota_met'] = sup.selected_images >= sup.quota
    sup['selected_share_of_available'] = (sup.selected_images / sup.eligible_images_full_val).round(3)
    save_table(sup, folder, 'support_vs_quota.csv')
    for c in classes:
        r = sup.loc[c]
        observe('coco', f'selected_images[{c}]', int(r.selected_images), flag=None if r.quota_met else 'QUOTA_NOT_MET',
                rule=f'selected images < quota {quota} (class limited by availability or by overlap with other classes)')
        observe('coco', f'boxes[{c}]', int(r.selected_boxes), flag='LOW_SUPPORT' if r.selected_boxes < 150 else None,
                rule='boxes < 150 (heuristic: per-class AP unstable)')
    fig, ax = plt.subplots(figsize=(11, 4))
    x = np.arange(len(classes))
    ax.bar(x - .2, sup.eligible_images_full_val, .4, label='images with class in full val2017', color='#bbb')
    ax.bar(x + .2, sup.selected_images, .4, label='selected images', color='#1f77b4')
    ax.axhline(quota, color='k', ls='--', label=f'quota {quota}')
    ax.set_xticks(x, classes, rotation=30, ha='right')
    ax.set_yscale('log')
    ax.legend()
    ax.set_title('Per-class availability vs selection')
    savefig(fig, folder, 'quota_vs_availability.png')

    # ---- 2.2 representativeness vs full val (descriptive; selection is stratified on purpose) ----
    rows = []
    fa['area'] = fa.area
    for c in classes:
        a_full = np.log2(fa[fa.cls == c].area.clip(lower=1))
        a_sub = np.log2(nc[nc.cls == c].area.clip(lower=1))
        r = eda.compare_samples(a_sub, a_full)
        rows.append(dict(cls=c, n_subset=len(a_sub), n_full=len(a_full), median_log2_area_subset=r['median_a'],
                         median_log2_area_full=r['median_b'], ks=r['ks'], cliffs_delta=r['cliffs_delta'],
                         small_share_subset=(nc[nc.cls == c].stratum == 'small').mean(),
                         small_share_full=(fa[fa.cls == c].area < 32 ** 2).mean()))
    rep = pd.DataFrame(rows).set_index('cls')
    rep['effect'] = rep.cliffs_delta.map(eda.effect_label)
    save_table(rep.round(3), folder, 'representativeness_vs_full_val.csv')
    for c in classes:
        observe('coco', f'size_shift_vs_full[{c}]', dict(delta=float(rep.loc[c, 'cliffs_delta']), effect=rep.loc[c, 'effect']),
                flag='SIZE_SHIFT' if abs(rep.loc[c, 'cliffs_delta']) >= .33 else None,
                rule='|Cliff delta| >= 0.33 between subset and full val2017 box areas (expected under stratification; report direction)')
    fig, ax = plt.subplots(1, 2, figsize=(14, 4))
    w = .4
    ax[0].bar(x - w / 2, rep.small_share_full, w, label='full val2017', color='#bbb')
    ax[0].bar(x + w / 2, rep.small_share_subset, w, label='subset', color='#1f77b4')
    ax[0].set_xticks(x, classes, rotation=30, ha='right')
    ax[0].set(title='Share of small boxes (<32^2 px)')
    ax[0].legend()
    strata = nc.pivot_table(index='cls', columns='stratum', values='id', aggfunc='size', fill_value=0).loc[classes][['small', 'medium', 'large']]
    (strata.div(strata.sum(axis=1), axis=0)).plot.bar(stacked=True, ax=ax[1], title='Box size strata in subset (share)', color=['#d62728', '#ff7f0e', '#2ca02c'])
    ax[1].tick_params(axis='x', rotation=30)
    savefig(fig, folder, 'representativeness_size.png')

    # ---- 2.3 geometry, spatial prior, crowd, overlap, truncation ----
    per = nc.groupby('cls').agg(boxes=('id', 'size'), images=('image_id', 'nunique'), area_frac_med=('area_frac', 'median'),
                                log2_aspect_med=('log2_aspect', 'median'), touch_border=('touch', 'mean'),
                                overlap_iou_gt_0_3=('max_iou', lambda s: (s > .3).mean()),
                                nested_contain_gt_0_9=('max_contain', lambda s: (s > .9).mean())).loc[classes]
    per['crowd_boxes'] = ann[ann.iscrowd == 1].groupby('cls').size().reindex(classes).fillna(0).astype(int)
    per['boxes_per_positive_image'] = per.boxes / per.images
    ci = {c: eda.cluster_bootstrap_mean_ci(nc[nc.cls == c].image_id.values, (nc[nc.cls == c].stratum == 'small').astype(float).values, seed=SEED) for c in classes}
    per['small_share'] = [ci[c]['mean'] for c in classes]
    per['small_ci_lo'] = [ci[c]['lo'] for c in classes]
    per['small_ci_hi'] = [ci[c]['hi'] for c in classes]
    save_table(per.round(4), folder, 'per_class_summary.csv')
    fig, ax = plt.subplots(1, 3, figsize=(16, 4))
    for c in classes:
        s = nc[nc.cls == c]
        ax[0].hist(np.log10(s.area_frac), bins=30, histtype='step', density=True, label=c)
        ax[1].hist(s.log2_aspect, bins=30, histtype='step', density=True)
    ax[0].set(title='log10(area / image area)')
    ax[0].legend(fontsize=6, ncol=2)
    ax[1].set(title='log2(w/h)')
    nc.groupby('image_id').size().plot.hist(bins=30, ax=ax[2], title='Taxonomy boxes per image')
    savefig(fig, folder, 'geometry.png')
    fig, ax = plt.subplots(2, 5, figsize=(16, 6.5))
    for a, c in zip(ax.ravel(), classes):
        s = nc[nc.cls == c]
        h, _, _ = np.histogram2d(s.cy, s.cx, bins=12, range=[[0, 1], [0, 1]])
        a.imshow(h / h.sum(), cmap='magma')
        a.set_title(c, fontsize=9)
        a.grid(False)
        a.axis('off')
    fig.suptitle('Box-centre density (normalised image coordinates)')
    savefig(fig, folder, 'center_density.png')
    pres = pd.DataFrame({c: img.index.isin(nc[nc.cls == c].image_id) for c in classes}, index=img.index)
    co = pd.DataFrame([[(pres[a] & pres[b]).sum() / max((pres[a] | pres[b]).sum(), 1) for b in classes] for a in classes], index=classes, columns=classes)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(co.values, cmap='viridis')
    ax.set_xticks(range(len(classes)), classes, rotation=45, ha='right')
    ax.set_yticks(range(len(classes)), classes)
    ax.set_title('Image-level co-occurrence (Jaccard)')
    ax.grid(False)
    fig.colorbar(im)
    savefig(fig, folder, 'cooccurrence.png')
    save_table(co.round(3), folder, 'cooccurrence_jaccard.csv', show=False)

    # ---- 2.4 images, licences ----
    lic = {l['id']: l['name'] for l in full.get('licenses', [])}
    lic_counts = img.license.map(lic).value_counts()
    restricted = img.license.map(lic).str.contains('NonCommercial|NoDerivs', na=False).mean()
    save_table(lic_counts.to_frame('images'), folder, 'image_licenses.csv')
    observe('coco', 'share_images_NonCommercial_or_NoDerivs', float(restricted), flag='LICENCE', rule='research use only, no redistribution of images')
    sizes = img.groupby(['width', 'height']).size().sort_values(ascending=False)
    print('top image sizes:', sizes.head(5).to_dict(), '| distinct sizes:', len(sizes))

    # ---- 2.5 overlays (downloads only the sampled images) ----
    rng = np.random.default_rng(SEED)
    fig, axes = plt.subplots(5, 6, figsize=(18, 14))
    imgdir = cdir / 'val2017_subset'
    for r, c in enumerate(classes):
        pool = nc[nc.cls == c].image_id.unique()
        pick = rng.choice(pool, 3, replace=False)
        for k, i in enumerate(pick):
            a = axes[r // 2, (r % 2) * 3 + k]
            fn = img.loc[i, 'file_name']
            path = imgdir / fn
            if not path.exists():
                download(COCO_IMG_URL.format(fn), path)
            im = Image.open(path).convert('RGB')
            d = ImageDraw.Draw(im)
            for _, b in ann[ann.image_id == i].iterrows():
                col = '#ff3b30' if b.cls == c else '#00c2ff'
                d.rectangle((b.x, b.y, b.x + b.w, b.y + b.h), outline=col, width=3)
            a.imshow(im)
            a.set_title(f'{c} | {fn}', fontsize=7)
            a.axis('off')
    fig.suptitle('Overlays (red = focus class, cyan = other taxonomy classes)')
    savefig(fig, folder, 'overlays.png')
    return dict(classes=classes)


guarded('coco', eda_coco)
'''

MOT_MD = r'''
## 3. DanceTrack (T) — độ khó association, dịch chuyển train/val, camera

Mỗi sequence là một đơn vị. Đặc trưng độ khó liên quan trực tiếp đến AssA/HOTA: mật độ, **che khuất** (IoU>0.3 với box khác), **cặp gần nhau** (IoU>0.5, nguy cơ đổi ID), **khoảng gián đoạn của ID** (tái xuất hiện), **vận tốc chuẩn hóa** theo chiều cao box và **tính phi tuyến** của chuyển động (góc rẽ giữa hai bước liên tiếp). So sánh train (tuning) với val (đánh giá) ở mức sequence, Holm cho nhiều đặc trưng. Camera: phase correlation trên các cặp frame liên tiếp, dùng để kiểm chứng proxy cũ, không phải nhãn.
'''

MOT = r'''
DT_BASE = 'https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/{}.zip'
CAM_PAIRS = 6
FEATURES = [('boxes_per_frame', 'mật độ box/frame'), ('occluded_share', 'tỉ lệ box bị che (IoU>0.3)'),
            ('close_pairs_per_1k_frames', 'cặp IoU>0.5 / 1000 frame'), ('gap_missing_share', 'tỉ lệ frame vắng của ID'),
            ('gaps_per_track', 'số gián đoạn / track'), ('track_len_median', 'độ dài track trung vị'),
            ('h_rel_median', 'chiều cao box / chiều cao ảnh'), ('speed_median', 'vận tốc chuẩn hóa trung vị'),
            ('speed_p90', 'vận tốc chuẩn hóa p90'), ('turn_deg_mean', 'góc rẽ trung bình (độ)'),
            ('cam_shift_median', 'dịch chuyển camera trung vị (px)')]


def eda_dancetrack():
    import cv2
    folder = OUT / 'dancetrack'
    folder.mkdir(exist_ok=True)
    zips = {}
    for name in ('train1', 'train2', 'val'):
        zips[name] = zipfile.ZipFile(eda.HttpRangeFile(DT_BASE.format(name)))
    seqs = {}
    for name, zf in zips.items():
        default = 'val' if name == 'val' else 'train'
        for n in (i.filename for i in zf.infolist() if not i.is_dir()):
            m = q.parse_mot_member(n, default)
            if not m:
                continue
            e = seqs.setdefault((m['split'], m['seq']), dict(zf=zf, frames={}, gt=None, info=None))
            if m['kind'] == 'seqinfo.ini':
                e['info'] = n
            elif m['kind'] == 'gt/gt.txt':
                e['gt'] = n
            else:
                e['frames'][int(m['frame'])] = n
    frozen = {(s, d['seq']): d for s in ('train', 'val') for d in REG['mot']['sequences'][s]}
    assert set(frozen) <= set(seqs), 'sequence đã đóng băng không còn trong nguồn'
    rows, pooled = [], {'train': dict(track_len=[], gap=[], speed=[], turn=[], h_rel=[], bpf=[]), 'val': dict(track_len=[], gap=[], speed=[], turn=[], h_rel=[], bpf=[])}
    gts, timeline = {}, {}
    for (split, seq), d in sorted(frozen.items()):
        e = seqs[(split, seq)]
        gt_bytes = e['zf'].read(e['gt'])
        assert hashlib.sha256(gt_bytes).hexdigest() == d['gt_sha256'], f'{seq}: GT khác bản đã đóng băng'
        info = q.parse_seqinfo(e['zf'].read(e['info']).decode())
        length, W, H = int(info['seqLength']), int(info['imWidth']), int(info['imHeight'])
        gt = q.parse_mot_gt(gt_bytes.decode())
        gts[(split, seq)] = gt
        tracks = eda.mot_track_table(gt)
        gaps = eda.mot_gap_lengths(gt)
        mo = eda.mot_motion(gt)
        ov = eda.mot_frame_overlap(gt)
        per_frame = np.bincount(gt[:, 0].astype(int), minlength=length + 1)[1:]
        timeline[(split, seq)] = per_frame
        # camera: consecutive pairs spread over the video
        starts = np.linspace(1, max(length - 1, 1), CAM_PAIRS).astype(int)
        pairs_img = []
        for s0 in starts:
            if s0 in e['frames'] and s0 + 1 in e['frames']:
                ims = []
                for fidx in (s0, s0 + 1):
                    arr = cv2.imdecode(np.frombuffer(e['zf'].read(e['frames'][fidx]), np.uint8), cv2.IMREAD_GRAYSCALE)
                    ims.append(cv2.resize(arr, (480, max(1, int(arr.shape[0] * 480 / arr.shape[1])))))
                pairs_img.append(tuple(ims))
        shifts = [float(np.hypot(*cv2.phaseCorrelate(np.float32(a), np.float32(b))[0])) for a, b in pairs_img]
        rows.append(dict(
            split=split, seq=seq, frames=length, width=W, height=H, tracks=len(tracks), boxes=len(gt),
            boxes_per_frame=len(gt) / length, occluded_share=float(ov['occluded'].mean()),
            close_pairs_per_1k_frames=float(ov['close_pairs'].sum() / length * 1000),
            gap_missing_share=float(tracks.missing.sum() / tracks.span.sum()), gaps_per_track=float(tracks.n_gaps.mean()),
            track_len_median=float(tracks.n_frames.median()), h_rel_median=float(np.median(gt[:, 5]) / H),
            speed_median=float(np.median(mo['speed'])), speed_p90=float(np.quantile(mo['speed'], .9)),
            turn_deg_mean=float(mo['turn_deg'].mean()) if len(mo['turn_deg']) else np.nan,
            cam_shift_median=float(np.median(shifts)) if shifts else np.nan, cam_pairs=len(shifts),
            ids_min=int(gt[:, 1].min()), ids_max=int(gt[:, 1].max()), ids_contiguous=bool(len(np.unique(gt[:, 1])) == gt[:, 1].max() - gt[:, 1].min() + 1)))
        p = pooled[split]
        p['track_len'] += tracks.n_frames.tolist()
        p['gap'] += gaps.tolist()
        p['speed'] += mo['speed'].tolist()
        p['turn'] += mo['turn_deg'].tolist()
        p['h_rel'] += (gt[:, 5] / H).tolist()
        p['bpf'] += per_frame.tolist()
    df = pd.DataFrame(rows)
    save_table(df.round(4), folder, 'sequence_features.csv', show=False)
    display(df.groupby('split')[[f for f, _ in FEATURES]].median().round(3))
    print('ID bắt đầu từ 0 và liên tục trong mọi sequence:', bool((df.ids_min == 0).all() and df.ids_contiguous.all()))

    # ---- 3.1 train vs val (sequence-level inference, Holm) ----
    tr, va = df[df.split == 'train'], df[df.split == 'val']
    comp = pd.DataFrame({f: eda.compare_samples(tr[f].dropna(), va[f].dropna()) for f, _ in FEATURES}).T
    comp['p_mw_holm'] = eda.holm_adjust(comp.p_mw.astype(float).values)
    comp['effect'] = comp.cliffs_delta.astype(float).map(eda.effect_label)
    comp['description'] = [dict(FEATURES)[f] for f in comp.index]
    save_table(comp.round(4), folder, 'train_vs_val_tests.csv')
    for f, r in comp.iterrows():
        shift = r.p_mw_holm < .05 and abs(r.cliffs_delta) >= .33
        observe('dancetrack', f'train_vs_val[{f}]', dict(delta=float(r.cliffs_delta), p_holm=float(r.p_mw_holm), effect=r.effect),
                flag='DISTRIBUTION_SHIFT' if shift else None, rule='Holm p<0.05 and |Cliff delta|>=0.33 at sequence level (train n=%d, val n=%d)' % (len(tr), len(va)))

    # ---- 3.2 val feature CIs (n sequences small) ----
    ci_rows = {f: eda.cluster_bootstrap_mean_ci(np.arange(len(va)), va[f].fillna(va[f].mean()).values, seed=SEED) for f, _ in FEATURES}
    ci_df = pd.DataFrame(ci_rows).T[['mean', 'lo', 'hi']]
    save_table(ci_df.round(4), folder, 'val_feature_means_bootstrap_ci.csv')

    # ---- 3.3 figures ----
    fig, ax = plt.subplots(2, 3, figsize=(17, 8))
    for split, col in (('train', '#1f77b4'), ('val', '#d62728')):
        p = pooled[split]
        ax[0, 0].hist(p['track_len'], bins=40, alpha=.5, density=True, color=col, label=split)
        if len(p['gap']):
            ax[0, 1].hist(np.log10(p['gap']), bins=30, alpha=.5, density=True, color=col)
        ax[0, 2].hist(np.clip(p['speed'], 0, 0.3), bins=40, alpha=.5, density=True, color=col)
        ax[1, 0].hist(p['turn'], bins=36, alpha=.5, density=True, color=col)
        ax[1, 1].hist(p['h_rel'], bins=40, alpha=.5, density=True, color=col)
        ax[1, 2].hist(p['bpf'], bins=range(0, 25), alpha=.5, density=True, color=col)
    ax[0, 0].set(title='Track length (frames present), pooled over tracks')
    ax[0, 0].legend()
    ax[0, 1].set(title='Interruption length of an ID, log10 frames')
    ax[0, 2].set(title='Speed per frame / box height (clipped 0.3)')
    ax[1, 0].set(title='Turn angle between consecutive steps (deg)')
    ax[1, 1].set(title='Box height / image height')
    ax[1, 2].set(title='Boxes per frame')
    fig.suptitle('Pooled distributions (descriptive; inference is done at sequence level)')
    savefig(fig, folder, 'pooled_distributions.png')

    fig, ax = plt.subplots(2, 3, figsize=(17, 7))
    for a, (f, desc) in zip(ax.ravel(), [FEATURES[i] for i in (0, 1, 3, 7, 9, 10)]):
        a.boxplot([tr[f].dropna(), va[f].dropna()], tick_labels=[f'train ({len(tr)})', f'val ({len(va)})'], showmeans=True)
        a.scatter(np.random.default_rng(1).normal(1, .04, len(tr)), tr[f], s=10, alpha=.5)
        a.scatter(np.random.default_rng(2).normal(2, .04, len(va)), va[f], s=10, alpha=.5)
        r = comp.loc[f]
        a.set_title(f'{desc}\nδ={r.cliffs_delta:.2f} ({r.effect}), Holm p={r.p_mw_holm:.3f}', fontsize=8)
    savefig(fig, folder, 'sequence_level_train_vs_val.png')

    corr = df[[f for f, _ in FEATURES]].corr(method='spearman')
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap='coolwarm')
    ax.set_xticks(range(len(corr)), corr.columns, rotation=60, ha='right', fontsize=7)
    ax.set_yticks(range(len(corr)), corr.columns, fontsize=7)
    ax.set_title(f'Spearman correlation of difficulty features (all {len(df)} sequences)')
    ax.grid(False)
    fig.colorbar(im)
    savefig(fig, folder, 'feature_correlation.png')
    save_table(corr.round(3), folder, 'feature_correlation.csv', show=False)

    fig, ax = plt.subplots(1, 2, figsize=(15, 4))
    for split, col in (('train', '#1f77b4'), ('val', '#d62728')):
        for (s, seq), t in timeline.items():
            if s == split:
                ax[0].plot(np.linspace(0, 1, len(t)), t, color=col, alpha=.35, lw=.8)
    ax[0].set(title='Boxes per frame over normalised time (blue train, red val)', xlabel='relative time')
    ax[1].hist([tr.cam_shift_median.dropna(), va.cam_shift_median.dropna()], bins=20, label=['train', 'val'])
    ax[1].axvline(1.0, color='k', ls='--')
    ax[1].set(title='Median camera shift between consecutive frames (px @480 wide)')
    ax[1].legend()
    savefig(fig, folder, 'density_timeline_and_camera.png')
    moving_val = int((va.cam_shift_median > 1.0).sum())
    observe('dancetrack', 'val_sequences_with_moving_camera', moving_val, flag='NO_CAMERA_STRATA' if moving_val < 5 else None,
            rule='fewer than 5 val sequences with median shift > 1 px: camera strata not analysable')
    observe('dancetrack', 'val_sequences', len(va), flag='FEW_UNITS', rule='fewer than 30 evaluation videos: wide CI, descriptive conclusions')
    observe('dancetrack', 'val_gap_missing_share_mean', float(va.gap_missing_share.mean()))

    # ---- 3.4 prior proxy check ----
    prior = pd.read_csv(next((PRIOR / 'dataset_eda' / 'dancetrack-mot').glob('*/sequence_ledger.csv')))
    m = df.merge(prior[['split', 'seq', 'camera_shift_px']], on=['split', 'seq'])
    rho = sps.spearmanr(m.cam_shift_median, m.camera_shift_px, nan_policy='omit')
    print(f'Spearman giữa proxy camera cũ (ít cặp) và mới ({CAM_PAIRS} cặp): rho={rho.statistic:.3f}')
    observe('dancetrack', 'camera_proxy_agreement_spearman', float(rho.statistic))

    # ---- 3.5 overlays: sequences spread over density, one dense/occluded frame each ----
    chosen = va.sort_values('boxes_per_frame').iloc[np.linspace(0, len(va) - 1, 6).astype(int)]
    fig, axes = plt.subplots(2, 3, figsize=(18, 9))
    for a, r in zip(axes.ravel(), chosen.itertuples()):
        e = seqs[('val', r.seq)]
        gt = gts[('val', r.seq)]
        frame = int(np.median(gt[:, 0]))
        arr = cv2.imdecode(np.frombuffer(e['zf'].read(e['frames'][frame]), np.uint8), cv2.IMREAD_COLOR)[:, :, ::-1]
        im = Image.fromarray(arr)
        d = ImageDraw.Draw(im)
        for row in gt[gt[:, 0] == frame]:
            d.rectangle((row[2], row[3], row[2] + row[4], row[3] + row[5]), outline=(255, 59, 48), width=3)
            d.text((row[2] + 3, row[3] + 3), str(int(row[1])), fill=(255, 255, 0))
        a.imshow(im)
        a.set_title(f'{r.seq} frame {frame} | {r.boxes_per_frame:.1f} box/frame | occl {r.occluded_share:.2f}', fontsize=8)
        a.axis('off')
    fig.suptitle('Val sequences spread over density, GT with identity labels')
    savefig(fig, folder, 'overlays.png')
    return dict(sequences=len(df))


guarded('dancetrack', eda_dancetrack)
'''

OBS_MD = r'''
## 4. Bảng quan sát và gói kết quả

Mỗi cờ là một **quy tắc heuristic ghi rõ trong cột `rule`**, không phải kết luận. Cờ chỉ ra chỗ phase 3/4 cần xử lý (báo cáo riêng lớp ít hỗ trợ, bootstrap theo nhóm, không phân tầng theo camera, ...).
'''

OBSERVE = r'''
obs = pd.DataFrame(OBS)
display(obs[obs.flag.notna()][['dataset', 'key', 'flag', 'value', 'rule']].to_string(index=False) if obs.flag.notna().any() else 'Không có cờ.')
write_json(OUT / 'eda-observations.json', dict(
    run_id=RUN_ID, finished_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(), seed=SEED,
    inputs_verified=dict(lvvo_gt=REG['lvvo']['gt_coco_canonical_sha256'], coco_gt=REG['coco']['gt_coco_canonical_sha256'],
                         mot_sequences_sha=REG['mot']['sequence_ids_sha256']),
    sections={k: ('ERROR' if v.get('error') else 'ok') for k, v in RESULTS.items()}, observations=OBS,
    model_inference_run=False, scoring_run=False))
bundle = OUT / 'bundle.zip'
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path != bundle and path.suffix in {'.json', '.csv', '.png'}:
            zf.write(path, path.relative_to(OUT))
print('Bundle:', bundle, f'{bundle.stat().st_size / 1e6:.1f} MB', '| sections:', {k: ('ERROR' if v.get('error') else 'ok') for k, v in RESULTS.items()})
'''


def build():
    sources = {m: (ROOT / m).read_text(encoding="utf-8") for m in MODULES}
    cells = [
        cell("markdown", INTRO),
        cell("code", SETUP),
        cell("code", EMBED.replace("{{", "{").replace("}}", "}").replace("{sources!r}", repr(sources))),
        cell("code", HELPERS),
        cell("markdown", LVVO_MD),
        cell("code", LVVO),
        cell("markdown", COCO_MD),
        cell("code", COCO),
        cell("markdown", MOT_MD),
        cell("code", MOT),
        cell("markdown", OBS_MD),
        cell("code", OBSERVE),
    ]
    notebook = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python"), colab=dict(provenance=[])))
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
