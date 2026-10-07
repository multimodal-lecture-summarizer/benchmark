"""Build a resumable, full-validation VISTA source materialization notebook."""

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


def md(source: str):
    return nbf.v4.new_markdown_cell(dedent(source).strip())


def code(source: str):
    return nbf.v4.new_code_cell(dedent(source).strip())


cells = [
    md("""
    # VISTA RQ2 — tạo đầu vào từ toàn bộ validation trên Colab T4

    Notebook này nhắm tới **toàn bộ 1.859 video validation**, không dừng ở 40 video EDA. Mỗi video được lấy đúng revision, chạy ASR đầy đủ bằng Whisper `small.en`, lấy khung hình mỗi 30 giây, rồi ghi checkpoint vào Drive. File MP4 mới chỉ lưu tạm trên máy Colab và được xóa sau khi trích xuất; 40 MP4 đã tải trong `MyDrive/VISTA_EDA/videos/val` được dùng lại. Khi Colab ngắt, chạy lại notebook để tiếp tục.

    **Cách chạy:** chọn Runtime → T4 GPU; thêm Colab Secret `HF_TOKEN` từ tài khoản đã được VISTA cấp quyền; Run all. Giữ cùng cấu hình và Drive qua các phiên. Mỗi phiên chạy tối đa `MAX_HOURS_PER_RUN`, sau đó tự dừng. Đây là bước tạo nguồn cho RQ2; **chưa sinh hoặc chấm tóm tắt**. Chỉ đọc validation, không mở test. Transcript và keyframe là tín hiệu máy tạo, không phải nhãn chuẩn.

    [VISTA dataset card](https://huggingface.co/datasets/dongqi-me/VISTA/blob/main/README.md) · [Hugging Face download API](https://huggingface.co/docs/huggingface_hub/package_reference/file_download) · [Whisper](https://github.com/openai/whisper)
    """),
    code("""
    %pip -q install -U huggingface_hub pandas opencv-python-headless openai-whisper==20250625
    import shutil, torch
    assert shutil.which('ffprobe') and shutil.which('ffmpeg'), 'Colab cần FFmpeg'
    assert torch.cuda.is_available(), 'Chọn T4 GPU trước khi chạy'
    print('GPU:', torch.cuda.get_device_name(0))
    """),
    code("""
    from pathlib import Path
    from getpass import getpass
    from google.colab import drive
    from huggingface_hub import HfApi, hf_hub_download
    import hashlib, importlib.metadata, json, os, re, subprocess, time, zipfile
    import pandas as pd
    from IPython.display import display

    REPO_ID='dongqi-me/VISTA'
    EXPECTED_REVISION='39c60afff185fbefe80b685898cf073da0fd92ab'
    ASR_MODEL='small.en'
    FRAME_INTERVAL_S=30
    FRAME_WIDTH=640
    MAX_FRAMES_PER_VIDEO=40
    MAX_HOURS_PER_RUN=4.5   # 0 = không đặt giới hạn thời gian
    MAX_VIDEOS_PER_RUN=0    # 0 = không đặt giới hạn số video
    MIN_DURATION_S=30       # chỉ loại tệp rất ngắn như mẫu 3 giây
    RETRY_FAILED=True

    drive.mount('/content/drive')
    ROOT=Path('/content/drive/MyDrive/VISTA_RQ2_SOURCE_1859')
    PRIOR_MEDIA=Path('/content/drive/MyDrive/VISTA_EDA/videos/val')
    ROOT.mkdir(parents=True,exist_ok=True)
    try:
        from google.colab import userdata
        token=userdata.get('HF_TOKEN')
    except Exception:
        token=None
    if not token: token=getpass('HF_TOKEN: ')
    assert token, 'Thiếu HF_TOKEN'
    api=HfApi(token=token)
    print('HF account:',api.whoami(token=token)['name'])
    revision=api.repo_info(REPO_ID,repo_type='dataset',token=token).sha
    assert revision==EXPECTED_REVISION, f'VISTA revision đổi: {revision}; kiểm tra trước khi trộn kết quả'
    recipe={'dataset':REPO_ID,'revision':revision,'split':'val','asr_model':ASR_MODEL,
            'frame_interval_s':FRAME_INTERVAL_S,'frame_width':FRAME_WIDTH,
            'max_frames_per_video':MAX_FRAMES_PER_VIDEO,'min_duration_s':MIN_DURATION_S}
    recipe_hash=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()[:12]
    OUT=ROOT/f'source_{recipe_hash}'
    TRANSCRIPTS=OUT/'transcripts'; FRAMES=OUT/'frames'
    for directory in (OUT,TRANSCRIPTS,FRAMES): directory.mkdir(parents=True,exist_ok=True)
    (OUT/'recipe.json').write_text(json.dumps(recipe,indent=2)+'\\n',encoding='utf-8')
    print('Output:',OUT)
    """),
    md("""## 1. Ghim toàn bộ validation và lập thứ tự xử lý đa dạng

    Danh sách 1.859 bản ghi được lấy từ `val.json` tại revision đã ghim. Thứ tự xử lý xoay vòng theo venue để các phiên đầu vẫn có nhiều chủ đề; mục tiêu cuối là xử lý **tất cả** bản ghi, không chỉ mẫu cân bằng. Abstract được lưu riêng ở metadata, không đưa vào ASR hoặc khung hình.
    """),
    code("""
    metadata_path=hf_hub_download(REPO_ID,'val.json',repo_type='dataset',revision=revision,token=token)
    raw=Path(metadata_path).read_bytes()
    metadata_sha256=hashlib.sha256(raw).hexdigest()
    target_metadata=OUT/'val_metadata.json'
    if not target_metadata.exists(): target_metadata.write_bytes(raw)
    else: assert hashlib.sha256(target_metadata.read_bytes()).hexdigest()==metadata_sha256
    obj=json.loads(raw)
    if isinstance(obj,list): records=obj
    elif isinstance(obj,dict) and isinstance(obj.get('data'),list): records=obj['data']
    else: raise ValueError('Cấu trúc val.json khác dự kiến; chưa xử lý media')
    val=pd.DataFrame(records)
    assert len(val)==1859 and {'id','video_file','venue'}.issubset(val.columns)
    val['video_file']=val.video_file.astype(str).map(lambda s:Path(s).name)
    assert val.id.is_unique and val.video_file.is_unique
    val['venue_group']=val.venue.fillna('unknown').astype(str)
    val['order_key']=val.id.astype(str).map(lambda s:hashlib.sha256(s.encode()).hexdigest())
    buckets={k:g.sort_values('order_key').to_dict('records') for k,g in val.groupby('venue_group')}
    ordered=[]
    while any(buckets.values()):
        for venue in sorted(buckets):
            if buckets[venue]: ordered.append(buckets[venue].pop(0))
    assert len(ordered)==len(val)
    order=pd.DataFrame(ordered)[['id','video_file','venue_group']]
    order['hub_path']='videos/val/'+order.video_file
    files={item.path:item for item in api.list_repo_tree(REPO_ID,path_in_repo='videos/val',
        repo_type='dataset',revision=revision,token=token) if hasattr(item,'size')}
    order['expected_bytes']=order.hub_path.map(lambda p:files[p].size if p in files else None)
    assert order.expected_bytes.notna().all(), 'Thiếu MP4 trong revision đã ghim'
    order.to_csv(OUT/'all_validation_order.csv',index=False)
    display(val.venue_group.value_counts().head(25).to_frame('records'))
    print('Validation:',len(val),'| venues:',val.venue_group.nunique(),
          '| metadata SHA256:',metadata_sha256)
    """),
    md("""## 2. Tải, ASR và khung hình có checkpoint

    Kết quả từng video được ghi ngay sau khi xử lý. `receipts.csv` giữ cả thất bại; chạy lại sẽ thử lại thất bại và bỏ qua tệp đã hoàn thành. Bộ nhớ Colab chỉ giữ một MP4 mới mỗi lần. Không cần tải lại 40 video EDA nếu chúng còn ở Drive.
    """),
    code("""
    import cv2, whisper
    model=whisper.load_model(ASR_MODEL,device='cuda')
    print('Whisper:',importlib.metadata.version('openai-whisper'))
    TEMP=Path('/content/vista_validation_temp')
    TEMP.mkdir(parents=True,exist_ok=True)
    receipts_path=OUT/'receipts.csv'
    if receipts_path.exists():
        old=pd.read_csv(receipts_path,dtype={'id':str}).fillna('')
        receipts={str(row['id']):row for row in old.to_dict('records')}
    else: receipts={}
    started=time.monotonic(); attempted=0

    def atomic_json(path, value):
        tmp=path.with_suffix(path.suffix+'.tmp')
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
        os.replace(tmp,path)

    def save_receipts():
        columns=['id','video_file','venue_group','status','source','duration_s',
            'expected_bytes','actual_bytes','asr_segments','asr_words','frames',
            'seconds','error_type','recipe_hash']
        frame=pd.DataFrame(receipts.values()).reindex(columns=columns)
        tmp=receipts_path.with_suffix('.tmp')
        frame.to_csv(tmp,index=False)
        os.replace(tmp,receipts_path)

    def media_info(path):
        proc=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams',
            '-of','json',str(path)],capture_output=True,text=True,timeout=90,check=True)
        data=json.loads(proc.stdout)
        video=next((s for s in data['streams'] if s['codec_type']=='video'),None)
        audio=next((s for s in data['streams'] if s['codec_type']=='audio'),None)
        if not video or not audio: raise ValueError('missing_video_or_audio_stream')
        return float(data['format']['duration'])

    def extract_frames(path, target, duration):
        cap=cv2.VideoCapture(str(path))
        if not cap.isOpened(): raise RuntimeError('opencv_video_open_failed')
        count=0; frame_rows=[]
        tmp=target.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED) as archive:
                for second in range(0,min(int(duration),FRAME_INTERVAL_S*MAX_FRAMES_PER_VIDEO),FRAME_INTERVAL_S):
                    cap.set(cv2.CAP_PROP_POS_MSEC,second*1000)
                    ok,frame=cap.read()
                    if not ok: continue
                    height,width=frame.shape[:2]
                    frame=cv2.resize(frame,(FRAME_WIDTH,round(height*FRAME_WIDTH/width)))
                    ok,jpg=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,82])
                    if not ok: continue
                    name=f'{second:05d}s.jpg'
                    archive.writestr(name,jpg.tobytes())
                    frame_rows.append({'file':name,'requested_seconds':second,
                        'decoded_seconds':round(float(cap.get(cv2.CAP_PROP_POS_MSEC))/1000,3)})
                    count+=1
                archive.writestr('frames.json',json.dumps(frame_rows))
            if not count: raise RuntimeError('no_decodable_frames')
            os.replace(tmp,target)
        finally:
            cap.release()
            tmp.unlink(missing_ok=True)
        return count

    for row in order.itertuples(index=False):
        if MAX_HOURS_PER_RUN and (time.monotonic()-started)>MAX_HOURS_PER_RUN*3600: break
        if MAX_VIDEOS_PER_RUN and attempted>=MAX_VIDEOS_PER_RUN: break
        record=receipts.get(str(row.id),{})
        transcript_path=TRANSCRIPTS/f'{row.id}.json'
        frames_path=FRAMES/f'{row.id}.zip'
        if (record.get('status')=='complete' and transcript_path.exists() and frames_path.exists()
            and record.get('recipe_hash')==recipe_hash): continue
        if record.get('status')=='too_short': continue
        if record.get('status')=='failed' and not RETRY_FAILED: continue
        attempted+=1; item_start=time.monotonic(); temp_path=None
        result={'id':str(row.id),'video_file':row.video_file,'venue_group':row.venue_group,
            'status':'failed','source':'','duration_s':'','expected_bytes':int(row.expected_bytes),
            'actual_bytes':'','asr_segments':'','asr_words':'','frames':'',
            'seconds':'','error_type':'','recipe_hash':recipe_hash}
        try:
            existing=PRIOR_MEDIA/row.video_file
            if existing.exists():
                path=existing; result['source']='prior_drive_media'
            else:
                path=Path(hf_hub_download(REPO_ID,row.hub_path,repo_type='dataset',
                    revision=revision,token=token,local_dir=TEMP))
                temp_path=path; result['source']='hub_temporary'
            result['actual_bytes']=path.stat().st_size
            if result['actual_bytes']!=result['expected_bytes']:
                raise ValueError('media_size_mismatch')
            duration=media_info(path); result['duration_s']=round(duration,2)
            if duration<MIN_DURATION_S:
                result['status']='too_short'
            else:
                if transcript_path.exists():
                    try:
                        prior=json.loads(transcript_path.read_text(encoding='utf-8'))
                        assert prior['recipe_hash']==recipe_hash and prior['id']==str(row.id)
                    except (ValueError,KeyError,AssertionError):
                        transcript_path.unlink()
                if not transcript_path.exists():
                    asr=model.transcribe(str(path),language='en',fp16=True,verbose=False,
                        temperature=0.0,condition_on_previous_text=False)
                    segments=[{'start':round(float(s['start']),2),'end':round(float(s['end']),2),
                        'text':str(s['text']).strip()} for s in asr['segments'] if str(s['text']).strip()]
                    atomic_json(transcript_path,{'id':str(row.id),'video_file':row.video_file,
                        'dataset_revision':revision,'recipe_hash':recipe_hash,'duration_s':duration,
                        'asr_model':ASR_MODEL,'language':asr.get('language'),'segments':segments,
                        'text':' '.join(s['text'] for s in segments)})
                transcript=json.loads(transcript_path.read_text(encoding='utf-8'))
                assert transcript['recipe_hash']==recipe_hash and transcript['id']==str(row.id)
                result['asr_segments']=len(transcript['segments'])
                result['asr_words']=len(transcript['text'].split())
                if frames_path.exists():
                    try:
                        with zipfile.ZipFile(frames_path) as archive:
                            assert archive.testzip() is None
                            result['frames']=len([n for n in archive.namelist() if n.endswith('.jpg')])
                            assert result['frames']>0
                    except (zipfile.BadZipFile,AssertionError):
                        frames_path.unlink()
                if not frames_path.exists():
                    result['frames']=extract_frames(path,frames_path,duration)
                result['status']='complete'
        except Exception as exc:
            # Do not store exception strings: signed CDN URLs can appear in them.
            result['error_type']=type(exc).__name__
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            result['seconds']=round(time.monotonic()-item_start,1)
            receipts[str(row.id)]=result
            save_receipts()
            print(f'{attempted} | {row.id} | {row.venue_group} | {result["status"]} | '
                  f'{result["seconds"]} s',flush=True)
    print('Processed this session:',attempted,'| receipt:',receipts_path)
    """),
    md("""## 3. Độ phủ thực tế sau mỗi phiên

    Bảng này tách **đã hoàn thành**, **quá ngắn**, **lỗi**, **chưa thử**; không thay mẫu thiếu bằng mẫu khác. Báo cáo venue giúp biết các phiên đầu đã phủ những nhóm nào. Chạy lại notebook cho đến khi `remaining == 0` hoặc xem lỗi để quyết định xử lý.
    """),
    code("""
    progress=order.merge(pd.read_csv(receipts_path,dtype={'id':str})[['id','status','asr_words','frames']],
        on='id',how='left') if receipts_path.exists() else order.assign(status=None)
    progress['status']=progress.status.fillna('not_run')
    display(progress.status.value_counts().to_frame('videos'))
    display(pd.crosstab(progress.venue_group,progress.status).sort_index())
    completed=int(progress.status.eq('complete').sum())
    remaining=int(progress.status.isin(['not_run','failed']).sum())
    print(f'Hoàn thành {completed}/{len(progress)}; cần tiếp tục/thử lại {remaining}; quá ngắn '
          f'{int(progress.status.eq("too_short").sum())}')
    progress.to_csv(OUT/'coverage.csv',index=False)
    """),
]

notebook=nbf.v4.new_notebook(cells=cells)
notebook.metadata.update({
    "kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},
    "language_info":{"name":"python"},
    "colab":{"name":"vista-validation-source-full-colab.ipynb","provenance":[]},
    "accelerator":"GPU",
})
target=Path(__file__).resolve().parents[1]/'notebooks'/'diagnostics'/'vista-validation-source-full-colab.ipynb'
target.parent.mkdir(parents=True,exist_ok=True)
nbf.write(notebook,target)
print(target)
