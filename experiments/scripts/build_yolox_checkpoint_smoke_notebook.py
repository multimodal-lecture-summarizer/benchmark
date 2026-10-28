"""Build the Colab notebook that smoke-tests detection source (b): the DanceTrack YOLOX checkpoint.

Usage (from benchmark/): python experiments/scripts/build_yolox_checkpoint_smoke_notebook.py
The notebook embeds experiments/scripts/yolox_checkpoint_smoke.py, so the script and the notebook cannot drift.
"""

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "experiments/scripts/yolox_checkpoint_smoke.py"
OUTPUT = ROOT / "experiments/notebooks/yolox-checkpoint-smoke-colab.ipynb"


def cell(kind, source):
    value = dict(cell_type=kind, metadata={}, source=source.strip("\n").splitlines(True))
    if kind == "code":
        ast.parse(source)
        value.update(execution_count=None, outputs=[])
    return value


INTRO = r'''
# Smoke — checkpoint YOLOX của DanceTrack (nguồn detections b)

Mục đích: kiểm **trước khi dùng** xem `noahcao/dancetrack_models/bytetrack_models/bytetrack_model.pth.tar` có (1) tải được và nạp `strict=True` vào YOLOX-X, (2) ra box người trên một khung val, (3) tự khai dữ liệu train hay không. Không chấm điểm, không chạy tracker.

Tiêu chí đạt/không đạt nằm ở `detection_source_b.smoke_acceptance` trong `tracker-search-space-dancetrack-261027.json`. Notebook chỉ báo dữ kiện; **việc coi val là "chưa thấy" hay bỏ nguồn (b) do người quyết định** sau khi đọc `yolox-checkpoint-smoke.json`.

Chạy tuần tự. GPU không bắt buộc (một khung, CPU vài giây). Cần ~1 GB trống cho checkpoint.
'''

SETUP = r'''
import subprocess, sys, json
from pathlib import Path

IN_COLAB = Path('/content').exists()
WORK = Path('/content/yolox-smoke') if IN_COLAB else Path.cwd() / 'yolox-smoke-work'
OUT = Path('/content/drive/MyDrive/DetTrack/yolox-smoke-261027') if IN_COLAB else WORK / 'out'
if IN_COLAB:
    from google.colab import drive
    drive.mount('/content/drive')
for p in (WORK, OUT):
    p.mkdir(parents=True, exist_ok=True)
# yolox is NOT pip-installed (its setup.py imports torch at build time and failed on Colab py3.13); inference only needs the
# python sources of yolox.models / yolox.utils, so clone the tagged release and put it on sys.path.
subprocess.run([sys.executable, '-m', 'pip', 'install', 'huggingface_hub', 'fsspec', 'aiohttp', 'opencv-python-headless',
                'loguru', 'thop', 'tabulate', 'pycocotools'], check=True)
YOLOX_DIR = WORK / 'YOLOX'
if not YOLOX_DIR.exists():
    subprocess.run(['git', 'clone', '--depth', '1', '--branch', '0.3.0', 'https://github.com/Megvii-BaseDetection/YOLOX.git',
                    str(YOLOX_DIR)], check=True)
sys.path.insert(0, str(YOLOX_DIR))
import yolox, yolox.models, yolox.utils      # fail here, not inside the smoke subprocess, if a dependency is missing
print('yolox', yolox.__version__, 'from', Path(yolox.__file__).parent, '\nwork:', WORK, '\nresults:', OUT)
'''

EMBED = r'''
SCRIPT = WORK / 'yolox_checkpoint_smoke.py'
SCRIPT.write_text({source!r}, encoding='utf-8')
print('script written:', SCRIPT)
'''

FRAME = r'''
# One DanceTrack val frame by HTTP range read (does not download the 11 GB archive).
import zipfile, fsspec
VAL_URL = 'https://huggingface.co/datasets/noahcao/dancetrack/resolve/main/val.zip'
N_SEQ = 3                                   # distinct sequences; 3 frames each, evenly spread, deterministic
FRAMES, GT = [], {}
with fsspec.open(VAL_URL, 'rb', block_size=1 << 20) as fh, zipfile.ZipFile(fh) as zf:
    names = [i.filename for i in zf.infolist() if not i.is_dir()]
    seqs = sorted({n.split('/')[1] for n in names if '/img1/' in n})
    for seq in seqs[:: max(1, len(seqs) // N_SEQ)][:N_SEQ]:
        rows = [l.split(',') for l in zf.read(f'val/{seq}/gt/gt.txt').decode().splitlines()]
        n_frames = max(int(r[0]) for r in rows)
        for f in (n_frames // 4, n_frames // 2, 3 * n_frames // 4):
            path = WORK / f'{seq}_{f:08d}.jpg'
            path.write_bytes(zf.read(f'val/{seq}/img1/{f:08d}.jpg'))
            FRAMES.append(str(path))
            GT[path.name] = [[float(r[2]), float(r[3]), float(r[4]), float(r[5])] for r in rows if int(r[0]) == f]
GT_FILE = WORK / 'gt.json'
GT_FILE.write_text(json.dumps(GT))
print(len(FRAMES), 'frames; GT boxes per frame:', {k: len(v) for k, v in GT.items()})
'''

RUN = r'''
import os
proc = subprocess.run([sys.executable, str(SCRIPT), '--frames', *FRAMES, '--gt', str(GT_FILE),
                       '--out', str(OUT / 'yolox-checkpoint-smoke.json')],
                      capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(YOLOX_DIR)})
if proc.returncode:
    print('--- stderr ---\n', proc.stderr[-4000:])
report = json.loads((OUT / 'yolox-checkpoint-smoke.json').read_text(encoding='utf-8'))
print('agreement with GT (IoU 0.5, score >= 0.5, mean over frames):', json.dumps(report['agreement_with_gt_at_score_0.5'], indent=1))
for variant, frames in report.get('inference', {}).items():
    print(variant)
    for name, r in frames.items():
        print(f"  {name}: GT={r['n_gt']}", {t: (v['n_det'], v['precision'], v['recall']) for t, v in r['by_threshold'].items()})
print('\nverdict inputs (facts only):', json.dumps(report['verdict_inputs'], indent=1))
'''

NOTE = r'''
## Đọc kết quả

- `loaded_strict=false` → thường là sai kiến trúc giả định (depth/width/num_classes) hoặc thiếu phụ thuộc; xem `error`, **không** suy ra checkpoint hỏng.
- Đạt về phát hiện = **precision và recall cao so với GT** (IoU 0.5) trên 9 khung, không phải "có box". Lần chạy đầu chỉ đếm box: 210 box trên khung có 7 GT, nên không chứng minh được gì. Hai kiểu tiền xử lý được chạy song song; `best_variant` là kiểu khớp GT hơn, và nếu cả hai đều kém thì checkpoint chưa dùng được theo cách nạp này.
- Cả 3 ngưỡng (0.3/0.5/0.7) được in: precision thấp ở 0.3 nhưng cao ở 0.5–0.7 là bình thường với detector cho tracker.
- `training_data_documented=false` (không có `exp`/`args` trong checkpoint) = chưa biết nó đã thấy val hay chưa → muốn dùng phải tra repo DanceTrack/ByteTrack exp file trước khi gọi val là "unseen".
- Gửi lại `yolox-checkpoint-smoke.json` (trong thư mục kết quả) để đóng câu hỏi nguồn (b).
'''


def build():
    source = SMOKE.read_text(encoding="utf-8")
    cells = [cell("markdown", INTRO), cell("code", SETUP),
             cell("code", EMBED.replace("{source!r}", repr(source))),
             cell("code", FRAME), cell("code", RUN), cell("markdown", NOTE)]
    notebook = dict(cells=cells, nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name="Python 3", language="python", name="python3"),
        language_info=dict(name="python"), colab=dict(provenance=[])))
    OUTPUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    return OUTPUT


if __name__ == "__main__":
    print(build())
