"""Build a standalone, cache-only Colab follow-up; preserve the executed EDA."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import nbformat

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT/'benchmark/experiments/scripts'
REGISTRY = ROOT/'benchmark/experiments/registry/datasets'
TARGET = ROOT/'benchmark/experiments/notebooks/diagnostics/mlpdataset-targeted-review-colab.ipynb'


def build():
    queue_path = REGISTRY/'mlpdataset-targeted-review-queue-v1.json'
    protocol_path = REGISTRY/'mlpdataset-slide-transition-protocol-v1.json'
    queue = json.loads(queue_path.read_text(encoding='utf8'))
    protocol = json.loads(protocol_path.read_text(encoding='utf8'))
    media = {}
    for case in queue['cases']:
        evidence = case.get('historical_evidence')
        if evidence:
            path = ROOT/evidence['clip_local_path'];data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == evidence['clip_sha256']
            media[case['video_id']+':'+str(case['annotation_index'])] = base64.b64encode(data).decode('ascii')
    bundle = dict(queue=queue, protocol=protocol, historical_media=media,
                  queue_sha256=hashlib.sha256(queue_path.read_bytes()).hexdigest(),
                  protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest())
    raw = json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()
    payload = base64.b64encode(raw).decode('ascii')
    fingerprint = hashlib.sha256(raw).hexdigest()
    cells = []
    md = lambda s: cells.append(nbformat.v4.new_markdown_cell(s))
    code = lambda s: cells.append(nbformat.v4.new_code_cell(s))
    md('''# MLPDataset — rà soát có mục tiêu từ cache\n\nCPU đủ. Notebook này không tải video, không sửa annotation và không chạy lại EDA. Giữ Drive và `RUN_NAME=mlpdataset-eda-261017-v3`. Notebook EDA đã chạy được giữ nguyên.\n\nHàng đợi82mốc/42video/10nhóm:14clip±5s cũ đã khớp hash và có quan sát thô;20mốc biên nguồn giữ HOLD theo policy;48mốc cần ngữ cảnh mới. Mặc định chỉ trích48mốc còn thiếu. Kết quả mới ở thư mục riêng cạnh run gốc. Mỗi clip/ảnh/checkpoint có hash và thời gian PTS; thành công trích ảnh không tự chứng nhận nhãn.\n\nProtocol-v1 đã chốt quy tắc; GT/cohort vẫn chờ review. Preview0.25s không đủ chứng nhận frame cuối slide. Sau khi chạy, lưu notebook cùng outputs để tiếp tục đánh giá nội dung và quyết định các ca chưa rõ.''')
    code('''from pathlib import Path
import base64, hashlib, html, io, json, os, re, shutil, subprocess, time
from datetime import datetime, timezone
import pandas as pd
from IPython.display import display, Markdown, HTML
RUN_NAME = "mlpdataset-eda-261017-v3" #@param {type:"string"}
USE_GOOGLE_DRIVE = True #@param {type:"boolean"}
EXTRACT_NEW_CONTEXTS = True #@param {type:"boolean"}
REVIEW_EXTRA_KEYS = [] # Optional video_id:index keys for historical/edge re-extraction.
REVIEW_MAX_MINUTES = 60 #@param {type:"number"}
REVIEW_MAX_GB = 0.75 #@param {type:"number"}
MIN_FREE_GB = 1.0 #@param {type:"number"}
SOURCE_STAGE_GB = 2.0 #@param {type:"number"}
assert re.fullmatch(r'[A-Za-z0-9_-]+',RUN_NAME)
assert 0 < REVIEW_MAX_MINUTES <= 240 and 0 < REVIEW_MAX_GB <= 8 and MIN_FREE_GB > 0
assert 0 <= SOURCE_STAGE_GB <= 8
if USE_GOOGLE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
    BASE = Path('/content/drive/MyDrive/MLPDataset_EDA')/RUN_NAME
else:
    BASE = Path.cwd()/RUN_NAME
if not BASE.is_dir():
    raise FileNotFoundError('Existing run cache not found: '+str(BASE))
REVIEW_ROOT = BASE.parent/(RUN_NAME+'-targeted-review-v1')
assert shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg and ffprobe required; no automatic download.'
print('Read existing source cache:',BASE)
print('Write separate review artifacts:',REVIEW_ROOT)
''')
    code("BUNDLE_BYTES = base64.b64decode("+repr(payload)+")\nassert hashlib.sha256(BUNDLE_BYTES).hexdigest() == "+repr(fingerprint)+"\nBUNDLE = json.loads(BUNDLE_BYTES)\nQUEUE = BUNDLE['queue']; PROTOCOL = BUNDLE['protocol']\nassert PROTOCOL['status'] == 'rules_frozen' and not PROTOCOL['evaluation_ready']\nprint(json.dumps(dict(queue=QUEUE['summary'],protocol=PROTOCOL['protocol_id'],gt_status=PROTOCOL['gt_status']),indent=2))")
    md('## Helpers — kiểm tra nguồn, cache mới và thời gian PTS\nKhông dùng `IPython.Video(filename=...)`; MP4 được nhúng trực tiếp bằng HTML. Source staging dùng RAM/local có giới hạn; hết dung lượng thì đọc nguồn Drive.')
    for name in ['mlpdataset_targeted_media.py', 'mlpdataset_source_staging.py',
                 'mlpdataset_targeted_review.py', 'mlpdataset_review_display.py']:
        code((SCRIPTS/name).read_text(encoding='utf-8-sig'))
    md('## Kiểm tra toàn bộ inventory và ràng buộc đầu vào\nCần các export trong `analysis/` và `videos/<id>/state.json` từ EDA đã hoàn tất. Hash/ID thay đổi thì dừng rõ ràng; không tự tải lại hoặc bỏ kiểm tra.')
    code('''validated_inputs = validate_review_inputs(BASE,QUEUE)
REVIEW_ROOT.mkdir(parents=True,exist_ok=True)
print(json.dumps(validated_inputs,indent=2))
def review_table(rows,label):
    frame = rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    display(Markdown(f'**{label}: {len(frame)} rows**'))
    display(HTML('<div style="max-height:480px;overflow:auto">'+frame.to_html(index=False,max_rows=None,escape=True)+'</div>'))
case_by_key = {c['video_id']+':'+str(c['annotation_index']):c for c in QUEUE['cases']}
assert set(REVIEW_EXTRA_KEYS) <= set(case_by_key), 'Unknown review key'
queue_table = [dict(video_id=c['video_id'],index=c['annotation_index'],time_s=c['annotation_s'],group=c['group'],reasons='; '.join(c['reasons']),action=c['review_action'],new_context=c['requires_new_dense_context'],gt_disposition='hold') for c in QUEUE['cases']]
review_table(queue_table,'Full targeted queue; zero inventory exclusions')
print(json.dumps(PROTOCOL,indent=2,ensure_ascii=False))
''')
    md('## 14 clip lịch sử đã xác minh\nCác clip được nhúng sẵn, khớp source/annotation/clip hash của snapshot EDA hiện tại. Quan sát thô chỉ xác nhận ngữ cảnh, không phải điểm GT ở độ phân giải frame gốc. Không trích lại các clip này theo mặc định.')
    code('''historical_rows = []
for key,case in case_by_key.items():
    evidence = case.get('historical_evidence')
    if not evidence:continue
    clip = base64.b64decode(BUNDLE['historical_media'][key])
    video = video_html(clip,evidence['clip_sha256'])
    info = dict(key=key,annotation_s=case['annotation_s'],event_observation=evidence['event_observation'],window=evidence['measured_window'],timing_status=evidence['timing_status'],gt_disposition='hold')
    historical_rows.append(info)
    display(HTML('<details><summary>'+html.escape(key+' — '+evidence['event_observation'])+'</summary><pre>'+html.escape(json.dumps(info,indent=2))+'</pre>'+video+'</details>'))
review_table(historical_rows,'Historical coarse observations, not corrected GT')
''')
    md('## Trích ±5 giây cho ngữ cảnh còn thiếu\nChỉ48mốc cần ảnh mới theo mặc định. Cache của lượt review này được xác minh rồi tái sử dụng khi chạy lại. Tiến trình từng mốc và mọi lỗi đều hiện rõ. Receipt lưu trước gallery; dừng chạy vẫn giữ checkpoint đã hoàn tất.')
    code('''selected_cases = [c for c in QUEUE['cases'] if (EXTRACT_NEW_CONTEXTS and c['requires_new_dense_context']) or c['video_id']+':'+str(c['annotation_index']) in REVIEW_EXTRA_KEYS]
stager = PreviewSourceStager(max_bytes=int(SOURCE_STAGE_GB*1024**3),enabled=SOURCE_STAGE_GB>0)
runner = ReviewRunner(BASE,REVIEW_ROOT,max_minutes=REVIEW_MAX_MINUTES,max_bytes=REVIEW_MAX_GB*1024**3,min_free_bytes=MIN_FREE_GB*1024**3,stage_getter=stager.get)
results = {}
selected_keys = {c['video_id']+':'+str(c['annotation_index']) for c in selected_cases}
def save_run_receipt(display_summary=None):
    all_case_statuses=[]
    for key,case in case_by_key.items():
        value=results.get(key)
        state=value['status'] if value else ('not_attempted' if key in selected_keys else case['review_action'])
        all_case_statuses.append(dict(key=key,group=case['group'],action=case['review_action'],selected_for_extraction=key in selected_keys,extraction_status=state,frames=len(value.get('frames',[])) if value else 0,error=value.get('error','') if value else '',gt_disposition='hold'))
    receipt = dict(all_case_statuses=all_case_statuses,schema_version=1,queue_id=QUEUE['queue_id'],queue_sha256=BUNDLE['queue_sha256'],protocol_sha256=BUNDLE['protocol_sha256'],input_notebook_sha256=QUEUE['input_notebook_sha256'],observed_at_utc=datetime.now(timezone.utc).isoformat(),inventory=QUEUE['inventory'],queue_summary=QUEUE['summary'],selected_for_extraction=len(selected_cases),results=results,runner=runner.stats(),source_staging=stager.stats(),historical_contexts=len(historical_rows),annotation_repairs_applied=0,semantic_certified_events=0,gt_status='pending',cohort_status='pending',evaluation_ready=False,display=display_summary or dict(status='pending_after_receipt'))
    save_review_json(REVIEW_ROOT/'review-receipt.json',receipt)
    return receipt
try:
    for position,case in enumerate(selected_cases,1):
        key = case['video_id']+':'+str(case['annotation_index'])
        print(f'Review [{position}/{len(selected_cases)}] {key}',flush=True)
        value = runner.run_case(case);results[key]=value
        save_run_receipt()
        print('  '+value['status']+'; frames='+str(len(value.get('frames',[]))),flush=True)
        if value['status']=='interrupted':raise KeyboardInterrupt('Review interrupted; completed checkpoints retained')
        if value['status']=='deadline':break
finally:
    stager.close()
    review_receipt=save_run_receipt()
print('Extraction receipt saved before gallery:',REVIEW_ROOT/'review-receipt.json')
status_rows=review_receipt['all_case_statuses']
review_table(status_rows,'All82case statuses; extraction readiness is not GT acceptance')
''')
    md('## Ảnh và video mới — mở từng mốc để xem\nHiển thị tất cả frame được chọn, kèm PTS gốc và offset; không tự chọn điểm có chuyển động lớn làm nhãn. Lỗi hiển thị được ghi riêng, không làm mất kết quả trích ảnh.')
    code('''display_summary = dict(status='complete',cases=0,rendered_frames=0,display_failures=0)
try:
    for key,value in results.items():
        try:
            block,stats = render_review_case(case_by_key[key],value,REVIEW_ROOT)
            display(HTML(block))
            display_summary['cases']+=1
            for field in ['rendered_frames','display_failures']:display_summary[field]+=stats[field]
        except Exception as error:
            display_summary['display_failures']+=1
            print('Presentation failed for',key,type(error).__name__,str(error)[:200])
        print('Gallery:',display_summary['cases'],'/',len(results),'cases;',display_summary['rendered_frames'],'frames',flush=True)
except BaseException:
    display_summary['status']='interrupted_after_receipt'
    raise
finally:
    review_receipt=save_run_receipt(display_summary)
''')
    md('## Hồ sơ review và điều kiện bước tiếp theo\nGT/cohort vẫn HOLD cho đến khi quyết định sự kiện và endpoint có bằng chứng frame gốc. Cửa sổ0.25s hỗ trợ phân loại/ngữ cảnh; nếu chưa rõ thì giữ bracket/HOLD, không lấy midpoint hoặc cộng bù timestamp hàng loạt. Không chạy detector để quyết định sửa GT.')
    code('''template=[]
for key,case in case_by_key.items():
    template.append(dict(protocol_id=PROTOCOL['protocol_id'],protocol_sha256=BUNDLE['protocol_sha256'],video_id=case['video_id'],source_sha256=case['source_sha256'],annotation_sha256=case['annotation_sha256'],original_row_index=case['annotation_index'],released_time_sec=case['annotation_s'],reviewer='',reviewed_at='',event_class='',disposition='hold',reason='native_endpoint_or_policy_pending',confidence='',native_evidence_status='unreviewed',pts_time_base_and_origin='',point_or_bracket='',effect_fields='',evidence_paths_and_sha256='',original_to_reviewed_event_mapping=''))
pd.DataFrame(template).to_csv(REVIEW_ROOT/'review-decisions-template.csv',index=False)
review_table(template,'Decision template, deliberately not approved labels')
print(json.dumps(review_receipt,indent=2,ensure_ascii=False))
display(Markdown('**Save this notebook with outputs. Không ZIP, không tải lại nguồn, không sửa annotation. Protocol rules đã frozen; semantic GT và cohort chưa frozen.**'))
''')
    notebook=nbformat.v4.new_notebook(cells=cells,metadata=dict(kernelspec=dict(display_name='Python3',language='python',name='python3'),language_info=dict(name='python')))
    for cell in cells:
        if cell.cell_type=='code':ast.parse(cell.source)
    nbformat.validate(notebook)
    nbformat.write(notebook,TARGET)
    print(TARGET.relative_to(ROOT),'cells=',len(cells),'bytes=',TARGET.stat().st_size)
    return notebook


if __name__=='__main__':
    build()
