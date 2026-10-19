"""Atomic/resumable inference evidence without rerunning or dropping frames."""
import copy
import os

import pytest

from experiments.scripts import spotting_comparison_io as io
from experiments.scripts.spotting_candidate_contract import canonical_sha
from experiments.scripts.spotting_comparison_process import exclusive_lock,memory


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(io,'OUT',tmp_path)
    frame=dict(frame_id='Frames/test/3/1/frame.png',image_sha256='source')
    identity=dict(run_id='frozen-run')
    record=dict(frame_id=frame['frame_id'],status='ok',error=None,predictions=[],wall_seconds=1.,origin='predictor_attempt')
    return identity,frame,record


def test_atomic_immutable_commit_and_exact_resume(setup):
    identity,frame,record=setup
    io.commit(identity,frame,'candidate',record)
    io.commit(identity,frame,'candidate',record)
    assert io.load_checkpoints(identity,[frame],'candidate')=={frame['frame_id']:record}
    changed=dict(record,predictions=[dict(text='different',polygon=[])])
    with pytest.raises(ValueError,match='immutable artifact differs'):
        io.commit(identity,frame,'candidate',changed)
    assert io.load_checkpoints(identity,[frame],'candidate')[frame['frame_id']]==record


@pytest.mark.parametrize('field,value',[('run_id','other'),('image_sha256','substituted'),('candidate_id','other')])
def test_stale_resume_rejected(setup,field,value):
    identity,frame,record=setup
    checkpoint=dict(run_id=identity['run_id'],candidate_id='candidate',image_sha256='source',record=record,record_sha256=canonical_sha(record))
    checkpoint[field]=value
    with pytest.raises(ValueError,match='identity mismatch'):
        io.validate_checkpoint(checkpoint,identity,frame,'candidate')


def test_payload_tampering_and_partial_failed_frame_reject(setup):
    identity,frame,record=setup
    checkpoint=dict(run_id=identity['run_id'],candidate_id='candidate',image_sha256='source',record=copy.deepcopy(record),record_sha256=canonical_sha(record))
    checkpoint['record']['status']='error'
    with pytest.raises(ValueError,match='digest'):
        io.validate_checkpoint(checkpoint,identity,frame,'candidate')
    failed=dict(record,status='error',error='engine failure',predictions=[dict(text='partial',polygon=[])])
    with pytest.raises(ValueError,match='failure record'):
        io.commit(identity,frame,'candidate',failed)


def test_completed_pending_bytes_recover_without_new_predictor_attempt(setup):
    identity,frame,record=setup
    target=io.checkpoint_path('candidate',frame['frame_id']);target.parent.mkdir(parents=True)
    item=dict(run_id=identity['run_id'],candidate_id='candidate',image_sha256='source',record=record,record_sha256=canonical_sha(record))
    pending=target.with_name(target.name+'.pending-crash');pending.write_bytes(io.encode(item))
    loaded=io.load_checkpoints(identity,[frame],'candidate')
    assert loaded[frame['frame_id']]==record and target.exists() and not pending.exists()


def test_pending_and_extra_records_never_silently_filtered(setup):
    identity,frame,record=setup
    io.commit(identity,frame,'candidate',record)
    with pytest.raises(ValueError,match='extra or duplicate'):
        io.load_checkpoints(identity,[],'candidate')


def test_run_lock_prevents_concurrent_execution_and_releases(tmp_path):
    path=tmp_path/'execution.lock'
    with exclusive_lock(path):
        with pytest.raises(ValueError,match='another run'):
            with exclusive_lock(path): pass
    assert path.exists() and not path.with_name(path.name+'.owner.json').exists()
    with exclusive_lock(path): pass
    assert memory()['process_peak_rss_bytes_to_date'] is None or memory()['process_peak_rss_bytes_to_date']>0


def test_systemic_guard_stops_identical_errors_but_not_after_success():
    from experiments.scripts.spotting_comparison_worker import systemic_failure
    recent=[];error=dict(status='error',error='TypeError: API mismatch')
    assert not systemic_failure(recent,error,3)
    assert not systemic_failure(recent,error,3)
    assert systemic_failure(recent,error,3)
    assert not systemic_failure(recent,dict(status='ok'),3) and recent==[]


def test_atomic_binary_aggregate_preserves_committed_bytes(tmp_path):
    path=tmp_path/'predictions.jsonl';data=b'{"frame_id":"one"}\n'
    io.write_bytes_once(path,data);io.write_bytes_once(path,data)
    with pytest.raises(ValueError,match='immutable artifact differs'):
        io.write_bytes_once(path,b'partial')
    assert path.read_bytes()==data
