"""Denominator, unlabelled prediction, influence and immutable-bundle contracts."""
import copy

import pytest

from experiments.scripts.cvid_test_scoring import paired_cluster_bootstrap, score_test_endpoints
from experiments.scripts.cvid_test_source import annotation_issues
from experiments.scripts import freeze_cvid_test_spotting as test_freezer
from experiments.scripts import freeze_iiit_cvid_spotting as validation_freezer
from experiments.scripts.freeze_cvid_test_spotting import verify_snapshot, write_bundle


def gt(ident='kept', course='3'):
    return dict(frame_id=ident,course=course,source_group=course+'/1',width=100,height=100,
                objects=[dict(object_id=ident+'#0',bbox_xyxy=[10,10,30,30],text='omega')])


def record(ident, text='omega'):
    return dict(frame_id=ident,status='ok',predictions=[
        dict(text=text,polygon=[[10,10],[30,10],[30,30],[10,30]])])


def test_uncertain_text_and_metadata_do_not_authorize_geometry_or_semantic_repair():
    assert annotation_issues('omega',[10,10,30,30],'0',100,100)==[]
    assert annotation_issues('*',[0,0,100,100],'0',100,100)==[]
    assert annotation_issues('jle',[-2,4,28,19],'0',1920,1090)==['outside_or_nonpositive_box']
    assert annotation_issues(' \t',[10,10,30,30],'1',100,100)==['blank_transcription','unresolved_difficult_flag']


def test_correct_extra_visible_text_still_fp_against_selective_released_labels():
    pred=record('kept')
    pred['predictions'].append(dict(text='visible but unannotated',polygon=[[60,60],[80,60],[80,80],[60,80]]))
    result=score_test_endpoints([gt()],[pred],[])['primary']
    assert result['overall']['spotting']['tp']==1
    assert result['overall']['spotting']['fp']==1
    assert result['overall']['detection']['fp']==1
    assert result['overall']['spotting']['recall']==1


def test_influence_removes_whole_frames_keeps_failures_and_never_rewrites_labels():
    refs=[gt(),gt('flagged','7'),gt('failure','10')]
    preds=[record('kept','amazon'),record('flagged')]
    original=copy.deepcopy((refs,preds))
    result=score_test_endpoints(refs,preds,['flagged'])
    a,b=result['primary'],result['observed_flag_frame_influence']
    assert a['selected_frames']==3 and a['failed_frames']==1
    assert a['overall']['spotting']['tp']==1 and a['overall']['spotting']['fn']==2
    assert b['selected_frames']==2 and b['failed_frames']==1
    assert b['overall']['spotting']['tp']==0 and b['overall']['spotting']['fp']==1
    assert b['overall']['spotting']['fn']==2
    assert (refs,preds)==original


def test_sensitivity_cannot_hide_extra_duplicate_or_malformed_primary_records():
    for preds in ([record('kept'),record('extra')],[record('kept'),record('kept')],
                  [dict(frame_id='kept',status='ok',predictions=[dict(text=None)])]):
        with pytest.raises(ValueError):
            score_test_endpoints([gt()],preds,['kept'])
    with pytest.raises(ValueError,match='exclusion'):
        score_test_endpoints([gt()],[],['unknown'])


def test_paired_bootstrap_pools_counts_and_is_order_independent():
    refs=[gt('a','3'),gt('b','7')]
    refs[1]['objects']=[dict(refs[1]['objects'][0],object_id='b#'+str(i)) for i in range(3)]
    a=score_test_endpoints(refs,[],[])['primary']['frames']
    b=score_test_endpoints(refs,[record('a')],[])['primary']['frames']
    result=paired_cluster_bootstrap(a,b,draws=200)
    assert result==paired_cluster_bootstrap(list(reversed(a)),list(reversed(b)),draws=200)
    assert result['observed']==pytest.approx(2/5)
    assert paired_cluster_bootstrap(b,a,draws=200)['observed']==pytest.approx(-2/5)
    assert result['groups']==['3','7'] and result['interval_95']==[0.,1.]
    with pytest.raises(ValueError,match='IDs'):
        paired_cluster_bootstrap(a,b[:-1],draws=200)
    changed=copy.deepcopy(b);changed[0]['course']='different'
    with pytest.raises(ValueError,match='cluster'):
        paired_cluster_bootstrap(a,changed,draws=200)


def test_frozen_bundle_preflight_rejects_before_partial_write_and_replay_is_identical(tmp_path,monkeypatch):
    monkeypatch.setattr(test_freezer,'ROOT',tmp_path)
    monkeypatch.setattr(validation_freezer,'ROOT',tmp_path)
    first,second=tmp_path/'first',tmp_path/'second'
    second.write_bytes(b'old')
    with pytest.raises(ValueError,match='new version'):
        write_bundle({first:b'new',second:b'changed'})
    assert not first.exists() and second.read_bytes()==b'old'
    write_bundle({first:b'new',second:b'old'},dry_run=True)
    assert not first.exists()
    write_bundle({first:b'new',second:b'old'})
    write_bundle({first:b'new',second:b'old'})
    assert first.read_bytes()==b'new'


def test_snapshot_mutation_and_outside_root_write_reject_before_mutation(tmp_path,monkeypatch):
    monkeypatch.setattr(test_freezer,'ROOT',tmp_path)
    source=tmp_path/'policy.json';source.write_bytes(b'original policy')
    snapshot={'policy.json':validation_freezer.file_sha(source)}
    verify_snapshot(snapshot)
    source.write_bytes(b'changed policy')
    with pytest.raises(ValueError,match='input changed'):
        verify_snapshot(snapshot)
    outside=tmp_path.parent/'outside-output.json'
    with pytest.raises(ValueError,match='outside benchmark'):
        write_bundle({tmp_path/'good':b'new',outside:b'new'})
    assert not (tmp_path/'good').exists() and not outside.exists()
