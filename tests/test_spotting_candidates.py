"""Frozen identity and output-contract tests; no model inference."""
import copy
import json

import pytest

from experiments.scripts.spotting_candidate_adapters import adapt_regions, frame_record
from experiments.scripts.spotting_candidate_contract import (
    bind_run_identity, canonical_sha, load_registry, sha, verify_files,
)


def test_native_coordinates_and_low_confidence_text_are_retained():
    polygon=[[1.25,2.75],[9.5,2.75],[9.5,8.25],[1.25,8.25]]
    rows=adapt_regions([(polygon,'a*2',0.001),(polygon,'',0.0)])
    assert rows[0]['polygon']==polygon
    assert rows[0]['text']=='a*2' and rows[0]['recognition_confidence']==0.001
    assert rows[1]['text']=='' and len(rows)==2


def test_adapter_does_not_clip_invalid_native_coordinates():
    rows=adapt_regions([([[-1,2],[9,2],[9,8]],'x',0.8)])
    assert rows[0]['polygon'][0][0]==-1


def test_empty_success_is_distinct_from_failure():
    good=frame_record('frame','unused',lambda _:[])
    def fail(_):
        raise RuntimeError('recognizer failed')
    bad=frame_record('frame','unused',fail)
    assert good['status']=='ok' and good['error'] is None and good['predictions']==[]
    assert bad['status']=='error' and bad['predictions']==[] and 'recognizer failed' in bad['error']


@pytest.mark.parametrize('confidence',[float('nan'),float('inf')])
def test_malformed_confidence_rejects_observation(confidence):
    with pytest.raises(ValueError,match='malformed'):
        adapt_regions([([[1,2],[3,2],[3,4]],'x',confidence)])


def test_missing_or_substituted_model_and_dictionary_fail(tmp_path):
    model=tmp_path/'model';model.write_bytes(b'actual model')
    dictionary=tmp_path/'en_dict.txt';dictionary.write_text('a\nb\n')
    hashes={'model':sha(model),'en_dict.txt':sha(dictionary)}
    verify_files(hashes,tmp_path)
    model.write_bytes(b'substitute')
    with pytest.raises(ValueError,match='identity mismatch'):
        verify_files(hashes,tmp_path)
    model.write_bytes(b'actual model');dictionary.unlink()
    with pytest.raises(ValueError,match='en_dict'):
        verify_files(hashes,tmp_path)


def test_file_paths_cannot_escape_declared_root(tmp_path):
    with pytest.raises(ValueError,match='identity mismatch'):
        verify_files({'../outside':'hash'},tmp_path)


def test_changed_threshold_or_grouping_invalidates_registry(tmp_path):
    for field in ('threshold','paragraph'):
        config={'threshold':0.7,'paragraph':False}
        r={'candidates':[{'configuration':config,'configuration_sha256':canonical_sha(config)}]}
        config[field]=0.1 if field=='threshold' else True
        p=tmp_path/'registry.json';p.write_text(json.dumps(r))
        with pytest.raises(ValueError,match='configuration hash'):
            load_registry(p)


def test_resume_different_weights_or_configuration_rejected(tmp_path):
    p=tmp_path/'identity.json';identity={'model_sha':'a','config_sha':'b'}
    bind_run_identity(p,identity)
    bind_run_identity(p,identity,predictions_exist=True)
    for field in identity:
        changed=copy.deepcopy(identity);changed[field]='changed'
        with pytest.raises(ValueError,match='resume identity'):
            bind_run_identity(p,changed)


def test_unbound_existing_predictions_rejected(tmp_path):
    with pytest.raises(ValueError,match='no bound identity'):
        bind_run_identity(tmp_path/'identity.json',{'config':'a'},predictions_exist=True)
