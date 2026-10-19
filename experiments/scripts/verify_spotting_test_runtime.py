"""Verify fresh candidate loading against frozen native test; never run frames."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

from experiments.scripts.spotting_candidate_contract import ROOT, canonical_sha, sha, verify_files
from experiments.scripts.spotting_runtime_binding import (
    BINDING_SHA, FREEZE_SHA, LOCK_SHA, NAME, TEST, VENV, read_json, require, test_binding,
)


def artifact(path):
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size)


def check_child(candidate,receipt,exit_code,snapshot):
    require(exit_code==0 and receipt.get('status')=='verified' and receipt.get('model_loading_verified') is True,
            'candidate loading failed: '+candidate['candidate_id'])
    require(receipt.get('candidate_id')==candidate['candidate_id'] and receipt.get('frame_inference_executed') is False,
            'child candidate/inference identity mismatch')
    identity=receipt['identity']
    require(canonical_sha(identity)==receipt['identity_sha256'], 'child identity digest mismatch')
    require(identity['configuration_sha256']==candidate['configuration_sha256'] and identity['model_sha256']==candidate['model_sha256'], 'child weights/config mismatch')
    require(receipt['snapshot']==snapshot and identity['snapshot_sha256']==canonical_sha(snapshot), 'child snapshot mismatch')
    require(not receipt['denied_network_attempts'], 'child attempted network access')
    return receipt['identity_sha256']


def run_child(candidate,attempt,env,snapshot,timeout=600):
    ident=candidate['candidate_id']
    child_receipt=attempt/(ident+'.json')
    stdout,stderr=attempt/(ident+'.stdout.txt'),attempt/(ident+'.stderr.txt')
    command=[str(VENV/'Scripts/python.exe'),'-s','-m','experiments.scripts.spotting_runtime_worker',
             '--candidate',ident,'--receipt',str(child_receipt)]
    print('Loading frozen candidate in fresh process:',ident,flush=True)
    with stdout.open('x',encoding='utf-8') as out,stderr.open('x',encoding='utf-8') as err:
        result=subprocess.run(command,cwd=ROOT,env=env,stdout=out,stderr=err,timeout=timeout,check=False)
    require(child_receipt.exists(), 'child did not write a fresh receipt: '+ident)
    child=read_json(child_receipt)
    fingerprint=check_child(candidate,child,result.returncode,snapshot)
    return dict(candidate_id=ident,identity_sha256=fingerprint,effective=child['identity']['effective'],
        basic_runtime=child['basic_runtime'],native_binary_fingerprint=child['identity']['native_binaries']['fingerprint_sha256'],
        native_binary_count=child['identity']['native_binaries']['file_count'],
        loaded_native_source_count=len(child['identity']['loaded_native_sources']),
        wall_seconds=child['wall_seconds'],pid=child['pid'],exit_code=result.returncode,
        child=artifact(child_receipt),stdout=artifact(stdout),stderr=artifact(stderr))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seal',action='store_true',help='exclusively publish verified registry receipt after success')
    parser.add_argument('--repeat-of',type=Path,help='require same complete candidate identity fingerprints as prior attempt')
    args=parser.parse_args()
    registry,binding,snapshot=test_binding()
    attempt=ROOT/'experiments/outputs/spotting-test-runtime-261014'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    attempt.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ);env.update(registry['cpu_environment']);env.pop('PYTHONPATH',None);env['PYTHONNOUSERSITE']='1'
    try:
        pip=subprocess.run([str(VENV/'Scripts/python.exe'),'-m','pip','check'],cwd=ROOT,env=env,
                           capture_output=True,text=True,timeout=120,check=False)
        (attempt/'pip-check.txt').write_text(pip.stdout+pip.stderr,encoding='utf-8')
        require(pip.returncode==0, 'isolated runtime pip check failed')
        rows=[run_child(c,attempt,env,snapshot) for c in registry['candidates']]
        require(len({r['candidate_id'] for r in rows})==2 and len({r['pid'] for r in rows})==2, 'fresh candidate coverage failed')
        repeat=None
        if args.repeat_of:
            previous=read_json(args.repeat_of)
            require(previous['model_loading_verified'] is True and previous['snapshot']==snapshot, 'repeat baseline invalid')
            require({r['candidate_id']:r['identity_sha256'] for r in previous['candidates']}==
                    {r['candidate_id']:r['identity_sha256'] for r in rows}, 'fresh-process repeat fingerprint mismatch')
            repeat=artifact(args.repeat_of.resolve())
        verify_files(snapshot,ROOT)
        result=dict(schema='iiit_cvid_test_bound_spotting_runtime_verification_v1',
            completed_at_utc=datetime.now(timezone.utc).isoformat(),model_loading_verified=True,
            frame_inference_executed=False,test_freeze_sha256=FREEZE_SHA,test_binding_sha256=BINDING_SHA,
            runtime_lock_sha256=LOCK_SHA,selected_frames=1754,selected_objects=40063,candidate_count=2,
            candidates=rows,snapshot=snapshot,pip_check=artifact(attempt/'pip-check.txt'),
            repeat_baseline=repeat,repeat_identity_verified=repeat is not None,
            limits=['actual offline loading and native state inspected; no image inference/accuracy/latency result',
                    'Python socket/DNS denial, not OS isolation or all native-DLL network attestation',
                    'Windows CPU runtime and exact code/files only; rerun preflight on any environment change',
                    'frozen annotation/exposure/source and packaged precision/grouping limits unchanged'],
            next_step='same-cohort comparison with new run identity; no validation resume or test tuning')
        final=attempt/'verification.json'
        with final.open('x',encoding='utf-8') as stream:
            json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        if args.seal:
            require(repeat is not None, 'seal requires a verified fresh-process repeat')
            target=TEST/'iiit-cvid-spotting-test-runtime-261014.json'
            with target.open('xb') as stream:
                stream.write(final.read_bytes())
        print(json.dumps(dict(status='verified',receipt=str(final),model_loading_verified=True,
                              repeat_identity_verified=repeat is not None,frame_inference_executed=False)),flush=True)
    except Exception as exc:
        failure=attempt/'failure.json'
        with failure.open('x',encoding='utf-8') as stream:
            json.dump(dict(status='failed',error=f'{type(exc).__name__}: {exc}',model_loading_verified=False,
                           frame_inference_executed=False),stream,indent=2)
        print('Runtime verification failed; retained evidence:',failure,flush=True)
        raise


if __name__=='__main__':
    main()
