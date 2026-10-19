"""Fail-closed test binding, native origins, offline guard and child receipts."""
import copy
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from experiments.scripts import spotting_runtime_binding as binding
from experiments.scripts.spotting_candidate_contract import canonical_sha, sha
from experiments.scripts.spotting_runtime_guard import deny_network
from experiments.scripts.spotting_runtime_inspect import inspect_paddle
from experiments.scripts import verify_spotting_test_runtime as verifier


@pytest.fixture
def pinned_fixture(tmp_path,monkeypatch):
    registry=tmp_path/'registry';registry.mkdir()
    artifact=tmp_path/'artifacts';artifact.mkdir()
    candidates=[]
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value),encoding='utf-8')
        return dict(path=path.relative_to(tmp_path).as_posix(),sha256=sha(path))
    for ident in ('easy','paddle'):
        weight=artifact/'models'/ident;weight.parent.mkdir(exist_ok=True);weight.write_bytes(b'pinned '+ident.encode())
        wheel=artifact/(ident+'.whl');wheel.write_bytes(b'pinned wheel')
        candidates.append(dict(candidate_id=ident,configuration={'threshold':.5},configuration_sha256=canonical_sha({'threshold':.5}),
            model_sha256={ident:sha(weight)},package=dict(file_sha256={},wheel_filename=wheel.name,wheel_sha256=sha(wheel))))
    value=dict(candidates=candidates,cohort_binding={})
    candidate_path=tmp_path/'candidates.json';write(candidate_path,value)
    freeze_path=registry/(binding.NAME+'-freeze.json')
    source=tmp_path/'research-data/iiit-cvid-source/IIIT-CVid.zip';source.parent.mkdir(parents=True);source.write_bytes(b'pinned source')
    write(freeze_path,dict(selected_frames=1754,selected_objects=40063,artifacts=[],prerequisites=[],preserved_sha256={},source_zip_sha256=sha(source)))
    binding_path=registry/(binding.NAME+'-candidate-binding.json')
    write(binding_path,dict(candidate_registry=dict(sha256=sha(candidate_path)),validation_cohort_binding_preserved={},test_inputs=[],
        candidates=[{k:c[k] for k in ('candidate_id','configuration_sha256','model_sha256')} for c in candidates]))
    evidence={}
    for suffix in ('-verified','-replay-verified'):
        path=registry/(binding.NAME+suffix+'.json');write(path,dict(freeze_receipt_sha256=sha(freeze_path)));evidence[suffix]=sha(path)
    lock=tmp_path/'lock';lock.write_bytes(b'pinned lock')
    for key,val in dict(ROOT=tmp_path,TEST=registry,REGISTRY=candidate_path,ARTIFACTS=artifact,RUNTIME_LOCK=lock,
        FREEZE_SHA=sha(freeze_path),BINDING_SHA=sha(binding_path),LOCK_SHA=sha(lock),EVIDENCE_SHA=evidence,IMPLEMENTATION=[]).items():
        monkeypatch.setattr(binding,key,val)
    monkeypatch.setattr(binding,'load_registry',lambda:copy.deepcopy(value))
    return tmp_path,artifact,candidate_path,binding_path,lock,value


def test_original_fixture_passes_and_weights_or_lock_tampering_fails(pinned_fixture):
    root,artifact,_,_,lock,_=pinned_fixture
    assert len(binding.test_binding()[0]['candidates'])==2
    weight=artifact/'models/easy';original=weight.read_bytes();weight.write_bytes(b'substituted')
    with pytest.raises(ValueError,match='identity mismatch'):
        binding.test_binding()
    weight.write_bytes(original);lock.write_bytes(b'changed version')
    with pytest.raises(ValueError,match='lock anchor'):
        binding.test_binding()


def test_internally_consistent_registry_and_binding_edit_rejects_trusted_anchor(pinned_fixture):
    _,_,candidate_path,binding_path,_,value=pinned_fixture
    value['candidates'][0]['configuration']['threshold']=.9
    value['candidates'][0]['configuration_sha256']=canonical_sha(value['candidates'][0]['configuration'])
    candidate_path.write_text(json.dumps(value))
    edited=json.loads(binding_path.read_text());edited['candidate_registry']['sha256']=sha(candidate_path)
    edited['candidates'][0]['configuration_sha256']=value['candidates'][0]['configuration_sha256']
    binding_path.write_text(json.dumps(edited))
    with pytest.raises(ValueError,match='test anchor'):
        binding.test_binding()


def test_wrong_interpreter_cannot_satisfy_locked_environment(tmp_path,monkeypatch):
    monkeypatch.setattr(binding,'VENV',tmp_path/'wrong-venv')
    with pytest.raises(ValueError,match='isolated spotting venv'):
        binding.isolated_runtime()


def test_unqualified_paddle_alias_outside_pinned_package_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(binding,'VENV',tmp_path/'venv')
    source=tmp_path/'venv/Lib/site-packages/paddleocr/tools/infer/predict_system.py'
    source.parent.mkdir(parents=True);source.write_text('native source')
    candidate=dict(package=dict(name='paddleocr',file_sha256={'paddleocr/tools/infer/predict_system.py':sha(source)}))
    modules={'tools.infer.predict_system':SimpleNamespace(__file__=str(source))}
    assert binding.assert_native_origins(candidate,modules)
    modules['tools.infer.predict_system']=SimpleNamespace(__file__=str(tmp_path/'untrusted.py'))
    with pytest.raises(ValueError,match='unexpected native module origin'):
        binding.assert_native_origins(candidate,modules)


def test_network_denial_is_exercised_and_restores_original_api(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:'restored')
    with deny_network() as attempts:
        with pytest.raises(RuntimeError,match='network disabled'):
            socket.getaddrinfo('example.invalid',443)
        with socket.socket() as client:
            with pytest.raises(RuntimeError,match='network disabled'):
                client.connect(('127.0.0.1',9))
    assert len(attempts)==2 and socket.getaddrinfo('unused',0)=='restored'


def test_effective_db_threshold_mismatch_fails_even_if_requested_config_matches():
    post=SimpleNamespace(thresh=.9,box_thresh=.6,unclip_ratio=1.5,score_mode='fast',box_type='quad',max_candidates=1000,min_size=3)
    reader=SimpleNamespace(args=SimpleNamespace(drop_score=0.),drop_score=0.,use_angle_cls=False,
        text_detector=SimpleNamespace(postprocess_op=post),text_recognizer=SimpleNamespace())
    with pytest.raises(ValueError,match='DB thresholds'):
        inspect_paddle(reader,dict(configuration=dict(constructor=dict(drop_score=0.))))


def child_fixture():
    candidate=dict(candidate_id='easy',configuration_sha256='config',model_sha256={'weight':'hash'})
    identity=dict(configuration_sha256='config',model_sha256={'weight':'hash'},snapshot_sha256=canonical_sha({}))
    receipt=dict(candidate_id='easy',status='verified',model_loading_verified=True,frame_inference_executed=False,
        identity=identity,identity_sha256=canonical_sha(identity),snapshot={},denied_network_attempts=[])
    return candidate,receipt


@pytest.mark.parametrize('field,value',[('status','failed'),('model_loading_verified',False),('candidate_id','other'),('frame_inference_executed',True),('denied_network_attempts',['download'])])
def test_child_success_requires_bound_complete_evidence(field,value):
    candidate,receipt=child_fixture();receipt[field]=value
    with pytest.raises(ValueError):
        verifier.check_child(candidate,receipt,0,{})


def test_nonzero_or_mismatched_snapshot_cannot_be_promoted_to_success():
    candidate,receipt=child_fixture()
    with pytest.raises(ValueError,match='loading failed'):
        verifier.check_child(candidate,receipt,1,{})
    receipt['snapshot']={'changed':'hash'}
    with pytest.raises(ValueError,match='snapshot'):
        verifier.check_child(candidate,receipt,0,{})
