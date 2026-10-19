"""Contract tests for ambiguity, failures and denominator-preserving spotting."""
import pytest

from experiments.scripts.spotting_metrics import (
    maximum_matching, normalize_text, prediction_polygon, score_cohort, score_frame,
)


def ground_truth():
    return dict(frame_id='Frames/val/11/1/frame.png',course='11',source_group='11/1',width=100,height=100,
                objects=[dict(object_id='a',bbox_xyxy=[10,10,30,30],text='A*2')])


def prediction(text='a*2', points=None):
    return dict(text=text,polygon=points if points is not None else [[10,10],[30,10],[30,30],[10,30]])


def record(predictions, **kwargs):
    return dict(frame_id=ground_truth()['frame_id'],status='ok',predictions=predictions,**kwargs)


def test_normalization_preserves_lecture_symbols_and_exposes_casefold():
    assert normalize_text(' Ａ*２\t Straße ') == 'a*2 strasse'
    assert normalize_text(' Ａ*２\t Straße ',True) == 'A*2 Straße'
    assert normalize_text('a*2') != normalize_text('a2')
    assert normalize_text('café') != normalize_text('cafe')


def test_augmenting_paths_avoid_greedy_under_count():
    assert len(maximum_matching([[0,1],[0]]))==2
    assert len(maximum_matching([[0],[0]]))==1


def test_correct_detection_with_wrong_or_empty_text_is_not_spotting_tp():
    for text in ('wrong',''):
        r=score_frame(ground_truth(),record([prediction(text)]))
        assert r['detection']['tp']==1 and r['spotting']['tp']==0
        assert r['spotting']['fp']==r['spotting']['fn']==1


def test_duplicate_detection_penalized_and_order_does_not_change_counts():
    preds=[prediction(),prediction('wrong')]
    first=score_frame(ground_truth(),record(preds))
    assert first==score_frame(ground_truth(),record(list(reversed(preds))))
    assert first['spotting']['tp']==1 and first['spotting']['fp']==1


def test_iou_equal_half_fails_strict_threshold():
    points=[[10,10],[50,10],[50,30],[10,30]]
    assert score_frame(ground_truth(),record([prediction(points=points)]))['detection']['tp']==0
    points=[[10,10],[49.9,10],[49.9,30],[10,30]]
    assert score_frame(ground_truth(),record([prediction(points=points)]))['spotting']['tp']==1


@pytest.mark.parametrize('points', [
    [[-1,10],[30,10],[30,30]], [[10,10],[101,10],[30,30]],
    [[10,10],[30,30],[10,30],[30,10]], [[10,10],[10,10],[10,10]],
    [[10,10],[float('nan'),10],[30,30]], [[True,10],[30,10],[30,30]],
    [[10,10],[10**400,10],[30,30]], None,
])
def test_invalid_geometry_is_fp_without_clipping(points):
    assert prediction_polygon(points,100,100) is None
    pred=prediction();pred['polygon']=points
    r=score_frame(ground_truth(),record([pred]))
    assert r['invalid_predictions']==1
    assert r['detection']['fp']==r['spotting']['fp']==1
    assert r['detection']['fn']==1


def test_missing_frame_is_retained_as_failure_and_all_gt_fn():
    r=score_cohort([ground_truth()],[])
    assert r['selected_frames']==r['failed_frames']==1
    assert r['overall']['spotting']['fn']==1
    assert r['failure_ledger'][0]['error']=='missing_record'


def test_partial_failed_frame_rejected():
    r=dict(frame_id=ground_truth()['frame_id'],status='error',error='oom',predictions=[prediction()])
    with pytest.raises(ValueError,match='no partial'):
        score_frame(ground_truth(),r)


def test_extra_duplicate_and_malformed_records_rejected():
    r=record([])
    with pytest.raises(ValueError,match='duplicate'):
        score_cohort([ground_truth()],[r,r])
    with pytest.raises(ValueError,match='extra'):
        score_cohort([ground_truth()],[dict(r,frame_id='extra')])
    with pytest.raises(ValueError,match='needs text'):
        score_frame(ground_truth(),record([dict(polygon=[[1,1],[2,1],[2,2]])]))


def test_pooled_hmean_uses_counts_not_mean_frame_f1():
    a=ground_truth();b=dict(a,frame_id='other',objects=[dict(o,object_id=str(i)) for i in range(3) for o in a['objects']])
    result=score_cohort([a,b],[record([prediction()]),dict(frame_id='other',status='ok',predictions=[])])
    assert result['overall']['spotting']['hmean']==pytest.approx(2/5)
    assert result['successful_frames']==2 and result['failed_frames']==0
