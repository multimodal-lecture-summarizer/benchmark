"""Fresh isolated child: verify identities, deny downloads and load one candidate."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from experiments.scripts.spotting_candidate_contract import (
    ARTIFACTS, ROOT, canonical_sha, configure_environment, sha, verify_candidate, verify_files,
)
from experiments.scripts.spotting_runtime_binding import (
    assert_native_origins, isolated_runtime, require, test_binding,
)
from experiments.scripts.spotting_runtime_guard import deny_network
from experiments.scripts.spotting_runtime_fingerprint import (
    installed_binary_snapshot, interpreter_identity, native_fingerprint,
)
from experiments.scripts.spotting_runtime_inspect import inspect_reader


@contextmanager
def trace_torch_weights(candidate):
    if candidate['candidate_id']!='easyocr_craft_english_g2':
        yield []
        return
    import torch
    original,observed=torch.load,[]
    def load(path,*args,**kwargs):
        target=Path(path).resolve()
        require(target.is_relative_to((ARTIFACTS/'models').resolve()), 'unexpected Torch checkpoint path')
        relative=target.relative_to((ARTIFACTS/'models').resolve()).as_posix()
        require(relative in candidate['model_sha256'] and sha(target)==candidate['model_sha256'][relative], 'Torch consumed checkpoint mismatch')
        observed.append(dict(path=str(target),sha256=sha(target),map_location=kwargs.get('map_location'),weights_only=kwargs.get('weights_only')))
        return original(path,*args,**kwargs)
    try:
        torch.load=load
        yield observed
    finally:
        torch.load=original


def verify_one(ident):
    registry,binding,snapshot=test_binding()
    packages=isolated_runtime()
    candidate=next(c for c in registry['candidates'] if c['candidate_id']==ident)
    configure_environment(registry)
    verify_candidate(candidate,registry,installed=True)
    require(not any(n in sys.modules for n in ('torch','paddle','easyocr','paddleocr')), 'engines imported before offline guard')
    interpreter=interpreter_identity()
    pre_binary=installed_binary_snapshot()
    with deny_network() as denied:
        # Install download denial before importing the engine or its backend.
        with trace_torch_weights(candidate) as weights:
            from experiments.scripts.spotting_candidate_adapters import load_candidate
            predictor,basic_runtime=load_candidate(candidate)
            effective=inspect_reader(candidate,predictor)
        require(not denied, 'network attempt during model loading')
        origins=assert_native_origins(candidate,dict(sys.modules))
        binaries=native_fingerprint()
        require(all(pre_binary.get(n)==h for n,h in binaries['files'].items()), 'native binary changed during engine import')
    if ident=='easyocr_craft_english_g2':
        require(len(weights)==2 and {Path(w['path']).name for w in weights}=={'craft_mlt_25k.pth','english_g2.pth'}, 'Torch checkpoint coverage mismatch')
    verify_candidate(candidate,registry,installed=True)
    verify_files(snapshot,ROOT)
    verify_files(pre_binary,Path(sys.prefix))
    require(interpreter_identity()==interpreter, 'interpreter changed during loading')
    require(all(os.environ.get(k)==v for k,v in registry['cpu_environment'].items()), 'CPU environment changed during loading')
    identity=dict(candidate_id=ident,configuration_sha256=candidate['configuration_sha256'],
        model_sha256=candidate['model_sha256'],snapshot_sha256=canonical_sha(snapshot),
        interpreter=interpreter,environment={k:os.environ[k] for k in registry['cpu_environment']},
        preload_native_binaries=pre_binary,pre_post_native_binaries_identical=True,
        packages=packages,effective=effective,loaded_native_sources=origins,native_binaries=binaries,
        consumed_torch_checkpoints=weights)
    return dict(status='verified',candidate_id=ident,model_loading_verified=True,frame_inference_executed=False,
        identity=identity,identity_sha256=canonical_sha(identity),basic_runtime=basic_runtime,
        snapshot=snapshot,python=sys.version,executable=sys.executable,prefix=sys.prefix,platform=platform.platform(),
        environment={k:os.environ[k] for k in registry['cpu_environment']},denied_network_attempts=denied,
        network_guard='Python socket/DNS APIs only; not operating-system/native-DLL isolation')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    started=time.perf_counter()
    try:
        result=verify_one(args.candidate)
    except Exception as exc:
        result=dict(status='failed',candidate_id=args.candidate,model_loading_verified=False,
                    frame_inference_executed=False,error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc())
    result.update(pid=os.getpid(),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-started)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    with args.receipt.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(dict(candidate_id=args.candidate,status=result['status'],wall_seconds=result['wall_seconds'])),flush=True)
    if result['status']!='verified':
        raise SystemExit(1)


if __name__=='__main__':
    main()
