"""Actual full-frame inference in the frozen candidate venv; resumable checkpoints."""
import argparse
import os
from pathlib import Path
import time
import traceback

from experiments.scripts.spotting_candidate_contract import ROOT,canonical_sha,sha,verify_files
from experiments.scripts.spotting_candidate_adapters import frame_record
from experiments.scripts.spotting_runtime_binding import read_json,require
from experiments.scripts.spotting_runtime_guard import deny_network
from experiments.scripts.spotting_comparison_io import OUT,RUNTIME,commit,load_checkpoints,progress,write_once
from experiments.scripts.spotting_comparison_process import exclusive_lock,memory,utc
from experiments.scripts.spotting_comparison_runtime import load_for_inference,verify_after


def systemic_failure(recent,record,limit):
    if record['status']=='ok': recent.clear();return False
    recent.append(record['error']);del recent[:-limit]
    return len(recent)==limit and len(set(recent))==1


def run(candidate_id,attempt):
    identity=read_json(OUT/'run-identity.json');frames=read_json(OUT/'input-manifest.json')
    verify_files(identity['snapshot'],ROOT)
    records=load_checkpoints(identity,frames,candidate_id)
    initial=len(records);new_count=0;started=time.perf_counter()
    location=OUT/candidate_id/'progress.json'
    base=dict(candidate_id=candidate_id,pid=os.getpid(),run_id=identity['run_id'],selected_frames=len(frames),resumed_frames=initial)
    progress(location,dict(base,state='initializing',phase_started_unix=time.time(),completed_frames=initial,updated_at_utc=utc()))
    with exclusive_lock(OUT/candidate_id/'worker.lock'),deny_network() as network:
        predictor,candidate,runtime,basic=load_for_inference(candidate_id,read_json(RUNTIME))
        require(not network,'network attempted during loading')
        write_once(attempt/'loaded-runtime.json',dict(runtime_identity_sha256=canonical_sha(runtime),identity=runtime,basic=basic))
        load_seconds=time.perf_counter()-started
        recent=[]
        for frame in frames:
            ident=frame['frame_id']
            if ident in records: continue
            path=OUT/frame['input_relative_path']
            require(sha(path)==frame['image_sha256'],'inference image changed before use')
            progress(location,dict(base,state='forward',frame_id=ident,phase_started_unix=time.time(),
                completed_frames=len(records),new_frames=new_count,updated_at_utc=utc()))
            trace={}
            def observed_predict(source):
                try: return predictor(source)
                except Exception:
                    trace['traceback']=traceback.format_exc();raise
            clock=time.perf_counter()
            record=frame_record(ident,path,observed_predict)
            record.update(wall_seconds=time.perf_counter()-clock,completed_at_utc=utc(),
                          origin='predictor_attempt',attempt_count=1,worker_pid=os.getpid(),**memory())
            if trace: record['traceback']=trace['traceback']
            require(sha(path)==frame['image_sha256'],'inference image changed during use')
            require(not network,'network attempted during inference')
            commit(identity,frame,candidate_id,record);records[ident]=record;new_count+=1
            progress(location,dict(base,state='between_frames',phase_started_unix=time.time(),completed_frames=len(records),
                successful_frames=sum(r['status']=='ok' for r in records.values()),failed_frames=sum(r['status']=='error' for r in records.values()),
                new_frames=new_count,updated_at_utc=utc(),last_frame_id=ident,last_wall_seconds=record['wall_seconds']))
            if systemic_failure(recent,record,identity['execution']['systemic_identical_model_exceptions']):
                write_once(attempt/'systemic-failure.json',dict(frame_id=ident,error=record['error'],
                    committed_frames=len(records),pending_frames=len(frames)-len(records),run_id=identity['run_id']))
                raise RuntimeError('three consecutive identical predictor errors; stop for technical investigation')
            if len(records)%25==0 or len(records)==len(frames):
                print(candidate_id,len(records),'/',len(frames),'failures',sum(r['status']=='error' for r in records.values()),flush=True)
        progress(location,dict(base,state='finalizing',phase_started_unix=time.time(),completed_frames=len(records),updated_at_utc=utc()))
        verify_after(candidate,predictor,runtime);verify_files(identity['snapshot'],ROOT)
        require(not network,'network attempted during final verification')
        result=dict(candidate_id=candidate_id,run_id=identity['run_id'],selected_frames=len(frames),committed_frames=len(records),
            successful_frames=sum(r['status']=='ok' for r in records.values()),failed_frames=sum(r['status']=='error' for r in records.values()),
            resumed_frames=initial,new_frames=new_count,worker_pid=os.getpid(),load_and_verification_seconds=load_seconds,
            worker_wall_seconds=time.perf_counter()-started,completed_at_utc=utc(),runtime_identity_sha256=canonical_sha(runtime),
            denied_network_attempts=network,frame_inference_executed=new_count>0,**memory())
        write_once(attempt/'worker-complete.json',result)
        progress(location,dict(base,state='complete',phase_started_unix=time.time(),completed_frames=len(records),
            successful_frames=result['successful_frames'],failed_frames=result['failed_frames'],updated_at_utc=utc()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True);parser.add_argument('--attempt',type=Path,required=True)
    args=parser.parse_args();run(args.candidate,args.attempt)


if __name__=='__main__': main()
