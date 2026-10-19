"""Load predictor with exactly the sealed runtime identity, without changing helpers."""
from pathlib import Path
import os
import sys

from experiments.scripts.spotting_candidate_contract import ROOT,canonical_sha,configure_environment,verify_candidate,verify_files
from experiments.scripts.spotting_runtime_binding import test_binding,isolated_runtime,assert_native_origins,require
from experiments.scripts.spotting_runtime_fingerprint import installed_binary_snapshot,interpreter_identity,native_fingerprint
from experiments.scripts.spotting_runtime_inspect import inspect_reader
from experiments.scripts.spotting_runtime_worker import trace_torch_weights


def load_for_inference(candidate_id,sealed):
    registry,_,snapshot=test_binding();packages=isolated_runtime()
    candidate=next(c for c in registry['candidates'] if c['candidate_id']==candidate_id)
    configure_environment(registry);verify_candidate(candidate,registry,installed=True)
    require(not any(n in sys.modules for n in ('torch','paddle','easyocr','paddleocr')),'engines imported before inference loading')
    interpreter=interpreter_identity();pre_binary=installed_binary_snapshot()
    with trace_torch_weights(candidate) as weights:
        from experiments.scripts.spotting_candidate_adapters import load_candidate
        predictor,basic=load_candidate(candidate)
        effective=inspect_reader(candidate,predictor)
    origins=assert_native_origins(candidate,dict(sys.modules));binaries=native_fingerprint()
    require(all(pre_binary.get(n)==h for n,h in binaries['files'].items()),'binary changed during inference load')
    identity=dict(candidate_id=candidate_id,configuration_sha256=candidate['configuration_sha256'],model_sha256=candidate['model_sha256'],
        snapshot_sha256=canonical_sha(snapshot),interpreter=interpreter,environment={k:os.environ[k] for k in registry['cpu_environment']},
        preload_native_binaries=pre_binary,pre_post_native_binaries_identical=True,packages=packages,effective=effective,
        loaded_native_sources=origins,native_binaries=binaries,consumed_torch_checkpoints=weights)
    expected=next(c for c in sealed['candidates'] if c['candidate_id']==candidate_id)['identity_sha256']
    require(canonical_sha(identity)==expected,'actual inference runtime differs from sealed identity')
    verify_files(snapshot,ROOT);verify_files(pre_binary,Path(sys.prefix))
    return predictor,candidate,identity,basic


def verify_after(candidate,predictor,identity):
    verify_candidate(candidate,test_binding()[0],installed=True)
    require(inspect_reader(candidate,predictor)==identity['effective'],'effective settings changed during inference')
    verify_files(identity['preload_native_binaries'],Path(sys.prefix))
    require(interpreter_identity()==identity['interpreter'],'interpreter changed during inference')
