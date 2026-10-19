"""Immutable, identity-bound per-frame checkpoints and exact source materialization."""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import zipfile

from experiments.scripts.spotting_candidate_contract import ROOT,canonical_sha,sha
from experiments.scripts.spotting_runtime_binding import TEST,NAME,require,read_json

OUT=ROOT/'experiments/outputs/cvid-test-spotting-261014'
CONTRACT=TEST/'iiit-cvid-test-spotting-analysis-261014.json'
RUNTIME=TEST/'iiit-cvid-spotting-test-runtime-261014.json'
RUNTIME_SHA='475a72e185716f05645d35a01ff2964c141370dfae9583b3dccc162a8c304d70'
INFERENCE_CODE=['spotting_comparison_io.py','spotting_comparison_process.py','spotting_comparison_runtime.py',
                'spotting_comparison_worker.py','run_spotting_comparison.py']


def encode(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')


def publish_pending(temp,path):
    # Windows rename is atomic and refuses an existing target; no hard-link privilege needed.
    if os.name=='nt': os.rename(temp,path)
    else:
        os.link(temp,path);temp.unlink()


def write_once(path,value):
    write_bytes_once(path,encode(value))


def write_bytes_once(path,data):
    """Exclusive atomic publish cannot overwrite an existing checkpoint."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        require(path.read_bytes()==data,'existing immutable artifact differs: '+str(path));return
    temp=path.with_name(path.name+'.pending-'+uuid.uuid4().hex)
    with temp.open('xb') as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())
    try:
        publish_pending(temp,path)
    except FileExistsError:
        require(path.read_bytes()==data,'concurrent checkpoint differs')
    except OSError:
        # Preserve complete pending bytes for recovery; do not re-infer to replace them.
        raise
    if temp.exists(): temp.unlink()


def progress(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.progress-'+uuid.uuid4().hex)
    temp.write_bytes(encode(value))
    for attempt in range(10):
        try: os.replace(temp,path);return
        except PermissionError:
            if attempt==9: raise
            time.sleep(.025)


def checkpoint_path(candidate,frame_id):
    relative=Path(frame_id+'.json')
    require(not relative.is_absolute() and '..' not in relative.parts and frame_id.startswith('Frames/test/'),'unsafe frame ID')
    return OUT/candidate/'records'/relative


def validate_checkpoint(checkpoint,identity,frame,candidate):
    record=checkpoint['record']
    require(checkpoint['run_id']==identity['run_id'] and checkpoint['candidate_id']==candidate and
            checkpoint['image_sha256']==frame['image_sha256'] and record['frame_id']==frame['frame_id'],'checkpoint identity mismatch')
    require(checkpoint['record_sha256']==canonical_sha(record),'checkpoint payload digest mismatch')
    require(record['status'] in ('ok','error') and isinstance(record['predictions'],list),'malformed frame record')
    if record['status']=='error':
        require(not record['predictions'] and isinstance(record.get('error'),str) and record['error'].strip(),'invalid failure record')
    else: require(record.get('error') is None,'successful frame carries an error')
    for pred in record['predictions']:
        require(isinstance(pred,dict) and isinstance(pred.get('text'),str),'malformed prediction text')
    return record


def load_checkpoints(identity,frames,candidate):
    known={f['frame_id']:f for f in frames};records={}
    folder=OUT/candidate/'records'
    for pending in sorted(folder.rglob('*.json.pending-*')) if folder.exists() else []:
        item=read_json(pending);ident=item['record']['frame_id']
        require(ident in known,'pending checkpoint outside cohort')
        validate_checkpoint(item,identity,known[ident],candidate)
        target=checkpoint_path(candidate,ident)
        if target.exists(): require(target.read_bytes()==pending.read_bytes(),'pending/committed disagreement')
        else: publish_pending(pending,target)
        if pending.exists(): pending.unlink()
    for path in sorted(folder.rglob('*.json')) if folder.exists() else []:
        item=read_json(path);ident=item['record']['frame_id']
        require(ident in known and ident not in records,'extra or duplicate checkpoint ID')
        require(path.resolve()==checkpoint_path(candidate,ident).resolve(),'checkpoint path/ID mismatch')
        records[ident]=validate_checkpoint(item,identity,known[ident],candidate)
    return records


def commit(identity,frame,candidate,record):
    item=dict(run_id=identity['run_id'],candidate_id=candidate,image_sha256=frame['image_sha256'],
              record_sha256=canonical_sha(record),record=record)
    validate_checkpoint(item,identity,frame,candidate)
    write_once(checkpoint_path(candidate,frame['frame_id']),item)


def materialize():
    require(sha(RUNTIME)==RUNTIME_SHA,'sealed runtime changed')
    manifest=read_json(TEST/(NAME+'-cohort.json'))
    frames=[]
    with zipfile.ZipFile(ROOT/'research-data/iiit-cvid-source/IIIT-CVid.zip') as archive:
        for source in manifest['frames']:
            if not source['selected']: continue
            relative='inputs/'+source['frame_id'];path=OUT/relative
            raw=archive.read(source['archive_image_member'])
            require(hashlib.sha256(raw).hexdigest()==source['image_sha256'],'source PNG hash mismatch')
            path.parent.mkdir(parents=True,exist_ok=True)
            write_bytes_once(path,raw)
            frames.append({**{k:source[k] for k in ('frame_id','course','source_group','width','height','image_sha256')},'input_relative_path':relative})
    require(len(frames)==1754,'inference manifest count changed')
    write_once(OUT/'input-manifest.json',frames)
    return frames
