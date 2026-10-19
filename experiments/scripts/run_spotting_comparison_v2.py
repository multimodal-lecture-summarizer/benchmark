"""Sequential full frozen-test inference, supervised/resumable without score tuning."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

from experiments.scripts.spotting_candidate_contract import ROOT,canonical_sha,sha,verify_files
from experiments.scripts.spotting_runtime_binding import VENV,read_json,require,test_binding
from experiments.scripts.spotting_comparison_io_v2 import (
    CONTRACT,INFERENCE_CODE,OUT,RUNTIME,RUNTIME_SHA,commit,encode,load_checkpoints,materialize,progress,write_once,write_bytes_once,
)
from experiments.scripts.spotting_comparison_process import exclusive_lock,utc
from experiments.scripts.spotting_comparison_supervision_v2 import bound_progress,terminate_tree


def prepare():
    registry,_,snapshot=test_binding()
    require(sha(RUNTIME)==RUNTIME_SHA,'sealed runtime changed')
    sealed=read_json(RUNTIME);verify_files(sealed['snapshot'],ROOT)
    contract=read_json(CONTRACT)
    predecessor=ROOT/contract['predecessor']['path']
    require(sha(predecessor)==contract['predecessor']['sha256'],'technical predecessor receipt changed')
    require(contract['candidate_order']==[c['candidate_id'] for c in registry['candidates']],'analysis candidate order changed')
    frames=materialize()
    snapshot=dict(sealed['snapshot'])
    for path in [RUNTIME,CONTRACT,OUT/'input-manifest.json',predecessor,
                 predecessor.with_name('technical-aborted-notebook.ipynb')]+[Path(__file__).with_name(n) for n in INFERENCE_CODE]:
        snapshot[path.relative_to(ROOT).as_posix()]=sha(path)
    immutable=dict(schema='cvid_full_test_spotting_inference_identity_v1',snapshot=snapshot,
        selected_frames=len(frames),candidate_order=contract['candidate_order'],execution=contract['execution'])
    identity=dict(immutable,run_id=canonical_sha(immutable))
    write_once(OUT/'run-identity.json',identity)
    write_once(OUT/'analysis-contract.json',contract)
    return registry,identity,frames


def supervise(candidate,identity,frames,env):
    folder=OUT/candidate;folder.mkdir(exist_ok=True)
    completed=load_checkpoints(identity,frames,candidate)
    if len(completed)==len(frames) and (folder/'candidate-complete.json').exists():
        saved=read_json(folder/'candidate-complete.json')
        raw=folder/'predictions.jsonl';expected=b''.join(encode(completed[f['frame_id']]) for f in frames)
        require(saved['run_id']==identity['run_id'] and raw.read_bytes()==expected and sha(raw)==saved['prediction_sha256'],
                'cached completion/prediction identity changed')
        require(saved['committed_frames']==len(completed) and saved['successful_frames']==sum(r['status']=='ok' for r in completed.values())
                and saved['failed_frames']==sum(r['status']=='error' for r in completed.values()),'cached coverage changed')
        return saved
    require(not list((folder/'attempts').glob('*/systemic-failure.json')),'unresolved systemic predictor failure; investigate before resume')
    while True:
        attempt=folder/'attempts'/(utc().replace(':','-')+'-'+uuid.uuid4().hex[:8]);attempt.mkdir(parents=True)
        command=[str(VENV/'Scripts/python.exe'),'-s','-m','experiments.scripts.spotting_comparison_worker_v2',
                 '--candidate',candidate,'--attempt',str(attempt)]
        launch=time.time();last_report=-1;timed_out=None
        with (attempt/'stdout.txt').open('x',encoding='utf-8') as stdout,(attempt/'stderr.txt').open('x',encoding='utf-8') as stderr:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr)
            write_once(attempt/'launched.json',dict(pid=process.pid,started_at_utc=utc(),run_id=identity['run_id'],command=command))
            while process.poll() is None:
                path=folder/'progress.json'
                state=read_json(path) if path.exists() else {}
                state=bound_progress(state,identity,attempt)
                count=state.get('completed_frames',len(completed))
                if count!=last_report and (count%25==0 or count==len(frames)):
                    print(candidate,count,'/',len(frames),'state',state.get('state','starting'),flush=True);last_report=count
                phase_start=state.get('phase_started_unix',launch)
                cap=identity['execution']['frame_wall_seconds'] if state.get('state')=='forward' else identity['execution']['startup_finalization_wall_seconds']
                if time.time()-phase_start>cap:
                    termination=terminate_tree(process,state);timed_out=state
                    write_once(attempt/'timeout.json',dict(state=state,cap_seconds=cap,terminated_at_utc=utc(),termination=termination));break
                time.sleep(1)
            code=process.wait()
        write_once(attempt/'exit.json',dict(returncode=code,timed_out=timed_out is not None,finished_at_utc=utc()))
        if timed_out is not None:
            require(timed_out.get('state')=='forward','startup/finalization timeout; pending frames remain resumable')
            frame=next(f for f in frames if f['frame_id']==timed_out['frame_id'])
            latest=load_checkpoints(identity,frames,candidate)
            if frame['frame_id'] not in latest:
                record=dict(frame_id=frame['frame_id'],status='error',error='frame_timeout_600_seconds',predictions=[],
                    origin='supervisor_timeout',attempt_count=1,worker_pid=timed_out['pid'],wall_seconds=cap,completed_at_utc=utc(),
                    rss_bytes=None,process_peak_rss_bytes_to_date=None)
                commit(identity,frame,candidate,record)
            continue
        require(code==0 and (attempt/'worker-complete.json').exists(),
                'worker interrupted/failed; pending frames remain resumable, inspect '+str(attempt))
        records=load_checkpoints(identity,frames,candidate)
        require(len(records)==len(frames),'worker did not account for every frame')
        raw=folder/'predictions.jsonl'
        data=b''.join(encode(records[f['frame_id']]) for f in frames)
        write_bytes_once(raw,data)
        result=dict(run_id=identity['run_id'],candidate_id=candidate,selected_frames=len(frames),committed_frames=len(records),
            successful_frames=sum(r['status']=='ok' for r in records.values()),failed_frames=sum(r['status']=='error' for r in records.values()),
            predictor_attempt_records=sum(r['origin']=='predictor_attempt' for r in records.values()),
            timeout_records=sum(r['origin']=='supervisor_timeout' for r in records.values()),missing_records=0,
            prediction_sha256=sha(raw),completed_at_utc=utc(),worker_completion=str((attempt/'worker-complete.json').relative_to(ROOT)))
        write_once(folder/'candidate-complete.json',result);return result


def run_all():
    OUT.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(OUT/'execution.lock'):
        registry,identity,frames=prepare()
        env=dict(os.environ);env.update(registry['cpu_environment']);env.pop('PYTHONPATH',None);env['PYTHONNOUSERSITE']='1'
        rows=[]
        for candidate in identity['candidate_order']:
            print('Starting full cohort:',candidate,flush=True)
            rows.append(supervise(candidate,identity,frames,env))
        verify_files(identity['snapshot'],ROOT)
        result=dict(schema='cvid_full_test_spotting_inference_v1',run_id=identity['run_id'],candidates=rows,
            selected_frames=1754,committed_records=sum(r['committed_frames'] for r in rows),frame_inference_executed=True,
            completed_at_utc=utc(),snapshot=identity['snapshot'])
        if not (OUT/'inference-complete.json').exists(): write_once(OUT/'inference-complete.json',result)
        else:
            saved=read_json(OUT/'inference-complete.json')
            require(saved['run_id']==identity['run_id'] and saved['candidates']==rows and saved['snapshot']==identity['snapshot'],
                    'inference completion mismatch')
        return read_json(OUT/'inference-complete.json')


if __name__=='__main__': print(json.dumps(run_all(),ensure_ascii=False,indent=2))
