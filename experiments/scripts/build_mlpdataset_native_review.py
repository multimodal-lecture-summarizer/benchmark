"""Generate standalone cache-only native-frame Colab handoff; no source acquisition."""
import ast
import base64
import hashlib
import json
from pathlib import Path
import nbformat

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT/'benchmark/experiments/scripts'
REGISTRY = ROOT/'benchmark/experiments/registry/datasets'
TARGET = ROOT/'benchmark/experiments/notebooks/diagnostics/mlpdataset-native-review-colab.ipynb'
HELPERS = ['mlpdataset_targeted_media.py', 'mlpdataset_source_staging.py',
           'mlpdataset_targeted_review.py', 'mlpdataset_review_display.py', 'mlpdataset_native_review.py']


def build(queue_path=None, protocol_path=None, target=None):
    queue_path = Path(queue_path or REGISTRY/'mlpdataset-native-review-queue-v1.json')
    protocol_path = Path(protocol_path or REGISTRY/'mlpdataset-slide-transition-protocol-v1.json')
    queue = json.loads(queue_path.read_text(encoding='utf8'))
    protocol_bytes = protocol_path.read_bytes()
    assert hashlib.sha256(protocol_bytes).hexdigest() == queue['protocol_sha256']
    bundle = dict(queue=queue, protocol=json.loads(protocol_bytes), queue_sha256=hashlib.sha256(queue_path.read_bytes()).hexdigest(),
                  helper_sha256={name:hashlib.sha256((SCRIPTS/name).read_bytes()).hexdigest() for name in HELPERS})
    raw = json.dumps(bundle,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    cells = []
    def md(source):
        cells.append(nbformat.v4.new_markdown_cell(source))
    def code(source):
        ast.parse(source)
        cells.append(nbformat.v4.new_code_cell(source))
    md('''# MLPDataset — native-frame follow-up from existing cache

CPU only. Reads full source videos already in Drive; no downloads, installs, detector inference or raw label edits. Writes a separate sibling `<RUN_NAME>-native-review-v1`. Existing EDA and targeted-review caches remain read-only.

Native means **every temporal presentation frame**, resized to480px width for diagnosis. Each job has explicit source-bound half-open bounds and original-row/evidence bindings. Independent ffprobe PTS must exactly match extracted frames, including consecutive identical frames. A5s decode/probe tail handles packet reordering; only frames inside the requested exact window are retained.

Extraction readiness is not reviewed ground truth. Inspect old/new guards, fades/builds/returns and every event inside each window. Keep uncertain endpoint, repeated-label mapping and source-edge equivalence on HOLD. No midpoint timestamp is invented. Save this notebook with outputs for manual follow-up.''')
    code('''from pathlib import Path
import base64, hashlib, html, json, re, shutil
from IPython.display import HTML, display
RUN_NAME = '''+repr(queue['drive_run_name'])+''' #@param {type:"string"}
USE_GOOGLE_DRIVE = True #@param {type:"boolean"}
MAX_MINUTES = 60 #@param {type:"number"}
OUTPUT_GIB = 0.75 #@param {type:"number"}
FREE_FLOOR_GIB = 1.0 #@param {type:"number"}
STAGE_GIB = 2.0 #@param {type:"number"}
INLINE_MIB = 128 #@param {type:"number"}
assert re.fullmatch(r'[A-Za-z0-9_-]+', RUN_NAME)
assert 0 < MAX_MINUTES <= 240 and 0 < OUTPUT_GIB <= 8 and FREE_FLOOR_GIB > 0
assert 0 <= STAGE_GIB <= 8 and 0 < INLINE_MIB <= 512
if USE_GOOGLE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
    BASE = Path('/content/drive/MyDrive/MLPDataset_EDA')/RUN_NAME
else:
    BASE = Path.cwd()/RUN_NAME
assert BASE.is_dir(), 'Existing cache missing; no automatic download'
assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required; no automatic install'
REVIEW_ROOT = BASE.parent/(RUN_NAME+'-native-review-v1')
print('Read source cache:', BASE)
print('Separate output:', REVIEW_ROOT)
''')
    code('BUNDLE_BYTES = base64.b64decode('+repr(base64.b64encode(raw).decode())+')\nassert hashlib.sha256(BUNDLE_BYTES).hexdigest() == '+repr(hashlib.sha256(raw).hexdigest())+'''
BUNDLE = json.loads(BUNDLE_BYTES)
QUEUE, PROTOCOL = BUNDLE['queue'], BUNDLE['protocol']
assert RUN_NAME == QUEUE['drive_run_name'], 'Run identity changed'
print('Native jobs:', len(QUEUE['jobs']), '| Original marks:', len(QUEUE['original_queue']['cases']))
print('Protocol:', QUEUE['protocol_id'], '| Ledger SHA256:', QUEUE['review_ledger_sha256'])
''')
    md('## Embedded exact helpers\nThese cells run without a repository checkout. Helper hashes are retained in the bound bundle. Existing inventory and annotation-export hashes are verified before extraction; full source bytes are checked once per source per session and fingerprints checked on reuse.')
    for name in HELPERS:
        code((SCRIPTS/name).read_text(encoding='utf-8-sig'))
    code('''validated_inputs = validate_review_inputs(BASE, QUEUE['original_queue'])
print(json.dumps(validated_inputs, indent=2))
print(json.dumps(PROTOCOL, indent=2, ensure_ascii=False))
''')
    md('## Extract every native frame in every queued window\nAll original-row and job statuses are saved before processing, after every job and on interruption. A finite deadline, output quota and disk-free floor apply. Interrupted work stops and rethrows; completed checkpoints remain reusable after integrity validation. Staging is bounded RAM/local scratch and cleaned on exit.')
    code('''stager = PreviewSourceStager(max_bytes=int(STAGE_GIB*1024**3), enabled=STAGE_GIB>0)
runner = NativeReviewRunner(BASE, REVIEW_ROOT, QUEUE, max_minutes=MAX_MINUTES,
    max_bytes=OUTPUT_GIB*1024**3, min_free_bytes=FREE_FLOOR_GIB*1024**3,
    width=480, stage_getter=stager.get)
try:
    receipt = run_native_queue(runner)
finally:
    stager.close()
print('Saved all-job and all-original-row receipt:', REVIEW_ROOT/'native-review-receipt.json')
print(json.dumps(receipt['job_statuses'], indent=2))
''')
    md('## Inline native-frame galleries\nEvery retained frame has an exact integer PTS/timebase caption. All PNGs stay on disk. If the global inline JPEG-image budget (logs and captions excluded) is reached, every omitted image is explicitly represented by its PTS and retained path; display status becomes partial. Complete FFmpeg logs are collapsible. Extraction status stays separate from display status.')
    code('''display_state = dict(status='complete', jobs=[], payload_bytes=0)
try:
    for i, job in enumerate(QUEUE['jobs'], 1):
        result = receipt['results'].get(job['job_id'])
        if result is None:
            print('Not attempted:', job['job_id'])
            continue
        try:
            block, stats = render_native_job(job, result, REVIEW_ROOT,
                max(0, int(INLINE_MIB*1024**2)-display_state['payload_bytes']))
            display(HTML(block))
        except Exception as error:
            failed_frames = result.get('frames') if isinstance(result, dict) else None
            retained_count = len(failed_frames) if isinstance(failed_frames, list) else 0
            stats = dict(status='display_error', rendered_frames=0,
                retained_frames=retained_count, omitted_inline_frames=retained_count,
                payload_bytes=0, error=f'{type(error).__name__}: {error}'[:500])
            display_state['status'] = 'partial_display_errors'
            print('Display failed:', job['job_id'], stats['error'], flush=True)
        display_state['jobs'].append(dict(job_id=job['job_id'], **stats))
        display_state['payload_bytes'] += stats['payload_bytes']
        if stats['status'] == 'partial_display_budget' and display_state['status'] == 'complete':
            display_state['status'] = 'partial_display_budget'
        runner.checkpoint(REVIEW_ROOT, display_state, 'native-display-receipt.json')
        print(f"Gallery [{i}/{len(QUEUE['jobs'])}] {job['job_id']}: {stats}", flush=True)
except BaseException:
    display_state['status'] = 'interrupted'
    raise
finally:
    runner.checkpoint(REVIEW_ROOT, display_state, 'native-display-receipt.json')
''')
    md('## Manual decisions — HOLD until reviewed\nThe template preserves every original identity. Fill observations and event mappings after inspecting all events and endpoint guards. Source-edge footage alone does not establish source-edition equivalence. No annotation repair, native GT endpoint or eligible cohort is certified by this notebook.')
    code('''template = []
for row in QUEUE['original_queue']['cases']:
    template.append(dict(video_id=row['video_id'], original_row_index=row['annotation_index'],
        annotation_s=row['annotation_s'], annotation_sha256=row['annotation_sha256'],
        source_sha256=row['source_sha256'], protocol_sha256=QUEUE['protocol_sha256'],
        review_ledger_sha256=QUEUE['review_ledger_sha256'], reviewer='', observations='',
        original_to_event_mapping='', disposition='hold', native_point=None,
        native_evidence_status='unreviewed', evidence_paths_and_sha256=[]))
runner.checkpoint(REVIEW_ROOT, dict(rows=template, gt_status='pending', evaluation_ready=False),
                  'native-decisions-template.json')
print('Manual template:', len(template), 'rows; native endpoints remain null')
print('Save notebook with outputs. No automatic GT/cohort certification.')
''')
    notebook = nbformat.v4.new_notebook(cells=cells, metadata=dict(kernelspec=dict(display_name='Python3',language='python',name='python3'), language_info=dict(name='python')))
    nbformat.validate(notebook)
    destination = Path(target or TARGET)
    nbformat.write(notebook, destination)
    print(destination, 'cells=', len(cells), 'bytes=', destination.stat().st_size)
    return notebook


if __name__ == '__main__':
    build()
